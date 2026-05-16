"""CapSolver captcha-solving service, shared by every browser navigation lane.

One engine, three consumers: the Playwright preview lane, the Playwright
interactive lane, and the Kimi WebBridge real-browser lane all reach captcha
solving through this service (directly, via the `/actions/captcha/*` endpoints,
or via the `solve_*_captcha` DeepAgents tools).

Contract verified against https://docs.capsolver.com (2026-05-15):

* `POST {base}/createTask`  body `{clientKey, task:{type, ...}}`
  -> `{errorId, errorCode, errorDescription, taskId, solution?}`
* `POST {base}/getTaskResult` body `{clientKey, taskId}`
  -> `{errorId, status, solution}`  (`status` in `idle|processing|ready`)
* `ImageToTextTask` returns `solution.text` INLINE in the createTask
  response — no polling. Token tasks (reCAPTCHA/hCaptcha/Turnstile) return a
  `taskId` and must be polled until `status == "ready"`.

The `clientKey` is a secret; it is never logged and is redacted from any error
string surfaced to the caller.
"""

from __future__ import annotations

import re
import time
from typing import Any, Literal, Protocol

import httpx
import structlog
from pydantic import BaseModel, Field

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.resilience import retry_transient_http
from cognitive_os.tools.policy import ToolAuditRecord, ToolRiskLevel, record_audit_event

_log = structlog.get_logger(__name__)

# Any `CAP-...` looking token, plus generic key/clientKey assignments.
_SECRET_RE = re.compile(r"(?i)(client_?key|api[_-]?key)\s*[:=]\s*\S+|CAP-[A-Za-z0-9]{16,}")

CaptchaKind = Literal[
    "image_to_text",
    "recaptcha_v2",
    "recaptcha_v3",
    "hcaptcha",
    "turnstile",
]

_TOKEN_TASK_TYPES: dict[str, str] = {
    "recaptcha_v2": "ReCaptchaV2TaskProxyLess",
    "recaptcha_v3": "ReCaptchaV3TaskProxyLess",
    "hcaptcha": "HCaptchaTaskProxyLess",
    "turnstile": "AntiTurnstileTaskProxyLess",
}


class CaptchaSolverError(RuntimeError):
    """Raised when a captcha cannot be solved."""


def _redact(value: str) -> str:
    return _SECRET_RE.sub("[REDACTED]", value)


class CaptchaSolution(BaseModel):
    kind: CaptchaKind
    # For image_to_text this is the recognized text; for token captchas it is
    # the gRecaptchaResponse / token the caller injects into the page.
    token: str
    task_id: str | None = None
    raw_solution: dict[str, Any] = Field(default_factory=dict)


class CaptchaStatus(BaseModel):
    status: Literal["disabled", "blocked", "ready"]
    reason: str | None = None
    base_url: str


class ImageCaptchaRequest(BaseModel):
    image_base64: str = Field(min_length=1, max_length=4_000_000)


class TokenCaptchaRequest(BaseModel):
    kind: Literal["recaptcha_v2", "recaptcha_v3", "hcaptcha", "turnstile"]
    website_url: str = Field(min_length=1, max_length=2000)
    website_key: str = Field(min_length=1, max_length=2000)
    page_action: str | None = Field(default=None, max_length=120)


class CaptchaProvider(Protocol):
    """Transport to CapSolver. Implementations must not raise for HTTP 200 with
    an `errorId != 0` — they return the parsed dict and let the service decide."""

    def create_task(self, task: dict[str, Any]) -> dict[str, Any]: ...

    def get_task_result(self, task_id: str) -> dict[str, Any]: ...


class CapSolverHttpProvider:
    """Real CapSolver transport."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    @property
    def _client_key(self) -> str:
        return self._settings.capsolver_api_key.get_secret_value()

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._settings.capsolver_base_url.rstrip('/')}{path}"
        try:
            response = retry_transient_http(
                lambda: httpx.post(
                    url,
                    json={"clientKey": self._client_key, **payload},
                    timeout=self._settings.http_timeout_seconds,
                )
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise CaptchaSolverError(f"CapSolver request failed: {_redact(str(exc))}") from exc
        except ValueError as exc:
            raise CaptchaSolverError("CapSolver returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise CaptchaSolverError("CapSolver returned a non-object payload.")
        return data

    def create_task(self, task: dict[str, Any]) -> dict[str, Any]:
        return self._post("/createTask", {"task": task})

    def get_task_result(self, task_id: str) -> dict[str, Any]:
        return self._post("/getTaskResult", {"taskId": task_id})


class FakeCaptchaProvider:
    """Deterministic provider for tests — no network."""

    def __init__(
        self,
        *,
        create_response: dict[str, Any] | None = None,
        result_responses: list[dict[str, Any]] | None = None,
    ) -> None:
        self._create_response = create_response or {"errorId": 0, "taskId": "fake-task"}
        self._result_responses = list(result_responses or [])
        self.create_calls: list[dict[str, Any]] = []
        self.result_calls: list[str] = []

    def create_task(self, task: dict[str, Any]) -> dict[str, Any]:
        self.create_calls.append(task)
        return self._create_response

    def get_task_result(self, task_id: str) -> dict[str, Any]:
        self.result_calls.append(task_id)
        if self._result_responses:
            return self._result_responses.pop(0)
        return {"errorId": 0, "status": "ready", "solution": {"gRecaptchaResponse": "tok"}}


def _check_capsolver_error(payload: dict[str, Any]) -> None:
    if payload.get("errorId"):
        code = payload.get("errorCode") or "unknown"
        desc = _redact(str(payload.get("errorDescription") or ""))
        raise CaptchaSolverError(f"CapSolver error {code}: {desc}")


def _extract_token(solution: dict[str, Any]) -> str:
    """Token captchas put the answer under one of several known keys."""
    for key in ("gRecaptchaResponse", "token", "text"):
        value = solution.get(key)
        if isinstance(value, str) and value:
            return value
    msg = "CapSolver solution did not contain a usable token."
    raise CaptchaSolverError(msg)


class CaptchaSolverService:
    """Capability-gated facade in front of CapSolver."""

    def __init__(
        self,
        provider: CaptchaProvider | None = None,
        app_settings: Settings = settings,
        *,
        sleep: Any = time.sleep,
    ) -> None:
        self._settings = app_settings
        self._provider = provider
        self._sleep = sleep

    def _resolve_provider(self) -> CaptchaProvider:
        if self._provider is None:
            self._provider = CapSolverHttpProvider(self._settings)
        return self._provider

    def status(self) -> CaptchaStatus:
        base = self._settings.capsolver_base_url
        if not self._settings.enable_captcha_solving:
            return CaptchaStatus(
                status="disabled",
                reason="ENABLE_CAPTCHA_SOLVING is false.",
                base_url=base,
            )
        key = self._settings.capsolver_api_key.get_secret_value()
        if not key or "CHANGEME" in key:
            return CaptchaStatus(
                status="blocked",
                reason="CAPSOLVER_API_KEY is not configured.",
                base_url=base,
            )
        return CaptchaStatus(status="ready", reason=None, base_url=base)

    def _require_ready(self) -> None:
        current = self.status()
        if current.status != "ready":
            raise CaptchaSolverError(current.reason or "Captcha solving is not available.")

    def _audit(self, kind: str, result: str, requested_by: str | None) -> None:
        try:
            record_audit_event(
                ToolAuditRecord(
                    tool_name=f"captcha.{kind}",
                    risk_level=ToolRiskLevel.EXTERNAL_ACTION,
                    args_redacted={"kind": kind},
                    result_summary=result,
                    actor_id=requested_by,
                )
            )
        except Exception as exc:
            _log.warning("captcha_audit_failed", kind=kind, error=str(exc))

    def solve_image(
        self,
        image_base64: str,
        *,
        requested_by: str | None = None,
    ) -> CaptchaSolution:
        cleaned = (image_base64 or "").strip()
        if not cleaned:
            raise CaptchaSolverError("image_base64 must not be empty.")
        # Defend against callers passing a data URI; CapSolver wants raw base64.
        if cleaned.startswith("data:") and "," in cleaned:
            cleaned = cleaned.split(",", 1)[1]
        self._require_ready()
        provider = self._resolve_provider()
        try:
            payload = provider.create_task({"type": "ImageToTextTask", "body": cleaned})
            _check_capsolver_error(payload)
            solution = payload.get("solution") or {}
            text = solution.get("text")
            if not isinstance(text, str) or not text:
                raise CaptchaSolverError("CapSolver ImageToText returned no text.")
        except CaptchaSolverError:
            self._audit("image_to_text", "error", requested_by)
            raise
        self._audit("image_to_text", "ok", requested_by)
        return CaptchaSolution(kind="image_to_text", token=text, raw_solution=solution)

    def solve_token(
        self,
        kind: CaptchaKind,
        *,
        website_url: str,
        website_key: str,
        page_action: str | None = None,
        requested_by: str | None = None,
    ) -> CaptchaSolution:
        if kind not in _TOKEN_TASK_TYPES:
            raise CaptchaSolverError(f"{kind} is not a token captcha type.")
        if not website_url.strip() or not website_key.strip():
            raise CaptchaSolverError("website_url and website_key are required.")
        self._require_ready()
        provider = self._resolve_provider()
        task: dict[str, Any] = {
            "type": _TOKEN_TASK_TYPES[kind],
            "websiteURL": website_url.strip(),
            "websiteKey": website_key.strip(),
        }
        if kind == "recaptcha_v3":
            task["pageAction"] = (page_action or "verify").strip()
        try:
            created = provider.create_task(task)
            _check_capsolver_error(created)
            task_id = created.get("taskId")
            if not isinstance(task_id, str) or not task_id:
                raise CaptchaSolverError("CapSolver did not return a taskId.")
            solution = self._poll(provider, task_id)
            token = _extract_token(solution)
        except CaptchaSolverError:
            self._audit(kind, "error", requested_by)
            raise
        self._audit(kind, "ok", requested_by)
        return CaptchaSolution(
            kind=kind,
            token=token,
            task_id=task_id,
            raw_solution=solution,
        )

    def _poll(self, provider: CaptchaProvider, task_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self._settings.capsolver_max_poll_seconds
        interval = self._settings.capsolver_poll_interval_seconds
        while True:
            result = provider.get_task_result(task_id)
            _check_capsolver_error(result)
            status = str(result.get("status") or "")
            if status == "ready":
                solution = result.get("solution")
                if not isinstance(solution, dict):
                    raise CaptchaSolverError("CapSolver ready result had no solution.")
                return solution
            if time.monotonic() >= deadline:
                raise CaptchaSolverError(
                    f"CapSolver did not solve the captcha within "
                    f"{self._settings.capsolver_max_poll_seconds}s (task {task_id})."
                )
            self._sleep(interval)

"""Kimi WebBridge integration: drive the user's REAL browser via a local daemon.

This is a different trust model from `actions/browser_preview.py`. Playwright
preview runs headless in a throwaway profile with no cookies; Kimi WebBridge
operates on the user's actual Chrome session — with their logins. That makes
it powerful (it can read your Gmail, post on LinkedIn) AND high-risk. The
service enforces three independent gates before any call lands on the daemon:

1. `ENABLE_KIMI_WEBBRIDGE=true` — server policy.
2. Target host must match `KIMI_WEBBRIDGE_ALLOWED_DOMAINS` (empty = block all).
3. Mutating ops (click/fill/upload/evaluate/close_tab/close_session) ALSO
   require `KIMI_WEBBRIDGE_ALLOW_MUTATIONS=true`.

Every call is audited (ToolRiskLevel.EXTERNAL_ACTION) and the URL/selector is
truncated in the audit row so structured logs don't carry session-bound data.

The service NEVER talks to the Kimi cloud — only to `127.0.0.1:10086`. The
daemon owns the cloud auth.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol
from urllib.parse import urlparse

import httpx
import structlog
from pydantic import BaseModel, Field

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.resilience import retry_transient_http
from cognitive_os.tools.policy import ToolAuditRecord, ToolRiskLevel, record_audit_event

_log = structlog.get_logger(__name__)

# Operations that only read browser state — gated by domain allow-list but NOT
# by the additional `KIMI_WEBBRIDGE_ALLOW_MUTATIONS` flag.
READ_ONLY_ACTIONS = frozenset(
    {"navigate", "snapshot", "screenshot", "find_tab", "list_tabs", "save_as_pdf", "network"}
)
# Operations that change browser state.
MUTATING_ACTIONS = frozenset({"click", "fill", "evaluate", "upload", "close_tab", "close_session"})

MAX_SELECTOR_LENGTH = 512
MAX_VALUE_LENGTH = 4000


class KimiWebBridgeError(RuntimeError):
    """Raised when a WebBridge call cannot be completed."""


class WebBridgeStatus(BaseModel):
    status: Literal["disabled", "blocked", "ready"]
    reason: str | None = None
    daemon_url: str
    daemon_running: bool = False
    extension_connected: bool = False
    allow_mutations: bool = False
    allowed_domain_count: int = 0


class NavigateRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    new_tab: bool = True
    session: str | None = Field(default=None, max_length=120)
    group_title: str | None = Field(default=None, max_length=120)


class SnapshotRequest(BaseModel):
    session: str | None = Field(default=None, max_length=120)


class ScreenshotRequest(BaseModel):
    session: str | None = Field(default=None, max_length=120)
    format: Literal["png", "jpeg"] = "png"
    quality: int = Field(default=80, ge=0, le=100)
    selector: str | None = Field(default=None, max_length=MAX_SELECTOR_LENGTH)


class ClickRequest(BaseModel):
    selector: str = Field(min_length=1, max_length=MAX_SELECTOR_LENGTH)
    session: str | None = Field(default=None, max_length=120)


class FillRequest(BaseModel):
    selector: str = Field(min_length=1, max_length=MAX_SELECTOR_LENGTH)
    value: str = Field(min_length=0, max_length=MAX_VALUE_LENGTH)
    session: str | None = Field(default=None, max_length=120)


class EvaluateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=8000)
    session: str | None = Field(default=None, max_length=120)


class CloseSessionRequest(BaseModel):
    session: str | None = Field(default=None, max_length=120)


class WebBridgeCallResult(BaseModel):
    status: Literal["ok", "blocked", "error"]
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


class WebBridgeProvider(Protocol):
    """Transport: caller posts the daemon command and gets its JSON back."""

    def call(self, action: str, args: dict[str, Any], session: str | None) -> dict[str, Any]: ...

    def status_probe(self) -> dict[str, Any]: ...


class HttpWebBridgeProvider:
    """Real provider talking to the local daemon (`POST /command`)."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    def _endpoint(self, path: str) -> str:
        return f"{self._settings.kimi_webbridge_url.rstrip('/')}{path}"

    def call(self, action: str, args: dict[str, Any], session: str | None) -> dict[str, Any]:
        body: dict[str, Any] = {"action": action, "args": args}
        if session:
            body["session"] = session
        try:
            response = retry_transient_http(
                lambda: httpx.post(
                    self._endpoint("/command"),
                    json=body,
                    timeout=self._settings.kimi_webbridge_request_timeout_seconds,
                )
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise KimiWebBridgeError(f"WebBridge daemon call failed: {exc}") from exc
        except ValueError as exc:
            raise KimiWebBridgeError("WebBridge daemon returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise KimiWebBridgeError("WebBridge daemon returned a non-object payload.")
        return payload

    def status_probe(self) -> dict[str, Any]:
        # The daemon exposes /command for actions; status is a CLI concern. We
        # probe by hitting the root with a short timeout — any 2xx/4xx means
        # the HTTP layer is alive (daemon running).
        try:
            response = httpx.get(self._endpoint("/"), timeout=2.0)
        except httpx.HTTPError as exc:
            return {"running": False, "extension_connected": False, "error": str(exc)}
        running = 200 <= response.status_code < 500
        # The extension-connected bit is only exposed via the CLI; treat it as
        # "unknown but daemon reachable". The frontend can call /command with a
        # cheap `list_tabs` to confirm extension wiring.
        return {"running": running, "extension_connected": running, "status": response.status_code}


class FakeWebBridgeProvider:
    """Deterministic in-memory provider used by tests."""

    def __init__(
        self,
        *,
        responses: dict[str, dict[str, Any]] | None = None,
        raises: bool = False,
        running: bool = True,
        extension_connected: bool = True,
    ) -> None:
        self._responses = responses or {}
        self._raises = raises
        self._running = running
        self._extension_connected = extension_connected
        self.calls: list[dict[str, Any]] = []

    def call(self, action: str, args: dict[str, Any], session: str | None) -> dict[str, Any]:
        self.calls.append({"action": action, "args": args, "session": session})
        if self._raises:
            raise KimiWebBridgeError("fake webbridge failure")
        return self._responses.get(action, {"success": True, "action": action})

    def status_probe(self) -> dict[str, Any]:
        return {"running": self._running, "extension_connected": self._extension_connected}


def _host_of(url: str) -> str | None:
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
    except ValueError:
        return None
    return (parsed.hostname or "").lower() or None


def _domain_allowed(host: str, allowed: list[str]) -> bool:
    """Subdomain-aware match. A literal ``*`` entry means "allow every host".

    The wildcard is an explicit operator opt-out of the allow-list (set via
    ``KIMI_WEBBRIDGE_ALLOWED_DOMAINS=*``). It is deliberately coarse: the agent
    drives the real browser, so the operator owns this risk decision.
    """
    if not host:
        return False
    host_lower = host.lower()
    for entry in allowed:
        entry_lower = entry.strip().lower().lstrip(".")
        if not entry_lower:
            continue
        if entry_lower == "*":
            return True
        if host_lower == entry_lower or host_lower.endswith(f".{entry_lower}"):
            return True
    return False


def _audit_webbridge(
    action: str,
    args_redacted: dict[str, Any],
    actor_id: str | None,
    result: str,
) -> None:
    try:
        record_audit_event(
            ToolAuditRecord(
                tool_name=f"webbridge.{action}",
                risk_level=ToolRiskLevel.EXTERNAL_ACTION,
                args_redacted=args_redacted,
                result_summary=result,
                actor_id=actor_id,
            )
        )
    except Exception as exc:
        _log.warning("webbridge_audit_failed", action=action, error=str(exc))


def _truncate(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


class KimiWebBridgeService:
    """Capability-gated facade in front of the local WebBridge daemon."""

    def __init__(
        self,
        provider: WebBridgeProvider | None = None,
        app_settings: Settings = settings,
    ) -> None:
        self._settings = app_settings
        self._provider = provider

    def _resolve_provider(self) -> WebBridgeProvider:
        if self._provider is None:
            self._provider = HttpWebBridgeProvider(self._settings)
        return self._provider

    def status(self) -> WebBridgeStatus:
        url = self._settings.kimi_webbridge_url
        allow_mut = bool(self._settings.kimi_webbridge_allow_mutations)
        domain_count = len(self._settings.kimi_webbridge_allowed_domains)
        if not self._settings.enable_kimi_webbridge:
            return WebBridgeStatus(
                status="disabled",
                reason="ENABLE_KIMI_WEBBRIDGE is false.",
                daemon_url=url,
                allow_mutations=allow_mut,
                allowed_domain_count=domain_count,
            )
        probe = self._resolve_provider().status_probe()
        running = bool(probe.get("running"))
        extension = bool(probe.get("extension_connected"))
        if not running:
            return WebBridgeStatus(
                status="blocked",
                reason=(
                    "WebBridge daemon not reachable at "
                    f"{url}. Start it with `~/.kimi-webbridge/bin/kimi-webbridge start`."
                ),
                daemon_url=url,
                daemon_running=False,
                extension_connected=False,
                allow_mutations=allow_mut,
                allowed_domain_count=domain_count,
            )
        if domain_count == 0:
            return WebBridgeStatus(
                status="blocked",
                reason=(
                    "KIMI_WEBBRIDGE_ALLOWED_DOMAINS is empty — set explicit domains "
                    "or '*' to allow every host."
                ),
                daemon_url=url,
                daemon_running=running,
                extension_connected=extension,
                allow_mutations=allow_mut,
                allowed_domain_count=domain_count,
            )
        return WebBridgeStatus(
            status="ready",
            reason=None,
            daemon_url=url,
            daemon_running=running,
            extension_connected=extension,
            allow_mutations=allow_mut,
            allowed_domain_count=domain_count,
        )

    def _require_ready(self) -> None:
        current = self.status()
        if current.status != "ready":
            raise KimiWebBridgeError(current.reason or "WebBridge is not available.")

    def _check_action_allowed(self, action: str) -> None:
        if action in MUTATING_ACTIONS and not self._settings.kimi_webbridge_allow_mutations:
            msg = (
                f"WebBridge action {action!r} is a mutation; "
                "set KIMI_WEBBRIDGE_ALLOW_MUTATIONS=true to enable."
            )
            raise KimiWebBridgeError(msg)
        if action not in READ_ONLY_ACTIONS and action not in MUTATING_ACTIONS:
            msg = f"Unknown WebBridge action {action!r}."
            raise KimiWebBridgeError(msg)

    def _check_url_allowed(self, url: str | None) -> None:
        if url is None:
            return
        host = _host_of(url)
        if host is None:
            raise KimiWebBridgeError(f"Could not parse host from URL {url!r}.")
        if not _domain_allowed(host, list(self._settings.kimi_webbridge_allowed_domains)):
            raise KimiWebBridgeError(f"Host {host!r} is not in KIMI_WEBBRIDGE_ALLOWED_DOMAINS.")

    def navigate(
        self,
        request: NavigateRequest,
        *,
        requested_by: str | None = None,
    ) -> WebBridgeCallResult:
        self._require_ready()
        self._check_action_allowed("navigate")
        self._check_url_allowed(request.url)
        args: dict[str, Any] = {"url": request.url, "newTab": request.new_tab}
        if request.group_title:
            args["group_title"] = request.group_title
        return self._call(
            "navigate",
            args,
            session=request.session,
            audit_extra={"host": _host_of(request.url)},
            actor_id=requested_by,
        )

    def snapshot(
        self,
        request: SnapshotRequest,
        *,
        requested_by: str | None = None,
    ) -> WebBridgeCallResult:
        self._require_ready()
        self._check_action_allowed("snapshot")
        return self._call("snapshot", {}, session=request.session, actor_id=requested_by)

    def screenshot(
        self,
        request: ScreenshotRequest,
        *,
        requested_by: str | None = None,
    ) -> WebBridgeCallResult:
        self._require_ready()
        self._check_action_allowed("screenshot")
        args: dict[str, Any] = {"format": request.format, "quality": request.quality}
        if request.selector:
            args["selector"] = request.selector
        return self._call(
            "screenshot",
            args,
            session=request.session,
            audit_extra={"selector_len": len(request.selector or "")},
            actor_id=requested_by,
        )

    def click(
        self,
        request: ClickRequest,
        *,
        requested_by: str | None = None,
    ) -> WebBridgeCallResult:
        self._require_ready()
        self._check_action_allowed("click")
        return self._call(
            "click",
            {"selector": request.selector},
            session=request.session,
            audit_extra={"selector": _truncate(request.selector, 200)},
            actor_id=requested_by,
        )

    def fill(
        self,
        request: FillRequest,
        *,
        requested_by: str | None = None,
    ) -> WebBridgeCallResult:
        self._require_ready()
        self._check_action_allowed("fill")
        return self._call(
            "fill",
            {"selector": request.selector, "value": request.value},
            session=request.session,
            audit_extra={
                "selector": _truncate(request.selector, 200),
                "value_len": len(request.value),
            },
            actor_id=requested_by,
        )

    def evaluate(
        self,
        request: EvaluateRequest,
        *,
        requested_by: str | None = None,
    ) -> WebBridgeCallResult:
        self._require_ready()
        self._check_action_allowed("evaluate")
        return self._call(
            "evaluate",
            {"code": request.code},
            session=request.session,
            audit_extra={"code_len": len(request.code)},
            actor_id=requested_by,
        )

    def list_tabs(
        self,
        *,
        session: str | None = None,
        requested_by: str | None = None,
    ) -> WebBridgeCallResult:
        self._require_ready()
        self._check_action_allowed("list_tabs")
        return self._call("list_tabs", {}, session=session, actor_id=requested_by)

    def close_session(
        self,
        request: CloseSessionRequest,
        *,
        requested_by: str | None = None,
    ) -> WebBridgeCallResult:
        self._require_ready()
        self._check_action_allowed("close_session")
        return self._call("close_session", {}, session=request.session, actor_id=requested_by)

    def _call(
        self,
        action: str,
        args: dict[str, Any],
        *,
        session: str | None,
        audit_extra: dict[str, Any] | None = None,
        actor_id: str | None,
    ) -> WebBridgeCallResult:
        audit_args = {
            "action": action,
            "session": session,
            "mutating": action in MUTATING_ACTIONS,
            **(audit_extra or {}),
        }
        try:
            payload = self._resolve_provider().call(action, args, session)
        except KimiWebBridgeError as exc:
            _audit_webbridge(action, audit_args, actor_id, f"error: {exc}")
            raise
        _audit_webbridge(action, audit_args, actor_id, "ok")
        return WebBridgeCallResult(status="ok", action=action, payload=payload)

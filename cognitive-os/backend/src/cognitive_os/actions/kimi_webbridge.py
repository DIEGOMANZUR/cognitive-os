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

import json
import os
import re
import shutil
import subprocess
import time
from typing import Any, Literal, Protocol
from urllib.parse import quote, urlparse

import httpx
import structlog
from pydantic import BaseModel, Field
from websockets.sync.client import connect as websocket_connect

from cognitive_os.actions.policy import (
    ActionPolicyViolation,
    HostnameResolver,
    validate_browser_target_ip,
)
from cognitive_os.core.config import Settings, settings
from cognitive_os.core.resilience import retry_transient_http
from cognitive_os.tools.policy import ToolAuditRecord, ToolRiskLevel, record_audit_event

_log = structlog.get_logger(__name__)
_LAST_EDGE_WAKE_AT = 0.0
_LAST_WEBBRIDGE_TAB_ID: int | None = None
_LAST_EDGE_DEVTOOLS_TARGET_ID: str | None = None
_EDGE_DEVTOOLS_SESSION_TARGETS: dict[str, str] = {}

# Operations that only read browser state — gated by domain allow-list but NOT
# by the additional `KIMI_WEBBRIDGE_ALLOW_MUTATIONS` flag.
READ_ONLY_ACTIONS = frozenset(
    {"navigate", "snapshot", "screenshot", "find_tab", "list_tabs", "save_as_pdf", "network"}
)
# Operations that change browser state.
MUTATING_ACTIONS = frozenset({"click", "fill", "evaluate", "upload", "close_tab", "close_session"})

MAX_SELECTOR_LENGTH = 512
MAX_VALUE_LENGTH = 4000
DEFAULT_KIMI_EXTENSION_ID = "bnlffdbcfnanfbknnlaflhlhkocccckg"
CHROMIUM_EXTENSION_ID_RE = re.compile(r"^[a-p]{32}$")


class KimiWebBridgeError(RuntimeError):
    """Raised when a WebBridge call cannot be completed."""


class KimiWebBridgePolicyError(KimiWebBridgeError):
    """Raised when local policy rejects a WebBridge call before runtime I/O."""


class WebBridgeStatus(BaseModel):
    status: Literal["disabled", "blocked", "ready"]
    reason: str | None = None
    daemon_url: str
    daemon_running: bool = False
    extension_connected: bool = False
    active_provider: Literal["kimi_webbridge", "edge_devtools"] | None = None
    edge_devtools_url: str | None = None
    edge_devtools_running: bool = False
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


class EdgeDevToolsProvider(Protocol):
    """Real-browser transport over Chrome DevTools Protocol."""

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
        return self._normalize_payload(payload)

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize the daemon's HTTP envelope into the service contract.

        Current Kimi WebBridge daemon responses use an envelope:
        ``{"ok": true, "data": {...}}`` or
        ``{"ok": false, "error": {"code": "...", "message": "..."}}``.
        Older/local test doubles returned the inner object directly. The
        backend service expects the inner object, and daemon errors must raise
        so callers/audit/readiness see a real failure instead of an apparently
        successful WebBridgeCallResult carrying an error payload.
        """
        if "ok" not in payload:
            return payload

        if payload.get("ok") is True:
            data = payload.get("data")
            if isinstance(data, dict):
                return data
            return {"data": data}

        error = payload.get("error")
        if isinstance(error, dict):
            code = str(error.get("code") or "daemon_error")
            message = str(error.get("message") or error)
            raise KimiWebBridgeError(f"WebBridge daemon error ({code}): {message}")
        if error:
            raise KimiWebBridgeError(f"WebBridge daemon error: {error}")
        raise KimiWebBridgeError("WebBridge daemon returned ok=false without error details.")

    def status_probe(self) -> dict[str, Any]:
        # Step 1: HTTP root probe — daemon process reachable?
        try:
            response = httpx.get(self._endpoint("/"), timeout=2.0)
        except httpx.HTTPError as exc:
            return {"running": False, "extension_connected": False, "error": str(exc)}
        running = 200 <= response.status_code < 500
        if not running:
            return {
                "running": False,
                "extension_connected": False,
                "status": response.status_code,
            }
        # Step 2 (Fase 72 E): real smoke against the daemon /command endpoint.
        # `list_tabs` is the cheapest action that requires the extension to
        # answer (status_probe before would say `extension_connected=true`
        # even when the extension was disabled/stale). Failure here means the
        # daemon is up but the browser extension is not actually wired.
        try:
            payload = self.call("list_tabs", {}, session=None)
        except KimiWebBridgeError as exc:
            return {
                "running": True,
                "extension_connected": False,
                "status": response.status_code,
                "error": str(exc),
            }
        extension_ok = bool(payload.get("success") and "tabs" in payload)
        return {
            "running": True,
            "extension_connected": extension_ok,
            "status": response.status_code,
            "tabs": len(payload.get("tabs", [])) if extension_ok else 0,
        }


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


class EdgeDevToolsCdpProvider:
    """Control the operator's real Edge/Chrome profile through local CDP.

    Kimi WebBridge is still supported, but on the dedicated-PC profile the
    browser is a runtime component. CDP is deterministic once Edge is launched
    with ``--remote-debugging-port`` and does not depend on the Kimi extension
    keeping a popup/service-worker context alive.
    """

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings
        self._seq = 0

    def _endpoint(self, path: str) -> str:
        return f"{self._settings.edge_devtools_url.rstrip('/')}{path}"

    def status_probe(self) -> dict[str, Any]:
        if not getattr(self._settings, "enable_edge_devtools_webbridge", False):
            return {"running": False, "enabled": False}
        try:
            version = httpx.get(self._endpoint("/json/version"), timeout=2.0)
            version.raise_for_status()
            targets = self._targets()
        except Exception as exc:  # noqa: BLE001 - status probe must not explode
            return {"running": False, "enabled": True, "error": str(exc)}
        return {
            "running": True,
            "enabled": True,
            "browser": version.json().get("Browser"),
            "targets": len(targets),
            "pages": len([target for target in targets if target.get("type") == "page"]),
        }

    def call(self, action: str, args: dict[str, Any], session: str | None) -> dict[str, Any]:
        if not getattr(self._settings, "enable_edge_devtools_webbridge", False):
            raise KimiWebBridgeError("Edge DevTools WebBridge is disabled.")
        if action == "navigate":
            return self._navigate(args, session)
        if action == "list_tabs":
            return self._list_tabs()
        if action == "close_session":
            return self._close_session(session)
        target = self._resolve_target(session=session)
        if action == "snapshot":
            return self._snapshot(target)
        if action == "screenshot":
            return self._screenshot(target, args)
        if action == "evaluate":
            return self._evaluate(target, str(args.get("code") or ""))
        if action == "click":
            return self._click(target, str(args.get("selector") or ""))
        if action == "fill":
            return self._fill(target, str(args.get("selector") or ""), str(args.get("value") or ""))
        raise KimiWebBridgeError(f"Edge DevTools does not support WebBridge action {action!r}.")

    def _targets(self) -> list[dict[str, Any]]:
        try:
            response = httpx.get(self._endpoint("/json"), timeout=5.0)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise KimiWebBridgeError(f"Edge DevTools is not reachable: {exc}") from exc
        except ValueError as exc:
            raise KimiWebBridgeError("Edge DevTools returned invalid JSON.") from exc
        if not isinstance(payload, list):
            raise KimiWebBridgeError("Edge DevTools returned a non-list target payload.")
        return [target for target in payload if isinstance(target, dict)]

    @staticmethod
    def _usable_page(target: dict[str, Any]) -> bool:
        if target.get("type") != "page":
            return False
        url = str(target.get("url") or "")
        return not url.startswith(("chrome-extension://", "chrome://", "edge://"))

    def _resolve_target(self, *, session: str | None) -> dict[str, Any]:
        global _LAST_EDGE_DEVTOOLS_TARGET_ID
        targets = self._targets()
        target_by_id = {
            str(target.get("id")): target for target in targets if isinstance(target.get("id"), str)
        }
        if session and session in _EDGE_DEVTOOLS_SESSION_TARGETS:
            target = target_by_id.get(_EDGE_DEVTOOLS_SESSION_TARGETS[session])
            if target and self._usable_page(target):
                _LAST_EDGE_DEVTOOLS_TARGET_ID = str(target["id"])
                return target
        if _LAST_EDGE_DEVTOOLS_TARGET_ID:
            target = target_by_id.get(_LAST_EDGE_DEVTOOLS_TARGET_ID)
            if target and self._usable_page(target):
                return target
        for target in targets:
            if self._usable_page(target):
                _LAST_EDGE_DEVTOOLS_TARGET_ID = str(target["id"])
                return target
        raise KimiWebBridgeError(
            "Edge DevTools has no usable page target. Open a normal http/https tab first."
        )

    def _new_target(self, url: str) -> dict[str, Any]:
        encoded = quote(url, safe="")
        last_error: Exception | None = None
        for method in ("put", "get"):
            try:
                response = getattr(httpx, method)(
                    self._endpoint(f"/json/new?{encoded}"),
                    timeout=10.0,
                )
                if response.status_code == 405:
                    continue
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict):
                    return payload
            except httpx.HTTPError as exc:
                last_error = exc
                if method == "get":
                    raise KimiWebBridgeError(f"Edge DevTools is not reachable: {exc}") from exc
            except ValueError as exc:
                last_error = exc
                if method == "get":
                    raise KimiWebBridgeError("Edge DevTools returned invalid JSON.") from exc
            except Exception as exc:
                last_error = exc
                if method == "get":
                    raise KimiWebBridgeError(f"Edge DevTools call failed: {exc}") from exc
        detail = f": {last_error}" if last_error else "."
        raise KimiWebBridgeError(f"Edge DevTools could not create a new page target{detail}")

    def _activate(self, target_id: str) -> None:
        try:
            httpx.get(self._endpoint(f"/json/activate/{target_id}"), timeout=3.0)
        except httpx.HTTPError:
            return

    def _navigate(self, args: dict[str, Any], session: str | None) -> dict[str, Any]:
        global _LAST_EDGE_DEVTOOLS_TARGET_ID
        url = str(args.get("url") or "")
        if not url:
            raise KimiWebBridgeError("navigate: url is required.")
        if bool(args.get("newTab", True)):
            target = self._new_target(url)
        else:
            target = self._resolve_target(session=session)
            self._send(target, "Page.navigate", {"url": url})
        target_id = str(target.get("id") or "")
        if not target_id:
            raise KimiWebBridgeError("Edge DevTools returned a target without id.")
        _LAST_EDGE_DEVTOOLS_TARGET_ID = target_id
        if session:
            _EDGE_DEVTOOLS_SESSION_TARGETS[session] = target_id
        self._activate(target_id)
        self._wait_ready(target)
        info = self._page_info(target)
        return {
            "success": True,
            "url": info.get("url") or url,
            "title": info.get("title") or "",
            "targetId": target_id,
            "provider": "edge_devtools",
        }

    def _list_tabs(self) -> dict[str, Any]:
        tabs = []
        for target in self._targets():
            if target.get("type") != "page":
                continue
            tabs.append(
                {
                    "targetId": target.get("id"),
                    "url": target.get("url") or "",
                    "title": target.get("title") or "",
                    "active": str(target.get("id")) == _LAST_EDGE_DEVTOOLS_TARGET_ID,
                    "provider": "edge_devtools",
                }
            )
        return {"success": True, "tabs": tabs}

    def _close_session(self, session: str | None) -> dict[str, Any]:
        target_id = _EDGE_DEVTOOLS_SESSION_TARGETS.pop(session, None) if session else None
        if target_id is None:
            return {"success": True, "closed": 0, "provider": "edge_devtools"}
        try:
            response = httpx.get(self._endpoint(f"/json/close/{target_id}"), timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise KimiWebBridgeError(f"Edge DevTools close_session failed: {exc}") from exc
        return {"success": True, "closed": 1, "provider": "edge_devtools"}

    def _send(
        self,
        target: dict[str, Any],
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ws_url = str(target.get("webSocketDebuggerUrl") or "")
        if not ws_url:
            raise KimiWebBridgeError("Edge DevTools target has no websocket URL.")
        self._seq += 1
        message_id = self._seq
        with websocket_connect(ws_url, open_timeout=5, close_timeout=2) as websocket:
            websocket.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                raw = websocket.recv(timeout=2)
                payload = json.loads(raw)
                if payload.get("id") != message_id:
                    continue
                if "error" in payload:
                    error = payload["error"]
                    message = error.get("message") if isinstance(error, dict) else str(error)
                    raise KimiWebBridgeError(f"Edge DevTools {method} failed: {message}")
                result = payload.get("result")
                return result if isinstance(result, dict) else {"result": result}
        raise KimiWebBridgeError(f"Edge DevTools {method} timed out.")

    def _wait_ready(self, target: dict[str, Any]) -> None:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                result = self._send(
                    target,
                    "Runtime.evaluate",
                    {
                        "expression": "document.readyState",
                        "returnByValue": True,
                        "awaitPromise": True,
                    },
                )
                ready = result.get("result", {}).get("value")
                if ready in {"interactive", "complete"}:
                    return
            except KimiWebBridgeError:
                pass
            time.sleep(0.25)

    def _runtime_value(self, target: dict[str, Any], expression: str) -> Any:
        result = self._send(
            target,
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if result.get("exceptionDetails"):
            details = result["exceptionDetails"]
            description = details.get("exception", {}).get("description") or details.get("text")
            raise KimiWebBridgeError(f"Edge DevTools evaluate failed: {description}")
        return result.get("result", {}).get("value")

    def _page_info(self, target: dict[str, Any]) -> dict[str, Any]:
        value = self._runtime_value(
            target,
            "(() => ({url: location.href, title: document.title, text: "
            "(document.body?.innerText || '').slice(0, 20000)}))()",
        )
        return value if isinstance(value, dict) else {}

    def _snapshot(self, target: dict[str, Any]) -> dict[str, Any]:
        info = self._page_info(target)
        try:
            tree = self._send(target, "Accessibility.getFullAXTree").get("nodes", [])
        except KimiWebBridgeError:
            tree = []
        return {
            "success": True,
            "url": info.get("url") or target.get("url") or "",
            "title": info.get("title") or target.get("title") or "",
            "text": info.get("text") or "",
            "tree": self._format_ax_tree(tree),
            "provider": "edge_devtools",
        }

    @staticmethod
    def _format_ax_tree(nodes: Any) -> list[dict[str, Any]]:
        if not isinstance(nodes, list):
            return []
        formatted: list[dict[str, Any]] = []
        for node in nodes[:400]:
            if not isinstance(node, dict):
                continue
            role = node.get("role", {}).get("value")
            if not role or role in {"none", "generic"}:
                continue
            item: dict[str, Any] = {"role": role}
            name = node.get("name", {}).get("value")
            value = node.get("value", {}).get("value")
            if name:
                item["name"] = str(name)
            if value:
                item["value"] = str(value)
            formatted.append(item)
        return formatted

    def _screenshot(self, target: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
        params: dict[str, Any] = {"format": args.get("format") or "png", "fromSurface": True}
        if params["format"] == "jpeg":
            params["quality"] = int(args.get("quality") or 80)
        result = self._send(target, "Page.captureScreenshot", params)
        data = str(result.get("data") or "")
        return {
            "success": True,
            "format": params["format"],
            "data": data,
            "dataLength": len(data),
            "provider": "edge_devtools",
        }

    def _evaluate(self, target: dict[str, Any], code: str) -> dict[str, Any]:
        if not code:
            raise KimiWebBridgeError("evaluate: code is required.")
        value = self._runtime_value(target, code)
        return {
            "type": type(value).__name__,
            "value": value,
            "provider": "edge_devtools",
        }

    def _click(self, target: dict[str, Any], selector: str) -> dict[str, Any]:
        if not selector:
            raise KimiWebBridgeError("click: selector is required.")
        value = self._runtime_value(
            target,
            f"""(() => {{
                const el = document.querySelector({json.dumps(selector)});
                if (!el) return {{error: 'element not found: {selector}'}};
                el.scrollIntoView({{block: 'center', inline: 'center'}});
                el.click();
                return {{
                    success: true,
                    tag: el.tagName,
                    text: (el.textContent || '').slice(0, 100),
                }};
            }})()""",
        )
        if isinstance(value, dict) and value.get("error"):
            raise KimiWebBridgeError(f"click: {value['error']}")
        return value if isinstance(value, dict) else {"success": True, "provider": "edge_devtools"}

    def _fill(self, target: dict[str, Any], selector: str, value: str) -> dict[str, Any]:
        if not selector:
            raise KimiWebBridgeError("fill: selector is required.")
        result = self._runtime_value(
            target,
            f"""(() => {{
                const el = document.querySelector({json.dumps(selector)});
                if (!el) return {{error: 'element not found: {selector}'}};
                el.focus();
                const value = {json.dumps(value)};
                const inputSetter =
                    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
                const textareaSetter =
                    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set;
                const setter = inputSetter || textareaSetter;
                if (setter && ('value' in el)) setter.call(el, value);
                else if ('value' in el) el.value = value;
                else el.textContent = value;
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                return {{success: true, tag: el.tagName}};
            }})()""",
        )
        if isinstance(result, dict) and result.get("error"):
            raise KimiWebBridgeError(f"fill: {result['error']}")
        if isinstance(result, dict):
            return result
        return {"success": True, "provider": "edge_devtools"}


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


def _safe_kimi_extension_id(raw: str | None) -> str:
    candidate = (raw or DEFAULT_KIMI_EXTENSION_ID).strip().lower()
    if CHROMIUM_EXTENSION_ID_RE.fullmatch(candidate):
        return candidate
    _log.warning("webbridge_invalid_extension_id_ignored")
    return DEFAULT_KIMI_EXTENSION_ID


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


def _remember_tab_id(payload: dict[str, Any]) -> None:
    global _LAST_WEBBRIDGE_TAB_ID
    tab_id = payload.get("tabId")
    if isinstance(tab_id, int):
        _LAST_WEBBRIDGE_TAB_ID = tab_id


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
        devtools_provider: EdgeDevToolsProvider | None = None,
        app_settings: Settings = settings,
        hostname_resolver: HostnameResolver | None = None,
    ) -> None:
        self._settings = app_settings
        self._provider = provider
        self._devtools_provider = devtools_provider
        self._hostname_resolver = hostname_resolver

    def _resolve_provider(self) -> WebBridgeProvider:
        if self._provider is None:
            self._provider = HttpWebBridgeProvider(self._settings)
        return self._provider

    def _resolve_devtools_provider(self) -> EdgeDevToolsProvider:
        if self._devtools_provider is None:
            self._devtools_provider = EdgeDevToolsCdpProvider(self._settings)
        return self._devtools_provider

    def _devtools_enabled(self) -> bool:
        return bool(getattr(self._settings, "enable_edge_devtools_webbridge", False))

    def _devtools_preferred(self) -> bool:
        return bool(getattr(self._settings, "edge_devtools_prefer", False))

    def _devtools_probe(self) -> dict[str, Any]:
        if not self._devtools_enabled():
            return {"running": False, "enabled": False}
        return self._resolve_devtools_provider().status_probe()

    def _can_wake_edge(self) -> bool:
        return (
            self._settings.operator_profile == "dedicated_local"
            and self._settings.local_autonomy_mode == "full"
        )

    def _cockpit_url(self) -> str:
        frontend_port = os.environ.get("FRONTEND_PORT", "3001")
        return f"http://localhost:{frontend_port}?tab=health"

    def _open_cockpit_app(self) -> bool:
        edge_bin = (
            shutil.which("microsoft-edge")
            or shutil.which("microsoft-edge-stable")
            or shutil.which("google-chrome")
            or shutil.which("chromium")
        )
        if edge_bin is None:
            return False
        try:
            subprocess.Popen(  # noqa: S603 - fixed executable path from PATH lookup
                [edge_bin, f"--app={self._cockpit_url()}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception as exc:  # noqa: BLE001 - degraded browser recovery only
            _log.warning(
                "webbridge_cockpit_focus_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return False

    def _wake_edge_profile(self) -> bool:
        """Best-effort wake of the operator's real Edge profile and Kimi popup."""
        if not self._can_wake_edge():
            return False
        global _LAST_EDGE_WAKE_AT
        now = time.monotonic()
        if now - _LAST_EDGE_WAKE_AT < 10:
            return False
        _LAST_EDGE_WAKE_AT = now

        edge_bin = (
            shutil.which("microsoft-edge")
            or shutil.which("microsoft-edge-stable")
            or shutil.which("google-chrome")
            or shutil.which("chromium")
        )
        gtk_launch = shutil.which("gtk-launch")
        if edge_bin is None and gtk_launch is None:
            return False
        extension_id = _safe_kimi_extension_id(os.environ.get("KIMI_EXTENSION_ID"))
        try:
            self._open_cockpit_app()
            time.sleep(2)
            extension_url = f"chrome-extension://{extension_id}/popup.html"
            if gtk_launch is not None:
                # nosemgrep
                subprocess.Popen(  # noqa: S603 - fixed executable path from PATH lookup
                    [  # nosemgrep
                        gtk_launch,
                        "microsoft-edge",
                        extension_url,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            elif edge_bin is not None:
                # nosemgrep
                subprocess.Popen(  # noqa: S603 - fixed executable path from PATH lookup
                    [  # nosemgrep
                        edge_bin,
                        extension_url,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            time.sleep(2)
            self._open_cockpit_app()
            return True
        except Exception as exc:  # noqa: BLE001 - degraded browser recovery only
            _log.warning(
                "webbridge_edge_wake_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return False

    def status(self) -> WebBridgeStatus:
        url = self._settings.kimi_webbridge_url
        allow_mut = bool(self._settings.kimi_webbridge_allow_mutations)
        domain_count = len(self._settings.kimi_webbridge_allowed_domains)
        if not self._settings.enable_kimi_webbridge:
            devtools_probe = self._devtools_probe()
            if bool(devtools_probe.get("running")):
                if domain_count == 0:
                    return WebBridgeStatus(
                        status="blocked",
                        reason=(
                            "KIMI_WEBBRIDGE_ALLOWED_DOMAINS is empty — set explicit domains "
                            "or '*' to allow every host."
                        ),
                        daemon_url=url,
                        daemon_running=False,
                        extension_connected=False,
                        active_provider=None,
                        edge_devtools_url=getattr(self._settings, "edge_devtools_url", None),
                        edge_devtools_running=True,
                        allow_mutations=allow_mut,
                        allowed_domain_count=domain_count,
                    )
                return WebBridgeStatus(
                    status="ready",
                    reason="Using Edge DevTools WebBridge; Kimi WebBridge is disabled.",
                    daemon_url=url,
                    daemon_running=False,
                    extension_connected=False,
                    active_provider="edge_devtools",
                    edge_devtools_url=getattr(self._settings, "edge_devtools_url", None),
                    edge_devtools_running=True,
                    allow_mutations=allow_mut,
                    allowed_domain_count=domain_count,
                )
            return WebBridgeStatus(
                status="disabled",
                reason="ENABLE_KIMI_WEBBRIDGE is false.",
                daemon_url=url,
                allow_mutations=allow_mut,
                allowed_domain_count=domain_count,
            )
        provider = self._resolve_provider()
        probe = provider.status_probe()
        running = bool(probe.get("running"))
        extension = bool(probe.get("extension_connected"))
        devtools_probe = self._devtools_probe()
        devtools_running = bool(devtools_probe.get("running"))
        if devtools_running and self._devtools_preferred():
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
                    active_provider=None,
                    edge_devtools_url=getattr(self._settings, "edge_devtools_url", None),
                    edge_devtools_running=True,
                    allow_mutations=allow_mut,
                    allowed_domain_count=domain_count,
                )
            return WebBridgeStatus(
                status="ready",
                reason=None,
                daemon_url=url,
                daemon_running=running,
                extension_connected=extension,
                active_provider="edge_devtools",
                edge_devtools_url=getattr(self._settings, "edge_devtools_url", None),
                edge_devtools_running=True,
                allow_mutations=allow_mut,
                allowed_domain_count=domain_count,
            )
        if running and not extension and self._wake_edge_profile():
            for _ in range(12):
                time.sleep(1)
                probe = provider.status_probe()
                extension = bool(probe.get("extension_connected"))
                if extension:
                    break
        if not running:
            if devtools_running:
                if domain_count == 0:
                    return WebBridgeStatus(
                        status="blocked",
                        reason=(
                            "KIMI_WEBBRIDGE_ALLOWED_DOMAINS is empty — set explicit domains "
                            "or '*' to allow every host."
                        ),
                        daemon_url=url,
                        daemon_running=False,
                        extension_connected=False,
                        active_provider=None,
                        edge_devtools_url=getattr(self._settings, "edge_devtools_url", None),
                        edge_devtools_running=True,
                        allow_mutations=allow_mut,
                        allowed_domain_count=domain_count,
                    )
                return WebBridgeStatus(
                    status="ready",
                    reason="Using Edge DevTools WebBridge; Kimi daemon is not reachable.",
                    daemon_url=url,
                    daemon_running=False,
                    extension_connected=False,
                    active_provider="edge_devtools",
                    edge_devtools_url=getattr(self._settings, "edge_devtools_url", None),
                    edge_devtools_running=True,
                    allow_mutations=allow_mut,
                    allowed_domain_count=domain_count,
                )
            return WebBridgeStatus(
                status="blocked",
                reason=(
                    "WebBridge daemon not reachable at "
                    f"{url}. Start it with `~/.kimi-webbridge/bin/kimi-webbridge start`."
                ),
                daemon_url=url,
                daemon_running=False,
                extension_connected=False,
                active_provider=None,
                edge_devtools_url=getattr(self._settings, "edge_devtools_url", None),
                edge_devtools_running=devtools_running,
                allow_mutations=allow_mut,
                allowed_domain_count=domain_count,
            )
        if not extension:
            if devtools_running:
                if domain_count == 0:
                    return WebBridgeStatus(
                        status="blocked",
                        reason=(
                            "KIMI_WEBBRIDGE_ALLOWED_DOMAINS is empty — set explicit domains "
                            "or '*' to allow every host."
                        ),
                        daemon_url=url,
                        daemon_running=running,
                        extension_connected=False,
                        active_provider=None,
                        edge_devtools_url=getattr(self._settings, "edge_devtools_url", None),
                        edge_devtools_running=True,
                        allow_mutations=allow_mut,
                        allowed_domain_count=domain_count,
                    )
                return WebBridgeStatus(
                    status="ready",
                    reason="Using Edge DevTools WebBridge; Kimi extension is not connected.",
                    daemon_url=url,
                    daemon_running=running,
                    extension_connected=False,
                    active_provider="edge_devtools",
                    edge_devtools_url=getattr(self._settings, "edge_devtools_url", None),
                    edge_devtools_running=True,
                    allow_mutations=allow_mut,
                    allowed_domain_count=domain_count,
                )
            return WebBridgeStatus(
                status="blocked",
                reason=(
                    "WebBridge daemon is reachable, but the browser extension "
                    "is not connected. Open Edge/Chrome with the Kimi WebBridge "
                    "extension enabled and refresh /actions/webbridge/status."
                ),
                daemon_url=url,
                daemon_running=running,
                extension_connected=False,
                active_provider=None,
                edge_devtools_url=getattr(self._settings, "edge_devtools_url", None),
                edge_devtools_running=devtools_running,
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
                active_provider=None,
                edge_devtools_url=getattr(self._settings, "edge_devtools_url", None),
                edge_devtools_running=devtools_running,
                allow_mutations=allow_mut,
                allowed_domain_count=domain_count,
            )
        return WebBridgeStatus(
            status="ready",
            reason=None,
            daemon_url=url,
            daemon_running=running,
            extension_connected=extension,
            active_provider="kimi_webbridge",
            edge_devtools_url=getattr(self._settings, "edge_devtools_url", None),
            edge_devtools_running=devtools_running,
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
            raise KimiWebBridgePolicyError(msg)
        if action in MUTATING_ACTIONS and self._settings.kimi_webbridge_require_approval:
            msg = (
                f"WebBridge action {action!r} is a mutation and requires human approval; "
                "direct execution is disabled while KIMI_WEBBRIDGE_REQUIRE_APPROVAL=true."
            )
            raise KimiWebBridgePolicyError(msg)
        if action not in READ_ONLY_ACTIONS and action not in MUTATING_ACTIONS:
            msg = f"Unknown WebBridge action {action!r}."
            raise KimiWebBridgePolicyError(msg)

    def _check_url_allowed(self, url: str | None) -> None:
        if url is None:
            return
        host = _host_of(url)
        if host is None:
            raise KimiWebBridgePolicyError(f"Could not parse host from URL {url!r}.")
        if not _domain_allowed(host, list(self._settings.kimi_webbridge_allowed_domains)):
            raise KimiWebBridgePolicyError(
                f"Host {host!r} is not in KIMI_WEBBRIDGE_ALLOWED_DOMAINS."
            )
        if getattr(self._settings, "enable_browser_ssrf_check", True):
            try:
                if self._hostname_resolver is None:
                    validate_browser_target_ip(host)
                else:
                    validate_browser_target_ip(host, resolver=self._hostname_resolver)
            except ActionPolicyViolation as exc:
                raise KimiWebBridgePolicyError(str(exc)) from exc

    def navigate(
        self,
        request: NavigateRequest,
        *,
        requested_by: str | None = None,
    ) -> WebBridgeCallResult:
        self._check_action_allowed("navigate")
        if not self._settings.enable_kimi_webbridge and not self._devtools_enabled():
            self._require_ready()
        self._check_url_allowed(request.url)
        self._require_ready()
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
        return self._call(
            "list_tabs",
            {},
            session=session,
            actor_id=requested_by,
            force_active_tab=False,
        )

    def close_session(
        self,
        request: CloseSessionRequest,
        *,
        requested_by: str | None = None,
    ) -> WebBridgeCallResult:
        self._require_ready()
        self._check_action_allowed("close_session")
        return self._call(
            "close_session",
            {},
            session=request.session,
            actor_id=requested_by,
            force_active_tab=False,
        )

    def _call(
        self,
        action: str,
        args: dict[str, Any],
        *,
        session: str | None,
        audit_extra: dict[str, Any] | None = None,
        actor_id: str | None,
        force_active_tab: bool = True,
    ) -> WebBridgeCallResult:
        # Kimi WebBridge v1.9.7 session-scoped snapshot/click can target its
        # own extension page instead of the real tab. For the dedicated-local
        # product path we drive the active Edge tab, which is the daemon path
        # verified live on this host. Explicit-session operations remain for
        # list/close where the daemon supports them reliably.
        daemon_session = None if force_active_tab else session
        audit_args = {
            "action": action,
            "session": session,
            "daemon_session": daemon_session,
            "session_mode": "active_tab" if force_active_tab else "explicit_session",
            "mutating": action in MUTATING_ACTIONS,
            **(audit_extra or {}),
        }
        if action == "navigate" and self._can_wake_edge():
            self._open_cockpit_app()
            time.sleep(1)
        if (
            action in {"snapshot", "screenshot", "click", "fill", "evaluate"}
            and daemon_session is None
            and _LAST_WEBBRIDGE_TAB_ID is not None
            and "_tabId" not in args
        ):
            args = {**args, "_tabId": _LAST_WEBBRIDGE_TAB_ID}
            audit_args["tab_id"] = _LAST_WEBBRIDGE_TAB_ID
        if self._devtools_enabled() and self._devtools_preferred():
            try:
                payload = self._resolve_devtools_provider().call(action, dict(args), session)
                audit_args["provider"] = "edge_devtools"
                _audit_webbridge(action, audit_args, actor_id, "ok")
                return WebBridgeCallResult(status="ok", action=action, payload=payload)
            except KimiWebBridgeError as devtools_exc:
                audit_args["edge_devtools_error"] = _truncate(str(devtools_exc), 240)

        provider = self._resolve_provider()
        try:
            payload = provider.call(action, args, daemon_session)
        except KimiWebBridgeError as exc:
            error_text = str(exc).lower()
            if self._devtools_enabled() and not self._devtools_preferred():
                try:
                    payload = self._resolve_devtools_provider().call(action, dict(args), session)
                    audit_args["provider"] = "edge_devtools"
                    audit_args["kimi_error"] = _truncate(str(exc), 240)
                    _audit_webbridge(action, audit_args, actor_id, "ok")
                    return WebBridgeCallResult(status="ok", action=action, payload=payload)
                except KimiWebBridgeError as devtools_exc:
                    audit_args["edge_devtools_error"] = _truncate(str(devtools_exc), 240)
            if action == "navigate" and args.get("newTab") is False:
                retry_args = {**args, "newTab": True}
                try:
                    payload = provider.call(action, retry_args, daemon_session)
                    audit_args["retried_with_new_tab"] = True
                    _remember_tab_id(payload)
                    _audit_webbridge(action, audit_args, actor_id, "ok")
                    return WebBridgeCallResult(status="ok", action=action, payload=payload)
                except KimiWebBridgeError as retry_exc:
                    exc = retry_exc
                    error_text = str(exc).lower()
            if "extension" not in error_text or "connected" not in error_text:
                _audit_webbridge(action, audit_args, actor_id, f"error: {exc}")
                raise
            if not self._wake_edge_profile():
                _audit_webbridge(action, audit_args, actor_id, f"error: {exc}")
                raise
            last_exc = exc
            for _ in range(12):
                time.sleep(1)
                try:
                    payload = provider.call(action, args, daemon_session)
                    break
                except KimiWebBridgeError as retry_exc:
                    last_exc = retry_exc
            else:
                _audit_webbridge(action, audit_args, actor_id, f"error: {last_exc}")
                raise last_exc
        if action == "navigate":
            _remember_tab_id(payload)
        audit_args["provider"] = "kimi_webbridge"
        _audit_webbridge(action, audit_args, actor_id, "ok")
        return WebBridgeCallResult(status="ok", action=action, payload=payload)

from __future__ import annotations

from typing import Any

import httpx
import pytest

from cognitive_os.actions.kimi_webbridge import (
    ClickRequest,
    EvaluateRequest,
    FakeWebBridgeProvider,
    FillRequest,
    KimiWebBridgeError,
    KimiWebBridgeService,
    NavigateRequest,
    ScreenshotRequest,
    SnapshotRequest,
    _domain_allowed,
    _host_of,
)
from cognitive_os.api.app import app
from cognitive_os.core.config import Settings


def _settings(
    *,
    enabled: bool = True,
    domains: list[str] | None = None,
    mutations: bool = False,
    require_approval: bool = True,
    ssrf_check: bool = False,
    url: str = "http://127.0.0.1:10086",
    edge_devtools: bool = False,
    edge_devtools_prefer: bool = False,
) -> Settings:
    return Settings.model_construct(
        enable_kimi_webbridge=enabled,
        kimi_webbridge_url=url,
        kimi_webbridge_require_approval=require_approval,
        kimi_webbridge_allowed_domains=domains or [],
        kimi_webbridge_allow_mutations=mutations,
        kimi_webbridge_request_timeout_seconds=5,
        enable_browser_ssrf_check=ssrf_check,
        http_timeout_seconds=5.0,
        enable_edge_devtools_webbridge=edge_devtools,
        edge_devtools_url="http://127.0.0.1:9222",
        edge_devtools_prefer=edge_devtools_prefer,
    )


class FakeEdgeDevToolsProvider:
    def __init__(self, *, running: bool = True, raises: bool = False) -> None:
        self.running = running
        self.raises = raises
        self.calls: list[dict[str, Any]] = []

    def status_probe(self) -> dict[str, Any]:
        return {"running": self.running, "enabled": True, "pages": 1 if self.running else 0}

    def call(self, action: str, args: dict[str, Any], session: str | None) -> dict[str, Any]:
        self.calls.append({"action": action, "args": args, "session": session})
        if self.raises:
            raise KimiWebBridgeError("fake edge devtools failure")
        return {"success": True, "action": action, "provider": "edge_devtools"}


def test_host_helpers() -> None:
    assert _host_of("https://Mail.Google.com/inbox") == "mail.google.com"
    assert _host_of("example.com") == "example.com"
    assert _host_of("") is None
    assert _domain_allowed("mail.google.com", ["google.com"]) is True
    assert _domain_allowed("notgoogle.com", ["google.com"]) is False
    assert _domain_allowed("google.com", ["google.com"]) is True
    assert _domain_allowed("anything", []) is False
    assert _domain_allowed("foo.example.com", [".example.com"]) is True
    # Wildcard = operator opted out of the allow-list.
    assert _domain_allowed("any-random-host.tld", ["*"]) is True
    assert _domain_allowed("bank.com", ["google.com", "*"]) is True


def test_status_disabled_blocked_ready() -> None:
    disabled = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(),
        app_settings=_settings(enabled=False),
    ).status()
    assert disabled.status == "disabled"

    no_daemon = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(running=False),
        app_settings=_settings(domains=["google.com"]),
    ).status()
    assert no_daemon.status == "blocked"
    assert "daemon" in (no_daemon.reason or "").lower()

    no_allowlist = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(),
        app_settings=_settings(domains=[]),
    ).status()
    assert no_allowlist.status == "blocked"
    assert "ALLOWED_DOMAINS" in (no_allowlist.reason or "")

    no_extension = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(extension_connected=False),
        app_settings=_settings(domains=["google.com"]),
    ).status()
    assert no_extension.status == "blocked"
    assert "extension" in (no_extension.reason or "").lower()

    ready = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(),
        app_settings=_settings(domains=["google.com"]),
    ).status()
    assert ready.status == "ready"
    assert ready.allowed_domain_count == 1


def test_status_uses_edge_devtools_when_kimi_extension_is_disconnected() -> None:
    service = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(extension_connected=False),
        devtools_provider=FakeEdgeDevToolsProvider(),
        app_settings=_settings(domains=["*"], edge_devtools=True),
    )

    status = service.status()

    assert status.status == "ready"
    assert status.active_provider == "edge_devtools"
    assert status.edge_devtools_running is True


def test_edge_devtools_preferred_for_real_browser_calls() -> None:
    fake_kimi = FakeWebBridgeProvider(responses={"snapshot": {"provider": "kimi"}})
    fake_devtools = FakeEdgeDevToolsProvider()
    service = KimiWebBridgeService(
        provider=fake_kimi,
        devtools_provider=fake_devtools,
        app_settings=_settings(
            domains=["google.com"],
            edge_devtools=True,
            edge_devtools_prefer=True,
        ),
    )

    result = service.snapshot(SnapshotRequest(session="main"))

    assert result.payload["provider"] == "edge_devtools"
    assert fake_devtools.calls == [{"action": "snapshot", "args": {}, "session": "main"}]
    assert fake_kimi.calls == []


def test_edge_devtools_fallback_when_kimi_daemon_fails() -> None:
    fake_devtools = FakeEdgeDevToolsProvider()
    service = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(raises=True),
        devtools_provider=fake_devtools,
        app_settings=_settings(domains=["google.com"], edge_devtools=True),
    )

    result = service.snapshot(SnapshotRequest())

    assert result.status == "ok"
    assert result.payload["provider"] == "edge_devtools"
    assert fake_devtools.calls[0]["action"] == "snapshot"


def test_wildcard_domains_makes_status_ready_and_allows_any_host() -> None:
    fake = FakeWebBridgeProvider()
    service = KimiWebBridgeService(
        provider=fake,
        app_settings=_settings(domains=["*"]),
    )
    assert service.status().status == "ready"
    # Any host is reachable when the operator set the wildcard.
    result = service.navigate(NavigateRequest(url="https://some-random-site.example/page"))
    assert result.status == "ok"


def test_settings_rejects_non_localhost_daemon() -> None:
    with pytest.raises(Exception, match="localhost"):
        Settings(
            enable_kimi_webbridge=True,
            kimi_webbridge_url="http://evil.example.com",
            kimi_webbridge_allowed_domains="google.com",
        )


def test_navigate_blocks_when_disabled() -> None:
    service = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(),
        app_settings=_settings(enabled=False),
    )
    with pytest.raises(KimiWebBridgeError, match="ENABLE_KIMI_WEBBRIDGE"):
        service.navigate(NavigateRequest(url="https://google.com"))


def test_navigate_rejects_domain_outside_allowlist() -> None:
    service = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(),
        app_settings=_settings(domains=["google.com"]),
    )
    with pytest.raises(KimiWebBridgeError, match="not in KIMI_WEBBRIDGE_ALLOWED_DOMAINS"):
        service.navigate(NavigateRequest(url="https://malicious.example"))


def test_navigate_accepts_subdomain_of_allowed_root() -> None:
    fake = FakeWebBridgeProvider()
    service = KimiWebBridgeService(
        provider=fake,
        app_settings=_settings(domains=["google.com"]),
    )
    result = service.navigate(NavigateRequest(url="https://mail.google.com/u/0"))
    assert result.status == "ok"
    assert fake.calls == [
        {
            "action": "navigate",
            "args": {"url": "https://mail.google.com/u/0", "newTab": True},
            "session": None,
        }
    ]


def test_sessioned_browser_actions_use_active_tab_transport() -> None:
    fake = FakeWebBridgeProvider(responses={"snapshot": {"url": "https://google.com"}})
    service = KimiWebBridgeService(
        provider=fake,
        app_settings=_settings(domains=["google.com"]),
    )

    service.navigate(NavigateRequest(url="https://google.com", session="agent-session"))
    snap = service.snapshot(SnapshotRequest(session="agent-session"))
    tabs = service.list_tabs(session="agent-session")

    assert snap.payload == {"url": "https://google.com"}
    assert fake.calls[0]["action"] == "navigate"
    assert fake.calls[0]["session"] is None
    assert fake.calls[1]["action"] == "snapshot"
    assert fake.calls[1]["session"] is None
    assert fake.calls[2]["action"] == "list_tabs"
    assert fake.calls[2]["session"] == "agent-session"
    assert tabs.status == "ok"


def test_navigate_rejects_private_ip_when_ssrf_check_enabled() -> None:
    service = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(),
        app_settings=_settings(domains=["example.com"], ssrf_check=True),
        hostname_resolver=lambda _: ["10.0.0.5"],
    )

    with pytest.raises(KimiWebBridgeError, match="non-public address"):
        service.navigate(NavigateRequest(url="https://example.com/private"))


def test_navigate_accepts_public_ip_when_ssrf_check_enabled() -> None:
    fake = FakeWebBridgeProvider()
    service = KimiWebBridgeService(
        provider=fake,
        app_settings=_settings(domains=["example.com"], ssrf_check=True),
        hostname_resolver=lambda _: ["93.184.216.34"],
    )

    result = service.navigate(NavigateRequest(url="https://example.com/page"))

    assert result.status == "ok"


def test_snapshot_and_screenshot_are_read_only_and_pass_through() -> None:
    fake = FakeWebBridgeProvider(responses={"snapshot": {"tree": "fake-tree", "url": "x"}})
    service = KimiWebBridgeService(
        provider=fake,
        app_settings=_settings(domains=["google.com"]),
    )
    snap = service.snapshot(SnapshotRequest())
    assert snap.payload == {"tree": "fake-tree", "url": "x"}
    shot = service.screenshot(ScreenshotRequest(format="jpeg", quality=60))
    assert shot.status == "ok"
    assert any(call["action"] == "screenshot" for call in fake.calls)


def test_mutating_ops_blocked_without_allow_mutations_flag() -> None:
    service = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(),
        app_settings=_settings(domains=["google.com"], mutations=False),
    )
    with pytest.raises(KimiWebBridgeError, match="KIMI_WEBBRIDGE_ALLOW_MUTATIONS"):
        service.click(ClickRequest(selector="#submit"))
    with pytest.raises(KimiWebBridgeError, match="KIMI_WEBBRIDGE_ALLOW_MUTATIONS"):
        service.fill(FillRequest(selector="#q", value="hola"))
    with pytest.raises(KimiWebBridgeError, match="KIMI_WEBBRIDGE_ALLOW_MUTATIONS"):
        service.evaluate(EvaluateRequest(code="1+1"))


def test_mutating_ops_blocked_when_approval_is_required() -> None:
    service = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(),
        app_settings=_settings(domains=["google.com"], mutations=True, require_approval=True),
    )
    with pytest.raises(KimiWebBridgeError, match="requires human approval"):
        service.click(ClickRequest(selector="#submit"))


def test_mutating_ops_work_when_flag_enabled_and_direct_approval_gate_disabled() -> None:
    fake = FakeWebBridgeProvider(responses={"click": {"success": True}})
    service = KimiWebBridgeService(
        provider=fake,
        app_settings=_settings(domains=["google.com"], mutations=True, require_approval=False),
    )
    result = service.click(ClickRequest(selector="#submit"))
    assert result.payload == {"success": True}


def test_daemon_failure_surfaces_kimi_error() -> None:
    service = KimiWebBridgeService(
        provider=FakeWebBridgeProvider(raises=True),
        app_settings=_settings(domains=["google.com"]),
    )
    with pytest.raises(KimiWebBridgeError, match="fake webbridge failure"):
        service.snapshot(SnapshotRequest())


def test_http_provider_call_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from cognitive_os.actions.kimi_webbridge import HttpWebBridgeProvider

    received: list[dict[str, Any]] = []

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        received.append({"url": url, "json": kwargs.get("json")})
        return httpx.Response(
            200,
            json={"ok": True, "data": {"success": True, "tabId": 42}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    cfg = _settings(domains=["google.com"])
    payload = HttpWebBridgeProvider(cfg).call("navigate", {"url": "https://google.com"}, "main")
    assert payload == {"success": True, "tabId": 42}
    assert received[0]["json"] == {
        "action": "navigate",
        "args": {"url": "https://google.com"},
        "session": "main",
    }


def test_http_provider_keeps_legacy_direct_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    from cognitive_os.actions.kimi_webbridge import HttpWebBridgeProvider

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        del kwargs
        return httpx.Response(
            200,
            json={"success": True, "tabs": []},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    payload = HttpWebBridgeProvider(_settings(domains=["google.com"])).call(
        "list_tabs",
        {},
        None,
    )
    assert payload == {"success": True, "tabs": []}


def test_http_provider_wraps_scalar_envelope_data(monkeypatch: pytest.MonkeyPatch) -> None:
    from cognitive_os.actions.kimi_webbridge import HttpWebBridgeProvider

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        del kwargs
        return httpx.Response(
            200,
            json={"ok": True, "data": "base64-image"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    payload = HttpWebBridgeProvider(_settings(domains=["google.com"])).call(
        "screenshot",
        {},
        None,
    )
    assert payload == {"data": "base64-image"}


def test_http_provider_raises_on_daemon_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cognitive_os.actions.kimi_webbridge import HttpWebBridgeProvider

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        del kwargs
        return httpx.Response(
            200,
            json={
                "ok": False,
                "error": {"code": "extension_error", "message": "Cannot access current tab"},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(KimiWebBridgeError, match="extension_error"):
        HttpWebBridgeProvider(_settings(domains=["google.com"])).call(
            "snapshot",
            {},
            None,
        )


def test_status_probe_unwraps_current_daemon_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cognitive_os.actions.kimi_webbridge import HttpWebBridgeProvider

    def fake_get(url: str, **kwargs: Any) -> httpx.Response:
        del kwargs
        return httpx.Response(404, text="page not found", request=httpx.Request("GET", url))

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        del kwargs
        return httpx.Response(
            200,
            json={"ok": True, "data": {"success": True, "tabs": []}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    probe = HttpWebBridgeProvider(_settings(domains=["google.com"])).status_probe()
    assert probe["running"] is True
    assert probe["extension_connected"] is True
    assert probe["tabs"] == 0


def test_http_provider_raises_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    from cognitive_os.actions.kimi_webbridge import HttpWebBridgeProvider

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(200, content=b"<<not json>>", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(KimiWebBridgeError, match="invalid JSON"):
        HttpWebBridgeProvider(_settings(domains=["google.com"])).call(
            "snapshot",
            {},
            None,
        )


@pytest.mark.asyncio
async def test_webbridge_endpoints_require_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        status_resp = await client.get("/actions/webbridge/status")
        navigate_resp = await client.post(
            "/actions/webbridge/navigate",
            json={"url": "https://google.com"},
        )
        snapshot_resp = await client.post("/actions/webbridge/snapshot", json={})
        click_resp = await client.post(
            "/actions/webbridge/click",
            json={"selector": "#x"},
        )
        fill_resp = await client.post(
            "/actions/webbridge/fill",
            json={"selector": "#x", "value": "y"},
        )
    for r in (status_resp, navigate_resp, snapshot_resp, click_resp, fill_resp):
        assert r.status_code == 401

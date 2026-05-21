"""Fase 73 — MCP client integration tests.

Covers the parser, the sync/async loaders' fail-open behavior, the
allowlist filter, and the `/system/mcp` endpoint shape. The async loader
is exercised end-to-end against a mocked `MultiServerMCPClient` so we
verify the integration contract without spinning up a real MCP server.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

import cognitive_os.api.app as api_app
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import Settings
from cognitive_os.integrations import mcp_client


def test_parse_sse_server() -> None:
    [spec] = mcp_client.parse_mcp_servers(["mem:sse:http://localhost:9001/sse"])
    assert spec.name == "mem"
    assert spec.transport == "sse"
    assert spec.target == "http://localhost:9001/sse"
    assert spec.as_connection_dict() == {
        "transport": "sse",
        "url": "http://localhost:9001/sse",
    }


def test_parse_stdio_with_extras() -> None:
    decl = "fs:stdio:/bin/mcp-fs --root /home/x::cwd=/tmp,env_TOKEN=abc"
    [spec] = mcp_client.parse_mcp_servers([decl])
    conn = spec.as_connection_dict()
    assert conn["transport"] == "stdio"
    assert conn["command"] == "/bin/mcp-fs"
    assert conn["args"] == ["--root", "/home/x"]
    assert conn["cwd"] == "/tmp"
    assert conn["env"] == {"TOKEN": "abc"}


def test_parse_drops_invalid_decls(caplog: pytest.LogCaptureFixture) -> None:
    """Broken declarations are dropped with a warning; valid ones survive."""
    with caplog.at_level("WARNING"):
        specs = mcp_client.parse_mcp_servers(["broken-no-colons", "ok:sse:http://x/sse"])
    names = [s.name for s in specs]
    assert names == ["ok"]
    assert any("broken-no-colons" in r.message for r in caplog.records)


def test_filter_tools_for_allowlist_empty_returns_all() -> None:
    class _T:
        def __init__(self, name: str) -> None:
            self.name = name

    tools = [_T("mem_search"), _T("gh_issues_list"), _T("misc_thing")]
    assert mcp_client.filter_tools_for_allowlist(tools, []) == tools


def test_filter_tools_for_allowlist_keeps_matching_prefix() -> None:
    class _T:
        def __init__(self, name: str) -> None:
            self.name = name

    tools = [_T("mem_search"), _T("gh_issues_list"), _T("misc_thing")]
    kept = mcp_client.filter_tools_for_allowlist(tools, ["mem", "gh"])
    assert {t.name for t in kept} == {"mem_search", "gh_issues_list"}


@pytest.mark.asyncio
async def test_load_mcp_tools_async_disabled_returns_empty() -> None:
    s = Settings(_env_file=None, enable_mcp_client=False)
    tools, statuses = await mcp_client.load_mcp_tools_async(s)
    assert tools == []
    assert statuses == []


@pytest.mark.asyncio
async def test_load_mcp_tools_async_records_per_server_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single broken server must not stop the others.

    We mock `MultiServerMCPClient` so `get_tools` raises for the first
    server and succeeds for the second. The loader should expose both
    statuses with the right `connected` flag.
    """

    class _FakeClient:
        def __init__(self, connections: dict, *, tool_name_prefix: bool) -> None:
            self._connections = connections

        async def get_tools(self, *, server_name: str | None = None) -> list[Any]:
            assert server_name is not None
            if server_name == "bad":
                raise RuntimeError("simulated network error")

            class _T:
                def __init__(self, name: str) -> None:
                    self.name = name

            return [_T(f"{server_name}_search"), _T(f"{server_name}_get")]

    monkeypatch.setattr("langchain_mcp_adapters.client.MultiServerMCPClient", _FakeClient)

    s = Settings(
        _env_file=None,
        enable_mcp_client=True,
        mcp_servers="bad:sse:http://bad/sse,good:sse:http://good/sse",
    )
    tools, statuses = await mcp_client.load_mcp_tools_async(s)

    by_name = {st.name: st for st in statuses}
    assert by_name["bad"].connected is False
    assert by_name["bad"].error is not None
    assert by_name["bad"].tools_count == 0

    assert by_name["good"].connected is True
    assert by_name["good"].error is None
    assert by_name["good"].tools_count == 2

    assert {getattr(t, "name", "") for t in tools} == {"good_search", "good_get"}


@pytest.mark.asyncio
async def test_system_mcp_inventory_timeout_returns_degraded_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _slow_loader(
        _settings: Settings,
    ) -> tuple[list[Any], list[mcp_client.MCPServerStatus]]:
        await asyncio.sleep(10)
        return [], []

    monkeypatch.setattr(api_app.settings, "enable_mcp_client", True, raising=False)
    monkeypatch.setattr(
        api_app.settings,
        "mcp_servers",
        ["slow:sse:http://localhost:9999/sse"],
        raising=False,
    )
    monkeypatch.setattr(api_app.settings, "mcp_inventory_timeout_seconds", 0.01, raising=False)
    monkeypatch.setattr(mcp_client, "load_mcp_tools_async", _slow_loader)

    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {create_access_token(user_id='operator')}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/system/mcp", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["declared_count"] == 1
    assert body["servers"][0]["connected"] is False
    assert "timed out" in body["servers"][0]["error"]


def test_sync_wrapper_short_circuits_off_dedicated_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sync helper must skip the network entirely outside dedicated_local
    so a multi-tenant deployment never grabs the operator-personal MCP tools.
    """
    s = Settings(
        _env_file=None,
        operator_profile="strict",
        enable_mcp_client=True,
        mcp_servers="mem:sse:http://localhost/sse",
    )
    monkeypatch.setattr(mcp_client, "settings", s)
    assert mcp_client.load_mcp_tools_for_role_sync("research") == []


class _NamedTool:
    """Minimal tool stub used by the cache tests."""

    def __init__(self, name: str) -> None:
        self.name = name


def test_sync_wrapper_caches_per_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fase 79.2: the per-role MCP tool list is cached for ~5 minutes so the
    DeepAgent factory doesn't pay the 5-server handshake on every request.
    The cache is invalidated by ``invalidate_mcp_tool_cache()`` (wired into
    /system/mcp), and an empty result is never cached so a transient outage
    cannot stick for the full TTL.
    """
    s = Settings(
        _env_file=None,
        operator_profile="dedicated_local",
        enable_mcp_client=True,
        mcp_servers="mem:sse:http://localhost/sse",
    )
    monkeypatch.setattr(mcp_client, "settings", s)
    mcp_client.invalidate_mcp_tool_cache()

    call_count = {"n": 0}

    async def _fake_load_async(_):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        return [_NamedTool("mem_recall"), _NamedTool("mem_search")], []

    monkeypatch.setattr(mcp_client, "load_mcp_tools_async", _fake_load_async)

    first = mcp_client.load_mcp_tools_for_role_sync("research")
    second = mcp_client.load_mcp_tools_for_role_sync("research")
    assert len(first) == 2
    assert len(second) == 2
    assert call_count["n"] == 1, "second call must hit the cache"

    # Invalidate and confirm the next call re-loads.
    mcp_client.invalidate_mcp_tool_cache()
    third = mcp_client.load_mcp_tools_for_role_sync("research")
    assert len(third) == 2
    assert call_count["n"] == 2

    # Different roles are cached separately.
    other = mcp_client.load_mcp_tools_for_role_sync("document_analysis")
    assert len(other) == 2
    assert call_count["n"] == 3


def test_sync_wrapper_does_not_cache_empty_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the loader returns no tools (transient error), the cache stays
    empty so the next call retries instead of returning [] for 5 minutes.
    """
    s = Settings(
        _env_file=None,
        operator_profile="dedicated_local",
        enable_mcp_client=True,
        mcp_servers="mem:sse:http://localhost/sse",
    )
    monkeypatch.setattr(mcp_client, "settings", s)
    mcp_client.invalidate_mcp_tool_cache()

    call_count = {"n": 0}

    async def _fake_load_empty(_):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        return [], []

    monkeypatch.setattr(mcp_client, "load_mcp_tools_async", _fake_load_empty)

    first = mcp_client.load_mcp_tools_for_role_sync("research")
    second = mcp_client.load_mcp_tools_for_role_sync("research")
    assert first == []
    assert second == []
    assert call_count["n"] == 2, "empty results must not be cached"

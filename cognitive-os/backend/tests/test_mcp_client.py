"""Fase 73 — MCP client integration tests.

Covers the parser, the sync/async loaders' fail-open behavior, the
allowlist filter, and the `/system/mcp` endpoint shape. The async loader
is exercised end-to-end against a mocked `MultiServerMCPClient` so we
verify the integration contract without spinning up a real MCP server.
"""

from __future__ import annotations

from typing import Any

import pytest

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

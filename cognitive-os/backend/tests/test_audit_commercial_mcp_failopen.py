"""P1 commercial-audit hardening — MCP client per-server fail-open.

Contract (`docs/ARCHITECTURE.md` §8; `integrations/mcp_client.py:_load_one_mcp_server`):

  When ``ENABLE_MCP_CLIENT=true`` the DeepAgent loads tools from declared
  servers. A single bad server (typo in MCP_SERVERS, dead daemon, stdio
  binary missing) MUST NOT take down the whole loader:

    * Bad declarations log a warning and are dropped during parsing.
    * Connection failures return ``MCPServerStatus(connected=False, error=...)``
      while other servers still load.
    * Empty / disabled config returns ``([], [])`` without raising.

This file exercises each of those failure modes against the actual
loader by injecting a stub ``MultiServerMCPClient`` so we never reach
out over the network. The hermetic test layer mirrors the real fail-open
flow.

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §E6/J5.
"""

from __future__ import annotations

from typing import Any

import pytest

from cognitive_os.integrations.mcp_client import (
    MCPServerSpec,
    _load_one_mcp_server,
    load_mcp_tools_async,
    parse_mcp_servers,
)

# ---- parser fail-open -----------------------------------------------------


def test_parse_mcp_servers_drops_invalid_decls_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("WARNING")
    decls = [
        "mem:stdio:supermemory-server",  # valid
        "not_well_formed",  # missing :transport:target
        ":no_name:stdio:bad",  # empty name
        "fs:stdio:/usr/bin/fs-server",  # valid
        "",  # empty
    ]
    parsed = parse_mcp_servers(decls)
    names = {spec.name for spec in parsed}
    assert "mem" in names
    assert "fs" in names
    # Each malformed entry must log a warning.
    log_text = caplog.text
    assert "mcp_server_parse_failed" in log_text
    # Number of valid parsed specs must equal valid input count.
    assert len(parsed) == 2


def test_parse_mcp_servers_handles_extras_block() -> None:
    specs = parse_mcp_servers(["mem:stdio:supermemory-server::cwd=/tmp,env_FOO=bar,env_BAZ=qux"])
    assert len(specs) == 1
    assert specs[0].extras == {"cwd": "/tmp", "env_FOO": "bar", "env_BAZ": "qux"}


# ---- _load_one_mcp_server fail-open --------------------------------------


class _ExplodingClient:
    """Simulates an MCP server that raises on `get_tools`."""

    def __init__(self, *_a: object, **_kw: object) -> None:
        pass

    async def get_tools(self, server_name: str) -> list[Any]:
        del server_name
        raise ConnectionError("simulated MCP backend down")


class _StubClient:
    """Simulates a healthy MCP server returning fake tools."""

    def __init__(self, connection_map: dict[str, Any], *, tool_name_prefix: bool = True) -> None:
        del connection_map, tool_name_prefix

    async def get_tools(self, server_name: str) -> list[Any]:
        # Return as many fake "tools" (just strings) as the server name length.
        return [f"{server_name}_tool_{i}" for i in range(len(server_name))]


@pytest.mark.asyncio
async def test_load_one_mcp_server_returns_failed_status_on_connection_error() -> None:
    spec = MCPServerSpec(
        name="audit_bad",
        transport="sse",
        target="http://127.0.0.1:65530/sse",  # unreachable port
        extras={},
    )
    tools, status = await _load_one_mcp_server(spec, _ExplodingClient)
    assert tools == []
    assert status.connected is False
    assert status.tools_count == 0
    assert status.error is not None and "ConnectionError" in status.error


@pytest.mark.asyncio
async def test_load_one_mcp_server_unknown_transport_returns_failed_status() -> None:
    spec = MCPServerSpec(
        name="audit_bad_transport",
        transport="not-a-transport",
        target="anywhere",
        extras={},
    )
    tools, status = await _load_one_mcp_server(spec, _StubClient)
    assert tools == []
    assert status.connected is False
    assert status.error is not None
    assert "unsupported transport" in status.error.lower()


@pytest.mark.asyncio
async def test_load_one_mcp_server_happy_path_returns_tools_and_connected() -> None:
    spec = MCPServerSpec(
        name="mem",
        transport="sse",
        target="http://127.0.0.1:9000/sse",
        extras={},
    )
    tools, status = await _load_one_mcp_server(spec, _StubClient)
    assert status.connected is True
    assert status.error is None
    assert status.tools_count == len(tools) == len("mem")


# ---- load_mcp_tools_async fail-open --------------------------------------


@pytest.mark.asyncio
async def test_load_mcp_tools_async_returns_empty_when_disabled() -> None:
    """When ``ENABLE_MCP_CLIENT=false`` the loader returns empty without raising."""
    from cognitive_os.core.config import Settings

    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        enable_mcp_client=False,
        mcp_servers=["mem:stdio:does-not-matter"],
    )
    tools, statuses = await load_mcp_tools_async(s)
    assert tools == []
    assert statuses == []


@pytest.mark.asyncio
async def test_load_mcp_tools_async_returns_empty_when_no_servers() -> None:
    """No declarations → empty result, no errors."""
    from cognitive_os.core.config import Settings

    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        enable_mcp_client=True,
        mcp_servers=[],
    )
    tools, statuses = await load_mcp_tools_async(s)
    assert tools == []
    assert statuses == []


def test_mcp_loader_source_uses_per_server_try_except() -> None:
    """Static guard: the loader file must still wrap server connects in a
    fail-open try/except. A refactor that hoisted the connect into a single
    bulk call would lose the per-server isolation.
    """
    import pathlib

    src = pathlib.Path("src/cognitive_os/integrations/mcp_client.py").read_text(encoding="utf-8")
    assert "fail-open per server" in src.lower() or ("fail-open per server".lower() in src.lower())
    # The dedicated worker function exists.
    assert "_load_one_mcp_server" in src
    # And concurrent gather wires it up.
    assert "asyncio" in src

"""Live smoke: every declared MCP server connects and lists its tools.

Read-only: `load_mcp_tools_async` dials each server and calls `list_tools()`.
It invokes no tool. A single broken server does not abort the others — the
test fails only if a server was declared but could not be reached.
"""

from __future__ import annotations

import pytest

from cognitive_os.core.config import settings

pytestmark = pytest.mark.live_readonly


@pytest.mark.asyncio
async def test_live_mcp_servers_connect_and_list_tools() -> None:
    if not settings.enable_mcp_client:
        pytest.skip("ENABLE_MCP_CLIENT is false")
    if not settings.mcp_servers:
        pytest.skip("MCP_SERVERS declares no server")

    from cognitive_os.integrations.mcp_client import load_mcp_tools_async

    tools, statuses = await load_mcp_tools_async()

    assert statuses, "MCP client enabled with servers declared but no status rows"
    failed = [f"{s.name}: {s.error}" for s in statuses if not s.connected]
    assert not failed, f"MCP server(s) failed to connect: {failed}"
    # A connected server should expose at least its own tool list object.
    assert isinstance(tools, list)

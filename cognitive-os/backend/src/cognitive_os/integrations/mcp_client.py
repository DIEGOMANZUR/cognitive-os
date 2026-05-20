"""MCP (Model Context Protocol) client integration.

Operator-declared MCP servers reach the DeepAgent as additional `StructuredTool`s
side-by-side with the 21 built-ins. The connection is opt-in
(`ENABLE_MCP_CLIENT=true`) and per-server (declarations in `MCP_SERVERS`) so a
fresh install ships with zero external dependencies — the operator decides
when to wire Supermemory, GitHub, a local filesystem MCP, etc.

Declarations follow the syntax described in `Settings.mcp_servers`:

    name:transport:target[:extra=value,...]

Transports:

- ``sse``               — target = URL (e.g. http://localhost:9001/sse)
- ``streamable_http``   — target = URL of an HTTP-streaming MCP server
- ``stdio``             — target = command line (shell-quoted); extras may set
                          ``cwd=/path`` and ``env_FOO=bar`` to seed env vars

The loader is async-only (the underlying `MultiServerMCPClient` is). Callers
that live in sync contexts (Celery tasks, the Telegram bot) must hop into an
event loop. Failures degrade gracefully: a single bad server logs a warning
and is skipped — the rest still load. (Fase 73 B.)
"""

from __future__ import annotations

import logging
import shlex
from dataclasses import dataclass
from typing import Any, cast

from cognitive_os.core.config import Settings, settings

logger = logging.getLogger(__name__)

_TRANSPORTS_URL: frozenset[str] = frozenset({"sse", "streamable_http", "websocket"})
_TRANSPORTS_STDIO: frozenset[str] = frozenset({"stdio"})


@dataclass(frozen=True)
class MCPServerSpec:
    """Parsed MCP server declaration ready for `MultiServerMCPClient`."""

    name: str
    transport: str
    target: str
    extras: dict[str, str]

    def as_connection_dict(self) -> dict[str, Any]:
        """Translate to the dict shape `MultiServerMCPClient` expects."""
        if self.transport in _TRANSPORTS_URL:
            entry: dict[str, Any] = {
                "transport": self.transport,
                "url": self.target,
            }
            headers = {
                key.removeprefix("header_"): value
                for key, value in self.extras.items()
                if key.startswith("header_")
            }
            if headers:
                entry["headers"] = headers
            return entry
        if self.transport in _TRANSPORTS_STDIO:
            argv = shlex.split(self.target)
            if not argv:
                msg = f"MCP server {self.name!r}: empty stdio command."
                raise ValueError(msg)
            entry = {
                "transport": "stdio",
                "command": argv[0],
                "args": argv[1:],
            }
            cwd = self.extras.get("cwd")
            if cwd:
                entry["cwd"] = cwd
            env = {
                key.removeprefix("env_"): value
                for key, value in self.extras.items()
                if key.startswith("env_")
            }
            if env:
                entry["env"] = env
            return entry
        msg = f"MCP server {self.name!r}: unsupported transport {self.transport!r}."
        raise ValueError(msg)


def parse_mcp_servers(declarations: list[str]) -> list[MCPServerSpec]:
    """Parse the CSV declarations from `MCP_SERVERS`.

    Bad declarations log a warning and are dropped so a single typo can't
    silence the entire client.
    """
    parsed: list[MCPServerSpec] = []
    for decl in declarations:
        try:
            spec = _parse_one(decl)
        except ValueError as exc:
            logger.warning("mcp_server_parse_failed decl=%r error=%s", decl, exc)
            continue
        parsed.append(spec)
    return parsed


def _parse_one(decl: str) -> MCPServerSpec:
    raw = decl.strip()
    if not raw:
        msg = "empty declaration"
        raise ValueError(msg)
    # Format: name:transport:target[:k=v,k=v,...]
    head, _, extras_part = raw.partition("::")
    if extras_part:
        # `::` is the optional separator before the extras block, kept simple
        # so URLs containing single colons (e.g. https://host:8080/sse) work.
        body = head
        extras = _parse_extras(extras_part)
    else:
        body = raw
        extras = {}
    name_part, _, rest = body.partition(":")
    transport, _, target = rest.partition(":")
    if not name_part or not transport or not target:
        msg = "expected `name:transport:target`"
        raise ValueError(msg)
    return MCPServerSpec(
        name=name_part.strip(),
        transport=transport.strip(),
        target=target.strip(),
        extras=extras,
    )


def _parse_extras(extras_block: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for piece in extras_block.split(","):
        if not piece.strip():
            continue
        key, _, value = piece.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        pairs[key] = value
    return pairs


@dataclass(frozen=True)
class MCPServerStatus:
    name: str
    transport: str
    target: str
    connected: bool
    tools_count: int
    error: str | None


async def load_mcp_tools_async(
    app_settings: Settings | None = None,
) -> tuple[list[Any], list[MCPServerStatus]]:
    """Connect to all declared MCP servers and return their tools + status.

    Returns ``(tools, statuses)`` so callers can inject tools into the agent
    AND publish the status table to `/system/mcp` / the UI tile. Each server
    is attempted in isolation: a single broken server does not stop the
    others (best-effort fail-open, the operator sees the failure in the UI).

    Returns empty lists when the client is disabled or no servers are
    declared — safe to call unconditionally from the DeepAgent factories.
    """
    s = app_settings or settings
    if not s.enable_mcp_client or not s.mcp_servers:
        return [], []

    try:
        from langchain_mcp_adapters.client import (  # noqa: PLC0415
            MultiServerMCPClient,
        )
    except ImportError as exc:
        logger.warning("mcp_adapter_unavailable error=%s", exc)
        return [], []

    specs = parse_mcp_servers(s.mcp_servers)
    if not specs:
        return [], []

    tools: list[Any] = []
    statuses: list[MCPServerStatus] = []
    for spec in specs:
        try:
            connection = spec.as_connection_dict()
        except ValueError as exc:
            logger.warning("mcp_server_config_failed name=%s error=%s", spec.name, exc)
            statuses.append(
                MCPServerStatus(
                    name=spec.name,
                    transport=spec.transport,
                    target=spec.target,
                    connected=False,
                    tools_count=0,
                    error=str(exc),
                )
            )
            continue
        try:
            # `MultiServerMCPClient` ships TypedDicts per transport for the
            # connection value. Our parser produces the right shape at runtime
            # but typing the whole branching union here would force us to
            # restructure the parser around literals. `cast` keeps the runtime
            # contract and silences mypy without sacrificing the dataclass.
            client = MultiServerMCPClient(cast(Any, {spec.name: connection}), tool_name_prefix=True)
            server_tools = await client.get_tools(server_name=spec.name)
        except Exception as exc:  # noqa: BLE001 — fail-open per server
            logger.warning(
                "mcp_server_connect_failed name=%s transport=%s error=%s",
                spec.name,
                spec.transport,
                type(exc).__name__,
            )
            statuses.append(
                MCPServerStatus(
                    name=spec.name,
                    transport=spec.transport,
                    target=spec.target,
                    connected=False,
                    tools_count=0,
                    error=f"{type(exc).__name__}: {exc}"[:200],
                )
            )
            continue
        tools.extend(server_tools)
        statuses.append(
            MCPServerStatus(
                name=spec.name,
                transport=spec.transport,
                target=spec.target,
                connected=True,
                tools_count=len(server_tools),
                error=None,
            )
        )
    return tools, statuses


def load_mcp_tools_for_role_sync(role: str) -> list[Any]:
    """Sync wrapper used by Celery / Telegram code paths.

    Returns the MCP tools allowed for ``role`` (``"research"`` or
    ``"document_analysis"``) under the operator's profile. Empty list if the
    client is disabled, no servers are declared, no event loop is available,
    or the loader times out. The DeepAgent simply runs without MCP tools in
    any failure mode — never blocks the task.
    """
    s = settings
    if not s.enable_mcp_client or not s.mcp_servers:
        return []
    if s.operator_profile != "dedicated_local":
        # External MCP tools are operator-personal (their credentials).
        # Only the dedicated_local profile expects to consume them.
        return []

    import asyncio  # noqa: PLC0415

    allowlist_map = {
        "research": s.mcp_allowed_for_research,
        "document_analysis": s.mcp_allowed_for_document_analysis,
    }
    allowlist = list(allowlist_map.get(role, []))

    async def _runner() -> list[Any]:
        tools, _statuses = await load_mcp_tools_async(s)
        return filter_tools_for_allowlist(tools, allowlist)

    try:
        return asyncio.run(asyncio.wait_for(_runner(), timeout=s.mcp_call_timeout_seconds))
    except RuntimeError:
        # asyncio.run inside an already-running loop is invalid. Fall back to
        # an isolated loop on a worker thread.
        import concurrent.futures  # noqa: PLC0415

        def _spawn() -> list[Any]:
            return asyncio.run(asyncio.wait_for(_runner(), timeout=s.mcp_call_timeout_seconds))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            try:
                return pool.submit(_spawn).result(timeout=s.mcp_call_timeout_seconds + 5)
            except Exception as exc:  # noqa: BLE001
                logger.warning("mcp_sync_wrapper_failed error=%s", type(exc).__name__)
                return []
    except Exception as exc:  # noqa: BLE001 - never break the agent
        logger.warning("mcp_sync_wrapper_failed error=%s", type(exc).__name__)
        return []


def filter_tools_for_allowlist(tools: list[Any], allowlist: list[str]) -> list[Any]:
    """Keep only tools whose name prefix matches an allow-listed server name.

    `tool_name_prefix=True` upstream gives names like ``<server>_<tool>``. An
    empty allowlist means "expose every loaded MCP tool" so the default of
    no `.env` allow-list still works for the operator who just declared one
    or two servers and trusts everything.
    """
    if not allowlist:
        return list(tools)
    prefixes = tuple(f"{name}_" for name in allowlist)
    return [t for t in tools if str(getattr(t, "name", "")).startswith(prefixes)]

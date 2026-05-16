"""Bridge to OpenHarness QueryEngine (HKUDS/OpenHarness), fused into Cognitive OS.

This is not a standalone harness: LangGraph orchestrates flows; LangChain DeepAgents
still produces structured DeepAgentResult. OpenHarness complements with a proven,
tool-heavy loop (QueryEngine + OpenAICompatibleClient retries + permissive execution)
when presets ask for more than \"grepglob\" deep-research prelude.

Docs: preset `research` aligns with upstream `openharness.tools.create_default_tool_registry`
minus MCP servers until we wire MCPConfig from Cognitive OS.
"""

from __future__ import annotations

import asyncio
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from cognitive_os.core.config import Settings

logger = structlog.get_logger(__name__)

_OPENHARNESS_SPEC = importlib.util.find_spec("openharness")


def is_openharness_available() -> bool:
    return _OPENHARNESS_SPEC is not None


def resolve_openharness_cwd(settings: Settings, thread_id: str | None, task_id: str | None) -> Path:
    """Match DeepAgents workspace when `deepagent_mirror` so OH sees the same files."""
    if settings.openharness_workspace_mode == "deepagent_mirror" and thread_id and task_id:
        return (Path(settings.local_storage_dir) / "workspaces" / thread_id / task_id).resolve()
    return Path(settings.openharness_workspace).resolve()


@dataclass(frozen=True, slots=True)
class OpenHarnessResearchResult:
    ok: bool
    answer: str = ""
    error: str | None = None
    skipped_reason: str | None = None


def _research_system_prompt() -> str:
    return (
        "You are OpenHarness tooling inside Cognitive OS (LangGraph + DeepAgents downstream).\n"
        "Prefer accurate, cited short notes the orchestrator will merge into a structured report.\n"
        "Use Spanish when user content is Spanish. Never fabricate accesses outside cwd."
    )


def build_tool_registry(app_settings: Settings, *, web_allowed: bool) -> Any:
    preset = app_settings.openharness_toolkit_preset
    web_on = web_allowed and app_settings.openharness_web_tools

    if preset == "full":
        from openharness.tools import create_default_tool_registry
        from openharness.tools.base import ToolRegistry

        upstream = create_default_tool_registry(None)
        if web_on:
            return upstream
        filtered = ToolRegistry()
        for tool in upstream.list_tools():
            if tool.name in {"web_search", "web_fetch"}:
                continue
            filtered.register(tool)
        return filtered

    from openharness.tools.base import ToolRegistry

    registry = ToolRegistry()
    from openharness.tools.glob_tool import GlobTool
    from openharness.tools.grep_tool import GrepTool

    if preset == "minimal":
        registry.register(GrepTool())
        registry.register(GlobTool())
        if app_settings.openharness_include_file_tools:
            from openharness.tools.file_read_tool import FileReadTool

            registry.register(FileReadTool())
        if web_on:
            from openharness.tools.web_fetch_tool import WebFetchTool
            from openharness.tools.web_search_tool import WebSearchTool

            registry.register(WebSearchTool())
            registry.register(WebFetchTool())
        return registry

    from openharness.tools.agent_tool import AgentTool
    from openharness.tools.ask_user_question_tool import AskUserQuestionTool
    from openharness.tools.bash_tool import BashTool
    from openharness.tools.brief_tool import BriefTool
    from openharness.tools.config_tool import ConfigTool
    from openharness.tools.cron_create_tool import CronCreateTool
    from openharness.tools.cron_delete_tool import CronDeleteTool
    from openharness.tools.cron_list_tool import CronListTool
    from openharness.tools.cron_toggle_tool import CronToggleTool
    from openharness.tools.enter_plan_mode_tool import EnterPlanModeTool
    from openharness.tools.enter_worktree_tool import EnterWorktreeTool
    from openharness.tools.exit_plan_mode_tool import ExitPlanModeTool
    from openharness.tools.exit_worktree_tool import ExitWorktreeTool
    from openharness.tools.file_edit_tool import FileEditTool
    from openharness.tools.file_read_tool import FileReadTool
    from openharness.tools.file_write_tool import FileWriteTool
    from openharness.tools.image_to_text_tool import ImageToTextTool
    from openharness.tools.lsp_tool import LspTool
    from openharness.tools.mcp_auth_tool import McpAuthTool
    from openharness.tools.notebook_edit_tool import NotebookEditTool
    from openharness.tools.remote_trigger_tool import RemoteTriggerTool
    from openharness.tools.send_message_tool import SendMessageTool
    from openharness.tools.skill_tool import SkillTool
    from openharness.tools.sleep_tool import SleepTool
    from openharness.tools.task_create_tool import TaskCreateTool
    from openharness.tools.task_get_tool import TaskGetTool
    from openharness.tools.task_list_tool import TaskListTool
    from openharness.tools.task_output_tool import TaskOutputTool
    from openharness.tools.task_stop_tool import TaskStopTool
    from openharness.tools.task_update_tool import TaskUpdateTool
    from openharness.tools.team_create_tool import TeamCreateTool
    from openharness.tools.team_delete_tool import TeamDeleteTool
    from openharness.tools.todo_write_tool import TodoWriteTool
    from openharness.tools.tool_search_tool import ToolSearchTool
    from openharness.tools.web_fetch_tool import WebFetchTool
    from openharness.tools.web_search_tool import WebSearchTool

    research_tools: list[Any] = [
        BashTool(),
        AskUserQuestionTool(),
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        NotebookEditTool(),
        GlobTool(),
        GrepTool(),
        ImageToTextTool(),
        LspTool(),
        SkillTool(),
        ToolSearchTool(),
        ConfigTool(),
        BriefTool(),
        SleepTool(),
        EnterWorktreeTool(),
        ExitWorktreeTool(),
        TodoWriteTool(),
        EnterPlanModeTool(),
        ExitPlanModeTool(),
        CronCreateTool(),
        CronListTool(),
        CronDeleteTool(),
        CronToggleTool(),
        RemoteTriggerTool(),
        TaskCreateTool(),
        TaskGetTool(),
        TaskListTool(),
        TaskStopTool(),
        TaskOutputTool(),
        TaskUpdateTool(),
        AgentTool(),
        SendMessageTool(),
        TeamCreateTool(),
        TeamDeleteTool(),
        McpAuthTool(),
    ]
    if web_on:
        research_tools.append(WebSearchTool())
        research_tools.append(WebFetchTool())
    for tool in research_tools:
        registry.register(tool)
    return registry


def _permission_context(app_settings: Settings) -> Any:
    """Headless Fusion: PLAN for minimal presets; FULL_AUTO when multi-tool OH runs."""
    from openharness.config.settings import PermissionSettings
    from openharness.permissions.modes import PermissionMode

    preset = app_settings.openharness_toolkit_preset
    mode = PermissionMode.PLAN if preset == "minimal" else PermissionMode.FULL_AUTO
    return PermissionSettings(mode=mode)


async def _run_engine_inner(
    app_settings: Settings,
    user_message: str,
    cwd: Path,
    *,
    web_allowed: bool,
) -> OpenHarnessResearchResult:
    from openharness.api.openai_client import OpenAICompatibleClient
    from openharness.engine.query_engine import QueryEngine
    from openharness.engine.stream_events import ErrorEvent
    from openharness.permissions.checker import PermissionChecker

    cwd.mkdir(parents=True, exist_ok=True)

    api_key = app_settings.primary_llm_api_key.get_secret_value()
    client = OpenAICompatibleClient(api_key=api_key, base_url=app_settings.primary_llm_base_url)
    registry = build_tool_registry(app_settings, web_allowed=web_allowed)
    perm = PermissionChecker(_permission_context(app_settings))
    engine = QueryEngine(
        api_client=client,
        tool_registry=registry,
        permission_checker=perm,
        cwd=cwd,
        model=app_settings.primary_llm_model,
        system_prompt=_research_system_prompt(),
        max_tokens=4096,
        max_turns=app_settings.openharness_max_turns,
        settings=None,
    )
    errors: list[str] = []
    async for event in engine.submit_message(user_message.strip()):
        if isinstance(event, ErrorEvent):
            errors.append(event.message)

    text = ""
    for msg in reversed(engine.messages):
        if getattr(msg, "role", None) == "assistant":
            text = msg.text
            break

    if errors and not text.strip():
        return OpenHarnessResearchResult(
            ok=False,
            error="; ".join(errors),
        )
    if not text.strip():
        return OpenHarnessResearchResult(
            ok=False,
            error="OpenHarness returned an empty assistant message.",
        )
    return OpenHarnessResearchResult(ok=True, answer=text.strip())


async def _run_engine(
    app_settings: Settings,
    user_message: str,
    cwd: Path,
    *,
    web_allowed: bool,
) -> OpenHarnessResearchResult:
    timeout = float(app_settings.openharness_query_timeout_seconds)
    return await asyncio.wait_for(
        _run_engine_inner(app_settings, user_message, cwd, web_allowed=web_allowed),
        timeout=timeout,
    )


def _execute_engine_blocking(
    app_settings: Settings,
    user_message: str,
    cwd: Path,
    *,
    web_allowed: bool,
) -> OpenHarnessResearchResult:
    """Run the async engine on a fresh event loop in a dedicated thread.

    Doing this inside a thread guarantees correctness whether or not the caller
    already has an event loop running (LangGraph nodes can be invoked from sync
    or async stacks). Without this aislamiento, calling `asyncio.run` from an
    async context would raise `RuntimeError: asyncio.run() cannot be called
    from a running event loop`, silently degrading the research path.
    """

    def _runner() -> OpenHarnessResearchResult:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(
                _run_engine(app_settings, user_message, cwd, web_allowed=web_allowed)
            )
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                logger.debug("openharness_loop_shutdown_failed", exc_info=True)
            asyncio.set_event_loop(None)
            loop.close()

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="openharness") as pool:
        future = pool.submit(_runner)
        return future.result()


def run_openharness_research_sync(
    app_settings: Settings,
    user_message: str,
    *,
    workspace_root: Path | None = None,
    thread_id: str | None = None,
    task_id: str | None = None,
    web_allowed: bool = True,
) -> OpenHarnessResearchResult:
    # Cheapest, least invasive checks first so the bridge degrades predictably:
    # disabled by config wins over "package missing" wins over "empty query".
    if not app_settings.enable_openharness_research:
        return OpenHarnessResearchResult(ok=False, skipped_reason="disabled")
    if not is_openharness_available():
        return OpenHarnessResearchResult(ok=False, skipped_reason="openharness_not_installed")
    if not (user_message or "").strip():
        return OpenHarnessResearchResult(ok=False, skipped_reason="empty_query")

    cwd = (
        workspace_root
        if workspace_root is not None
        else resolve_openharness_cwd(app_settings, thread_id, task_id)
    ).resolve()

    try:
        return _execute_engine_blocking(app_settings, user_message, cwd, web_allowed=web_allowed)
    except TimeoutError:
        secs = app_settings.openharness_query_timeout_seconds
        logger.warning("openharness_query_timeout", seconds=secs)
        return OpenHarnessResearchResult(
            ok=False,
            error=f"OpenHarness exceeded timeout ({secs}s)",
        )
    except RuntimeError as exc:
        logger.warning("openharness_async_runtime_error", error=str(exc))
        return OpenHarnessResearchResult(ok=False, error=str(exc))
    except Exception as exc:
        logger.exception("openharness_research_failed")
        return OpenHarnessResearchResult(ok=False, error=str(exc))

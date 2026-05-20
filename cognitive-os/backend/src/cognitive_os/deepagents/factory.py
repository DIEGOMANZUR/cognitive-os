from __future__ import annotations

import inspect
from typing import Any, cast

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend

from cognitive_os.agents.llm_factory import create_agent_chat_model
from cognitive_os.core.config import settings
from cognitive_os.deepagents.schemas import (
    DeepAgentResult,
    DeepAgentTask,
    DeepAgentToolPolicy,
    DeepAgentWorkspace,
)
from cognitive_os.deepagents.tools import build_deepagent_tools

SENSITIVE_INTERRUPT_TOOLS = {
    "execute": True,
    "shell": True,
    "bash": True,
    "browser_action": True,
    "send_email": True,
    "publish_social_post": True,
    "delete_file": True,
    "edit_project_file": True,
}


def create_controlled_deep_agent(
    task: DeepAgentTask,
    policy: DeepAgentToolPolicy,
    workspace: DeepAgentWorkspace,
    *,
    system_prompt: str,
    skills_paths: list[str] | None = None,
    startup_memory: str | None = None,
    memory_paths: list[str] | None = None,
    tools: list[Any] | None = None,
    mcp_tools: list[Any] | None = None,
    response_format: Any | None = None,
) -> Any:
    workspace.root_dir.mkdir(parents=True, exist_ok=True)
    agent_tools = tools or build_deepagent_tools(
        policy=policy,
        workspace=workspace,
        allowed_doc_ids=task.allowed_doc_ids,
        user_id=task.user_id,
        mcp_tools=mcp_tools,
    )
    backend = FilesystemBackend(
        root_dir=workspace.root_dir,
        virtual_mode=True,
        max_file_size_mb=2,
    )
    permissions = [
        FilesystemPermission(operations=["read", "write"], paths=["/**"], mode="allow"),
    ]
    create_kwargs: dict[str, Any] = {
        "model": create_agent_chat_model(),
        "tools": agent_tools,
        "system_prompt": _system_prompt(
            task,
            system_prompt,
            skills_paths=skills_paths or [],
            startup_memory=startup_memory,
        ),
        "permissions": permissions,
        "backend": backend,
        "interrupt_on": cast(Any, SENSITIVE_INTERRUPT_TOOLS),
        "response_format": response_format or DeepAgentResult,
        "debug": False,
        "name": f"cognitive_os_{task.task_type}_deepagent",
    }
    supported_parameters = inspect.signature(create_deep_agent).parameters
    if "skills" in supported_parameters and skills_paths:
        create_kwargs["skills"] = skills_paths
    resolved_memory_paths = _prepare_memory_paths(
        workspace,
        startup_memory=startup_memory,
        memory_paths=memory_paths,
    )
    if "memory" in supported_parameters and resolved_memory_paths:
        create_kwargs["memory"] = resolved_memory_paths
    subagents_enabled = (
        "subagents" in supported_parameters
        and settings.deepagents_enable_subagents
        and task.metadata.get("enable_subagents", True)
    )
    if subagents_enabled:
        create_kwargs["subagents"] = build_controlled_subagents(
            task,
            policy,
            tools=agent_tools,
            permissions=permissions,
            skills_paths=skills_paths or [],
        )
    return create_deep_agent(**create_kwargs)


def build_controlled_subagents(
    task: DeepAgentTask,
    policy: DeepAgentToolPolicy,
    *,
    tools: list[Any],
    permissions: list[Any],
    skills_paths: list[str],
) -> list[Any]:
    """Build safe synchronous subagents for DeepAgents 0.6.x.

    DeepAgents adds a general-purpose subagent by default. Cognitive OS adds
    narrow, policy-bound specialists so the supervisor can quarantine large RAG,
    citation, timeline and contradiction work without granting extra powers.
    """
    if not task.metadata.get("enable_subagents", True):
        return []

    if task.task_type == "document_analysis":
        return [
            _subagent(
                name="evidence-matrix-specialist",
                description=(
                    "Builds fact/evidence/citation matrices from allowed local documents."
                ),
                system_prompt=(
                    "You are a document evidence specialist. Use only allowed documents. "
                    "Return compact findings with doc_id, chunk_id and page references."
                ),
                tools=tools,
                permissions=permissions,
                skills_paths=skills_paths,
            ),
            _subagent(
                name="timeline-specialist",
                description="Extracts dated events and uncertainty from allowed evidence.",
                system_prompt=(
                    "You are a chronology specialist. Extract dates, actors and source "
                    "citations. Mark inferred or uncertain dates explicitly."
                ),
                tools=tools,
                permissions=permissions,
                skills_paths=skills_paths,
            ),
            _subagent(
                name="contradiction-reviewer",
                description="Finds contradictions, gaps and unsupported claims.",
                system_prompt=(
                    "You are a contradiction reviewer. Compare claims against evidence, "
                    "flag unsupported claims, and never invent missing facts."
                ),
                tools=tools,
                permissions=permissions,
                skills_paths=skills_paths,
            ),
        ]

    subagents = [
        _subagent(
            name="local-rag-researcher",
            description="Searches allowed local documents and returns cited evidence only.",
            system_prompt=(
                "You are a local RAG researcher. Prefer search_local_docs and "
                "read_document_pages. Only use allowed_doc_ids. Return evidence with citations."
            ),
            tools=tools,
            permissions=permissions,
            skills_paths=skills_paths,
        ),
        _subagent(
            name="citation-auditor",
            description="Checks whether an answer has adequate citations and uncertainty notes.",
            system_prompt=(
                "You are a citation auditor. Verify that claims have doc_id/chunk_id/page or "
                "URL citations. Report missing evidence and uncertainty clearly."
            ),
            tools=tools,
            permissions=permissions,
            skills_paths=skills_paths,
        ),
    ]
    if policy.allow_web and task.web_allowed:
        subagents.append(
            _subagent(
                name="web-researcher",
                description="Runs web research only when web access is enabled by policy.",
                system_prompt=(
                    "You are a web researcher. Use web search only when policy allows it. "
                    "Return source URLs, titles and dates when available."
                ),
                tools=tools,
                permissions=permissions,
                skills_paths=skills_paths,
            )
        )
    return subagents


def _subagent(
    *,
    name: str,
    description: str,
    system_prompt: str,
    tools: list[Any],
    permissions: list[Any],
    skills_paths: list[str],
) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "name": name,
        "description": description,
        "system_prompt": system_prompt,
        "tools": tools,
        "permissions": permissions,
        "interrupt_on": cast(Any, SENSITIVE_INTERRUPT_TOOLS),
    }
    if skills_paths:
        spec["skills"] = skills_paths
    return spec


def _prepare_memory_paths(
    workspace: DeepAgentWorkspace,
    *,
    startup_memory: str | None,
    memory_paths: list[str] | None,
) -> list[str]:
    resolved = list(memory_paths or [])
    if startup_memory and startup_memory.strip():
        memory_dir = workspace.root_dir / ".cognitive_os"
        memory_dir.mkdir(parents=True, exist_ok=True)
        memory_file = memory_dir / "AGENTS.md"
        memory_file.write_text(
            "# Cognitive OS Startup Memory\n\n" + startup_memory.strip() + "\n",
            encoding="utf-8",
        )
        resolved.append("./.cognitive_os/AGENTS.md")
    return resolved


def _system_prompt(
    task: DeepAgentTask,
    system_prompt: str,
    *,
    skills_paths: list[str],
    startup_memory: str | None,
) -> str:
    skills_summary = "\n".join(f"- {path}" for path in skills_paths) or "- none"
    memory_summary = startup_memory.strip() if startup_memory else "No startup memory loaded."
    restrictions = f"""
Restricciones runtime:
- task_id: {task.task_id}
- thread_id: {task.thread_id}
- tipo: {task.task_type}
- max_iterations: {task.max_iterations}
- budget_usd_limit: {task.budget_usd_limit}
- require_citations: {task.require_citations}
- web_allowed: {task.web_allowed}
- allowed_doc_ids: {task.allowed_doc_ids}

Skills disponibles:
{skills_summary}

Memoria de arranque redactada:
{memory_summary}

Usa solo las herramientas permitidas. Si detectas una accion externa, no la ejecutes:
agregala a requested_external_actions.
No edites skills core ni memoria directamente. Para memoria usa propose_memory_update.
"""
    return f"{system_prompt.strip()}\n\n{restrictions.strip()}"

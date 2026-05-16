from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

from cognitive_os.core.config import settings
from cognitive_os.deepagents.factory import create_controlled_deep_agent
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService
from cognitive_os.deepagents.schemas import (
    DeepAgentResult,
    DeepAgentTask,
    DeepAgentToolPolicy,
    DeepAgentWorkspace,
)
from cognitive_os.deepagents.skills_registry import DeepAgentSkillsRegistry
from cognitive_os.tools.policy import ToolAuditRecord, ToolRiskLevel, record_audit_event

SYSTEM_PROMPT_RESEARCH = """
Eres un subagente de investigación profunda dentro de Cognitive OS.

No eres el orquestador principal. Trabajas bajo políticas estrictas.

Objetivo:
Investigar una pregunta compleja usando solo las herramientas permitidas y devolver un informe
verificable.

Reglas:
1. No inventes hechos.
2. Separa hechos, inferencias e incertidumbre.
3. Usa documentos locales cuando estén disponibles.
4. Cita siempre con doc_id, chunk_id y páginas cuando uses RAG local.
5. Si usas web, cita URL, título y fecha si está disponible.
6. No ejecutes shell.
7. No intentes acceder a archivos fuera del workspace.
8. No envíes emails.
9. No publiques en redes.
10. No modifiques archivos del proyecto.
11. Si falta evidencia, di claramente qué falta.
12. Si una solicitud implica acción externa, no la ejecutes: repórtala como
requested_external_actions.
13. Devuelve una respuesta útil, estructurada y auditabile.
"""


def build_research_user_message_content(task: DeepAgentTask) -> str:
    """Une preludio OpenHarness (si existe en metadata) con la pregunta del usuario."""
    prelude = ""
    raw = task.metadata.get("openharness_prelude") if task.metadata else None
    if isinstance(raw, str) and raw.strip():
        prelude = (
            "Preludio de OpenHarness (QueryEngine dentro de Cognitive OS).\n"
            "Integra y contrasta estos apuntes con tu propia evidencia y citas.\n\n"
            f"{raw.strip()}\n\n---\n\n"
        )
    return (
        f"{prelude}Pregunta: {task.query}\n"
        "Devuelve DeepAgentResult estructurado. No ejecutes acciones externas."
    )


def build_research_deepagent(task: DeepAgentTask) -> Any:
    workspace = create_workspace(task)
    policy = research_policy(task)
    skills_paths, startup_memory = _skills_and_memory(task, "research")
    return create_controlled_deep_agent(
        task,
        policy,
        workspace,
        system_prompt=SYSTEM_PROMPT_RESEARCH,
        skills_paths=skills_paths,
        startup_memory=startup_memory,
    )


def run_research_deepagent(task: DeepAgentTask) -> DeepAgentResult:
    workspace = create_workspace(task)
    policy = research_policy(task)
    skills_paths, startup_memory = _skills_and_memory(task, "research")
    agent = create_controlled_deep_agent(
        task,
        policy,
        workspace,
        system_prompt=SYSTEM_PROMPT_RESEARCH,
        skills_paths=skills_paths,
        startup_memory=startup_memory,
    )
    raw_output = agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=build_research_user_message_content(task),
                )
            ]
        }
    )
    result = coerce_deepagent_result(raw_output, task)
    report_path = workspace.root_dir / "report.md"
    report_path.write_text(_report_markdown(result), encoding="utf-8")
    result.generated_files.append("report.md")
    _write_result_json(workspace, result)
    _audit(task, "deepagent_research_finished")
    return result


def research_policy(task: DeepAgentTask) -> DeepAgentToolPolicy:
    return DeepAgentToolPolicy(
        allow_local_rag=True,
        allow_neo4j_read=True,
        allow_web=task.web_allowed and settings.web_search_enabled,
        allow_workspace_write=True,
        allow_shell=False,
        allow_browser=False,
        allow_email=False,
        allow_social_posting=False,
        allow_delete=False,
    )


def create_workspace(task: DeepAgentTask) -> DeepAgentWorkspace:
    root = Path(settings.local_storage_dir) / "workspaces" / task.thread_id / task.task_id
    root.mkdir(parents=True, exist_ok=True)
    return DeepAgentWorkspace(root_dir=root, thread_id=task.thread_id, task_id=task.task_id)


def _skills_and_memory(task: DeepAgentTask, agent_name: str) -> tuple[list[str], str | None]:
    registry = DeepAgentSkillsRegistry()
    skills_paths = registry.get_enabled_skill_paths(
        agent_name,
        task.task_type,
        user_id=task.user_id,
    )
    if not settings.deepagents_enable_memory:
        return skills_paths, None
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        return skills_paths, None
    try:
        startup_memory = asyncio.run(
            DeepAgentMemoryService().get_startup_memory(
                agent_name,
                user_id=task.user_id,
                thread_id=task.thread_id,
            )
        )
    except Exception:
        startup_memory = None
    return skills_paths, startup_memory


def coerce_deepagent_result(raw_output: Any, task: DeepAgentTask) -> DeepAgentResult:
    if isinstance(raw_output, DeepAgentResult):
        return raw_output
    if isinstance(raw_output, dict):
        structured = raw_output.get("structured_response")
        if isinstance(structured, DeepAgentResult):
            return structured
        if isinstance(structured, dict):
            return DeepAgentResult.model_validate(structured)
        if "task_id" in raw_output and "status" in raw_output:
            return DeepAgentResult.model_validate(raw_output)
        messages = raw_output.get("messages")
        if isinstance(messages, list) and messages:
            return _from_text(str(messages[-1].content), task)
    return _from_text(str(raw_output), task)


def _from_text(text: str, task: DeepAgentTask) -> DeepAgentResult:
    findings = [
        line.strip("-* ").strip()
        for line in text.splitlines()
        if line.strip().startswith(("-", "*"))
    ]
    return DeepAgentResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="ok" if text.strip() else "needs_more_info",
        answer=text or "DeepAgent no devolvio contenido.",
        findings=findings,
        citations=[],
        uncertainty_notes=[],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=text[:2000] if text else None,
    )


def _report_markdown(result: DeepAgentResult) -> str:
    findings = "\n".join(f"- {finding}" for finding in result.findings) or "- Sin hallazgos."
    citation_lines: list[str] = []
    for citation in result.citations:
        parts: list[str] = []
        if citation.doc_id:
            parts.append(f"doc_id={citation.doc_id}")
        if citation.chunk_id:
            parts.append(f"chunk_id={citation.chunk_id}")
        if citation.title:
            parts.append(f"title={citation.title}")
        if citation.page_start is not None:
            parts.append(f"p{citation.page_start}-{citation.page_end or citation.page_start}")
        if citation.url:
            parts.append(f"url={citation.url}")
        if citation.quote:
            parts.append(f'"{citation.quote[:120]}"')
        citation_lines.append("- " + " | ".join(parts))
    citations = "\n".join(citation_lines) or "- Sin citas."
    uncertainty = (
        "\n".join(f"- {note}" for note in result.uncertainty_notes)
        if result.uncertainty_notes
        else "- Ninguna."
    )
    return (
        "# DeepAgent Report\n\n"
        f"## Answer\n\n{result.answer}\n\n"
        f"## Findings\n\n{findings}\n\n"
        f"## Citations\n\n{citations}\n\n"
        f"## Uncertainty\n\n{uncertainty}\n"
    )


def _write_result_json(workspace: DeepAgentWorkspace, result: DeepAgentResult) -> None:
    (workspace.root_dir / "result.json").write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _audit(task: DeepAgentTask, event: str) -> None:
    try:
        record_audit_event(
            ToolAuditRecord(
                tool_name=f"deepagents.{task.task_type}",
                risk_level=ToolRiskLevel.READ_ONLY,
                args_redacted={
                    "task_id": task.task_id,
                    "thread_id": task.thread_id,
                    "event": event,
                },
                result_summary="ok",
                actor_id=task.user_id,
            )
        )
    except Exception:
        return

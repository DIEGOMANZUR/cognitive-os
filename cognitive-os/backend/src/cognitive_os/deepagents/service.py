from __future__ import annotations

from typing import Any

import structlog

from cognitive_os.deepagents.document_deepagent import run_document_analysis_deepagent
from cognitive_os.deepagents.policies import DeepAgentPolicyViolation
from cognitive_os.deepagents.research_deepagent import run_research_deepagent
from cognitive_os.deepagents.schemas import DeepAgentCitation, DeepAgentResult, DeepAgentTask
from cognitive_os.memory.retrieval import RetrievedContext, retrieve_context

logger = structlog.get_logger(__name__)


def run_deepagent_task(task: DeepAgentTask) -> DeepAgentResult:
    try:
        if task.task_type == "research":
            result = run_research_deepagent(task)
            if result.status == "failed":
                return _research_local_rag_fallback(
                    task,
                    result.raw_summary or "; ".join(result.uncertainty_notes) or result.answer,
                )
            return result
        if task.task_type == "document_analysis":
            return run_document_analysis_deepagent(task)
        return DeepAgentResult(
            task_id=task.task_id,
            thread_id=task.thread_id,
            status="failed",
            answer=f"Unsupported DeepAgent task_type: {task.task_type}",
            findings=[],
            citations=[],
            uncertainty_notes=["Tipo de tarea no soportado."],
            generated_files=[],
            requested_external_actions=[],
            raw_summary=None,
        )
    except DeepAgentPolicyViolation as exc:
        return _blocked(task, str(exc))
    except TimeoutError as exc:
        if task.task_type == "research":
            return _research_local_rag_fallback(task, f"DeepAgent timeout: {exc}")
        return _failed(task, f"DeepAgent timeout: {exc}")
    except Exception as exc:
        logger.exception(
            "deepagent_task_failed",
            task_id=task.task_id,
            task_type=task.task_type,
            error_type=type(exc).__name__,
        )
        if task.task_type == "research":
            return _research_local_rag_fallback(task, f"{type(exc).__name__}: {exc}")
        return _failed(task, f"{type(exc).__name__}: {exc}")


def _research_local_rag_fallback(task: DeepAgentTask, detail: str) -> DeepAgentResult:
    try:
        contexts = _retrieve_research_fallback_contexts(task)
    except Exception as exc:
        return _failed(task, f"{detail}; local_rag_fallback_failed={type(exc).__name__}: {exc}")

    if not contexts:
        return _failed(task, f"{detail}; local_rag_fallback_no_citations")

    citations = [_deepagent_citation_from_context(context) for context in contexts]
    findings = [_finding_from_context(context) for context in contexts]
    cited_lines = "\n".join(
        f"- {citation.title or citation.doc_id or 'local_doc'}:"
        f"{citation.page_start}-{citation.page_end} | {citation.quote or ''}"
        for citation in citations[:5]
    )
    return DeepAgentResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="ok",
        answer=(
            "DeepAgent primary execution failed; Cognitive OS used direct local RAG fallback.\n\n"
            f"{cited_lines}"
        ),
        findings=findings,
        citations=citations,
        uncertainty_notes=[detail, "direct_local_rag_fallback_used"],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=detail,
    )


def _retrieve_research_fallback_contexts(task: DeepAgentTask) -> list[RetrievedContext]:
    if task.allowed_doc_ids:
        by_chunk: dict[str, RetrievedContext] = {}
        for doc_id in task.allowed_doc_ids:
            for context in retrieve_context(task.query, filters={"doc_id": doc_id})[:8]:
                key = str(context.metadata.get("chunk_id") or context.citation)
                by_chunk[key] = context
        return list(by_chunk.values())[:8]
    return retrieve_context(task.query)[:8]


def _deepagent_citation_from_context(context: RetrievedContext) -> DeepAgentCitation:
    metadata = context.metadata
    title = str(metadata.get("title") or context.citation.split(":", 1)[0] or "local_doc")
    return DeepAgentCitation(
        source_type="local_doc",
        title=title,
        doc_id=str(metadata.get("doc_id") or ""),
        chunk_id=str(metadata.get("chunk_id") or ""),
        page_start=int(metadata.get("page_start") or 0),
        page_end=int(metadata.get("page_end") or metadata.get("page_start") or 0),
        quote=context.text[:1000],
        relevance=context.score,
    )


def _finding_from_context(context: RetrievedContext) -> str:
    text = " ".join(context.text.split())
    if len(text) > 220:
        text = f"{text[:217]}..."
    return text


def _blocked(task: DeepAgentTask, detail: str) -> DeepAgentResult:
    return DeepAgentResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="blocked",
        answer="DeepAgent task blocked by Cognitive OS policy.",
        findings=[],
        citations=[],
        uncertainty_notes=[detail],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=detail,
    )


def _failed(task: DeepAgentTask, detail: str) -> DeepAgentResult:
    return DeepAgentResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="failed",
        answer="DeepAgent task failed before producing a reliable result.",
        findings=[],
        citations=[],
        uncertainty_notes=[detail],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=detail,
    )


def run_deepagent_task_from_dict(task_dict: dict[str, Any]) -> DeepAgentResult:
    return run_deepagent_task(DeepAgentTask.model_validate(task_dict))

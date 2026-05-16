from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.tools import StructuredTool
from sqlalchemy import func, select

from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import AuditEvent, Document, DocumentPage, HumanApproval
from cognitive_os.deepagents.document_analysis.schemas import DocumentAnalysisTask, EvidenceCitation
from cognitive_os.memory.retrieval import RetrievedContext, retrieve_context

MAX_PAGES_PER_READ = 20
MAX_ARTIFACT_BYTES = 5 * 1024 * 1024
FilterValue = str | int | bool
Retriever = Callable[[str, dict[str, FilterValue] | None], list[RetrievedContext]]
PageLoader = Callable[[str, int, int], dict[str, Any]]


def build_document_analysis_tools(
    task: DocumentAnalysisTask,
    *,
    workspace_root: Path,
    retriever: Retriever | None = None,
) -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            func=lambda query, doc_ids, limit=12: search_within_allowed_docs(
                query,
                doc_ids,
                limit=limit,
                task=task,
                retriever=retriever,
            ),
            name="search_within_allowed_docs",
            description="Busca solo dentro de doc_ids autorizados y devuelve citas verificables.",
        ),
        StructuredTool.from_function(
            func=lambda doc_id, page_start, page_end: read_allowed_pages(
                doc_id,
                page_start,
                page_end,
                task=task,
            ),
            name="read_allowed_pages",
            description="Lee paginas autorizadas de documentos ya ingeridos.",
        ),
        StructuredTool.from_function(
            func=lambda doc_id: get_document_metadata(doc_id, task=task),
            name="get_document_metadata",
            description="Obtiene metadata redactada de documento autorizado.",
        ),
        StructuredTool.from_function(
            func=lambda case_id, question: query_case_graph_readonly(case_id, question, task=task),
            name="query_case_graph_readonly",
            description="Consulta segura al grafo con consultas predefinidas.",
        ),
        StructuredTool.from_function(
            func=lambda relative_path, content: write_analysis_artifact(
                relative_path,
                content,
                task=task,
                workspace_root=workspace_root,
            ),
            name="write_analysis_artifact",
            description="Escribe artefactos solo en el workspace de analisis.",
        ),
        StructuredTool.from_function(
            func=lambda section_name, content, citations: propose_legal_draft_section(
                section_name,
                content,
                citations,
                task=task,
            ),
            name="propose_legal_draft_section",
            description="Propone una seccion de borrador legal y exige revision humana.",
        ),
    ]


def search_within_allowed_docs(
    query: str,
    doc_ids: list[str],
    limit: int = 12,
    *,
    task: DocumentAnalysisTask,
    retriever: Retriever | None = None,
) -> dict[str, Any]:
    requested = [doc_id for doc_id in doc_ids if doc_id in task.doc_ids]
    if not requested:
        return {"error": "no_authorized_doc_ids", "results": [], "citations": []}
    active_retriever = retriever or _default_retriever
    contexts: list[RetrievedContext] = []
    for doc_id in requested:
        contexts.extend(active_retriever(query, {"doc_id": doc_id}))
    filtered = [
        context
        for context in contexts
        if str(context.metadata.get("doc_id")) in requested
        and _citation_pages_allowed(context.metadata, task)
    ][:limit]
    citations = [_citation_from_context(context) for context in filtered]
    _safe_audit("document_analysis.search", task, {"query_length": len(query)})
    return {
        "results": [
            {"text": context.text, "score": context.score, "metadata": _safe_metadata(context)}
            for context in filtered
        ],
        "citations": [citation.model_dump(mode="json") for citation in citations],
        "warnings": [],
    }


def read_allowed_pages(
    doc_id: str,
    page_start: int,
    page_end: int,
    *,
    task: DocumentAnalysisTask,
    page_loader: PageLoader | None = None,
) -> dict[str, Any]:
    if doc_id not in task.doc_ids:
        return {"error": "doc_not_allowed", "pages": []}
    if page_end < page_start:
        return {"error": "invalid_page_range", "pages": []}
    if page_end - page_start + 1 > MAX_PAGES_PER_READ:
        return {"error": "too_many_pages", "max_pages": MAX_PAGES_PER_READ}
    if not _range_allowed(doc_id, page_start, page_end, task):
        return {"error": "page_range_not_allowed", "pages": []}
    if page_loader is not None:
        return page_loader(doc_id, page_start, page_end)
    _safe_audit("document_analysis.read_pages", task, {"doc_id": doc_id})
    return _run_async(_read_pages_from_db(doc_id, page_start, page_end))


def get_document_metadata(doc_id: str, *, task: DocumentAnalysisTask) -> dict[str, Any]:
    if doc_id not in task.doc_ids:
        return {"error": "doc_not_allowed"}
    return _run_async(_document_metadata_from_db(doc_id))


def query_case_graph_readonly(
    case_id: str, question: str, *, task: DocumentAnalysisTask
) -> dict[str, Any]:
    if task.case_id and case_id != task.case_id:
        return {"error": "case_not_allowed"}
    lowered = question.lower()
    if any(keyword in lowered for keyword in ("match ", "merge ", "delete ", "create ", "cypher")):
        return {"error": "unsupported_graph_query", "reason": "Cypher libre no permitido."}
    if "entity" in lowered or "entidad" in lowered:
        query_type = "entities_in_case"
    elif "event" in lowered or "evento" in lowered:
        query_type = "events_in_case"
    elif "doc" in lowered or "documento" in lowered:
        query_type = "docs_for_entity"
    elif "relation" in lowered or "relacion" in lowered:
        query_type = "relations_for_doc"
    else:
        return {"error": "unsupported_graph_query"}
    return {"query_type": query_type, "results": [], "warnings": ["neo4j_adapter_pending"]}


def write_analysis_artifact(
    relative_path: str,
    content: str,
    *,
    task: DocumentAnalysisTask,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    if len(content.encode()) > MAX_ARTIFACT_BYTES:
        return {"error": "artifact_too_large", "max_bytes": MAX_ARTIFACT_BYTES}
    raw = Path(relative_path)
    if raw.is_absolute() or any(part == ".." for part in raw.parts):
        return {"error": "path_traversal_blocked"}
    root = workspace_root or analysis_workspace(task)
    destination = (root / raw).resolve()
    try:
        destination.relative_to(root.resolve())
    except ValueError:
        return {"error": "path_traversal_blocked"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    _safe_audit("document_analysis.write_artifact", task, {"relative_path": raw.as_posix()})
    return {
        "relative_path": destination.relative_to(root.resolve()).as_posix(),
        "bytes": len(content.encode()),
    }


def propose_legal_draft_section(
    section_name: str,
    content: str,
    citations: list[dict[str, Any]],
    *,
    task: DocumentAnalysisTask,
) -> dict[str, Any]:
    redacted_citations = [
        {
            "doc_id": citation.get("doc_id"),
            "page_start": citation.get("page_start"),
            "page_end": citation.get("page_end"),
        }
        for citation in citations
    ]
    _run_async(_create_human_review(task, section_name, content, redacted_citations))
    return {
        "section_name": section_name,
        "human_review_required": True,
        "status": "pending_review",
    }


def analysis_workspace(task: DocumentAnalysisTask) -> Path:
    root = (
        Path(settings.local_storage_dir) / "workspaces" / task.thread_id / task.task_id / "analysis"
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def _default_retriever(
    query: str,
    filters: dict[str, FilterValue] | None,
) -> list[RetrievedContext]:
    return retrieve_context(query, filters=filters)


def _citation_from_context(context: RetrievedContext) -> EvidenceCitation:
    metadata = context.metadata
    return EvidenceCitation(
        doc_id=str(metadata.get("doc_id")),
        chunk_id=str(metadata.get("chunk_id")) if metadata.get("chunk_id") is not None else None,
        page_start=int(metadata.get("page_start", 0)),
        page_end=int(metadata.get("page_end", 0)),
        source_path=_redact_path(str(metadata.get("source_path", ""))),
        quote=context.text[:500],
        relevance=context.score,
        extraction_method=metadata.get("extraction_method"),
    )


def _safe_metadata(context: RetrievedContext) -> dict[str, Any]:
    metadata = dict(context.metadata)
    if "source_path" in metadata:
        metadata["source_path"] = _redact_path(str(metadata["source_path"]))
    return metadata


def _redact_path(path: str) -> str:
    return Path(path).name if path else path


def _citation_pages_allowed(metadata: dict[str, Any], task: DocumentAnalysisTask) -> bool:
    return _range_allowed(
        str(metadata.get("doc_id")),
        int(metadata.get("page_start", 0)),
        int(metadata.get("page_end", 0)),
        task,
    )


def _range_allowed(doc_id: str, page_start: int, page_end: int, task: DocumentAnalysisTask) -> bool:
    ranges = task.allowed_page_ranges.get(doc_id)
    if not ranges:
        return True
    return any(page_start >= start and page_end <= end for start, end in ranges)


async def _read_pages_from_db(doc_id: str, page_start: int, page_end: int) -> dict[str, Any]:
    async with session_scope() as session:
        document_id = UUID(doc_id)
        document = await session.get(Document, document_id)
        if document is None:
            return {"error": "document_not_found", "pages": []}
        result = await session.execute(
            select(DocumentPage)
            .where(
                DocumentPage.document_id == document_id,
                DocumentPage.page_number >= page_start,
                DocumentPage.page_number <= page_end,
            )
            .order_by(DocumentPage.page_number)
        )
        pages = list(result.scalars().all())
        return {
            "doc_id": doc_id,
            "pages": [
                {
                    "page_number": page.page_number,
                    "text": page.text,
                    "extraction_method": page.extraction_method,
                    "warnings": page.warnings,
                }
                for page in pages
            ],
        }


async def _document_metadata_from_db(doc_id: str) -> dict[str, Any]:
    async with session_scope() as session:
        document_id = UUID(doc_id)
        document = await session.get(Document, document_id)
        if document is None:
            return {"error": "document_not_found"}
        page_count = await session.scalar(
            select(func.count(DocumentPage.id)).where(DocumentPage.document_id == document_id)
        )
        warning_rows = await session.execute(
            select(DocumentPage.warnings).where(DocumentPage.document_id == document_id)
        )
        warnings = [warning for row in warning_rows.scalars().all() for warning in row]
        return {
            "doc_id": doc_id,
            "title": document.title,
            "source_path": _redact_path(document.source_path),
            "page_count": page_count or 0,
            "sha256": document.sha256,
            "extraction_status": document.status,
            "warnings": warnings,
            "created_at": document.created_at.isoformat(),
        }


async def _create_human_review(
    task: DocumentAnalysisTask,
    section_name: str,
    content: str,
    citations: list[dict[str, Any]],
) -> None:
    async with session_scope() as session:
        session.add(
            HumanApproval(
                action="document_analysis_legal_draft",
                requested_action="document_analysis_legal_draft",
                args_redacted={
                    "task_id": task.task_id,
                    "section_name": section_name,
                    "content_preview": content[:500],
                    "citations": citations,
                },
                requested_by=task.user_id,
            )
        )
        session.add(
            AuditEvent(
                actor_id=task.user_id,
                action="document_analysis.propose_legal_draft_section",
                resource_type="document_analysis",
                resource_id=task.task_id,
                metadata_json={"section_name": section_name},
            )
        )


async def _audit(action: str, task: DocumentAnalysisTask, metadata: dict[str, Any]) -> None:
    async with session_scope() as session:
        session.add(
            AuditEvent(
                actor_id=task.user_id,
                action=action,
                resource_type="document_analysis",
                resource_id=task.task_id,
                metadata_json=metadata,
            )
        )


def _safe_audit(action: str, task: DocumentAnalysisTask, metadata: dict[str, Any]) -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            _run_async(_audit(action, task, metadata))
        except Exception:
            return


def _run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    msg = "Document analysis sync tool cannot perform database IO inside an active event loop."
    raise RuntimeError(msg)

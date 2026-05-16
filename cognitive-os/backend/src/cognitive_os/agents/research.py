from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Sequence
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select

from cognitive_os.agents.state import RetrievalCitation
from cognitive_os.agents.web_search import (
    TavilyWebSearchClient,
    WebSearchClient,
    WebSearchResult,
    build_default_web_search_client,
)
from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import Document, DocumentPage
from cognitive_os.memory.retrieval import RetrievedContext, retrieve_context

__all__ = [
    "LocalDocHit",
    "PageCitation",
    "ReadOnlyResearchTools",
    "ResearchAgent",
    "ResearchReport",
    "TavilyWebSearchClient",
    "WebSearchClient",
    "WebSearchResult",
]


class LocalDocHit(BaseModel):
    doc_id: str
    page_start: int
    page_end: int
    chunk_id: str
    text: str
    source_path: str
    score: float | None = None

    def to_citation(self) -> RetrievalCitation:
        return RetrievalCitation(
            source_path=self.source_path,
            page_start=self.page_start,
            page_end=self.page_end,
            quote=self.text,
            doc_id=self.doc_id,
            chunk_id=self.chunk_id,
        )


class PageCitation(BaseModel):
    doc_id: str
    page: int
    text: str | None
    source_path: str
    warnings: list[str] = Field(default_factory=list)


class ResearchReport(BaseModel):
    answer: str
    bullet_findings: list[str] = Field(default_factory=list)
    citations: list[RetrievalCitation] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    used_sources: list[str] = Field(default_factory=list)


LocalSearch = Callable[[str], list[RetrievedContext]]


class ReadOnlyResearchTools:
    def __init__(
        self,
        *,
        local_search: LocalSearch = retrieve_context,
        web_client: WebSearchClient | None = None,
        app_settings: Settings = settings,
    ) -> None:
        self._local_search = local_search
        self._web_client = web_client or build_default_web_search_client(app_settings)
        self._settings = app_settings

    def search_local_docs(self, query: str) -> list[LocalDocHit]:
        return [_context_to_hit(context) for context in self._local_search(query)]

    def search_web(self, query: str) -> list[WebSearchResult]:
        if not self._settings.web_search_enabled:
            return []
        return self._web_client.search(query)

    def read_citation(self, doc_id: str, page: int) -> PageCitation | None:
        return _run_async(_read_citation(doc_id, page))


class ResearchAgent:
    def __init__(self, *, tools: ReadOnlyResearchTools | None = None) -> None:
        self._tools = tools or ReadOnlyResearchTools()

    def run(
        self,
        query: str,
        *,
        retrieved_context: Sequence[RetrievalCitation] | None = None,
    ) -> ResearchReport:
        local_hits = self._local_hits_from_context(retrieved_context)
        if not local_hits:
            local_hits = self._tools.search_local_docs(query)
        web_hits = self._tools.search_web(query)

        citations = [hit.to_citation() for hit in local_hits]
        citations.extend(hit.to_citation() for hit in web_hits)
        used_sources = _used_sources(local_hits=local_hits, web_hits=web_hits)

        if not citations:
            return ResearchReport(
                answer=(
                    "No hay evidencia suficiente en las fuentes disponibles para responder con "
                    "certeza. No invento una conclusión sin respaldo documental."
                ),
                uncertainty_notes=[
                    "No se encontraron documentos locales ni fuentes web habilitadas "
                    "con evidencia.",
                    "Se requiere incorporar documentos relevantes o habilitar búsqueda web "
                    "con clave válida.",
                ],
                used_sources=[],
            )

        bullet_findings = _build_findings(local_hits=local_hits, web_hits=web_hits)
        answer = _build_answer(query=query, bullet_findings=bullet_findings)
        uncertainty_notes = _build_uncertainty_notes(local_hits=local_hits, web_hits=web_hits)
        return ResearchReport(
            answer=answer,
            bullet_findings=bullet_findings,
            citations=citations,
            uncertainty_notes=uncertainty_notes,
            used_sources=used_sources,
        )

    @staticmethod
    def _local_hits_from_context(
        retrieved_context: Sequence[RetrievalCitation] | None,
    ) -> list[LocalDocHit]:
        hits: list[LocalDocHit] = []
        for citation in retrieved_context or []:
            if not citation.doc_id or not citation.chunk_id or not citation.quote:
                continue
            hits.append(
                LocalDocHit(
                    doc_id=citation.doc_id,
                    page_start=citation.page_start,
                    page_end=citation.page_end,
                    chunk_id=citation.chunk_id,
                    text=citation.quote,
                    source_path=citation.source_path,
                )
            )
        return hits


async def _read_citation(doc_id: str, page: int) -> PageCitation | None:
    document_id = UUID(doc_id)
    async with session_scope() as session:
        result = await session.execute(
            select(DocumentPage, Document.source_path)
            .join(Document, Document.id == DocumentPage.document_id)
            .where(DocumentPage.document_id == document_id, DocumentPage.page_number == page)
        )
        row = result.one_or_none()
        if row is None:
            return None
        page_row, source_path = row
        return PageCitation(
            doc_id=doc_id,
            page=page_row.page_number,
            text=page_row.text,
            source_path=source_path,
            warnings=list(page_row.warnings),
        )


def _run_async[T](awaitable: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    msg = "read_citation cannot run synchronously inside an active event loop."
    raise RuntimeError(msg)


def _context_to_hit(context: RetrievedContext) -> LocalDocHit:
    metadata = context.metadata
    return LocalDocHit(
        doc_id=str(metadata.get("doc_id", "")),
        page_start=int(metadata.get("page_start", 1)),
        page_end=int(metadata.get("page_end", metadata.get("page_start", 1))),
        chunk_id=str(metadata.get("chunk_id", "")),
        text=context.text,
        source_path=str(metadata.get("source_path", context.citation.split(":", 1)[0])),
        score=context.score,
    )


def _build_answer(*, query: str, bullet_findings: Sequence[str]) -> str:
    findings = "\n".join(f"- {finding}" for finding in bullet_findings)
    return (
        "Respuesta de investigación basada solo en fuentes disponibles.\n\n"
        f"Pregunta: {query}\n\n"
        "Hechos e inferencias:\n"
        f"{findings}"
    )


def _build_findings(
    *,
    local_hits: Sequence[LocalDocHit],
    web_hits: Sequence[WebSearchResult],
) -> list[str]:
    findings: list[str] = []
    for hit in local_hits[:5]:
        snippet = _compact(hit.text)
        findings.append(
            "Hecho documentado: "
            f"{snippet} (doc_id={hit.doc_id}, pagina={hit.page_start}, chunk_id={hit.chunk_id})."
        )
    for web_hit in web_hits[:3]:
        snippet = _compact(web_hit.snippet)
        findings.append(f"Hecho de fuente web: {snippet} ({web_hit.title}, {web_hit.url}).")
    if len(local_hits) + len(web_hits) > len(findings):
        findings.append(
            "Inferencia: existen fuentes adicionales recuperadas, pero se priorizaron "
            "las más relevantes."
        )
    return findings


def _build_uncertainty_notes(
    *,
    local_hits: Sequence[LocalDocHit],
    web_hits: Sequence[WebSearchResult],
) -> list[str]:
    notes: list[str] = []
    if not local_hits:
        notes.append("No se encontraron citas en documentos locales para esta pregunta.")
    if not web_hits:
        notes.append("No se usaron fuentes web; pueden faltar antecedentes externos recientes.")
    return notes


def _used_sources(
    *,
    local_hits: Sequence[LocalDocHit],
    web_hits: Sequence[WebSearchResult],
) -> list[str]:
    sources = {f"local:{hit.doc_id}:{hit.chunk_id}" for hit in local_hits}
    sources.update(f"web:{hit.url}" for hit in web_hits)
    return sorted(sources)


def _compact(text: str, *, max_chars: int = 240) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 1].rstrip()}..."

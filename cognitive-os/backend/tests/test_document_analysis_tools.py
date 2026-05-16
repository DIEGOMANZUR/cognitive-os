from __future__ import annotations

from pathlib import Path
from typing import Any

from cognitive_os.deepagents.document_analysis.schemas import DocumentAnalysisTask
from cognitive_os.deepagents.document_analysis.tools import (
    read_allowed_pages,
    search_within_allowed_docs,
    write_analysis_artifact,
)
from cognitive_os.memory.retrieval import RetrievedContext


def _task(**overrides: object) -> DocumentAnalysisTask:
    data = {
        "task_id": "task-1",
        "thread_id": "thread-1",
        "user_id": "user-1",
        "case_id": None,
        "doc_ids": ["doc-a", "doc-b"],
        "query": "Analiza los hechos principales.",
        "modes": ["evidence_matrix"],
        "allowed_page_ranges": {"doc-a": [(1, 5)], "doc-b": [(1, 5)]},
    }
    data.update(overrides)
    return DocumentAnalysisTask.model_validate(data)


def _context(doc_id: str, page: int, text: str) -> RetrievedContext:
    return RetrievedContext(
        text=text,
        citation=f"{doc_id}:{page}-{page}",
        score=0.9,
        metadata={
            "doc_id": doc_id,
            "chunk_id": f"{doc_id}-chunk",
            "source_path": f"/sensitive/{doc_id}.pdf",
            "page_start": page,
            "page_end": page,
            "extraction_method": "native_pdf",
        },
    )


def test_search_within_allowed_docs_filters_doc_ids() -> None:
    task = _task()

    def retriever(query: str, filters: dict[str, str] | None) -> list[RetrievedContext]:
        del query, filters
        return [
            _context("doc-a", 1, "El hecho ocurrió el 10 de noviembre de 2023."),
            _context("doc-c", 1, "Documento no autorizado."),
        ]

    result = search_within_allowed_docs("hecho", ["doc-a", "doc-c"], task=task, retriever=retriever)

    assert len(result["citations"]) == 1
    assert result["citations"][0]["doc_id"] == "doc-a"
    assert result["results"][0]["metadata"]["source_path"] == "doc-a.pdf"


def test_read_allowed_pages_maximum_twenty_pages() -> None:
    result = read_allowed_pages("doc-a", 1, 21, task=_task())

    assert result["error"] == "too_many_pages"


def test_read_allowed_pages_blocks_unallowed_doc() -> None:
    result = read_allowed_pages("doc-c", 1, 1, task=_task())

    assert result["error"] == "doc_not_allowed"


def test_read_allowed_pages_uses_loader_for_valid_request() -> None:
    def loader(doc_id: str, page_start: int, page_end: int) -> dict[str, Any]:
        return {"doc_id": doc_id, "pages": [{"page_number": page_start, "page_end": page_end}]}

    result = read_allowed_pages("doc-a", 1, 1, task=_task(), page_loader=loader)

    assert result["pages"][0]["page_number"] == 1


def test_write_analysis_artifact_blocks_path_traversal(tmp_path: Path) -> None:
    result = write_analysis_artifact("../escape.md", "bad", task=_task(), workspace_root=tmp_path)

    assert result["error"] == "path_traversal_blocked"


def test_write_analysis_artifact_allows_relative_path(tmp_path: Path) -> None:
    result = write_analysis_artifact("report.md", "ok", task=_task(), workspace_root=tmp_path)

    assert result["relative_path"] == "report.md"
    assert (tmp_path / "report.md").read_text(encoding="utf-8") == "ok"

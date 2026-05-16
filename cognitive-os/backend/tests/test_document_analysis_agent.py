from __future__ import annotations

from typing import Any

import pytest

import cognitive_os.deepagents.document_analysis.agent as agent_module
from cognitive_os.deepagents.document_analysis.agent import DocumentAnalysisDeepAgent
from cognitive_os.deepagents.document_analysis.schemas import (
    DocumentAnalysisResult,
    DocumentAnalysisTask,
    EvidenceCitation,
)
from cognitive_os.memory.retrieval import RetrievedContext


class FakeMemoryService:
    async def get_startup_memory(self, *args: object, **kwargs: object) -> str:
        del args, kwargs
        return "Memoria redactada."


def _task(*, modes: list[str] | None = None) -> DocumentAnalysisTask:
    return DocumentAnalysisTask(
        task_id="task-1",
        thread_id="thread-1",
        user_id="user-1",
        case_id=None,
        doc_ids=["doc-a", "doc-b"],
        query="Analiza el hecho principal.",
        modes=modes or ["evidence_matrix"],
    )


def _result() -> DocumentAnalysisResult:
    citation = EvidenceCitation(
        doc_id="doc-a",
        chunk_id="chunk-a",
        page_start=1,
        page_end=1,
        quote="El hecho ocurrió el 10 de noviembre de 2023.",
    )
    return DocumentAnalysisResult(
        task_id="task-1",
        thread_id="thread-1",
        status="ok",
        executive_summary="Resumen mock.",
        evidence_matrix=[],
        timeline=[],
        contradictions=[],
        missing_evidence=[],
        draft_sections={},
        citations=[citation],
        uncertainty_notes=["Sin incertidumbres adicionales."],
        generated_files=[],
        human_review_required=False,
        warnings=[],
        raw_agent_summary=None,
    )


def _retriever(query: str, filters: dict[str, str] | None) -> list[RetrievedContext]:
    del query, filters
    return [
        RetrievedContext(
            text="El hecho ocurrió el 10 de noviembre de 2023.",
            citation="doc-a:1-1",
            score=0.9,
            metadata={
                "doc_id": "doc-a",
                "chunk_id": "chunk-a",
                "source_path": "/private/doc-a.pdf",
                "page_start": 1,
                "page_end": 1,
            },
        ),
        RetrievedContext(
            text="El hecho ocurrió el 11 de noviembre de 2023.",
            citation="doc-b:2-2",
            score=0.8,
            metadata={
                "doc_id": "doc-b",
                "chunk_id": "chunk-b",
                "source_path": "/private/doc-b.pdf",
                "page_start": 2,
                "page_end": 2,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_deepagent_mock_returns_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    monkeypatch.setattr(agent_module, "DeepAgentMemoryService", FakeMemoryService)
    monkeypatch.setattr(agent_module, "analysis_workspace", lambda task: tmp_path)

    class FakeAgent:
        def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
            assert "messages" in payload
            return {"structured_response": _result()}

    def fake_factory(*args: object, **kwargs: object) -> FakeAgent:
        del args, kwargs
        return FakeAgent()

    result = await DocumentAnalysisDeepAgent(
        retriever=_retriever,
        agent_factory=fake_factory,
    ).run(_task())

    assert result.executive_summary == "Resumen mock."
    assert "result.json" in result.generated_files
    assert "report.md" in result.generated_files


@pytest.mark.asyncio
async def test_deepagent_failure_uses_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    monkeypatch.setattr(agent_module, "analysis_workspace", lambda task: tmp_path)

    def failing_factory(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("boom")

    result = await DocumentAnalysisDeepAgent(
        retriever=_retriever,
        agent_factory=failing_factory,
    ).run(_task(modes=["evidence_matrix", "timeline", "contradictions"]))

    assert result.status == "partial"
    assert result.evidence_matrix
    assert result.timeline
    assert result.contradictions
    assert any("deepagent_failed_fallback_used" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_legal_draft_support_requires_human_review(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    monkeypatch.setattr(agent_module, "analysis_workspace", lambda task: tmp_path)

    def failing_factory(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("boom")

    result = await DocumentAnalysisDeepAgent(
        retriever=_retriever,
        agent_factory=failing_factory,
    ).run(_task(modes=["legal_draft_support"]))

    assert result.human_review_required is True
    assert result.draft_sections

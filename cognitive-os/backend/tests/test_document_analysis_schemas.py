from __future__ import annotations

from datetime import date

import pytest

from cognitive_os.deepagents.document_analysis.schemas import (
    DocumentAnalysisResult,
    DocumentAnalysisTask,
    EvidenceCitation,
    EvidenceMatrixRow,
    TimelineEvent,
)


def _task(**overrides: object) -> DocumentAnalysisTask:
    data = {
        "task_id": "task-1",
        "thread_id": "thread-1",
        "user_id": "user-1",
        "case_id": None,
        "doc_ids": ["doc-a"],
        "query": "Analiza los hechos principales.",
        "modes": ["evidence_matrix"],
    }
    data.update(overrides)
    return DocumentAnalysisTask.model_validate(data)


def test_validates_task() -> None:
    task = _task(allowed_page_ranges={"doc-a": [(1, 3)]})

    assert task.doc_ids == ["doc-a"]
    assert task.allowed_page_ranges["doc-a"] == [(1, 3)]


def test_rejects_invalid_page_range() -> None:
    with pytest.raises(ValueError, match="positive and ordered"):
        _task(allowed_page_ranges={"doc-a": [(3, 1)]})


def test_rejects_page_range_for_unauthorized_doc() -> None:
    with pytest.raises(ValueError, match="unauthorized doc_id"):
        _task(allowed_page_ranges={"doc-b": [(1, 2)]})


def test_validates_result() -> None:
    citation = EvidenceCitation(
        doc_id="doc-a",
        chunk_id="chunk-a",
        page_start=1,
        page_end=1,
        quote="El hecho ocurrió el 10 de noviembre de 2023.",
    )
    result = DocumentAnalysisResult(
        task_id="task-1",
        thread_id="thread-1",
        status="ok",
        executive_summary="Resumen.",
        evidence_matrix=[
            EvidenceMatrixRow(
                claim_id="claim-1",
                claim="El hecho ocurrió el 10 de noviembre de 2023.",
                claim_type="fact",
                supporting_evidence=[citation],
                strength="strong",
            )
        ],
        timeline=[
            TimelineEvent(
                event_id="event-1",
                date_text="2023-11-10",
                normalized_date=date(2023, 11, 10),
                date_certainty="exact",
                event_summary="Hecho principal.",
                citations=[citation],
            )
        ],
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

    assert result.citations[0].chunk_id == "chunk-a"

from __future__ import annotations

from cognitive_os.deepagents.document_analysis.evaluators import (
    calculate_quality_score,
    validate_claim_support,
    validate_contradictions,
    validate_timeline,
)
from cognitive_os.deepagents.document_analysis.schemas import (
    ContradictionFinding,
    DocumentAnalysisResult,
    DocumentAnalysisTask,
    EvidenceCitation,
    EvidenceMatrixRow,
    TimelineEvent,
)


def _task() -> DocumentAnalysisTask:
    return DocumentAnalysisTask(
        task_id="task-1",
        thread_id="thread-1",
        doc_ids=["doc-a", "doc-b"],
        query="hecho",
        modes=["evidence_matrix"],
    )


def _citation(doc_id: str = "doc-a") -> EvidenceCitation:
    return EvidenceCitation(
        doc_id=doc_id,
        chunk_id="chunk-1",
        page_start=1,
        page_end=1,
        quote="El hecho ocurrió el 10 de noviembre de 2023.",
    )


def _result(**overrides: object) -> DocumentAnalysisResult:
    data = {
        "task_id": "task-1",
        "thread_id": "thread-1",
        "status": "ok",
        "executive_summary": "Resumen.",
        "evidence_matrix": [],
        "timeline": [],
        "contradictions": [],
        "missing_evidence": [],
        "draft_sections": {},
        "citations": [],
        "uncertainty_notes": ["Incertidumbre declarada."],
        "generated_files": [],
        "human_review_required": False,
        "warnings": [],
        "raw_agent_summary": None,
    }
    data.update(overrides)
    return DocumentAnalysisResult.model_validate(data)


def test_claim_factual_without_citation_becomes_unsupported() -> None:
    result = _result(
        evidence_matrix=[
            EvidenceMatrixRow(
                claim_id="claim-1",
                claim="Hecho sin soporte.",
                claim_type="fact",
                supporting_evidence=[],
                strength="weak",
            )
        ]
    )

    warnings = validate_claim_support(result)

    assert "unsupported_fact:claim-1" in warnings
    assert result.evidence_matrix[0].strength == "unsupported"
    assert result.evidence_matrix[0].needs_human_review is True


def test_contradiction_without_two_citations_fails() -> None:
    contradiction = ContradictionFinding.model_construct(
        contradiction_id="contradiction-1",
        topic="Fecha",
        statement_a="10",
        statement_b="11",
        citation_a=_citation(),
        citation_b=None,
        contradiction_type="date",
        severity="high",
        explanation="Falta una cita.",
        needs_human_review=False,
    )
    result = _result(contradictions=[contradiction])

    warnings = validate_contradictions(result)

    assert warnings == ["contradiction_missing_dual_citation:contradiction-1"]


def test_timeline_without_citation_gets_warning() -> None:
    result = _result(
        timeline=[
            TimelineEvent(
                event_id="event-1",
                date_text="2023-11-10",
                normalized_date=None,
                date_certainty="exact",
                event_summary="Evento sin cita.",
                citations=[],
            )
        ]
    )

    warnings = validate_timeline(result)

    assert "timeline_event_missing_citation:event-1" in warnings
    assert "timeline_exact_without_normalized_date:event-1" in warnings


def test_quality_score_drops_with_unsupported_claims() -> None:
    result = _result(
        evidence_matrix=[
            EvidenceMatrixRow(
                claim_id="claim-1",
                claim="Hecho sin soporte.",
                claim_type="fact",
                supporting_evidence=[],
                strength="unsupported",
            )
        ],
        citations=[_citation()],
    )

    assert calculate_quality_score(result, _task()) < 100

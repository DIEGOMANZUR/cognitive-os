from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from cognitive_os.deepagents.document_analysis.exporters import DocumentAnalysisExporter
from cognitive_os.deepagents.document_analysis.schemas import (
    ContradictionFinding,
    DocumentAnalysisResult,
    EvidenceCitation,
    EvidenceMatrixRow,
    TimelineEvent,
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
        executive_summary="Resumen ejecutivo.",
        evidence_matrix=[
            EvidenceMatrixRow(
                claim_id="claim-1",
                claim="El hecho ocurrió el 10 de noviembre de 2023.",
                claim_type="fact",
                supporting_evidence=[citation],
                strength="strong",
            )
        ],
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


def _result_with_timeline_and_contradiction() -> DocumentAnalysisResult:
    citation_a = EvidenceCitation(
        doc_id="doc-a",
        chunk_id="chunk-1",
        page_start=3,
        page_end=3,
        quote="El evento ocurrió el 10 de noviembre de 2023.",
    )
    citation_b = EvidenceCitation(
        doc_id="doc-b",
        chunk_id="chunk-9",
        page_start=8,
        page_end=8,
        quote="El evento ocurrió el 11 de noviembre de 2023.",
    )
    base = _result()
    base.timeline = [
        TimelineEvent(
            event_id="event-1",
            date_text="10 de noviembre de 2023",
            normalized_date=date(2023, 11, 10),
            date_certainty="exact",
            event_summary="Hecho central de la causa.",
            involved_entities=["persona-a"],
            citations=[citation_a],
            notes="",
        )
    ]
    base.contradictions = [
        ContradictionFinding(
            contradiction_id="contradiction-1",
            topic="Fecha del hecho",
            statement_a="El evento ocurrió el 10 de noviembre.",
            statement_b="El evento ocurrió el 11 de noviembre.",
            citation_a=citation_a,
            citation_b=citation_b,
            contradiction_type="date",
            severity="high",
            explanation="Las citas indican fechas distintas.",
            needs_human_review=True,
        )
    ]
    return base


def test_export_json_valid(tmp_path: Path) -> None:
    path = DocumentAnalysisExporter().export_json(_result(), tmp_path)

    loaded = DocumentAnalysisResult.model_validate_json(path.read_text(encoding="utf-8"))
    assert loaded.task_id == "task-1"


def test_export_markdown_contains_sections(tmp_path: Path) -> None:
    path = DocumentAnalysisExporter().export_markdown(_result(), tmp_path)
    content = path.read_text(encoding="utf-8")

    assert "## Resumen ejecutivo" in content
    assert "## Matriz hecho/evidencia/cita" in content
    assert "## Contradicciones" in content


def test_docx_export_optional(tmp_path: Path) -> None:
    path = DocumentAnalysisExporter().export_docx(_result(), tmp_path)

    assert path is None or path.exists()


def test_export_csvs_emits_three_files_with_expected_headers(tmp_path: Path) -> None:
    paths = DocumentAnalysisExporter().export_csvs(
        _result_with_timeline_and_contradiction(), tmp_path
    )

    names = sorted(path.name for path in paths)
    assert names == ["contradictions.csv", "evidence_matrix.csv", "timeline.csv"]
    matrix_rows = list(csv.reader((tmp_path / "evidence_matrix.csv").open()))
    assert matrix_rows[0][0] == "claim_id"
    assert matrix_rows[1][0] == "claim-1"
    timeline_rows = list(csv.reader((tmp_path / "timeline.csv").open()))
    assert timeline_rows[0] == [
        "event_id",
        "date_text",
        "normalized_date",
        "date_certainty",
        "event_summary",
        "involved_entities",
        "citations",
        "contradictions",
        "notes",
    ]
    assert timeline_rows[1][2] == "2023-11-10"
    contradiction_rows = list(csv.reader((tmp_path / "contradictions.csv").open()))
    assert contradiction_rows[0][0] == "contradiction_id"
    assert contradiction_rows[1][3] == "high"

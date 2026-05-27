"""V2-EVAL-001 regression: GET /document-analysis/{id} must mirror persisted result.

Prompt 5 V2.0 sweep observed live:
    GET /document-analysis/v2_04_full_1779913647 -> {"evidence_matrix": absent,
                                                    "timeline": absent,
                                                    "contradictions": absent,
                                                    "available_artifacts": null}
    GET /document-analysis/.../download/json -> {"evidence_matrix": [2 claims],
                                                "timeline": [2 events],
                                                "contradictions": [1 finding]}

That ``falso vacío'' would let the operator close a legal review thinking the
agent found nothing, while the downloadable report actually contains the
findings. The fix expands the endpoint response so it reflects the persisted
row exactly.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

import cognitive_os.api.app as api_app
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.deepagents.document_analysis.schemas import (
    ContradictionFinding,
    DocumentAnalysisResult,
    EvidenceCitation,
    EvidenceMatrixRow,
    MissingEvidenceFinding,
    TimelineEvent,
)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


def _seed_result_with_contradiction() -> DocumentAnalysisResult:
    """Build a `DocumentAnalysisResult` that resembles the heuristic fallback
    output observed in production: 2 evidence rows, 2 timeline events,
    1 contradiction detected. This is the shape that triggered V2-EVAL-001."""
    citation = EvidenceCitation(
        doc_id="11111111-1111-1111-1111-111111111111",
        chunk_id="11111111-1111-1111-1111-111111111111:p1:c0",
        page_start=1,
        page_end=1,
        source_path="contract.pdf",
        quote=(
            "Clausula 1: La obligación principal del proveedor es entregar reportes trimestrales."
        ),
    )
    citation_b = EvidenceCitation(
        doc_id="11111111-1111-1111-1111-111111111111",
        chunk_id="11111111-1111-1111-1111-111111111111:p2:c1",
        page_start=2,
        page_end=2,
        source_path="contract.pdf",
        quote="Anexo A: Fecha de pago de la primera cuota: 1 de abril de 2026.",
    )
    return DocumentAnalysisResult(
        task_id="v2_eval_001_consistency_task",
        thread_id="v2_eval_001_thread",
        status="partial",
        executive_summary="Fixture seed: 2 claims, 2 events, 1 contradiction.",
        evidence_matrix=[
            EvidenceMatrixRow(
                claim_id="claim-1",
                claim="Proveedor debe entregar reportes trimestrales",
                claim_type="fact",
                supporting_evidence=[citation],
                strength="moderate",
            ),
            EvidenceMatrixRow(
                claim_id="claim-2",
                claim="Fecha de pago 1 de abril de 2026",
                claim_type="fact",
                supporting_evidence=[citation_b],
                strength="moderate",
            ),
        ],
        timeline=[
            TimelineEvent(
                event_id="event-1",
                date_text="15 de marzo de 2026",
                normalized_date="2026-03-15",
                date_certainty="exact",
                event_summary="Firma del contrato.",
                citations=[citation],
            ),
            TimelineEvent(
                event_id="event-2",
                date_text="1 de abril de 2026",
                normalized_date="2026-04-01",
                date_certainty="exact",
                event_summary="Primera cuota.",
                citations=[citation_b],
            ),
        ],
        contradictions=[
            ContradictionFinding(
                contradiction_id="contradiction-1",
                topic="Fecha del hecho",
                statement_a="El hecho ocurrió el 15 de marzo de 2026.",
                statement_b="El hecho ocurrió el 1 de abril de 2026.",
                citation_a=citation,
                citation_b=citation_b,
                contradiction_type="date",
                severity="medium",
                explanation="Las citas indican fechas distintas para el mismo hecho consultado.",
            )
        ],
        missing_evidence=[
            MissingEvidenceFinding(
                finding_id="missing-1",
                expected_evidence="Cláusula de rescisión",
                why_it_matters=(
                    "Sin cláusula de rescisión no se puede asesorar sobre salida temprana."
                ),
                status="not_found",
            )
        ],
        citations=[citation, citation_b],
        generated_files=[
            "report.md",
            "result.json",
            "report.docx",
            "evidence_matrix.csv",
            "timeline.csv",
            "contradictions.csv",
        ],
        human_review_required=True,
        warnings=["deepagent_failed_fallback_used:BadRequestError"],
    )


@pytest.mark.asyncio
async def test_get_endpoint_exposes_evidence_matrix_timeline_and_contradictions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V2-EVAL-001: the `GET /document-analysis/{task_id}` body MUST carry
    the same evidence_matrix / timeline / contradictions counts as the
    persisted `result.json` artifact. Otherwise an operator scanning the
    response sees a `falso vacío' while the report has findings.

    Before the fix the response only had {status, generated_files,
    human_review_required, warnings}. Asking `.evidence_matrix | length`
    on that yielded 0 regardless of what the heuristic fallback wrote to
    disk."""
    seed = _seed_result_with_contradiction()

    async def fake_get(_self: object, task_id: str) -> DocumentAnalysisResult | None:
        assert task_id == seed.task_id
        return seed

    monkeypatch.setattr(api_app.DocumentAnalysisService, "get_analysis_result", fake_get)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/document-analysis/{seed.task_id}",
            headers=_headers(),
        )

    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()

    # Core metadata that the previous response already exposed.
    assert body["task_id"] == seed.task_id
    assert body["status"] == "partial"
    assert body["human_review_required"] is True
    assert "deepagent_failed_fallback_used:BadRequestError" in body["warnings"]

    # Regression: the body now reflects the persisted result.
    assert len(body["evidence_matrix"]) == 2
    assert len(body["timeline"]) == 2
    assert len(body["contradictions"]) == 1
    assert len(body["missing_evidence"]) == 1

    # available_artifacts must list the generated files so the frontend can
    # show direct download links instead of always probing every endpoint.
    assert sorted(body["available_artifacts"]) == sorted(
        [
            "evidence_matrix.csv",
            "report.docx",
            "report.md",
            "result.json",
            "timeline.csv",
            "contradictions.csv",
        ]
    )

    # Same exposure via the original `generated_files` field for clients
    # that already consume it.
    assert body["generated_files"] == seed.generated_files

    # The thread_id is now visible too — useful for the cockpit to deep-link
    # back into the chat that produced this analysis.
    assert body["thread_id"] == seed.thread_id

    # Citation/quote content is forwarded so the operator can pre-screen
    # findings before opening the .docx/.csv.
    first_quote = body["evidence_matrix"][0]["supporting_evidence"][0]["quote"]
    assert "Clausula 1" in first_quote or "reportes trimestrales" in first_quote


@pytest.mark.asyncio
async def test_get_endpoint_still_404s_when_task_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The expanded response must NOT regress the 404 contract for unknown
    task_ids."""

    async def fake_get(_self: object, task_id: str) -> DocumentAnalysisResult | None:
        del task_id
        return None

    monkeypatch.setattr(api_app.DocumentAnalysisService, "get_analysis_result", fake_get)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/document-analysis/does-not-exist",
            headers=_headers(),
        )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Document analysis result not found"

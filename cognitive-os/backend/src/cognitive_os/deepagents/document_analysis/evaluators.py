from __future__ import annotations

from datetime import date

from cognitive_os.deepagents.document_analysis.schemas import (
    DocumentAnalysisResult,
    DocumentAnalysisTask,
)


def validate_citation_integrity(
    result: DocumentAnalysisResult,
    task: DocumentAnalysisTask,
) -> list[str]:
    warnings: list[str] = []
    for citation in result.citations:
        if citation.doc_id not in task.doc_ids:
            warnings.append(f"citation_doc_out_of_scope:{citation.doc_id}")
        if citation.page_start < 1 or citation.page_end < citation.page_start:
            warnings.append(f"citation_page_invalid:{citation.doc_id}")
    return warnings


def validate_claim_support(result: DocumentAnalysisResult) -> list[str]:
    warnings: list[str] = []
    for row in result.evidence_matrix:
        if row.claim_type == "fact" and not row.supporting_evidence:
            row.strength = "unsupported"
            row.needs_human_review = True
            warnings.append(f"unsupported_fact:{row.claim_id}")
    return warnings


def validate_contradictions(result: DocumentAnalysisResult) -> list[str]:
    warnings: list[str] = []
    for contradiction in result.contradictions:
        if not contradiction.citation_a or not contradiction.citation_b:
            contradiction.needs_human_review = True
            warnings.append(f"contradiction_missing_dual_citation:{contradiction.contradiction_id}")
    return warnings


def validate_timeline(result: DocumentAnalysisResult) -> list[str]:
    warnings: list[str] = []
    for event in result.timeline:
        if not event.citations and event.date_certainty != "unknown":
            event.notes = _append_note(event.notes, "Timeline event lacks citation.")
            warnings.append(f"timeline_event_missing_citation:{event.event_id}")
        if event.normalized_date is None and event.date_certainty == "exact":
            event.date_certainty = "unknown"
            warnings.append(f"timeline_exact_without_normalized_date:{event.event_id}")
    return warnings


def calculate_quality_score(result: DocumentAnalysisResult, task: DocumentAnalysisTask) -> int:
    score = 100
    score -= 8 * len(validate_citation_integrity(result, task))
    score -= 10 * len([row for row in result.evidence_matrix if row.strength == "unsupported"])
    score -= 8 * len(validate_contradictions(result))
    score -= 5 * len(validate_timeline(result))
    if not result.uncertainty_notes:
        score -= 5
    return max(0, min(100, score))


def apply_quality_evaluation(
    result: DocumentAnalysisResult,
    task: DocumentAnalysisTask,
) -> DocumentAnalysisResult:
    warnings: list[str] = []
    warnings.extend(validate_citation_integrity(result, task))
    warnings.extend(validate_claim_support(result))
    warnings.extend(validate_contradictions(result))
    warnings.extend(validate_timeline(result))
    score = calculate_quality_score(result, task)
    result.warnings.extend(warnings)
    result.warnings.append(f"quality_score:{score}")
    if score < 85:
        result.status = "partial" if result.status == "ok" else result.status
        result.human_review_required = True
    if result.draft_sections and task.require_human_review_for_drafts:
        result.human_review_required = True
        if result.status == "ok":
            result.status = "needs_human_review"
    # V2-EVAL-202 (P3): reconcile top-level flag with item-level signals.
    # A high-severity contradiction or any contradiction explicitly flagged
    # needs_human_review must propagate to the top-level boolean so the
    # frontend approval banner is shown. Previously the top-level flag only
    # flipped on quality-score or draft conditions, which could hide
    # individually severe items in artifacts that otherwise passed the score.
    has_high_severity_contradiction = any(
        getattr(c, "severity", "").lower() == "high" for c in result.contradictions
    )
    has_item_needs_review = any(
        getattr(c, "needs_human_review", False) for c in result.contradictions
    )
    if has_high_severity_contradiction or has_item_needs_review:
        result.human_review_required = True
    return result


def normalize_event_date(date_text: str) -> date | None:
    try:
        return date.fromisoformat(date_text)
    except ValueError:
        return None


def _append_note(existing: str, note: str) -> str:
    return note if not existing else f"{existing} {note}"

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

DocumentAnalysisMode = Literal[
    "evidence_matrix",
    "timeline",
    "contradictions",
    "full_report",
    "legal_draft_support",
    "case_summary",
]
DocumentAnalysisOutputFormat = Literal["json", "markdown", "docx", "csv"]


def default_output_formats() -> list[DocumentAnalysisOutputFormat]:
    return ["json", "markdown"]


class DocumentAnalysisTask(BaseModel):
    task_id: str
    thread_id: str
    user_id: str | None = None
    case_id: str | None = None
    doc_ids: list[str]
    query: str
    modes: list[DocumentAnalysisMode]
    allowed_page_ranges: dict[str, list[tuple[int, int]]] = Field(default_factory=dict)
    require_citations: bool = True
    max_pages_per_doc: int = 200
    max_total_pages: int = 500
    web_allowed: bool = False
    use_graph: bool = True
    output_formats: list[DocumentAnalysisOutputFormat] = Field(
        default_factory=default_output_formats
    )
    require_human_review_for_drafts: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_scope(self) -> DocumentAnalysisTask:
        if not self.doc_ids:
            msg = "At least one doc_id is required."
            raise ValueError(msg)
        if not self.modes:
            msg = "At least one analysis mode is required."
            raise ValueError(msg)
        total_pages = 0
        for doc_id, ranges in self.allowed_page_ranges.items():
            if doc_id not in self.doc_ids:
                msg = f"Allowed page range references unauthorized doc_id: {doc_id}"
                raise ValueError(msg)
            for start, end in ranges:
                if start < 1 or end < start:
                    msg = "Page ranges must be positive and ordered."
                    raise ValueError(msg)
                span = end - start + 1
                if span > self.max_pages_per_doc:
                    msg = "Allowed page range exceeds max_pages_per_doc."
                    raise ValueError(msg)
                total_pages += span
        if total_pages > self.max_total_pages:
            msg = "Allowed page ranges exceed max_total_pages."
            raise ValueError(msg)
        return self


class EvidenceCitation(BaseModel):
    doc_id: str
    chunk_id: str | None = None
    page_start: int
    page_end: int
    source_path: str | None = None
    quote: str | None = None
    relevance: float | None = None
    extraction_method: str | None = None


class EvidenceMatrixRow(BaseModel):
    claim_id: str
    claim: str
    claim_type: Literal["fact", "inference", "uncertainty", "contradiction", "missing_evidence"]
    supporting_evidence: list[EvidenceCitation] = Field(default_factory=list)
    opposing_evidence: list[EvidenceCitation] = Field(default_factory=list)
    strength: Literal["strong", "moderate", "weak", "unsupported"]
    notes: str = ""
    needs_human_review: bool = False


class TimelineEvent(BaseModel):
    event_id: str
    date_text: str
    normalized_date: date | None = None
    date_certainty: Literal["exact", "approximate", "inferred", "unknown"]
    event_summary: str
    involved_entities: list[str] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    notes: str = ""


class ContradictionFinding(BaseModel):
    contradiction_id: str
    topic: str
    statement_a: str
    statement_b: str
    citation_a: EvidenceCitation
    citation_b: EvidenceCitation
    contradiction_type: Literal[
        "date",
        "identity",
        "sequence",
        "content",
        "omission",
        "metadata",
        "other",
    ]
    severity: Literal["low", "medium", "high"]
    explanation: str
    needs_human_review: bool = True


class MissingEvidenceFinding(BaseModel):
    finding_id: str
    expected_evidence: str
    why_it_matters: str
    related_claims: list[str] = Field(default_factory=list)
    search_attempts: list[str] = Field(default_factory=list)
    status: Literal["not_found", "ambiguous", "outside_scope"]


class DocumentAnalysisResult(BaseModel):
    task_id: str
    thread_id: str
    status: Literal["ok", "partial", "failed", "blocked", "needs_human_review"]
    executive_summary: str
    evidence_matrix: list[EvidenceMatrixRow] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    contradictions: list[ContradictionFinding] = Field(default_factory=list)
    missing_evidence: list[MissingEvidenceFinding] = Field(default_factory=list)
    draft_sections: dict[str, str] = Field(default_factory=dict)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    generated_files: list[str] = Field(default_factory=list)
    human_review_required: bool = False
    warnings: list[str] = Field(default_factory=list)
    raw_agent_summary: str | None = None

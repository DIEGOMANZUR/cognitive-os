from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class ToolRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def _source_display(source_path: str, title: str | None = None) -> str:
    """Render a user-facing source label without leaking absolute filesystem paths.

    - If a `title` is provided, it wins (it carries the document title from the DB).
    - Otherwise, take the basename of `source_path` by splitting on either separator,
      so both POSIX (`/tmp/foo.pdf`) and Windows (`C:\\docs\\foo.pdf`) paths collapse
      to their final segment regardless of the host OS where the lookup happens.
    """
    if title:
        stripped = title.strip()
        if stripped:
            return stripped
    if not source_path:
        return ""
    last_slash = max(source_path.rfind("/"), source_path.rfind("\\"))
    candidate = source_path[last_slash + 1 :] if last_slash >= 0 else source_path
    return candidate or source_path


class RetrievalCitation(BaseModel):
    source_path: str = ""
    page_start: int = 0
    page_end: int = 0
    quote: str | None = None
    doc_id: str | None = None
    chunk_id: str | None = None
    url: str | None = None
    title: str | None = None
    date: str | None = None

    @property
    def citation(self) -> str:
        if self.url:
            title = self.title or self.url
            date = f" ({self.date})" if self.date else ""
            return f"{title}{date} - {self.url}"
        display = _source_display(self.source_path, self.title)
        local = (
            f"{display}:{self.page_start}-{self.page_end}"
            if display
            else (f"p{self.page_start}-{self.page_end}")
        )
        identifiers = []
        if self.doc_id:
            identifiers.append(f"doc_id={self.doc_id}")
        if self.chunk_id:
            identifiers.append(f"chunk_id={self.chunk_id}")
        return f"{local} [{' '.join(identifiers)}]" if identifiers else local


class HumanReviewItem(BaseModel):
    reason: str
    risk_level: ToolRiskLevel = ToolRiskLevel.MEDIUM
    proposed_action: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    route: str
    content: str
    citations: list[RetrievalCitation] = Field(default_factory=list)
    uncertainty: str | None = None


class BudgetState(BaseModel):
    max_tokens: int = 128_000
    used_tokens: int = 0


class ToolPolicy(BaseModel):
    readonly_mode: bool = True
    require_human_approval_for_external_actions: bool = True
    allowed_risk_level: ToolRiskLevel = ToolRiskLevel.LOW


class RouterDecision(BaseModel):
    route: Literal["research", "legal", "comm", "social"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    needs_human_review: bool = False


class CognitiveState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    thread_id: str
    user_id: str
    active_route: str
    retrieved_context: list[RetrievalCitation]
    pending_human_review: HumanReviewItem | None
    budget: BudgetState
    tool_policy: ToolPolicy
    error_count: int
    agent_result: AgentResult
    requested_doc_ids: NotRequired[list[str]]
    case_id: NotRequired[str | None]
    last_research_report: NotRequired[dict[str, Any]]
    last_deepagent_result: NotRequired[dict[str, Any]]
    last_document_analysis_result: NotRequired[dict[str, Any]]
    last_error: NotRequired[str | None]
    route_reason: NotRequired[str | None]

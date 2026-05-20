from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DeepAgentMemoryScope = Literal["global", "user", "case", "thread", "agent"]
DeepAgentMemoryKind = Literal[
    "preference",
    "procedure",
    "lesson",
    "warning",
    "fact",
    "style",
    "tool_feedback",
    "episodic",
]
DeepAgentMemorySource = Literal["human", "agent_proposed", "consolidated", "system"]
DeepAgentMemorySensitivity = Literal["public", "internal", "sensitive", "secret"]
DeepAgentMemoryStatus = Literal["active", "pending_approval", "rejected", "archived"]


class DeepAgentMemoryItem(BaseModel):
    memory_id: str
    scope: DeepAgentMemoryScope
    user_id: str | None = None
    case_id: str | None = None
    thread_id: str | None = None
    agent_name: str
    kind: DeepAgentMemoryKind
    content: str
    source: DeepAgentMemorySource
    confidence: float = Field(ge=0.0, le=1.0)
    sensitivity: DeepAgentMemorySensitivity
    status: DeepAgentMemoryStatus
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeepAgentMemoryProposal(BaseModel):
    proposal_id: str
    proposed_by_agent: str
    scope: DeepAgentMemoryScope
    reason: str
    proposed_content: str
    sensitivity: DeepAgentMemorySensitivity
    source_task_id: str | None = None
    requires_approval: bool = True
    # Fase 71 P2.J: scoping context propagated from the calling task so the
    # materialised memory can be recalled per-user / per-case / per-thread.
    # Optional + nullable to preserve back-compat with existing proposals.
    user_id: str | None = None
    case_id: str | None = None
    thread_id: str | None = None
    # Fase 78 (Fase A): proposals can now carry a kind so the recipe
    # extractor can emit `procedure` rows that the approval pipeline
    # materialises with the correct kind. Defaults keep backwards compat
    # with the consolidator that historically only emitted lessons.
    kind: DeepAgentMemoryKind = "lesson"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # `metadata` overlaps with BaseModel.metadata in some pydantic versions;
    # silence the protected-namespace warning since we own the field.
    model_config = ConfigDict(protected_namespaces=())


class DeepAgentSkillDescriptor(BaseModel):
    name: str
    description: str
    path: str
    version: str
    risk_level: str
    allowed_tools: list[str]
    enabled: bool = True

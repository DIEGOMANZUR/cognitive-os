from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class DeepAgentTask(BaseModel):
    task_id: str
    thread_id: str
    user_id: str | None = None
    task_type: Literal["research", "document_analysis"]
    query: str
    allowed_doc_ids: list[str] = Field(default_factory=list)
    web_allowed: bool = False
    max_iterations: int = 12
    budget_usd_limit: float = 3.0
    require_citations: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeepAgentCitation(BaseModel):
    source_type: Literal["local_doc", "web", "neo4j"]
    title: str | None = None
    doc_id: str | None = None
    chunk_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    url: str | None = None
    quote: str | None = None
    relevance: float | None = None


class DeepAgentResult(BaseModel):
    task_id: str
    thread_id: str
    status: Literal["ok", "needs_more_info", "blocked", "failed"]
    answer: str
    findings: list[str] = Field(default_factory=list)
    citations: list[DeepAgentCitation] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    generated_files: list[str] = Field(default_factory=list)
    requested_external_actions: list[dict[str, Any]] = Field(default_factory=list)
    raw_summary: str | None = None


class DeepAgentWorkspace(BaseModel):
    root_dir: Path
    thread_id: str
    task_id: str


class DeepAgentToolPolicy(BaseModel):
    allow_local_rag: bool = True
    allow_neo4j_read: bool = True
    allow_web: bool = False
    allow_workspace_write: bool = True
    allow_shell: bool = False
    allow_browser: bool = False
    allow_email: bool = False
    allow_social_posting: bool = False
    allow_delete: bool = False
    # Read-only personal-assistant capabilities. The underlying services do
    # their own capability-gating (`status() != "ready"` blocks the call), so
    # default-on is safe: the tool will return a controlled error if the
    # capability is disabled or unconfigured.
    allow_maps: bool = True
    allow_calendar_read: bool = True
    allow_drive_read: bool = True
    allow_notes_read: bool = True
    # WebBridge drives the user's real browser. Default off — the agent must be
    # explicitly trusted with a session that owns the user's logins. Even when
    # on, the service-level allow-list + mutations gate still apply.
    allow_kimi_webbridge: bool = False
    # Captcha solving is read-only for the page (it returns a token the agent
    # injects) but spends CapSolver credits, so it stays a deliberate opt-in.
    # Default on: the service still gates on ENABLE_CAPTCHA_SOLVING + key, so a
    # disabled deployment yields a controlled error rather than a real call.
    allow_captcha_solving: bool = True

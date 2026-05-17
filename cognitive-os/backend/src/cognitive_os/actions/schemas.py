from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

CapabilityStatus = Literal["disabled", "blocked", "configured", "ready"]
ActionType = Literal[
    "computer_organize",
    "browser_navigation",
    "gmail_query",
    "godaddy_dns_change",
    "document_generate",
    "browser_preview",
    "browser_interactive",
    "calendar_create_event",
    "drive_upload_file",
]
DocumentFormat = Literal["docx", "xlsx", "pptx"]
ActionRequestStatus = Literal[
    "previewed",
    "blocked",
    "pending_approval",
    "queued",
    "running",
    "completed",
    "failed",
    "rejected",
    "cancelled",
]


class ActionCapabilityStatus(BaseModel):
    name: str
    status: CapabilityStatus
    summary: str
    requires_approval: bool = True
    dry_run_only: bool = True
    reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrowserNavigationRequest(BaseModel):
    url: str = Field(min_length=1)
    headed: bool = False
    vision: bool = False
    persistent_session: bool = False
    session_name: str = Field(default="default", min_length=1, max_length=80)


class BrowserNavigationValidation(BaseModel):
    allowed: bool
    url: str
    normalized_origin: str | None = None
    provider: str
    headless: bool
    vision: bool
    persistent_session: bool
    profile_dir: str | None = None
    reason: str | None = None
    requires_approval: bool = True


class ComputerOrganizeRequest(BaseModel):
    root_path: str = Field(min_length=1)
    strategy: Literal["by_type"] = "by_type"
    recursive: bool = False
    include_hidden: bool = False
    max_files: int | None = Field(default=None, ge=1, le=5000)


class FileMovePreview(BaseModel):
    source: str
    destination: str
    category: str
    reason: str


class ComputerOrganizePlan(BaseModel):
    status: Literal["ok", "blocked"]
    root_path: str
    dry_run_only: bool = True
    requires_approval: bool = True
    operations: list[FileMovePreview] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reason: str | None = None


class FileMoveResult(BaseModel):
    source: str
    destination: str
    status: Literal["moved", "skipped", "failed"]
    error: str | None = None


class ComputerOrganizeExecutionResult(BaseModel):
    status: Literal["completed", "blocked", "failed"]
    root_path: str
    moved_count: int = 0
    operations: list[FileMoveResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reason: str | None = None


class ComputerInventoryRequest(BaseModel):
    root_path: str = Field(min_length=1)
    recursive: bool = True
    include_hidden: bool = False
    max_files: int = Field(default=5000, ge=1, le=50000)
    include_sha256: bool = False


class FileInventoryEntry(BaseModel):
    relative_path: str
    category: str
    extension: str
    size_bytes: int
    modified_at: str
    sha256: str | None = None


class ComputerInventoryResult(BaseModel):
    status: Literal["completed", "blocked", "failed"]
    root_path: str
    inventory_path: str | None = None
    file_count: int = 0
    total_bytes: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_extension: dict[str, int] = Field(default_factory=dict)
    entries: list[FileInventoryEntry] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reason: str | None = None


class GmailQueryPreviewRequest(BaseModel):
    query: str = ""
    max_results: int = Field(default=10, ge=1, le=50)
    include_snippets: bool = True


class GmailQueryPreview(BaseModel):
    status: Literal["ok", "blocked"]
    query: str
    max_results: int
    scopes: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    reason: str | None = None


class GmailDigestRequest(BaseModel):
    lookback_hours: int = Field(default=24, ge=1, le=168)
    max_messages: int = Field(default=50, ge=1, le=200)
    labels: list[str] = Field(default_factory=list)
    include_proposed_drafts: bool = True


class GmailDigestSender(BaseModel):
    domain: str
    address_redacted: str
    message_count: int
    latest_subject: str | None = None


class GmailDigestMessage(BaseModel):
    message_id: str
    thread_id: str | None = None
    sender_domain: str
    sender_redacted: str
    subject: str | None = None
    snippet: str | None = None
    labels: list[str] = Field(default_factory=list)
    received_at: datetime | None = None


class GmailDigestProposedDraft(BaseModel):
    in_reply_to_message_id: str
    sender_redacted: str
    subject_hint: str | None = None
    rationale: str
    body_preview: str
    requires_approval: bool = True


class GmailDigestPreview(BaseModel):
    status: Literal["ok", "blocked"]
    lookback_hours: int
    max_messages: int
    scopes: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    dry_run_only: bool = True
    total_messages: int = 0
    senders: list[GmailDigestSender] = Field(default_factory=list)
    top_messages: list[GmailDigestMessage] = Field(default_factory=list)
    proposed_drafts: list[GmailDigestProposedDraft] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reason: str | None = None


class GoDaddyDnsRecordChange(BaseModel):
    domain: str = Field(min_length=1)
    record_type: Literal["A", "AAAA", "CNAME", "MX", "TXT", "SRV", "NS"]
    name: str = Field(default="@", min_length=1, max_length=255)
    data: str = Field(min_length=1, max_length=2048)
    ttl: int = Field(default=600, ge=600, le=604800)
    priority: int | None = Field(default=None, ge=0, le=65535)


class GoDaddyDnsChangePreview(BaseModel):
    status: Literal["ok", "blocked"]
    method: Literal["PATCH", "PUT"]
    endpoint: str
    change: GoDaddyDnsRecordChange
    dry_run_only: bool = True
    requires_approval: bool = True
    reason: str | None = None


class GoDaddyDnsExecutionResult(BaseModel):
    status: Literal["completed", "blocked", "failed"]
    method: Literal["PATCH", "PUT"]
    endpoint: str
    change: GoDaddyDnsRecordChange
    dry_run_only: bool = True
    status_code: int | None = None
    reason: str | None = None


class DocumentSection(BaseModel):
    heading: str = Field(default="", max_length=300)
    paragraphs: list[str] = Field(default_factory=list)
    tables: list[DocumentTable] = Field(default_factory=list)
    images: list[DocumentImage] = Field(default_factory=list)


class DocumentTable(BaseModel):
    caption: str = Field(default="", max_length=300)
    headers: list[str] = Field(default_factory=list, max_length=50)
    rows: list[list[str | float | int]] = Field(default_factory=list, max_length=500)


class DocumentImage(BaseModel):
    path: str = Field(min_length=1, max_length=1000)
    caption: str = Field(default="", max_length=300)
    width_inches: float = Field(default=5.5, gt=0, le=7.0)


class SpreadsheetFormula(BaseModel):
    row: int = Field(ge=1, le=100000)
    column: int = Field(ge=1, le=16384)
    formula: str = Field(min_length=2, max_length=2000)


class SpreadsheetSheet(BaseModel):
    name: str = Field(default="Sheet1", min_length=1, max_length=31)
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str | float | int]] = Field(default_factory=list)
    formulas: list[SpreadsheetFormula] = Field(default_factory=list)


class SlideContent(BaseModel):
    title: str = Field(default="", max_length=300)
    layout: Literal["bullets", "title", "two_column", "quote"] = "bullets"
    bullets: list[str] = Field(default_factory=list)
    right_bullets: list[str] = Field(default_factory=list)
    quote: str = Field(default="", max_length=2000)
    caption: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=4000)


class DocumentGenerateRequest(BaseModel):
    format: DocumentFormat
    output_filename: str = Field(min_length=1, max_length=200)
    title: str = Field(default="", max_length=300)
    subtitle: str = Field(default="", max_length=300)
    author: str = Field(default="", max_length=200)
    docx_sections: list[DocumentSection] = Field(default_factory=list)
    xlsx_sheets: list[SpreadsheetSheet] = Field(default_factory=list)
    pptx_slides: list[SlideContent] = Field(default_factory=list)


class DocumentGeneratePreview(BaseModel):
    status: Literal["ok", "blocked"]
    format: DocumentFormat
    output_path: str
    estimated_blocks: int
    requires_approval: bool = False
    reason: str | None = None


class DocumentGenerateExecutionResult(BaseModel):
    status: Literal["completed", "blocked", "failed"]
    format: DocumentFormat
    output_path: str
    bytes_written: int = 0
    reason: str | None = None


class BrowserPreviewRequest(BaseModel):
    url: str = Field(min_length=1)
    capture_screenshot: bool = True
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "load"


class BrowserPreviewExecutionResult(BaseModel):
    status: Literal["completed", "blocked", "failed"]
    url: str
    final_url: str | None = None
    title: str | None = None
    screenshot_path: str | None = None
    bytes_written: int = 0
    duration_ms: int = 0
    reason: str | None = None


BrowserStepKind = Literal[
    "navigate",
    "click",
    "fill",
    "scroll",
    "wait",
    "screenshot",
    "analyze",
]


class BrowserStep(BaseModel):
    """One step in a `browser_interactive` plan.

    - `navigate`: load a NEW url (must pass the domain allow-list)
    - `click`: click a CSS selector
    - `fill`: type `value` into a CSS selector
    - `scroll`: scroll the page by `value` pixels (default 600)
    - `wait`: wait `value` milliseconds (capped to 10s)
    - `screenshot`: capture a PNG and persist it inside BROWSER_SCREENSHOT_DIR
    - `analyze`: capture a screenshot then call the multimodal LLM with `prompt`
    """

    kind: BrowserStepKind
    url: str | None = None
    selector: str | None = Field(default=None, max_length=400)
    value: str | None = Field(default=None, max_length=2000)
    prompt: str | None = Field(default=None, max_length=4000)


class BrowserInteractiveRequest(BaseModel):
    url: str = Field(min_length=1)
    steps: list[BrowserStep] = Field(default_factory=list, max_length=24)
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "load"


class BrowserStepResult(BaseModel):
    step_index: int
    kind: BrowserStepKind
    status: Literal["ok", "blocked", "failed"]
    final_url: str | None = None
    title: str | None = None
    screenshot_path: str | None = None
    analysis: str | None = None
    reason: str | None = None
    duration_ms: int = 0


class BrowserInteractiveExecutionResult(BaseModel):
    status: Literal["completed", "blocked", "failed"]
    url: str
    final_url: str | None = None
    steps: list[BrowserStepResult] = Field(default_factory=list)
    reason: str | None = None
    duration_ms: int = 0


class ActionRequestView(BaseModel):
    id: UUID
    action_type: ActionType
    status: ActionRequestStatus
    requested_by: str | None
    approval_id: UUID | None = None
    job_id: UUID | None = None
    payload_redacted: dict[str, Any] = Field(default_factory=dict)
    preview: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class ActionDispatchResponse(BaseModel):
    action_request: ActionRequestView
    dispatched: bool
    reason: str | None = None


# --- workflow.v1: exportable / importable ActionRequest plans ------------

# Subset of ActionType that the workflow document supports. Read-only carriles
# (`browser_navigation`, `gmail_query`) are intentionally excluded — they have
# no payload that survives serialization in a useful way.
WorkflowActionType = Literal[
    "computer_organize",
    "godaddy_dns_change",
    "document_generate",
    "browser_preview",
    "browser_interactive",
    "calendar_create_event",
    "drive_upload_file",
]


class WorkflowSource(BaseModel):
    """Provenance of a workflow document.

    Optional; lets the importer trace a `workflow.v1` JSON back to the original
    `ActionRequest` and the operator that exported it.
    """

    exported_at: datetime
    exported_by: str | None = None
    source_action_request_id: UUID | None = None


class WorkflowDocument(BaseModel):
    """Versioned, declarative export of an ActionRequest plan.

    Stable on-disk format so operators can clone, edit, version-control and
    re-submit plans. The redacted payload is the public surface; if the
    original request had executable secrets (encrypted at rest), they are
    intentionally NOT included — the importer recomputes a fresh payload from
    user-supplied fields.

    Schema versioning: `workflow_version` starts at `1.0`. Future breaking
    changes bump the major; additive changes bump the minor.
    """

    workflow_version: Literal["1.0"] = "1.0"
    action_type: WorkflowActionType
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Redacted payload (no secret values).",
    )
    preview: dict[str, Any] | None = Field(
        default=None,
        description="Optional read-only preview snapshot for the operator UI.",
    )
    source: WorkflowSource | None = None
    notes: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowImportResult(BaseModel):
    """Result of a `POST /actions/requests/from-workflow` call."""

    action_request: ActionRequestView
    dry_run: bool
    notes: str | None = None

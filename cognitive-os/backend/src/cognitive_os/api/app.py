from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator
from contextlib import ExitStack, asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

import structlog
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select

from cognitive_os.actions.browser import BrowserActionService
from cognitive_os.actions.calendar import (
    CalendarError,
    CalendarEvent,
    CalendarService,
    CalendarStatus,
    EventCreatePreview,
    EventCreateRequest,
    ListEventsRequest,
)
from cognitive_os.actions.captcha import (
    CaptchaSolution,
    CaptchaSolverError,
    CaptchaSolverService,
    CaptchaStatus,
    ImageCaptchaRequest,
    TokenCaptchaRequest,
)
from cognitive_os.actions.computer import ComputerActionService
from cognitive_os.actions.documents import DocumentActionService
from cognitive_os.actions.domains import GoDaddyActionService
from cognitive_os.actions.drive import (
    DriveError,
    DriveFile,
    DriveFolderPreview,
    DriveFolderRequest,
    DriveSearchRequest,
    DriveService,
    DriveStatus,
    DriveUploadPreview,
    DriveUploadRequest,
)
from cognitive_os.actions.gmail_digest import GmailDigestService, GmailReader, GmailRestReader
from cognitive_os.actions.kimi_webbridge import (
    ClickRequest,
    CloseSessionRequest,
    EvaluateRequest,
    FillRequest,
    KimiWebBridgeError,
    KimiWebBridgeService,
    NavigateRequest,
    ScreenshotRequest,
    SnapshotRequest,
    WebBridgeCallResult,
    WebBridgeStatus,
)
from cognitive_os.actions.mail import GmailActionService
from cognitive_os.actions.maps import (
    GeocodeRequest,
    GeocodeResult,
    MapsError,
    MapsService,
    MapsStatus,
    RoutePlan,
    RouteRequest,
)
from cognitive_os.actions.payload_crypto import protect_payload, reveal_payload
from cognitive_os.actions.schemas import (
    ActionCapabilityStatus,
    ActionDispatchResponse,
    ActionRequestStatus,
    ActionRequestView,
    ActionType,
    BrowserInteractiveRequest,
    BrowserNavigationRequest,
    BrowserNavigationValidation,
    BrowserPreviewRequest,
    ComputerInventoryRequest,
    ComputerInventoryResult,
    ComputerOrganizePlan,
    ComputerOrganizeRequest,
    DocumentGeneratePreview,
    DocumentGenerateRequest,
    GmailDigestPreview,
    GmailDigestRequest,
    GmailQueryPreview,
    GmailQueryPreviewRequest,
    GoDaddyDnsChangePreview,
    GoDaddyDnsRecordChange,
    WorkflowDocument,
    WorkflowImportResult,
)
from cognitive_os.actions.service import (
    ActionRequestError,
    ActionRequestService,
    ApprovalAlreadyDecidedError,
    ApprovalDecisionError,
    ApprovalNotFoundError,
    ApprovalPayloadCorruptError,
    ApprovalSelfDecisionError,
    decide_approval,
)
from cognitive_os.agents.graph import (
    build_graph,
    cast_state,
    initial_state,
    postgres_checkpointer,
    resume_graph,
)
from cognitive_os.agents.research import ReadOnlyResearchTools, ResearchAgent
from cognitive_os.agents.research_orchestrator import (
    ResearchEvent,
    ResearchOrchestrator,
    ResearchOrchestratorDisabledError,
    ResearchRunRequest,
)
from cognitive_os.agents.research_persistence import create_research_run_store
from cognitive_os.agents.state import CognitiveState
from cognitive_os.agents.web_search import configured_web_search_provider_names
from cognitive_os.assist.schemas import (
    PersonalNoteCreate,
    PersonalNoteSearchHit,
    PersonalNoteUpdate,
    PersonalNoteView,
    PersonalTaskCreate,
    PersonalTaskUpdate,
    PersonalTaskView,
)
from cognitive_os.assist.service import PersonalAssistDisabledError, PersonalAssistService
from cognitive_os.core.auth import (
    AuthenticatedUser,
    require_admin_user,
    require_authenticated_user,
    require_langsmith_api_access,
)
from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.core.health import HealthDashboard, check_health_dashboard
from cognitive_os.core.observability import configure_langsmith, disable_langsmith
from cognitive_os.core.path_policy import IngestPathPolicyError, resolve_ingest_document_path
from cognitive_os.core.rate_limit import rate_limit_dependency
from cognitive_os.db.models import (
    ActionRequest,
    AuditEvent,
    Document,
    DocumentChunk,
    HumanApproval,
    Job,
    JobEvent,
)
from cognitive_os.deepagents.document_analysis.schemas import (
    DocumentAnalysisResult,
    DocumentAnalysisTask,
)
from cognitive_os.deepagents.document_analysis.service import DocumentAnalysisService
from cognitive_os.deepagents.memory_schemas import DeepAgentMemoryScope
from cognitive_os.deepagents.memory_service import DeepAgentMemoryError, DeepAgentMemoryService
from cognitive_os.deepagents.openshell_adapter import (
    OpenShellAdapter,
    requires_openshell_approval,
)
from cognitive_os.deepagents.openshell_policy import redact_openshell_payload
from cognitive_os.deepagents.openshell_schemas import OpenShellResult, OpenShellTask
from cognitive_os.deepagents.skills_registry import DeepAgentSkillsRegistry
from cognitive_os.mail.schemas import (
    MailApproveReplyRequest,
    MailEditReplyRequest,
    MailMessageView,
    MailSendResult,
    MailStatusView,
    MailSyncResult,
)
from cognitive_os.mail.service import MailServiceError, PersonalMailService
from cognitive_os.memory.retrieval import RetrievedContext, retrieve_context
from cognitive_os.voice.schemas import SpeakRequest, TranscriptionResult, VoiceStatus
from cognitive_os.voice.service import VoiceError, VoiceService
from cognitive_os.workers.tasks import (
    consolidate_all_deepagent_memory_task,
    ingest_pdf_task,
    run_action_request_task_async,
    run_deepagent_task_async,
    run_document_analysis_task_async,
    run_openshell_task_async,
    sync_personal_mail_task,
)

logger = structlog.get_logger(__name__)


def _empty_retriever(query: str) -> list[RetrievedContext]:
    del query
    return []


def _safe_retriever(query: str) -> list[RetrievedContext]:
    """Retrieve hybrid context, returning [] when the stack is not yet provisioned.

    The chat endpoint must keep working when Weaviate or the embeddings provider
    are unavailable (fresh install, dev without keys, network blip). In that case
    we degrade to no-retrieval rather than 500'ing the request.
    """
    try:
        return retrieve_context(query)
    except Exception as exc:
        logger.warning(
            "retrieve_context_unavailable",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return []


def _build_default_graph(checkpointer: Any) -> Any:
    return build_graph(
        checkpointer=checkpointer,
        retriever=_safe_retriever,
        research_agent=ResearchAgent(
            tools=ReadOnlyResearchTools(local_search=_safe_retriever),
        ),
    )


# Module-level graph using MemorySaver. Production swaps this in the lifespan
# below for a Postgres-backed graph; tests rely on monkeypatching this name.
_api_graph = _build_default_graph(MemorySaver())
_checkpointer_stack: ExitStack | None = None
_checkpointer_kind: str = "memory"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Open a Postgres-backed checkpointer for the duration of the API process.

    On startup we try to materialize a `PostgresSaver` (so threads survive restarts).
    If Postgres is unreachable or the checkpointer setup fails for any reason we
    log a warning and stay on the in-memory checkpointer that was bound at import
    time. Either way `_api_graph` is a working graph.
    """
    global _api_graph, _checkpointer_stack, _checkpointer_kind
    stack = ExitStack()
    original_graph = _api_graph
    original_kind = _checkpointer_kind
    # Wire LangSmith env vars into os.environ for LangChain auto-tracing.
    await asyncio.to_thread(configure_langsmith)
    try:
        try:
            saver = await asyncio.to_thread(stack.enter_context, postgres_checkpointer())
            _api_graph = _build_default_graph(saver)
            _checkpointer_stack = stack
            _checkpointer_kind = "postgres"
            logger.info("checkpointer_ready", backend="postgres")
        except Exception as exc:
            await asyncio.to_thread(stack.close)
            stack = ExitStack()
            _checkpointer_stack = stack
            _checkpointer_kind = "memory"
            logger.warning(
                "checkpointer_postgres_unavailable_fallback_memory",
                error_type=type(exc).__name__,
                error=str(exc),
            )
        yield
    finally:
        try:
            await asyncio.to_thread(stack.close)
        except Exception as exc:
            logger.warning(
                "checkpointer_close_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
        _api_graph = original_graph
        _checkpointer_stack = None
        _checkpointer_kind = original_kind
        disable_langsmith()


app = FastAPI(title="Cognitive OS API", lifespan=lifespan)
_auth_dependency = Depends(require_authenticated_user)
_admin_auth_dependency = Depends(require_admin_user)
_langsmith_auth_dependency = Depends(require_langsmith_api_access)

# Rate limit policies for hot endpoints. Defaults assume one human operator per
# user_id: 30 approval decisions per minute is generous, 60 dispatch attempts
# protects against a buggy frontend loop, 30 request creations per minute
# bounds idempotency-fanout abuse.
_RL_APPROVAL_DECISION = Depends(
    rate_limit_dependency("approval_decision", max_events=30, window_seconds=60.0)
)
_RL_ACTION_DISPATCH = Depends(
    rate_limit_dependency("action_dispatch", max_events=60, window_seconds=60.0)
)
_RL_ACTION_REQUEST_CREATE = Depends(
    rate_limit_dependency("action_request_create", max_events=30, window_seconds=60.0)
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Any, call_next: Any) -> Any:
    """Attach a request-scoped correlation id to logs and the response.

    Honors an incoming `X-Request-ID` header (truncated to 64 chars to bound the
    surface) or generates a fresh uuid4. The id is bound to structlog's
    contextvars so any logger inside the request inherits it, and echoed back
    on the response so callers can correlate failures with server-side logs.
    """
    import structlog as _structlog

    incoming = (request.headers.get("X-Request-ID") or "").strip()[:64]
    request_id = incoming or str(uuid4())
    _structlog.contextvars.clear_contextvars()
    _structlog.contextvars.bind_contextvars(request_id=request_id)
    try:
        response = await call_next(request)
    finally:
        _structlog.contextvars.clear_contextvars()
    response.headers["X-Request-ID"] = request_id
    return response


class HealthResponse(BaseModel):
    status: str
    service: str


class SystemInfoResponse(BaseModel):
    service: str
    environment: str
    python_version: str
    fastapi_version: str
    pytest_marker_default: str
    require_human_approval_for_external_actions: bool
    approval_require_four_eyes: bool
    approval_pending_max_hours: int
    action_payload_encryption_required: bool
    research_persistence_backend: str
    git_commit: str | None = None
    alembic_head: str | None = None
    started_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    thread_id: str | None = None
    doc_ids: list[str] | None = None
    case_id: str | None = None


class ChatResponse(BaseModel):
    thread_id: str
    message: str
    route: str
    pending_human_review: dict[str, Any] | None = None


class ThreadResponse(BaseModel):
    thread_id: str
    values: dict[str, Any]


class ResumeThreadRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject|edit)$")
    message: str | None = None


class IngestDocumentRequest(BaseModel):
    document_path: str = Field(min_length=1)


class IngestDocumentResponse(BaseModel):
    job_id: UUID
    status: str


class JobResponse(BaseModel):
    id: UUID
    job_type: str
    status: str
    progress: int
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class JobEventResponse(BaseModel):
    id: UUID
    job_id: UUID
    event_type: str
    status: str
    message: str | None
    metadata_json: dict[str, Any]
    created_at: datetime


class ApprovalResponse(BaseModel):
    id: UUID
    requested_action: str
    args_redacted: dict[str, Any]
    status: str
    requested_by: str | None
    approver_user_id: str | None
    created_at: datetime
    decided_at: datetime | None


class DeepAgentResearchRequest(BaseModel):
    query: str = Field(min_length=1)
    thread_id: str | None = None
    web_allowed: bool = False


class OpenShellRunResponse(BaseModel):
    status: str
    job_id: UUID | None = None
    approval_id: UUID | None = None
    result: OpenShellResult | None = None


class DocumentAnalysisRunResponse(BaseModel):
    status: str
    task_id: str
    job_id: UUID | None = None
    result: DocumentAnalysisResult | None = None


class MemoryRejectRequest(BaseModel):
    reason: str = Field(min_length=1)


class MemoryExportRequest(BaseModel):
    scope: DeepAgentMemoryScope
    user_id: str | None = None
    case_id: str | None = None


class EpisodicMemoryRequest(BaseModel):
    """Registro autorizado de un hecho episódico para el usuario (cronología corta/medio plazo).

    Sirve como base temporal hasta integrar extracción automática desde trabajos y Telegram.
    """

    summary: str = Field(min_length=8, max_length=4000)
    agent_name: str = Field(default="cognitive-os", min_length=1, max_length=128)
    thread_id: str | None = Field(default=None, max_length=128)
    case_id: str | None = Field(default=None, max_length=128)
    sensitivity: Literal["public", "internal", "sensitive"] = Field(default="internal")


class DocumentSummaryResponse(BaseModel):
    id: UUID
    title: str | None
    source_path: str
    sha256: str
    status: str
    page_count: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class AuditEventResponse(BaseModel):
    id: UUID
    actor_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    metadata_json: dict[str, Any]
    created_at: datetime


class KnowledgeStatsResponse(BaseModel):
    documents: int
    pages: int
    chunks: int
    jobs_running: int
    jobs_completed: int
    jobs_failed: int
    approvals_pending: int


class PublicConfigResponse(BaseModel):
    environment: str
    web_search_enabled: bool
    tools_readonly_mode: bool
    require_human_approval_for_external_actions: bool
    enable_browser_automation: bool
    enable_computer_actions: bool
    enable_email_send: bool
    enable_social_posting: bool
    enable_document_generation: bool
    enable_research_orchestrator: bool
    research_persistence_backend: str
    enable_openharness_research: bool
    openharness_research_pipeline: str
    openharness_toolkit_preset: str
    openharness_workspace_mode: str
    openharness_web_tools: bool
    enable_openshell_sandbox: bool
    enable_personal_assistant_api: bool
    enable_personal_reminder_delivery: bool
    enable_maps_routing: bool
    maps_default_travel_mode: str
    enable_google_calendar: bool
    enable_google_calendar_write: bool
    enable_google_drive: bool
    enable_google_drive_write: bool
    google_drive_upload_max_bytes: int
    google_drive_deliverables_folder_name: str
    telegram_enabled: bool
    telegram_gmail_digest_enabled: bool
    langsmith_tracing: bool
    langsmith_endpoints_require_admin: bool
    browser_automation_provider: str
    browser_headless_default: bool
    browser_allow_headed: bool
    browser_allow_vision: bool
    browser_allowed_domains_count: int
    computer_allowed_roots_count: int
    computer_organize_dry_run_only: bool
    document_asset_roots_count: int
    gmail_read_enabled: bool
    gmail_send_enabled: bool
    mail_enabled: bool
    mail_godaddy_enabled: bool
    mail_require_approval_for_send: bool
    mail_poll_interval_seconds: int
    mail_fetch_max_per_folder: int
    mail_imap_timeout_seconds: int
    mail_smtp_timeout_seconds: int
    mail_gmail_label: str
    godaddy_enabled: bool
    godaddy_dns_dry_run_only: bool
    godaddy_allow_production_writes: bool
    godaddy_allowed_domains_count: int
    reranker_enabled: bool
    reranker_model: str
    deepagents_enable_skills: bool
    deepagents_enable_subagents: bool
    deepagents_enable_memory: bool
    deepagents_memory_require_approval: bool
    embeddings_provider: str
    embeddings_model: str
    embeddings_dimension: int
    embeddings_key_pool_size: int
    primary_llm_provider: str
    primary_llm_model: str
    web_search_providers: list[str]


class JobCancelResponse(BaseModel):
    id: UUID
    status: str


class ThreadSummaryResponse(BaseModel):
    thread_id: str
    last_active_at: datetime | None
    last_route: str | None
    last_message_preview: str | None


class DocumentChunkResponse(BaseModel):
    chunk_id: str
    chunk_index: int
    page_start: int
    page_end: int
    sha256: str
    text: str


class SkillDetailResponse(BaseModel):
    name: str
    description: str
    version: str
    risk_level: str
    allowed_tools: list[str]
    path: str
    enabled: bool
    content: str


class AgentPolicyView(BaseModel):
    allow_local_rag: bool
    allow_neo4j_read: bool
    allow_web: bool
    allow_workspace_write: bool
    allow_shell: bool
    allow_browser: bool
    allow_email: bool
    allow_social_posting: bool
    allow_delete: bool


class AgentStatsView(BaseModel):
    total_jobs: int
    running: int
    completed: int
    failed: int
    last_active_at: datetime | None


class AgentSummaryView(BaseModel):
    name: str
    kind: str
    description: str
    job_type: str
    policy: AgentPolicyView
    tools: list[str]
    skills: list[str]
    memory_enabled: bool
    requires_approval_for_drafts: bool
    web_search_enabled: bool
    stats: AgentStatsView


class LangSmithProjectView(BaseModel):
    id: str
    name: str
    run_count: int | None = None


class LangSmithRunView(BaseModel):
    id: str
    name: str | None
    run_type: str | None
    status: str | None
    start_time: datetime | None
    end_time: datetime | None
    latency_ms: float | None
    error: str | None
    total_tokens: int | None
    parent_run_id: str | None


class LangSmithRunDetailView(LangSmithRunView):
    inputs: dict[str, Any] | None = None
    outputs: dict[str, Any] | None = None
    extra: dict[str, Any] | None = None
    tags: list[str] | None = None


class LangSmithStatusView(BaseModel):
    enabled: bool
    project: str
    endpoint: str
    detail: str | None = None


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="cognitive-os")


_SYSTEM_STARTED_AT = datetime.now(UTC)


def _resolve_git_commit() -> str | None:
    """Capture the current commit at startup if running inside a git checkout.

    Returns short SHA on success, `None` when git is unreachable or the source
    tree was not built from a git clone (e.g. container with only the wheel).
    """
    import subprocess  # noqa: PLC0415 - localized to startup helper

    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent,
        Path(__file__).resolve().parent.parent.parent.parent.parent,
    ]
    for repo in candidates:
        if not (repo / ".git").exists():
            continue
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short=12", "HEAD"],
                cwd=str(repo),
                capture_output=True,
                text=True,
                check=False,
                timeout=2.0,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        if result.returncode == 0:
            return result.stdout.strip() or None
    return None


def _resolve_alembic_head() -> str | None:
    """Read the latest Alembic revision directly from the versions directory.

    Avoids importing the Alembic CLI at request time: we glob the version
    files and walk the down_revision chain to find the tip. Returns `None`
    when the directory is missing (e.g. running tests against an installed
    wheel).
    """
    import re  # noqa: PLC0415 - small helper localized to startup

    versions_dir = Path(__file__).resolve().parent.parent.parent.parent / "alembic" / "versions"
    if not versions_dir.exists():
        return None
    revision_re = re.compile(r"^revision[^=]*=\s*[\"']([0-9a-fA-F]+)[\"']", re.MULTILINE)
    down_re = re.compile(r"^down_revision[^=]*=\s*(?:[\"']([0-9a-fA-F]+)[\"']|None)", re.MULTILINE)
    children: set[str] = set()
    revisions: set[str] = set()
    for entry in versions_dir.glob("*.py"):
        try:
            text = entry.read_text(encoding="utf-8")
        except OSError:
            continue
        rev_match = revision_re.search(text)
        down_match = down_re.search(text)
        if rev_match:
            revisions.add(rev_match.group(1))
        if down_match and down_match.group(1):
            children.add(down_match.group(1))
    tips = revisions - children
    if not tips:
        return None
    # Multiple heads should never happen in this repo; pick lexicographic max.
    return sorted(tips)[-1]


_SYSTEM_GIT_COMMIT = _resolve_git_commit()
_SYSTEM_ALEMBIC_HEAD = _resolve_alembic_head()


@app.get("/system/info", response_model=SystemInfoResponse)
async def system_info(
    user: AuthenticatedUser = _auth_dependency,
) -> SystemInfoResponse:
    """Ops-facing snapshot of the live runtime: versions and policy defaults.

    Operators read this to confirm the API really restarted with the policy
    flags they expect (encryption required, four-eyes, approval TTL, research
    persistence backend). Cheaper than a full health dashboard and safe to
    poll from the operator console.
    """
    del user
    import sys

    import fastapi

    return SystemInfoResponse(
        service="cognitive-os",
        environment=settings.environment,
        python_version=sys.version.split()[0],
        fastapi_version=fastapi.__version__,
        pytest_marker_default="not integration and not slow",
        require_human_approval_for_external_actions=(
            settings.require_human_approval_for_external_actions
        ),
        approval_require_four_eyes=settings.approval_require_four_eyes,
        approval_pending_max_hours=settings.approval_pending_max_hours,
        action_payload_encryption_required=settings.action_payload_encryption_required,
        research_persistence_backend=settings.research_persistence_backend,
        git_commit=_SYSTEM_GIT_COMMIT,
        alembic_head=_SYSTEM_ALEMBIC_HEAD,
        started_at=_SYSTEM_STARTED_AT,
    )


@app.get("/health/dashboard", response_model=HealthDashboard)
async def health_dashboard(
    user: AuthenticatedUser = _auth_dependency,
) -> HealthDashboard:
    del user
    dashboard = await check_health_dashboard()
    return dashboard.model_copy(
        update={
            "components": [
                *dashboard.components,
                _checkpointer_component(),
            ]
        }
    )


def _checkpointer_component() -> Any:
    from cognitive_os.core.health import ComponentHealth  # local import avoids cycles

    return ComponentHealth(
        name="checkpointer",
        status="ok" if _checkpointer_kind == "postgres" else "configured",
        detail=(
            "LangGraph thread state is persisted to Postgres."
            if _checkpointer_kind == "postgres"
            else (
                "LangGraph thread state is held in memory only; restart loses threads. "
                "Configure Postgres via DATABASE_URL to enable persistence."
            )
        ),
        metadata={"backend": _checkpointer_kind},
    )


@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> StreamingResponse:
    """SSE stream of LangGraph node updates for incremental UX feedback.

    Each `data:` line is a JSON object with shape:
      {"event": "<event_name>", "thread_id": "...", "payload": {...}}

    Events emitted:
      * `thread_started`        — after thread_id resolution.
      * `node_update`           — one per node completion (router, retrieve_context,
                                   research/legal/comm/social, human_review, final_response).
      * `final_response`        — assistant message + active_route + pending_human_review.
      * `interrupt`             — emitted instead of final_response when the graph paused
                                   for human approval; client should call `/threads/{id}/resume`.
      * `error`                 — emitted on any uncaught exception. Generator still terminates.
      * `done`                  — last event, signals stream end.
    """
    thread_id = request.thread_id or str(uuid4())
    state = initial_state(
        request.message,
        thread_id=thread_id,
        user_id=user.user_id,
        doc_ids=request.doc_ids,
        case_id=request.case_id,
    )
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    return StreamingResponse(
        _chat_stream_events(state, config, thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _chat_stream_events(
    state: CognitiveState,
    config: dict[str, Any],
    thread_id: str,
) -> AsyncIterator[str]:
    queue: asyncio.Queue[Any] = asyncio.Queue()
    sentinel = object()
    loop = asyncio.get_running_loop()

    def _drain_graph() -> None:
        try:
            for chunk in _api_graph.stream(state, config=config, stream_mode="updates"):
                asyncio.run_coroutine_threadsafe(queue.put(chunk), loop).result()
        except Exception as exc:
            logger.warning(
                "chat_stream_graph_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            asyncio.run_coroutine_threadsafe(
                queue.put({"__stream_error__": exc}),
                loop,
            ).result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(sentinel), loop).result()

    drain_task = asyncio.create_task(asyncio.to_thread(_drain_graph))

    yield _sse({"event": "thread_started", "thread_id": thread_id})

    interrupted = False
    try:
        while True:
            chunk = await queue.get()
            if chunk is sentinel:
                break
            if isinstance(chunk, dict) and "__stream_error__" in chunk:
                raw = chunk["__stream_error__"]
                detail = (
                    _chat_stream_error_detail(raw) if isinstance(raw, BaseException) else str(raw)
                )
                yield _sse(
                    {
                        "event": "error",
                        "thread_id": thread_id,
                        "detail": detail,
                    }
                )
                continue
            if isinstance(chunk, dict) and "__interrupt__" in chunk:
                yield _sse(
                    {
                        "event": "interrupt",
                        "thread_id": thread_id,
                        "payload": _extract_interrupt_payload(chunk),
                    }
                )
                interrupted = True
                continue
            if isinstance(chunk, dict):
                for node_name, node_update in chunk.items():
                    yield _sse(
                        {
                            "event": "node_update",
                            "thread_id": thread_id,
                            "node": str(node_name),
                            "payload": _safe_json(node_update),
                        }
                    )

        if not interrupted:
            snapshot = _api_graph.get_state(config)
            if snapshot.values:
                state_view = cast_state(snapshot.values)
                response = _chat_response(thread_id, state_view)
                yield _sse(
                    {
                        "event": "final_response",
                        "thread_id": thread_id,
                        "message": response.message,
                        "route": response.route,
                        "pending_human_review": response.pending_human_review,
                    }
                )

        yield _sse({"event": "done", "thread_id": thread_id})
    finally:
        drain_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await drain_task


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(_safe_json(payload), ensure_ascii=False)}\n\n"


def _chat_stream_error_detail(exc: BaseException) -> str:
    """Avoid leaking stack internals to SSE clients in production."""
    if settings.environment == "production":
        return "internal_error"
    return f"{type(exc).__name__}: {exc}"


def _safe_json(value: Any) -> Any:
    return jsonable_encoder(value)


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ChatResponse:
    thread_id = request.thread_id or str(uuid4())
    raw_result = await asyncio.to_thread(
        _api_graph.invoke,
        initial_state(
            request.message,
            thread_id=thread_id,
            user_id=user.user_id,
            doc_ids=request.doc_ids,
            case_id=request.case_id,
        ),
        config={"configurable": {"thread_id": thread_id}},
    )
    return _chat_response_from_raw(thread_id, raw_result)


@app.get("/threads/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: str,
    user: AuthenticatedUser = _auth_dependency,
) -> ThreadResponse:
    del user
    snapshot = _api_graph.get_state({"configurable": {"thread_id": thread_id}})
    if not snapshot.values:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return ThreadResponse(thread_id=thread_id, values=_serialize_state(cast_state(snapshot.values)))


@app.post("/threads/{thread_id}/resume", response_model=ChatResponse)
async def resume_thread(
    thread_id: str,
    request: ResumeThreadRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ChatResponse:
    del user
    raw_result = await asyncio.to_thread(
        resume_graph,
        _api_graph,
        thread_id=thread_id,
        action=request.action,
        message=request.message,
    )
    return _chat_response_from_raw(thread_id, raw_result)


@app.post(
    "/documents/ingest",
    response_model=IngestDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_document(
    request: IngestDocumentRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> IngestDocumentResponse:
    try:
        document_path = str(resolve_ingest_document_path(request.document_path, settings))
    except IngestPathPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    async with session_scope() as session:
        job = Job(
            job_type="document_ingestion",
            status="queued",
            progress=0,
            metadata_json={"document_path": document_path, "requested_by": user.user_id},
        )
        session.add(job)
        await session.flush()
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="job_queued",
                status="queued",
                message="Document ingestion queued",
                metadata_json={"document_path": document_path},
            )
        )
        job_id = job.id

    ingest_pdf_task.apply_async(args=[document_path, str(job_id)], queue="ingestion")
    return IngestDocumentResponse(job_id=job_id, status="queued")


@app.post(
    "/deepagents/research",
    response_model=IngestDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_deepagent_research(
    request: DeepAgentResearchRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> IngestDocumentResponse:
    thread_id = request.thread_id or str(uuid4())
    task_id = str(uuid4())
    task_dict = {
        "task_id": task_id,
        "thread_id": thread_id,
        "user_id": user.user_id,
        "task_type": "research",
        "query": request.query,
        "web_allowed": request.web_allowed,
    }
    async with session_scope() as session:
        job = Job(
            job_type="deepagent_research",
            status="queued",
            progress=0,
            metadata_json={
                "task_id": task_id,
                "thread_id": thread_id,
                "requested_by": user.user_id,
            },
        )
        session.add(job)
        await session.flush()
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="job_queued",
                status="queued",
                message="DeepAgent research queued",
                metadata_json={"task_id": task_id, "thread_id": thread_id},
            )
        )
        job_id = job.id
    run_deepagent_task_async.apply_async(args=[task_dict, str(job_id)], queue="agent_longrun")
    return IngestDocumentResponse(job_id=job_id, status="queued")


@app.get("/sandbox/openshell/status", response_model=dict[str, Any])
async def openshell_status(
    user: AuthenticatedUser = _auth_dependency,
) -> dict[str, Any]:
    del user
    return await OpenShellAdapter().status()


@app.post(
    "/sandbox/openshell/run",
    response_model=OpenShellRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_openshell(
    request: OpenShellTask,
    user: AuthenticatedUser = _auth_dependency,
) -> OpenShellRunResponse:
    task = request.model_copy(update={"user_id": request.user_id or user.user_id})
    adapter = OpenShellAdapter()
    if not settings.enable_openshell_sandbox:
        result = await adapter.run_task(task)
        return OpenShellRunResponse(status=result.status, result=result)

    if requires_openshell_approval(task, settings):
        job_id, approval_id = await _create_openshell_approval_job(task, user.user_id)
        return OpenShellRunResponse(status="needs_approval", job_id=job_id, approval_id=approval_id)

    job_id = await _create_openshell_job(task, user.user_id)
    run_openshell_task_async.apply_async(
        args=[task.model_dump(mode="json"), str(job_id)],
        queue="agent_longrun",
    )
    return OpenShellRunResponse(status="queued", job_id=job_id)


@app.post(
    "/document-analysis/run",
    response_model=DocumentAnalysisRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_document_analysis(
    request: DocumentAnalysisTask,
    user: AuthenticatedUser = _auth_dependency,
) -> DocumentAnalysisRunResponse:
    task = request.model_copy(update={"user_id": request.user_id or user.user_id})
    job_id = await _create_document_analysis_job(task, user.user_id)
    run_document_analysis_task_async.apply_async(
        args=[task.model_dump(mode="json"), str(job_id)],
        queue="agent_longrun",
    )
    return DocumentAnalysisRunResponse(status="queued", task_id=task.task_id, job_id=job_id)


@app.get("/document-analysis/{task_id}", response_model=dict[str, Any])
async def get_document_analysis_result(
    task_id: str,
    user: AuthenticatedUser = _auth_dependency,
) -> dict[str, Any]:
    del user
    result = await DocumentAnalysisService().get_analysis_result(task_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document analysis result not found",
        )
    return {
        "task_id": result.task_id,
        "status": result.status,
        "generated_files": result.generated_files,
        "human_review_required": result.human_review_required,
        "warnings": result.warnings,
    }


@app.get("/document-analysis/{task_id}/report", response_class=PlainTextResponse)
async def get_document_analysis_report(
    task_id: str,
    user: AuthenticatedUser = _auth_dependency,
) -> PlainTextResponse:
    del user
    path = _analysis_file_path(task_id, "report.md")
    return PlainTextResponse(
        path.read_text(encoding="utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@app.get("/document-analysis/{task_id}/download/json")
async def download_document_analysis_json(
    task_id: str,
    user: AuthenticatedUser = _auth_dependency,
) -> FileResponse:
    del user
    return _download_analysis_file(task_id, "result.json", "application/json")


@app.get("/document-analysis/{task_id}/download/markdown")
async def download_document_analysis_markdown(
    task_id: str,
    user: AuthenticatedUser = _auth_dependency,
) -> FileResponse:
    del user
    return _download_analysis_file(task_id, "report.md", "text/markdown")


@app.get("/document-analysis/{task_id}/download/docx")
async def download_document_analysis_docx(
    task_id: str,
    user: AuthenticatedUser = _auth_dependency,
) -> FileResponse:
    del user
    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return _download_analysis_file(task_id, "report.docx", media_type)


_ANALYSIS_CSV_FILES = {
    "evidence_matrix": "evidence_matrix.csv",
    "timeline": "timeline.csv",
    "contradictions": "contradictions.csv",
}


@app.get("/document-analysis/{task_id}/download/csv/{kind}")
async def download_document_analysis_csv(
    task_id: str,
    kind: str,
    user: AuthenticatedUser = _auth_dependency,
) -> FileResponse:
    del user
    filename = _ANALYSIS_CSV_FILES.get(kind)
    if filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown CSV kind: {kind}",
        )
    return _download_analysis_file(task_id, filename, "text/csv")


@app.get("/deepagents/skills", response_model=list[dict[str, Any]])
async def list_deepagent_skills(
    user: AuthenticatedUser = _auth_dependency,
) -> list[dict[str, Any]]:
    registry = DeepAgentSkillsRegistry()
    skills = registry.discover_core_skills() + registry.discover_user_skills(user.user_id)
    return [skill.model_dump() for skill in skills if skill.enabled]


@app.get("/deepagents/skills/{name}", response_model=SkillDetailResponse)
async def get_deepagent_skill(
    name: str,
    user: AuthenticatedUser = _auth_dependency,
) -> SkillDetailResponse:
    """Return the metadata + raw `SKILL.md` content for one skill."""
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid skill name")
    registry = DeepAgentSkillsRegistry()
    skills = registry.discover_core_skills() + registry.discover_user_skills(user.user_id)
    for skill in skills:
        if skill.name == name and skill.enabled:
            content_path = Path(skill.path) / "SKILL.md"
            try:
                content = content_path.read_text(encoding="utf-8")
            except OSError:
                content = ""
            data = skill.model_dump()
            return SkillDetailResponse(
                **{
                    "name": data["name"],
                    "description": data["description"],
                    "version": data["version"],
                    "risk_level": data["risk_level"],
                    "allowed_tools": data["allowed_tools"],
                    "path": data["path"],
                    "enabled": data["enabled"],
                    "content": content,
                }
            )
    raise HTTPException(status_code=404, detail="Skill not found")


@app.get("/documents/{document_id}/chunks", response_model=list[DocumentChunkResponse])
async def list_document_chunks(
    document_id: UUID,
    limit: int = 50,
    user: AuthenticatedUser = _auth_dependency,
) -> list[DocumentChunkResponse]:
    del user
    bounded = max(1, min(limit, 500))
    async with session_scope() as session:
        result = await session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(bounded)
        )
        return [
            DocumentChunkResponse(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                sha256=chunk.sha256,
                text=chunk.text,
            )
            for chunk in result.scalars().all()
        ]


@app.get("/threads", response_model=list[ThreadSummaryResponse])
async def list_recent_threads(
    limit: int = 30,
    user: AuthenticatedUser = _auth_dependency,
) -> list[ThreadSummaryResponse]:
    """List recent LangGraph threads.

    Combines two signals:
      1. The `langgraph` `checkpoints` table (if `PostgresSaver` is active) —
         this captures every chat thread, including ones that never enqueued a
         Celery job.
      2. `jobs.metadata_json.thread_id` — captures DeepAgent / DocumentAnalysis
         tasks even when the in-memory checkpointer is in use.

    Results are deduped by `thread_id` and sorted newest first.
    """
    del user
    bounded = max(1, min(limit, 200))
    seen: dict[str, ThreadSummaryResponse] = {}

    # 1) langgraph checkpoint table (best-effort, table may not exist yet)
    try:
        async with session_scope() as session:
            from sqlalchemy import text as sql_text  # local import: optional path

            checkpoint_rows = await session.execute(
                sql_text(
                    """
                    SELECT thread_id, MAX(checkpoint_id) AS last_id
                    FROM checkpoints
                    GROUP BY thread_id
                    ORDER BY last_id DESC
                    LIMIT :lim
                    """
                ),
                {"lim": bounded},
            )
            for row in checkpoint_rows:
                thread_id = str(row[0])
                if thread_id and thread_id not in seen:
                    seen[thread_id] = ThreadSummaryResponse(
                        thread_id=thread_id,
                        last_active_at=None,
                        last_route="checkpoint",
                        last_message_preview=None,
                    )
    except Exception as exc:
        logger.debug(
            "checkpoint_thread_listing_unavailable",
            error_type=type(exc).__name__,
            error=str(exc),
        )

    # 2) job metadata
    async with session_scope() as session:
        result = await session.execute(
            select(Job).order_by(desc(Job.updated_at)).limit(bounded * 4)
        )
        for job in result.scalars().all():
            md = job.metadata_json or {}
            raw_thread_id = md.get("thread_id")
            if not isinstance(raw_thread_id, str):
                continue
            thread_id_str: str = raw_thread_id
            existing = seen.get(thread_id_str)
            if existing is None or existing.last_active_at is None:
                seen[thread_id_str] = ThreadSummaryResponse(
                    thread_id=thread_id_str,
                    last_active_at=job.updated_at,
                    last_route=str(md.get("last_route") or md.get("task_type") or job.job_type),
                    last_message_preview=None,
                )

    # newest first; threads sourced only from checkpoints (no timestamp) go last
    items = sorted(
        seen.values(),
        key=lambda summary: summary.last_active_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    return items[:bounded]


@app.get("/deepagents/memory", response_model=list[dict[str, Any]])
async def list_deepagent_memory(
    scope: DeepAgentMemoryScope = "user",
    user: AuthenticatedUser = _auth_dependency,
) -> list[dict[str, Any]]:
    items = await DeepAgentMemoryService().list_memory(scope, user_id=user.user_id)
    return [item.model_dump(mode="json") for item in items]


@app.get("/deepagents/memory/proposals", response_model=list[dict[str, Any]])
async def list_deepagent_memory_proposals(
    user: AuthenticatedUser = _auth_dependency,
) -> list[dict[str, Any]]:
    del user
    return await DeepAgentMemoryService().list_memory_proposals()


@app.post("/deepagents/memory/proposals/{proposal_id}/approve", response_model=dict[str, Any])
async def approve_deepagent_memory_proposal(
    proposal_id: str,
    user: AuthenticatedUser = _admin_auth_dependency,
) -> dict[str, Any]:
    """Admin-gated: memory mutations permanently shape future agent runs."""
    item = await DeepAgentMemoryService().approve_memory_proposal(proposal_id, user.user_id)
    return item.model_dump(mode="json")


@app.post(
    "/deepagents/memory/proposals/{proposal_id}/reject", status_code=status.HTTP_204_NO_CONTENT
)
async def reject_deepagent_memory_proposal(
    proposal_id: str,
    request: MemoryRejectRequest,
    user: AuthenticatedUser = _admin_auth_dependency,
) -> None:
    """Admin-gated counterpart of approve."""
    await DeepAgentMemoryService().reject_memory_proposal(
        proposal_id,
        user.user_id,
        request.reason,
    )


@app.post("/deepagents/memory/export", response_model=dict[str, Any])
async def export_deepagent_memory(
    request: MemoryExportRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> dict[str, Any]:
    user_id = request.user_id or user.user_id
    return await DeepAgentMemoryService().export_memory(
        request.scope,
        user_id=user_id,
        case_id=request.case_id,
    )


@app.post("/deepagents/memory/episodic", response_model=dict[str, Any])
async def append_episodic_memory(
    request: EpisodicMemoryRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> dict[str, Any]:
    """Persists a short-lived episodic memory tied to this user without a proposal round-trip."""
    try:
        item = await DeepAgentMemoryService().record_episodic_memory(
            user_id=user.user_id,
            summary=request.summary,
            agent_name=request.agent_name,
            thread_id=request.thread_id,
            case_id=request.case_id,
            sensitivity=request.sensitivity,
        )
    except DeepAgentMemoryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return item.model_dump(mode="json")


@app.get("/assist/tasks", response_model=list[PersonalTaskView])
async def list_assist_tasks(
    user: AuthenticatedUser = _auth_dependency,
    statuses: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 80,
) -> list[PersonalTaskView]:
    try:
        svc = PersonalAssistService()
        return await svc.list_tasks(user.user_id, statuses=statuses, limit=limit)
    except PersonalAssistDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@app.post("/assist/tasks", response_model=PersonalTaskView, status_code=status.HTTP_201_CREATED)
async def create_assist_task(
    body: PersonalTaskCreate,
    user: AuthenticatedUser = _auth_dependency,
) -> PersonalTaskView:
    try:
        return await PersonalAssistService().create_task(user.user_id, body)
    except PersonalAssistDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@app.get("/assist/tasks/{task_id}", response_model=PersonalTaskView)
async def get_assist_task(
    task_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> PersonalTaskView:
    try:
        row = await PersonalAssistService().get_task(user.user_id, task_id)
    except PersonalAssistDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return row


@app.patch("/assist/tasks/{task_id}", response_model=PersonalTaskView)
async def patch_assist_task(
    task_id: UUID,
    body: PersonalTaskUpdate,
    user: AuthenticatedUser = _auth_dependency,
) -> PersonalTaskView:
    try:
        row = await PersonalAssistService().update_task(user.user_id, task_id, body)
    except PersonalAssistDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return row


@app.delete("/assist/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assist_task(
    task_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> None:
    try:
        ok = await PersonalAssistService().delete_task(user.user_id, task_id)
    except PersonalAssistDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")


@app.get("/assist/notes", response_model=list[PersonalNoteView])
async def list_assist_notes(
    user: AuthenticatedUser = _auth_dependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[PersonalNoteView]:
    try:
        return await PersonalAssistService().list_notes(user.user_id, limit=limit)
    except PersonalAssistDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@app.post("/assist/notes", response_model=PersonalNoteView, status_code=status.HTTP_201_CREATED)
async def create_assist_note(
    body: PersonalNoteCreate,
    user: AuthenticatedUser = _auth_dependency,
) -> PersonalNoteView:
    try:
        return await PersonalAssistService().create_note(user.user_id, body)
    except PersonalAssistDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@app.get("/assist/notes/search", response_model=list[PersonalNoteSearchHit])
async def search_assist_notes(
    user: AuthenticatedUser = _auth_dependency,
    q: Annotated[str, Query(max_length=2000)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[PersonalNoteSearchHit]:
    # Declared before `/assist/notes/{note_id}` so the literal path wins the
    # route match (the `{note_id}` route is UUID-typed and would 422 on "search").
    # An empty/whitespace `q` yields an empty list (handled in the service).
    try:
        return await PersonalAssistService().search_notes(user.user_id, q, limit=limit)
    except PersonalAssistDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@app.get("/assist/notes/{note_id}", response_model=PersonalNoteView)
async def get_assist_note(
    note_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> PersonalNoteView:
    try:
        row = await PersonalAssistService().get_note(user.user_id, note_id)
    except PersonalAssistDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return row


@app.patch("/assist/notes/{note_id}", response_model=PersonalNoteView)
async def patch_assist_note(
    note_id: UUID,
    body: PersonalNoteUpdate,
    user: AuthenticatedUser = _auth_dependency,
) -> PersonalNoteView:
    try:
        row = await PersonalAssistService().update_note(user.user_id, note_id, body)
    except PersonalAssistDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return row


@app.delete("/assist/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assist_note(
    note_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> None:
    try:
        ok = await PersonalAssistService().delete_note(user.user_id, note_id)
    except PersonalAssistDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> JobResponse:
    del user
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return _job_response(job)


@app.get("/jobs/{job_id}/events", response_model=list[JobEventResponse])
async def get_job_events(
    job_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> list[JobEventResponse]:
    del user
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        result = await session.execute(
            select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.created_at)
        )
        return [_job_event_response(event) for event in result.scalars().all()]


@app.get("/approvals", response_model=list[ApprovalResponse])
async def list_approvals(
    user: AuthenticatedUser = _auth_dependency,
) -> list[ApprovalResponse]:
    del user
    async with session_scope() as session:
        result = await session.execute(
            select(HumanApproval).order_by(HumanApproval.created_at.desc()).limit(100)
        )
        return [_approval_response(approval) for approval in result.scalars().all()]


@app.post(
    "/approvals/{approval_id}/approve",
    response_model=ApprovalResponse,
    dependencies=[_RL_APPROVAL_DECISION],
)
async def approve_approval(
    approval_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> ApprovalResponse:
    return await _decide_approval(
        approval_id,
        status_value="approved",
        approver_user_id=user.user_id,
    )


@app.post(
    "/approvals/{approval_id}/reject",
    response_model=ApprovalResponse,
    dependencies=[_RL_APPROVAL_DECISION],
)
async def reject_approval(
    approval_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> ApprovalResponse:
    return await _decide_approval(
        approval_id,
        status_value="rejected",
        approver_user_id=user.user_id,
    )


@app.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    job_type: str | None = None,
    job_status: str | None = None,
    limit: int = 50,
    user: AuthenticatedUser = _auth_dependency,
) -> list[JobResponse]:
    """Recent jobs, newest first. Filter by `job_type` and/or `status`."""
    del user
    bounded_limit = max(1, min(limit, 200))
    async with session_scope() as session:
        stmt = select(Job).order_by(desc(Job.created_at)).limit(bounded_limit)
        if job_type:
            stmt = stmt.where(Job.job_type == job_type)
        if job_status:
            stmt = stmt.where(Job.status == job_status)
        result = await session.execute(stmt)
        return [_job_response(job) for job in result.scalars().all()]


@app.post("/jobs/{job_id}/cancel", response_model=JobCancelResponse)
async def cancel_job(
    job_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> JobCancelResponse:
    """Mark a job as cancelled and append an audit event.

    This does *not* kill the underlying Celery task — it is an idempotent
    state transition for the operator dashboard. Active workers will keep
    running their current iteration but the cancel flag will be visible to
    any code that polls the job state.
    """
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        if job.status in {"completed", "failed", "cancelled"}:
            return JobCancelResponse(id=job.id, status=job.status)
        job.status = "cancelled"
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="job_cancelled",
                status="cancelled",
                message="Cancelled from operator dashboard",
                metadata_json={"by_user": user.user_id},
            )
        )
        return JobCancelResponse(id=job.id, status=job.status)


@app.get("/documents", response_model=list[DocumentSummaryResponse])
async def list_documents(
    limit: int = 50,
    user: AuthenticatedUser = _auth_dependency,
) -> list[DocumentSummaryResponse]:
    del user
    bounded_limit = max(1, min(limit, 200))
    async with session_scope() as session:
        page_counts = (
            select(
                Document.id.label("doc_id"),
                func.count(DocumentChunk.id).label("chunk_count"),
            )
            .join(DocumentChunk, DocumentChunk.document_id == Document.id, isouter=True)
            .group_by(Document.id)
            .subquery()
        )
        stmt = (
            select(Document, page_counts.c.chunk_count)
            .join(page_counts, page_counts.c.doc_id == Document.id, isouter=True)
            .order_by(desc(Document.created_at))
            .limit(bounded_limit)
        )
        result = await session.execute(stmt)
        rows = result.all()
        return [
            DocumentSummaryResponse(
                id=document.id,
                title=document.title,
                source_path=document.source_path,
                sha256=document.sha256,
                status=document.status,
                page_count=int(document.metadata_json.get("page_count", 0) or 0),
                chunk_count=int(chunk_count or 0),
                created_at=document.created_at,
                updated_at=document.updated_at,
            )
            for document, chunk_count in rows
        ]


@app.get("/audit/events", response_model=list[AuditEventResponse])
async def list_audit_events(
    limit: int = 100,
    user: AuthenticatedUser = _auth_dependency,
) -> list[AuditEventResponse]:
    del user
    bounded_limit = max(1, min(limit, 500))
    async with session_scope() as session:
        result = await session.execute(
            select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(bounded_limit)
        )
        return [
            AuditEventResponse(
                id=event.id,
                actor_id=event.actor_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                metadata_json=event.metadata_json,
                created_at=event.created_at,
            )
            for event in result.scalars().all()
        ]


@app.get("/knowledge/stats", response_model=KnowledgeStatsResponse)
async def knowledge_stats(
    user: AuthenticatedUser = _auth_dependency,
) -> KnowledgeStatsResponse:
    del user
    async with session_scope() as session:
        documents = await session.scalar(select(func.count(Document.id))) or 0
        chunks = await session.scalar(select(func.count(DocumentChunk.id))) or 0
        jobs_running = (
            await session.scalar(
                select(func.count(Job.id)).where(Job.status.in_(("queued", "running")))
            )
            or 0
        )
        jobs_completed = (
            await session.scalar(select(func.count(Job.id)).where(Job.status == "completed")) or 0
        )
        jobs_failed = (
            await session.scalar(select(func.count(Job.id)).where(Job.status == "failed")) or 0
        )
        approvals_pending = (
            await session.scalar(
                select(func.count(HumanApproval.id)).where(HumanApproval.status == "pending")
            )
            or 0
        )
        # documents.page_count lives in metadata_json; sum it via JSONB cast.
        pages_result = await session.execute(
            select(Document.metadata_json).where(Document.metadata_json.isnot(None))
        )
        pages = sum(int((row[0] or {}).get("page_count", 0) or 0) for row in pages_result)
    return KnowledgeStatsResponse(
        documents=int(documents),
        pages=int(pages),
        chunks=int(chunks),
        jobs_running=int(jobs_running),
        jobs_completed=int(jobs_completed),
        jobs_failed=int(jobs_failed),
        approvals_pending=int(approvals_pending),
    )


@app.get("/config/public", response_model=PublicConfigResponse)
async def public_config(
    user: AuthenticatedUser = _auth_dependency,
) -> PublicConfigResponse:
    """Non-secret configuration view for the operator panel."""
    del user
    web_providers = configured_web_search_provider_names(settings)
    return PublicConfigResponse(
        environment=settings.environment,
        web_search_enabled=settings.web_search_enabled,
        tools_readonly_mode=settings.tools_readonly_mode,
        require_human_approval_for_external_actions=(
            settings.require_human_approval_for_external_actions
        ),
        enable_browser_automation=settings.enable_browser_automation,
        enable_computer_actions=settings.enable_computer_actions,
        enable_email_send=settings.enable_email_send,
        enable_social_posting=settings.enable_social_posting,
        enable_document_generation=settings.enable_document_generation,
        enable_research_orchestrator=settings.enable_research_orchestrator,
        research_persistence_backend=settings.research_persistence_backend,
        enable_openharness_research=settings.enable_openharness_research,
        openharness_research_pipeline=settings.openharness_research_pipeline,
        openharness_toolkit_preset=settings.openharness_toolkit_preset,
        openharness_workspace_mode=settings.openharness_workspace_mode,
        openharness_web_tools=settings.openharness_web_tools,
        enable_openshell_sandbox=settings.enable_openshell_sandbox,
        enable_personal_assistant_api=settings.enable_personal_assistant_api,
        enable_personal_reminder_delivery=settings.enable_personal_reminder_delivery,
        enable_maps_routing=settings.enable_maps_routing,
        maps_default_travel_mode=settings.maps_default_travel_mode,
        enable_google_calendar=settings.enable_google_calendar,
        enable_google_calendar_write=settings.enable_google_calendar_write,
        enable_google_drive=settings.enable_google_drive,
        enable_google_drive_write=settings.enable_google_drive_write,
        google_drive_upload_max_bytes=settings.google_drive_upload_max_bytes,
        google_drive_deliverables_folder_name=settings.google_drive_deliverables_folder_name,
        telegram_enabled=settings.telegram_enabled,
        telegram_gmail_digest_enabled=settings.telegram_gmail_digest_enabled,
        langsmith_tracing=settings.langsmith_tracing,
        langsmith_endpoints_require_admin=settings.langsmith_endpoints_require_admin,
        browser_automation_provider=settings.browser_automation_provider,
        browser_headless_default=settings.browser_headless_default,
        browser_allow_headed=settings.browser_allow_headed,
        browser_allow_vision=settings.browser_allow_vision,
        browser_allowed_domains_count=len(settings.browser_allowed_domains),
        computer_allowed_roots_count=len(settings.computer_allowed_roots),
        computer_organize_dry_run_only=settings.computer_organize_dry_run_only,
        document_asset_roots_count=len(settings.document_asset_roots),
        gmail_read_enabled=settings.gmail_read_enabled,
        gmail_send_enabled=settings.gmail_send_enabled,
        mail_enabled=settings.mail_enabled,
        mail_godaddy_enabled=settings.mail_godaddy_enabled,
        mail_require_approval_for_send=settings.mail_require_approval_for_send,
        mail_poll_interval_seconds=settings.mail_poll_interval_seconds,
        mail_fetch_max_per_folder=settings.mail_fetch_max_per_folder,
        mail_imap_timeout_seconds=settings.mail_imap_timeout_seconds,
        mail_smtp_timeout_seconds=settings.mail_smtp_timeout_seconds,
        mail_gmail_label=settings.mail_gmail_label,
        godaddy_enabled=settings.godaddy_enabled,
        godaddy_dns_dry_run_only=settings.godaddy_dns_dry_run_only,
        godaddy_allow_production_writes=settings.godaddy_allow_production_writes,
        godaddy_allowed_domains_count=len(settings.godaddy_allowed_domains),
        reranker_enabled=settings.reranker_enabled,
        reranker_model=settings.reranker_model,
        deepagents_enable_skills=settings.deepagents_enable_skills,
        deepagents_enable_subagents=settings.deepagents_enable_subagents,
        deepagents_enable_memory=settings.deepagents_enable_memory,
        deepagents_memory_require_approval=settings.deepagents_memory_require_approval,
        embeddings_provider=settings.embeddings_provider,
        embeddings_model=settings.embeddings_model,
        embeddings_dimension=settings.embeddings_dimension,
        embeddings_key_pool_size=len(settings.embeddings_api_keys),
        primary_llm_provider=settings.primary_llm_provider,
        primary_llm_model=settings.primary_llm_model,
        web_search_providers=web_providers,
    )


@app.get("/actions/capabilities", response_model=list[ActionCapabilityStatus])
async def action_capabilities(
    user: AuthenticatedUser = _auth_dependency,
) -> list[ActionCapabilityStatus]:
    """Current external-action posture without exposing secrets."""
    del user
    return [
        BrowserActionService().status(),
        ComputerActionService().status(),
        DocumentActionService().status(),
        GmailActionService().status(),
        GoDaddyActionService().status(),
        _maps_capability(),
        _calendar_capability(),
        _drive_capability(),
    ]


def _maps_capability() -> ActionCapabilityStatus:
    current = MapsService().status()
    return ActionCapabilityStatus(
        name="maps",
        status=current.status,
        summary="Google Maps geocoding and traffic-aware routing; read-only.",
        requires_approval=False,
        dry_run_only=True,
        reasons=[current.reason] if current.reason else [],
        metadata={"default_travel_mode": current.default_travel_mode},
    )


def _calendar_capability() -> ActionCapabilityStatus:
    current = CalendarService().status()
    return ActionCapabilityStatus(
        name="google_calendar",
        status=current.status,
        summary="Google Calendar event listing plus approved event creation.",
        requires_approval=current.write_enabled,
        dry_run_only=not current.write_enabled,
        reasons=[current.reason] if current.reason else [],
        metadata={"calendar_id": current.calendar_id, "write_enabled": current.write_enabled},
    )


def _drive_capability() -> ActionCapabilityStatus:
    current = DriveService().status()
    return ActionCapabilityStatus(
        name="google_drive",
        status=current.status,
        summary="Google Drive search plus approved uploads to Cognitive OS deliverables.",
        requires_approval=current.write_enabled,
        dry_run_only=not current.write_enabled,
        reasons=[current.reason] if current.reason else [],
        metadata={
            "write_enabled": current.write_enabled,
            "upload_max_bytes": current.upload_max_bytes,
            "deliverables_folder_name": current.deliverables_folder_name,
        },
    )


@app.post("/actions/browser/validate", response_model=BrowserNavigationValidation)
async def validate_browser_navigation(
    request: BrowserNavigationRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> BrowserNavigationValidation:
    del user
    return BrowserActionService().validate_navigation(request)


@app.post("/actions/computer/organize/preview", response_model=ComputerOrganizePlan)
async def preview_computer_organize(
    request: ComputerOrganizeRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ComputerOrganizePlan:
    del user
    return ComputerActionService().build_organize_plan(request)


@app.post(
    "/actions/computer/organize/request",
    response_model=ActionRequestView,
    dependencies=[_RL_ACTION_REQUEST_CREATE],
)
async def request_computer_organize(
    request: ComputerOrganizeRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ActionRequestView:
    return await ActionRequestService().create_computer_organize_request(
        request,
        requested_by=user.user_id,
    )


@app.post("/actions/computer/inventory", response_model=ComputerInventoryResult)
async def create_computer_inventory(
    request: ComputerInventoryRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ComputerInventoryResult:
    del user
    return ComputerActionService().build_inventory(request)


@app.get("/actions/requests", response_model=list[ActionRequestView])
async def list_action_requests(
    user: AuthenticatedUser = _auth_dependency,
    limit: int = 50,
    action_type: ActionType | None = None,
    request_status: Annotated[
        ActionRequestStatus | None,
        Query(alias="status"),
    ] = None,
) -> list[ActionRequestView]:
    del user
    return await ActionRequestService().list_action_requests(
        limit=limit,
        action_type=action_type,
        status=request_status,
    )


@app.get("/actions/requests/{action_request_id}", response_model=ActionRequestView)
async def get_action_request(
    action_request_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> ActionRequestView:
    del user
    action_request = await ActionRequestService().get_action_request(action_request_id)
    if action_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action request not found",
        )
    return action_request


@app.post(
    "/actions/requests/{action_request_id}/dispatch",
    response_model=ActionDispatchResponse,
    dependencies=[_RL_ACTION_DISPATCH],
)
async def dispatch_action_request(
    action_request_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> ActionDispatchResponse:
    del user
    try:
        action_request = await ActionRequestService().queue_approved_action_request(
            action_request_id
        )
    except ActionRequestError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if action_request.job_id is None:
        return ActionDispatchResponse(
            action_request=action_request,
            dispatched=False,
            reason="Action request has no job to dispatch.",
        )
    if action_request.status != "queued":
        return ActionDispatchResponse(
            action_request=action_request,
            dispatched=False,
            reason=f"Action request status is {action_request.status}; nothing queued.",
        )
    run_action_request_task_async.apply_async(
        args=[str(action_request.id), str(action_request.job_id)],
        queue="agent_longrun",
    )
    return ActionDispatchResponse(action_request=action_request, dispatched=True)


@app.get("/actions/requests/{action_request_id}/workflow", response_model=WorkflowDocument)
async def export_action_request_workflow(
    action_request_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> WorkflowDocument:
    """Export an ActionRequest as a portable `workflow.v1` document.

    The export uses the redacted payload — encrypted secrets stay server-side.
    Operators can edit the document and re-submit via
    `POST /actions/requests/from-workflow` to clone the plan.
    """
    try:
        document = await ActionRequestService().export_workflow(
            action_request_id,
            exported_by=user.user_id,
        )
    except ActionRequestError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action request not found",
        )
    return document


@app.post(
    "/actions/requests/from-workflow",
    response_model=WorkflowImportResult,
    dependencies=[_RL_ACTION_REQUEST_CREATE],
)
async def create_action_request_from_workflow(
    document: WorkflowDocument,
    user: AuthenticatedUser = _auth_dependency,
) -> WorkflowImportResult:
    """Re-create an ActionRequest from a `workflow.v1` document.

    The importer routes the document through the same `create_*_request`
    carrils the standard endpoints use, so allow-lists, approval gating,
    idempotency dedup and payload encryption all apply unchanged.
    """
    try:
        view = await ActionRequestService().create_from_workflow(
            document,
            requested_by=user.user_id,
        )
    except ActionRequestError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return WorkflowImportResult(
        action_request=view,
        dry_run=False,
        notes=document.notes,
    )


@app.get("/actions/gmail/status", response_model=ActionCapabilityStatus)
async def gmail_status(
    user: AuthenticatedUser = _auth_dependency,
) -> ActionCapabilityStatus:
    del user
    return GmailActionService().status()


@app.post("/actions/gmail/query/preview", response_model=GmailQueryPreview)
async def preview_gmail_query(
    request: GmailQueryPreviewRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> GmailQueryPreview:
    del user
    return GmailActionService().preview_query(request)


_gmail_digest_reader: GmailReader | None = None


def get_gmail_digest_reader() -> GmailReader | None:
    if _gmail_digest_reader is not None:
        return _gmail_digest_reader
    if settings.gmail_read_enabled:
        return GmailRestReader.from_settings(settings)
    return _gmail_digest_reader


@app.post("/actions/gmail/digest/preview", response_model=GmailDigestPreview)
async def preview_gmail_digest(
    request: GmailDigestRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> GmailDigestPreview:
    del user
    return GmailDigestService(reader=get_gmail_digest_reader()).build_preview(request)


@app.get("/actions/maps/status", response_model=MapsStatus)
async def maps_status(user: AuthenticatedUser = _auth_dependency) -> MapsStatus:
    del user
    return MapsService().status()


@app.post("/actions/maps/geocode", response_model=GeocodeResult)
async def maps_geocode(
    request: GeocodeRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> GeocodeResult:
    del user
    try:
        return await asyncio.to_thread(MapsService().geocode, request.address)
    except MapsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@app.post("/actions/maps/route", response_model=RoutePlan)
async def maps_route(
    request: RouteRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> RoutePlan:
    del user
    try:
        return await asyncio.to_thread(
            lambda: MapsService().plan_route(
                origin=request.origin,
                destination=request.destination,
                intermediates=request.intermediates,
                travel_mode=request.travel_mode,
                traffic_aware=request.traffic_aware,
                departure_time=request.departure_time,
            )
        )
    except MapsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@app.get("/voice/status", response_model=VoiceStatus)
async def voice_status(user: AuthenticatedUser = _auth_dependency) -> VoiceStatus:
    del user
    return VoiceService().status()


@app.post("/voice/transcribe", response_model=TranscriptionResult)
async def voice_transcribe(
    file: Annotated[UploadFile, File()],
    user: AuthenticatedUser = _auth_dependency,
) -> TranscriptionResult:
    del user
    audio = await file.read()
    content_type = file.content_type or "application/octet-stream"
    try:
        return await asyncio.to_thread(
            lambda: VoiceService().transcribe(audio, content_type=content_type)
        )
    except VoiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post("/voice/speak")
async def voice_speak(
    request: SpeakRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> Response:
    del user
    try:
        result = await asyncio.to_thread(
            lambda: VoiceService().synthesize(
                request.text,
                voice_id=request.voice_id,
                model=request.model,
            )
        )
    except VoiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return Response(
        content=result.audio,
        media_type=result.media_type,
        headers={"X-Voice-Model": result.model, "X-Voice-Id": result.voice_id},
    )


@app.get("/actions/calendar/status", response_model=CalendarStatus)
async def calendar_status(user: AuthenticatedUser = _auth_dependency) -> CalendarStatus:
    del user
    return CalendarService().status()


@app.post("/actions/calendar/events", response_model=list[CalendarEvent])
async def calendar_events(
    request: ListEventsRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> list[CalendarEvent]:
    del user
    try:
        return await asyncio.to_thread(CalendarService().list_events, request)
    except CalendarError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post("/actions/calendar/events/create", response_model=EventCreatePreview)
async def calendar_events_create(
    request: EventCreateRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> EventCreatePreview:
    """Preview-only Calendar create surface.

    Real writes must use `/actions/calendar/events/request`, so every mutation
    is backed by `ActionRequest`, `HumanApproval`, Celery dispatch and audit.
    """
    if not request.dry_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Direct Calendar writes are disabled; create an ActionRequest via "
                "/actions/calendar/events/request."
            ),
        )
    try:
        return await asyncio.to_thread(
            lambda: CalendarService().create_event(request, requested_by=user.user_id)
        )
    except CalendarError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post(
    "/actions/calendar/events/request",
    response_model=ActionRequestView,
    dependencies=[_RL_ACTION_REQUEST_CREATE],
)
async def calendar_events_request(
    request: EventCreateRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ActionRequestView:
    return await ActionRequestService().create_calendar_event_request(
        request,
        requested_by=user.user_id,
    )


@app.get("/actions/drive/status", response_model=DriveStatus)
async def drive_status(user: AuthenticatedUser = _auth_dependency) -> DriveStatus:
    del user
    return DriveService().status()


@app.post("/actions/drive/files", response_model=list[DriveFile])
async def drive_files(
    request: DriveSearchRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> list[DriveFile]:
    del user
    try:
        return await asyncio.to_thread(DriveService().list_files, request)
    except DriveError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.get("/actions/drive/files/{file_id}", response_model=DriveFile)
async def drive_get_file(
    file_id: str,
    user: AuthenticatedUser = _auth_dependency,
) -> DriveFile:
    del user
    try:
        return await asyncio.to_thread(DriveService().get_file, file_id)
    except DriveError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post("/actions/drive/files/upload", response_model=DriveUploadPreview)
async def drive_upload_file(
    request: DriveUploadRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> DriveUploadPreview:
    """Preview-only Drive upload surface.

    Real uploads must use `/actions/drive/files/upload/request`, so every file
    mutation is backed by `ActionRequest`, `HumanApproval`, Celery dispatch and audit.
    """
    if not request.dry_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Direct Drive uploads are disabled; create an ActionRequest via "
                "/actions/drive/files/upload/request."
            ),
        )
    try:
        return await asyncio.to_thread(
            lambda: DriveService().upload_file(request, requested_by=user.user_id)
        )
    except DriveError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post("/actions/drive/folders/ensure", response_model=DriveFolderPreview)
async def drive_ensure_folder(
    request: DriveFolderRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> DriveFolderPreview:
    if not request.dry_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Direct Drive folder writes are disabled; approved Drive uploads "
                "ensure the deliverables folder during execution."
            ),
        )
    try:
        return await asyncio.to_thread(
            lambda: DriveService().ensure_deliverables_folder(request, requested_by=user.user_id)
        )
    except DriveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@app.post(
    "/actions/drive/files/upload/request",
    response_model=ActionRequestView,
    dependencies=[_RL_ACTION_REQUEST_CREATE],
)
async def drive_upload_file_request(
    request: DriveUploadRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ActionRequestView:
    return await ActionRequestService().create_drive_upload_request(
        request,
        requested_by=user.user_id,
    )


@app.get("/actions/webbridge/status", response_model=WebBridgeStatus)
async def webbridge_status(user: AuthenticatedUser = _auth_dependency) -> WebBridgeStatus:
    del user
    return await asyncio.to_thread(KimiWebBridgeService().status)


def _webbridge_call(
    fn: Any,
    *args: Any,
    **kwargs: Any,
) -> WebBridgeCallResult:
    try:
        result = fn(*args, **kwargs)
    except KimiWebBridgeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    if not isinstance(result, WebBridgeCallResult):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WebBridge service returned an unexpected payload type.",
        )
    return result


@app.post("/actions/webbridge/navigate", response_model=WebBridgeCallResult)
async def webbridge_navigate(
    request: NavigateRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> WebBridgeCallResult:
    return await asyncio.to_thread(
        lambda: _webbridge_call(KimiWebBridgeService().navigate, request, requested_by=user.user_id)
    )


@app.post("/actions/webbridge/snapshot", response_model=WebBridgeCallResult)
async def webbridge_snapshot(
    request: SnapshotRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> WebBridgeCallResult:
    return await asyncio.to_thread(
        lambda: _webbridge_call(KimiWebBridgeService().snapshot, request, requested_by=user.user_id)
    )


@app.post("/actions/webbridge/screenshot", response_model=WebBridgeCallResult)
async def webbridge_screenshot(
    request: ScreenshotRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> WebBridgeCallResult:
    return await asyncio.to_thread(
        lambda: _webbridge_call(
            KimiWebBridgeService().screenshot, request, requested_by=user.user_id
        )
    )


@app.post("/actions/webbridge/click", response_model=WebBridgeCallResult)
async def webbridge_click(
    request: ClickRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> WebBridgeCallResult:
    return await asyncio.to_thread(
        lambda: _webbridge_call(KimiWebBridgeService().click, request, requested_by=user.user_id)
    )


@app.post("/actions/webbridge/fill", response_model=WebBridgeCallResult)
async def webbridge_fill(
    request: FillRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> WebBridgeCallResult:
    return await asyncio.to_thread(
        lambda: _webbridge_call(KimiWebBridgeService().fill, request, requested_by=user.user_id)
    )


@app.post("/actions/webbridge/evaluate", response_model=WebBridgeCallResult)
async def webbridge_evaluate(
    request: EvaluateRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> WebBridgeCallResult:
    return await asyncio.to_thread(
        lambda: _webbridge_call(KimiWebBridgeService().evaluate, request, requested_by=user.user_id)
    )


@app.post("/actions/webbridge/list_tabs", response_model=WebBridgeCallResult)
async def webbridge_list_tabs(
    user: AuthenticatedUser = _auth_dependency,
) -> WebBridgeCallResult:
    return await asyncio.to_thread(
        lambda: _webbridge_call(KimiWebBridgeService().list_tabs, requested_by=user.user_id)
    )


@app.post("/actions/webbridge/close_session", response_model=WebBridgeCallResult)
async def webbridge_close_session(
    request: CloseSessionRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> WebBridgeCallResult:
    return await asyncio.to_thread(
        lambda: _webbridge_call(
            KimiWebBridgeService().close_session, request, requested_by=user.user_id
        )
    )


@app.get("/actions/captcha/status", response_model=CaptchaStatus)
async def captcha_status(user: AuthenticatedUser = _auth_dependency) -> CaptchaStatus:
    del user
    return CaptchaSolverService().status()


@app.post("/actions/captcha/image", response_model=CaptchaSolution)
async def captcha_solve_image(
    request: ImageCaptchaRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> CaptchaSolution:
    try:
        return await asyncio.to_thread(
            lambda: CaptchaSolverService().solve_image(
                request.image_base64, requested_by=user.user_id
            )
        )
    except CaptchaSolverError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post("/actions/captcha/token", response_model=CaptchaSolution)
async def captcha_solve_token(
    request: TokenCaptchaRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> CaptchaSolution:
    try:
        return await asyncio.to_thread(
            lambda: CaptchaSolverService().solve_token(
                request.kind,
                website_url=request.website_url,
                website_key=request.website_key,
                page_action=request.page_action,
                requested_by=user.user_id,
            )
        )
    except CaptchaSolverError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.get("/mail/status", response_model=MailStatusView)
async def personal_mail_status(
    user: AuthenticatedUser = _auth_dependency,
) -> MailStatusView:
    del user
    return await PersonalMailService().status()


@app.post("/mail/sync", response_model=MailSyncResult)
async def sync_personal_mail_now(
    user: AuthenticatedUser = _auth_dependency,
) -> MailSyncResult:
    del user
    return await PersonalMailService().sync_now()


@app.post("/mail/sync/dispatch", response_model=dict[str, Any])
async def dispatch_personal_mail_sync(
    user: AuthenticatedUser = _auth_dependency,
) -> dict[str, Any]:
    del user
    async_result = sync_personal_mail_task.apply_async(queue="mail")
    return {"task_id": str(async_result.id), "status": "dispatched"}


@app.get("/mail/messages", response_model=list[MailMessageView])
async def list_personal_mail_messages(
    user: AuthenticatedUser = _auth_dependency,
    statuses: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 80,
) -> list[MailMessageView]:
    del user
    return await PersonalMailService().list_messages(statuses=statuses, limit=limit)


@app.get("/mail/messages/{message_id}", response_model=MailMessageView)
async def get_personal_mail_message(
    message_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> MailMessageView:
    del user
    row = await PersonalMailService().get_message(message_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mail message not found")
    return row


@app.patch("/mail/messages/{message_id}/reply", response_model=MailMessageView)
async def edit_personal_mail_reply(
    message_id: UUID,
    request: MailEditReplyRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> MailMessageView:
    del user
    row = await PersonalMailService().edit_reply(message_id, request)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mail message not found")
    return row


@app.post("/mail/messages/{message_id}/ignore", response_model=MailMessageView)
async def ignore_personal_mail_message(
    message_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> MailMessageView:
    del user
    row = await PersonalMailService().ignore_message(message_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mail message not found")
    return row


@app.post("/mail/messages/{message_id}/approve-send", response_model=MailSendResult)
async def approve_personal_mail_send(
    message_id: UUID,
    request: MailApproveReplyRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> MailSendResult:
    try:
        return await PersonalMailService().approve_and_send(
            message_id,
            request,
            approved_by=user.user_id,
        )
    except MailServiceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.post(
    "/actions/browser/request",
    response_model=ActionRequestView,
    dependencies=[_RL_ACTION_REQUEST_CREATE],
)
async def request_browser_navigation(
    request: BrowserNavigationRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ActionRequestView:
    return await ActionRequestService().create_browser_navigation_request(
        request,
        requested_by=user.user_id,
    )


@app.post(
    "/actions/browser/preview/request",
    response_model=ActionRequestView,
    dependencies=[_RL_ACTION_REQUEST_CREATE],
)
async def request_browser_preview(
    request: BrowserPreviewRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ActionRequestView:
    return await ActionRequestService().create_browser_preview_request(
        request,
        requested_by=user.user_id,
    )


@app.post(
    "/actions/browser/interactive/request",
    response_model=ActionRequestView,
    dependencies=[_RL_ACTION_REQUEST_CREATE],
)
async def request_browser_interactive(
    request: BrowserInteractiveRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ActionRequestView:
    """Persist an interactive browsing plan (multi-step with optional vision)."""
    return await ActionRequestService().create_browser_interactive_request(
        request,
        requested_by=user.user_id,
    )


@app.post("/actions/gmail/query/request", response_model=ActionRequestView)
async def request_gmail_query(
    request: GmailQueryPreviewRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ActionRequestView:
    return await ActionRequestService().create_gmail_query_request(
        request,
        requested_by=user.user_id,
    )


@app.post(
    "/actions/godaddy/dns/request",
    response_model=ActionRequestView,
    dependencies=[_RL_ACTION_REQUEST_CREATE],
)
async def request_godaddy_dns_change(
    request: GoDaddyDnsRecordChange,
    user: AuthenticatedUser = _auth_dependency,
) -> ActionRequestView:
    return await ActionRequestService().create_godaddy_dns_change_request(
        request,
        requested_by=user.user_id,
    )


@app.post("/actions/requests/{action_request_id}/cancel", response_model=ActionRequestView)
async def cancel_action_request(
    action_request_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> ActionRequestView:
    try:
        return await ActionRequestService().cancel_action_request(
            action_request_id,
            requested_by=user.user_id,
        )
    except ActionRequestError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.get("/actions/godaddy/status", response_model=ActionCapabilityStatus)
async def godaddy_status(
    user: AuthenticatedUser = _auth_dependency,
) -> ActionCapabilityStatus:
    del user
    return GoDaddyActionService().status()


@app.post("/actions/godaddy/dns/preview", response_model=GoDaddyDnsChangePreview)
async def preview_godaddy_dns_change(
    request: GoDaddyDnsRecordChange,
    user: AuthenticatedUser = _auth_dependency,
) -> GoDaddyDnsChangePreview:
    del user
    return GoDaddyActionService().preview_dns_change(request)


@app.get("/actions/documents/status", response_model=ActionCapabilityStatus)
async def documents_status(
    user: AuthenticatedUser = _auth_dependency,
) -> ActionCapabilityStatus:
    del user
    return DocumentActionService().status()


@app.post("/actions/documents/preview", response_model=DocumentGeneratePreview)
async def preview_document_generate(
    request: DocumentGenerateRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> DocumentGeneratePreview:
    del user
    return DocumentActionService().build_preview(request)


@app.post(
    "/actions/documents/request",
    response_model=ActionRequestView,
    dependencies=[_RL_ACTION_REQUEST_CREATE],
)
async def request_document_generate(
    request: DocumentGenerateRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ActionRequestView:
    return await ActionRequestService().create_document_generate_request(
        request,
        requested_by=user.user_id,
    )


@app.post("/deepagents/memory/consolidate/run", response_model=dict[str, Any])
async def trigger_memory_consolidation(
    user: AuthenticatedUser = _admin_auth_dependency,
) -> dict[str, Any]:
    """Dispatch the per-agent memory consolidation Celery task immediately.

    Admin-gated: the task rewrites long-term agent memory; only operators with
    admin role or `ADMIN_USER_IDS` membership should be able to trigger it
    out-of-band.
    """
    del user
    async_result = consolidate_all_deepagent_memory_task.apply_async(queue="maintenance")
    return {"task_id": str(async_result.id), "status": "dispatched"}


_AGENT_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "research",
        "kind": "deepagent",
        "description": (
            "Investigación profunda con citas verificables. Combina RAG local, "
            "grafo Neo4j y búsqueda web multi-proveedor (Tavily + Brave + "
            "Perplexity con dedup por URL canónica)."
        ),
        "job_type": "deepagent_research",
        "policy_factory": lambda s: {
            "allow_local_rag": True,
            "allow_neo4j_read": True,
            "allow_web": s.web_search_enabled,
            "allow_workspace_write": True,
            "allow_shell": False,
            "allow_browser": False,
            "allow_email": False,
            "allow_social_posting": False,
            "allow_delete": False,
        },
        "tools": [
            "search_local_docs",
            "read_document_pages",
            "graph_query_readonly",
            "search_web",
            "write_workspace_file",
            "list_available_skills",
            "read_skill",
            "get_relevant_memory",
            "propose_memory_update",
        ],
        "skills_default": [
            "rag-research",
            "evidence-matrix",
            "citation-discipline",
            "report-writer",
        ],
    },
    {
        "name": "document-analysis",
        "kind": "deepagent",
        "description": (
            "Análisis legal/documental con Evidence Ledger determinístico, "
            "matriz hecho/evidencia/cita, timeline, contradicciones y CSVs."
        ),
        "job_type": "document_analysis",
        "policy_factory": lambda s: {
            "allow_local_rag": True,
            "allow_neo4j_read": True,
            "allow_web": False,
            "allow_workspace_write": True,
            "allow_shell": False,
            "allow_browser": False,
            "allow_email": False,
            "allow_social_posting": False,
            "allow_delete": False,
        },
        "tools": [
            "search_within_allowed_docs",
            "read_allowed_pages",
            "get_document_metadata",
            "query_case_graph_readonly",
            "write_analysis_artifact",
            "propose_legal_draft_section",
        ],
        "skills_default": [
            "rag-research",
            "evidence-matrix",
            "timeline-builder",
            "contradiction-detector",
            "citation-discipline",
            "legal-draft-careful",
            "report-writer",
        ],
    },
    {
        "name": "openshell-sandbox",
        "kind": "sandbox",
        "description": (
            "Ejecución de código en sandbox aislado. Bloqueado por defecto, "
            "requiere aprobación humana incluso cuando esté habilitado."
        ),
        "job_type": "openshell_sandbox",
        "policy_factory": lambda s: {
            "allow_local_rag": False,
            "allow_neo4j_read": False,
            "allow_web": s.openshell_allow_network,
            "allow_workspace_write": True,
            "allow_shell": s.enable_openshell_sandbox,
            "allow_browser": False,
            "allow_email": False,
            "allow_social_posting": False,
            "allow_delete": False,
        },
        "tools": ["run_sandboxed_code_task"],
        "skills_default": ["sandbox-code-analysis"],
    },
    {
        "name": "action-plane",
        "kind": "controlled-tools",
        "description": (
            "Browser, computador local, Gmail y GoDaddy en modo preview-first. "
            "Expone validaciones y planes; la ejecucion real futura requiere "
            "aprobacion humana y auditoria."
        ),
        "job_type": "external_action",
        "policy_factory": lambda s: {
            "allow_local_rag": False,
            "allow_neo4j_read": False,
            "allow_web": s.enable_browser_automation,
            "allow_workspace_write": s.enable_computer_actions,
            "allow_shell": False,
            "allow_browser": s.enable_browser_automation,
            "allow_email": s.mail_enabled or s.gmail_read_enabled or s.gmail_send_enabled,
            "allow_social_posting": False,
            "allow_delete": False,
        },
        "tools": [
            "validate_browser_navigation",
            "preview_computer_organize",
            "preview_gmail_query",
            "personal_mail_sync",
            "personal_mail_reply_proposals",
            "preview_godaddy_dns_change",
        ],
        "skills_default": [],
    },
)


@app.get("/agents", response_model=list[AgentSummaryView])
async def list_agents(
    user: AuthenticatedUser = _auth_dependency,
) -> list[AgentSummaryView]:
    """Operational view of every controlled agent with config + recent activity."""
    del user
    summaries: list[AgentSummaryView] = []
    async with session_scope() as session:
        for spec in _AGENT_DEFINITIONS:
            job_type = str(spec["job_type"])
            count_total = (
                await session.scalar(select(func.count(Job.id)).where(Job.job_type == job_type))
                or 0
            )
            count_running = (
                await session.scalar(
                    select(func.count(Job.id))
                    .where(Job.job_type == job_type)
                    .where(Job.status.in_(("queued", "running", "waiting_approval")))
                )
                or 0
            )
            count_completed = (
                await session.scalar(
                    select(func.count(Job.id))
                    .where(Job.job_type == job_type)
                    .where(Job.status == "completed")
                )
                or 0
            )
            count_failed = (
                await session.scalar(
                    select(func.count(Job.id))
                    .where(Job.job_type == job_type)
                    .where(Job.status == "failed")
                )
                or 0
            )
            last_at = await session.scalar(
                select(Job.updated_at)
                .where(Job.job_type == job_type)
                .order_by(desc(Job.updated_at))
                .limit(1)
            )
            policy_dict = spec["policy_factory"](settings)
            summaries.append(
                AgentSummaryView(
                    name=str(spec["name"]),
                    kind=str(spec["kind"]),
                    description=str(spec["description"]),
                    job_type=job_type,
                    policy=AgentPolicyView(**policy_dict),
                    tools=list(spec["tools"]),
                    skills=list(spec["skills_default"]),
                    memory_enabled=settings.deepagents_enable_memory,
                    requires_approval_for_drafts=(
                        settings.require_human_approval_for_external_actions
                    ),
                    web_search_enabled=settings.web_search_enabled,
                    stats=AgentStatsView(
                        total_jobs=int(count_total),
                        running=int(count_running),
                        completed=int(count_completed),
                        failed=int(count_failed),
                        last_active_at=last_at,
                    ),
                )
            )
    return summaries


@app.get("/langsmith/status", response_model=LangSmithStatusView)
async def langsmith_status(
    user: AuthenticatedUser = _langsmith_auth_dependency,
) -> LangSmithStatusView:
    del user
    info = await asyncio.to_thread(_observability_status)
    enabled = info.get("status") == "ok"
    return LangSmithStatusView(
        enabled=enabled,
        project=str(info.get("project") or settings.langsmith_project),
        endpoint=str(
            info.get("endpoint")
            or os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
        ),
        detail=info.get("detail"),
    )


def _observability_status() -> dict[str, Any]:
    from cognitive_os.core.observability import configure_langsmith

    return configure_langsmith()


@app.get("/langsmith/projects", response_model=list[LangSmithProjectView])
async def langsmith_projects(
    user: AuthenticatedUser = _langsmith_auth_dependency,
) -> list[LangSmithProjectView]:
    del user
    return await asyncio.to_thread(_langsmith_list_projects)


def _langsmith_read_key() -> str | None:
    """Prefer the personal access token for read APIs (broader scopes)."""
    pat = settings.langsmith_personal_access_token.get_secret_value().strip()
    if pat and pat != "CHANGEME":
        return pat
    langsmith_credential = settings.langsmith_api_key.get_secret_value().strip()
    if langsmith_credential and langsmith_credential != "CHANGEME":
        return langsmith_credential
    return None


def _langsmith_list_projects() -> list[LangSmithProjectView]:
    api_key = _langsmith_read_key()
    if not api_key:
        return []
    try:
        from langsmith import Client

        client = Client(
            api_key=api_key,
            api_url=os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
        )
        projects = list(client.list_projects(limit=50))
        return [
            LangSmithProjectView(
                id=str(getattr(project, "id", "")),
                name=str(getattr(project, "name", "")),
                run_count=getattr(project, "run_count", None),
            )
            for project in projects
            if getattr(project, "name", "")
        ]
    except Exception as exc:
        logger.warning("langsmith_projects_failed", error_type=type(exc).__name__, error=str(exc))
        return []


@app.get("/langsmith/runs", response_model=list[LangSmithRunView])
async def langsmith_runs(
    project: str | None = None,
    limit: int = 50,
    error_only: bool = False,
    user: AuthenticatedUser = _langsmith_auth_dependency,
) -> list[LangSmithRunView]:
    del user
    bounded = max(1, min(limit, 200))
    project_name = project or settings.langsmith_project
    return await asyncio.to_thread(_langsmith_list_runs, project_name, bounded, error_only)


def _langsmith_list_runs(project_name: str, limit: int, error_only: bool) -> list[LangSmithRunView]:
    api_key = _langsmith_read_key()
    if not api_key:
        return []
    try:
        from langsmith import Client

        client = Client(
            api_key=api_key,
            api_url=os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
        )
        kwargs: dict[str, Any] = {
            "project_name": project_name,
            "limit": limit,
            "is_root": True,
        }
        if error_only:
            kwargs["error"] = True
        runs = list(client.list_runs(**kwargs))
        return [_run_view(run) for run in runs]
    except Exception as exc:
        logger.warning("langsmith_runs_failed", error_type=type(exc).__name__, error=str(exc))
        return []


@app.get("/langsmith/runs/{run_id}", response_model=LangSmithRunDetailView)
async def langsmith_run_detail(
    run_id: str,
    user: AuthenticatedUser = _langsmith_auth_dependency,
) -> LangSmithRunDetailView:
    del user
    detail = await asyncio.to_thread(_langsmith_run_detail, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="LangSmith run not found")
    return detail


def _langsmith_run_detail(run_id: str) -> LangSmithRunDetailView | None:
    api_key = _langsmith_read_key()
    if not api_key:
        return None
    try:
        from langsmith import Client

        client = Client(
            api_key=api_key,
            api_url=os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
        )
        run = client.read_run(run_id)
    except Exception as exc:
        logger.warning("langsmith_run_failed", run_id=run_id, error=str(exc))
        return None
    base = _run_view(run)
    return LangSmithRunDetailView(
        **base.model_dump(),
        inputs=_safe_dict(getattr(run, "inputs", None)),
        outputs=_safe_dict(getattr(run, "outputs", None)),
        extra=_safe_dict(getattr(run, "extra", None)),
        tags=list(getattr(run, "tags", []) or []) or None,
    )


def _run_view(run: Any) -> LangSmithRunView:
    start = getattr(run, "start_time", None)
    end = getattr(run, "end_time", None)
    latency = None
    if start and end:
        latency = max(0.0, (end - start).total_seconds() * 1000)
    return LangSmithRunView(
        id=str(getattr(run, "id", "")),
        name=getattr(run, "name", None),
        run_type=getattr(run, "run_type", None),
        status=getattr(run, "status", None),
        start_time=start,
        end_time=end,
        latency_ms=latency,
        error=getattr(run, "error", None),
        total_tokens=getattr(run, "total_tokens", None),
        parent_run_id=str(getattr(run, "parent_run_id", "") or "") or None,
    )


def _safe_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        return dict(value)
    except Exception:
        return None


async def _decide_approval(
    approval_id: UUID,
    *,
    status_value: str,
    approver_user_id: str,
) -> ApprovalResponse:
    """REST adapter on top of `actions.service.decide_approval`.

    Translates domain errors to HTTP status codes and dispatches the OpenShell
    Celery task after the DB transaction commits.
    """
    try:
        result = await decide_approval(
            approval_id,
            status_value=status_value,
            approver_user_id=approver_user_id,
            payload_resolver=_openshell_task_payload_from_job,
        )
    except ApprovalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found"
        ) from exc
    except ApprovalAlreadyDecidedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval already decided: {exc.current_status}",
        ) from exc
    except ApprovalSelfDecisionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except ApprovalPayloadCorruptError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ApprovalDecisionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    if result.openshell_dispatch is not None:
        run_openshell_task_async.apply_async(
            args=[result.openshell_dispatch.task_payload, result.openshell_dispatch.job_id],
            queue="agent_longrun",
        )
    return _approval_response(result.approval)


def _openshell_task_payload_from_job(job: Job) -> dict[str, Any]:
    """Reveal the OpenShell executable payload stored on a `Job`.

    Raises domain-level `ApprovalPayloadCorruptError` so callers (REST adapter
    and Telegram bot) decide their own status/message. Never raises
    HTTPException directly — keeping this surface framework-agnostic lets the
    shared `decide_approval` invoke it without importing FastAPI.
    """
    metadata = job.metadata_json or {}
    stored_payload = metadata.get("task_payload_executable")
    redacted_payload = metadata.get("task_payload_redacted")
    if not isinstance(stored_payload, dict):
        raise ApprovalPayloadCorruptError(
            "OpenShell approval is missing executable task payload"
        )
    if not isinstance(redacted_payload, dict):
        redacted_payload = {}
    try:
        payload = reveal_payload(stored_payload, redacted_payload, settings)
        task = OpenShellTask.model_validate(payload)
    except Exception as exc:
        raise ApprovalPayloadCorruptError(
            "OpenShell approval payload is not executable"
        ) from exc
    return task.model_dump(mode="json")


async def _create_openshell_job(task: OpenShellTask, requested_by: str) -> UUID:
    async with session_scope() as session:
        job = Job(
            job_type="openshell_sandbox",
            status="queued",
            progress=0,
            metadata_json={
                "task_id": task.task_id,
                "thread_id": task.thread_id,
                "requested_by": requested_by,
            },
        )
        session.add(job)
        await session.flush()
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="openshell_task_received",
                status="queued",
                message="OpenShell sandbox task queued",
                metadata_json={"task_id": task.task_id, "thread_id": task.thread_id},
            )
        )
        return job.id


async def _create_openshell_approval_job(
    task: OpenShellTask,
    requested_by: str,
) -> tuple[UUID, UUID]:
    task_payload = task.model_dump(mode="json")
    async with session_scope() as session:
        job = Job(
            job_type="openshell_sandbox",
            status="waiting_approval",
            progress=0,
            metadata_json={
                "task_id": task.task_id,
                "thread_id": task.thread_id,
                "requested_by": requested_by,
                "task_payload_executable": protect_payload(task_payload, settings),
                "task_payload_redacted": redact_openshell_payload(task_payload),
            },
        )
        session.add(job)
        await session.flush()
        approval = HumanApproval(
            action="run_sandboxed_code_task",
            requested_action="run_sandboxed_code_task",
            args_redacted=redact_openshell_payload(task.model_dump(mode="json")),
            requested_by=requested_by,
            job_id=job.id,
        )
        session.add(approval)
        await session.flush()
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="openshell_approval_required",
                status="waiting_approval",
                message="OpenShell sandbox task requires human approval",
                metadata_json={"approval_id": str(approval.id), "task_id": task.task_id},
            )
        )
        return job.id, approval.id


async def _create_document_analysis_job(task: DocumentAnalysisTask, requested_by: str) -> UUID:
    async with session_scope() as session:
        job = Job(
            job_type="document_analysis",
            status="queued",
            progress=0,
            metadata_json={
                "task_id": task.task_id,
                "thread_id": task.thread_id,
                "doc_ids_count": len(task.doc_ids),
                "requested_by": requested_by,
            },
        )
        session.add(job)
        await session.flush()
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="job_queued",
                status="queued",
                message="Document analysis queued",
                metadata_json={"task_id": task.task_id, "thread_id": task.thread_id},
            )
        )
        return job.id


def _download_analysis_file(task_id: str, filename: str, media_type: str) -> FileResponse:
    path = _analysis_file_path(task_id, filename)
    return FileResponse(path, media_type=media_type, filename=path.name)


def _analysis_file_path(task_id: str, filename: str) -> Path:
    if not task_id or any(char in task_id for char in "/\\*?[]"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task_id")
    base = (Path(settings.local_storage_dir) / "workspaces").resolve()
    candidates = sorted(base.glob(f"*/{task_id}/analysis/{filename}"))
    for candidate in candidates:
        resolved = candidate.resolve()
        try:
            resolved.relative_to(base)
        except ValueError:
            continue
        if resolved.is_file():
            return resolved
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Document analysis artifact not found",
    )


def _chat_response(thread_id: str, state: CognitiveState) -> ChatResponse:
    result = state.get("agent_result")
    pending = state.get("pending_human_review")
    latest_message = ""
    messages = state.get("messages", [])
    if messages:
        latest_message = str(messages[-1].content)
    if result is not None:
        latest_message = result.content
    return ChatResponse(
        thread_id=thread_id,
        message=latest_message,
        route=str(state.get("active_route", "research")),
        pending_human_review=pending.model_dump() if pending is not None else None,
    )


def _chat_response_from_raw(thread_id: str, raw_result: Any) -> ChatResponse:
    if isinstance(raw_result, dict) and "__interrupt__" in raw_result:
        interrupt_payload = _extract_interrupt_payload(raw_result)
        snapshot = _api_graph.get_state({"configurable": {"thread_id": thread_id}})
        route = "research"
        if snapshot.values:
            route = str(cast_state(snapshot.values).get("active_route", route))
        return ChatResponse(
            thread_id=thread_id,
            message="Human approval required.",
            route=route,
            pending_human_review=interrupt_payload,
        )
    return _chat_response(thread_id, cast_state(raw_result))


def _extract_interrupt_payload(raw_result: dict[str, Any]) -> dict[str, Any]:
    interrupts = raw_result.get("__interrupt__")
    if isinstance(interrupts, tuple | list) and interrupts:
        first = interrupts[0]
        value = getattr(first, "value", first)
        if isinstance(value, dict):
            return value
    return {"reason": "Human approval required."}


def _serialize_state(state: CognitiveState) -> dict[str, Any]:
    values: dict[str, Any] = {}
    messages = state.get("messages", [])
    if messages:
        values["messages"] = [
            {"type": message.type, "content": str(message.content)} for message in messages
        ]
    for key, value in state.items():
        if key == "messages":
            continue
        if hasattr(value, "model_dump"):
            values[key] = value.model_dump()
        else:
            values[key] = jsonable_encoder(value)
    return values


def _job_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        metadata_json=job.metadata_json,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


_research_orchestrator: ResearchOrchestrator | None = None


def get_research_orchestrator() -> ResearchOrchestrator:
    global _research_orchestrator
    if _research_orchestrator is None:
        _research_orchestrator = ResearchOrchestrator(
            store=create_research_run_store(settings),
        )
    return _research_orchestrator


class ResearchRunView(BaseModel):
    run_id: str
    status: str
    request: ResearchRunRequest
    subtasks: list[dict[str, Any]] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)
    synthesis: dict[str, Any] | None = None
    score: dict[str, Any] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


def _research_run_view(run: Any) -> ResearchRunView:
    return ResearchRunView(
        run_id=run.run_id,
        status=run.status,
        request=run.request,
        subtasks=[s.model_dump(mode="json") for s in run.subtasks],
        results=[r.model_dump(mode="json") for r in run.results],
        synthesis=run.synthesis.model_dump(mode="json") if run.synthesis else None,
        score=run.score.model_dump(mode="json") if run.score else None,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error=run.error,
    )


@app.post("/research/runs", response_model=ResearchRunView)
async def start_research_run(
    request: ResearchRunRequest,
    user: AuthenticatedUser = _auth_dependency,
) -> ResearchRunView:
    request = request.model_copy(update={"user_id": request.user_id or user.user_id})
    try:
        run = get_research_orchestrator().start_run(request)
    except ResearchOrchestratorDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return _research_run_view(run)


@app.get("/research/runs", response_model=list[ResearchRunView])
async def list_research_runs(
    user: AuthenticatedUser = _auth_dependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ResearchRunView]:
    del user
    return [_research_run_view(r) for r in get_research_orchestrator().list_runs(limit=limit)]


@app.get("/research/runs/{run_id}", response_model=ResearchRunView)
async def get_research_run(
    run_id: str,
    user: AuthenticatedUser = _auth_dependency,
) -> ResearchRunView:
    del user
    run = get_research_orchestrator().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research run not found.")
    return _research_run_view(run)


@app.post("/research/runs/{run_id}/cancel", response_model=ResearchRunView)
async def cancel_research_run(
    run_id: str,
    user: AuthenticatedUser = _auth_dependency,
) -> ResearchRunView:
    del user
    run = get_research_orchestrator().cancel_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research run not found.")
    return _research_run_view(run)


_RESEARCH_TERMINAL_STATUSES = frozenset({"completed", "cancelled", "failed", "blocked"})


@app.get("/research/runs/{run_id}/events")
async def stream_research_events(
    run_id: str,
    user: AuthenticatedUser = _auth_dependency,
) -> StreamingResponse:
    """SSE stream of `ResearchEvent`s for a single research run.

    The endpoint emits every event already produced by the run (so a client
    that connects late still sees the full history), then keeps streaming
    new events until the run reaches a terminal state. The final frame is
    a `snapshot` event carrying the full `ResearchRunView` so the UI does
    not need a separate GET to render the result.
    """
    del user
    orchestrator = get_research_orchestrator()
    if orchestrator.get_run(run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research run not found.")
    return StreamingResponse(
        _research_events_stream(orchestrator, run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _research_events_stream(
    orchestrator: ResearchOrchestrator,
    run_id: str,
) -> AsyncIterator[str]:
    """Yield SSE frames for a research run until it reaches a terminal state.

    Reading `run.events` under CPython's GIL is atomic for list slicing, so we
    snapshot the list and advance a cursor each tick. The poll interval is
    short (50 ms) to keep streaming low-latency without burning CPU.
    """
    last_idx = 0
    poll_interval = 0.05
    while True:
        run = orchestrator.get_run(run_id)
        if run is None:
            yield _sse({"event": "error", "run_id": run_id, "detail": "run_not_found"})
            return
        snapshot_events = list(run.events)
        new_events = snapshot_events[last_idx:]
        for event in new_events:
            yield _research_event_sse(event)
        last_idx = len(snapshot_events)
        if run.status in _RESEARCH_TERMINAL_STATUSES:
            yield _sse(
                {
                    "event": "snapshot",
                    "run_id": run_id,
                    "payload": _research_run_view(run).model_dump(mode="json"),
                }
            )
            yield _sse({"event": "done", "run_id": run_id})
            return
        await asyncio.sleep(poll_interval)


def _research_event_sse(event: ResearchEvent) -> str:
    return _sse(
        {
            "event": event.kind,
            "run_id": event.run_id,
            "timestamp": event.timestamp.isoformat(),
            "payload": event.payload,
        }
    )


def _job_event_response(event: JobEvent) -> JobEventResponse:
    return JobEventResponse(
        id=event.id,
        job_id=event.job_id,
        event_type=event.event_type,
        status=event.status,
        message=event.message,
        metadata_json=event.metadata_json,
        created_at=event.created_at,
    )


def _approval_response(approval: HumanApproval) -> ApprovalResponse:
    return ApprovalResponse(
        id=approval.id,
        requested_action=approval.requested_action,
        args_redacted=approval.args_redacted,
        status=approval.status,
        requested_by=approval.requested_by,
        approver_user_id=approval.approver_user_id,
        created_at=approval.created_at,
        decided_at=approval.decided_at,
    )

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import desc, select

from cognitive_os.actions.browser import BrowserActionService
from cognitive_os.actions.browser_interactive import BrowserInteractiveService
from cognitive_os.actions.browser_preview import BrowserPreviewService
from cognitive_os.actions.calendar import CalendarError, CalendarService, EventCreateRequest
from cognitive_os.actions.computer import ComputerActionService
from cognitive_os.actions.documents import DocumentActionService
from cognitive_os.actions.domains import GoDaddyActionService
from cognitive_os.actions.drive import (
    DriveError,
    DriveFolderRequest,
    DriveOrganizeRequest,
    DriveService,
    DriveUploadRequest,
)
from cognitive_os.actions.mail import GmailActionService
from cognitive_os.actions.payload_crypto import protect_payload, reveal_payload
from cognitive_os.actions.policy import ActionPolicyViolation
from cognitive_os.actions.schemas import (
    ActionRequestStatus,
    ActionRequestView,
    ActionType,
    BrowserInteractiveRequest,
    BrowserNavigationRequest,
    BrowserPreviewRequest,
    ComputerOrganizePlan,
    ComputerOrganizeRequest,
    DocumentGenerateRequest,
    GmailQueryPreviewRequest,
    GoDaddyDnsRecordChange,
    WorkflowActionType,
    WorkflowDocument,
    WorkflowSource,
)
from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import ActionRequest, AuditEvent, HumanApproval, Job, JobEvent
from cognitive_os.tools.policy import redact_tool_args
from cognitive_os.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _celery_task_id(async_result: Any) -> str | None:
    raw_id = getattr(async_result, "id", None) or getattr(async_result, "task_id", None)
    if raw_id is None:
        return None
    task_id = str(raw_id).strip()
    return task_id or None


_ACTIVE_STATUSES: tuple[str, ...] = (
    "previewed",
    "pending_approval",
    "queued",
    "running",
)

# Action types that the dedicated_local profile is allowed to auto-approve.
# Reversible and scoped to the agent's own workspace — no external comms, no
# write over existing third-party data. Drive organize over foreign data,
# mail send, browser, openshell and code_build stay manual on purpose.
#
# `computer_organize`: Fase 73 amplía la whitelist al filesystem local del
# operador. En dedicated_local el PC pertenece al agente y mover/renombrar
# archivos NO es irreversible — siguen en el disco, sólo cambian de path —
# así que pedirlo cada vez era pura fricción. El plan completo (`preview`)
# queda persistido en el `ActionRequest` para auditar después.
_AUTO_APPROVABLE_REVERSIBLE_ACTIONS: frozenset[str] = frozenset(
    {
        "drive_ensure_folder",
        "drive_upload_file",
        "computer_organize",
    }
)

# action_type values supported by the workflow.v1 export/import contract. Must
# stay in sync with `WorkflowActionType` in `actions/schemas.py`.
WORKFLOW_EXPORTABLE_TYPES: frozenset[str] = frozenset(
    {
        "computer_organize",
        "godaddy_dns_change",
        "document_generate",
        "browser_preview",
        "browser_interactive",
        "calendar_create_event",
        "drive_upload_file",
        "drive_ensure_folder",
        "drive_organize_files",
    }
)


class ActionRequestError(RuntimeError):
    """Raised when an action request cannot progress through its lifecycle."""


class ApprovalDecisionError(RuntimeError):
    """Base class for `decide_approval` domain errors.

    Each subclass maps cleanly to an HTTP status in the REST endpoint and to a
    human-readable message in the Telegram bot, so both surfaces stay in sync
    without coupling to FastAPI's HTTPException.
    """


class ApprovalNotFoundError(ApprovalDecisionError):
    """The `approval_id` does not exist."""


class ApprovalAlreadyDecidedError(ApprovalDecisionError):
    """The approval already moved past `pending`."""

    def __init__(self, current_status: str) -> None:
        super().__init__(f"Approval already decided: {current_status}")
        self.current_status = current_status


class ApprovalSelfDecisionError(ApprovalDecisionError):
    """Four-eyes contract: requester and approver are the same user."""


class ApprovalPayloadCorruptError(ApprovalDecisionError):
    """The approval is linked to a job whose stored payload cannot be revealed."""


@dataclass(slots=True)
class OpenShellDispatchSpec:
    """Returned by `decide_approval` when an OpenShell job must be queued.

    Caller dispatches the Celery task after the DB transaction commits so the
    sandbox worker never sees a job that the operator can still see as
    `waiting_approval`.
    """

    task_payload: dict[str, Any]
    job_id: str


@dataclass(slots=True)
class ApprovalDecisionResult:
    approval: HumanApproval
    openshell_dispatch: OpenShellDispatchSpec | None = None
    # Set when an approved `run_code_build:<id>` HumanApproval is accepted.
    # The caller dispatches `cognitive_os.run_code_build` after commit, same
    # post-transaction pattern as `openshell_dispatch`.
    code_build_job_id: str | None = None


@dataclass(slots=True)
class ActionDispatchReservation:
    action_request: ActionRequestView
    should_dispatch: bool
    reason: str | None = None


async def decide_approval(
    approval_id: UUID,
    *,
    status_value: str,
    approver_user_id: str,
    payload_resolver: Callable[[Job], dict[str, Any]] | None = None,
    app_settings: Settings = settings,
) -> ApprovalDecisionResult:
    """Decide a `HumanApproval` and cascade side-effects.

    Shared by `/approvals/{id}/{approve|reject}` and the Telegram bot so both
    inherit four-eyes, cascade to Job/ActionRequest, AuditEvent emission and
    OpenShell dispatch in the same atomic transaction. The Celery dispatch
    itself happens after commit — callers receive the spec via
    `ApprovalDecisionResult.openshell_dispatch`.

    `payload_resolver` is a hook so the API layer can inject its
    `_openshell_task_payload_from_job` (which knows how to reveal the
    encrypted payload). Callers that don't want OpenShell side-effects pass
    `None` and any sandbox approval is decided but not queued.
    """
    if status_value not in {"approved", "rejected"}:
        msg = f"Unsupported decision: {status_value!r}"
        raise ApprovalDecisionError(msg)

    openshell_dispatch: OpenShellDispatchSpec | None = None
    async with session_scope() as session:
        approval = await session.get(HumanApproval, approval_id)
        if approval is None:
            raise ApprovalNotFoundError(f"Approval not found: {approval_id}")
        if approval.status != "pending":
            raise ApprovalAlreadyDecidedError(approval.status)
        if (
            app_settings.approval_require_four_eyes
            and approval.requested_by
            and approval.requested_by == approver_user_id
        ):
            raise ApprovalSelfDecisionError(
                "Approver must differ from requester: human-in-the-loop requires four-eyes review."
            )

        approval.status = status_value
        approval.approver_user_id = approver_user_id
        approval.approved_by = approver_user_id if status_value == "approved" else None
        approval.decided_at = datetime.now(UTC)

        job = await session.get(Job, approval.job_id) if approval.job_id is not None else None
        if status_value == "rejected":
            if job is not None and job.status not in {"completed", "failed", "cancelled"}:
                job.status = "rejected"
                job.progress = 100
                session.add(
                    JobEvent(
                        job_id=job.id,
                        event_type="approval_rejected",
                        status="rejected",
                        message="Human approval rejected",
                        metadata_json={"approval_id": str(approval.id)},
                    )
                )
            action_request_result = await session.execute(
                select(ActionRequest).where(ActionRequest.approval_id == approval.id)
            )
            action_request = action_request_result.scalar_one_or_none()
            if action_request is not None and action_request.status not in {
                "completed",
                "failed",
                "cancelled",
                "rejected",
            }:
                action_request.status = "rejected"
                action_request.error = "Human approval rejected"
        elif (
            status_value == "approved"
            and job is not None
            and job.job_type == "openshell_sandbox"
            and job.status == "waiting_approval"
        ):
            if payload_resolver is None:
                raise ApprovalPayloadCorruptError(
                    "OpenShell approval requires a payload resolver to dispatch."
                )
            try:
                task_payload = payload_resolver(job)
            except ApprovalDecisionError:
                raise
            except Exception as exc:  # noqa: BLE001 - convert to domain error
                raise ApprovalPayloadCorruptError(
                    "OpenShell approval payload is not executable"
                ) from exc
            job.status = "queued"
            job.progress = 0
            session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="openshell_approval_approved",
                    status="queued",
                    message="OpenShell sandbox approval accepted; task queued",
                    metadata_json={"approval_id": str(approval.id)},
                )
            )
            openshell_dispatch = OpenShellDispatchSpec(
                task_payload=task_payload,
                job_id=str(job.id),
            )

        code_build_job_id: str | None = None
        if (
            status_value == "approved"
            and job is not None
            and job.job_type == "code_build"
            and job.status == "waiting_approval"
        ):
            job.status = "queued"
            job.progress = 0
            session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="code_build_approval_approved",
                    status="queued",
                    message="Code build plan approved; build queued",
                    metadata_json={"approval_id": str(approval.id)},
                )
            )
            code_build_job_id = str(job.id)

        session.add(
            AuditEvent(
                actor_id=approver_user_id,
                action=f"approval.{status_value}",
                resource_type="human_approval",
                resource_id=str(approval.id),
                metadata_json={
                    "requested_action": approval.requested_action,
                    "requested_by": approval.requested_by,
                    "job_id": str(approval.job_id) if approval.job_id else None,
                },
            )
        )
        await session.flush()
        return ApprovalDecisionResult(
            approval=approval,
            openshell_dispatch=openshell_dispatch,
            code_build_job_id=code_build_job_id,
        )


class ActionRequestService:
    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    def _should_auto_approve_action(self, action_type: str) -> bool:
        if (
            self._settings.operator_profile == "dedicated_local"
            and getattr(self._settings, "local_autonomy_mode", "guarded") == "full"
            and not self._settings.require_human_approval_for_external_actions
        ):
            return True
        return (
            self._settings.auto_approve_reversible_actions
            and action_type in _AUTO_APPROVABLE_REVERSIBLE_ACTIONS
        )

    async def _find_active_idempotent_request(
        self,
        session: object,
        *,
        action_type: str,
        requested_by: str,
        idempotency_key: str,
    ) -> ActionRequest | None:
        """Return an active ActionRequest matching (type, requester, key) if any.

        Acts as a fast-path dedup for double-clicks or retried POSTs: the row is
        unique up to a (action_type, requested_by, idempotency_key) tuple while
        the prior request has not reached a terminal state. Same payload from a
        different user is intentionally treated as an independent intent.
        """
        if not idempotency_key:
            return None
        stmt = (
            select(ActionRequest)
            .where(ActionRequest.action_type == action_type)
            .where(ActionRequest.idempotency_key == idempotency_key)
            .where(ActionRequest.requested_by == requested_by)
            .where(ActionRequest.status.in_(_ACTIVE_STATUSES))
            .order_by(desc(ActionRequest.created_at))
            .limit(1)
        )
        result = await session.execute(stmt)  # type: ignore[attr-defined]
        row = result.scalar_one_or_none()
        return cast("ActionRequest | None", row)

    async def create_computer_organize_request(
        self,
        request: ComputerOrganizeRequest,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        plan = ComputerActionService(self._settings).build_organize_plan(request)
        payload_executable = request.model_dump(mode="json")
        payload_redacted = redact_tool_args(payload_executable)
        preview = plan.model_dump(mode="json")
        action_status = _initial_status(
            blocked=plan.status == "blocked",
            dry_run_only=plan.dry_run_only,
        )
        idempotency_key = _idempotency_key("computer_organize", payload_redacted)

        async with session_scope() as session:
            existing = await self._find_active_idempotent_request(
                session,
                action_type="computer_organize",
                requested_by=requested_by,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                return _view(existing)
            action_request = ActionRequest(
                action_type="computer_organize",
                status=action_status,
                requested_by=requested_by,
                idempotency_key=idempotency_key,
                payload_redacted=payload_redacted,
                payload_executable=protect_payload(payload_executable, self._settings),
                preview=preview,
                error=plan.reason if plan.status == "blocked" else None,
                metadata_json={"requires_approval": True, "dry_run_only": plan.dry_run_only},
            )
            session.add(action_request)
            await session.flush()

            if action_status == "pending_approval":
                job = Job(
                    job_type="external_action",
                    status="waiting_approval",
                    progress=0,
                    metadata_json={
                        "action_request_id": str(action_request.id),
                        "action_type": action_request.action_type,
                        "requested_by": requested_by,
                    },
                )
                session.add(job)
                await session.flush()

                approval = HumanApproval(
                    action="execute_action_request",
                    requested_action=f"execute_action_request:{action_request.id}",
                    args_redacted={
                        "action_request_id": str(action_request.id),
                        "action_type": action_request.action_type,
                        "preview": preview,
                    },
                    requested_by=requested_by,
                    job_id=job.id,
                    metadata_json={"action_request_id": str(action_request.id)},
                )
                session.add(approval)
                await session.flush()

                action_request.job_id = job.id
                action_request.approval_id = approval.id
                session.add(
                    JobEvent(
                        job_id=job.id,
                        event_type="action_approval_required",
                        status="waiting_approval",
                        message="Action request requires human approval",
                        metadata_json={
                            "action_request_id": str(action_request.id),
                            "approval_id": str(approval.id),
                        },
                    )
                )

            session.add(
                AuditEvent(
                    actor_id=requested_by,
                    action="action_request.created",
                    resource_type="action_request",
                    resource_id=str(action_request.id),
                    metadata_json={
                        "action_type": action_request.action_type,
                        "status": action_request.status,
                        "payload_redacted": payload_redacted,
                    },
                )
            )
            await session.flush()
            view = _view(action_request)
            auto_approve_eligible = (
                action_status == "pending_approval"
                and self._should_auto_approve_action("computer_organize")
                and action_request.approval_id is not None
            )
            approval_id_to_auto = action_request.approval_id if auto_approve_eligible else None

        if approval_id_to_auto is not None:
            view = await self._auto_approve_and_dispatch(
                approval_id=approval_id_to_auto,
                action_request_id=view.id,
                requested_by=requested_by,
            )
        return view

    async def create_browser_navigation_request(
        self,
        request: BrowserNavigationRequest,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        validation = BrowserActionService(self._settings).validate_navigation(request)
        payload_redacted = redact_tool_args(request.model_dump(mode="json"))
        preview = validation.model_dump(mode="json")
        blocked = not validation.allowed
        return await self._persist_preview_request(
            action_type="browser_navigation",
            payload_redacted=payload_redacted,
            preview=preview,
            blocked=blocked,
            reason=validation.reason,
            requested_by=requested_by,
        )

    async def create_gmail_query_request(
        self,
        request: GmailQueryPreviewRequest,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        preview_model = GmailActionService(self._settings).preview_query(request)
        payload_redacted = redact_tool_args(request.model_dump(mode="json"))
        preview = preview_model.model_dump(mode="json")
        blocked = preview_model.status == "blocked"
        return await self._persist_preview_request(
            action_type="gmail_query",
            payload_redacted=payload_redacted,
            preview=preview,
            blocked=blocked,
            reason=preview_model.reason,
            requested_by=requested_by,
        )

    async def create_godaddy_dns_change_request(
        self,
        change: GoDaddyDnsRecordChange,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        preview_model = GoDaddyActionService(self._settings).preview_dns_change(change)
        payload_executable = preview_model.change.model_dump(mode="json")
        payload_redacted = redact_tool_args(payload_executable)
        preview = preview_model.model_dump(mode="json")
        blocked = preview_model.status == "blocked"
        action_status = _initial_status(blocked=blocked, dry_run_only=preview_model.dry_run_only)
        idempotency_key = _idempotency_key("godaddy_dns_change", payload_redacted)

        async with session_scope() as session:
            existing = await self._find_active_idempotent_request(
                session,
                action_type="godaddy_dns_change",
                requested_by=requested_by,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                return _view(existing)
            action_request = ActionRequest(
                action_type="godaddy_dns_change",
                status=action_status,
                requested_by=requested_by,
                idempotency_key=idempotency_key,
                payload_redacted=payload_redacted,
                payload_executable=protect_payload(payload_executable, self._settings),
                preview=preview,
                error=preview_model.reason if blocked else None,
                metadata_json={
                    "requires_approval": True,
                    "dry_run_only": preview_model.dry_run_only,
                    "endpoint": preview_model.endpoint,
                },
            )
            session.add(action_request)
            await session.flush()

            if action_status == "pending_approval":
                job = Job(
                    job_type="external_action",
                    status="waiting_approval",
                    progress=0,
                    metadata_json={
                        "action_request_id": str(action_request.id),
                        "action_type": action_request.action_type,
                        "requested_by": requested_by,
                    },
                )
                session.add(job)
                await session.flush()

                approval = HumanApproval(
                    action="execute_action_request",
                    requested_action=f"execute_action_request:{action_request.id}",
                    args_redacted={
                        "action_request_id": str(action_request.id),
                        "action_type": action_request.action_type,
                        "preview": preview,
                    },
                    requested_by=requested_by,
                    job_id=job.id,
                    metadata_json={"action_request_id": str(action_request.id)},
                )
                session.add(approval)
                await session.flush()

                action_request.job_id = job.id
                action_request.approval_id = approval.id
                session.add(
                    JobEvent(
                        job_id=job.id,
                        event_type="action_approval_required",
                        status="waiting_approval",
                        message="GoDaddy DNS change requires human approval",
                        metadata_json={
                            "action_request_id": str(action_request.id),
                            "approval_id": str(approval.id),
                        },
                    )
                )

            session.add(
                AuditEvent(
                    actor_id=requested_by,
                    action="action_request.created",
                    resource_type="action_request",
                    resource_id=str(action_request.id),
                    metadata_json={
                        "action_type": action_request.action_type,
                        "status": action_request.status,
                        "payload_redacted": payload_redacted,
                    },
                )
            )
            await session.flush()
            view = _view(action_request)
            auto_approve_eligible = (
                action_status == "pending_approval"
                and self._should_auto_approve_action("godaddy_dns_change")
                and action_request.approval_id is not None
            )
            approval_id_to_auto = action_request.approval_id if auto_approve_eligible else None

        if approval_id_to_auto is not None:
            view = await self._auto_approve_and_dispatch(
                approval_id=approval_id_to_auto,
                action_request_id=view.id,
                requested_by=requested_by,
            )
        return view

    async def create_document_generate_request(
        self,
        request: DocumentGenerateRequest,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        preview_model = DocumentActionService(self._settings).build_preview(request)
        payload_executable = request.model_dump(mode="json")
        payload_redacted = redact_tool_args(payload_executable)
        preview = preview_model.model_dump(mode="json")
        blocked = preview_model.status == "blocked"
        action_status = "blocked" if blocked else "pending_approval"
        idempotency_key = _idempotency_key("document_generate", payload_redacted)

        async with session_scope() as session:
            existing = await self._find_active_idempotent_request(
                session,
                action_type="document_generate",
                requested_by=requested_by,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                return _view(existing)
            action_request = ActionRequest(
                action_type="document_generate",
                status=action_status,
                requested_by=requested_by,
                idempotency_key=idempotency_key,
                payload_redacted=payload_redacted,
                payload_executable=protect_payload(payload_executable, self._settings),
                preview=preview,
                error=preview_model.reason if blocked else None,
                metadata_json={
                    "requires_approval": True,
                    "dry_run_only": False,
                    "format": request.format,
                },
            )
            session.add(action_request)
            await session.flush()

            if action_status == "pending_approval":
                job = Job(
                    job_type="external_action",
                    status="waiting_approval",
                    progress=0,
                    metadata_json={
                        "action_request_id": str(action_request.id),
                        "action_type": action_request.action_type,
                        "requested_by": requested_by,
                    },
                )
                session.add(job)
                await session.flush()

                approval = HumanApproval(
                    action="execute_action_request",
                    requested_action=f"execute_action_request:{action_request.id}",
                    args_redacted={
                        "action_request_id": str(action_request.id),
                        "action_type": action_request.action_type,
                        "preview": preview,
                    },
                    requested_by=requested_by,
                    job_id=job.id,
                    metadata_json={"action_request_id": str(action_request.id)},
                )
                session.add(approval)
                await session.flush()

                action_request.job_id = job.id
                action_request.approval_id = approval.id
                session.add(
                    JobEvent(
                        job_id=job.id,
                        event_type="action_approval_required",
                        status="waiting_approval",
                        message="Action request requires human approval",
                        metadata_json={
                            "action_request_id": str(action_request.id),
                            "approval_id": str(approval.id),
                        },
                    )
                )

            session.add(
                AuditEvent(
                    actor_id=requested_by,
                    action="action_request.created",
                    resource_type="action_request",
                    resource_id=str(action_request.id),
                    metadata_json={
                        "action_type": action_request.action_type,
                        "status": action_request.status,
                        "payload_redacted": payload_redacted,
                    },
                )
            )
            await session.flush()
            view = _view(action_request)
            auto_approve_eligible = (
                action_status == "pending_approval"
                and self._should_auto_approve_action("document_generate")
                and action_request.approval_id is not None
            )
            approval_id_to_auto = action_request.approval_id if auto_approve_eligible else None

        if approval_id_to_auto is not None:
            view = await self._auto_approve_and_dispatch(
                approval_id=approval_id_to_auto,
                action_request_id=view.id,
                requested_by=requested_by,
            )
        return view

    async def create_calendar_event_request(
        self,
        request: EventCreateRequest,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        service = CalendarService(app_settings=self._settings)
        preview: dict[str, object]
        blocked = False
        reason: str | None = None
        try:
            preview_model = service.create_event(request.model_copy(update={"dry_run": True}))
            preview = preview_model.model_dump(mode="json")
            status = service.status()
            if status.status != "ready":
                blocked = True
                reason = status.reason or "Google Calendar is not ready."
            elif not status.write_enabled:
                blocked = True
                reason = "ENABLE_GOOGLE_CALENDAR_WRITE is false; refusing executable request."
        except CalendarError as exc:
            preview = {"status": "blocked", "reason": str(exc)}
            blocked = True
            reason = str(exc)

        executable = request.model_copy(update={"dry_run": False}).model_dump(mode="json")
        redacted = redact_tool_args(executable)
        return await self._persist_executable_request(
            action_type="calendar_create_event",
            payload_executable=executable,
            payload_redacted=redacted,
            preview=preview,
            blocked=blocked,
            reason=reason,
            requested_by=requested_by,
            approval_message="Google Calendar event creation requires human approval",
            metadata={"requires_approval": True, "dry_run_only": False, "google": "calendar"},
        )

    async def create_drive_upload_request(
        self,
        request: DriveUploadRequest,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        service = DriveService(app_settings=self._settings)
        preview: dict[str, object]
        blocked = False
        reason: str | None = None
        try:
            preview_model = service.upload_file(request.model_copy(update={"dry_run": True}))
            preview = preview_model.model_dump(mode="json")
            status = service.status()
            if preview_model.status == "blocked":
                blocked = True
                reason = preview_model.reason
            elif status.status != "ready":
                blocked = True
                reason = status.reason or "Google Drive is not ready."
            elif not status.write_enabled:
                blocked = True
                reason = "ENABLE_GOOGLE_DRIVE_WRITE is false; refusing executable request."
        except DriveError as exc:
            preview = {"status": "blocked", "reason": str(exc)}
            blocked = True
            reason = str(exc)

        executable = request.model_copy(update={"dry_run": False}).model_dump(mode="json")
        redacted = redact_tool_args(executable)
        return await self._persist_executable_request(
            action_type="drive_upload_file",
            payload_executable=executable,
            payload_redacted=redacted,
            preview=preview,
            blocked=blocked,
            reason=reason,
            requested_by=requested_by,
            approval_message="Google Drive upload requires human approval",
            metadata={"requires_approval": True, "dry_run_only": False, "google": "drive"},
        )

    async def create_drive_folder_request(
        self,
        request: DriveFolderRequest,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        service = DriveService(app_settings=self._settings)
        preview: dict[str, object]
        blocked = False
        reason: str | None = None
        try:
            preview_model = service.ensure_deliverables_folder(
                request.model_copy(update={"dry_run": True}),
                requested_by=requested_by,
            )
            preview = preview_model.model_dump(mode="json")
            status = service.status()
            if status.status != "ready":
                blocked = True
                reason = status.reason or "Google Drive is not ready."
            elif not status.write_enabled:
                blocked = True
                reason = "ENABLE_GOOGLE_DRIVE_WRITE is false; refusing executable request."
        except DriveError as exc:
            preview = {"status": "blocked", "reason": str(exc)}
            blocked = True
            reason = str(exc)

        executable = request.model_copy(update={"dry_run": False}).model_dump(mode="json")
        redacted = redact_tool_args(executable)
        return await self._persist_executable_request(
            action_type="drive_ensure_folder",
            payload_executable=executable,
            payload_redacted=redacted,
            preview=preview,
            blocked=blocked,
            reason=reason,
            requested_by=requested_by,
            approval_message="Google Drive deliverables folder creation requires human approval",
            metadata={"requires_approval": True, "dry_run_only": False, "google": "drive"},
        )

    async def create_drive_organize_request(
        self,
        request: DriveOrganizeRequest,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        service = DriveService(app_settings=self._settings)
        preview: dict[str, object]
        blocked = False
        reason: str | None = None
        frozen_file_ids: list[str] = []
        try:
            preview_model = service.organize_files(
                request.model_copy(update={"dry_run": True}),
                requested_by=requested_by,
            )
            preview = preview_model.model_dump(mode="json")
            # Freeze the exact files the operator is approving so the execute
            # path moves precisely this set (no re-search). See
            # DriveOrganizeRequest.file_ids.
            frozen_file_ids = [op.file.file_id for op in preview_model.operations]
            status = service.status()
            if status.status != "ready":
                blocked = True
                reason = status.reason or "Google Drive is not ready."
            elif not status.write_enabled:
                blocked = True
                reason = "ENABLE_GOOGLE_DRIVE_WRITE is false; refusing executable request."
        except DriveError as exc:
            preview = {"status": "blocked", "reason": str(exc)}
            blocked = True
            reason = str(exc)

        executable = request.model_copy(
            update={"dry_run": False, "file_ids": frozen_file_ids}
        ).model_dump(mode="json")
        redacted = redact_tool_args(executable)
        return await self._persist_executable_request(
            action_type="drive_organize_files",
            payload_executable=executable,
            payload_redacted=redacted,
            preview=preview,
            blocked=blocked,
            reason=reason,
            requested_by=requested_by,
            approval_message="Google Drive file organization requires human approval",
            metadata={"requires_approval": True, "dry_run_only": False, "google": "drive"},
        )

    async def create_browser_preview_request(
        self,
        request: BrowserPreviewRequest,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        service = BrowserPreviewService(self._settings)
        blocked_reason: str | None = None
        normalized_url = request.url
        try:
            normalized = service.validate(request)
            if normalized is not None:
                normalized_url = normalized[0]
        except ActionPolicyViolation as exc:
            blocked_reason = str(exc)

        preview = {
            "url": normalized_url,
            "wait_until": request.wait_until,
            "capture_screenshot": request.capture_screenshot,
            "timeout_ms": self._settings.browser_navigation_timeout_ms,
            "status": "blocked" if blocked_reason else "ok",
            "reason": blocked_reason,
        }
        payload_executable = request.model_dump(mode="json")
        payload_redacted = redact_tool_args(payload_executable)
        action_status = "blocked" if blocked_reason else "pending_approval"
        idempotency_key = _idempotency_key("browser_preview", payload_redacted)

        async with session_scope() as session:
            existing = await self._find_active_idempotent_request(
                session,
                action_type="browser_preview",
                requested_by=requested_by,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                return _view(existing)
            action_request = ActionRequest(
                action_type="browser_preview",
                status=action_status,
                requested_by=requested_by,
                idempotency_key=idempotency_key,
                payload_redacted=payload_redacted,
                payload_executable=protect_payload(payload_executable, self._settings),
                preview=preview,
                error=blocked_reason,
                metadata_json={
                    "requires_approval": True,
                    "dry_run_only": False,
                    "real_browser": True,
                },
            )
            session.add(action_request)
            await session.flush()

            if action_status == "pending_approval":
                job = Job(
                    job_type="external_action",
                    status="waiting_approval",
                    progress=0,
                    metadata_json={
                        "action_request_id": str(action_request.id),
                        "action_type": action_request.action_type,
                        "requested_by": requested_by,
                    },
                )
                session.add(job)
                await session.flush()
                approval = HumanApproval(
                    action="execute_action_request",
                    requested_action=f"execute_action_request:{action_request.id}",
                    args_redacted={
                        "action_request_id": str(action_request.id),
                        "action_type": action_request.action_type,
                        "preview": preview,
                    },
                    requested_by=requested_by,
                    job_id=job.id,
                    metadata_json={"action_request_id": str(action_request.id)},
                )
                session.add(approval)
                await session.flush()
                action_request.job_id = job.id
                action_request.approval_id = approval.id
                session.add(
                    JobEvent(
                        job_id=job.id,
                        event_type="action_approval_required",
                        status="waiting_approval",
                        message="Action request requires human approval",
                        metadata_json={
                            "action_request_id": str(action_request.id),
                            "approval_id": str(approval.id),
                        },
                    )
                )

            session.add(
                AuditEvent(
                    actor_id=requested_by,
                    action="action_request.created",
                    resource_type="action_request",
                    resource_id=str(action_request.id),
                    metadata_json={
                        "action_type": action_request.action_type,
                        "status": action_request.status,
                        "payload_redacted": payload_redacted,
                    },
                )
            )
            await session.flush()
            view = _view(action_request)
            auto_approve_eligible = (
                action_status == "pending_approval"
                and self._should_auto_approve_action("browser_preview")
                and action_request.approval_id is not None
            )
            approval_id_to_auto = action_request.approval_id if auto_approve_eligible else None

        if approval_id_to_auto is not None:
            view = await self._auto_approve_and_dispatch(
                approval_id=approval_id_to_auto,
                action_request_id=view.id,
                requested_by=requested_by,
            )
        return view

    async def create_browser_interactive_request(
        self,
        request: BrowserInteractiveRequest,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        """Persist an interactive browsing plan as an `ActionRequest`.

        The plan is validated synchronously (URL allow-list + per-step rules);
        any policy violation is recorded as `blocked` instead of `pending_approval`,
        so the operator UI shows the reason without ever queueing the worker.
        """
        service = BrowserInteractiveService(self._settings)
        blocked_reason: str | None = None
        normalized_url = request.url
        try:
            normalized = service.validate(request)
            normalized_url = normalized[0]
        except ActionPolicyViolation as exc:
            blocked_reason = str(exc)

        preview = {
            "url": normalized_url,
            "wait_until": request.wait_until,
            "step_count": len(request.steps),
            "steps": [step.model_dump(mode="json") for step in request.steps],
            "timeout_ms": self._settings.browser_navigation_timeout_ms,
            "status": "blocked" if blocked_reason else "ok",
            "reason": blocked_reason,
        }
        payload_executable = request.model_dump(mode="json")
        payload_redacted = redact_tool_args(payload_executable)
        action_status = "blocked" if blocked_reason else "pending_approval"
        idempotency_key = _idempotency_key("browser_interactive", payload_redacted)

        async with session_scope() as session:
            existing = await self._find_active_idempotent_request(
                session,
                action_type="browser_interactive",
                requested_by=requested_by,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                return _view(existing)
            action_request = ActionRequest(
                action_type="browser_interactive",
                status=action_status,
                requested_by=requested_by,
                idempotency_key=idempotency_key,
                payload_redacted=payload_redacted,
                payload_executable=protect_payload(payload_executable, self._settings),
                preview=preview,
                error=blocked_reason,
                metadata_json={
                    "requires_approval": True,
                    "dry_run_only": False,
                    "real_browser": True,
                    "interactive": True,
                },
            )
            session.add(action_request)
            await session.flush()

            if action_status == "pending_approval":
                job = Job(
                    job_type="external_action",
                    status="waiting_approval",
                    progress=0,
                    metadata_json={
                        "action_request_id": str(action_request.id),
                        "action_type": action_request.action_type,
                        "requested_by": requested_by,
                    },
                )
                session.add(job)
                await session.flush()
                approval = HumanApproval(
                    action="execute_action_request",
                    requested_action=f"execute_action_request:{action_request.id}",
                    args_redacted={
                        "action_request_id": str(action_request.id),
                        "action_type": action_request.action_type,
                        "preview": preview,
                    },
                    requested_by=requested_by,
                    job_id=job.id,
                    metadata_json={"action_request_id": str(action_request.id)},
                )
                session.add(approval)
                await session.flush()
                action_request.job_id = job.id
                action_request.approval_id = approval.id
                session.add(
                    JobEvent(
                        job_id=job.id,
                        event_type="action_approval_required",
                        status="waiting_approval",
                        message="Interactive browser plan awaiting approval",
                        metadata_json={
                            "action_request_id": str(action_request.id),
                            "approval_id": str(approval.id),
                            "step_count": len(request.steps),
                        },
                    )
                )

            session.add(
                AuditEvent(
                    actor_id=requested_by,
                    action="action_request.created",
                    resource_type="action_request",
                    resource_id=str(action_request.id),
                    metadata_json={
                        "action_type": action_request.action_type,
                        "status": action_request.status,
                        "payload_redacted": payload_redacted,
                    },
                )
            )
            await session.flush()
            view = _view(action_request)
            auto_approve_eligible = (
                action_status == "pending_approval"
                and self._should_auto_approve_action("browser_interactive")
                and action_request.approval_id is not None
            )
            approval_id_to_auto = action_request.approval_id if auto_approve_eligible else None

        if approval_id_to_auto is not None:
            view = await self._auto_approve_and_dispatch(
                approval_id=approval_id_to_auto,
                action_request_id=view.id,
                requested_by=requested_by,
            )
        return view

    async def _persist_preview_request(
        self,
        *,
        action_type: str,
        payload_redacted: dict[str, object],
        preview: dict[str, object],
        blocked: bool,
        reason: str | None,
        requested_by: str,
    ) -> ActionRequestView:
        action_status = "blocked" if blocked else "previewed"
        idempotency_key = _idempotency_key(action_type, payload_redacted)
        async with session_scope() as session:
            existing = await self._find_active_idempotent_request(
                session,
                action_type=action_type,
                requested_by=requested_by,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                return _view(existing)
            action_request = ActionRequest(
                action_type=action_type,
                status=action_status,
                requested_by=requested_by,
                idempotency_key=idempotency_key,
                payload_redacted=payload_redacted,
                preview=preview,
                error=reason if blocked else None,
                metadata_json={
                    "requires_approval": True,
                    "dry_run_only": True,
                    "preview_only": True,
                },
            )
            session.add(action_request)
            await session.flush()
            session.add(
                AuditEvent(
                    actor_id=requested_by,
                    action="action_request.created",
                    resource_type="action_request",
                    resource_id=str(action_request.id),
                    metadata_json={
                        "action_type": action_type,
                        "status": action_status,
                        "payload_redacted": payload_redacted,
                    },
                )
            )
            await session.flush()
            return _view(action_request)

    async def _persist_executable_request(
        self,
        *,
        action_type: str,
        payload_executable: dict[str, object],
        payload_redacted: dict[str, object],
        preview: dict[str, object],
        blocked: bool,
        reason: str | None,
        requested_by: str,
        approval_message: str,
        metadata: dict[str, object],
    ) -> ActionRequestView:
        action_status = "blocked" if blocked else "pending_approval"
        idempotency_key = _idempotency_key(action_type, payload_redacted)
        async with session_scope() as session:
            existing = await self._find_active_idempotent_request(
                session,
                action_type=action_type,
                requested_by=requested_by,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                return _view(existing)
            action_request = ActionRequest(
                action_type=action_type,
                status=action_status,
                requested_by=requested_by,
                idempotency_key=idempotency_key,
                payload_redacted=payload_redacted,
                payload_executable=protect_payload(payload_executable, self._settings),
                preview=preview,
                error=reason if blocked else None,
                metadata_json=metadata,
            )
            session.add(action_request)
            await session.flush()

            if action_status == "pending_approval":
                job = Job(
                    job_type="external_action",
                    status="waiting_approval",
                    progress=0,
                    metadata_json={
                        "action_request_id": str(action_request.id),
                        "action_type": action_request.action_type,
                        "requested_by": requested_by,
                    },
                )
                session.add(job)
                await session.flush()
                approval = HumanApproval(
                    action="execute_action_request",
                    requested_action=f"execute_action_request:{action_request.id}",
                    args_redacted={
                        "action_request_id": str(action_request.id),
                        "action_type": action_request.action_type,
                        "preview": preview,
                    },
                    requested_by=requested_by,
                    job_id=job.id,
                    metadata_json={"action_request_id": str(action_request.id)},
                )
                session.add(approval)
                await session.flush()
                action_request.job_id = job.id
                action_request.approval_id = approval.id
                session.add(
                    JobEvent(
                        job_id=job.id,
                        event_type="action_approval_required",
                        status="waiting_approval",
                        message=approval_message,
                        metadata_json={
                            "action_request_id": str(action_request.id),
                            "approval_id": str(approval.id),
                        },
                    )
                )

            session.add(
                AuditEvent(
                    actor_id=requested_by,
                    action="action_request.created",
                    resource_type="action_request",
                    resource_id=str(action_request.id),
                    metadata_json={
                        "action_type": action_type,
                        "status": action_status,
                        "payload_redacted": payload_redacted,
                    },
                )
            )
            await session.flush()
            view = _view(action_request)
            auto_approve_eligible = (
                action_status == "pending_approval"
                and self._should_auto_approve_action(action_type)
                and action_request.approval_id is not None
            )
            approval_id_to_auto = action_request.approval_id if auto_approve_eligible else None

        if approval_id_to_auto is not None:
            view = await self._auto_approve_and_dispatch(
                approval_id=approval_id_to_auto,
                action_request_id=view.id,
                requested_by=requested_by,
            )
        return view

    async def _auto_approve_and_dispatch(
        self,
        *,
        approval_id: UUID,
        action_request_id: UUID,
        requested_by: str,
    ) -> ActionRequestView:
        """Approve + queue + dispatch an action whitelisted by dedicated_local.

        Three-step cascade that mirrors what the REST and Telegram surfaces do
        when the operator manually approves an ActionRequest:

        1. `decide_approval` flips the HumanApproval to ``approved`` and emits
           AuditEvents atomically. Note that this only moves the AR to
           ``queued`` for the OpenShell sandbox carrier — Drive/Calendar
           ActionRequests stay in ``pending_approval``.
        2. `queue_approved_action_request` is the canonical step that flips
           the Drive/Calendar/etc AR to ``queued`` and primes the Job. Without
           this call, step 3 would find no AR in ``queued`` state and the
           dispatch silently no-ops (Fase 71 P0.1 fix from GPT-5.5 review #3).
        3. `reserve_action_dispatch` atomically reserves the AR with the
           ``submitting`` dispatch_state so a retry / duplicate trigger
           cannot fan out into two Celery tasks. Broker failures degrade to
           a warning + AuditEvent: the AR stays ``queued`` for the reaper.
        """
        try:
            await decide_approval(
                approval_id,
                status_value="approved",
                approver_user_id=f"auto:dedicated_local:{requested_by}",
                payload_resolver=None,
                app_settings=self._settings,
            )
        except ApprovalDecisionError:
            return await self._reload_view(action_request_id)

        try:
            await self.queue_approved_action_request(action_request_id)
        except ActionRequestError:
            return await self._reload_view(action_request_id)

        try:
            reservation = await self.reserve_action_dispatch(action_request_id)
        except ActionRequestError:
            return await self._reload_view(action_request_id)

        action_request = reservation.action_request
        if not reservation.should_dispatch or action_request.job_id is None:
            return action_request

        try:
            from cognitive_os.workers.tasks import run_action_request_task_async

            async_result = run_action_request_task_async.apply_async(
                args=[str(action_request.id), str(action_request.job_id)],
                queue="agent_longrun",
            )
        except Exception as exc:  # noqa: BLE001 - broker offline must not break the caller
            logger.warning(
                "auto_approve_dispatch_failed",
                extra={
                    "action_request_id": str(action_request.id),
                    "error_type": type(exc).__name__,
                },
            )
            with contextlib.suppress(Exception):
                await self.record_action_dispatch_event(
                    job_id=action_request.job_id,
                    action_request_id=action_request.id,
                    event_type="action_request_dispatch_failed",
                    status="queued",
                    message="Auto-approve dispatch failed before Celery accepted it",
                    metadata_json={
                        "error_type": type(exc).__name__,
                        "surface": "auto_approve",
                    },
                )
        else:
            with contextlib.suppress(Exception):
                dispatch_metadata: dict[str, object] = {
                    "queue": "agent_longrun",
                    "surface": "auto_approve",
                }
                task_id = _celery_task_id(async_result)
                if task_id is not None:
                    dispatch_metadata["celery_task_id"] = task_id
                await self.record_action_dispatch_event(
                    job_id=action_request.job_id,
                    action_request_id=action_request.id,
                    event_type="action_request_dispatch_submitted",
                    status="queued",
                    message="Auto-approve submitted action request to Celery",
                    metadata_json=dispatch_metadata,
                )
        return action_request

    async def _reload_view(self, action_request_id: UUID) -> ActionRequestView:
        async with session_scope() as session:
            current = await session.get(ActionRequest, action_request_id)
            if current is None:
                msg = f"Action request vanished while auto-approving: {action_request_id}"
                raise ActionRequestError(msg)
            return _view(current)

    async def cancel_action_request(
        self,
        action_request_id: UUID,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        async with session_scope() as session:
            action_request = await session.get(ActionRequest, action_request_id)
            if action_request is None:
                msg = f"Action request not found: {action_request_id}"
                raise ActionRequestError(msg)
            if action_request.status in {"completed", "failed", "cancelled", "rejected"}:
                return _view(action_request)
            if action_request.status == "running":
                msg = "Cannot cancel a running action request."
                raise ActionRequestError(msg)

            previous_status = action_request.status
            job: Job | None = None
            celery_task_id: str | None = None
            if action_request.job_id is not None:
                job = await session.get(Job, action_request.job_id)
                if job is not None:
                    raw_task_id = (job.metadata_json or {}).get("celery_task_id")
                    celery_task_id = (
                        raw_task_id if isinstance(raw_task_id, str) and raw_task_id else None
                    )
            if previous_status == "queued" and celery_task_id is not None:
                try:
                    await asyncio.to_thread(
                        celery_app.control.revoke,
                        celery_task_id,
                        terminate=True,
                        signal="SIGTERM",
                    )
                except Exception as exc:  # noqa: BLE001 - operator-facing broker failure
                    if job is not None:
                        metadata = dict(job.metadata_json or {})
                        metadata["celery_revoke_failed_at"] = datetime.now(UTC).isoformat()
                        metadata["celery_revoke_error_type"] = type(exc).__name__
                        metadata["celery_revoke_error"] = str(exc)
                        job.metadata_json = metadata
                        session.add(
                            JobEvent(
                                job_id=job.id,
                                event_type="action_request_cancel_failed",
                                status=job.status,
                                message=(
                                    "Celery revoke failed; action request status was left unchanged"
                                ),
                                metadata_json={
                                    "action_request_id": str(action_request.id),
                                    "celery_task_id": celery_task_id,
                                    "previous_status": previous_status,
                                    "error_type": type(exc).__name__,
                                    "error": str(exc),
                                },
                            )
                        )
                    session.add(
                        AuditEvent(
                            actor_id=requested_by,
                            action="action_request.cancel_failed",
                            resource_type="action_request",
                            resource_id=str(action_request.id),
                            metadata_json={
                                "action_type": action_request.action_type,
                                "previous_status": previous_status,
                                "error_type": type(exc).__name__,
                            },
                        )
                    )
                    await session.flush()
                    return _view(action_request)

            action_request.status = "cancelled"
            if job is not None:
                job.status = "cancelled"
                job.progress = 100
                job_metadata = dict(job.metadata_json or {})
                if celery_task_id is not None:
                    job_metadata["celery_revoke_requested_at"] = datetime.now(UTC).isoformat()
                    job_metadata["celery_revoke_signal"] = "SIGTERM"
                else:
                    job_metadata["cancel_without_celery_task_id"] = True
                    job_metadata["cancel_without_celery_task_id_at"] = datetime.now(UTC).isoformat()
                job.metadata_json = job_metadata
                session.add(
                    JobEvent(
                        job_id=job.id,
                        event_type="action_request_cancelled",
                        status="cancelled",
                        message="Action request cancelled by operator",
                        metadata_json={
                            "action_request_id": str(action_request.id),
                            "previous_status": previous_status,
                            "celery_task_id": celery_task_id,
                            "celery_revoke_requested": celery_task_id is not None,
                        },
                    )
                )
            session.add(
                AuditEvent(
                    actor_id=requested_by,
                    action="action_request.cancelled",
                    resource_type="action_request",
                    resource_id=str(action_request.id),
                    metadata_json={
                        "action_type": action_request.action_type,
                        "previous_status": previous_status,
                    },
                )
            )
            await session.flush()
            return _view(action_request)

    async def list_action_requests(
        self,
        *,
        limit: int = 50,
        action_type: ActionType | None = None,
        status: ActionRequestStatus | None = None,
    ) -> list[ActionRequestView]:
        bounded_limit = max(1, min(limit, 200))
        async with session_scope() as session:
            stmt = select(ActionRequest).order_by(desc(ActionRequest.created_at))
            if action_type is not None:
                stmt = stmt.where(ActionRequest.action_type == action_type)
            if status is not None:
                stmt = stmt.where(ActionRequest.status == status)
            stmt = stmt.limit(bounded_limit)
            result = await session.execute(stmt)
            return [_view(action_request) for action_request in result.scalars().all()]

    async def get_action_request(self, action_request_id: UUID) -> ActionRequestView | None:
        async with session_scope() as session:
            action_request = await session.get(ActionRequest, action_request_id)
            return _view(action_request) if action_request is not None else None

    async def export_workflow(
        self,
        action_request_id: UUID,
        *,
        exported_by: str | None,
    ) -> WorkflowDocument | None:
        """Serialize an ActionRequest into a `workflow.v1` document.

        The export uses the **redacted** payload as the public surface; any
        encrypted-at-rest secrets stay server-side. Returns None when the row
        does not exist; raises `ActionRequestError` when the action type is
        not exportable as a workflow.
        """
        async with session_scope() as session:
            row = await session.get(ActionRequest, action_request_id)
            if row is None:
                return None
            if row.action_type not in WORKFLOW_EXPORTABLE_TYPES:
                msg = f"action_type {row.action_type!r} is not exportable as workflow.v1"
                raise ActionRequestError(msg)
            return WorkflowDocument(
                action_type=cast("WorkflowActionType", row.action_type),
                payload=dict(row.payload_redacted or {}),
                preview=dict(row.preview or {}) or None,
                source=WorkflowSource(
                    exported_at=datetime.now(UTC),
                    exported_by=exported_by,
                    source_action_request_id=row.id,
                ),
            )

    async def create_from_workflow(
        self,
        document: WorkflowDocument,
        *,
        requested_by: str,
    ) -> ActionRequestView:
        """Re-create an ActionRequest from a `workflow.v1` document.

        Dispatches by `action_type` to the existing `create_*_request` carrils
        so all guardrails (allow-lists, approval, idempotency, encryption)
        apply exactly as if the operator had submitted the request through
        the standard endpoint.
        """
        if document.workflow_version != "1.0":
            msg = f"Unsupported workflow version: {document.workflow_version!r}"
            raise ActionRequestError(msg)
        payload = dict(document.payload or {})
        action_type = document.action_type
        if action_type == "computer_organize":
            return await self.create_computer_organize_request(
                ComputerOrganizeRequest.model_validate(payload),
                requested_by=requested_by,
            )
        if action_type == "godaddy_dns_change":
            return await self.create_godaddy_dns_change_request(
                GoDaddyDnsRecordChange.model_validate(payload),
                requested_by=requested_by,
            )
        if action_type == "document_generate":
            return await self.create_document_generate_request(
                DocumentGenerateRequest.model_validate(payload),
                requested_by=requested_by,
            )
        if action_type == "browser_preview":
            return await self.create_browser_preview_request(
                BrowserPreviewRequest.model_validate(payload),
                requested_by=requested_by,
            )
        if action_type == "browser_interactive":
            return await self.create_browser_interactive_request(
                BrowserInteractiveRequest.model_validate(payload),
                requested_by=requested_by,
            )
        if action_type == "calendar_create_event":
            return await self.create_calendar_event_request(
                EventCreateRequest.model_validate(payload),
                requested_by=requested_by,
            )
        if action_type == "drive_upload_file":
            return await self.create_drive_upload_request(
                DriveUploadRequest.model_validate(payload),
                requested_by=requested_by,
            )
        if action_type == "drive_ensure_folder":
            return await self.create_drive_folder_request(
                DriveFolderRequest.model_validate(payload),
                requested_by=requested_by,
            )
        if action_type == "drive_organize_files":
            return await self.create_drive_organize_request(
                DriveOrganizeRequest.model_validate(payload),
                requested_by=requested_by,
            )
        msg = f"Unsupported workflow action_type: {action_type!r}"
        raise ActionRequestError(msg)

    async def queue_approved_action_request(self, action_request_id: UUID) -> ActionRequestView:
        async with session_scope() as session:
            stmt = (
                select(ActionRequest).where(ActionRequest.id == action_request_id).with_for_update()
            )
            action_request = (await session.execute(stmt)).scalar_one_or_none()
            if action_request is None:
                msg = (
                    "Action request not found; dispatch blocked before side effects: "
                    f"{action_request_id}"
                )
                raise ActionRequestError(msg)
            if action_request.status in {
                "cancelled",
                "completed",
                "failed",
                "queued",
                "rejected",
                "running",
            }:
                return _view(action_request)
            if action_request.status in {"blocked", "previewed"}:
                msg = f"Action request is not executable: {action_request.status}"
                raise ActionRequestError(msg)
            if action_request.approval_id is None or action_request.job_id is None:
                msg = "Action request has no approval/job gate."
                raise ActionRequestError(msg)

            approval = await session.get(HumanApproval, action_request.approval_id)
            if approval is None:
                msg = "Action request approval not found."
                raise ActionRequestError(msg)
            job = await session.get(Job, action_request.job_id)
            if job is None:
                msg = "Action request job not found."
                raise ActionRequestError(msg)
            if approval.status == "rejected":
                action_request.status = "rejected"
                job.status = "rejected"
                job.progress = 100
                session.add(
                    JobEvent(
                        job_id=job.id,
                        event_type="action_request_rejected",
                        status="rejected",
                        message="Action request approval was rejected",
                        metadata_json={"action_request_id": str(action_request.id)},
                    )
                )
                await session.flush()
                return _view(action_request)
            if approval.status != "approved":
                msg = "Action request is waiting for approval."
                raise ActionRequestError(msg)

            action_request.status = "queued"
            job.status = "queued"
            job.progress = 0
            session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="action_request_queued",
                    status="queued",
                    message="Approved action request queued",
                    metadata_json={"action_request_id": str(action_request.id)},
                )
            )
            await session.flush()
            return _view(action_request)

    async def reserve_action_dispatch(self, action_request_id: UUID) -> ActionDispatchReservation:
        async with session_scope() as session:
            stmt = (
                select(ActionRequest).where(ActionRequest.id == action_request_id).with_for_update()
            )
            action_request = (await session.execute(stmt)).scalar_one_or_none()
            if action_request is None:
                msg = f"Action request not found: {action_request_id}"
                raise ActionRequestError(msg)
            if action_request.status != "queued":
                return ActionDispatchReservation(
                    action_request=_view(action_request),
                    should_dispatch=False,
                    reason=f"Action request status is {action_request.status}; nothing queued.",
                )

            metadata = dict(action_request.metadata_json or {})
            dispatch_state = str(metadata.get("dispatch_state") or "")
            if dispatch_state == "submitted":
                return ActionDispatchReservation(
                    action_request=_view(action_request),
                    should_dispatch=False,
                    reason="Action request dispatch already submitted; waiting for worker.",
                )
            if dispatch_state == "submitting":
                return ActionDispatchReservation(
                    action_request=_view(action_request),
                    should_dispatch=False,
                    reason="Action request dispatch already in progress.",
                )

            metadata["dispatch_state"] = "submitting"
            metadata["dispatch_claimed_at"] = datetime.now(UTC).isoformat()
            action_request.metadata_json = metadata
            await session.flush()
            return ActionDispatchReservation(
                action_request=_view(action_request),
                should_dispatch=True,
            )

    async def record_action_dispatch_event(
        self,
        *,
        job_id: UUID,
        action_request_id: UUID,
        event_type: str,
        status: str,
        message: str,
        metadata_json: dict[str, object] | None = None,
    ) -> None:
        async with session_scope() as session:
            action_request = await session.get(ActionRequest, action_request_id)
            if action_request is not None:
                metadata = dict(action_request.metadata_json or {})
                metadata.pop("dispatch_claimed_at", None)
                if event_type == "action_request_dispatch_submitted":
                    metadata["dispatch_state"] = "submitted"
                    metadata["dispatch_submitted_at"] = datetime.now(UTC).isoformat()
                    queue_name = (metadata_json or {}).get("queue")
                    if isinstance(queue_name, str):
                        metadata["dispatch_queue"] = queue_name
                    metadata.pop("dispatch_last_error_type", None)
                elif event_type == "action_request_dispatch_failed":
                    metadata["dispatch_state"] = "failed"
                    metadata["dispatch_failed_at"] = datetime.now(UTC).isoformat()
                    error_type = (metadata_json or {}).get("error_type")
                    if isinstance(error_type, str):
                        metadata["dispatch_last_error_type"] = error_type
                action_request.metadata_json = metadata
            job = await session.get(Job, job_id)
            if job is not None:
                job_metadata = dict(job.metadata_json or {})
                celery_task_id = (metadata_json or {}).get("celery_task_id")
                if isinstance(celery_task_id, str) and celery_task_id:
                    job_metadata["celery_task_id"] = celery_task_id
                    job_metadata["celery_task_name"] = "action_request"
                queue_name = (metadata_json or {}).get("queue")
                if isinstance(queue_name, str):
                    job_metadata["celery_queue"] = queue_name
                surface_name = (metadata_json or {}).get("surface")
                if isinstance(surface_name, str):
                    job_metadata["celery_surface"] = surface_name
                if event_type == "action_request_dispatch_submitted":
                    job_metadata["celery_submitted_at"] = datetime.now(UTC).isoformat()
                elif event_type == "action_request_dispatch_failed":
                    error_type = (metadata_json or {}).get("error_type")
                    if isinstance(error_type, str):
                        job_metadata["celery_dispatch_error_type"] = error_type
                    job_metadata["celery_dispatch_failed_at"] = datetime.now(UTC).isoformat()
                job.metadata_json = job_metadata
            session.add(
                JobEvent(
                    job_id=job_id,
                    event_type=event_type,
                    status=status,
                    message=message,
                    metadata_json={
                        "action_request_id": str(action_request_id),
                        **(metadata_json or {}),
                    },
                )
            )
            await session.flush()

    async def execute_action_request(self, action_request_id: UUID) -> ActionRequestView:
        # Atomic state transition: SELECT ... FOR UPDATE locks the row, and we only
        # promote to "running" from "queued". Any concurrent worker that already
        # transitioned the row will see status="running" and exit without re-executing.
        async with session_scope() as session:
            stmt = (
                select(ActionRequest).where(ActionRequest.id == action_request_id).with_for_update()
            )
            action_request = (await session.execute(stmt)).scalar_one_or_none()
            if action_request is None:
                msg = f"Action request not found: {action_request_id}"
                raise ActionRequestError(msg)
            if action_request.status == "running":
                return _view(action_request)
            if action_request.status in {"completed", "failed", "cancelled", "rejected"}:
                return _view(action_request)
            if action_request.status != "queued":
                msg = (
                    f"Action request not executable from status {action_request.status!r}; "
                    "expected 'queued'."
                )
                raise ActionRequestError(msg)
            action_request.status = "running"
            action_request.error = None
            await session.flush()

        try:
            result = await self._execute(action_request_id)
        except Exception as exc:
            await self._mark_failed(action_request_id, f"{type(exc).__name__}: {exc}")
            raise

        async with session_scope() as session:
            action_request = await session.get(ActionRequest, action_request_id)
            if action_request is None:
                msg = f"Action request not found after execution: {action_request_id}"
                raise ActionRequestError(msg)
            action_request.result = result
            action_request.status = "completed" if result.get("status") == "completed" else "failed"
            raw_reason = result.get("reason")
            action_request.error = raw_reason if isinstance(raw_reason, str) else None
            session.add(
                AuditEvent(
                    actor_id=action_request.requested_by,
                    action="action_request.executed",
                    resource_type="action_request",
                    resource_id=str(action_request.id),
                    metadata_json={
                        "action_type": action_request.action_type,
                        "status": action_request.status,
                        "result": result,
                    },
                )
            )
            await session.flush()
            return _view(action_request)

    async def _execute(self, action_request_id: UUID) -> dict[str, object]:
        async with session_scope() as session:
            action_request = await session.get(ActionRequest, action_request_id)
            if action_request is None:
                msg = f"Action request not found: {action_request_id}"
                raise ActionRequestError(msg)
            action_type = action_request.action_type
            # Prefer the unredacted execution payload; fall back to redacted only when
            # the row predates the payload_executable migration. This prevents `_execute`
            # from running with `[REDACTED]` literals injected by the audit redactor.
            payload = reveal_payload(
                action_request.payload_executable,
                action_request.payload_redacted,
                self._settings,
            )
            preview = dict(action_request.preview)

        if action_type == "computer_organize":
            computer_service = ComputerActionService(self._settings)
            # Execute the operator-approved plan stored in `preview` rather than
            # recomputing the plan from a fresh filesystem scan. Otherwise the human
            # approval guarantee is meaningless: the operator approves plan A but the
            # worker would execute whatever plan B looks like at execute-time.
            approved_plan = _try_parse_computer_plan(preview)
            if approved_plan is not None:
                exec_result = computer_service.execute_approved_plan(approved_plan)
            else:
                exec_result = computer_service.execute_organize_plan(
                    ComputerOrganizeRequest.model_validate(payload)
                )
            return exec_result.model_dump(mode="json")

        if action_type == "document_generate":
            doc_result = DocumentActionService(self._settings).execute(
                DocumentGenerateRequest.model_validate(payload)
            )
            return doc_result.model_dump(mode="json")

        if action_type == "browser_preview":
            preview_result = BrowserPreviewService(self._settings).execute(
                BrowserPreviewRequest.model_validate(payload)
            )
            return preview_result.model_dump(mode="json")

        if action_type == "browser_interactive":
            interactive_result = BrowserInteractiveService(self._settings).execute(
                BrowserInteractiveRequest.model_validate(payload)
            )
            return interactive_result.model_dump(mode="json")

        if action_type == "godaddy_dns_change":
            dns_result = GoDaddyActionService(self._settings).execute_dns_change(
                GoDaddyDnsRecordChange.model_validate(payload)
            )
            return dns_result.model_dump(mode="json")

        if action_type == "calendar_create_event":
            calendar_result = CalendarService(app_settings=self._settings).create_event(
                EventCreateRequest.model_validate(payload),
                requested_by=action_request.requested_by,
            )
            dumped = calendar_result.model_dump(mode="json")
            if calendar_result.status == "created":
                return {**dumped, "status": "completed"}
            return {**dumped, "status": "failed"}

        if action_type == "drive_upload_file":
            drive_result = DriveService(app_settings=self._settings).upload_file(
                DriveUploadRequest.model_validate(payload),
                requested_by=action_request.requested_by,
            )
            dumped = drive_result.model_dump(mode="json")
            if drive_result.status == "uploaded":
                return {**dumped, "status": "completed"}
            return {**dumped, "status": "failed"}

        if action_type == "drive_ensure_folder":
            folder_result = DriveService(app_settings=self._settings).ensure_deliverables_folder(
                DriveFolderRequest.model_validate(payload),
                requested_by=action_request.requested_by,
            )
            dumped = folder_result.model_dump(mode="json")
            if folder_result.status in {"ready", "created"}:
                return {**dumped, "status": "completed"}
            return {**dumped, "status": "failed"}

        if action_type == "drive_organize_files":
            organize_result = DriveService(app_settings=self._settings).organize_files(
                DriveOrganizeRequest.model_validate(payload),
                requested_by=action_request.requested_by,
            )
            dumped = organize_result.model_dump(mode="json")
            if organize_result.status == "completed":
                return {**dumped, "status": "completed"}
            return {**dumped, "status": "failed"}

        return {
            "status": "failed",
            "reason": f"No executor is enabled for action type: {action_type}",
        }

    async def reap_stuck_running(self, *, max_minutes: int | None = None) -> int:
        """Mark `running` action requests older than the cap as `failed`.

        A Celery worker that died mid-execution leaves the row stuck in `running`
        forever (no heartbeat in the schema). This reaper is the safety net:
        it walks all stale rows, marks them `failed`, links a JobEvent and an
        AuditEvent, and returns how many it touched. Designed to run on Celery
        beat (see `cognitive_os.workers.tasks.reap_stuck_action_requests_task`).
        """
        threshold = max_minutes or self._settings.action_request_running_max_minutes
        cutoff = datetime.now(UTC) - timedelta(minutes=max(1, threshold))
        reaped = 0
        async with session_scope() as session:
            stmt = (
                select(ActionRequest)
                .where(ActionRequest.status == "running")
                .where(ActionRequest.updated_at < cutoff)
            )
            stuck = (await session.execute(stmt)).scalars().all()
            for action_request in stuck:
                reason = (
                    f"reaper: action request stuck in 'running' for more than "
                    f"{threshold} minutes; the worker likely died."
                )
                action_request.status = "failed"
                action_request.error = reason
                action_request.result = {"status": "failed", "reason": reason}
                if action_request.job_id is not None:
                    job = await session.get(Job, action_request.job_id)
                    if job is not None and job.status not in {"completed", "failed", "cancelled"}:
                        job.status = "failed"
                        job.progress = 100
                        session.add(
                            JobEvent(
                                job_id=job.id,
                                event_type="action_request_reaped",
                                status="failed",
                                message=reason,
                                metadata_json={
                                    "action_request_id": str(action_request.id),
                                    "stuck_since": action_request.updated_at.isoformat(),
                                },
                            )
                        )
                session.add(
                    AuditEvent(
                        actor_id="system.reaper",
                        action="action_request.reaped",
                        resource_type="action_request",
                        resource_id=str(action_request.id),
                        metadata_json={
                            "action_type": action_request.action_type,
                            "stuck_since": action_request.updated_at.isoformat(),
                            "threshold_minutes": threshold,
                        },
                    )
                )
                reaped += 1
        return reaped

    async def reap_stale_dispatch_reservations(self, *, max_minutes: int | None = None) -> int:
        """Unstick ActionRequests whose dispatch reservation never resolved.

        `reserve_action_dispatch` writes `metadata_json.dispatch_state =
        'submitting'` before `apply_async`. If the process dies between the
        reservation and the actual dispatch (or before the
        submitted/failed event is recorded), the row stays `status='queued'`
        with a sticky `submitting`/`submitted` and `reserve_action_dispatch`
        refuses to ever dispatch it again — the action is stranded.

        This sweeper ages those reservations out: a dispatch should resolve
        in seconds, so a still-`queued` row whose reservation is older than
        the cap is dead. We set `dispatch_state='failed'` (NOT remove it):
        per the Fase 64 contract `failed` is the one state that *allows*
        re-dispatch, so the next dispatch attempt (panel auto-dispatch,
        Telegram, or REST) can re-reserve and proceed. Returns how many it
        unstuck. Runs on Celery beat alongside the other reapers.
        """
        threshold = max_minutes or max(5, self._settings.action_request_running_max_minutes)
        cutoff = datetime.now(UTC) - timedelta(minutes=max(1, threshold))
        swept = 0
        async with session_scope() as session:
            stmt = (
                select(ActionRequest)
                .where(ActionRequest.status == "queued")
                .where(ActionRequest.updated_at < cutoff)
            )
            rows = (await session.execute(stmt)).scalars().all()
            for action_request in rows:
                metadata = dict(action_request.metadata_json or {})
                dispatch_state = str(metadata.get("dispatch_state") or "")
                if dispatch_state not in {"submitting", "submitted"}:
                    continue
                metadata["dispatch_state"] = "failed"
                metadata["dispatch_reaped_at"] = datetime.now(UTC).isoformat()
                metadata["dispatch_last_error_type"] = "DispatchReservationStale"
                metadata.pop("dispatch_claimed_at", None)
                action_request.metadata_json = metadata
                if action_request.job_id is not None:
                    session.add(
                        JobEvent(
                            job_id=action_request.job_id,
                            event_type="action_request_dispatch_reservation_reaped",
                            status="queued",
                            message=(
                                "Stale dispatch reservation cleared; the action "
                                "can be dispatched again."
                            ),
                            metadata_json={
                                "action_request_id": str(action_request.id),
                                "previous_dispatch_state": dispatch_state,
                                "threshold_minutes": threshold,
                            },
                        )
                    )
                session.add(
                    AuditEvent(
                        actor_id="system.reaper",
                        action="action_request.dispatch_reservation_reaped",
                        resource_type="action_request",
                        resource_id=str(action_request.id),
                        metadata_json={
                            "action_type": action_request.action_type,
                            "previous_dispatch_state": dispatch_state,
                            "threshold_minutes": threshold,
                        },
                    )
                )
                swept += 1
        return swept

    async def reap_stale_pending_approvals(self, *, max_hours: int | None = None) -> int:
        """Flip `pending` HumanApproval rows older than the cap to `expired`.

        A pending approval that never got decided is a liability: if the operator
        approves it tomorrow, an action that made sense yesterday may execute now
        against stale state. The reaper closes the loop by aging out stale rows
        and cascading the rejection to any linked Job/ActionRequest.
        """
        threshold = max_hours or self._settings.approval_pending_max_hours
        cutoff = datetime.now(UTC) - timedelta(hours=max(1, threshold))
        reaped = 0
        async with session_scope() as session:
            stmt = (
                select(HumanApproval)
                .where(HumanApproval.status == "pending")
                .where(HumanApproval.created_at < cutoff)
            )
            stale = (await session.execute(stmt)).scalars().all()
            for approval in stale:
                approval.status = "expired"
                approval.decided_at = datetime.now(UTC)
                if approval.job_id is not None:
                    job = await session.get(Job, approval.job_id)
                    if job is not None and job.status not in {
                        "completed",
                        "failed",
                        "cancelled",
                        "rejected",
                    }:
                        job.status = "rejected"
                        job.progress = 100
                        session.add(
                            JobEvent(
                                job_id=job.id,
                                event_type="approval_expired",
                                status="rejected",
                                message="Approval expired by reaper",
                                metadata_json={
                                    "approval_id": str(approval.id),
                                    "threshold_hours": threshold,
                                },
                            )
                        )
                action_request_row = (
                    await session.execute(
                        select(ActionRequest).where(ActionRequest.approval_id == approval.id)
                    )
                ).scalar_one_or_none()
                if action_request_row is not None and action_request_row.status not in {
                    "completed",
                    "failed",
                    "cancelled",
                    "rejected",
                }:
                    action_request_row.status = "rejected"
                    action_request_row.error = "Approval expired before decision"
                session.add(
                    AuditEvent(
                        actor_id="system.reaper",
                        action="approval.expired",
                        resource_type="human_approval",
                        resource_id=str(approval.id),
                        metadata_json={
                            "requested_action": approval.requested_action,
                            "requested_by": approval.requested_by,
                            "threshold_hours": threshold,
                        },
                    )
                )
                reaped += 1
        return reaped

    async def _mark_failed(self, action_request_id: UUID, detail: str) -> None:
        async with session_scope() as session:
            action_request = await session.get(ActionRequest, action_request_id)
            if action_request is None:
                return
            action_request.status = "failed"
            action_request.error = detail
            action_request.result = {"status": "failed", "reason": detail}


def _initial_status(*, blocked: bool, dry_run_only: bool) -> str:
    if blocked:
        return "blocked"
    if dry_run_only:
        return "previewed"
    return "pending_approval"


def _try_parse_computer_plan(preview: dict[str, object]) -> ComputerOrganizePlan | None:
    """Best-effort parse of a stored preview JSON back into a typed plan.

    Returns None when the preview is missing/malformed (e.g., an old row created
    before the preview-driven executor existed), so callers can fall back to the
    legacy "recompute the plan" path without crashing.
    """
    if not preview:
        return None
    try:
        return ComputerOrganizePlan.model_validate(preview)
    except Exception:
        return None


def _idempotency_key(action_type: str, payload: dict[str, object]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{action_type}:{rendered}".encode()).hexdigest()


def _view(action_request: ActionRequest) -> ActionRequestView:
    return ActionRequestView(
        id=action_request.id,
        action_type=cast("ActionType", action_request.action_type),
        status=cast("ActionRequestStatus", action_request.status),
        requested_by=action_request.requested_by,
        approval_id=action_request.approval_id,
        job_id=action_request.job_id,
        payload_redacted=action_request.payload_redacted,
        preview=action_request.preview,
        result=action_request.result,
        error=action_request.error,
        created_at=action_request.created_at,
        updated_at=action_request.updated_at,
    )

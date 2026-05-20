from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from celery import Task

from cognitive_os.actions.gmail_digest import (
    GmailDigestService,
    GmailRestReader,
    render_gmail_digest_telegram,
)
from cognitive_os.actions.schemas import GmailDigestRequest
from cognitive_os.actions.service import ActionRequestService
from cognitive_os.assist.reminders import deliver_personal_task_reminders
from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import Job, JobEvent
from cognitive_os.deepagents.document_analysis.schemas import DocumentAnalysisTask
from cognitive_os.deepagents.document_analysis.service import DocumentAnalysisService
from cognitive_os.deepagents.failure_postmortem import scan_recent_jobs as scan_failure_patterns
from cognitive_os.deepagents.memory_consolidation import DeepAgentMemoryConsolidator
from cognitive_os.deepagents.openshell_adapter import OpenShellAdapter
from cognitive_os.deepagents.openshell_policy import OpenShellPolicyViolation
from cognitive_os.deepagents.openshell_schemas import OpenShellTask
from cognitive_os.deepagents.recipe_extractor import extract_pending_recipes
from cognitive_os.deepagents.research_deepagent import create_workspace
from cognitive_os.deepagents.schemas import DeepAgentTask
from cognitive_os.deepagents.service import run_deepagent_task
from cognitive_os.ingestion.pipeline import DocumentIngestionPipeline
from cognitive_os.integrations.telegram_notify import send_telegram_markdown
from cognitive_os.mail.service import PersonalMailService
from cognitive_os.workers.celery_app import celery_app

TRANSIENT_EXCEPTIONS = (ConnectionError, TimeoutError, httpx.TimeoutException)
_ACTION_REQUEST_TERMINAL_JOB_STATUS = {
    "completed": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
    "rejected": "rejected",
}


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


async def _create_job(
    *,
    job_type: str,
    status: str,
    progress: int,
    metadata_json: dict[str, Any] | None = None,
) -> UUID:
    async with session_scope() as session:
        job = Job(
            job_type=job_type,
            status=status,
            progress=progress,
            metadata_json=metadata_json or {},
        )
        session.add(job)
        await session.flush()
        return job.id


async def _update_job(
    job_id: UUID,
    *,
    status: str,
    progress: int | None = None,
    event_type: str,
    message: str,
    metadata_json: dict[str, Any] | None = None,
) -> None:
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        if job is None:
            msg = f"Job not found: {job_id}"
            raise ValueError(msg)
        job.status = status
        if progress is not None:
            job.progress = progress
        if metadata_json:
            job.metadata_json = {**job.metadata_json, **metadata_json}
        session.add(
            JobEvent(
                job_id=job_id,
                event_type=event_type,
                status=status,
                message=message,
                metadata_json=metadata_json or {},
            )
        )


async def _read_job_status(job_id: UUID) -> str | None:
    """Return the current status string for `job_id`, or None when missing.

    Used by Celery tasks to short-circuit retries on jobs that already reached
    a terminal state (worker crashed between DB commit and Celery ACK).
    """
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        return None if job is None else job.status


async def _read_action_request_status(action_request_id: UUID) -> str | None:
    """Current status of an ActionRequest, or None when missing.

    The worker sets Job→running BEFORE ActionRequestService flips the
    ActionRequest queued→running. If the worker crashes in that window, a
    Celery retry that only looked at Job.status would short-circuit and
    strand the ActionRequest in `queued` forever. Reading the AR status lets
    the retry distinguish "genuine duplicate (AR running/terminal)" from
    "crashed in the window (AR still queued/pending → must proceed)".
    `execute_action_request` is itself atomic (SELECT ... FOR UPDATE, only
    promotes from `queued`), so proceeding is always safe.
    """
    from cognitive_os.db.models import ActionRequest  # noqa: PLC0415

    async with session_scope() as session:
        ar = await session.get(ActionRequest, action_request_id)
        return None if ar is None else ar.status


async def _reserve_code_build_job(job_id: UUID) -> tuple[str, str | None]:
    """Atomically claim a Code Director build job for execution.

    Returns ``("claimed", previous_status)`` when this caller transitioned the
    job from ``queued``/``submitted``/``submitting`` to ``running``, or
    ``("skip", current_status)`` when the job is missing / already terminal /
    already running by another worker. The previous-status helper distinguishes
    "duplicate dispatch (already running)" from "worker re-entry on terminal"
    so the caller logs the right thing.

    Why atomic: ``_read_job_status`` + later UPDATE is a check-then-act race;
    two Celery workers can each read ``queued`` and both invoke ``run_build``
    against the same workspace (Fase 69 P0.4 — GPT-5.5 review #2).
    """
    from sqlalchemy import update  # noqa: PLC0415

    async with session_scope() as session:
        current_job = await session.get(Job, job_id)
        if current_job is None:
            return ("skip", None)
        current_status = current_job.status
        if current_status in {"completed", "failed", "cancelled", "rejected"}:
            return ("skip", current_status)
        if current_status == "running":
            return ("skip", current_status)
        result = await session.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.status.in_(("queued", "submitting", "submitted")),
            )
            .values(status="running", updated_at=datetime.now(UTC))
        )
        rowcount = getattr(result, "rowcount", 0) or 0
        if rowcount == 0:
            # Another worker raced us between SELECT and UPDATE.
            refreshed = await session.get(Job, job_id)
            return ("skip", refreshed.status if refreshed is not None else None)
        session.add(
            JobEvent(
                job_id=job_id,
                event_type="code_build_dispatch_reserved",
                status="running",
                message=f"Reserved for execution (from status={current_status}).",
                metadata_json={"previous_status": current_status},
            )
        )
        return ("claimed", current_status)


async def _mark_job_failed(job_id: UUID, exc: Exception) -> None:
    await _update_job(
        job_id,
        status="failed",
        progress=None,
        event_type="task_failed",
        message=f"{type(exc).__name__}: {exc}",
        metadata_json={"error_type": type(exc).__name__},
    )


@celery_app.task(
    bind=True,
    name="cognitive_os.ingest_pdf",
    autoretry_for=TRANSIENT_EXCEPTIONS,
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def ingest_pdf_task(self: Task, document_path: str, job_id: str) -> dict[str, Any]:
    del self
    active_job_id = UUID(job_id)
    try:
        _run(
            _update_job(
                active_job_id,
                status="running",
                progress=1,
                event_type="task_started",
                message="Celery ingestion task started",
            )
        )
        result = _run(
            DocumentIngestionPipeline().ingest_pdf_for_job(
                Path(document_path),
                job_id=active_job_id,
            )
        )
        return {
            "job_id": str(active_job_id),
            "document_id": str(result.document_id),
            "pages": len(result.pages),
            "chunks": len(result.chunks),
            "warnings": result.warnings,
        }
    except Exception as exc:
        _run(_mark_job_failed(active_job_id, exc))
        raise


@celery_app.task(name="cognitive_os.health_check")
def health_check_task() -> dict[str, Any]:
    job_id = _run(
        _create_job(
            job_type="health_check",
            status="running",
            progress=0,
            metadata_json={"task": "health_check"},
        )
    )
    try:
        _run(
            _update_job(
                job_id,
                status="completed",
                progress=100,
                event_type="health_check_completed",
                message="Celery health check completed",
            )
        )
        return {"ok": True, "job_id": str(job_id)}
    except Exception as exc:
        _run(_mark_job_failed(job_id, exc))
        raise


@celery_app.task(
    name="cognitive_os.cleanup_old_jobs",
    autoretry_for=TRANSIENT_EXCEPTIONS,
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def cleanup_old_jobs_task(days: int = 30) -> dict[str, Any]:
    job_id = _run(
        _create_job(
            job_type="cleanup_old_jobs",
            status="running",
            progress=0,
            metadata_json={"days": days},
        )
    )
    try:
        cleaned_count = _run(_cleanup_old_terminal_jobs(days=days))
        _run(
            _update_job(
                job_id,
                status="completed",
                progress=100,
                event_type="cleanup_completed",
                message=f"Checked old terminal jobs; marked {cleaned_count}",
                metadata_json={"cleaned_count": cleaned_count},
            )
        )
        return {"job_id": str(job_id), "cleaned_count": cleaned_count}
    except Exception as exc:
        _run(_mark_job_failed(job_id, exc))
        raise


@celery_app.task(name="cognitive_os.debug_fast")
def debug_fast_task(value: str = "ok") -> dict[str, str]:
    job_id = _run(
        _create_job(
            job_type="debug_fast",
            status="running",
            progress=0,
            metadata_json={"value": value},
        )
    )
    _run(
        _update_job(
            job_id,
            status="completed",
            progress=100,
            event_type="debug_fast_completed",
            message="Debug fast task completed",
            metadata_json={"value": value},
        )
    )
    return {"value": value, "job_id": str(job_id)}


@celery_app.task(
    name="cognitive_os.sync_personal_mail",
    autoretry_for=TRANSIENT_EXCEPTIONS,
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def sync_personal_mail_task() -> dict[str, Any]:
    job_id = _run(
        _create_job(
            job_type="personal_mail_sync",
            status="running",
            progress=0,
            metadata_json={"task": "sync_personal_mail"},
        )
    )
    try:
        result = _run(PersonalMailService().sync_now())
        # Fase 72 D: si el sync tuvo errores parciales (uno de los providers
        # falló) reportamos `completed_with_warnings` en vez de `completed`,
        # y promovemos los errores a campo top-level en metadata para que la
        # UI los muestre sin tener que abrir el JSON entero.
        had_errors = bool(result.errors)
        final_status = "completed_with_warnings" if had_errors else "completed"
        event_type = (
            "personal_mail_sync_completed_with_warnings"
            if had_errors
            else "personal_mail_sync_completed"
        )
        message = (
            f"Fetched {result.fetched}; inserted {result.inserted}; errors={len(result.errors)}"
            if had_errors
            else f"Fetched {result.fetched}; inserted {result.inserted}"
        )
        _run(
            _update_job(
                job_id,
                status=final_status,
                progress=100,
                event_type=event_type,
                message=message,
                metadata_json=result.model_dump(mode="json"),
            )
        )
        return {"job_id": str(job_id), **result.model_dump(mode="json")}
    except Exception as exc:
        _run(_mark_job_failed(job_id, exc))
        raise


@celery_app.task(name="cognitive_os.run_deepagent_task")
def run_deepagent_task_async(task_dict: dict[str, Any], job_id: str) -> dict[str, Any]:
    active_job_id = UUID(job_id)
    task = DeepAgentTask.model_validate(task_dict)
    try:
        _run(
            _update_job(
                active_job_id,
                status="running",
                progress=5,
                event_type="started",
                message="DeepAgent task started",
                metadata_json={"task_id": task.task_id, "task_type": task.task_type},
            )
        )
        workspace = create_workspace(task)
        _run(
            _update_job(
                active_job_id,
                status="running",
                progress=10,
                event_type="workspace_created",
                message="DeepAgent workspace created",
                metadata_json={"task_id": task.task_id},
            )
        )
        _run(
            _update_job(
                active_job_id,
                status="running",
                progress=20,
                event_type="agent_started",
                message="DeepAgent invocation started",
            )
        )
        result = run_deepagent_task(task)
        (workspace.root_dir / "result.json").write_text(
            json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        terminal_status = "completed" if result.status in {"ok", "needs_more_info"} else "failed"
        _run(
            _update_job(
                active_job_id,
                status=terminal_status,
                progress=100,
                event_type="agent_finished",
                message=f"DeepAgent task finished with status {result.status}",
                metadata_json={"result": result.model_dump(mode="json")},
            )
        )
        return result.model_dump(mode="json")
    except Exception as exc:
        _run(_mark_job_failed(active_job_id, exc))
        raise


@celery_app.task(name="cognitive_os.run_openshell_task")
def run_openshell_task_async(task_dict: dict[str, Any], job_id: str) -> dict[str, Any]:
    active_job_id = UUID(job_id)
    task = OpenShellTask.model_validate(task_dict)
    existing_status = _run(_read_job_status(active_job_id))
    if existing_status in {"completed", "failed", "cancelled", "rejected"}:
        return {
            "job_id": job_id,
            "status": existing_status,
            "skipped": True,
            "reason": "Worker re-entry on a job already in a terminal state.",
        }
    if existing_status == "running":
        # Duplicate dispatch (same approval decided twice) — already in
        # flight. Same idempotency guard as run_action_request/code_build.
        return {
            "job_id": job_id,
            "status": existing_status,
            "skipped": True,
            "reason": "Duplicate dispatch: an OpenShell task for this job is already running.",
        }
    try:
        _run(
            _update_job(
                active_job_id,
                status="running",
                progress=2,
                event_type="openshell_task_received",
                message="OpenShell task received",
                metadata_json={"task_id": task.task_id, "thread_id": task.thread_id},
            )
        )
        _run(
            _update_job(
                active_job_id,
                status="running",
                progress=8,
                event_type="openshell_policy_validated",
                message="OpenShell policy validation started",
                metadata_json={"task_id": task.task_id},
            )
        )
        adapter = OpenShellAdapter()
        result = _run(adapter.run_task(task, job_id=job_id))
        if result.status == "needs_approval":
            _run(
                _update_job(
                    active_job_id,
                    status="waiting_approval",
                    progress=15,
                    event_type="openshell_approval_required",
                    message="OpenShell task requires human approval",
                    metadata_json={"task_id": task.task_id},
                )
            )
            return result.model_dump(mode="json")

        _run(
            _update_job(
                active_job_id,
                status="running",
                progress=30,
                event_type="openshell_gateway_checked",
                message="OpenShell gateway checked",
                metadata_json={"status": result.status},
            )
        )
        _run(
            _update_job(
                active_job_id,
                status="running",
                progress=60,
                event_type="openshell_execution_started",
                message="OpenShell execution attempted",
                metadata_json={"task_id": task.task_id},
            )
        )
        output_dir = settings.openshell_allowed_output_dir / task.thread_id / task.task_id
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "result.json").write_text(
            json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        terminal_status = "completed" if result.status == "ok" else "failed"
        _run(
            _update_job(
                active_job_id,
                status=terminal_status,
                progress=100,
                event_type="openshell_execution_finished",
                message=f"OpenShell task finished with status {result.status}",
                metadata_json={"task_id": task.task_id, "result": result.model_dump(mode="json")},
            )
        )
        _run(
            _update_job(
                active_job_id,
                status=terminal_status,
                progress=100,
                event_type="openshell_outputs_collected",
                message="OpenShell outputs collected",
                metadata_json={"result_path": str(output_dir / "result.json")},
            )
        )
        return result.model_dump(mode="json")
    except OpenShellPolicyViolation as exc:
        blocked_result: dict[str, Any] = {
            "task_id": task.task_id,
            "thread_id": task.thread_id,
            "status": "blocked",
            "summary": str(exc),
        }
        _run(
            _update_job(
                active_job_id,
                status="failed",
                progress=None,
                event_type="openshell_failed",
                message=f"OpenShell policy violation: {exc}",
                metadata_json={"task_id": task.task_id},
            )
        )
        return blocked_result
    except Exception as exc:
        _run(_mark_job_failed(active_job_id, exc))
        raise


@celery_app.task(name="cognitive_os.reap_stale_approvals")
def reap_stale_approvals_task() -> dict[str, Any]:
    """Reap HumanApproval rows stuck in `pending` past
    `approval_pending_max_hours`.

    Safe to schedule on Celery beat: idempotent, emits AuditEvent and rejects
    any linked Job/ActionRequest.
    """
    job_id = _run(
        _create_job(
            job_type="reap_stale_approvals",
            status="running",
            progress=0,
            metadata_json={"max_hours": settings.approval_pending_max_hours},
        )
    )
    try:
        reaped = _run(ActionRequestService().reap_stale_pending_approvals())
        _run(
            _update_job(
                job_id,
                status="completed",
                progress=100,
                event_type="reap_completed",
                message=f"Reaped {reaped} stale pending approval(s)",
                metadata_json={"reaped": reaped},
            )
        )
        return {"job_id": str(job_id), "reaped": reaped}
    except Exception as exc:
        _run(_mark_job_failed(job_id, exc))
        raise


@celery_app.task(name="cognitive_os.reap_stuck_action_requests")
def reap_stuck_action_requests_task() -> dict[str, Any]:
    """Reap ActionRequests stuck in `running` past `action_request_running_max_minutes`.

    Safe to schedule on Celery beat: idempotent, never touches terminal rows,
    and emits AuditEvent + JobEvent for each row it reclaims.
    """
    job_id = _run(
        _create_job(
            job_type="reap_stuck_action_requests",
            status="running",
            progress=0,
            metadata_json={
                "max_minutes": settings.action_request_running_max_minutes,
            },
        )
    )
    try:
        service = ActionRequestService()
        reaped = _run(service.reap_stuck_running())
        # Also unstick dispatch reservations that never resolved (process
        # died between reserve_action_dispatch and apply_async). Same beat
        # cadence; cheap and idempotent.
        dispatch_unstuck = _run(service.reap_stale_dispatch_reservations())
        _run(
            _update_job(
                job_id,
                status="completed",
                progress=100,
                event_type="reap_completed",
                message=(
                    f"Reaped {reaped} stuck action_request(s); "
                    f"unstuck {dispatch_unstuck} stale dispatch reservation(s)"
                ),
                metadata_json={"reaped": reaped, "dispatch_unstuck": dispatch_unstuck},
            )
        )
        return {
            "job_id": str(job_id),
            "reaped": reaped,
            "dispatch_unstuck": dispatch_unstuck,
        }
    except Exception as exc:
        _run(_mark_job_failed(job_id, exc))
        raise


@celery_app.task(name="cognitive_os.run_action_request")
def run_action_request_task_async(action_request_id: str, job_id: str) -> dict[str, Any]:
    active_job_id = UUID(job_id)
    active_action_request_id = UUID(action_request_id)
    # Celery may retry a task that already crossed a terminal boundary (worker
    # crashed after the DB update but before ACK). Re-entering on a job already
    # in a terminal state would overwrite the real outcome — short-circuit
    # instead and return the existing row.
    existing_status = _run(_read_job_status(active_job_id))
    if existing_status == "running":
        # Only short-circuit if the ActionRequest itself is already running
        # or terminal (genuine duplicate). If the AR is still queued/pending
        # the previous attempt crashed in the Job→running ⇢ AR→running
        # window: must proceed so the action isn't stranded.
        # execute_action_request is atomic, so re-entry is safe either way.
        ar_status = _run(_read_action_request_status(active_action_request_id))
        if ar_status in {"running", "completed", "failed", "cancelled", "rejected"}:
            return {
                "id": str(active_action_request_id),
                "job_id": str(active_job_id),
                "status": existing_status,
                "ar_status": ar_status,
                "skipped": True,
                "reason": "Worker re-entry; ActionRequest already running/terminal.",
            }
        # else: fall through — crashed in the window, AR still needs to run.
    if existing_status in {"completed", "failed", "cancelled", "rejected"}:
        return {
            "id": str(active_action_request_id),
            "job_id": str(active_job_id),
            "status": existing_status,
            "skipped": True,
            "reason": "Worker re-entry on a job already in a terminal state.",
        }
    try:
        _run(
            _update_job(
                active_job_id,
                status="running",
                progress=10,
                event_type="action_request_started",
                message="Action request execution started",
                metadata_json={"action_request_id": action_request_id},
            )
        )
        result = _run(ActionRequestService().execute_action_request(active_action_request_id))
        terminal_status = _ACTION_REQUEST_TERMINAL_JOB_STATUS.get(result.status)
        if terminal_status is None:
            _run(
                _update_job(
                    active_job_id,
                    status=result.status,
                    progress=None,
                    event_type="action_request_not_executed",
                    message=(
                        "Action request worker exited without terminal update because "
                        f"request is {result.status}"
                    ),
                    metadata_json={
                        "action_request_id": action_request_id,
                        "result": result.model_dump(mode="json"),
                    },
                )
            )
            return result.model_dump(mode="json")
        _run(
            _update_job(
                active_job_id,
                status=terminal_status,
                progress=100,
                event_type="action_request_finished",
                message=f"Action request finished with status {result.status}",
                metadata_json={
                    "action_request_id": action_request_id,
                    "result": result.model_dump(mode="json"),
                },
            )
        )
        return result.model_dump(mode="json")
    except Exception as exc:
        _run(_mark_job_failed(active_job_id, exc))
        raise


KNOWN_DEEPAGENT_NAMES: tuple[str, ...] = ("research", "document-analysis")


@celery_app.task(name="cognitive_os.consolidate_deepagent_memory")
def consolidate_deepagent_memory_task(scope: str, target_id: str) -> dict[str, Any]:
    job_id = _run(
        _create_job(
            job_type="deepagent_memory_consolidation",
            status="running",
            progress=0,
            metadata_json={"scope": scope, "target_id": target_id},
        )
    )
    try:
        consolidator = DeepAgentMemoryConsolidator()
        if scope == "thread":
            proposals = _run(consolidator.consolidate_thread(target_id))
        else:
            proposals = _run(
                consolidator.consolidate_agent_lessons(
                    target_id, datetime.now(UTC) - timedelta(days=1)
                )
            )
        _run(
            _update_job(
                job_id,
                status="completed",
                progress=100,
                event_type="deepagent_memory_consolidated",
                message=f"Generated {len(proposals)} DeepAgent memory proposals",
                metadata_json={"proposal_count": len(proposals)},
            )
        )
        return {
            "job_id": str(job_id),
            "proposal_count": len(proposals),
            "proposal_ids": [proposal.proposal_id for proposal in proposals],
        }
    except Exception as exc:
        _run(_mark_job_failed(job_id, exc))
        raise


@celery_app.task(name="cognitive_os.consolidate_all_deepagent_memory")
def consolidate_all_deepagent_memory_task(
    agent_names: tuple[str, ...] = KNOWN_DEEPAGENT_NAMES,
) -> dict[str, Any]:
    """Schedule per-agent consolidation jobs (the beat target)."""
    dispatched: list[str] = []
    for name in agent_names:
        consolidate_deepagent_memory_task.apply_async(args=("agent", name), queue="maintenance")
        dispatched.append(name)
    return {"dispatched": dispatched, "count": len(dispatched)}


@celery_app.task(name="cognitive_os.run_document_analysis")
def run_document_analysis_task_async(task_dict: dict[str, Any], job_id: str) -> dict[str, Any]:
    active_job_id = UUID(job_id)
    task = DocumentAnalysisTask.model_validate(task_dict)
    try:
        _run(
            _update_job(
                active_job_id,
                status="running",
                progress=1,
                event_type="document_analysis_received",
                message="Document analysis task received",
                metadata_json={"task_id": task.task_id, "thread_id": task.thread_id},
            )
        )
        result = _run(DocumentAnalysisService().run_analysis_as_job(task, job_id))
        return result.model_dump(mode="json")
    except Exception as exc:
        _run(_mark_job_failed(active_job_id, exc))
        raise


@celery_app.task(name="cognitive_os.run_code_build")
def run_code_build_task_async(job_id: str) -> dict[str, Any]:
    """Execute an approved code build.

    Dispatched ONLY from `_decide_approval` when a `run_code_build:<id>`
    HumanApproval is accepted — so by the time this runs the operator has
    already approved the plan and the budget estimate. The director enforces
    its own per-build hard caps (runtime / calls / USD); this task just
    re-enters on already-terminal jobs defensively (Celery retry safety).
    """
    from cognitive_os.code_director.service import CodeDirectorService

    active_job_id = UUID(job_id)
    outcome, previous_status = _run(_reserve_code_build_job(active_job_id))
    if outcome == "skip":
        return {
            "job_id": job_id,
            "status": previous_status,
            "skipped": True,
            "reason": (
                "Worker re-entry on a job already in a terminal state."
                if previous_status in {"completed", "failed", "cancelled", "rejected"}
                else (
                    "Duplicate dispatch: a code build for this job is already running."
                    if previous_status == "running"
                    else f"Job not eligible for execution (status={previous_status})."
                )
            ),
        }
    try:
        result = _run(CodeDirectorService().run_build(active_job_id))
        return result.model_dump(mode="json")
    except Exception as exc:
        _run(_mark_job_failed(active_job_id, exc))
        raise


async def _cleanup_old_terminal_jobs(*, days: int) -> int:
    from sqlalchemy import delete

    cutoff = datetime.now(UTC) - timedelta(days=days)
    async with session_scope() as session:
        result = await session.execute(
            delete(Job).where(
                Job.status.in_(("completed", "failed", "cancelled")),
                Job.updated_at < cutoff,
            )
        )
        rowcount = getattr(result, "rowcount", 0)
        return int(rowcount or 0)


async def _reap_stale_running_jobs(*, max_hours: int) -> int:
    """Mark queued/running/waiting_approval jobs older than `max_hours` as
    `failed` with a `job_reaped_stale` JobEvent.

    Zombie jobs (worker crashed before transitioning to terminal) otherwise
    sit forever in /knowledge/stats jobs_running and inflate the count. This
    reaper is conservative: only acts on jobs whose `updated_at` hasn't moved
    in `max_hours` AND whose status indicates the worker should have made
    progress by now. (Fase 72 C.)
    """
    from sqlalchemy import select  # noqa: PLC0415

    cutoff = datetime.now(UTC) - timedelta(hours=max_hours)
    stuck_statuses = ("queued", "running", "submitting", "submitted")
    reaped = 0
    async with session_scope() as session:
        result = await session.execute(
            select(Job).where(
                Job.status.in_(stuck_statuses),
                Job.updated_at < cutoff,
            )
        )
        for job in result.scalars().all():
            previous_status = job.status
            job.status = "failed"
            job.progress = 100
            session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="job_reaped_stale",
                    status="failed",
                    message=(
                        f"Job stuck in `{previous_status}` for more than "
                        f"{max_hours}h. Reaped by stale-jobs reaper."
                    ),
                    metadata_json={
                        "previous_status": previous_status,
                        "max_hours": max_hours,
                    },
                )
            )
            reaped += 1
    return reaped


@celery_app.task(name="cognitive_os.reap_stale_running_jobs")
def reap_stale_running_jobs_task() -> dict[str, int]:
    reaped = _run(_reap_stale_running_jobs(max_hours=settings.stale_job_max_hours))
    return {"reaped": reaped, "max_hours": settings.stale_job_max_hours}


@celery_app.task(name="cognitive_os.deliver_personal_reminders")
def deliver_personal_reminders_task() -> dict[str, Any]:
    return _run(deliver_personal_task_reminders(settings))


@celery_app.task(name="cognitive_os.scan_failure_postmortems")
def scan_failure_postmortems_task() -> dict[str, Any]:
    """Beat target for Fase 79.3: scan recent jobs for failure-recovery
    patterns and emit warning proposals (auto-promoted after N repeats).

    Idempotent: each (failed_event_id, succeeded_event_id) pair is checked
    against existing proposals before creating a new one.
    """
    if not settings.failure_postmortem_enabled:
        return {"skipped": True, "reason": "FAILURE_POSTMORTEM_ENABLED=false"}
    return _run(scan_failure_patterns())


@celery_app.task(name="cognitive_os.extract_pending_recipes")
def extract_pending_recipes_task() -> dict[str, Any]:
    """Beat target for Fase 78: distil successful long-running jobs into
    procedural memory proposals.

    Idempotent: the extractor scopes its work to ``Job`` rows whose
    ``extracted_recipe_at`` column is NULL, sets the timestamp on each
    successful pass (proposal OR explicit LLM skip), and leaves the
    column untouched on transient LLM errors so the next beat cycle
    retries. Safe to run more often than 30 min if the operator wants
    faster feedback.
    """
    if not settings.recipe_extractor_enabled:
        return {"skipped": True, "reason": "RECIPE_EXTRACTOR_ENABLED=false"}
    return _run(extract_pending_recipes())


@celery_app.task(name="cognitive_os.telegram_gmail_digest")
def telegram_gmail_digest_task() -> dict[str, Any]:
    cfg = settings
    if not (cfg.telegram_enabled and cfg.telegram_gmail_digest_enabled and cfg.gmail_read_enabled):
        return {
            "skipped": True,
            "reason": "digest_prereqs_missing",
            "telegram_enabled": cfg.telegram_enabled,
            "digest_enabled": cfg.telegram_gmail_digest_enabled,
            "gmail_read_enabled": cfg.gmail_read_enabled,
        }
    reader = GmailRestReader.from_settings(cfg)
    svc = GmailDigestService(reader=reader, app_settings=cfg)
    preview = svc.build_preview(
        GmailDigestRequest(
            lookback_hours=cfg.telegram_gmail_digest_lookback_hours,
            max_messages=50,
        )
    )
    text = render_gmail_digest_telegram(preview)
    targets_raw = cfg.telegram_gmail_digest_chat_ids or cfg.telegram_authorized_user_ids
    if not targets_raw:
        return {
            "skipped": True,
            "reason": "no_telegram_chat_targets",
            "preview_status": preview.status,
        }
    for cid in targets_raw:
        send_telegram_markdown(int(cid), text)
    return {
        "preview_status": preview.status,
        "chats_sent": len(targets_raw),
        "lookback_hours": cfg.telegram_gmail_digest_lookback_hours,
    }

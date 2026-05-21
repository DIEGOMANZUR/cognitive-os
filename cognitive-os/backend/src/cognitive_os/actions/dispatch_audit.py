"""Shared Celery dispatch helper with auditable JobEvent emission.

Both the REST surface (`/approvals/{id}/{approve|reject}`) and the Telegram
bot (`/approve`, `/reject`) end up dispatching Celery tasks (OpenShell sandbox,
Code Director build, ActionRequest run) after committing the approval. If the
broker is down right after the commit, the operator sees the approval decided
but no progress on the job — silent failure. This helper guarantees that a
JobEvent is always emitted (submitted OR failed), so `/jobs/{id}/events`
tells the truth even when Celery refuses the task.

Use the sync wrapper for fire-and-forget contexts (Telegram bot's `_run`
adapter), and the async one inside FastAPI / async services.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from cognitive_os.core.db import session_scope
from cognitive_os.db.models import Job, JobEvent

logger = logging.getLogger(__name__)


def _celery_task_id(async_result: Any) -> str | None:
    raw_id = getattr(async_result, "id", None) or getattr(async_result, "task_id", None)
    if raw_id is None:
        return None
    task_id = str(raw_id).strip()
    return task_id or None


async def dispatch_celery_with_audit(
    *,
    task_name: str,
    apply_async: Callable[[], Any],
    job_id: UUID,
    surface: str = "rest",
) -> bool:
    """Submit a Celery task and emit a visible JobEvent either way.

    Returns ``True`` when ``apply_async()`` returned without raising,
    ``False`` when the broker (or anything else) refused the dispatch. The
    caller can use the boolean to surface a friendlier message; the audit
    trail is taken care of regardless.

    ``surface`` lets us trace whether the dispatch came from REST, Telegram,
    or the auto-approve helper without scanning code paths after the fact.
    """
    try:
        async_result = apply_async()
    except Exception as exc:  # noqa: BLE001 - broker offline is operator-facing
        logger.warning(
            "celery_dispatch_failed task=%s surface=%s error=%s",
            task_name,
            surface,
            type(exc).__name__,
        )
        with contextlib.suppress(Exception):
            async with session_scope() as session:
                job = await session.get(Job, job_id)
                if job is not None:
                    metadata = dict(job.metadata_json or {})
                    metadata["celery_task_name"] = task_name
                    metadata["celery_surface"] = surface
                    metadata["celery_dispatch_error_type"] = type(exc).__name__
                    job.metadata_json = metadata
                session.add(
                    JobEvent(
                        job_id=job_id,
                        event_type=f"{task_name}_dispatch_failed",
                        status="queued",
                        message=(
                            f"Celery refused {task_name} dispatch from "
                            f"{surface} ({type(exc).__name__}). Job remains "
                            "queued for the reaper."
                        ),
                        metadata_json={
                            "error_type": type(exc).__name__,
                            "surface": surface,
                        },
                    )
                )
        return False
    with contextlib.suppress(Exception):
        task_id = _celery_task_id(async_result)
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            metadata_json: dict[str, Any] = {"surface": surface}
            if task_id is not None:
                metadata_json["celery_task_id"] = task_id
                if job is not None:
                    metadata = dict(job.metadata_json or {})
                    metadata["celery_task_id"] = task_id
                    metadata["celery_task_name"] = task_name
                    metadata["celery_surface"] = surface
                    job.metadata_json = metadata
            session.add(
                JobEvent(
                    job_id=job_id,
                    event_type=f"{task_name}_dispatch_submitted",
                    status="queued",
                    message=f"{task_name} submitted to Celery from {surface}.",
                    metadata_json=metadata_json,
                )
            )
    return True

"""P1 commercial-audit hardening — dedicated reaper tests.

Contract (`docs/RUNBOOK.md` §Beat; `docs/ARCHITECTURE.md` §6):

  Three reapers must reclaim stuck rows on their own schedule:

  * ``reap_stale_pending_approvals`` — pending approvals older than
    ``APPROVAL_PENDING_MAX_HOURS``.
  * ``reap_stuck_running`` (actions) — action_requests stuck in
    queued/running past ``ACTION_REQUEST_RUNNING_MAX_MINUTES``.
  * ``_reap_stale_running_jobs`` — jobs in queued/running/submitting/
    submitted past ``STALE_JOB_MAX_HOURS``.

The existing ``test_approval_reaper.py`` covers the approvals reaper.
This file adds the missing two with seed-and-reap behavioural assertions
over the test DB.

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §D6/D7.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from cognitive_os.actions.service import ActionRequestService
from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import (
    ActionRequest,
    HumanApproval,
    Job,
    JobEvent,
)
from cognitive_os.workers.tasks import _reap_stale_running_jobs


@pytest.fixture
async def clean_slate() -> None:
    """Truncate the four tables this audit touches.

    FK order matters: ``ActionRequest.approval_id`` references
    ``HumanApproval.id``; ``JobEvent.job_id`` references ``Job.id``.
    Children before parents.
    """
    async with session_scope() as session:
        await session.execute(delete(JobEvent))
        await session.execute(delete(ActionRequest))
        await session.execute(delete(HumanApproval))
        await session.execute(delete(Job))


@pytest.mark.asyncio
async def test_reap_stuck_action_requests_reclaims_running_rows_past_threshold(
    clean_slate: None,
) -> None:
    del clean_slate
    cutoff_minutes = settings.action_request_running_max_minutes
    stale = datetime.now(UTC) - timedelta(minutes=cutoff_minutes + 5)
    fresh = datetime.now(UTC) - timedelta(minutes=1)

    async with session_scope() as session:
        stale_row = ActionRequest(
            action_type="browser_preview",
            status="running",
            requested_by="audit-reaper",
            idempotency_key=f"audit-stale-{uuid4()}",
            payload_redacted={},
            payload_executable={},
            preview={"status": "ok"},
            created_at=stale,
            updated_at=stale,
        )
        fresh_row = ActionRequest(
            action_type="browser_preview",
            status="running",
            requested_by="audit-reaper",
            idempotency_key=f"audit-fresh-{uuid4()}",
            payload_redacted={},
            payload_executable={},
            preview={"status": "ok"},
            created_at=fresh,
            updated_at=fresh,
        )
        session.add_all([stale_row, fresh_row])
        await session.flush()
        stale_id = stale_row.id
        fresh_id = fresh_row.id

    reaped = await ActionRequestService().reap_stuck_running()
    assert reaped >= 1

    async with session_scope() as session:
        stale_reloaded = await session.get(ActionRequest, stale_id)
        fresh_reloaded = await session.get(ActionRequest, fresh_id)
    assert stale_reloaded is not None
    assert fresh_reloaded is not None
    # The reaper must transition the stale row OUT of running.
    assert stale_reloaded.status != "running", (
        f"stale action_request still 'running' after reaper; status={stale_reloaded.status}"
    )
    # The fresh row must be untouched.
    assert fresh_reloaded.status == "running"


@pytest.mark.asyncio
async def test_reap_stale_running_jobs_marks_zombies_failed(clean_slate: None) -> None:
    del clean_slate
    cutoff_hours = settings.stale_job_max_hours
    stale = datetime.now(UTC) - timedelta(hours=cutoff_hours + 2)
    fresh = datetime.now(UTC) - timedelta(hours=1)

    async with session_scope() as session:
        zombie = Job(
            job_type="audit-zombie",
            status="running",
            created_at=stale,
            updated_at=stale,
        )
        active = Job(
            job_type="audit-active",
            status="running",
            created_at=fresh,
            updated_at=fresh,
        )
        session.add_all([zombie, active])
        await session.flush()
        zombie_id = zombie.id
        active_id = active.id

    reaped = await _reap_stale_running_jobs(max_hours=cutoff_hours)
    assert reaped >= 1

    async with session_scope() as session:
        zombie_reloaded = await session.get(Job, zombie_id)
        active_reloaded = await session.get(Job, active_id)
        # Reaper writes a `job_reaped_stale` JobEvent.
        events = (
            (await session.execute(select(JobEvent).where(JobEvent.job_id == zombie_id)))
            .scalars()
            .all()
        )
    assert zombie_reloaded is not None and zombie_reloaded.status == "failed"
    assert zombie_reloaded.progress == 100
    assert active_reloaded is not None and active_reloaded.status == "running"
    assert any(event.event_type == "job_reaped_stale" for event in events)


@pytest.mark.asyncio
async def test_reap_stuck_action_requests_is_idempotent(clean_slate: None) -> None:
    """Running the reaper twice over the same fixture must not double-reap."""
    del clean_slate
    cutoff_minutes = settings.action_request_running_max_minutes
    stale = datetime.now(UTC) - timedelta(minutes=cutoff_minutes + 5)
    async with session_scope() as session:
        row = ActionRequest(
            action_type="browser_preview",
            status="running",
            requested_by="audit-idempotent",
            idempotency_key=f"audit-idemp-{uuid4()}",
            payload_redacted={},
            payload_executable={},
            preview={"status": "ok"},
            created_at=stale,
            updated_at=stale,
        )
        session.add(row)

    service = ActionRequestService()
    first = await service.reap_stuck_running()
    second = await service.reap_stuck_running()
    assert first >= 1
    # The second pass must report 0 — the row is already terminal.
    assert second == 0


@pytest.mark.asyncio
async def test_reap_stale_running_jobs_is_idempotent(clean_slate: None) -> None:
    del clean_slate
    cutoff_hours = settings.stale_job_max_hours
    stale = datetime.now(UTC) - timedelta(hours=cutoff_hours + 5)
    async with session_scope() as session:
        zombie = Job(
            job_type="audit-zombie",
            status="running",
            created_at=stale,
            updated_at=stale,
        )
        session.add(zombie)

    first = await _reap_stale_running_jobs(max_hours=cutoff_hours)
    second = await _reap_stale_running_jobs(max_hours=cutoff_hours)
    assert first >= 1
    assert second == 0

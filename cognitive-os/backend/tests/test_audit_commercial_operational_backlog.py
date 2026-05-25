"""P1 commercial-audit hardening — operational_backlog reactivity.

Contract (AUDIT-2026-F closed; `docs/CURRENT_STATE.md` §Health;
`core/health.py:_check_operational_backlog`):

  The ``operational_backlog`` component MUST go ``degraded`` when ANY
  of the four breach conditions is true:

  1. an approval has been pending past ``approval_pending_max_hours``;
  2. a job has been in queued/running past ``stale_job_max_hours``;
  3. an action_request has been queued/running past
     ``action_request_running_max_minutes``;
  4. no reaper has completed in the past ``_BEAT_LAG_DEGRADE_MINUTES``.

We seed each condition independently against the test DB and assert the
component flips to ``degraded`` with the expected metadata keys. The
existing test_health_dashboard.py covers the happy path; this file
covers the breach paths individually.

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §D8.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete

from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.core.health import _check_operational_backlog
from cognitive_os.db.models import (
    ActionRequest,
    DeepAgentMemoryProposalRecord,
    HumanApproval,
    Job,
    JobEvent,
)


@pytest.fixture
async def clean_slate() -> None:
    """Truncate the tables this check reads + every table whose FK targets HumanApproval.

    The audit suite is hermetic against `cognitive_os_test`, but other tests
    (e.g. failure_postmortem, skill_promoter, recipe_extractor) may seed rows
    in ``deepagent_memory_proposals`` with ``approval_id`` populated. We must
    delete those children before ``HumanApproval`` or the cleanup hits
    ``ForeignKeyViolationError`` on the
    ``fk_deepagent_memory_proposals_approval_id_human_approvals`` constraint
    (root cause of the suite flakiness logged in audit 2026-05-25,
    F-P0-001 in ``corregir_cognitive.md``).

    FK order matters: both ``ActionRequest.approval_id`` and
    ``DeepAgentMemoryProposalRecord.approval_id`` reference ``HumanApproval.id``;
    ``JobEvent.job_id`` references ``Job.id``. So we drop children before parents.

    If new tables with a FK to ``human_approvals`` appear, the regression test
    ``test_clean_slate_fixture_covers_all_fks.py`` will flag this fixture as
    out of date.
    """
    async with session_scope() as session:
        await session.execute(delete(JobEvent))
        await session.execute(delete(ActionRequest))
        await session.execute(delete(DeepAgentMemoryProposalRecord))
        await session.execute(delete(HumanApproval))
        await session.execute(delete(Job))


@pytest.mark.asyncio
async def test_operational_backlog_is_ok_with_empty_state(clean_slate: None) -> None:
    del clean_slate
    result = await _check_operational_backlog()
    assert result.status == "ok"
    assert result.metadata["approvals_pending"] == 0
    assert result.metadata["approvals_stale"] == 0
    assert result.metadata["jobs_stale"] == 0
    assert result.metadata["action_requests_stuck"] == 0


@pytest.mark.asyncio
async def test_operational_backlog_degrades_on_stale_approval(clean_slate: None) -> None:
    del clean_slate
    cutoff_hours = settings.approval_pending_max_hours
    stale_age = datetime.now(UTC) - timedelta(hours=cutoff_hours + 2)
    async with session_scope() as session:
        approval = HumanApproval(
            action="audit",
            requested_action="audit-operational-backlog",
            requested_by="audit",
            status="pending",
            created_at=stale_age,
            updated_at=stale_age,
        )
        session.add(approval)

    result = await _check_operational_backlog()
    assert result.status == "degraded"
    assert result.metadata["approvals_stale"] >= 1
    assert "approval" in (result.detail or "").lower()


@pytest.mark.asyncio
async def test_operational_backlog_degrades_on_stale_job(clean_slate: None) -> None:
    del clean_slate
    cutoff_hours = settings.stale_job_max_hours
    stale_age = datetime.now(UTC) - timedelta(hours=cutoff_hours + 2)
    async with session_scope() as session:
        job = Job(
            job_type="audit-job",
            status="running",
            created_at=stale_age,
            updated_at=stale_age,
        )
        session.add(job)

    result = await _check_operational_backlog()
    assert result.status == "degraded"
    assert result.metadata["jobs_stale"] >= 1
    assert "job" in (result.detail or "").lower()


@pytest.mark.asyncio
async def test_operational_backlog_degrades_on_stuck_action_request(clean_slate: None) -> None:
    del clean_slate
    cutoff_minutes = settings.action_request_running_max_minutes
    stuck_age = datetime.now(UTC) - timedelta(minutes=cutoff_minutes + 2)
    async with session_scope() as session:
        action_request = ActionRequest(
            action_type="browser_preview",
            status="running",
            requested_by="audit",
            idempotency_key=f"audit-stuck-{uuid4()}",
            payload_redacted={},
            payload_executable={},
            preview={"status": "ok"},
            created_at=stuck_age,
            updated_at=stuck_age,
        )
        session.add(action_request)

    result = await _check_operational_backlog()
    assert result.status == "degraded"
    assert result.metadata["action_requests_stuck"] >= 1
    assert "action request" in (result.detail or "").lower()


@pytest.mark.asyncio
async def test_operational_backlog_metadata_contains_all_expected_keys(
    clean_slate: None,
) -> None:
    """The metadata payload must surface every counter the operator needs."""
    del clean_slate
    result = await _check_operational_backlog()
    expected_keys = {
        "approvals_pending",
        "approvals_stale",
        "jobs_stale",
        "action_requests_stuck",
        "beat_lag_minutes",
        "beat_lag_degrade_minutes",
    }
    assert expected_keys.issubset(result.metadata.keys())


@pytest.mark.asyncio
async def test_operational_backlog_ok_when_pending_approvals_are_recent(
    clean_slate: None,
) -> None:
    """A pending approval below the threshold must not trigger degrade."""
    del clean_slate
    fresh = datetime.now(UTC) - timedelta(minutes=5)
    async with session_scope() as session:
        approval = HumanApproval(
            action="audit",
            requested_action="audit-recent",
            requested_by="audit",
            status="pending",
            created_at=fresh,
            updated_at=fresh,
        )
        session.add(approval)

    result = await _check_operational_backlog()
    assert result.status == "ok"
    assert result.metadata["approvals_pending"] >= 1
    assert result.metadata["approvals_stale"] == 0

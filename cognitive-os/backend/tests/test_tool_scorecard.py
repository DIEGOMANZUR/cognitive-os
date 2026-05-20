"""Fase 79.4 — tool effectiveness scorecard regression tests.

These tests build fake job + event rows and assert the aggregator
produces the right counts + reliability score. UPSERT semantics
verified by re-running the aggregator on the same window.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from cognitive_os.core.db import session_scope
from cognitive_os.db.models import Job, JobEvent, ToolInvocationMetric
from cognitive_os.deepagents.tool_scorecard import (
    _Counters,
    aggregate_window,
    compute_reliability_score,
    list_recent_scorecard,
    persist_scorecard_window,
)


async def _job_with_events(
    *,
    events: list[tuple[str, str, dict | None]],
    job_type: str = "deepagent_research",
    agent_name: str = "research",
) -> UUID:
    """Create a Job with the given list of (event_type, status, metadata) tuples.

    Each event gets a monotonically-increasing ``created_at`` (start + i ms)
    so the aggregator's chronological ordering is deterministic — without
    this, ``func.now()`` server defaults collapse all events to the same
    timestamp and ``write_workspace_file`` may be processed before the
    ``tool_succeeded`` event it should credit.
    """
    async with session_scope() as session:
        base_time = datetime.now(UTC)
        job = Job(
            job_type=job_type,
            status="completed",
            progress=100,
            metadata_json={"agent_name": agent_name},
        )
        session.add(job)
        await session.flush()
        for i, (event_type, status, metadata) in enumerate(events):
            event = JobEvent(
                job_id=job.id,
                event_type=event_type,
                status=status,
                message=event_type,
                metadata_json=metadata or {},
            )
            session.add(event)
            await session.flush()
            event.created_at = base_time + timedelta(milliseconds=i)
        await session.flush()
        return job.id


def test_reliability_score_full_combination() -> None:
    """0.5*1.0 (all success) + 0.3*1.0 (all downstream) + 0.2*1.0 (no rejects) = 1.0."""
    c = _Counters(invoke=10, success=10, failure=0, downstream=10, approve=5, reject=0)
    assert compute_reliability_score(c) == pytest.approx(1.0)


def test_reliability_score_zero_invocations_returns_none() -> None:
    assert compute_reliability_score(_Counters()) is None


def test_reliability_score_partial() -> None:
    """8/10 success, 4/8 downstream, no approvals → 0.5*0.8 + 0.3*0.5 + 0.2*1.0 = 0.75."""
    c = _Counters(invoke=10, success=8, failure=2, downstream=4, approve=0, reject=0)
    assert compute_reliability_score(c) == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_aggregate_window_counts_success_failure_correctly() -> None:
    import uuid

    tool = f"score_tool_{uuid.uuid4().hex[:8]}"
    await _job_with_events(
        events=[
            ("tool_invoked", "running", {"tool": tool}),
            ("tool_succeeded", "completed", {"tool": tool, "latency_ms": 200}),
            ("tool_invoked", "running", {"tool": tool}),
            ("tool_failed", "error", {"tool": tool}),
        ],
    )

    now = datetime.now(UTC)
    entries = await aggregate_window(
        period_start=now - timedelta(hours=1), period_end=now + timedelta(hours=1)
    )
    matching = [e for e in entries if e.tool_name == tool]
    assert len(matching) == 1
    entry = matching[0]
    assert entry.agent_role == "research"
    assert entry.counters.success == 1
    assert entry.counters.failure == 1
    assert entry.counters.invoke >= 2
    assert entry.reliability_score is not None
    assert 0 <= entry.reliability_score <= 1


@pytest.mark.asyncio
async def test_aggregate_window_downstream_credit() -> None:
    """A `write_workspace_file` event after a `tool_succeeded` should bump
    the downstream_use_count for that tool — proxy for "was the result used".
    """
    import uuid

    tool = f"downstream_tool_{uuid.uuid4().hex[:8]}"
    await _job_with_events(
        events=[
            ("tool_invoked", "running", {"tool": tool}),
            ("tool_succeeded", "completed", {"tool": tool}),
            ("write_workspace_file", "completed", {}),
        ],
    )

    now = datetime.now(UTC)
    entries = await aggregate_window(
        period_start=now - timedelta(hours=1), period_end=now + timedelta(hours=1)
    )
    matching = [e for e in entries if e.tool_name == tool]
    assert len(matching) == 1
    assert matching[0].counters.downstream == 1


@pytest.mark.asyncio
async def test_persist_and_upsert_idempotent() -> None:
    """Running the aggregator twice on the same window should UPSERT,
    not create duplicate rows.
    """
    import uuid

    tool = f"upsert_tool_{uuid.uuid4().hex[:8]}"
    await _job_with_events(
        events=[
            ("tool_invoked", "running", {"tool": tool}),
            ("tool_succeeded", "completed", {"tool": tool}),
        ],
    )

    now = datetime.now(UTC)
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(hours=1)
    first = await persist_scorecard_window(period_start=window_start, period_end=window_end)
    second = await persist_scorecard_window(period_start=window_start, period_end=window_end)
    assert first["entries_written"] >= 1
    assert second["entries_written"] >= 1

    async with session_scope() as session:
        rows = (
            (
                await session.execute(
                    select(ToolInvocationMetric).where(
                        ToolInvocationMetric.tool_name == tool,
                        ToolInvocationMetric.period_start == window_start,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].success_count >= 1


@pytest.mark.asyncio
async def test_list_recent_scorecard_filters_by_window() -> None:
    import uuid

    tool = f"listed_tool_{uuid.uuid4().hex[:8]}"
    await _job_with_events(
        events=[
            ("tool_invoked", "running", {"tool": tool}),
            ("tool_succeeded", "completed", {"tool": tool}),
        ],
    )
    now = datetime.now(UTC)
    await persist_scorecard_window(
        period_start=now - timedelta(hours=1), period_end=now + timedelta(hours=1)
    )

    rows = await list_recent_scorecard(days=2, limit=200)
    assert any(r["tool_name"] == tool for r in rows)

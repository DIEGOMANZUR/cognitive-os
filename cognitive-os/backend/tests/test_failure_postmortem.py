"""Fase 79.3 (Fase D) — failure post-mortem scanner regression tests.

These tests use the real Postgres session via `session_scope`. Conftest
already disables real LLM factories so the scanner runs without network.
The scanner itself is LLM-free (Jaccard token overlap, no embedding
model), so no LLM stub is needed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select

from cognitive_os.core.db import session_scope
from cognitive_os.db.models import (
    DeepAgentMemoryProposalRecord,
    DeepAgentMemoryRecord,
    Job,
    JobEvent,
)
from cognitive_os.deepagents.failure_postmortem import (
    _normalise_args,
    _strings_similar,
    find_failure_patterns,
    scan_recent_jobs,
)


async def _job_with_failure_recovery(
    *,
    tool_name: str = "search_local_docs",
    job_type: str = "deepagent_research",
    args_fail: dict[str, Any] | None = None,
    args_ok: dict[str, Any] | None = None,
) -> tuple[UUID, UUID, UUID]:
    """Create a Job with one tool_failed followed by one tool_succeeded.

    Returns (job_id, failed_event_id, succeeded_event_id).
    """
    af = args_fail or {"args": {"q": "contratos del año", "limit": 100}}
    ao = args_ok or {"args": {"q": "contratos del año", "limit": 10}}
    af = {**af, "tool": tool_name}
    ao = {**ao, "tool": tool_name}
    async with session_scope() as session:
        now = datetime.now(UTC)
        job = Job(
            job_type=job_type,
            status="completed",
            progress=100,
            metadata_json={"agent_name": "research"},
        )
        session.add(job)
        await session.flush()
        job.created_at = now - timedelta(seconds=120)
        job.updated_at = now
        failed = JobEvent(
            job_id=job.id,
            event_type="tool_failed",
            status="error",
            message="HTTP 400 — limit too high",
            metadata_json=af,
        )
        succeeded = JobEvent(
            job_id=job.id,
            event_type="tool_succeeded",
            status="completed",
            message="OK",
            metadata_json=ao,
        )
        session.add(failed)
        session.add(succeeded)
        await session.flush()
        return job.id, failed.id, succeeded.id


def test_strings_similar_catches_close_args() -> None:
    a = "[('q', 'contratos del año'), ('limit', '100')]"
    b = "[('q', 'contratos del año'), ('limit', '10')]"
    assert _strings_similar(a, b)


def test_strings_similar_rejects_disjoint_args() -> None:
    a = "[('q', 'contratos del año'), ('limit', '100')]"
    b = "[('cypher', 'MATCH (n) RETURN n')]"
    assert not _strings_similar(a, b)


def test_normalise_args_strips_volatile_keys() -> None:
    md = {
        "args": {
            "q": "contratos",
            "limit": 10,
            "request_id": "abc-123",
            "trace_id": "trace-xyz",
        }
    }
    out = _normalise_args(md)
    assert "request_id" not in out
    assert "trace_id" not in out
    assert "contratos" in out


@pytest.mark.asyncio
async def test_find_failure_patterns_pairs_fail_and_recovery() -> None:
    job_id, failed_id, succeeded_id = await _job_with_failure_recovery()
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        events = (
            (
                await session.execute(
                    select(JobEvent)
                    .where(JobEvent.job_id == job_id)
                    .order_by(JobEvent.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        patterns = find_failure_patterns(job, events)
    assert len(patterns) == 1
    assert patterns[0].failed_event_id == failed_id
    assert patterns[0].succeeded_event_id == succeeded_id
    assert patterns[0].tool_name == "search_local_docs"
    assert patterns[0].agent_role == "research"


@pytest.mark.asyncio
async def test_find_failure_patterns_skips_unrelated_recovery() -> None:
    """A success on a *different* tool right after a failure is NOT a recovery."""
    async with session_scope() as session:
        now = datetime.now(UTC)
        job = Job(
            job_type="deepagent_research",
            status="completed",
            progress=100,
            metadata_json={"agent_name": "research"},
        )
        session.add(job)
        await session.flush()
        job.created_at = now - timedelta(seconds=60)
        job.updated_at = now
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="tool_failed",
                status="error",
                message="fail",
                metadata_json={"tool": "search_local_docs", "args": {"q": "x"}},
            )
        )
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="tool_succeeded",
                status="completed",
                message="ok",
                metadata_json={"tool": "graph_query_readonly", "args": {"cypher": "M"}},
            )
        )
        await session.flush()
        events = (
            (
                await session.execute(
                    select(JobEvent)
                    .where(JobEvent.job_id == job.id)
                    .order_by(JobEvent.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        patterns = find_failure_patterns(job, events)
    assert patterns == []


@pytest.mark.asyncio
async def test_record_failure_pattern_creates_proposal() -> None:
    """Unique tool per test keeps this isolated from sibling tests that share
    the Postgres DB across runs (no rollback between session_scope commits).
    """
    import uuid

    unique_tool = f"isolated_tool_{uuid.uuid4().hex[:8]}"
    job_id, *_ = await _job_with_failure_recovery(tool_name=unique_tool)
    summary = await scan_recent_jobs()
    assert summary["patterns_found"] >= 1
    assert summary["proposals_created"] >= 1
    async with session_scope() as session:
        proposals = (
            (
                await session.execute(
                    select(DeepAgentMemoryProposalRecord).where(
                        DeepAgentMemoryProposalRecord.source_task_id == str(job_id)
                    )
                )
            )
            .scalars()
            .all()
        )
        assert proposals
        # Top-level keys are set by the shared memory_service flow; the
        # scanner-specific metadata is stored under `payload`.
        assert proposals[0].metadata_json["kind"] == "warning"
        assert proposals[0].metadata_json["payload"]["pattern_kind"] == "failure_recovery"


@pytest.mark.asyncio
async def test_duplicate_event_pair_does_not_create_second_proposal() -> None:
    """The (failed_event_id, succeeded_event_id) idempotency key blocks
    re-creating a proposal for the same evidence on a second scan.
    """
    import uuid

    unique_tool = f"isolated_tool_{uuid.uuid4().hex[:8]}"
    job_id, *_ = await _job_with_failure_recovery(tool_name=unique_tool)
    await scan_recent_jobs()
    summary2 = await scan_recent_jobs()
    assert summary2["duplicates"] >= 1
    async with session_scope() as session:
        proposals = (
            (
                await session.execute(
                    select(DeepAgentMemoryProposalRecord).where(
                        DeepAgentMemoryProposalRecord.source_task_id == str(job_id)
                    )
                )
            )
            .scalars()
            .all()
        )
        # The first scan created the proposal; second scan saw the idempotency
        # key in metadata_json and did NOT create a duplicate row.
        assert len(proposals) == 1


@pytest.mark.asyncio
async def test_auto_promotion_after_threshold_occurrences() -> None:
    """3 distinct jobs with the same (agent_role, tool_name) recovery pattern
    should auto-promote on the 3rd — operator silence counts as approval.

    Uses a unique tool name so this test is isolated from any active
    warnings other tests may have left in the shared Postgres DB.
    """
    import uuid

    unique_tool = f"unique_tool_{uuid.uuid4().hex[:8]}"
    pattern_jobs: list[UUID] = []
    for i in range(3):
        jid, *_ = await _job_with_failure_recovery(
            tool_name=unique_tool,
            args_fail={"args": {"q": f"query{i}", "limit": 100}},
            args_ok={"args": {"q": f"query{i}", "limit": 10}},
        )
        pattern_jobs.append(jid)

    summary = await scan_recent_jobs()
    assert summary["patterns_found"] >= 3
    assert summary["auto_promoted"] >= 1
    async with session_scope() as session:
        actives = (
            (
                await session.execute(
                    select(DeepAgentMemoryRecord).where(
                        DeepAgentMemoryRecord.kind == "warning",
                        DeepAgentMemoryRecord.status == "active",
                        DeepAgentMemoryRecord.metadata_json["tool_name"].astext == unique_tool,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert actives
        assert any((r.metadata_json or {}).get("approved_by") == "auto_promotion" for r in actives)

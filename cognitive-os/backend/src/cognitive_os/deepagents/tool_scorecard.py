"""Tool effectiveness scorecard — Fase 79.4 (Fase C of the learning plan).

The aggregator walks ``job_events`` for the previous day (or any window
the caller specifies), counts ``tool_invoked / tool_succeeded /
tool_failed`` per (agent_role, tool_name), derives a reliability score,
and UPSERTs the rollup into ``tool_invocation_metrics``.

Score formula (matches §4 of AGENT_LEARNING_PLAN.md):

    reliability_score = 0.5 * success_rate
                      + 0.3 * downstream_use_rate
                      + 0.2 * approve_rate

Where:

* ``success_rate     = success_count / invoke_count``
* ``downstream_use_rate = downstream_use_count / max(success_count, 1)``
  — proxy for "was the tool result actually used by the agent"; the
  current pipeline approximates this as "tool_succeeded followed by
  ``answer_finalized`` or ``write_workspace_file`` in the same job".
* ``approve_rate     = user_approve_count / max(user_approve_count +
                       user_reject_count, 1)`` — only relevant for tools
  that surface ActionRequests; defaults to 1.0 when no approvals exist.

The aggregator is idempotent: re-running on the same window UPSERTs the
same row. It is also safe to call on overlapping windows — operators
can backfill yesterday at any time without corrupting today's rollup.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import ActionRequest, Job, JobEvent, ToolInvocationMetric

logger = logging.getLogger(__name__)

# Event types that count toward each metric.
_INVOKE_EVENTS: frozenset[str] = frozenset(
    {"tool_invoked", "tool_succeeded", "tool_failed", "tool_completed", "agent_tool_call"}
)
_SUCCESS_EVENTS: frozenset[str] = frozenset({"tool_succeeded", "tool_completed"})
_FAIL_EVENTS: frozenset[str] = frozenset({"tool_failed"})
# Downstream usage proxy: the agent produced a finalized answer after the
# tool succeeded. We don't need exact tracing — the rollup is a signal,
# not a forensic record.
_DOWNSTREAM_EVENTS: frozenset[str] = frozenset(
    {"answer_finalized", "write_workspace_file", "research_completed"}
)


@dataclass(slots=True)
class _Counters:
    invoke: int = 0
    success: int = 0
    failure: int = 0
    downstream: int = 0
    approve: int = 0
    reject: int = 0
    latencies_ms: list[float] = field(default_factory=list)


def _agent_role_from_job(job: Job) -> str:
    md = job.metadata_json or {}
    candidate = md.get("agent_name") or md.get("agent")
    if isinstance(candidate, str) and candidate:
        return candidate
    job_type: str = job.job_type or "deepagent"
    return job_type.removeprefix("deepagent_") or "deepagent"


def _tool_name(event: JobEvent) -> str | None:
    md = event.metadata_json or {}
    tool = md.get("tool") or md.get("tool_name")
    if isinstance(tool, str) and tool.strip():
        return tool.strip()
    return None


def _latency_ms_from_event(event: JobEvent) -> float | None:
    md = event.metadata_json or {}
    for key in ("latency_ms", "duration_ms"):
        value = md.get(key)
        if isinstance(value, int | float) and value > 0:
            return float(value)
    return None


def compute_reliability_score(c: _Counters) -> float | None:
    """Return the 0..1 reliability score, or None when no invocations.

    Returning None instead of 0.0 keeps the UI honest: "we have no data"
    is not the same as "this tool reliably fails".
    """
    if c.invoke <= 0:
        return None
    success_rate = c.success / c.invoke
    downstream_rate = c.downstream / c.success if c.success > 0 else 0.0
    total_decisions = c.approve + c.reject
    approve_rate = c.approve / total_decisions if total_decisions > 0 else 1.0
    return max(0.0, min(1.0, 0.5 * success_rate + 0.3 * downstream_rate + 0.2 * approve_rate))


@dataclass(slots=True)
class ScorecardEntry:
    agent_role: str
    tool_name: str
    counters: _Counters
    reliability_score: float | None

    def avg_latency(self) -> float | None:
        return (
            sum(self.counters.latencies_ms) / len(self.counters.latencies_ms)
            if self.counters.latencies_ms
            else None
        )


async def aggregate_window(
    *,
    period_start: datetime,
    period_end: datetime,
    app_settings: Settings | None = None,
) -> list[ScorecardEntry]:
    """Compute scorecard rows for ``[period_start, period_end)``.

    The function reads job events + linked ActionRequests in one round
    trip. Window typically aligns to a UTC day; daily beat passes the
    previous day's range.
    """
    cfg = app_settings or settings
    del cfg  # settings unused for now; keep param for parity with other modules

    by_key: dict[tuple[str, str], _Counters] = {}

    async with session_scope() as session:
        event_query = (
            select(JobEvent, Job)
            .join(Job, JobEvent.job_id == Job.id)
            .where(
                and_(
                    JobEvent.created_at >= period_start,
                    JobEvent.created_at < period_end,
                    JobEvent.event_type.in_(_INVOKE_EVENTS | _DOWNSTREAM_EVENTS),
                )
            )
        )
        rows = (await session.execute(event_query)).all()

        # Group raw events first so downstream events can be charged to
        # the previously-succeeded tool calls in the same job.
        job_events: dict[UUID, list[tuple[JobEvent, Job]]] = {}
        for event, job in rows:
            job_events.setdefault(job.id, []).append((event, job))

        for job_id, pairs in job_events.items():
            pairs.sort(key=lambda p: p[0].created_at)
            last_success_per_tool: dict[str, _Counters] = {}
            job_role: str | None = None
            for event, job in pairs:
                if job_role is None:
                    job_role = _agent_role_from_job(job)
                if event.event_type in _DOWNSTREAM_EVENTS:
                    # Charge the downstream signal to every tool that
                    # succeeded earlier in the job (capped at 1 per tool
                    # to prevent double-counting).
                    for counters in last_success_per_tool.values():
                        counters.downstream += 1
                    last_success_per_tool.clear()
                    continue
                tool = _tool_name(event)
                if tool is None:
                    continue
                key = (job_role or "deepagent", tool)
                counters = by_key.setdefault(key, _Counters())
                if event.event_type in _INVOKE_EVENTS - _SUCCESS_EVENTS - _FAIL_EVENTS:
                    counters.invoke += 1
                if event.event_type in _SUCCESS_EVENTS:
                    counters.success += 1
                    counters.invoke = max(counters.invoke, counters.success + counters.failure)
                    last_success_per_tool[tool] = counters
                if event.event_type in _FAIL_EVENTS:
                    counters.failure += 1
                    counters.invoke = max(counters.invoke, counters.success + counters.failure)
                latency = _latency_ms_from_event(event)
                if latency is not None:
                    counters.latencies_ms.append(latency)
            del job_id

        # Approve/reject signals come from the ActionRequest table — the
        # tool that emitted the request is recorded in ``args_redacted.tool``
        # (best-effort: only ActionRequest types map 1:1 to a tool).
        ar_query = select(ActionRequest).where(
            and_(
                ActionRequest.created_at >= period_start,
                ActionRequest.created_at < period_end,
                ActionRequest.status.in_(("approved", "rejected")),
            )
        )
        ars: Sequence[ActionRequest] = (await session.execute(ar_query)).scalars().all()
        for ar in ars:
            # ActionRequest exposes `payload_redacted` (HumanApproval uses
            # `args_redacted` — easy to confuse). The payload may include a
            # `tool` hint when the request was created by a DeepAgent tool;
            # otherwise we fall back to the action_type which is 1:1 with a
            # tool name for the personal-action set.
            tool = (ar.payload_redacted or {}).get("tool") or ar.action_type
            if not isinstance(tool, str):
                continue
            md = ar.metadata_json or {}
            role = md.get("agent_role") or md.get("agent_name") or "deepagent"
            counters = by_key.setdefault((str(role), tool), _Counters())
            if ar.status == "approved":
                counters.approve += 1
            elif ar.status == "rejected":
                counters.reject += 1

    return [
        ScorecardEntry(
            agent_role=role,
            tool_name=tool,
            counters=counters,
            reliability_score=compute_reliability_score(counters),
        )
        for (role, tool), counters in by_key.items()
    ]


async def persist_scorecard_window(
    *,
    period_start: datetime,
    period_end: datetime,
    app_settings: Settings | None = None,
) -> dict[str, Any]:
    """Aggregate the window and UPSERT one row per (role, tool).

    Returns a summary suitable for the Celery beat log.
    """
    entries = await aggregate_window(
        period_start=period_start,
        period_end=period_end,
        app_settings=app_settings,
    )
    if not entries:
        return {
            "window_start": period_start.isoformat(),
            "window_end": period_end.isoformat(),
            "entries_written": 0,
        }

    async with session_scope() as session:
        for entry in entries:
            stmt = insert(ToolInvocationMetric).values(
                agent_role=entry.agent_role,
                tool_name=entry.tool_name,
                period_start=period_start,
                period_end=period_end,
                invoke_count=entry.counters.invoke,
                success_count=entry.counters.success,
                failure_count=entry.counters.failure,
                downstream_use_count=entry.counters.downstream,
                user_approve_count=entry.counters.approve,
                user_reject_count=entry.counters.reject,
                avg_latency_ms=entry.avg_latency(),
                reliability_score=entry.reliability_score,
                metadata_json={},
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_tool_invocation_metrics_role_tool_period",
                set_={
                    "period_end": stmt.excluded.period_end,
                    "invoke_count": stmt.excluded.invoke_count,
                    "success_count": stmt.excluded.success_count,
                    "failure_count": stmt.excluded.failure_count,
                    "downstream_use_count": stmt.excluded.downstream_use_count,
                    "user_approve_count": stmt.excluded.user_approve_count,
                    "user_reject_count": stmt.excluded.user_reject_count,
                    "avg_latency_ms": stmt.excluded.avg_latency_ms,
                    "reliability_score": stmt.excluded.reliability_score,
                    "updated_at": datetime.now(UTC),
                },
            )
            await session.execute(stmt)

    return {
        "window_start": period_start.isoformat(),
        "window_end": period_end.isoformat(),
        "entries_written": len(entries),
    }


async def aggregate_previous_day(*, app_settings: Settings | None = None) -> dict[str, Any]:
    """Convenience wrapper used by the daily Celery beat.

    Computes ``[yesterday 00:00 UTC, today 00:00 UTC)`` and persists.
    """
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return await persist_scorecard_window(
        period_start=today - timedelta(days=1),
        period_end=today,
        app_settings=app_settings,
    )


async def list_recent_scorecard(*, days: int = 7, limit: int = 200) -> list[dict[str, Any]]:
    """Return recent scorecard rows for the UI tab.

    Sorted by ``period_start DESC, reliability_score DESC`` so the most
    recent / most reliable tools surface first.
    """
    cutoff = datetime.now(UTC) - timedelta(days=max(1, days))
    async with session_scope() as session:
        result = await session.execute(
            select(ToolInvocationMetric)
            .where(ToolInvocationMetric.period_start >= cutoff)
            .order_by(
                ToolInvocationMetric.period_start.desc(),
                ToolInvocationMetric.reliability_score.desc().nulls_last(),
            )
            .limit(max(1, limit))
        )
        return [_serialize(row) for row in result.scalars().all()]


async def render_scorecard_for_prompt(
    *,
    agent_role: str,
    days: int = 14,
    high_conf_threshold: float = 0.85,
    low_conf_threshold: float = 0.50,
    min_invocations: int = 5,
) -> str:
    """Render a compact "Confiabilidad de tools" section for the agent prompt.

    Returns an empty string when the rollup has no data for ``agent_role`` —
    callers should treat that as "no signal yet" and not inject anything.

    Two buckets:
    * ``high_conf`` (✅) — reliability ≥ ``high_conf_threshold``.
    * ``low_conf`` (⚠️) — reliability ≤ ``low_conf_threshold`` AND
      ``invoke_count >= min_invocations`` (filter out noise).

    The text is intentionally short (< 1 KB) so it fits comfortably inside
    the system prompt budget. (Fase 79.4 — Fase C.)
    """
    cutoff = datetime.now(UTC) - timedelta(days=max(1, days))
    async with session_scope() as session:
        result = await session.execute(
            select(ToolInvocationMetric)
            .where(
                and_(
                    ToolInvocationMetric.agent_role == agent_role,
                    ToolInvocationMetric.period_start >= cutoff,
                    ToolInvocationMetric.reliability_score.isnot(None),
                )
            )
            .order_by(ToolInvocationMetric.reliability_score.desc().nulls_last())
        )
        rows = list(result.scalars().all())
    if not rows:
        return ""
    # Aggregate across periods so the operator sees one entry per tool.
    by_tool: dict[str, ToolInvocationMetric] = {}
    for row in rows:
        if row.tool_name not in by_tool:
            by_tool[row.tool_name] = row
    high_conf = [
        r
        for r in by_tool.values()
        if r.reliability_score is not None and r.reliability_score >= high_conf_threshold
    ]
    low_conf = [
        r
        for r in by_tool.values()
        if r.reliability_score is not None
        and r.reliability_score <= low_conf_threshold
        and r.invoke_count >= min_invocations
    ]
    if not high_conf and not low_conf:
        return ""
    lines = ["## Confiabilidad de tools (últimos 14 días)"]
    if high_conf:
        lines.append("Tools confiables (úsalos primero):")
        for row in high_conf[:8]:
            lines.append(
                f"- ✅ {row.tool_name} — éxito {row.success_count}/{row.invoke_count} "
                f"(score {row.reliability_score:.2f})"
            )
    if low_conf:
        lines.append("Tools con baja confiabilidad reciente (úsalos con cuidado):")
        for row in low_conf[:8]:
            lines.append(
                f"- ⚠️ {row.tool_name} — éxito {row.success_count}/{row.invoke_count} "
                f"(score {row.reliability_score:.2f})"
            )
    return "\n".join(lines)


def _serialize(row: ToolInvocationMetric) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "agent_role": row.agent_role,
        "tool_name": row.tool_name,
        "period_start": row.period_start.isoformat(),
        "period_end": row.period_end.isoformat(),
        "invoke_count": row.invoke_count,
        "success_count": row.success_count,
        "failure_count": row.failure_count,
        "downstream_use_count": row.downstream_use_count,
        "user_approve_count": row.user_approve_count,
        "user_reject_count": row.user_reject_count,
        "avg_latency_ms": row.avg_latency_ms,
        "reliability_score": row.reliability_score,
    }

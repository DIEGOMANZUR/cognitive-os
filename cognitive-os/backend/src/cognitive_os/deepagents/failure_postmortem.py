"""Failure post-mortems — Fase 79.3 (Fase D of the agent learning plan).

The scanner walks recent ``JobEvent`` rows looking for *recoverable
failure patterns*: a ``tool_failed`` event followed (within the same
job, within a short window) by a ``tool_succeeded`` event for the same
tool with similar arguments. The intuition: the agent tried something
that didn't work, then tried a variant that did. That's a *warning*
worth memorising so future runs skip the broken first attempt.

Output: ``DeepAgentMemoryProposal(kind="warning")`` rows that go through
the standard approval flow. A pattern that the operator approves once
becomes part of the system prompt for future agents in that role.

Auto-promotion rule: if the same (agent_role, tool_name, normalised_args)
pattern has been observed ≥ N times (default 3) WITHOUT any operator
rejection, the scanner auto-promotes the warning to ``active`` without
asking again — the evidence is overwhelming and the operator's silent
acceptance counts as approval. This matches §3 of AGENT_LEARNING_PLAN.md.

Idempotency: each pair (failed_event_id, succeeded_event_id) is recorded
in ``DeepAgentMemoryProposalRecord.metadata_json.evidence_pair`` so the
scanner can skip pairs it has already processed. The Job row itself
does NOT carry a marker (unlike the recipe extractor) because a single
job may surface several failure patterns over its lifetime.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import (
    DeepAgentMemoryProposalRecord,
    DeepAgentMemoryRecord,
    Job,
    JobEvent,
)
from cognitive_os.deepagents.memory_schemas import DeepAgentMemoryProposal
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService

logger = logging.getLogger(__name__)

# Event types we treat as "the agent invoked a tool" — needed to walk the
# event stream and pair failure → recovery.
_FAIL_EVENTS: frozenset[str] = frozenset({"tool_failed"})
_SUCCESS_EVENTS: frozenset[str] = frozenset({"tool_succeeded", "tool_completed"})

# Max gap (in event index, not time) between failure and recovery — keeps
# us from pairing two events that are obviously unrelated. 10 is enough to
# tolerate retry loops with intermediate retries / logs.
_PAIR_MAX_DISTANCE = 10


@dataclass(slots=True)
class FailurePattern:
    """Captures one recoverable failure observed in a job trajectory."""

    job_id: UUID
    agent_role: str
    tool_name: str
    failed_event_id: UUID
    succeeded_event_id: UUID
    failure_message: str
    success_args_normalised: str
    failure_args_normalised: str


@dataclass(slots=True)
class PostMortemResult:
    job_id: UUID
    status: str  # "proposal_created" | "auto_promoted" | "duplicate" | "no_patterns"
    proposal_id: str | None = None
    memory_id: str | None = None
    pattern_count: int = 0


def _normalise_args(metadata: dict[str, Any] | None) -> str:
    """Render tool args into a stable string for similarity matching.

    Strips volatile keys (``request_id``, ``timestamp``, ``trace_id``…)
    and lowercases the rest. We don't need full embedding similarity —
    the patterns we care about share the same tool + similar key paths
    even if specific values differ (e.g. two ``search_local_docs`` calls
    with different ``query`` strings still expose the same anti-pattern
    when both fail on missing index).
    """
    if not metadata:
        return ""
    volatile = {"request_id", "trace_id", "timestamp", "started_at", "finished_at"}
    args = metadata.get("args") or metadata.get("input") or {}
    if not isinstance(args, dict):
        return str(args)[:200].lower()
    kept = {k: str(v)[:80] for k, v in args.items() if k not in volatile}
    return repr(sorted(kept.items())).lower()[:400]


def _strings_similar(a: str, b: str, *, threshold: float = 0.5) -> bool:
    """Cheap Jaccard-style similarity on token sets — no embedding model needed.

    The scanner runs daily on hundreds of events; loading an embedding
    model just for pairing failures would be over-engineering. Tokens
    overlap is enough to catch the "same args, different value" case.
    """
    if not a or not b:
        return False
    if a == b:
        return True
    tokens_a = set(re.split(r"[\s,(){}\[\]'\"=:]+", a))
    tokens_b = set(re.split(r"[\s,(){}\[\]'\"=:]+", b))
    tokens_a.discard("")
    tokens_b.discard("")
    if not tokens_a or not tokens_b:
        return False
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) >= threshold


def _tool_name_from_event(event: JobEvent) -> str | None:
    md = event.metadata_json or {}
    tool = md.get("tool") or md.get("tool_name")
    if isinstance(tool, str) and tool.strip():
        return tool.strip()
    return None


def _agent_role_from_job(job: Job) -> str:
    md = job.metadata_json or {}
    candidate = md.get("agent_name") or md.get("agent")
    if isinstance(candidate, str) and candidate:
        return candidate
    # Map job_type to role: deepagent_research → research, etc.
    job_type: str = job.job_type or "deepagent"
    return job_type.removeprefix("deepagent_") or "deepagent"


def find_failure_patterns(
    job: Job,
    events: Sequence[JobEvent],
) -> list[FailurePattern]:
    """Walk a job's events and return every ``tool_failed → tool_succeeded``
    pair where the tool is the same and the args are similar (Jaccard ≥ 0.5).

    The list is empty for jobs without recoveries — that's the common case
    and the caller short-circuits without proposal work.
    """
    role = _agent_role_from_job(job)
    patterns: list[FailurePattern] = []
    ordered = sorted(events, key=lambda e: e.created_at)
    for i, failed in enumerate(ordered):
        if failed.event_type not in _FAIL_EVENTS:
            continue
        failed_tool = _tool_name_from_event(failed)
        if not failed_tool:
            continue
        failed_args = _normalise_args(failed.metadata_json)
        # Look ahead at most _PAIR_MAX_DISTANCE events for a successful
        # recovery using the same tool.
        for succeeded in ordered[i + 1 : i + 1 + _PAIR_MAX_DISTANCE]:
            if succeeded.event_type not in _SUCCESS_EVENTS:
                continue
            ok_tool = _tool_name_from_event(succeeded)
            if ok_tool != failed_tool:
                continue
            ok_args = _normalise_args(succeeded.metadata_json)
            if not _strings_similar(failed_args, ok_args):
                continue
            patterns.append(
                FailurePattern(
                    job_id=job.id,
                    agent_role=role,
                    tool_name=failed_tool,
                    failed_event_id=failed.id,
                    succeeded_event_id=succeeded.id,
                    failure_message=(failed.message or "")[:300],
                    failure_args_normalised=failed_args,
                    success_args_normalised=ok_args,
                )
            )
            # Move on — we don't want duplicate pairs from one failure.
            break
    return patterns


async def record_failure_pattern(
    pattern: FailurePattern,
    *,
    memory_service: DeepAgentMemoryService | None = None,
    app_settings: Settings | None = None,
) -> PostMortemResult:
    """Persist one failure pattern as a warning proposal (or auto-promote).

    Returns a :class:`PostMortemResult` describing what happened so the
    Celery task can log a one-liner.
    """
    cfg = app_settings or settings
    service = memory_service or DeepAgentMemoryService()
    threshold = cfg.failure_postmortem_autopromote_threshold

    async with session_scope() as session:
        # Idempotency check — has this exact event pair already been recorded?
        # The proposal record stores caller-supplied `metadata` under
        # `metadata_json["payload"]` (see _persist_proposal_in_session),
        # so we drill into ["payload"] for the evidence_pair lookup.
        evidence_key = f"{pattern.failed_event_id}:{pattern.succeeded_event_id}"
        # Use first() instead of scalar_one_or_none() because a faulty
        # historical scan may have inserted multiple rows with the same
        # evidence_pair (defensive coding — uniqueness is a contract we
        # enforce going forward but the table may carry legacy data).
        existing_for_pair = (
            await session.execute(
                select(DeepAgentMemoryProposalRecord)
                .where(
                    DeepAgentMemoryProposalRecord.metadata_json["payload"]["evidence_pair"].astext
                    == evidence_key
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing_for_pair is not None:
            return PostMortemResult(
                pattern.job_id,
                "duplicate",
                proposal_id=str(existing_for_pair.id),
            )

        # Count prior occurrences of the same (agent_role, tool_name)
        # pattern. We don't require identical args because the goal is to
        # warn the agent about a recurring class of failure, not a single
        # instance.
        proposal_match = await session.execute(
            select(DeepAgentMemoryProposalRecord).where(
                and_(
                    DeepAgentMemoryProposalRecord.metadata_json["payload"]["pattern_kind"].astext
                    == "failure_recovery",
                    DeepAgentMemoryProposalRecord.metadata_json["payload"]["agent_role"].astext
                    == pattern.agent_role,
                    DeepAgentMemoryProposalRecord.metadata_json["payload"]["tool_name"].astext
                    == pattern.tool_name,
                )
            )
        )
        prior_proposals = list(proposal_match.scalars().all())
        # Active warnings about the same pattern. If an operator-approved (or
        # previously auto-promoted) warning already covers this pattern, the
        # new pattern is redundant — short-circuit to "duplicate" so we don't
        # spam the operator's Memoria UI with N copies of the same advice.
        active_match = await session.execute(
            select(DeepAgentMemoryRecord).where(
                and_(
                    DeepAgentMemoryRecord.kind == "warning",
                    DeepAgentMemoryRecord.status == "active",
                    DeepAgentMemoryRecord.metadata_json["agent_role"].astext == pattern.agent_role,
                    DeepAgentMemoryRecord.metadata_json["tool_name"].astext == pattern.tool_name,
                )
            )
        )
        active_warnings = list(active_match.scalars().all())
        if active_warnings:
            return PostMortemResult(
                pattern.job_id,
                "duplicate",
                pattern_count=len(prior_proposals) + len(active_warnings),
            )
        # Rejected proposals lower the auto-promotion confidence — operator
        # already said no, don't override them silently.
        rejected_count = sum(1 for p in prior_proposals if p.status == "rejected")
        if rejected_count >= cfg.failure_postmortem_max_rejections:
            return PostMortemResult(pattern.job_id, "duplicate", pattern_count=len(prior_proposals))

        occurrence_index = len(prior_proposals) + 1
        # Auto-promotion is the ONLY auto-deploy path in the learning plan
        # (AGENT_LEARNING_PLAN.md Fase D). `failure_postmortem_auto_promote_enabled`
        # is its kill switch: with it false, every learned warning is forced
        # through the operator approval gate — a literal "cero auto-deploy"
        # posture. See AUDIT-2026-C.
        auto_promote = (
            cfg.failure_postmortem_auto_promote_enabled
            and occurrence_index >= threshold
            and rejected_count == 0
        )

        proposal_id = str(uuid4())
        proposed_content = (
            f"Warning: `{pattern.tool_name}` falló en {pattern.agent_role} "
            f"con args parecidos a {pattern.failure_args_normalised[:160]} "
            f"({pattern.failure_message[:160] or 'sin mensaje'}). "
            f"La recuperación exitosa usó args {pattern.success_args_normalised[:160]}."
        )
        proposal = DeepAgentMemoryProposal(
            proposal_id=proposal_id,
            proposed_by_agent="failure_postmortem_scanner",
            scope="agent",
            reason=(
                f"Patrón de recuperación tras fallo de `{pattern.tool_name}` "
                f"(ocurrencia #{occurrence_index}). "
                + (
                    f"Auto-promovido si ocurrencia ≥ {threshold} sin rechazos previos."
                    if cfg.failure_postmortem_auto_promote_enabled
                    else "Auto-promoción deshabilitada; requiere aprobación del operador."
                )
            ),
            proposed_content=proposed_content,
            sensitivity="internal",
            source_task_id=str(pattern.job_id),
            requires_approval=not auto_promote,
            kind="warning",
            confidence=min(0.4 + 0.15 * (occurrence_index - 1), 0.95),
            metadata={
                "pattern_kind": "failure_recovery",
                "agent_role": pattern.agent_role,
                "tool_name": pattern.tool_name,
                "evidence_pair": evidence_key,
                "failure_message": pattern.failure_message,
                "failure_args_normalised": pattern.failure_args_normalised,
                "success_args_normalised": pattern.success_args_normalised,
                "occurrence_index": occurrence_index,
                "extracted_by": "fase79_failure_postmortem",
            },
        )
        await service.propose_memory_update(proposal, session=session)
        if auto_promote:
            # We could rely on `approve_memory_proposal` but that opens a
            # new session and we want everything in one transaction.
            await session.flush()
            record = await session.get(DeepAgentMemoryProposalRecord, UUID(proposal_id))
            assert record is not None  # noqa: S101
            from datetime import UTC, datetime  # noqa: PLC0415

            record.status = "applied"
            record.decided_at = datetime.now(UTC)
            materialised = DeepAgentMemoryRecord(
                scope=record.scope,
                user_id=None,
                case_id=None,
                thread_id=None,
                agent_name=record.proposed_by_agent,
                kind="warning",
                content_redacted=record.proposed_content_redacted,
                source="consolidated",
                confidence=proposal.confidence,
                sensitivity=record.sensitivity,
                status="active",
                metadata_json={
                    "approved_by": "auto_promotion",
                    "proposal_id": proposal_id,
                    "source_task_id": str(pattern.job_id),
                    **(proposal.metadata or {}),
                },
            )
            session.add(materialised)
            await session.flush()
            return PostMortemResult(
                pattern.job_id,
                "auto_promoted",
                proposal_id=proposal_id,
                memory_id=str(materialised.id),
                pattern_count=occurrence_index,
            )
        return PostMortemResult(
            pattern.job_id,
            "proposal_created",
            proposal_id=proposal_id,
            pattern_count=occurrence_index,
        )


async def scan_recent_jobs(
    *,
    memory_service: DeepAgentMemoryService | None = None,
    app_settings: Settings | None = None,
) -> dict[str, Any]:
    """Sweep recent jobs for failure-recovery patterns.

    Called by the Celery beat task; safe to call manually for tests or
    operator-triggered runs (admin REST endpoint).
    """
    cfg = app_settings or settings
    limit = max(1, cfg.failure_postmortem_max_per_cycle)

    async with session_scope() as session:
        # Recent jobs that completed or completed_with_warnings — those are
        # the ones whose trajectory contains a recovery. failed jobs are
        # uninteresting (no recovery), running jobs are too volatile.
        query = (
            select(Job)
            .where(
                or_(
                    Job.status == "completed",
                    Job.status == "completed_with_warnings",
                )
            )
            .order_by(Job.updated_at.desc())
            .limit(limit)
        )
        jobs: Sequence[Job] = (await session.execute(query)).scalars().all()
        job_event_pairs: list[tuple[Job, Sequence[JobEvent]]] = []
        for job in jobs:
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
            job_event_pairs.append((job, events))

    summary: dict[str, Any] = {
        "scanned_jobs": len(job_event_pairs),
        "patterns_found": 0,
        "proposals_created": 0,
        "auto_promoted": 0,
        "duplicates": 0,
        "proposal_ids": [],
        "memory_ids": [],
    }
    for job, events in job_event_pairs:
        patterns = find_failure_patterns(job, events)
        if not patterns:
            continue
        summary["patterns_found"] += len(patterns)
        for pattern in patterns:
            try:
                result = await record_failure_pattern(
                    pattern,
                    memory_service=memory_service,
                    app_settings=cfg,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "failure_postmortem_record_failed job_id=%s tool=%s",
                    pattern.job_id,
                    pattern.tool_name,
                )
                logger.warning("failure_postmortem_skip error=%s", type(exc).__name__)
                continue
            if result.status == "proposal_created":
                summary["proposals_created"] += 1
                if result.proposal_id:
                    summary["proposal_ids"].append(result.proposal_id)
            elif result.status == "auto_promoted":
                summary["auto_promoted"] += 1
                if result.memory_id:
                    summary["memory_ids"].append(result.memory_id)
            elif result.status == "duplicate":
                summary["duplicates"] += 1
    return summary

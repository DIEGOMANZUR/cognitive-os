"""Nightly reflection — Fase 81 (Fase E of the agent learning plan).

Once a day (cron at 03:00 UTC by default) the reflector asks the
primary chat model (gpt-5.5 via the operator's gateway) to look at the
last 24 hours of conversational threads and surface implicit
preferences / lessons the operator has expressed. Each proposal must
quote the original message — the validator drops any proposal whose
``evidence_quotes`` are not literal substrings of the transcript we
shipped to the model. This is the single most important guardrail in
§6.5 of ``AGENT_LEARNING_PLAN.md``.

Auto-disable: if more than ``NIGHTLY_REFLECTION_MAX_REJECTION_RATE`` of
the proposals emitted by ``proposed_by_agent="nightly_reflection"`` in
the last ``NIGHTLY_REFLECTION_REJECTION_WATCH_DAYS`` window were
rejected by the operator, the next pass exits early without burning
tokens. The operator re-enables by flipping the env flag.

Inputs we treat as the "transcript" for a thread:

* The user-facing payload of ``Job.metadata_json["user_query"]`` /
  ``["preview"]["title"]`` (if present).
* Significant ``JobEvent.message`` entries — limited to events that
  carry human-readable text.
* ``HumanApproval`` decisions (approved / rejected) with their notes.

We deliberately do **not** read LangGraph checkpoint tables — they are
managed by the langgraph_postgres library and we don't want to grow a
coupling with their internal schema. Threading the existing JobEvent /
HumanApproval rows gives us everything the operator can also see in
the UI, which is the right "audit-able" surface for evidence.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import (
    AuditEvent,
    ConversationThread,
    DeepAgentMemoryProposalRecord,
    HumanApproval,
    Job,
    JobEvent,
)
from cognitive_os.deepagents.memory_schemas import (
    DeepAgentMemoryKind,
    DeepAgentMemoryProposal,
    DeepAgentMemorySensitivity,
)
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService
from cognitive_os.deepagents.nightly_reflection_prompts import (
    REFLECTION_RESPONSE_FORMAT,
    REFLECTION_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

# Injectable LLM hook so tests can run without burning tokens. The
# default implementation wraps the primary chat model. Return must be a
# string containing JSON the validator can parse.
ReflectionLLM = Callable[[list[dict[str, str]]], "str | None"]


@dataclass(slots=True)
class TranscriptSegment:
    """One line of the transcript with an opaque id the LLM must cite."""

    message_id: str
    role: str  # "user" | "agent" | "tool" | "operator_decision"
    text: str


@dataclass(slots=True)
class Transcript:
    thread_id: str
    user_id: str | None
    segments: list[TranscriptSegment] = field(default_factory=list)

    def all_text(self) -> str:
        return "\n".join(f"[{s.message_id}|{s.role}] {s.text}" for s in self.segments)

    def has_quote(self, quote: str) -> bool:
        return quote.strip() in self.all_text() if quote and quote.strip() else False

    def known_message_id(self, mid: str) -> bool:
        return any(s.message_id == mid for s in self.segments)


@dataclass(slots=True)
class ReflectionProposal:
    """Parsed + validated LLM output for one proposal."""

    kind: str  # "preference" | "lesson"
    content: str
    confidence: float
    sensitivity: str
    evidence_message_ids: list[str]
    evidence_quotes: list[str]


@dataclass(slots=True)
class ReflectionRunResult:
    """Outcome of a single reflection pass over one thread."""

    thread_id: str
    status: str  # "ok" | "skipped_no_transcript" | "llm_error" | "no_evidence"
    proposals_created: int = 0
    proposal_ids: list[str] = field(default_factory=list)
    reason: str | None = None


def _default_llm_invoker(messages: list[dict[str, str]]) -> str | None:
    """Production LLM — wraps `create_primary_chat_model`."""
    from cognitive_os.agents.llm_factory import create_primary_chat_model  # noqa: PLC0415

    llm = create_primary_chat_model()
    formatted: list[tuple[str, str]] = [(str(m["role"]), str(m["content"])) for m in messages]
    response = llm.invoke(formatted)
    content = getattr(response, "content", response)
    if isinstance(content, list):
        parts: list[str] = []
        for chunk in content:
            if isinstance(chunk, dict):
                parts.append(str(chunk.get("text") or chunk.get("content") or ""))
            else:
                parts.append(str(chunk))
        return "".join(parts)
    return str(content) if content is not None else None


# ----------------------------------------------------------------------
# Transcript builder
# ----------------------------------------------------------------------


def _job_user_text(job: Job) -> str | None:
    md = job.metadata_json or {}
    for key in ("user_query", "query", "user_message", "input_text"):
        candidate = md.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    preview = md.get("preview")
    if isinstance(preview, dict):
        candidate = preview.get("title") or preview.get("description")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _event_user_text(event: JobEvent) -> str | None:
    if event.message and event.message.strip():
        return event.message.strip()
    md = event.metadata_json or {}
    for key in ("message", "summary", "text"):
        candidate = md.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _approval_text(approval: HumanApproval) -> str:
    decision = (approval.status or "pending").lower()
    summary = approval.action or "(decision)"
    args = approval.args_redacted or {}
    blurb = json.dumps(args, ensure_ascii=False)[:200] if args else ""
    parts = [f"decision={decision}", f"action={summary}"]
    if approval.approver_user_id:
        parts.append(f"by={approval.approver_user_id}")
    if blurb:
        parts.append(f"args={blurb}")
    return " · ".join(parts)


async def build_transcript_for_thread(
    thread: ConversationThread,
    *,
    lookback_start: datetime,
    session: AsyncSession,
    max_segments: int = 60,
) -> Transcript:
    """Assemble a flat transcript from Jobs / JobEvents / HumanApprovals.

    The LLM never sees the underlying ORM objects — only the message_id
    strings we generate here so the validator can cross-check quotes.
    """
    transcript = Transcript(
        thread_id=str(thread.id),
        user_id=str(thread.user_id) if thread.user_id else None,
    )
    job_rows: Sequence[Job] = (
        (
            await session.execute(
                select(Job)
                .where(
                    and_(
                        Job.thread_id == thread.id,
                        Job.created_at >= lookback_start,
                    )
                )
                .order_by(Job.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    job_ids = [job.id for job in job_rows]
    for job in job_rows:
        text = _job_user_text(job)
        if text:
            transcript.segments.append(
                TranscriptSegment(
                    message_id=f"job:{job.id}",
                    role="user",
                    text=text[:1000],
                )
            )
    if job_ids:
        event_rows: Sequence[JobEvent] = (
            (
                await session.execute(
                    select(JobEvent)
                    .where(
                        and_(
                            JobEvent.job_id.in_(job_ids),
                            JobEvent.created_at >= lookback_start,
                        )
                    )
                    .order_by(JobEvent.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        for event in event_rows:
            text = _event_user_text(event)
            if not text:
                continue
            role = "agent"
            etype = (event.event_type or "").lower()
            if "tool" in etype:
                role = "tool"
            elif "user" in etype or "input" in etype:
                role = "user"
            transcript.segments.append(
                TranscriptSegment(
                    message_id=f"event:{event.id}",
                    role=role,
                    text=text[:1000],
                )
            )
    approval_rows: Sequence[HumanApproval] = (
        (
            await session.execute(
                select(HumanApproval)
                .where(
                    and_(
                        HumanApproval.thread_id == thread.id,
                        HumanApproval.created_at >= lookback_start,
                    )
                )
                .order_by(HumanApproval.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    for approval in approval_rows:
        transcript.segments.append(
            TranscriptSegment(
                message_id=f"approval:{approval.id}",
                role="operator_decision",
                text=_approval_text(approval),
            )
        )
    if len(transcript.segments) > max_segments:
        # Keep the most recent N segments — those are the ones with the
        # freshest signal about the user's current preferences.
        transcript.segments = transcript.segments[-max_segments:]
    return transcript


# ----------------------------------------------------------------------
# LLM call + response parser
# ----------------------------------------------------------------------


def _extract_json_blob(raw: str) -> str:
    """Pull the first JSON array or object out of ``raw``.

    The LLM is asked to emit a strict JSON array, but `langchain-openai`
    sometimes wraps the answer with prose or a fenced block. We accept
    either — the validator handles the rest.
    """
    if not raw:
        return ""
    fence = re.search(r"```(?:json)?\s*(.+?)```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    array = re.search(r"\[\s*[\s\S]*\]", raw)
    if array:
        return array.group(0)
    obj = re.search(r"\{\s*[\s\S]*\}", raw)
    if obj:
        return obj.group(0)
    return raw.strip()


def parse_reflection_response(raw: str | None) -> list[dict[str, Any]]:
    """Coerce the model output into a list of dicts. Returns ``[]`` on
    parse error so the caller can record a transient skip without
    poisoning the validator with a half-baked structure.
    """
    if not raw:
        return []
    blob = _extract_json_blob(raw)
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        # Some models wrap arrays under a "proposals" key.
        for key in ("proposals", "items", "results", "preferences"):
            inner = parsed.get(key)
            if isinstance(inner, list):
                parsed = inner
                break
        else:
            parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


# Quotes shorter than this are too generic to count as evidence — a
# 3-char "el" appears in almost any Spanish transcript and would let a
# hallucinating model "prove" anything. 12 chars forces a real phrase.
_MIN_QUOTE_LEN = 12


def validate_proposal(
    raw: dict[str, Any],
    transcript: Transcript,
    *,
    min_confidence: float,
) -> ReflectionProposal | None:
    """Return a :class:`ReflectionProposal` or ``None`` if validation fails.

    Rules (matches §6.5 of AGENT_LEARNING_PLAN.md):
    * Quotes must be literal substrings of the transcript.
    * Quotes must be at least ``_MIN_QUOTE_LEN`` chars (no trivial tokens).
    * Message IDs must reference real transcript segments.
    * Confidence must clear ``min_confidence``.
    * Sensitivity may not be ``secret`` (would block storage anyway).
    """
    kind = str(raw.get("kind") or "").lower()
    if kind not in {"preference", "lesson"}:
        return None
    content = str(raw.get("content") or "").strip()
    if not content:
        return None
    raw_confidence = raw.get("confidence")
    try:
        confidence = float(raw_confidence) if raw_confidence is not None else 0.0
    except (TypeError, ValueError):
        return None
    if confidence < min_confidence:
        return None
    quotes_raw = raw.get("evidence_quotes") or []
    ids_raw = raw.get("evidence_message_ids") or []
    if not isinstance(quotes_raw, list) or not isinstance(ids_raw, list):
        return None
    quotes = [str(q).strip() for q in quotes_raw if isinstance(q, str) and q.strip()]
    ids = [str(i).strip() for i in ids_raw if isinstance(i, str) and i.strip()]
    if not quotes or not ids:
        return None
    if any(len(q) < _MIN_QUOTE_LEN for q in quotes):
        return None
    if not all(transcript.has_quote(q) for q in quotes):
        return None
    if not all(transcript.known_message_id(i) for i in ids):
        return None
    sensitivity = str(raw.get("sensitivity") or "internal").lower()
    if sensitivity not in {"public", "internal", "sensitive"}:
        sensitivity = "internal"
    return ReflectionProposal(
        kind=kind,
        content=content[:2000],
        confidence=max(0.0, min(1.0, confidence)),
        sensitivity=sensitivity,
        evidence_message_ids=ids,
        evidence_quotes=quotes,
    )


# ----------------------------------------------------------------------
# Auto-disable check
# ----------------------------------------------------------------------


async def is_auto_disabled(
    *,
    app_settings: Settings | None = None,
    now: datetime | None = None,
) -> tuple[bool, str | None]:
    """Return ``(True, reason)`` if the rejection rate exceeds threshold.

    Idempotent / cheap — counts rows in the proposals table over the
    watch window. Used by the beat task as a circuit breaker.
    """
    cfg = app_settings or settings
    if cfg.nightly_reflection_max_rejection_rate >= 1.0:
        return False, None
    watch_days = max(1, cfg.nightly_reflection_rejection_watch_days)
    horizon = (now or datetime.now(UTC)) - timedelta(days=watch_days)
    async with session_scope() as session:
        result = await session.execute(
            select(
                DeepAgentMemoryProposalRecord.status,
            ).where(
                and_(
                    DeepAgentMemoryProposalRecord.proposed_by_agent == "nightly_reflection",
                    DeepAgentMemoryProposalRecord.created_at >= horizon,
                )
            )
        )
        statuses = [row[0] for row in result.all()]
    if not statuses:
        return False, None
    decided = [s for s in statuses if s in {"approved", "rejected", "applied"}]
    if len(decided) < 5:
        # Not enough decisions yet to trust the rate; let the scanner run.
        return False, None
    rejected = sum(1 for s in decided if s == "rejected")
    rate = rejected / len(decided)
    if rate > cfg.nightly_reflection_max_rejection_rate:
        return True, f"rejection_rate={rate:.0%} > {cfg.nightly_reflection_max_rejection_rate:.0%}"
    return False, None


# ----------------------------------------------------------------------
# Public entry points
# ----------------------------------------------------------------------


async def reflect_on_thread(
    thread: ConversationThread,
    *,
    lookback_start: datetime,
    session: AsyncSession,
    memory_service: DeepAgentMemoryService,
    llm_invoker: ReflectionLLM,
    app_settings: Settings,
) -> ReflectionRunResult:
    """Run the reflection pass on a single thread.

    Always commits via the caller's transaction; the worker wraps each
    thread in its own session so a per-thread LLM error doesn't roll
    back the whole night's work.
    """
    transcript = await build_transcript_for_thread(
        thread,
        lookback_start=lookback_start,
        session=session,
    )
    if not transcript.segments:
        return ReflectionRunResult(
            thread_id=str(thread.id),
            status="skipped_no_transcript",
            reason="empty_transcript",
        )
    user_msg = (
        "Conversación (cada línea lleva un [id|role] que debes citar exactamente):\n\n"
        f"{transcript.all_text()}\n\n"
        "Responde un JSON array siguiendo el formato indicado."
    )
    messages = [
        {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
        {"role": "user", "content": REFLECTION_RESPONSE_FORMAT},
        {"role": "user", "content": user_msg},
    ]
    try:
        raw = llm_invoker(messages)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "nightly_reflection_llm_failed thread_id=%s error=%s",
            thread.id,
            type(exc).__name__,
        )
        return ReflectionRunResult(
            thread_id=str(thread.id),
            status="llm_error",
            reason=f"{type(exc).__name__}: {exc}",
        )

    items = parse_reflection_response(raw)
    if not items:
        return ReflectionRunResult(
            thread_id=str(thread.id),
            status="no_evidence",
            reason="parse_or_empty",
        )

    max_proposals = max(1, app_settings.nightly_reflection_max_proposals_per_thread)
    proposals_made: list[str] = []
    for item in items[:max_proposals]:
        validated = validate_proposal(
            item,
            transcript,
            min_confidence=app_settings.nightly_reflection_min_confidence,
        )
        if validated is None:
            continue
        proposal = DeepAgentMemoryProposal(
            proposal_id=str(uuid4()),
            proposed_by_agent="nightly_reflection",
            scope="user" if transcript.user_id else "thread",
            reason="Reflexión nocturna sobre la conversación del último día.",
            proposed_content=validated.content,
            sensitivity=_cast_sensitivity(validated.sensitivity),
            source_task_id=str(thread.id),
            requires_approval=True,
            user_id=transcript.user_id,
            thread_id=str(thread.id),
            kind=_cast_kind(validated.kind),
            confidence=validated.confidence,
            metadata={
                "evidence_message_ids": validated.evidence_message_ids,
                "evidence_quotes": validated.evidence_quotes,
                "transcript_size": len(transcript.segments),
                "extracted_by": "fase81_nightly_reflection",
            },
        )
        try:
            await memory_service.propose_memory_update(proposal, session=session)
        except Exception:  # noqa: BLE001
            logger.exception("nightly_reflection_persist_failed thread_id=%s", thread.id)
            continue
        proposals_made.append(proposal.proposal_id)
    return ReflectionRunResult(
        thread_id=str(thread.id),
        status="ok" if proposals_made else "no_evidence",
        proposals_created=len(proposals_made),
        proposal_ids=proposals_made,
        reason=None if proposals_made else "all_proposals_rejected_by_validator",
    )


def _cast_kind(value: str) -> DeepAgentMemoryKind:
    return value  # type: ignore[return-value]


def _cast_sensitivity(value: str) -> DeepAgentMemorySensitivity:
    return value  # type: ignore[return-value]


async def run_nightly_reflection(
    *,
    llm_invoker: ReflectionLLM | None = None,
    memory_service: DeepAgentMemoryService | None = None,
    app_settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Sweep recent threads and emit reflection proposals.

    Driven by the daily Celery beat. Each thread runs in its own session
    so one model error / transient DB hiccup never poisons the whole
    pass. The summary returned is what the beat logs.
    """
    cfg = app_settings or settings
    if not cfg.nightly_reflection_enabled:
        return {"skipped": True, "reason": "NIGHTLY_REFLECTION_ENABLED=false"}
    disabled, reason = await is_auto_disabled(app_settings=cfg, now=now)
    if disabled:
        async with session_scope() as session:
            session.add(
                AuditEvent(
                    action="deepagents.reflection.auto_disabled",
                    actor_id="nightly_reflection",
                    resource_type="deepagent_reflection",
                    resource_id="self",
                    metadata_json={"reason": reason},
                )
            )
        logger.warning("nightly_reflection_auto_disabled reason=%s", reason)
        return {"skipped": True, "reason": reason}

    lookback_start = (now or datetime.now(UTC)) - timedelta(
        hours=cfg.nightly_reflection_lookback_hours,
    )
    invoker = llm_invoker or _default_llm_invoker
    service = memory_service or DeepAgentMemoryService()

    summary: dict[str, Any] = {
        "scanned_threads": 0,
        "proposals_created": 0,
        "threads_with_proposals": 0,
        "proposal_ids": [],
        "llm_errors": 0,
        "no_evidence": 0,
    }
    async with session_scope() as outer:
        threads: Sequence[ConversationThread] = (
            (
                await outer.execute(
                    select(ConversationThread)
                    .where(ConversationThread.updated_at >= lookback_start)
                    .order_by(ConversationThread.updated_at.desc())
                    .limit(max(1, cfg.nightly_reflection_max_threads_per_cycle))
                )
            )
            .scalars()
            .all()
        )

    for thread in threads:
        summary["scanned_threads"] += 1
        async with session_scope() as session:
            attached = await session.get(ConversationThread, thread.id)
            if attached is None:
                continue
            result = await reflect_on_thread(
                attached,
                lookback_start=lookback_start,
                session=session,
                memory_service=service,
                llm_invoker=invoker,
                app_settings=cfg,
            )
        if result.status == "ok" and result.proposal_ids:
            summary["threads_with_proposals"] += 1
            summary["proposals_created"] += result.proposals_created
            summary["proposal_ids"].extend(result.proposal_ids)
        elif result.status == "llm_error":
            summary["llm_errors"] += 1
        elif result.status in {"no_evidence", "skipped_no_transcript"}:
            summary["no_evidence"] += 1
    return summary


async def list_recent_reflections(*, days: int = 7) -> list[dict[str, Any]]:
    """Return reflection proposals for the UI."""
    cutoff = datetime.now(UTC) - timedelta(days=max(1, days))
    async with session_scope() as session:
        result = await session.execute(
            select(DeepAgentMemoryProposalRecord)
            .where(
                and_(
                    DeepAgentMemoryProposalRecord.proposed_by_agent == "nightly_reflection",
                    DeepAgentMemoryProposalRecord.created_at >= cutoff,
                )
            )
            .order_by(DeepAgentMemoryProposalRecord.created_at.desc())
        )
        rows: list[dict[str, Any]] = []
        for row in result.scalars().all():
            meta = row.metadata_json or {}
            payload = meta.get("payload") or {}
            rows.append(
                {
                    "proposal_id": str(row.id),
                    "status": row.status,
                    "kind": meta.get("kind") or "lesson",
                    "scope": row.scope,
                    "reason": row.reason,
                    "proposed_content": row.proposed_content_redacted,
                    "evidence_message_ids": payload.get("evidence_message_ids") or [],
                    "evidence_quotes": payload.get("evidence_quotes") or [],
                    "confidence": meta.get("confidence"),
                    "thread_id": meta.get("thread_id"),
                    "user_id": meta.get("user_id"),
                    "created_at": row.created_at.isoformat(),
                    "decided_at": row.decided_at.isoformat() if row.decided_at else None,
                }
            )
        return rows


__all__ = [
    "ReflectionProposal",
    "ReflectionRunResult",
    "Transcript",
    "TranscriptSegment",
    "build_transcript_for_thread",
    "is_auto_disabled",
    "list_recent_reflections",
    "parse_reflection_response",
    "reflect_on_thread",
    "run_nightly_reflection",
    "validate_proposal",
]

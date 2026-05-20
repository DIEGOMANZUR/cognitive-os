"""Fase 81 (Fase E) — nightly reflection regression tests.

The LLM is fully injectable, so these tests never hit the network. We
exercise the validator (evidence-quote enforcement) plus the full
``run_nightly_reflection`` driver on real Postgres state.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import (
    ConversationThread,
    DeepAgentMemoryProposalRecord,
    HumanApproval,
    Job,
    JobEvent,
)
from cognitive_os.deepagents.nightly_reflection import (
    Transcript,
    TranscriptSegment,
    build_transcript_for_thread,
    is_auto_disabled,
    parse_reflection_response,
    run_nightly_reflection,
    validate_proposal,
)


def _proposal_payload(
    *,
    kind: str = "preference",
    content: str = "El usuario prefiere respuestas breves.",
    confidence: float = 0.85,
    sensitivity: str = "internal",
    message_ids: list[str] | None = None,
    quotes: list[str] | None = None,
) -> dict[str, object]:
    return {
        "kind": kind,
        "content": content,
        "confidence": confidence,
        "sensitivity": sensitivity,
        "evidence_message_ids": message_ids or [],
        "evidence_quotes": quotes or [],
    }


def _transcript(*, segments: list[tuple[str, str, str]]) -> Transcript:
    return Transcript(
        thread_id="thr",
        user_id="u-1",
        segments=[
            TranscriptSegment(message_id=mid, role=role, text=text) for mid, role, text in segments
        ],
    )


def test_validate_requires_literal_quote() -> None:
    transcript = _transcript(segments=[("event:1", "user", "Quiero respuestas breves por favor.")])
    ok = validate_proposal(
        _proposal_payload(
            message_ids=["event:1"],
            quotes=["respuestas breves"],
        ),
        transcript,
        min_confidence=0.7,
    )
    assert ok is not None
    bad_quote = validate_proposal(
        _proposal_payload(
            message_ids=["event:1"],
            quotes=["respuestas detalladas"],  # never said
        ),
        transcript,
        min_confidence=0.7,
    )
    assert bad_quote is None


def test_validate_rejects_unknown_message_id() -> None:
    transcript = _transcript(segments=[("event:1", "user", "Algo dicho explícitamente.")])
    invalid = validate_proposal(
        _proposal_payload(
            message_ids=["event:does-not-exist"],
            quotes=["dicho explícitamente"],
        ),
        transcript,
        min_confidence=0.7,
    )
    assert invalid is None


def test_validate_rejects_low_confidence() -> None:
    transcript = _transcript(segments=[("event:1", "user", "El usuario lo dijo.")])
    low = validate_proposal(
        _proposal_payload(
            confidence=0.4,
            message_ids=["event:1"],
            quotes=["lo dijo"],
        ),
        transcript,
        min_confidence=0.7,
    )
    assert low is None


def test_parse_reflection_response_extracts_fenced_json() -> None:
    raw = """Some prose then:
```json
[
  {"kind": "preference", "content": "x", "confidence": 0.8,
   "sensitivity": "internal", "evidence_message_ids": ["event:1"],
   "evidence_quotes": ["x"]}
]
```
"""
    parsed = parse_reflection_response(raw)
    assert isinstance(parsed, list)
    assert parsed[0]["kind"] == "preference"


def test_parse_reflection_response_returns_empty_on_garbage() -> None:
    assert parse_reflection_response("not valid json at all") == []
    assert parse_reflection_response("") == []
    assert parse_reflection_response(None) == []


async def _seed_thread_with_message(
    *,
    user_text: str,
    operator_decision: str | None = None,
) -> ConversationThread:
    async with session_scope() as session:
        thread = ConversationThread(title="reflection-test")
        session.add(thread)
        await session.flush()
        job = Job(
            job_type="orchestrator",
            status="completed",
            progress=100,
            thread_id=thread.id,
            metadata_json={"user_query": user_text},
        )
        session.add(job)
        await session.flush()
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="agent_response",
                status="completed",
                message="Respuesta del agente al usuario.",
            )
        )
        if operator_decision:
            session.add(
                HumanApproval(
                    action="external_action",
                    requested_action="external_action",
                    args_redacted={"tool": "x"},
                    requested_by="u-1",
                    status=operator_decision,
                    approver_user_id="u-1" if operator_decision == "approved" else None,
                    thread_id=thread.id,
                )
            )
        return thread


@pytest.mark.asyncio
async def test_build_transcript_includes_job_and_events() -> None:
    thread = await _seed_thread_with_message(
        user_text="El usuario tiene una preferencia clara por brevedad.",
        operator_decision="approved",
    )
    async with session_scope() as session:
        attached = await session.get(ConversationThread, thread.id)
        assert attached is not None
        transcript = await build_transcript_for_thread(
            attached,
            lookback_start=datetime.now(UTC) - timedelta(hours=2),
            session=session,
        )
    texts = transcript.all_text()
    assert "preferencia clara por brevedad" in texts
    assert "Respuesta del agente" in texts
    assert "decision=approved" in texts


async def _wipe_reflection_proposals() -> None:
    """Avoid the auto-disable circuit breaker firing from prior test seeds.

    Each test in this file runs against the same shared Postgres, so the
    auto-disable circuit breaker can be tripped by a sibling test that
    seeded rejected proposals. Clean slate per test that runs the
    scanner itself.
    """
    async with session_scope() as session:
        rows = (
            (
                await session.execute(
                    select(DeepAgentMemoryProposalRecord).where(
                        DeepAgentMemoryProposalRecord.proposed_by_agent == "nightly_reflection",
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            await session.delete(row)


@pytest.mark.asyncio
async def test_run_nightly_reflection_emits_proposal_on_validated_payload() -> None:
    await _wipe_reflection_proposals()
    thread = await _seed_thread_with_message(
        user_text="El usuario quiere respuestas breves y directas.",
    )
    quote = "respuestas breves y directas"

    def fake_invoker(messages: list[dict[str, str]]) -> str:
        # Sanity: the user message must mention our seed text — protects
        # us from the runner accidentally passing an empty transcript.
        assert any(quote in m.get("content", "") for m in messages)
        # Look up the job id we just inserted so we can cite it.
        return json.dumps(
            [
                {
                    "kind": "preference",
                    "content": "Prefiere respuestas concisas.",
                    "confidence": 0.85,
                    "sensitivity": "internal",
                    "evidence_message_ids": [f"job:{job_id}"],
                    "evidence_quotes": [quote],
                }
            ]
        )

    async with session_scope() as session:
        job_id = (
            (await session.execute(select(Job).where(Job.thread_id == thread.id).limit(1)))
            .scalars()
            .first()
            .id
        )

    summary = await run_nightly_reflection(llm_invoker=fake_invoker)
    assert summary.get("proposals_created", 0) >= 1
    async with session_scope() as session:
        result = await session.execute(
            select(DeepAgentMemoryProposalRecord).where(
                DeepAgentMemoryProposalRecord.proposed_by_agent == "nightly_reflection",
            )
        )
        rows = list(result.scalars().all())
    assert rows, "expected at least one reflection proposal row"
    payload = (rows[0].metadata_json or {}).get("payload") or {}
    assert payload.get("evidence_quotes") == [quote]


@pytest.mark.asyncio
async def test_run_nightly_reflection_skips_when_quotes_not_in_transcript() -> None:
    await _wipe_reflection_proposals()
    await _seed_thread_with_message(user_text="Texto totalmente distinto.")

    def fake_invoker(messages: list[dict[str, str]]) -> str:
        return json.dumps(
            [
                {
                    "kind": "lesson",
                    "content": "Inventando una preferencia.",
                    "confidence": 0.9,
                    "sensitivity": "internal",
                    "evidence_message_ids": ["event:does-not-exist"],
                    "evidence_quotes": ["frase inventada"],
                }
            ]
        )

    before_count = 0
    async with session_scope() as session:
        result = await session.execute(
            select(DeepAgentMemoryProposalRecord).where(
                DeepAgentMemoryProposalRecord.proposed_by_agent == "nightly_reflection",
            )
        )
        before_count = len(list(result.scalars().all()))

    await run_nightly_reflection(llm_invoker=fake_invoker)

    async with session_scope() as session:
        result = await session.execute(
            select(DeepAgentMemoryProposalRecord).where(
                DeepAgentMemoryProposalRecord.proposed_by_agent == "nightly_reflection",
            )
        )
        after_count = len(list(result.scalars().all()))
    assert after_count == before_count, "validator should suppress evidence-less proposals"


@pytest.mark.asyncio
async def test_auto_disable_kicks_in_when_rejection_rate_exceeds_threshold() -> None:
    # Seed 6 nightly_reflection proposals, 5 rejected, 1 applied → 83%.
    now = datetime.now(UTC)
    async with session_scope() as session:
        for status in ["rejected"] * 5 + ["applied"]:
            session.add(
                DeepAgentMemoryProposalRecord(
                    proposed_by_agent="nightly_reflection",
                    scope="user",
                    reason="seeded for test",
                    proposed_content_redacted="x",
                    sensitivity="internal",
                    source_task_id=str(uuid.uuid4()),
                    status=status,
                    created_at=now,
                )
            )
    disabled, reason = await is_auto_disabled(app_settings=settings, now=now)
    assert disabled is True
    assert reason is not None
    assert "rejection_rate" in reason

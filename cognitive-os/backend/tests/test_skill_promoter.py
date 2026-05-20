"""Fase 80 (Fase B) — skill promotion regression tests.

The promoter is LLM-free: it walks ``deepagent_memory_records`` joined
against ``procedure_invocation_log`` and emits proposals based purely
on counts. No model is mocked.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select

from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import (
    DeepAgentMemoryProposalRecord,
    DeepAgentMemoryRecord,
    ProcedureInvocationLog,
)
from cognitive_os.deepagents.skill_promoter import (
    disable_underperforming_auto_skills,
    evaluate_pending_promotions,
    gather_stats,
    log_procedure_invocation,
    log_procedure_usage_for_job,
    mark_outcome_for_job,
    materialise_yaml_skill,
    render_yaml_skill_text,
)


async def _make_procedure_record(
    *,
    content: str | None = None,
    recipe: dict[str, Any] | None = None,
) -> UUID:
    """Insert an active procedure memory record and return its id."""
    payload = recipe or {
        "title": f"Test procedure {uuid.uuid4().hex[:6]}",
        "summary": "Steps reused enough to deserve a skill.",
        "steps": [
            {"step": 1, "tool": "search_local_docs", "purpose": "find docs"},
            {"step": 2, "tool": "write_workspace_file", "purpose": "draft answer"},
        ],
    }
    async with session_scope() as session:
        record = DeepAgentMemoryRecord(
            scope="agent",
            agent_name="research",
            kind="procedure",
            content_redacted=content or "auto procedure",
            source="agent_proposed",
            confidence=0.7,
            sensitivity="internal",
            status="active",
            metadata_json={"recipe": payload},
        )
        session.add(record)
        await session.flush()
        return record.id


async def _log_invocations(
    memory_id: UUID,
    outcomes: list[str],
    *,
    job_id: UUID | None = None,
) -> None:
    """Direct-insert N invocations with the given outcomes (skips job link)."""
    async with session_scope() as session:
        for outcome in outcomes:
            session.add(
                ProcedureInvocationLog(
                    memory_id=memory_id,
                    job_id=job_id,
                    outcome=outcome,
                )
            )
        await session.flush()


def test_render_yaml_skill_text_includes_frontmatter() -> None:
    text = render_yaml_skill_text(
        name="drive-organize",
        description="Organiza el Drive trimestralmente.",
        recipe={
            "summary": "Organiza el Drive.",
            "steps": [
                {"step": 1, "tool": "drive_search", "purpose": "buscar"},
            ],
        },
        source_memory_id=uuid.uuid4(),
    )
    assert text.startswith("---\n")
    assert "name: drive-organize" in text
    assert "risk_level: approval_required" in text
    assert "drive_search" in text


def test_render_yaml_skill_text_sanitises_dashes_in_description() -> None:
    """A description with `---` must not break the YAML frontmatter parser."""
    text = render_yaml_skill_text(
        name="x",
        description="Paso 1 --- luego --- el paso 2.",
        recipe=None,
        source_memory_id=uuid.uuid4(),
    )
    # The frontmatter block is delimited by the first two `---`. The
    # description line must not introduce a third one.
    _, frontmatter, _ = text.split("---", 2)
    assert "description:" in frontmatter
    assert "---" not in frontmatter


@pytest.mark.asyncio
async def test_gather_stats_counts_outcomes() -> None:
    memory_id = await _make_procedure_record()
    await _log_invocations(memory_id, ["success", "success", "failure", "partial", "pending"])
    async with session_scope() as session:
        stats = await gather_stats(memory_id, session=session)
    assert stats.success_count == 2
    assert stats.failure_count == 1
    assert stats.partial_count == 1
    assert stats.pending_count == 1
    assert stats.total_resolved == 4
    assert 0.24 < stats.failure_rate < 0.26


@pytest.mark.asyncio
async def test_evaluate_below_threshold_does_not_propose() -> None:
    memory_id = await _make_procedure_record()
    await _log_invocations(memory_id, ["success"])
    summary = await evaluate_pending_promotions()
    assert summary.get("proposals_created", 0) == 0


@pytest.mark.asyncio
async def test_evaluate_handles_procedure_with_empty_content() -> None:
    """A procedure whose content is empty must not crash the promoter."""
    memory_id = await _make_procedure_record(content="")
    await _log_invocations(memory_id, ["success", "success", "success"])
    # Should not raise IndexError on empty content_redacted.splitlines().
    summary = await evaluate_pending_promotions()
    assert summary["proposals_created"] >= 1


@pytest.mark.asyncio
async def test_evaluate_emits_proposal_above_threshold() -> None:
    memory_id = await _make_procedure_record()
    await _log_invocations(memory_id, ["success", "success", "success"])
    summary = await evaluate_pending_promotions()
    async with session_scope() as session:
        result = await session.execute(
            select(DeepAgentMemoryProposalRecord).where(
                DeepAgentMemoryProposalRecord.metadata_json["payload"]["skill_promotion"][
                    "source_memory_id"
                ].astext
                == str(memory_id)
            )
        )
        rows = list(result.scalars().all())
    assert summary["proposals_created"] >= 1
    assert rows, "expected at least one promotion proposal row"
    proposal = rows[0]
    payload = (proposal.metadata_json or {}).get("payload") or {}
    promotion = payload.get("skill_promotion")
    assert promotion and promotion.get("route") == "yaml"
    assert promotion.get("yaml_skill_text", "").startswith("---\n")


@pytest.mark.asyncio
async def test_evaluate_skips_when_failure_rate_too_high() -> None:
    memory_id = await _make_procedure_record()
    # 3 successes + 5 failures = 62.5% failure_rate → above default 30%.
    await _log_invocations(
        memory_id,
        ["success", "success", "success", "failure", "failure", "failure", "failure", "failure"],
    )
    await evaluate_pending_promotions()
    async with session_scope() as session:
        result = await session.execute(
            select(DeepAgentMemoryProposalRecord).where(
                DeepAgentMemoryProposalRecord.metadata_json["payload"]["skill_promotion"][
                    "source_memory_id"
                ].astext
                == str(memory_id)
            )
        )
        rows = list(result.scalars().all())
    assert not rows, "promoter should refuse procedures with high failure rate"


@pytest.mark.asyncio
async def test_materialise_yaml_skill_writes_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "deepagents_user_skills_dir", tmp_path)
    memory_id = await _make_procedure_record()
    await _log_invocations(memory_id, ["success", "success", "success"])
    await evaluate_pending_promotions()
    async with session_scope() as session:
        result = await session.execute(
            select(DeepAgentMemoryProposalRecord).where(
                DeepAgentMemoryProposalRecord.metadata_json["payload"]["skill_promotion"][
                    "source_memory_id"
                ].astext
                == str(memory_id)
            )
        )
        proposal = result.scalars().first()
    assert proposal is not None
    res = await materialise_yaml_skill(proposal.id, approver_user_id="operator")
    assert res["already_existed"] is False
    skill_file = Path(res["skill_file"])
    assert skill_file.exists()
    text = skill_file.read_text(encoding="utf-8")
    assert "name:" in text
    # Re-running should detect idempotency.
    res2 = await materialise_yaml_skill(proposal.id, approver_user_id="operator")
    assert res2["already_existed"] is True


@pytest.mark.asyncio
async def test_log_and_mark_outcome_for_job_collapses_pending() -> None:
    memory_id = await _make_procedure_record()
    job_id = uuid.uuid4()
    await log_procedure_invocation(memory_id=memory_id, job_id=job_id)
    await log_procedure_invocation(memory_id=memory_id, job_id=job_id)
    touched = await mark_outcome_for_job(job_id=job_id, outcome="success")
    assert touched == 2
    async with session_scope() as session:
        stats = await gather_stats(memory_id, session=session)
    assert stats.success_count == 2
    assert stats.pending_count == 0


@pytest.mark.asyncio
async def test_log_procedure_usage_for_job_uses_active_procedures() -> None:
    memory_id = await _make_procedure_record()
    job_id = uuid.uuid4()
    ids = await log_procedure_usage_for_job(
        job_id=job_id,
        thread_id="thr-1",
        user_id="u-1",
        agent_name="research",
        limit=4,
    )
    assert ids, "expected at least one invocation row for an active procedure"
    async with session_scope() as session:
        result = await session.execute(
            select(ProcedureInvocationLog).where(
                ProcedureInvocationLog.job_id == job_id,
            )
        )
        rows = list(result.scalars().all())
    assert any(r.memory_id == memory_id for r in rows)
    assert all(r.outcome == "pending" for r in rows)


@pytest.mark.asyncio
async def test_rollback_disables_failing_auto_promoted_skill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A promoted skill with > rollback_max_failure_rate is archived."""
    monkeypatch.setattr(settings, "deepagents_user_skills_dir", tmp_path)
    memory_id = await _make_procedure_record()
    await _log_invocations(memory_id, ["success"] * 5)
    await evaluate_pending_promotions()
    async with session_scope() as session:
        proposal = (
            (
                await session.execute(
                    select(DeepAgentMemoryProposalRecord).where(
                        DeepAgentMemoryProposalRecord.metadata_json["payload"]["skill_promotion"][
                            "source_memory_id"
                        ].astext
                        == str(memory_id)
                    )
                )
            )
            .scalars()
            .first()
        )
    assert proposal is not None
    res = await materialise_yaml_skill(proposal.id, approver_user_id="operator")
    promoted_memory_id = UUID(res["memory_id"])
    # Force the promoted memory row to look "recent" then attribute many
    # failures to it via the invocation log.
    await _log_invocations(promoted_memory_id, ["failure"] * 5 + ["success"])
    summary = await disable_underperforming_auto_skills()
    assert summary["disabled"] >= 1
    async with session_scope() as session:
        refreshed = await session.get(DeepAgentMemoryRecord, promoted_memory_id)
    assert refreshed is not None
    assert refreshed.status == "archived"
    disabled_path = Path(res["skill_file"]).with_suffix(".md.disabled")
    assert disabled_path.exists() or not Path(res["skill_file"]).exists()

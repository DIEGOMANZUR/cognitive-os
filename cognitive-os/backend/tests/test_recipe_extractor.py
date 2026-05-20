"""Unit tests for the Fase 78 recipe extractor.

These tests exercise the extractor against a real (Postgres) session via
``session_scope``. The conftest already disables real LLM factories, so
we always inject a stub ``llm_invoker`` callable. The extractor never
talks to the network in tests.
"""

from __future__ import annotations

import asyncio
import json
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
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService
from cognitive_os.deepagents.recipe_extractor import (
    RecipeExtractionResult,
    extract_pending_recipes,
    extract_recipe_for_job,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_RECIPE = {
    "title": "Resumir contratos del año por cliente",
    "summary": "Reúne contratos, los lee, los cruza con clientes y emite un resumen.",
    "preconditions": ["Documentos del año indexados"],
    "inputs_typical": {"year": "int"},
    "steps": [
        {"step": 1, "tool": "search_local_docs", "purpose": "Buscar contratos"},
        {"step": 2, "tool": "read_document_pages", "purpose": "Leer páginas"},
        {"step": 3, "tool": "graph_query_readonly", "purpose": "Cruzar con cliente"},
        {"step": 4, "tool": "write_workspace_file", "purpose": "Resumen final"},
    ],
    "outputs_typical": "Un archivo final.md.",
    "estimated_runtime_seconds": 120,
    "success_indicators": ["final.md existe"],
    "tags": ["contratos"],
}


def _recipe_invoker() -> Any:
    def _invoke(_messages: list[dict[str, str]]) -> str:
        return json.dumps(_VALID_RECIPE, ensure_ascii=False)

    return _invoke


def _skip_invoker() -> Any:
    def _invoke(_messages: list[dict[str, str]]) -> str:
        return '{"skip": true, "reason": "trayectoria trivial"}'

    return _invoke


def _failing_invoker(exc: type[Exception] = RuntimeError) -> Any:
    def _invoke(_messages: list[dict[str, str]]) -> str:
        raise exc("fake LLM outage")

    return _invoke


async def _make_job(
    *,
    status: str = "completed",
    job_type: str = "deepagent_research",
    tool_calls: int = 6,
    duration_seconds: int = 90,
    metadata: dict[str, Any] | None = None,
) -> UUID:
    """Insert a Job + N JobEvents shaped like a successful tool-using run."""
    async with session_scope() as session:
        now = datetime.now(UTC)
        started = now - timedelta(seconds=duration_seconds)
        job = Job(
            job_type=job_type,
            status=status,
            progress=100,
            metadata_json={"agent_name": "research", **(metadata or {})},
        )
        session.add(job)
        await session.flush()
        # Force the timestamps so the duration check sees enough seconds —
        # `created_at`/`updated_at` are server-side defaults so we tweak
        # them post-flush.
        job.created_at = started
        job.updated_at = now
        for i in range(tool_calls):
            session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="tool_invoked",
                    status="completed",
                    message=f"call #{i}",
                    metadata_json={"tool": f"tool_{i % 3}"},
                )
            )
        await session.flush()
        return job.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_creates_procedure_proposal() -> None:
    job_id = await _make_job()
    service = DeepAgentMemoryService()

    result = await extract_recipe_for_job(
        job_id, llm_invoker=_recipe_invoker(), memory_service=service
    )

    assert isinstance(result, RecipeExtractionResult)
    assert result.status == "proposal"
    assert result.proposal_id is not None

    async with session_scope() as session:
        proposals = (
            (
                await session.execute(
                    select(DeepAgentMemoryProposalRecord).where(
                        DeepAgentMemoryProposalRecord.id == UUID(result.proposal_id)
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(proposals) == 1
        proposal = proposals[0]
        assert proposal.metadata_json["kind"] == "procedure"
        assert proposal.metadata_json["payload"]["recipe"]["title"].startswith("Resumir")

        job = await session.get(Job, job_id)
        assert job is not None
        assert job.extracted_recipe_at is not None


@pytest.mark.asyncio
async def test_skips_jobs_below_tool_threshold() -> None:
    job_id = await _make_job(tool_calls=2)

    result = await extract_recipe_for_job(job_id, llm_invoker=_recipe_invoker())

    assert result.status == "ineligible"
    assert result.reason == "not_enough_tool_calls"

    async with session_scope() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.extracted_recipe_at is None


@pytest.mark.asyncio
async def test_skips_failed_jobs() -> None:
    job_id = await _make_job(status="failed")

    result = await extract_recipe_for_job(job_id, llm_invoker=_recipe_invoker())

    assert result.status == "ineligible"
    assert result.reason == "not_succeeded"


@pytest.mark.asyncio
async def test_skips_ineligible_job_types() -> None:
    job_id = await _make_job(job_type="health_check")

    result = await extract_recipe_for_job(job_id, llm_invoker=_recipe_invoker())

    assert result.status == "ineligible"
    assert result.reason == "job_type_not_eligible"


@pytest.mark.asyncio
async def test_skips_short_duration_jobs() -> None:
    job_id = await _make_job(duration_seconds=5)

    result = await extract_recipe_for_job(job_id, llm_invoker=_recipe_invoker())

    assert result.status == "ineligible"
    assert result.reason == "duration_below_threshold"


@pytest.mark.asyncio
async def test_already_processed_job_is_skipped() -> None:
    job_id = await _make_job()
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        job.extracted_recipe_at = datetime.now(UTC)

    result = await extract_recipe_for_job(job_id, llm_invoker=_recipe_invoker())

    assert result.status == "ineligible"
    assert result.reason == "already_processed"


@pytest.mark.asyncio
async def test_llm_failure_does_not_mark_processed() -> None:
    job_id = await _make_job()

    result = await extract_recipe_for_job(job_id, llm_invoker=_failing_invoker())

    assert result.status == "llm_error"
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        # On transient failure we MUST leave the marker NULL so the next
        # beat retries — otherwise a single Gemini outage silently
        # discards every job it sees.
        assert job.extracted_recipe_at is None
        proposals = (await session.execute(select(DeepAgentMemoryProposalRecord))).scalars().all()
        assert not any(p.source_task_id == str(job_id) for p in proposals)


@pytest.mark.asyncio
async def test_llm_skip_signal_marks_processed_but_no_proposal() -> None:
    job_id = await _make_job()

    result = await extract_recipe_for_job(job_id, llm_invoker=_skip_invoker())

    assert result.status == "skipped_by_llm"
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.extracted_recipe_at is not None
        proposals = (await session.execute(select(DeepAgentMemoryProposalRecord))).scalars().all()
        assert not any(p.source_task_id == str(job_id) for p in proposals)


@pytest.mark.asyncio
async def test_garbage_llm_response_is_treated_as_error() -> None:
    job_id = await _make_job()

    def _garbage(_messages: list[dict[str, str]]) -> str:
        return "this is not json at all"

    result = await extract_recipe_for_job(job_id, llm_invoker=_garbage)

    assert result.status == "llm_error"
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        # Same rule as test_llm_failure: parse error == transient,
        # so the marker stays NULL.
        assert job.extracted_recipe_at is None


@pytest.mark.asyncio
async def test_concurrent_extractor_idempotency() -> None:
    """Two back-to-back extractions on the same job → exactly one proposal."""
    job_id = await _make_job()

    first = await extract_recipe_for_job(job_id, llm_invoker=_recipe_invoker())
    second = await extract_recipe_for_job(job_id, llm_invoker=_recipe_invoker())

    assert first.status == "proposal"
    assert second.status == "ineligible"  # already_processed

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
        assert len(proposals) == 1


@pytest.mark.asyncio
async def test_truly_concurrent_extractions_produce_one_proposal() -> None:
    """Fase 79 P1-A regression: two extractors racing on the same job must
    not both emit proposals. The ``with_for_update(skip_locked=True)`` lock
    inside the extractor means whichever transaction grabs the row first
    wins; the other sees ``locked_by_other_worker`` and bails.
    """
    job_id = await _make_job()

    results = await asyncio.gather(
        extract_recipe_for_job(job_id, llm_invoker=_recipe_invoker()),
        extract_recipe_for_job(job_id, llm_invoker=_recipe_invoker()),
    )

    statuses = sorted(r.status for r in results)
    # Exactly one wins; the other returns ineligible (locked or already
    # processed depending on micro-timing).
    assert statuses == ["ineligible", "proposal"]
    losing = next(r for r in results if r.status == "ineligible")
    assert losing.reason in {"locked_by_other_worker", "already_processed"}

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
        assert len(proposals) == 1


@pytest.mark.asyncio
async def test_proposal_persistence_failure_does_not_mark_processed() -> None:
    """Fase 79 P1-B regression: if `propose_memory_update` raises (e.g. the
    secret-validation regex rejects the recipe), the outer transaction must
    roll back so `extracted_recipe_at` stays NULL. Otherwise a partial
    failure would silently swallow the job.
    """

    class _RejectingService(DeepAgentMemoryService):
        async def propose_memory_update(  # type: ignore[override]
            self, proposal, *, session=None
        ):
            raise RuntimeError("simulated post-LLM persistence failure")

    job_id = await _make_job()

    # The extractor wraps the call in the transaction, so a raise propagates.
    with pytest.raises(RuntimeError, match="simulated"):
        await extract_recipe_for_job(
            job_id,
            llm_invoker=_recipe_invoker(),
            memory_service=_RejectingService(),
        )

    async with session_scope() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.extracted_recipe_at is None
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
        assert proposals == []


@pytest.mark.asyncio
async def test_extract_pending_recipes_sweeps_batch() -> None:
    jid_a = await _make_job()
    jid_b = await _make_job()
    # One ineligible (failed) job to confirm the sweep filters correctly.
    await _make_job(status="failed")

    summary = await extract_pending_recipes(llm_invoker=_recipe_invoker())

    assert summary["proposed"] >= 2
    proposal_ids = summary["proposal_ids"]
    assert len(proposal_ids) >= 2

    async with session_scope() as session:
        a = await session.get(Job, jid_a)
        b = await session.get(Job, jid_b)
        assert a is not None and a.extracted_recipe_at is not None
        assert b is not None and b.extracted_recipe_at is not None


@pytest.mark.asyncio
async def test_proposal_round_trip_to_active_procedure_record() -> None:
    """Approving a procedure proposal should materialise kind=procedure."""
    job_id = await _make_job()
    service = DeepAgentMemoryService()

    result = await extract_recipe_for_job(
        job_id, llm_invoker=_recipe_invoker(), memory_service=service
    )
    assert result.proposal_id is not None

    item = await service.approve_memory_proposal(result.proposal_id, "test-admin")

    assert item.kind == "procedure"
    assert item.confidence == pytest.approx(0.65)
    assert "fase78_recipe_extractor" in json.dumps(item.metadata or {})

    async with session_scope() as session:
        records = (
            (
                await session.execute(
                    select(DeepAgentMemoryRecord).where(
                        DeepAgentMemoryRecord.id == UUID(item.memory_id)
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(records) == 1
        assert records[0].kind == "procedure"

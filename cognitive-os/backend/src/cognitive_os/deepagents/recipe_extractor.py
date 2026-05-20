"""Recipe extractor — Fase 78 (Fase A of the agent learning plan).

The extractor scans successful long-running jobs and, when the trajectory
looks reusable, asks the secondary chat model to distil it into a
``DeepAgentMemoryProposal(kind="procedure")``. The proposal goes through
the same approval flow as every other learning artifact (operator
approval in the Memoria UI), so this module never mutates active memory
on its own.

Trigger surface:
* :func:`extract_recipe_for_job` — process a single job (used by tests
  and by the admin "Extract now" REST endpoint).
* :func:`extract_pending_recipes` — sweep the next batch of pending
  jobs (used by the Celery beat task).

Idempotency: the job carries an ``extracted_recipe_at`` timestamp. The
extractor sets it whenever the LLM emits a usable answer OR an explicit
skip signal, but **not** when the LLM call raises — that path falls back
to a retry on the next beat cycle so a transient outage does not silently
discard the job.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import Job, JobEvent
from cognitive_os.deepagents.memory_schemas import DeepAgentMemoryProposal
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService
from cognitive_os.deepagents.recipe_prompts import (
    RecipeParseError,
    build_recipe_messages,
    parse_recipe_response,
    serialize_trajectory,
)

logger = logging.getLogger(__name__)

# Job statuses that count as a successful completion for recipe extraction.
# `completed_with_warnings` is included because the mail sync emits it when
# one provider fails but the overall job still produced a useful output.
_SUCCESS_STATUSES: frozenset[str] = frozenset({"completed", "completed_with_warnings"})

# Event types that the recipe extractor treats as "the agent invoked a
# tool". Counting these (instead of every JobEvent row) keeps the
# tool_call_count threshold meaningful: a job that emits 30 progress
# notifications but invokes one tool is NOT a procedure worth distilling.
_TOOL_INVOCATION_EVENTS: frozenset[str] = frozenset(
    {
        "tool_invoked",
        "tool_succeeded",
        "tool_failed",
        "tool_completed",
        "agent_tool_call",
    }
)


# Type alias for an injectable LLM invoker. Tests stub this to avoid the
# autouse hermetic-LLM guard in conftest. The default implementation
# wraps the secondary chat model. Return value is the raw model output;
# the extractor parses it via `parse_recipe_response`.
RecipeLLM = Callable[[list[dict[str, str]]], "str | None"]


@dataclass(slots=True)
class RecipeExtractionResult:
    job_id: UUID
    status: str  # "proposal" | "skipped_by_llm" | "ineligible" | "llm_error"
    proposal_id: str | None = None
    reason: str | None = None


def _default_llm_invoker(messages: list[dict[str, str]]) -> str | None:
    """Real LLM invoker — used in production. Tests inject a stub."""
    from cognitive_os.agents.llm_factory import create_secondary_chat_model  # noqa: PLC0415

    llm = create_secondary_chat_model()
    # ChatOpenAI accepts (role, content) tuples or dicts; tuples work
    # across langchain-openai versions.
    formatted: list[tuple[str, str]] = [(str(msg["role"]), str(msg["content"])) for msg in messages]
    response = llm.invoke(formatted)
    content = getattr(response, "content", response)
    if isinstance(content, list):
        # Some langchain versions return content as a list of dicts when
        # the model emits multiple chunks. Concatenate the text parts.
        parts: list[str] = []
        for chunk in content:
            if isinstance(chunk, dict):
                parts.append(str(chunk.get("text") or chunk.get("content") or ""))
            else:
                parts.append(str(chunk))
        return "".join(parts)
    return str(content) if content is not None else None


async def extract_recipe_for_job(
    job_id: UUID,
    *,
    llm_invoker: RecipeLLM | None = None,
    memory_service: DeepAgentMemoryService | None = None,
    app_settings: Settings | None = None,
) -> RecipeExtractionResult:
    """Extract a recipe from a single job. Returns the outcome with details.

    The extractor never raises on policy mismatches; it returns an
    `ineligible` result so the caller (beat sweep / REST endpoint) can
    log a one-liner without try/except spaghetti.
    """
    cfg = app_settings or settings
    service = memory_service or DeepAgentMemoryService()

    async with session_scope() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return RecipeExtractionResult(job_id, "ineligible", reason="job_not_found")
        if job.extracted_recipe_at is not None:
            return RecipeExtractionResult(job_id, "ineligible", reason="already_processed")
        if job.status not in _SUCCESS_STATUSES:
            return RecipeExtractionResult(job_id, "ineligible", reason="not_succeeded")
        eligible = cfg.recipe_extractor_eligible_job_types
        if eligible and job.job_type not in eligible:
            return RecipeExtractionResult(job_id, "ineligible", reason="job_type_not_eligible")

        events_query = (
            select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.created_at.asc())
        )
        event_rows: Sequence[JobEvent] = (await session.execute(events_query)).scalars().all()

        tool_events = [ev for ev in event_rows if ev.event_type in _TOOL_INVOCATION_EVENTS]
        # Fallback: some agents emit `tool_*` events with custom names
        # (e.g. `agent_tool_<tool>`). If the strict count is below
        # threshold, fall back to "any event whose metadata carries a
        # tool field" so we don't miss procedures from older agents.
        if len(tool_events) < cfg.recipe_extractor_min_tool_calls:
            tool_events = [
                ev
                for ev in event_rows
                if (ev.metadata_json or {}).get("tool") or (ev.metadata_json or {}).get("tool_name")
            ]
        if len(tool_events) < cfg.recipe_extractor_min_tool_calls:
            return RecipeExtractionResult(job_id, "ineligible", reason="not_enough_tool_calls")

        duration = (job.updated_at - job.created_at).total_seconds()
        if duration < cfg.recipe_extractor_min_duration_seconds:
            return RecipeExtractionResult(job_id, "ineligible", reason="duration_below_threshold")

        agent_name = _agent_name_from_job(job)
        trajectory = serialize_trajectory(
            job_type=job.job_type,
            agent_name=agent_name,
            duration_seconds=duration,
            events=[_event_to_dict(ev) for ev in event_rows],
        )

        messages = build_recipe_messages(trajectory)
        invoker = llm_invoker or _default_llm_invoker
        try:
            raw = await asyncio.to_thread(invoker, messages)
        except Exception as exc:  # noqa: BLE001
            # Transient LLM failures must NOT mark the job processed; we
            # want the next beat cycle to retry. Log + bail.
            logger.warning(
                "recipe_extract_llm_failed job_id=%s error=%s",
                job_id,
                type(exc).__name__,
            )
            return RecipeExtractionResult(
                job_id, "llm_error", reason=f"{type(exc).__name__}: {exc}"
            )

        try:
            parsed = parse_recipe_response(raw)
        except RecipeParseError as exc:
            logger.warning("recipe_extract_parse_failed job_id=%s error=%s", job_id, exc)
            return RecipeExtractionResult(job_id, "llm_error", reason=str(exc))

        if parsed.get("skip"):
            # The LLM saw the trajectory and decided it isn't reusable.
            # Mark processed so we don't re-ask, but don't emit a proposal.
            job.extracted_recipe_at = datetime.now(UTC)
            return RecipeExtractionResult(
                job_id, "skipped_by_llm", reason=str(parsed.get("reason"))
            )

        proposal = _build_proposal(
            job=job,
            agent_name=agent_name,
            recipe=parsed,
            duration_seconds=duration,
            tool_call_count=len(tool_events),
        )
        await service.propose_memory_update(proposal)
        job.extracted_recipe_at = datetime.now(UTC)
        return RecipeExtractionResult(job_id, "proposal", proposal_id=proposal.proposal_id)


async def extract_pending_recipes(
    *,
    llm_invoker: RecipeLLM | None = None,
    memory_service: DeepAgentMemoryService | None = None,
    app_settings: Settings | None = None,
) -> dict[str, Any]:
    """Sweep jobs that look extractable, up to the per-cycle cap.

    Called by the Celery beat task; safe to call manually for tests or
    operator-triggered runs (admin REST endpoint).
    """
    cfg = app_settings or settings
    eligible = cfg.recipe_extractor_eligible_job_types
    limit = max(1, cfg.recipe_extractor_max_per_cycle)

    async with session_scope() as session:
        query = select(Job.id).where(
            Job.status.in_(_SUCCESS_STATUSES),
            Job.extracted_recipe_at.is_(None),
        )
        if eligible:
            query = query.where(Job.job_type.in_(eligible))
        query = query.order_by(Job.updated_at.desc()).limit(limit)
        job_ids = [row[0] for row in (await session.execute(query)).all()]

    results: list[RecipeExtractionResult] = []
    for job_id in job_ids:
        try:
            result = await extract_recipe_for_job(
                job_id,
                llm_invoker=llm_invoker,
                memory_service=memory_service,
                app_settings=cfg,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("recipe_extract_unhandled_error job_id=%s", job_id)
            result = RecipeExtractionResult(
                job_id, "llm_error", reason=f"unhandled:{type(exc).__name__}:{exc}"
            )
        results.append(result)

    proposed = sum(1 for r in results if r.status == "proposal")
    skipped = sum(1 for r in results if r.status == "skipped_by_llm")
    ineligible = sum(1 for r in results if r.status == "ineligible")
    errored = sum(1 for r in results if r.status == "llm_error")
    return {
        "scanned": len(results),
        "proposed": proposed,
        "skipped_by_llm": skipped,
        "ineligible": ineligible,
        "errored": errored,
        "proposal_ids": [r.proposal_id for r in results if r.proposal_id],
    }


def _agent_name_from_job(job: Job) -> str:
    """Derive an agent name for the proposal from the job row.

    The DB model does not have a dedicated `agent_name` column; agents
    drop it into `metadata_json["agent_name"]` when they create the job.
    Fall back to the `job_type` so the materialised proposal still has
    something meaningful.
    """
    md = job.metadata_json or {}
    candidate = md.get("agent_name") or md.get("agent")
    if isinstance(candidate, str) and candidate:
        return candidate
    # `deepagent_research` -> `research`, `document_analysis` -> `document_analysis`.
    job_type: str = job.job_type or "deepagent"
    return job_type.removeprefix("deepagent_") or "deepagent"


def _event_to_dict(event: JobEvent) -> dict[str, Any]:
    return {
        "event_type": event.event_type,
        "message": event.message,
        "created_at": event.created_at,
        "metadata": event.metadata_json or {},
    }


def _build_proposal(
    *,
    job: Job,
    agent_name: str,
    recipe: dict[str, Any],
    duration_seconds: float,
    tool_call_count: int,
) -> DeepAgentMemoryProposal:
    title = str(recipe.get("title") or "Receta extraída")
    summary = str(recipe.get("summary") or "")
    proposed_content = _render_recipe_summary(title, summary, recipe)
    md = job.metadata_json or {}
    user_id = md.get("user_id") or md.get("requested_by")
    thread_id = str(job.thread_id) if job.thread_id is not None else None
    return DeepAgentMemoryProposal(
        proposal_id=str(uuid4()),
        proposed_by_agent=agent_name,
        scope="agent",
        reason=(
            f"Receta consolidada de un job {job.job_type} exitoso "
            f"({tool_call_count} tool calls, {int(duration_seconds)}s)."
        ),
        proposed_content=proposed_content,
        sensitivity="internal",
        source_task_id=str(job.id),
        requires_approval=True,
        user_id=str(user_id) if user_id else None,
        thread_id=thread_id,
        kind="procedure",
        confidence=0.65,
        metadata={
            "recipe": recipe,
            "job_id": str(job.id),
            "job_type": job.job_type,
            "tool_call_count": tool_call_count,
            "duration_seconds": int(duration_seconds),
            "extracted_by": "fase78_recipe_extractor",
        },
    )


def _render_recipe_summary(title: str, summary: str, recipe: dict[str, Any]) -> str:
    """Short, human-readable preview stored as the proposal's content.

    Why duplicate the recipe (which is also in metadata.payload)? The
    proposals list view renders ``proposed_content`` directly; we want
    the operator to see the title + first steps without expanding the
    JSON payload. Keep it under 2 KB so the redact step stays cheap.
    """
    steps = recipe.get("steps") or []
    step_lines: list[str] = []
    for step in steps[:6]:
        if not isinstance(step, dict):
            continue
        idx = step.get("step")
        tool = step.get("tool") or "?"
        purpose = step.get("purpose") or ""
        step_lines.append(f"  {idx}. {tool} — {purpose}")
    return (f"Receta: {title}\n{summary}\nPasos:\n" + "\n".join(step_lines))[:2000]

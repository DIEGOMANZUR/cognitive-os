"""Skill promotion — Fase 80 (Fase B of the agent learning plan).

Promotes ``kind=procedure`` memory records into first-class YAML skills
once the operator has seen them succeed enough times in real jobs. The
flow is deliberately conservative — auto-promotion of executable
behaviour is forbidden by §7 of ``AGENT_LEARNING_PLAN.md``, so every
promotion still needs an explicit approval. What the promoter automates
is the *proposal*: scanning usage, deriving a YAML template, and parking
it in the operator's review queue.

Lifecycle:

1. Some agent build references a ``kind=procedure`` record (via the
   structured memory inflated into the system prompt). The skill
   inflater calls :func:`log_procedure_invocation` to record a *pending*
   row in ``procedure_invocation_log``. Each row carries the job id so
   we can credit the eventual outcome.
2. When the job finishes the worker calls
   :func:`mark_outcome_for_job` so every log row from that job picks up
   the right outcome (``success`` / ``failure`` / ``partial``).
3. The Celery beat task :func:`evaluate_pending_promotions` walks active
   procedure records, joins against the log, and emits a
   ``DeepAgentMemoryProposal`` with ``metadata.skill_promotion`` when a
   procedure crosses ``MIN_SUCCESSES`` and stays under
   ``MAX_FAILURE_RATE``. Auto-promotion is **never** performed; the
   operator approves via the existing Memoria UI.
4. On approval the API hands the proposal to
   :func:`materialise_yaml_skill`, which writes the YAML file to the
   user skills directory (B.1 path). The B.2 (code-based) route is a
   no-op in this PR — the proposal still records the intent so a future
   Code Director run can pick it up.
5. The post-promotion rollback checker
   (:func:`disable_underperforming_auto_skills`) sweeps recently promoted
   skills; anything with > ``rollback_max_failure_rate`` failures in the
   30-day window is archived and the YAML file disabled. Reversible by
   editing the SKILL.md frontmatter.

This module does not touch the secondary LLM. The proposal content is
rendered from the procedure's stored payload (the recipe extractor
already produced a structured JSON), so no inference happens here.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import (
    DeepAgentMemoryProposalRecord,
    DeepAgentMemoryRecord,
    ProcedureInvocationLog,
)
from cognitive_os.deepagents.memory_schemas import (
    DeepAgentMemoryProposal,
    DeepAgentMemoryScope,
)
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
class PromotionStats:
    memory_id: UUID
    success_count: int
    failure_count: int
    partial_count: int
    pending_count: int

    @property
    def total_resolved(self) -> int:
        return self.success_count + self.failure_count + self.partial_count

    @property
    def failure_rate(self) -> float:
        denom = self.total_resolved
        return self.failure_count / denom if denom > 0 else 0.0


@dataclass(slots=True)
class PromotionResult:
    memory_id: UUID
    status: str  # "proposal_created" | "skipped" | "already_proposed" | "below_threshold"
    proposal_id: str | None = None
    reason: str | None = None


def _slugify(text: str, *, fallback: str = "auto-skill") -> str:
    base = _SLUG_RE.sub("-", (text or "").strip().lower()).strip("-")
    if not base:
        base = fallback
    return base[:60]


async def log_procedure_invocation(
    *,
    memory_id: UUID | str,
    job_id: UUID | str | None,
    thread_id: str | None = None,
    user_id: str | None = None,
    agent_name: str | None = None,
    session: AsyncSession | None = None,
    metadata: dict[str, Any] | None = None,
) -> UUID:
    """Record that a procedure memory was referenced by an agent build.

    Returns the log row id so the caller can attach it to the running
    job. If a ``session`` is supplied the write joins that transaction;
    otherwise we open our own. We do not commit (the caller's session
    boundary handles that) when a session is provided.
    """
    mid = memory_id if isinstance(memory_id, UUID) else UUID(str(memory_id))
    jid: UUID | None
    if isinstance(job_id, UUID):
        jid = job_id
    elif job_id is None:
        jid = None
    else:
        jid = UUID(str(job_id))
    row = ProcedureInvocationLog(
        memory_id=mid,
        job_id=jid,
        thread_id=thread_id,
        user_id=user_id,
        agent_name=agent_name,
        outcome="pending",
        metadata_json=metadata or {},
    )
    if session is not None:
        session.add(row)
        await session.flush()
        return row.id
    async with session_scope() as new_session:
        new_session.add(row)
        await new_session.flush()
        return row.id


async def log_procedure_usage_for_job(
    *,
    job_id: UUID | str,
    thread_id: str | None = None,
    user_id: str | None = None,
    agent_name: str | None = None,
    limit: int = 8,
) -> list[UUID]:
    """Log one ``pending`` invocation per active procedure that could have
    been injected into this agent's startup memory.

    Called from the worker before the agent runs. A procedure shows up
    in an agent's system prompt only when it is either *not* agent-scoped
    (global / user / case / thread procedures reach everyone) OR its
    ``agent_name`` matches the running agent — that's exactly what
    ``DeepAgentMemoryService.get_startup_memory`` does. We mirror that
    filter here so the usage signal is accurate: a procedure is credited
    only for jobs whose prompt actually contained it.

    The eventual ``mark_outcome_for_job`` call collapses all of these
    pending rows to the right outcome (success / failure).
    """
    jid = job_id if isinstance(job_id, UUID) else UUID(str(job_id))
    async with session_scope() as session:
        where_clause = and_(
            DeepAgentMemoryRecord.kind == "procedure",
            DeepAgentMemoryRecord.status == "active",
        )
        if agent_name:
            # Agent-scoped procedures only count for their own agent;
            # broader scopes reach every agent's prompt.
            where_clause = and_(
                where_clause,
                or_(
                    DeepAgentMemoryRecord.scope != "agent",
                    DeepAgentMemoryRecord.agent_name == agent_name,
                ),
            )
        candidates = (
            (
                await session.execute(
                    select(DeepAgentMemoryRecord)
                    .where(where_clause)
                    .order_by(DeepAgentMemoryRecord.updated_at.desc())
                    .limit(max(1, limit))
                )
            )
            .scalars()
            .all()
        )
        ids: list[UUID] = []
        for record in candidates:
            ids.append(
                await log_procedure_invocation(
                    memory_id=record.id,
                    job_id=jid,
                    thread_id=thread_id,
                    user_id=user_id,
                    agent_name=agent_name,
                    session=session,
                    metadata={"injection_kind": "startup_memory"},
                )
            )
        return ids


async def mark_outcome_for_job(
    *,
    job_id: UUID | str,
    outcome: str,
    session: AsyncSession | None = None,
) -> int:
    """Set ``outcome`` on every pending log row for a given job.

    Returns the number of rows touched. Idempotent: re-running with the
    same outcome is a no-op once rows are already resolved (they're
    matched on ``outcome == 'pending'``).
    """
    if outcome not in {"pending", "success", "failure", "partial"}:
        msg = f"invalid outcome: {outcome!r}"
        raise ValueError(msg)
    jid = job_id if isinstance(job_id, UUID) else UUID(str(job_id))

    async def _do(s: AsyncSession) -> int:
        result = await s.execute(
            select(ProcedureInvocationLog).where(
                and_(
                    ProcedureInvocationLog.job_id == jid,
                    ProcedureInvocationLog.outcome == "pending",
                )
            )
        )
        rows = list(result.scalars().all())
        for row in rows:
            row.outcome = outcome
        return len(rows)

    if session is not None:
        return await _do(session)
    async with session_scope() as new_session:
        return await _do(new_session)


async def gather_stats(
    memory_id: UUID,
    *,
    session: AsyncSession,
) -> PromotionStats:
    """Aggregate counts per outcome for a single procedure record."""
    grouped = await session.execute(
        select(
            ProcedureInvocationLog.outcome,
            func.count(ProcedureInvocationLog.id),
        )
        .where(ProcedureInvocationLog.memory_id == memory_id)
        .group_by(ProcedureInvocationLog.outcome)
    )
    counts = {row[0]: int(row[1]) for row in grouped.all()}
    return PromotionStats(
        memory_id=memory_id,
        success_count=counts.get("success", 0),
        failure_count=counts.get("failure", 0),
        partial_count=counts.get("partial", 0),
        pending_count=counts.get("pending", 0),
    )


def render_yaml_skill_text(
    *,
    name: str,
    description: str,
    recipe: dict[str, Any] | None,
    source_memory_id: UUID,
) -> str:
    """Render the YAML payload for a B.1 (prompt-based) skill.

    Single source of truth for the on-disk format. We keep the shape
    deliberately small so the existing skills registry parser
    (``_parse_frontmatter`` in ``skills_registry.py``) can read it
    verbatim — a frontmatter block plus a markdown body.
    """
    # Sanitise the description so it can never break the YAML frontmatter:
    # newlines collapse to spaces and any run of dashes (which would be
    # read as a `---` frontmatter delimiter by `_parse_frontmatter`) is
    # squashed to a single em dash.
    safe_desc = re.sub(r"-{2,}", "—", description.replace("\n", " ")).strip()[:300]
    safe_desc = safe_desc or "Skill auto-promovido."
    steps_lines: list[str] = []
    if recipe and isinstance(recipe.get("steps"), list):
        for raw in recipe["steps"][:12]:
            if not isinstance(raw, dict):
                continue
            step = raw.get("step") or len(steps_lines) + 1
            tool = raw.get("tool") or "?"
            purpose = (raw.get("purpose") or "").strip()
            input_pattern = (raw.get("input_pattern") or "").strip()
            line = f"  {step}. `{tool}` — {purpose}"
            if input_pattern:
                line += f" (input: {input_pattern})"
            steps_lines.append(line)
    body_steps = "\n".join(steps_lines) or "  1. (sin pasos registrados — ver memoria origen)"
    preconds: list[str] = []
    if recipe and isinstance(recipe.get("preconditions"), list):
        preconds = [str(p) for p in recipe["preconditions"] if str(p).strip()][:10]
    preconds_block = (
        "\n".join(f"  - {p}" for p in preconds)
        if preconds
        else "  - Sin precondiciones registradas."
    )
    outputs = ""
    if recipe and isinstance(recipe.get("outputs_typical"), str):
        outputs = recipe["outputs_typical"].strip()
    outputs_block = outputs or "Resultado equivalente al de la receta original."
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {safe_desc}\n"
        "version: 1.0.0\n"
        "risk_level: approval_required\n"
        "allowed_tools:\n"
        "  - search_local_docs\n"
        "  - read_document_pages\n"
        "  - write_workspace_file\n"
        "  - get_relevant_memory\n"
        "  - propose_memory_update\n"
        "---\n\n"
        f"# {name}\n\n"
        f"{safe_desc}\n\n"
        "## Precondiciones\n"
        f"{preconds_block}\n\n"
        "## Pasos validados\n"
        f"{body_steps}\n\n"
        "## Salida esperada\n"
        f"{outputs_block}\n\n"
        "## Procedencia\n"
        f"Auto-promoted from memory `{source_memory_id}`. Generated by "
        "`deepagents.skill_promoter` (Fase 80). Disable by editing the\n"
        "frontmatter `risk_level` to `disabled` or moving the file out of\n"
        "the user skills directory.\n"
    )


async def _existing_promotion_proposal(
    session: AsyncSession,
    memory_id: UUID,
) -> DeepAgentMemoryProposalRecord | None:
    """Return any open promotion proposal already on file for a memory."""
    result = await session.execute(
        select(DeepAgentMemoryProposalRecord)
        .where(
            and_(
                DeepAgentMemoryProposalRecord.metadata_json["payload"]["skill_promotion"][
                    "source_memory_id"
                ].astext
                == str(memory_id),
                DeepAgentMemoryProposalRecord.status.in_(("pending", "approved", "applied")),
            )
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def propose_skill_promotion(
    record: DeepAgentMemoryRecord,
    stats: PromotionStats,
    *,
    memory_service: DeepAgentMemoryService | None = None,
    session: AsyncSession,
) -> PromotionResult:
    """Create a ``DeepAgentMemoryProposal`` capturing the promotion intent.

    The proposal lives in the same table as recipe / warning proposals so
    the existing approval UI just works. The differentiator is
    ``metadata.skill_promotion`` — the approve handler reads that to
    decide whether to materialise a YAML skill file.
    """
    service = memory_service or DeepAgentMemoryService()
    existing = await _existing_promotion_proposal(session, record.id)
    if existing is not None:
        return PromotionResult(
            record.id,
            "already_proposed",
            proposal_id=str(existing.id),
            reason=f"existing_proposal_status={existing.status}",
        )

    payload = record.metadata_json or {}
    recipe = payload.get("recipe") if isinstance(payload, dict) else None
    if not isinstance(recipe, dict):
        recipe = None
    suggested_title = (recipe or {}).get("title") if recipe else None
    content_lines = (record.content_redacted or "").splitlines()
    first_content_line = content_lines[0] if content_lines else ""
    base_name = suggested_title or first_content_line
    skill_name = _slugify(str(base_name) or f"procedure-{record.id.hex[:8]}")
    description = (recipe or {}).get("summary") if recipe else None
    if not isinstance(description, str) or not description.strip():
        description = first_content_line[:280] or skill_name

    proposal_id = str(uuid4())
    yaml_text = render_yaml_skill_text(
        name=skill_name,
        description=description,
        recipe=recipe,
        source_memory_id=record.id,
    )
    scope_value: DeepAgentMemoryScope = record.scope or "agent"  # type: ignore[assignment]
    proposal = DeepAgentMemoryProposal(
        proposal_id=proposal_id,
        proposed_by_agent="skill_promoter",
        scope=scope_value,
        reason=(
            f"Procedure `{skill_name}` ya tiene {stats.success_count} éxitos / "
            f"{stats.failure_count} fallos. Lista para promoverse a skill."
        ),
        proposed_content=(
            f"Promover memoria {record.id} a skill `{skill_name}` "
            f"({stats.success_count}/{stats.total_resolved or 0} éxitos, "
            f"failure_rate={stats.failure_rate:.0%})."
        ),
        sensitivity=record.sensitivity or "internal",  # type: ignore[arg-type]
        source_task_id=str(record.id),
        requires_approval=True,
        user_id=record.user_id,
        case_id=record.case_id,
        thread_id=record.thread_id,
        kind="procedure",
        confidence=min(0.9, 0.6 + 0.05 * stats.success_count),
        metadata={
            "skill_promotion": {
                "source_memory_id": str(record.id),
                "skill_name": skill_name,
                "route": "yaml",
                "yaml_skill_text": yaml_text,
                "stats": {
                    "success_count": stats.success_count,
                    "failure_count": stats.failure_count,
                    "partial_count": stats.partial_count,
                    "failure_rate": stats.failure_rate,
                },
                "promoted_at_utc": datetime.now(UTC).isoformat(),
                "agent_name": record.agent_name,
            },
            "extracted_by": "fase80_skill_promoter",
        },
    )
    await service.propose_memory_update(proposal, session=session)
    return PromotionResult(
        record.id,
        "proposal_created",
        proposal_id=proposal_id,
        reason=f"successes={stats.success_count} failures={stats.failure_count}",
    )


async def evaluate_pending_promotions(
    *,
    memory_service: DeepAgentMemoryService | None = None,
    app_settings: Settings | None = None,
) -> dict[str, Any]:
    """Sweep active procedure records, emit promotion proposals when ready.

    Called by the Celery beat task. Safe to invoke from the admin REST
    endpoint for an on-demand pass.
    """
    cfg = app_settings or settings
    if not cfg.skill_promoter_enabled:
        return {
            "skipped": True,
            "reason": "SKILL_PROMOTER_ENABLED=false",
        }
    limit = max(1, cfg.skill_promoter_max_per_cycle)
    min_successes = max(1, cfg.skill_promoter_min_successes)
    max_failure_rate = max(0.0, min(1.0, cfg.skill_promoter_max_failure_rate))

    summary: dict[str, Any] = {
        "scanned_procedures": 0,
        "proposals_created": 0,
        "already_proposed": 0,
        "below_threshold": 0,
        "skipped": 0,
        "proposal_ids": [],
    }
    async with session_scope() as session:
        candidates = (
            (
                await session.execute(
                    select(DeepAgentMemoryRecord)
                    .where(
                        and_(
                            DeepAgentMemoryRecord.kind == "procedure",
                            DeepAgentMemoryRecord.status == "active",
                        )
                    )
                    .order_by(DeepAgentMemoryRecord.updated_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        for record in candidates:
            summary["scanned_procedures"] += 1
            stats = await gather_stats(record.id, session=session)
            if stats.success_count < min_successes:
                summary["below_threshold"] += 1
                continue
            if stats.failure_rate > max_failure_rate:
                summary["below_threshold"] += 1
                continue
            try:
                result = await propose_skill_promotion(
                    record,
                    stats,
                    memory_service=memory_service,
                    session=session,
                )
            except Exception:  # noqa: BLE001
                logger.exception("skill_promoter_failed memory_id=%s", record.id)
                summary["skipped"] += 1
                continue
            if result.status == "proposal_created":
                summary["proposals_created"] += 1
                if result.proposal_id:
                    summary["proposal_ids"].append(result.proposal_id)
            elif result.status == "already_proposed":
                summary["already_proposed"] += 1
            else:
                summary["skipped"] += 1
    return summary


def _user_skills_root(cfg: Settings) -> Path:
    """Resolve the on-disk root where auto-promoted skills live.

    We use a `_auto/` subdirectory of the configured user skills dir so a
    rollback / wipe is just `rm -rf ./storage/deepagents/skills/user/_auto`.
    """
    root = Path(cfg.deepagents_user_skills_dir).resolve() / "_auto"
    root.mkdir(parents=True, exist_ok=True)
    return root


async def materialise_yaml_skill(
    proposal_id: str | UUID,
    *,
    approver_user_id: str,
    app_settings: Settings | None = None,
) -> dict[str, Any]:
    """Write the YAML skill referenced by ``proposal_id`` to disk.

    Idempotent: if the file already exists with identical content we
    leave it alone. We also flip the proposal row to ``status=applied``
    and emit a derived memory row so the registry shows up in startup
    memory.

    Returns a small descriptor suitable for the API response.
    """
    cfg = app_settings or settings
    pid = proposal_id if isinstance(proposal_id, UUID) else UUID(str(proposal_id))
    async with session_scope() as session:
        record = await session.get(DeepAgentMemoryProposalRecord, pid)
        if record is None:
            msg = f"proposal_not_found: {pid}"
            raise ValueError(msg)
        payload = (record.metadata_json or {}).get("payload") or {}
        promotion = payload.get("skill_promotion") if isinstance(payload, dict) else None
        if not isinstance(promotion, dict):
            msg = f"proposal_missing_skill_promotion_payload: {pid}"
            raise ValueError(msg)
        skill_name = str(promotion.get("skill_name") or "").strip()
        yaml_text = promotion.get("yaml_skill_text")
        if not skill_name or not isinstance(yaml_text, str):
            msg = f"proposal_skill_promotion_incomplete: {pid}"
            raise ValueError(msg)
        slug = _slugify(skill_name)
        root = _user_skills_root(cfg)
        skill_dir = root / slug
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists() and skill_file.read_text(encoding="utf-8") == yaml_text:
            already_existed = True
        else:
            skill_file.write_text(yaml_text, encoding="utf-8")
            already_existed = False
        record.status = "applied"
        record.decided_at = datetime.now(UTC)
        # Make the materialised skill discoverable as an active memory
        # too, so the next agent build (which calls list_memory) sees the
        # promotion summary alongside other notes.
        source_id = promotion.get("source_memory_id")
        agent_name = promotion.get("agent_name") or record.proposed_by_agent
        memory_row = DeepAgentMemoryRecord(
            scope=record.scope,
            user_id=None,
            case_id=None,
            thread_id=None,
            agent_name=str(agent_name) if agent_name else "skill_promoter",
            kind="procedure",
            content_redacted=(
                f"Skill `{slug}` promovido desde la memoria {source_id}. "
                f"Archivo: storage/deepagents/skills/user/_auto/{slug}/SKILL.md."
            ),
            source="consolidated",
            confidence=0.9,
            sensitivity=record.sensitivity,
            status="active",
            metadata_json={
                "approved_by": approver_user_id,
                "proposal_id": str(pid),
                "skill_slug": slug,
                "source_memory_id": str(source_id) if source_id else None,
                "auto_promoted_from_procedure": True,
                "skill_file": str(skill_file),
            },
        )
        session.add(memory_row)
        await session.flush()
        return {
            "proposal_id": str(pid),
            "skill_slug": slug,
            "skill_file": str(skill_file),
            "already_existed": already_existed,
            "memory_id": str(memory_row.id),
        }


async def disable_underperforming_auto_skills(
    *,
    app_settings: Settings | None = None,
) -> dict[str, Any]:
    """Rollback safety — disable auto-promoted skills with poor track record.

    Sweeps recently-promoted skill memories (last
    ``rollback_window_days``) and computes their post-promotion outcome
    ratio. If failures dominate beyond ``rollback_max_failure_rate`` the
    memory row is archived and the on-disk YAML file is renamed to
    ``SKILL.md.disabled`` so the registry stops loading it. Reversible
    by renaming the file back.
    """
    cfg = app_settings or settings
    window_days = max(1, cfg.skill_promoter_rollback_window_days)
    max_failure_rate = max(0.0, min(1.0, cfg.skill_promoter_rollback_max_failure_rate))
    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    summary: dict[str, Any] = {
        "checked": 0,
        "disabled": 0,
        "ok": 0,
        "disabled_slugs": [],
    }
    async with session_scope() as session:
        query = select(DeepAgentMemoryRecord).where(
            and_(
                DeepAgentMemoryRecord.kind == "procedure",
                DeepAgentMemoryRecord.status == "active",
                DeepAgentMemoryRecord.created_at >= cutoff,
                DeepAgentMemoryRecord.metadata_json["auto_promoted_from_procedure"].astext
                == "true",
            )
        )
        promotions: Sequence[DeepAgentMemoryRecord] = (await session.execute(query)).scalars().all()
        for promotion in promotions:
            summary["checked"] += 1
            stats = await gather_stats(promotion.id, session=session)
            denom = stats.total_resolved
            if denom == 0:
                summary["ok"] += 1
                continue
            failure_rate = stats.failure_rate
            if failure_rate <= max_failure_rate:
                summary["ok"] += 1
                continue
            slug = (promotion.metadata_json or {}).get("skill_slug")
            skill_file_path = (promotion.metadata_json or {}).get("skill_file")
            promotion.status = "archived"
            promotion.metadata_json = {
                **(promotion.metadata_json or {}),
                "rollback_disabled_at": datetime.now(UTC).isoformat(),
                "rollback_failure_rate": failure_rate,
            }
            if isinstance(skill_file_path, str):
                try:
                    src = Path(skill_file_path)
                    if src.exists():
                        src.rename(src.with_suffix(".md.disabled"))
                except OSError as exc:  # pragma: no cover — surfaced via summary
                    logger.warning(
                        "skill_promoter_rollback_rename_failed slug=%s error=%s",
                        slug,
                        type(exc).__name__,
                    )
            summary["disabled"] += 1
            if isinstance(slug, str):
                summary["disabled_slugs"].append(slug)
    return summary


async def list_skill_promotion_proposals() -> list[dict[str, Any]]:
    """Return open / applied promotion proposals for the UI."""
    async with session_scope() as session:
        result = await session.execute(
            select(DeepAgentMemoryProposalRecord)
            .where(
                DeepAgentMemoryProposalRecord.metadata_json["payload"]["skill_promotion"].isnot(
                    None,
                )
            )
            .order_by(DeepAgentMemoryProposalRecord.created_at.desc())
        )
        items: list[dict[str, Any]] = []
        for row in result.scalars().all():
            meta = row.metadata_json or {}
            payload = meta.get("payload") or {}
            promotion = payload.get("skill_promotion") or {}
            items.append(
                {
                    "proposal_id": str(row.id),
                    "status": row.status,
                    "proposed_by_agent": row.proposed_by_agent,
                    "reason": row.reason,
                    "skill_name": promotion.get("skill_name"),
                    "route": promotion.get("route"),
                    "source_memory_id": promotion.get("source_memory_id"),
                    "stats": promotion.get("stats"),
                    "promoted_at_utc": promotion.get("promoted_at_utc"),
                    "created_at": row.created_at.isoformat(),
                    "decided_at": row.decided_at.isoformat() if row.decided_at else None,
                }
            )
        return items

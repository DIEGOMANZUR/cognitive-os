from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.sql.elements import ColumnElement

from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import (
    ActionRequest,
    AuditEvent,
    HumanApproval,
    Job,
    JobEvent,
    MailAccount,
    MailMessage,
)

FIXTURE_SOURCE = "commercial_qa"
FixtureScenario = Literal[
    "empty",
    "degraded",
    "populated",
    "pending_approval",
    "failed_job",
    "retryable_job",
    "mail_digest_disabled",
    "mail_digest_read_only",
    "malformed_api_state",
    "mobile_friendly_state",
]

router = APIRouter(prefix="/test/fixtures", tags=["test-fixtures"])


class FixtureState(BaseModel):
    enabled: bool
    source: str = FIXTURE_SOURCE
    scenarios_seeded: list[str] = Field(default_factory=list)
    jobs: int = 0
    job_events: int = 0
    approvals: int = 0
    action_requests: int = 0
    mail_accounts: int = 0
    mail_messages: int = 0
    audit_events: int = 0
    notes: list[str] = Field(default_factory=list)


def _fixtures_enabled() -> bool:
    app_env = os.environ.get("APP_ENV", "").strip().lower()
    enabled = os.environ.get("COGOS_TEST_FIXTURES_ENABLED", "").strip().lower()
    return (
        settings.environment == "test" or app_env == "test" or enabled in {"1", "true", "yes", "on"}
    )


def _require_fixtures_enabled() -> None:
    if _fixtures_enabled():
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Test fixtures are disabled. Set APP_ENV=test or "
            "COGOS_TEST_FIXTURES_ENABLED=true before starting the API."
        ),
    )


def _meta(scenario: str, **extra: object) -> dict[str, object]:
    return {"fixture_source": FIXTURE_SOURCE, "fixture_scenario": scenario, **extra}


def _is_fixture(model: Any) -> ColumnElement[bool]:
    return cast(ColumnElement[bool], model.metadata_json["fixture_source"].astext == FIXTURE_SOURCE)


async def _reset_fixtures() -> None:
    async with session_scope() as session:
        fixture_accounts = select(MailAccount.id).where(_is_fixture(MailAccount))
        fixture_jobs = select(Job.id).where(_is_fixture(Job))
        await session.execute(
            delete(MailMessage).where(MailMessage.account_id.in_(fixture_accounts))
        )
        await session.execute(delete(MailAccount).where(_is_fixture(MailAccount)))
        await session.execute(delete(JobEvent).where(JobEvent.job_id.in_(fixture_jobs)))
        await session.execute(delete(ActionRequest).where(_is_fixture(ActionRequest)))
        await session.execute(delete(HumanApproval).where(_is_fixture(HumanApproval)))
        await session.execute(delete(Job).where(_is_fixture(Job)))
        await session.execute(delete(AuditEvent).where(_is_fixture(AuditEvent)))


async def _create_job(
    *,
    scenario: str,
    job_type: str,
    job_status: str,
    progress: int,
    event_type: str,
    event_status: str,
    message: str,
    stale: bool = False,
    retryable: bool = False,
) -> Job:
    stale_at = datetime.now(UTC) - timedelta(hours=max(settings.stale_job_max_hours + 1, 2))
    job = Job(
        job_type=job_type,
        status=job_status,
        progress=progress,
        metadata_json=_meta(scenario, retryable=retryable),
    )
    if stale:
        job.created_at = stale_at
        job.updated_at = stale_at
    async with session_scope() as session:
        session.add(job)
        await session.flush()
        event = JobEvent(
            job_id=job.id,
            event_type=event_type,
            status=event_status,
            message=message,
            metadata_json=_meta(scenario, retryable=retryable),
        )
        if stale:
            event.created_at = stale_at
            event.updated_at = stale_at
        session.add(event)
        await session.flush()
        return job


async def _seed_pending_approval() -> None:
    scenario = "pending_approval"
    async with session_scope() as session:
        job = Job(
            job_type="action_request",
            status="waiting_approval",
            progress=0,
            metadata_json=_meta(scenario),
        )
        session.add(job)
        await session.flush()
        action_request = ActionRequest(
            action_type="computer_organize",
            status="pending_approval",
            requested_by="commercial-qa",
            idempotency_key="commercial-qa-pending-approval",
            payload_redacted={"root": "/tmp/cognitive-os-fixture", "dry_run": True},
            payload_executable={"root": "/tmp/cognitive-os-fixture", "dry_run": True},
            preview={"summary": "No-op fixture action for QA only.", "dry_run": True},
            job_id=job.id,
            metadata_json=_meta(scenario),
        )
        session.add(action_request)
        await session.flush()
        approval = HumanApproval(
            action="execute_action_request",
            requested_action=f"execute_action_request:{action_request.id}",
            args_redacted={"action_type": "computer_organize", "dry_run": True},
            requested_by="commercial-qa",
            job_id=job.id,
            status="pending",
            metadata_json=_meta(scenario),
        )
        session.add(approval)
        await session.flush()
        action_request.approval_id = approval.id
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="fixture_waiting_approval",
                status="waiting_approval",
                message="Commercial QA fixture approval is pending.",
                metadata_json=_meta(scenario, action_request_id=str(action_request.id)),
            )
        )


async def _seed_mail_read_only() -> None:
    scenario = "mail_digest_read_only"
    async with session_scope() as session:
        account = MailAccount(
            label="fixture-readonly-mail",
            kind="imap",
            email_address="fixture@example.test",
            username="fixture@example.test",
            monitor_folders=["Fixture"],
            send_capable=False,
            is_default_sender=False,
            active=True,
            metadata_json=_meta(scenario),
        )
        session.add(account)
        await session.flush()
        session.add(
            MailMessage(
                account_id=account.id,
                folder="Fixture",
                uid="fixture-001",
                sender="sender@example.test",
                recipients=["fixture@example.test"],
                subject="Fixture read-only reply proposal",
                snippet="Local fixture message with a proposed response.",
                body_text="This message is safe fixture data only.",
                received_at=datetime.now(UTC),
                classification="important",
                importance_score=0.91,
                proposed_reply_text="Texto sugerido por fixture. Copiar manualmente; no draft.",
                proposed_reply_rationale="Fixture confirms read-only mail UX.",
                status="reply_proposed",
                metadata_json=_meta(scenario),
            )
        )


async def _seed_scenario(scenario: FixtureScenario) -> None:
    if scenario == "empty":
        return
    if scenario == "populated":
        await _create_job(
            scenario=scenario,
            job_type="deepagent_research",
            job_status="running",
            progress=42,
            event_type="fixture_progress",
            event_status="running",
            message="Commercial QA populated fixture is running.",
        )
        await _seed_mail_read_only()
        return
    if scenario == "pending_approval":
        await _seed_pending_approval()
        return
    if scenario == "failed_job":
        await _create_job(
            scenario=scenario,
            job_type="document_analysis",
            job_status="failed",
            progress=100,
            event_type="fixture_failed",
            event_status="failed",
            message="Fixture job failed with visible diagnostics.",
        )
        return
    if scenario == "retryable_job":
        await _create_job(
            scenario=scenario,
            job_type="deepagent_research",
            job_status="failed",
            progress=100,
            event_type="fixture_retry_available",
            event_status="failed",
            message="Fixture failure is retryable; operator can rerun the workflow.",
            retryable=True,
        )
        return
    if scenario == "degraded":
        await _create_job(
            scenario=scenario,
            job_type="action_request",
            job_status="running",
            progress=5,
            event_type="fixture_stale_running_job",
            event_status="running",
            message="Fixture stale running job should degrade operational_backlog.",
            stale=True,
        )
        return
    if scenario == "mail_digest_read_only":
        await _seed_mail_read_only()
        return
    if scenario in {"mail_digest_disabled", "malformed_api_state", "mobile_friendly_state"}:
        async with session_scope() as session:
            session.add(
                AuditEvent(
                    actor_id="commercial-qa",
                    action=f"fixture_{scenario}",
                    resource_type="test_fixture",
                    resource_id=scenario,
                    metadata_json=_meta(scenario),
                )
            )
        return


async def _state() -> FixtureState:
    async with session_scope() as session:
        fixture_jobs = select(Job.id).where(_is_fixture(Job))
        fixture_accounts = select(MailAccount.id).where(_is_fixture(MailAccount))
        rows: dict[str, int | None] = {
            "jobs": await session.scalar(select(func.count(Job.id)).where(_is_fixture(Job))),
            "job_events": await session.scalar(
                select(func.count(JobEvent.id)).where(JobEvent.job_id.in_(fixture_jobs))
            ),
            "approvals": await session.scalar(
                select(func.count(HumanApproval.id)).where(_is_fixture(HumanApproval))
            ),
            "action_requests": await session.scalar(
                select(func.count(ActionRequest.id)).where(_is_fixture(ActionRequest))
            ),
            "mail_accounts": await session.scalar(
                select(func.count(MailAccount.id)).where(_is_fixture(MailAccount))
            ),
            "mail_messages": await session.scalar(
                select(func.count(MailMessage.id)).where(
                    MailMessage.account_id.in_(fixture_accounts)
                )
            ),
            "audit_events": await session.scalar(
                select(func.count(AuditEvent.id)).where(_is_fixture(AuditEvent))
            ),
        }
        scenarios = await session.execute(
            select(AuditEvent.metadata_json["fixture_scenario"].astext).where(
                _is_fixture(AuditEvent)
            )
        )
    seeded = sorted({str(item) for item in scenarios.scalars().all() if item})
    notes: list[str] = []
    if rows["jobs"]:
        notes.append("Fixture jobs are visible through /jobs and /jobs/{id}/events.")
    if rows["approvals"]:
        notes.append("Fixture approval is safe/no-op and uses redacted dry-run payload.")
    if rows["mail_messages"]:
        notes.append("Fixture mail data is read-only and uses example.test addresses.")
    counts = {key: int(value or 0) for key, value in rows.items()}
    return FixtureState(
        enabled=_fixtures_enabled(),
        scenarios_seeded=seeded,
        jobs=counts["jobs"],
        job_events=counts["job_events"],
        approvals=counts["approvals"],
        action_requests=counts["action_requests"],
        mail_accounts=counts["mail_accounts"],
        mail_messages=counts["mail_messages"],
        audit_events=counts["audit_events"],
        notes=notes,
    )


@router.post("/reset", response_model=FixtureState)
async def reset_test_fixtures() -> FixtureState:
    _require_fixtures_enabled()
    await _reset_fixtures()
    return await _state()


@router.post("/seed/{scenario}", response_model=FixtureState)
async def seed_test_fixture(scenario: FixtureScenario) -> FixtureState:
    _require_fixtures_enabled()
    await _seed_scenario(scenario)
    async with session_scope() as session:
        session.add(
            AuditEvent(
                actor_id="commercial-qa",
                action="fixture_seeded",
                resource_type="test_fixture",
                resource_id=scenario,
                metadata_json=_meta(scenario),
            )
        )
    return await _state()


@router.get("/state", response_model=FixtureState)
async def test_fixture_state() -> FixtureState:
    _require_fixtures_enabled()
    return await _state()

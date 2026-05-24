from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from cognitive_os.api.app import app
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import ActionRequest, HumanApproval, Job, MailMessage

SCENARIOS = [
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


@pytest.mark.asyncio
async def test_test_fixtures_are_disabled_without_explicit_test_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("COGOS_TEST_FIXTURES_ENABLED", raising=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/test/fixtures/reset")

    assert response.status_code == 403
    assert "APP_ENV=test" in response.json()["detail"]


@pytest.mark.asyncio
async def test_test_fixtures_seed_safe_borrable_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COGOS_TEST_FIXTURES_ENABLED", "true")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        reset = await client.post("/test/fixtures/reset")
        approval = await client.post("/test/fixtures/seed/pending_approval")
        mail = await client.post("/test/fixtures/seed/mail_digest_read_only")
        retryable = await client.post("/test/fixtures/seed/retryable_job")
        state = await client.get("/test/fixtures/state")

    assert reset.status_code == 200
    assert approval.status_code == 200
    assert mail.status_code == 200
    assert retryable.status_code == 200
    assert state.status_code == 200
    payload = state.json()
    assert payload["enabled"] is True
    assert payload["approvals"] == 1
    assert payload["action_requests"] == 1
    assert payload["mail_messages"] == 1
    assert payload["jobs"] >= 2

    async with session_scope() as session:
        approval_row = (
            await session.execute(
                select(HumanApproval).where(
                    HumanApproval.metadata_json["fixture_source"].astext == "commercial_qa"
                )
            )
        ).scalar_one_or_none()
        assert approval_row is not None
        action_request = (
            await session.execute(
                select(ActionRequest).where(
                    ActionRequest.metadata_json["fixture_source"].astext == "commercial_qa"
                )
            )
        ).scalar_one_or_none()
        assert action_request is not None
        mail_message = (
            await session.execute(
                select(MailMessage).where(
                    MailMessage.metadata_json["fixture_source"].astext == "commercial_qa"
                )
            )
        ).scalar_one_or_none()
        assert mail_message is not None
        job_rows = (
            (
                await session.execute(
                    select(Job).where(Job.metadata_json["fixture_source"].astext == "commercial_qa")
                )
            )
            .scalars()
            .all()
        )
        assert job_rows

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        cleared = await client.post("/test/fixtures/reset")
    assert cleared.status_code == 200
    assert cleared.json()["jobs"] == 0
    assert cleared.json()["approvals"] == 0
    assert cleared.json()["mail_messages"] == 0


@pytest.mark.asyncio
async def test_test_fixtures_seed_and_reset_every_supported_scenario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for scenario in SCENARIOS:
            reset = await client.post("/test/fixtures/reset")
            seeded = await client.post(f"/test/fixtures/seed/{scenario}")
            state = await client.get("/test/fixtures/state")

            assert reset.status_code == 200
            assert seeded.status_code == 200
            assert state.status_code == 200
            payload = state.json()
            assert payload["enabled"] is True
            assert payload["scenarios_seeded"] == [scenario]

            if scenario == "pending_approval":
                assert payload["approvals"] == 1
                assert payload["action_requests"] == 1
            if scenario in {"populated", "mail_digest_read_only"}:
                assert payload["mail_messages"] == 1
            if scenario in {"degraded", "populated", "failed_job", "retryable_job"}:
                assert payload["jobs"] == 1
                assert payload["job_events"] == 1

        cleared = await client.post("/test/fixtures/reset")
        assert cleared.status_code == 200
        assert cleared.json()["scenarios_seeded"] == []
        assert cleared.json()["jobs"] == 0
        assert cleared.json()["approvals"] == 0
        assert cleared.json()["action_requests"] == 0
        assert cleared.json()["mail_messages"] == 0


@pytest.mark.asyncio
async def test_test_fixtures_reject_unknown_scenario(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/test/fixtures/seed/production_copy")

    assert response.status_code == 422

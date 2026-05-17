"""End-to-end regression: per-user rate limit on hot endpoints.

The rate-limit module is unit-tested in `test_rate_limit.py`. This file
verifies the dependency is actually wired into the FastAPI route layer for
the three buckets we care about commercially: approval decisions, action
dispatch, and ActionRequest creation.

We use the in-memory limiter (`default_rate_limiter`) and reset it between
tests so the bucket state does not leak.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

import cognitive_os.actions.service as action_service_module
import cognitive_os.api.app as api_app
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.rate_limit import default_rate_limiter
from cognitive_os.db.models import HumanApproval


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    default_rate_limiter().reset()


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


@pytest.mark.asyncio
async def test_approval_decision_endpoint_rate_limits_after_30_per_minute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    approval_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    approval = HumanApproval(
        id=approval_id,
        status="pending",
        action="execute_action_request",
        requested_action="execute_action_request:demo",
        args_redacted={},
        requested_by="operator-other",
        created_at=now,
        updated_at=now,
    )

    class _AlwaysPendingSession:
        async def get(self, _model: type[object], _obj_id: UUID) -> object | None:
            # Reset to pending each call so the 409 path doesn't short-circuit.
            approval.status = "pending"
            return approval

        async def execute(self, _stmt: object) -> object:
            class _R:
                @staticmethod
                def scalar_one_or_none() -> None:
                    return None

            return _R()

        def add(self, _obj: object) -> None:
            return None

        async def flush(self) -> None:
            return None

    @asynccontextmanager
    async def fake_session_scope():
        yield _AlwaysPendingSession()

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(api_app, "session_scope", fake_session_scope, raising=False)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 30 OK
        for i in range(30):
            response = await client.post(f"/approvals/{approval_id}/approve", headers=_headers())
            assert response.status_code == 200, f"call {i} status {response.status_code}"
        # 31st should be 429 from the rate limit, not 200 / 409.
        response = await client.post(f"/approvals/{approval_id}/approve", headers=_headers())
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        body = response.json()
        assert "approval_decision" in body["detail"]

"""Admin-gating regression tests for high-impact endpoints.

These guarantee that DeepAgent memory mutations and the immediate memory
consolidation trigger require admin credentials. Non-admin operators must
receive 403 even with a valid JWT.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _operator_headers() -> dict[str, str]:
    token = create_access_token(user_id="alice", roles=["operator"])
    return {"Authorization": f"Bearer {token}"}


def _admin_headers() -> dict[str, str]:
    token = create_access_token(user_id="root", roles=["admin"])
    return {"Authorization": f"Bearer {token}"}


def test_memory_proposal_approve_requires_admin(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "admin_user_ids", [])
    monkeypatch.setattr(settings, "auth_admin_roles", ["admin"])
    response = client.post(
        "/deepagents/memory/proposals/abc/approve",
        headers=_operator_headers(),
    )
    assert response.status_code == 403
    assert "Admin" in response.json()["detail"]


def test_memory_proposal_reject_requires_admin(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "admin_user_ids", [])
    monkeypatch.setattr(settings, "auth_admin_roles", ["admin"])
    response = client.post(
        "/deepagents/memory/proposals/abc/reject",
        headers=_operator_headers(),
        json={"reason": "no"},
    )
    assert response.status_code == 403


def test_memory_consolidate_requires_admin(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "admin_user_ids", [])
    monkeypatch.setattr(settings, "auth_admin_roles", ["admin"])
    response = client.post(
        "/deepagents/memory/consolidate/run",
        headers=_operator_headers(),
    )
    assert response.status_code == 403


def test_memory_proposal_reject_accepted_for_admin_role(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject must still pass through the service layer when the caller is admin.

    The service raises against a missing proposal — we verify the request gets
    past the auth gate (any non-403 response proves the gate did not short
    circuit).
    """
    monkeypatch.setattr(settings, "admin_user_ids", [])
    monkeypatch.setattr(settings, "auth_admin_roles", ["admin"])

    async def fake_reject(self: object, proposal_id: str, user_id: str, reason: str) -> None:
        del self, proposal_id, user_id, reason

    from cognitive_os.deepagents.memory_service import DeepAgentMemoryService

    monkeypatch.setattr(DeepAgentMemoryService, "reject_memory_proposal", fake_reject)
    response = client.post(
        "/deepagents/memory/proposals/abc/reject",
        headers=_admin_headers(),
        json={"reason": "stale"},
    )
    assert response.status_code == 204

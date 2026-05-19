"""Regression for the operator-facing `/system/info` snapshot."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


def test_system_info_requires_auth(client: TestClient) -> None:
    response = client.get("/system/info")
    assert response.status_code == 401


def test_system_info_returns_policy_snapshot(client: TestClient) -> None:
    """`/system/info` mirrors the live settings — assert shape + sane ranges,
    not absolute values. Absolute defaults are exercised hermetically in
    `tests/test_config.py`. The operator's `.env` (perfil dedicated_local
    + overrides explícitos) legitimately reshapes the booleans here, so
    this regression is now only a wiring + types contract.
    """
    response = client.get("/system/info", headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "cognitive-os"
    assert "python_version" in body
    assert "fastapi_version" in body
    # Fase 68b: operator_profile is reported so the panel can show the
    # active profile in the header.
    assert body.get("operator_profile") in {"strict", "dedicated_local"}
    # Shape contract — values come from settings; both perfiles produce booleans.
    assert isinstance(body["approval_require_four_eyes"], bool)
    assert isinstance(body["require_human_approval_for_external_actions"], bool)
    assert body["approval_pending_max_hours"] >= 1
    # New runtime metadata fields (may be None when running outside a git tree).
    assert "git_commit" in body
    assert "alembic_head" in body

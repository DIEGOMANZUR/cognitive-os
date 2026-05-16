from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token, decode_jwt
from cognitive_os.core.config import settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_langsmith_ok_when_gate_off(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "langsmith_endpoints_require_admin", False)
    headers = {"Authorization": f"Bearer {create_access_token(user_id='1')}"}
    response = client.get("/langsmith/status", headers=headers)
    assert response.status_code == 200


def test_langsmith_forbidden_when_gate_on_and_admin_list_empty(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "langsmith_endpoints_require_admin", True)
    monkeypatch.setattr(settings, "admin_user_ids", [])
    monkeypatch.setattr(settings, "auth_admin_roles", ["admin"])
    headers = {"Authorization": f"Bearer {create_access_token(user_id='1')}"}
    response = client.get("/langsmith/status", headers=headers)
    assert response.status_code == 403


def test_langsmith_ok_when_gate_on_and_jwt_is_admin(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "langsmith_endpoints_require_admin", True)
    monkeypatch.setattr(settings, "admin_user_ids", [1])
    headers = {"Authorization": f"Bearer {create_access_token(user_id='1')}"}
    response = client.get("/langsmith/status", headers=headers)
    assert response.status_code == 200


def test_langsmith_ok_when_gate_on_and_jwt_has_admin_role(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "langsmith_endpoints_require_admin", True)
    monkeypatch.setattr(settings, "admin_user_ids", [])
    monkeypatch.setattr(settings, "auth_admin_roles", ["admin"])
    headers = {
        "Authorization": f"Bearer {create_access_token(user_id='external', roles=['admin'])}"
    }
    response = client.get("/langsmith/status", headers=headers)
    assert response.status_code == 200


def test_local_access_tokens_include_normalized_roles() -> None:
    token = create_access_token(user_id="operator-1", roles=["Admin", " operator ", ""])
    payload = decode_jwt(token)

    assert payload["roles"] == ["admin", "operator"]

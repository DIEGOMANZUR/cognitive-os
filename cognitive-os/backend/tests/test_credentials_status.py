"""Regression for /system/credentials-status and the inventory module."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import Settings
from cognitive_os.core.credentials_inventory import (
    INVENTORY,
    CredentialSpec,
    build_status,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='root', roles=['admin'])}"}


def _operator_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='alice', roles=['operator'])}"}


def test_inventory_attrs_resolve_against_settings() -> None:
    """Every `setting_attr` declared in the inventory must exist on Settings."""
    cfg = Settings()
    for spec in INVENTORY:
        for attr in spec.setting_attrs:
            assert hasattr(cfg, attr), f"{spec.name!r} references missing Settings.{attr}"


def _placeholder_settings() -> Settings:
    """Build a Settings with the documented `CHANGEME` placeholders.

    `Settings()` would otherwise inherit values from the operator's local
    `.env` (pydantic-settings reads it by default), so we force every secret
    we care about back to its placeholder before asserting the inventory.
    """
    from pydantic import SecretStr

    fields = {
        "mail_enabled": False,
        "mail_godaddy_enabled": False,
        "enable_personal_assistant_api": False,
        "enable_google_calendar": False,
        "enable_google_drive": False,
        "enable_maps_routing": False,
        "enable_kimi_webbridge": False,
        "telegram_enabled": False,
        "enable_browser_automation": False,
        "enable_computer_actions": False,
        "voice_enabled": False,
        "enable_research_orchestrator": False,
        "primary_llm_api_key": SecretStr("CHANGEME"),
        "embeddings_api_key": SecretStr("CHANGEME"),
        "jwt_secret": SecretStr("CHANGEME"),
        "database_url": "postgresql+asyncpg://cog:CHANGEME@localhost:5432/cog",  # noqa: E501  # pragma: allowlist secret
        "neo4j_password": SecretStr("CHANGEME"),
        "weaviate_api_key": SecretStr("CHANGEME"),
        "action_payload_encryption_key": SecretStr("CHANGEME"),
        "gmail_client_id": "CHANGEME",
        "gmail_client_secret": SecretStr("CHANGEME"),
        "google_client_id": "CHANGEME",
        "google_client_secret": SecretStr("CHANGEME"),
        "google_maps_api_key": SecretStr("CHANGEME"),
        "elevenlabs_api_key": SecretStr("CHANGEME"),
        "godaddy_api_key": SecretStr("CHANGEME"),
        "godaddy_api_secret": SecretStr("CHANGEME"),
        "mail_godaddy_username": "CHANGEME",
        "mail_godaddy_password": SecretStr("CHANGEME"),
        "tavily_api_key": SecretStr("CHANGEME"),
        "brave_search_api_key": SecretStr("CHANGEME"),
        "exa_api_key": SecretStr("CHANGEME"),
        "langsmith_api_key": SecretStr("CHANGEME"),
        "telegram_bot_token": SecretStr("CHANGEME"),
    }
    return Settings(**fields)


def test_build_status_reports_placeholder_as_missing() -> None:
    cfg = _placeholder_settings()
    report = build_status(cfg, env={})
    secret_specs = [s for s in INVENTORY if s.setting_attrs or s.env_vars]
    missing_names = {it.name for it in report.items if not it.configured}
    assert "JWT_SECRET" in missing_names
    assert report.total == len(secret_specs)


def test_build_status_marks_required_versus_optional() -> None:
    cfg = _placeholder_settings()
    report = build_status(cfg, env={})
    required_missing = [it for it in report.items if not it.configured and not it.optional]
    assert report.missing_required == len(required_missing)
    required_names = {it.name for it in required_missing}
    assert "PRIMARY_LLM_API_KEY" in required_names
    assert "EMBEDDINGS_API_KEY" in required_names


def test_build_status_picks_up_env_var_credentials() -> None:
    spec = CredentialSpec(
        name="TEST_TOKEN",
        enables="unit test only",
        setting_attrs=(),
        env_vars=("TEST_TOKEN_X",),
        how_to_obtain="N/A",
    )
    cfg = Settings()
    missing = build_status(cfg, inventory=[spec], env={})
    assert missing.items[0].configured is False
    present = build_status(cfg, inventory=[spec], env={"TEST_TOKEN_X": "real-value"})
    assert present.items[0].configured is True
    placeholder = build_status(cfg, inventory=[spec], env={"TEST_TOKEN_X": "CHANGEME"})
    assert placeholder.items[0].configured is False


def test_endpoint_requires_admin(client: TestClient) -> None:
    response = client.get("/system/credentials-status", headers=_operator_headers())
    assert response.status_code == 403


def test_endpoint_returns_structured_payload(client: TestClient) -> None:
    response = client.get("/system/credentials-status", headers=_admin_headers())
    assert response.status_code == 200
    body = response.json()
    assert {"total", "configured", "missing_required", "items"} <= body.keys()
    assert body["total"] == len(INVENTORY)
    assert isinstance(body["items"], list)
    for item in body["items"]:
        assert {"name", "configured", "optional", "enables", "how_to_obtain"} <= item.keys()


def test_endpoint_never_returns_credential_values(client: TestClient) -> None:
    """Defense in depth: no SecretStr value should ever appear in the payload."""
    import json

    response = client.get("/system/credentials-status", headers=_admin_headers())
    body = json.dumps(response.json())
    # Values from .env should never end up serialized. We pick a few canonical
    # markers a real key would carry but a placeholder wouldn't.
    forbidden_markers = ["sk-", "Bearer ", "AIza", "ghp_", "secret-", "pass"]
    for marker in forbidden_markers:
        # `Bearer ` would only sneak in via a leaked Authorization header.
        # `pass` is too generic so we lower-case the haystack and require it
        # to appear next to `word=` style serialization, not in capability text.
        if marker == "pass":
            assert ':"pass' not in body.lower()
        else:
            assert marker not in body, f"endpoint leaked credential marker: {marker}"

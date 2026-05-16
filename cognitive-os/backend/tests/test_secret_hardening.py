"""Regression tests that secrets never leak through APIs, logs, or model dumps.

These guard against accidental `SecretStr.get_secret_value()` in a Pydantic
`BaseModel` field, a logger that forgets to redact, or a future endpoint that
adds a `SecretStr` field to a response body.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, SecretStr

from cognitive_os.core.config import Settings
from cognitive_os.core.logging import _redact_value, redact_secrets
from cognitive_os.core.secrets import (
    PLACEHOLDER,
    SecretNotConfiguredError,
    SecretStore,
    default_secret_store,
)

# Sentinels that uniquely identify each secret in the test environment so the
# leak check is unambiguous (no false positives from normal strings).
_TEST_JWT = "test-jwt-secret-XYZ123-do-not-leak"  # noqa: S105  # pragma: allowlist secret
_TEST_PG_PWD = "test-pg-pwd-ABC987-do-not-leak"  # noqa: S105  # pragma: allowlist secret
_TEST_LLM_KEY = "sk-test-llm-key-do-not-leak-456"  # noqa: S105  # pragma: allowlist secret


def _test_settings() -> Settings:
    """Build a Settings with sentinel secrets the test can grep for."""
    return Settings.model_construct(
        jwt_secret=SecretStr(_TEST_JWT),
        postgres_password=SecretStr(_TEST_PG_PWD),
        primary_llm_api_key=SecretStr(_TEST_LLM_KEY),
        database_url=f"postgresql+asyncpg://cogos:{_TEST_PG_PWD}@localhost:5432/cognitive_os",
    )


def test_settings_model_dump_does_not_leak_secret_values() -> None:
    """Pydantic's default `model_dump()` must keep `SecretStr` opaque.

    This is Pydantic's contract, but verifying it here means a future change
    that switches to `model_dump(mode='python', context={'serialize_as': ...})`
    or similar would fail loudly instead of silently exposing keys.
    """
    cfg = _test_settings()
    dumped = json.dumps(cfg.model_dump(mode="json"), default=str)
    assert _TEST_JWT not in dumped
    assert _TEST_LLM_KEY not in dumped
    # postgres_password is a SecretStr; its raw value must not appear even
    # though `database_url` (a plain str field) does carry it. database_url
    # is intentionally a plain string in this project — the *regression* we
    # protect against is the SecretStr ever serializing its raw value.
    assert "**" in json.dumps(cfg.model_dump(mode="python"), default=str)


def test_secret_store_returns_value_when_configured() -> None:
    cfg = _test_settings()
    store = SecretStore(app_settings=cfg)
    assert store.get("jwt_secret") == _TEST_JWT
    assert store.is_configured("primary_llm_api_key") is True


def test_secret_store_returns_none_for_placeholder() -> None:
    cfg = Settings.model_construct(
        elevenlabs_api_key=SecretStr(PLACEHOLDER),
        notion_api_key=SecretStr("CHANGEME-anything-after"),
    )
    store = SecretStore(app_settings=cfg)
    assert store.get("elevenlabs_api_key") is None
    assert store.get("notion_api_key") is None
    assert store.is_configured("elevenlabs_api_key") is False


def test_secret_store_require_raises_when_missing() -> None:
    cfg = Settings.model_construct(elevenlabs_api_key=SecretStr(PLACEHOLDER))
    store = SecretStore(app_settings=cfg)
    with pytest.raises(SecretNotConfiguredError, match="elevenlabs_api_key"):
        store.require("elevenlabs_api_key")


def test_secret_store_overrides_take_precedence() -> None:
    cfg = _test_settings()
    store = SecretStore(app_settings=cfg, overrides={"jwt_secret": "from-override"})
    assert store.get("jwt_secret") == "from-override"


def test_secret_store_env_override_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _test_settings()
    monkeypatch.setenv("SECRET_OVERRIDE_JWT_SECRET", "from-env")
    store = SecretStore(app_settings=cfg)
    assert store.get("jwt_secret") == "from-env"


def test_secret_store_unknown_name_returns_none() -> None:
    store = SecretStore(app_settings=_test_settings())
    assert store.get("does_not_exist") is None
    assert store.is_configured("does_not_exist") is False


def test_default_secret_store_is_a_singleton() -> None:
    assert default_secret_store() is default_secret_store()


def test_logging_redactor_strips_known_patterns() -> None:
    event = {
        "Authorization": "Bearer abc123-def-456",  # pragma: allowlist secret
        "api_key": "sk-test-key-xyz",  # pragma: allowlist secret
        "nested": {"password": "hunter2", "ok": "value"},  # pragma: allowlist secret
        "dsn": "postgresql://user:pwd@host:5432/db",  # pragma: allowlist secret
        "list": ["sk-leaked-12345", "fine"],  # pragma: allowlist secret
        "value": "Bearer should-be-redacted",  # pragma: allowlist secret
    }
    out = redact_secrets(None, "info", event)
    assert out["Authorization"] == "[REDACTED]"
    assert out["api_key"] == "[REDACTED]"
    assert out["nested"]["password"] == "[REDACTED]"
    assert out["nested"]["ok"] == "value"
    assert "pwd" not in out["dsn"]
    assert out["list"][0] != "sk-leaked-12345"
    assert "should-be-redacted" not in out["value"]


def test_logging_redactor_handles_secretstr() -> None:
    out = _redact_value({"key": SecretStr("very-secret")})
    assert isinstance(out, dict)
    assert out["key"] == "[REDACTED]"


def test_public_config_response_class_has_no_secret_fields() -> None:
    """No field annotated with `SecretStr` may appear in the public config view."""
    from cognitive_os.api.app import PublicConfigResponse

    for field_name, field in PublicConfigResponse.model_fields.items():
        annotation = field.annotation
        assert annotation is not SecretStr, (
            f"PublicConfigResponse.{field_name} must not be SecretStr"
        )


def test_no_response_model_in_app_has_secretstr_field() -> None:
    """No BaseModel response class used by FastAPI declares a SecretStr field.

    This is the regression boundary: a future endpoint that adds a SecretStr to a
    response body would silently serialize it as `"**********"` (Pydantic default),
    but the *intent* of a response body is "public payload". Forbidding the type
    altogether eliminates that footgun.
    """
    import cognitive_os.api.app as app_module

    offenders: list[str] = []
    for name in dir(app_module):
        value = getattr(app_module, name, None)
        if not isinstance(value, type):
            continue
        if not issubclass(value, BaseModel) or value is BaseModel:
            continue
        for field_name, field in value.model_fields.items():
            if field.annotation is SecretStr:
                offenders.append(f"{name}.{field_name}")
    assert offenders == [], f"Response model fields typed as SecretStr: {offenders}"

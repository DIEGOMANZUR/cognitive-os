from __future__ import annotations

import os
from typing import Any, cast

import pytest
from pydantic import SecretStr

from cognitive_os.core.config import Settings
from cognitive_os.core.observability import (
    LANGSMITH_ENV_VARS,
    configure_langsmith,
    disable_langsmith,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in LANGSMITH_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _settings(**overrides: Any) -> Settings:
    """Build a `Settings` whose env_file is shimmed to a test sentinel."""
    base: dict[str, Any] = {
        "langsmith_tracing": True,
        "langsmith_api_key": SecretStr("ls__test-key"),
        "langsmith_project": "cognitive_os_tests",
        "_env_file": None,
    }
    base.update(overrides)
    return cast(Settings, Settings.model_validate(base))


def test_disabled_when_flag_off() -> None:
    info = configure_langsmith(_settings(langsmith_tracing=False))

    assert info["status"] == "disabled"
    assert "LANGSMITH_TRACING" not in os.environ


def test_degraded_when_key_placeholder() -> None:
    info = configure_langsmith(_settings(langsmith_api_key=SecretStr("CHANGEME")))

    assert info["status"] == "degraded"
    assert "LANGSMITH_TRACING" not in os.environ


def test_exports_env_and_handles_unreachable_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the credential check to a host that always fails fast.
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "http://127.0.0.1:1")

    info = configure_langsmith(_settings())

    # Even when the endpoint is unreachable we still exported the env vars
    # so LangChain can pick them up; status surfaces the error to the dashboard.
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "ls__test-key"  # pragma: allowlist secret
    assert os.environ["LANGSMITH_PROJECT"] == "cognitive_os_tests"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert info["status"] == "degraded"
    assert info["project"] == "cognitive_os_tests"


def test_disable_langsmith_clears_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in LANGSMITH_ENV_VARS:
        monkeypatch.setenv(var, "x")

    disable_langsmith()

    for var in LANGSMITH_ENV_VARS:
        assert var not in os.environ

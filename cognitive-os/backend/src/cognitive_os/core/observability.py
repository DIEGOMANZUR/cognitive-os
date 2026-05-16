"""LangSmith observability bootstrap.

`pydantic-settings` reads `.env` into the `Settings` object but does not export
to `os.environ`. The LangChain runtime reads `LANGSMITH_*` from `os.environ`
directly, so we have to re-export them here on boot. Centralising this in one
function (used by both the FastAPI lifespan and the Celery worker) keeps the
behavior consistent and gives us a single place to validate the credential.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

from cognitive_os.core.config import Settings, settings

logger = structlog.get_logger(__name__)

LANGSMITH_ENV_VARS = (
    "LANGSMITH_TRACING",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "LANGSMITH_ENDPOINT",
    # LangChain legacy aliases — set both so old/new releases pick them up.
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_PROJECT",
    "LANGCHAIN_ENDPOINT",
)


def configure_langsmith(app_settings: Settings | None = None) -> dict[str, Any]:
    """Export LangSmith credentials to `os.environ` and verify the API key.

    Returns a status dict suitable for `/health/dashboard`. Idempotent: safe
    to call multiple times. Never raises — credential failures are logged and
    surfaced via the returned `status="degraded"`. Resolves the active
    `Settings` lazily at call time so tests can monkeypatch the module-level
    `settings` without re-binding a default argument.
    """
    if app_settings is None:
        app_settings = settings
    if not app_settings.langsmith_tracing:
        return {
            "status": "disabled",
            "detail": "LANGSMITH_TRACING=false; set to true to enable.",
            "project": app_settings.langsmith_project,
        }
    langsmith_credential = app_settings.langsmith_api_key.get_secret_value().strip()
    if not langsmith_credential or langsmith_credential == "CHANGEME":
        return {
            "status": "degraded",
            "detail": "LANGSMITH_API_KEY missing while tracing is enabled.",
            "project": app_settings.langsmith_project,
        }

    # Export to os.environ so the LangChain runtime's auto-tracing picks it up.
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = langsmith_credential
    os.environ["LANGSMITH_PROJECT"] = app_settings.langsmith_project
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = langsmith_credential
    os.environ["LANGCHAIN_PROJECT"] = app_settings.langsmith_project
    os.environ.setdefault("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    os.environ.setdefault("LANGCHAIN_ENDPOINT", os.environ["LANGSMITH_ENDPOINT"])

    endpoint = os.environ["LANGSMITH_ENDPOINT"].rstrip("/")
    try:
        # Direct authenticated GET to /info. `langsmith.Client.info` swallows
        # connection errors silently so we use httpx for a deterministic probe.
        response = httpx.get(
            f"{endpoint}/info",
            headers={"x-api-key": langsmith_credential},
            timeout=app_settings.http_timeout_seconds,
        )
        response.raise_for_status()
        logger.info("langsmith_ready", project=app_settings.langsmith_project)
        return {
            "status": "ok",
            "project": app_settings.langsmith_project,
            "endpoint": endpoint,
        }
    except Exception as exc:  # noqa: BLE001 - we want the dashboard to see this
        logger.warning(
            "langsmith_unreachable",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return {
            "status": "degraded",
            "detail": f"{type(exc).__name__}: {exc}",
            "project": app_settings.langsmith_project,
        }


def disable_langsmith() -> None:
    """Best-effort cleanup of process env on shutdown."""
    for var in LANGSMITH_ENV_VARS:
        os.environ.pop(var, None)

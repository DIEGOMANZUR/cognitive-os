from __future__ import annotations

import pytest

from cognitive_os.core import health as health_module
from cognitive_os.core.health import ComponentHealth, check_health_dashboard

_CHECKS: tuple[tuple[str, str], ...] = (
    ("_check_postgres", "postgres"),
    ("_check_redis", "redis"),
    ("_check_weaviate", "weaviate"),
    ("_check_neo4j", "neo4j"),
    ("_check_primary_llm", "primary_llm"),
    ("_check_embeddings", "embeddings"),
    ("_check_workers", "workers"),
    ("_check_langsmith", "langsmith"),
    ("_check_voice", "voice"),
    ("_check_maps", "maps"),
    ("_check_calendar", "google_calendar"),
    ("_check_drive", "google_drive"),
    ("_check_webbridge", "kimi_webbridge"),
    ("_check_captcha", "captcha_solver"),
)


def _install_checks(
    monkeypatch: pytest.MonkeyPatch,
    statuses: dict[str, str] | None = None,
) -> None:
    resolved = statuses or {}
    for attr, name in _CHECKS:

        async def check(name: str = name) -> ComponentHealth:
            return ComponentHealth(name=name, status=resolved.get(name, "ok"))

        monkeypatch.setattr(health_module, attr, check)


@pytest.mark.asyncio
async def test_health_dashboard_degrades_on_component_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_checks(monkeypatch, {"redis": "degraded"})

    dashboard = await check_health_dashboard()

    assert dashboard.status == "degraded"
    assert {component.name: component.status for component in dashboard.components}["redis"] == (
        "degraded"
    )


@pytest.mark.asyncio
async def test_health_dashboard_treats_optional_states_as_non_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_checks(
        monkeypatch,
        {
            "voice": "disabled",
            "maps": "ready",
            "google_calendar": "blocked",
            "google_drive": "configured",
        },
    )

    dashboard = await check_health_dashboard()

    assert dashboard.status == "degraded"
    statuses = {component.name: component.status for component in dashboard.components}
    assert statuses["voice"] == "disabled"
    assert statuses["maps"] == "ready"
    assert statuses["google_drive"] == "configured"


@pytest.mark.asyncio
async def test_health_dashboard_check_exception_becomes_sanitized_degraded_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_checks(monkeypatch)

    async def broken_postgres() -> ComponentHealth:
        raise RuntimeError("token=abc123 failed at /home/operator/cognitive-os/token.json")

    monkeypatch.setattr(health_module, "_check_postgres", broken_postgres)

    dashboard = await check_health_dashboard()

    postgres = next(component for component in dashboard.components if component.name == "postgres")
    assert dashboard.status == "degraded"
    assert postgres.status == "degraded"
    assert postgres.detail is not None
    assert "abc123" not in postgres.detail
    assert "/home/operator" not in postgres.detail
    assert "[REDACTED]" in postgres.detail
    assert "[PATH]" in postgres.detail

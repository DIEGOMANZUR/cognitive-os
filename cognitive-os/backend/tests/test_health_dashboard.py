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
    ("_check_mail", "mail"),
    ("_check_mcp", "mcp_client"),
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
async def test_health_dashboard_treats_non_failure_states_as_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_checks(
        monkeypatch,
        {
            "voice": "disabled",
            "maps": "ready",
            "google_drive": "configured",
        },
    )

    dashboard = await check_health_dashboard()

    assert dashboard.status == "ok"
    statuses = {component.name: component.status for component in dashboard.components}
    assert statuses["voice"] == "disabled"
    assert statuses["maps"] == "ready"
    assert statuses["google_drive"] == "configured"


@pytest.mark.asyncio
async def test_health_dashboard_degrades_on_blocked_enabled_integration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_checks(monkeypatch, {"google_calendar": "blocked"})

    dashboard = await check_health_dashboard()

    assert dashboard.status == "degraded"
    statuses = {component.name: component.status for component in dashboard.components}
    assert statuses["google_calendar"] == "blocked"


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


@pytest.mark.asyncio
async def test_health_dashboard_times_out_a_stuck_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_checks(monkeypatch)
    monkeypatch.setattr(health_module.settings, "health_component_timeout_seconds", 0.01)

    async def stuck_postgres() -> ComponentHealth:
        await health_module.asyncio.sleep(10)
        return ComponentHealth(name="postgres", status="ok")

    monkeypatch.setattr(health_module, "_check_postgres", stuck_postgres)

    dashboard = await check_health_dashboard()

    postgres = next(component for component in dashboard.components if component.name == "postgres")
    assert dashboard.status == "degraded"
    assert postgres.status == "degraded"
    assert postgres.detail == "Health check timed out after 0.01s."
    assert postgres.latency_ms is not None
    assert postgres.latency_ms < 500


@pytest.mark.asyncio
async def test_workers_health_reports_registered_tasks_and_consumed_queues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_tasks = set(health_module.celery_app.conf.task_routes.keys())
    expected_queues = {queue.name for queue in health_module.celery_app.conf.task_queues}

    monkeypatch.setattr(
        health_module.celery_app.control,
        "ping",
        lambda timeout: (_ for _ in ()).throw(RuntimeError("ping should not be used")),
    )
    monkeypatch.setattr(
        health_module,
        "_inspect_workers_snapshot",
        lambda: {
            "registered": {"celery@test": sorted(expected_tasks)},
            "active_queues": {
                "celery@test": [{"name": queue_name} for queue_name in sorted(expected_queues)]
            },
            "active": {"celery@test": []},
            "reserved": {"celery@test": []},
            "scheduled": {"celery@test": []},
        },
    )

    component = await health_module._check_workers()

    assert component.status == "ok"
    assert component.metadata["missing_registered_tasks"] == []
    assert component.metadata["missing_queues"] == []
    assert component.metadata["expected_task_count"] == len(expected_tasks)


@pytest.mark.asyncio
async def test_workers_health_degrades_when_task_or_queue_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_tasks = set(health_module.celery_app.conf.task_routes.keys())
    missing_task = "cognitive_os.run_action_request"
    registered = sorted(expected_tasks - {missing_task})

    monkeypatch.setattr(
        health_module.celery_app.control,
        "ping",
        lambda timeout: [{"celery@test": {"ok": "pong", "timeout": timeout}}],
    )
    monkeypatch.setattr(
        health_module,
        "_inspect_workers_snapshot",
        lambda: {
            "registered": {"celery@test": registered},
            "active_queues": {"celery@test": [{"name": "default"}]},
            "active": {"celery@test": [{"id": "active-1"}]},
            "reserved": {"celery@test": []},
            "scheduled": {"celery@test": []},
        },
    )

    component = await health_module._check_workers()

    assert component.status == "degraded"
    assert missing_task in component.metadata["missing_registered_tasks"]
    assert "mail" in component.metadata["missing_queues"]
    assert component.metadata["active_count"] == 1
    assert component.detail is not None
    assert "Missing registered task" in component.detail

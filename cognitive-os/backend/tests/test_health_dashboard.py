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
    ("_check_operational_backlog", "operational_backlog"),
)


def _install_checks(
    monkeypatch: pytest.MonkeyPatch,
    statuses: dict[str, str] | None = None,
) -> None:
    resolved = statuses or {}
    for attr, name in _CHECKS:

        async def check(name: str = name, **_kwargs: object) -> ComponentHealth:
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
async def test_health_dashboard_is_ok_only_when_every_component_is_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ok` overall means every component was verified by a live probe (or is
    honestly off). `disabled`/`ready` count as verified; `ok` does too."""
    _install_checks(
        monkeypatch,
        {
            "voice": "disabled",
            "maps": "ready",
        },
    )

    dashboard = await check_health_dashboard()

    assert dashboard.status == "ok"
    statuses = {component.name: component.status for component in dashboard.components}
    assert statuses["voice"] == "disabled"
    assert statuses["maps"] == "ready"


@pytest.mark.asyncio
async def test_health_dashboard_is_configured_when_any_component_unverified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUDIT-2026-B: a component that is only `configured` (wired, never
    probed live) must NOT paint the dashboard green. The overall verdict is
    `configured` — honest about the fact that nothing was dialled."""
    _install_checks(
        monkeypatch,
        {
            "voice": "disabled",
            "maps": "ready",
            "google_drive": "configured",
        },
    )

    dashboard = await check_health_dashboard()

    assert dashboard.status == "configured"
    statuses = {component.name: component.status for component in dashboard.components}
    assert statuses["google_drive"] == "configured"


@pytest.mark.asyncio
async def test_health_dashboard_degraded_beats_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real failure always wins over a merely-unverified component."""
    _install_checks(
        monkeypatch,
        {"google_drive": "configured", "redis": "degraded"},
    )

    dashboard = await check_health_dashboard()

    assert dashboard.status == "degraded"


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
async def test_primary_llm_configured_without_live_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default (verify_live=False) must NOT dial the provider — it reports
    `configured` so a passive /health poll never burns tokens."""
    monkeypatch.setattr(
        health_module.settings.primary_llm_api_key,
        "get_secret_value",
        lambda: "real-key",
    )

    component = await health_module._check_primary_llm()

    assert component.status == "configured"
    assert "skipped" in (component.detail or "")


@pytest.mark.asyncio
async def test_primary_llm_verify_live_does_a_real_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """verify_live=True must invoke the model and return a verified `ok`."""
    monkeypatch.setattr(
        health_module.settings.primary_llm_api_key,
        "get_secret_value",
        lambda: "real-key",
    )

    class _FakeModel:
        async def ainvoke(self, _prompt: object) -> object:
            return type("Result", (), {"content": "pong"})()

    from cognitive_os.agents import llm_factory

    monkeypatch.setattr(llm_factory, "create_primary_chat_model", lambda: _FakeModel())

    component = await health_module._check_primary_llm(verify_live=True)

    assert component.status == "ok"
    assert component.latency_ms is not None


@pytest.mark.asyncio
async def test_primary_llm_verify_live_degrades_on_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        health_module.settings.primary_llm_api_key,
        "get_secret_value",
        lambda: "real-key",
    )

    def _boom() -> object:
        raise RuntimeError("provider down")

    from cognitive_os.agents import llm_factory

    monkeypatch.setattr(llm_factory, "create_primary_chat_model", _boom)

    component = await health_module._check_primary_llm(verify_live=True)

    assert component.status == "degraded"


@pytest.mark.asyncio
async def test_mail_verify_live_probes_imap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """verify_live=True on mail must run the IMAP probe; default must not."""
    monkeypatch.setattr(health_module.settings, "mail_enabled", True)
    monkeypatch.setattr(health_module.settings, "mail_godaddy_enabled", True)
    monkeypatch.setattr(health_module.settings, "mail_godaddy_username", "ops@example.com")
    monkeypatch.setattr(
        health_module.settings.mail_godaddy_password,
        "get_secret_value",
        lambda: "secret",
    )

    probed: list[bool] = []

    def _fake_probe() -> bool:
        probed.append(True)
        return True

    monkeypatch.setattr(health_module, "_probe_godaddy_imap", _fake_probe)

    passive = await health_module._check_mail()
    assert passive.status == "configured"
    assert probed == []

    live = await health_module._check_mail(verify_live=True)
    assert live.status == "ok"
    assert probed == [True]


@pytest.mark.asyncio
async def test_check_health_dashboard_verify_live_propagates_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """check_health_dashboard(verify_live=True) must pass the flag to the
    spend-bearing checks so the operator's /health/verify is a real probe."""
    seen: dict[str, bool] = {}

    async def _spy_llm(*, verify_live: bool = False) -> ComponentHealth:
        seen["primary_llm"] = verify_live
        return ComponentHealth(name="primary_llm", status="ok")

    async def _spy_embeddings(*, verify_live: bool = False) -> ComponentHealth:
        seen["embeddings"] = verify_live
        return ComponentHealth(name="embeddings", status="ok")

    async def _spy_mail(*, verify_live: bool = False) -> ComponentHealth:
        seen["mail"] = verify_live
        return ComponentHealth(name="mail", status="ok")

    _install_checks(monkeypatch)
    monkeypatch.setattr(health_module, "_check_primary_llm", _spy_llm)
    monkeypatch.setattr(health_module, "_check_embeddings", _spy_embeddings)
    monkeypatch.setattr(health_module, "_check_mail", _spy_mail)

    await check_health_dashboard(verify_live=True)

    assert seen == {"primary_llm": True, "embeddings": True, "mail": True}


class _FakeBacklogSession:
    """Returns the 5 scalar() results _check_operational_backlog asks for, in
    order: approvals_pending, approvals_stale, jobs_stale,
    action_requests_stuck, last_reap_completed."""

    def __init__(self, values: list[object]) -> None:
        self._values = list(values)

    async def __aenter__(self) -> _FakeBacklogSession:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def scalar(self, _stmt: object) -> object:
        return self._values.pop(0)


@pytest.mark.asyncio
async def test_operational_backlog_ok_when_within_thresholds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime, timedelta

    recent_reap = datetime.now(UTC) - timedelta(minutes=4)
    monkeypatch.setattr(
        health_module,
        "async_session_factory",
        lambda: _FakeBacklogSession([3, 0, 0, 0, recent_reap]),
    )

    component = await health_module._check_operational_backlog()

    assert component.status == "ok"
    assert component.metadata["approvals_pending"] == 3
    assert component.metadata["approvals_stale"] == 0
    assert component.metadata["beat_lag_minutes"] is not None
    assert component.metadata["beat_lag_minutes"] < 10


@pytest.mark.asyncio
async def test_operational_backlog_degrades_on_stale_approvals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    monkeypatch.setattr(
        health_module,
        "async_session_factory",
        lambda: _FakeBacklogSession([12, 4, 0, 0, datetime.now(UTC)]),
    )

    component = await health_module._check_operational_backlog()

    assert component.status == "degraded"
    assert component.metadata["approvals_stale"] == 4
    assert component.detail is not None
    assert "approval" in component.detail


@pytest.mark.asyncio
async def test_operational_backlog_degrades_on_dead_beat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No reaper completed in hours → Celery beat is effectively dead and the
    backlog will grow unnoticed. The dashboard must say so."""
    from datetime import UTC, datetime, timedelta

    stale_reap = datetime.now(UTC) - timedelta(hours=5)
    monkeypatch.setattr(
        health_module,
        "async_session_factory",
        lambda: _FakeBacklogSession([0, 0, 0, 0, stale_reap]),
    )

    component = await health_module._check_operational_backlog()

    assert component.status == "degraded"
    assert component.detail is not None
    assert "beat" in component.detail.lower()


@pytest.mark.asyncio
async def test_operational_backlog_ok_when_no_reaper_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh install with no reaper history (last_reap=None) must NOT degrade
    — absence of history is not a failure."""
    monkeypatch.setattr(
        health_module,
        "async_session_factory",
        lambda: _FakeBacklogSession([0, 0, 0, 0, None]),
    )

    component = await health_module._check_operational_backlog()

    assert component.status == "ok"
    assert component.metadata["beat_lag_minutes"] is None


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

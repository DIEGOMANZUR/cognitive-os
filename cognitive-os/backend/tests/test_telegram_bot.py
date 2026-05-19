from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

import cognitive_os.actions.service as action_service_module
import cognitive_os.api.app as api_app_module
import cognitive_os.workers.tasks as worker_tasks
from cognitive_os.integrations import telegram_bot


class DummyBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str, bool]] = []

    def send(self, chat_id: int, text: str, *, markdown: bool = True) -> None:
        self.sent.append((chat_id, text, markdown))


def test_approve_action_request_from_telegram_queues_and_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval_id = UUID("11111111-1111-1111-1111-111111111111")
    action_request_id = UUID("22222222-2222-2222-2222-222222222222")
    job_id = UUID("33333333-3333-3333-3333-333333333333")
    captured: dict[str, Any] = {}

    async def fake_decide_approval(
        approval_id_arg: UUID,
        *,
        status_value: str,
        approver_user_id: str,
        payload_resolver: object | None = None,
        **_kwargs: object,
    ) -> object:
        captured["approval_id"] = approval_id_arg
        captured["status_value"] = status_value
        captured["approver_user_id"] = approver_user_id
        captured["payload_resolver"] = payload_resolver
        return SimpleNamespace(
            approval=SimpleNamespace(
                requested_action=f"execute_action_request:{action_request_id}"
            ),
            openshell_dispatch=None,
            code_build_job_id=None,
        )

    class FakeActionRequestService:
        async def record_action_dispatch_event(
            self,
            *,
            job_id: UUID,
            action_request_id: UUID,
            event_type: str,
            status: str,
            message: str,
            metadata_json: dict[str, object] | None = None,
        ) -> None:
            captured["dispatch_event"] = {
                "job_id": job_id,
                "action_request_id": action_request_id,
                "event_type": event_type,
                "status": status,
                "message": message,
                "metadata_json": metadata_json or {},
            }

        async def queue_approved_action_request(self, action_request_id_arg: UUID) -> object:
            captured["queued_action_request_id"] = action_request_id_arg
            return SimpleNamespace(id=action_request_id_arg, job_id=job_id, status="queued")

        async def reserve_action_dispatch(self, action_request_id_arg: UUID) -> object:
            captured["reserved_action_request_id"] = action_request_id_arg
            return action_service_module.ActionDispatchReservation(
                action_request=SimpleNamespace(
                    id=action_request_id_arg,
                    job_id=job_id,
                    status="queued",
                ),
                should_dispatch=True,
            )

    dispatched: list[dict[str, Any]] = []

    def fake_apply_async(*, args: list[str], queue: str) -> None:
        dispatched.append({"args": args, "queue": queue})

    monkeypatch.setattr(action_service_module, "decide_approval", fake_decide_approval)
    monkeypatch.setattr(action_service_module, "ActionRequestService", FakeActionRequestService)
    monkeypatch.setattr(worker_tasks.run_action_request_task_async, "apply_async", fake_apply_async)

    bot = DummyBot()
    telegram_bot.cmd_approve(bot, 4242, str(approval_id))

    assert captured["approval_id"] == approval_id
    assert captured["status_value"] == "approved"
    assert captured["approver_user_id"] == "telegram:4242"
    assert captured["queued_action_request_id"] == action_request_id
    assert captured["reserved_action_request_id"] == action_request_id
    assert dispatched == [
        {
            "args": [str(action_request_id), str(job_id)],
            "queue": "agent_longrun",
        }
    ]
    assert captured["dispatch_event"] == {
        "job_id": job_id,
        "action_request_id": action_request_id,
        "event_type": "action_request_dispatch_submitted",
        "status": "queued",
        "message": "Telegram submitted action request to Celery",
        "metadata_json": {"queue": "agent_longrun", "surface": "telegram"},
    }
    assert "despachado en `agent_longrun`" in bot.sent[-1][1]


def test_telegram_openshell_payload_resolver_is_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval_id = UUID("44444444-4444-4444-4444-444444444444")
    resolver_calls: list[object] = []

    def fake_payload_resolver(job: object) -> dict[str, Any]:
        resolver_calls.append(job)
        return {"task_id": "demo"}

    async def fake_decide_approval(
        approval_id_arg: UUID,
        *,
        payload_resolver: Any,
        **_kwargs: object,
    ) -> object:
        assert approval_id_arg == approval_id
        assert payload_resolver(SimpleNamespace(job_type="openshell_sandbox")) == {
            "task_id": "demo"
        }
        return SimpleNamespace(
            approval=SimpleNamespace(requested_action="run_openshell:demo"),
            openshell_dispatch=None,
            code_build_job_id=None,
        )

    monkeypatch.setattr(api_app_module, "_openshell_task_payload_from_job", fake_payload_resolver)
    monkeypatch.setattr(action_service_module, "decide_approval", fake_decide_approval)

    bot = DummyBot()
    telegram_bot.cmd_approve(bot, 4242, str(approval_id))

    assert len(resolver_calls) == 1
    assert bot.sent[-1][1].endswith("→ approved")


@pytest.mark.asyncio
async def test_resolve_approval_short_prefix_requires_unique_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    match = UUID("aaaaaaaa-1111-1111-1111-111111111111")

    class FakeScalars:
        def __init__(self, values: list[UUID]) -> None:
            self.values = values

        def all(self) -> list[UUID]:
            return self.values

    class FakeResult:
        def __init__(self, values: list[UUID]) -> None:
            self.values = values

        def scalars(self) -> FakeScalars:
            return FakeScalars(self.values)

    class FakeSession:
        def __init__(self, values: list[UUID]) -> None:
            self.values = values

        async def execute(self, _stmt: object) -> FakeResult:
            return FakeResult(self.values)

    @asynccontextmanager
    async def unique_session_scope():
        yield FakeSession([match])

    monkeypatch.setattr(telegram_bot, "session_scope", unique_session_scope)
    resolved, error = await telegram_bot._resolve_approval_id("aaaaaaaa")

    assert resolved == match
    assert error is None

    @asynccontextmanager
    async def ambiguous_session_scope():
        yield FakeSession(
            [
                UUID("bbbbbbbb-1111-1111-1111-111111111111"),
                UUID("bbbbbbbb-2222-2222-2222-222222222222"),
            ]
        )

    monkeypatch.setattr(telegram_bot, "session_scope", ambiguous_session_scope)
    resolved, error = await telegram_bot._resolve_approval_id("bbbbbbbb")

    assert resolved is None
    assert error == "prefijo ambiguo; usá más caracteres del approval_id"


@pytest.mark.asyncio
async def test_resolve_approval_rejects_too_short_prefix_without_db() -> None:
    resolved, error = await telegram_bot._resolve_approval_id("abc")

    assert resolved is None
    assert error == "prefijo demasiado corto; usá al menos 4 caracteres"


@pytest.mark.asyncio
async def test_resolve_approval_rejects_sql_wildcard_prefix_without_db() -> None:
    resolved, error = await telegram_bot._resolve_approval_id("aaaa%")

    assert resolved is None
    assert error == "id inválido"


def test_cmd_job_rejects_sql_wildcard_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/job %` (or `/job _`) must NOT match arbitrary jobs via LIKE wildcards.

    `_resolve_approval_id` already had this whitelist; `cmd_job` had the same
    `ilike(f"{prefix}%")` pattern but was missing it. Keep both surfaces in sync.
    """
    queried: list[str] = []

    @asynccontextmanager
    async def tracking_session_scope() -> Any:
        class _Session:
            async def get(self, *_a: Any, **_kw: Any) -> Any:
                raise ValueError("not a uuid")  # force the prefix branch

            async def execute(self, *_a: Any, **_kw: Any) -> Any:
                queried.append("hit_db")
                raise AssertionError("must not query DB with wildcard prefix")

        yield _Session()

    monkeypatch.setattr(telegram_bot, "session_scope", tracking_session_scope)
    bot = DummyBot()
    telegram_bot.cmd_job(bot, 1, "%")
    assert queried == []
    assert bot.sent and "no encontrado" in bot.sent[-1][1].lower()

    bot = DummyBot()
    telegram_bot.cmd_job(bot, 1, "abc_def")  # contains '_' wildcard
    assert queried == []
    assert bot.sent and "no encontrado" in bot.sent[-1][1].lower()


# -- /maps /calendar /drive /freebusy gating ---------------------------------


def test_cmd_maps_requires_separator() -> None:
    bot = DummyBot()
    telegram_bot.cmd_maps(bot, 1, "Buenos Aires")
    assert bot.sent and "origen | destino" in bot.sent[-1][1]


def test_cmd_maps_reports_disabled_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from cognitive_os.actions import maps as maps_module

    class _Status:
        status = "disabled"
        reason = "ENABLE_MAPS_ROUTING is false."

    class _FakeMapsService:
        def status(self) -> _Status:
            return _Status()

    monkeypatch.setattr(maps_module, "MapsService", _FakeMapsService)
    bot = DummyBot()
    telegram_bot.cmd_maps(bot, 1, "A | B")
    assert "Maps:" in bot.sent[-1][1]


def test_cmd_calendar_blocked_when_status_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    from cognitive_os.actions import calendar as calendar_module

    class _Status:
        status = "blocked"
        reason = "No token.json found"

    class _FakeCalendarService:
        def status(self) -> _Status:
            return _Status()

    monkeypatch.setattr(calendar_module, "CalendarService", _FakeCalendarService)
    bot = DummyBot()
    telegram_bot.cmd_calendar(bot, 1, "")
    assert "Calendar:" in bot.sent[-1][1]


def test_cmd_drive_requires_query() -> None:
    bot = DummyBot()
    telegram_bot.cmd_drive(bot, 1, "")
    assert "Uso:" in bot.sent[-1][1]


def test_cmd_mail_respects_disable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telegram_bot.settings, "mail_enabled", False)
    bot = DummyBot()
    telegram_bot.cmd_mail(bot, 1, "")
    assert "MAIL_ENABLED=false" in bot.sent[-1][1]


def test_cmd_sandbox_respects_disable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telegram_bot.settings, "enable_openshell_sandbox", False)
    bot = DummyBot()
    telegram_bot.cmd_sandbox(bot, 1, "")
    assert "ENABLE_OPENSHELL_SANDBOX=false" in bot.sent[-1][1]


def test_cmd_capabilities_lists_flags() -> None:
    bot = DummyBot()
    telegram_bot.cmd_capabilities(bot, 1, "")
    text = bot.sent[-1][1]
    for token in (
        "browser_automation",
        "google_calendar",
        "google_drive",
        "godaddy_dns",
        "research_orchestrator",
    ):
        assert token in text


def test_parse_int_arg_clamps_to_bounds() -> None:
    assert telegram_bot._parse_int_arg("", default=10) == 10
    assert telegram_bot._parse_int_arg("3", default=10) == 3
    assert telegram_bot._parse_int_arg("999", default=10, high=20) == 20
    assert telegram_bot._parse_int_arg("not-a-number", default=7) == 7
    assert telegram_bot._parse_int_arg("0", default=7, low=2, high=8) == 2


def test_every_view_has_at_least_one_slash_command() -> None:
    """If the UI gains a domain, Telegram must too — keeps surfaces in sync."""
    expected = {
        "health",
        "stats",
        "config",
        "agents",
        "skills",
        "memory",
        "jobs",
        "approvals",
        "threads",
        "chat",
        "ingest",
        "tasks",
        "notes",
        "gmaildigest",
        "runs",
        "maps",
        "calendar",
        "freebusy",
        "drive",
        "documents",
        "audit",
        "mail",
        "research",
        "codebuild",
        "sandbox",
        "capabilities",
    }
    registered = set(telegram_bot.COMMAND_HANDLERS.keys())
    missing = expected - registered
    assert not missing, f"Missing slash commands: {sorted(missing)}"

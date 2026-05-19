from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

import cognitive_os.workers.tasks as tasks_module
from cognitive_os.actions.schemas import ActionRequestView


def _view(status: str, *, action_request_id: UUID, job_id: UUID) -> ActionRequestView:
    now = datetime.now(UTC)
    return ActionRequestView(
        id=action_request_id,
        action_type="browser_preview",
        status=status,  # type: ignore[arg-type]
        requested_by="operator-1",
        approval_id=None,
        job_id=job_id,
        payload_redacted={},
        preview={},
        result={},
        error=None,
        created_at=now,
        updated_at=now,
    )


def test_run_action_request_duplicate_running_does_not_mark_job_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action_request_id = UUID("11111111-1111-1111-1111-111111111111")
    job_id = UUID("22222222-2222-2222-2222-222222222222")
    calls: list[dict[str, Any]] = []

    class FakeActionRequestService:
        async def execute_action_request(self, received_id: UUID) -> ActionRequestView:
            assert received_id == action_request_id
            return _view("running", action_request_id=action_request_id, job_id=job_id)

    async def fake_update_job(
        received_job_id: UUID,
        *,
        status: str,
        progress: int | None = None,
        event_type: str,
        message: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> None:
        calls.append(
            {
                "job_id": received_job_id,
                "status": status,
                "progress": progress,
                "event_type": event_type,
                "message": message,
                "metadata_json": metadata_json or {},
            }
        )

    async def fake_read_job_status(_job_id: UUID) -> str | None:
        return "queued"

    monkeypatch.setattr(tasks_module, "ActionRequestService", FakeActionRequestService)
    monkeypatch.setattr(tasks_module, "_update_job", fake_update_job)
    monkeypatch.setattr(tasks_module, "_read_job_status", fake_read_job_status)

    result = tasks_module.run_action_request_task_async.run(
        str(action_request_id),
        str(job_id),
    )

    assert result["status"] == "running"
    assert [call["status"] for call in calls] == ["running", "running"]
    assert calls[-1]["event_type"] == "action_request_not_executed"
    assert all(call["status"] != "failed" for call in calls)


def test_run_action_request_preserves_cancelled_terminal_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action_request_id = UUID("33333333-3333-3333-3333-333333333333")
    job_id = UUID("44444444-4444-4444-4444-444444444444")
    calls: list[dict[str, Any]] = []

    class FakeActionRequestService:
        async def execute_action_request(self, received_id: UUID) -> ActionRequestView:
            assert received_id == action_request_id
            return _view("cancelled", action_request_id=action_request_id, job_id=job_id)

    async def fake_update_job(
        received_job_id: UUID,
        *,
        status: str,
        progress: int | None = None,
        event_type: str,
        message: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> None:
        del message, metadata_json
        calls.append(
            {
                "job_id": received_job_id,
                "status": status,
                "progress": progress,
                "event_type": event_type,
            }
        )

    async def fake_read_job_status(_job_id: UUID) -> str | None:
        return "queued"

    monkeypatch.setattr(tasks_module, "ActionRequestService", FakeActionRequestService)
    monkeypatch.setattr(tasks_module, "_update_job", fake_update_job)
    monkeypatch.setattr(tasks_module, "_read_job_status", fake_read_job_status)

    result = tasks_module.run_action_request_task_async.run(
        str(action_request_id),
        str(job_id),
    )

    assert result["status"] == "cancelled"
    assert calls[-1]["status"] == "cancelled"
    assert calls[-1]["event_type"] == "action_request_finished"


def test_run_action_request_short_circuits_when_job_already_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Celery retries on already-terminal jobs must not overwrite the outcome."""
    action_request_id = UUID("55555555-5555-5555-5555-555555555555")
    job_id = UUID("66666666-6666-6666-6666-666666666666")
    calls: list[dict[str, Any]] = []
    service_calls: list[UUID] = []

    class FakeActionRequestService:
        async def execute_action_request(
            self, received_id: UUID
        ) -> ActionRequestView:  # pragma: no cover - must not be reached
            service_calls.append(received_id)
            return _view("running", action_request_id=action_request_id, job_id=job_id)

    async def fake_update_job(
        *args: Any, **kwargs: Any
    ) -> None:  # pragma: no cover - must not be reached
        calls.append({"args": args, "kwargs": kwargs})

    async def fake_read_job_status(_job_id: UUID) -> str | None:
        return "completed"

    monkeypatch.setattr(tasks_module, "ActionRequestService", FakeActionRequestService)
    monkeypatch.setattr(tasks_module, "_update_job", fake_update_job)
    monkeypatch.setattr(tasks_module, "_read_job_status", fake_read_job_status)

    result = tasks_module.run_action_request_task_async.run(
        str(action_request_id),
        str(job_id),
    )

    assert result["skipped"] is True
    assert result["status"] == "completed"
    assert service_calls == []
    assert calls == []


def test_run_action_request_short_circuits_when_job_already_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Genuine duplicate (Job AND ActionRequest already running): short-circuit."""
    action_request_id = UUID("77777777-7777-7777-7777-777777777777")
    job_id = UUID("88888888-8888-8888-8888-888888888888")
    calls: list[dict[str, Any]] = []
    service_calls: list[UUID] = []

    class FakeActionRequestService:
        async def execute_action_request(
            self, received_id: UUID
        ) -> ActionRequestView:  # pragma: no cover - must not be reached
            service_calls.append(received_id)
            return _view("running", action_request_id=action_request_id, job_id=job_id)

    async def fake_update_job(
        *args: Any, **kwargs: Any
    ) -> None:  # pragma: no cover - must not be reached
        calls.append({"args": args, "kwargs": kwargs})

    async def fake_read_job_status(_job_id: UUID) -> str | None:
        return "running"

    async def fake_read_ar_status(_ar_id: UUID) -> str | None:
        return "running"

    monkeypatch.setattr(tasks_module, "ActionRequestService", FakeActionRequestService)
    monkeypatch.setattr(tasks_module, "_update_job", fake_update_job)
    monkeypatch.setattr(tasks_module, "_read_job_status", fake_read_job_status)
    monkeypatch.setattr(tasks_module, "_read_action_request_status", fake_read_ar_status)

    result = tasks_module.run_action_request_task_async.run(
        str(action_request_id),
        str(job_id),
    )

    assert result["skipped"] is True
    assert result["status"] == "running"
    assert result["ar_status"] == "running"
    assert "already running" in result["reason"]
    assert service_calls == []
    assert calls == []


def test_run_action_request_proceeds_when_job_running_but_ar_still_queued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (GPT-5.5 P1): crash window Job→running before AR→running.

    If the previous attempt crashed after setting Job=running but before
    ActionRequestService flipped AR queued→running, a Celery retry that
    only looked at Job.status would short-circuit and strand the AR
    forever. The worker must inspect the ActionRequest itself and
    proceed when it's still queued/pending. `execute_action_request` is
    atomic (FOR UPDATE, only promotes from queued), so this is safe.
    """
    action_request_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    job_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    service_calls: list[UUID] = []

    class FakeActionRequestService:
        async def execute_action_request(self, received_id: UUID) -> ActionRequestView:
            service_calls.append(received_id)
            return _view("completed", action_request_id=action_request_id, job_id=job_id)

    async def fake_update_job(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def fake_read_job_status(_job_id: UUID) -> str | None:
        return "running"  # crashed previous attempt left it as running

    async def fake_read_ar_status(_ar_id: UUID) -> str | None:
        return "queued"  # AR never got promoted: must proceed

    monkeypatch.setattr(tasks_module, "ActionRequestService", FakeActionRequestService)
    monkeypatch.setattr(tasks_module, "_update_job", fake_update_job)
    monkeypatch.setattr(tasks_module, "_read_job_status", fake_read_job_status)
    monkeypatch.setattr(tasks_module, "_read_action_request_status", fake_read_ar_status)

    result = tasks_module.run_action_request_task_async.run(
        str(action_request_id),
        str(job_id),
    )

    assert result.get("skipped") is not True
    assert service_calls == [action_request_id]
    assert result["status"] == "completed"


# -- Fase 69 P0.4 — Code Director atomic dispatch reservation -----------------


def test_run_code_build_skips_when_reservation_finds_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two workers receive the same dispatch; the second finds `running` after
    the first claimed the job and must skip without invoking the service.

    Models `_reserve_code_build_job` returning ``("skip", "running")``.
    """
    job_id = UUID("33333333-3333-3333-3333-333333333333")
    service_calls: list[UUID] = []

    class FakeCodeDirectorService:
        async def run_build(self, received_id: UUID) -> Any:
            service_calls.append(received_id)
            raise AssertionError("run_build must not be called when reservation skips")

    async def fake_reserve(_job_id: UUID) -> tuple[str, str | None]:
        assert _job_id == job_id
        return ("skip", "running")

    monkeypatch.setattr(
        "cognitive_os.code_director.service.CodeDirectorService",
        FakeCodeDirectorService,
    )
    monkeypatch.setattr(tasks_module, "_reserve_code_build_job", fake_reserve)

    result = tasks_module.run_code_build_task_async.run(str(job_id))

    assert service_calls == []
    assert result["skipped"] is True
    assert result["status"] == "running"
    assert "Duplicate dispatch" in result["reason"]


def test_run_code_build_proceeds_when_reservation_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the atomic UPDATE succeeds (status went queued→running) the worker
    must run the build exactly once. Verifies the happy path."""
    from pydantic import BaseModel  # noqa: PLC0415

    class _BuildResult(BaseModel):
        job_id: UUID
        status: str

    job_id = UUID("44444444-4444-4444-4444-444444444444")
    service_calls: list[UUID] = []

    class FakeCodeDirectorService:
        async def run_build(self, received_id: UUID) -> _BuildResult:
            service_calls.append(received_id)
            return _BuildResult(job_id=received_id, status="completed")

    async def fake_reserve(_job_id: UUID) -> tuple[str, str | None]:
        return ("claimed", "queued")

    monkeypatch.setattr(
        "cognitive_os.code_director.service.CodeDirectorService",
        FakeCodeDirectorService,
    )
    monkeypatch.setattr(tasks_module, "_reserve_code_build_job", fake_reserve)

    result = tasks_module.run_code_build_task_async.run(str(job_id))

    assert service_calls == [job_id]
    assert result["status"] == "completed"
    assert result.get("skipped") is not True

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

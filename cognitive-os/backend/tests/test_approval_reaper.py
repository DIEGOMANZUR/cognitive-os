"""Regression tests for `ActionRequestService.reap_stale_pending_approvals`.

The reaper closes a real commercial risk: a pending HumanApproval that lives
forever could be decided long after the context that created it is stale,
firing an obsolete external action.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

import cognitive_os.actions.service as action_service_module
from cognitive_os.actions.service import ActionRequestService
from cognitive_os.core.config import Settings
from cognitive_os.db.models import ActionRequest, AuditEvent, HumanApproval, Job, JobEvent


class _FakeSession:
    def __init__(
        self,
        approvals: list[HumanApproval],
        jobs: dict[UUID, Job],
        action_requests: dict[UUID, ActionRequest],
    ) -> None:
        self._approvals = approvals
        self._jobs = jobs
        self._action_requests = action_requests
        self.added: list[Any] = []

    async def execute(self, stmt: object) -> Any:  # noqa: ARG002
        # Heuristic: the reaper issues two kinds of queries — a HumanApproval
        # bulk select and an ActionRequest lookup by approval_id.
        target_text = str(stmt).lower()
        if "human_approvals" in target_text and "action_requests" not in target_text:

            class _R:
                @staticmethod
                def scalars() -> Any:
                    class _S:
                        @staticmethod
                        def all() -> list[HumanApproval]:
                            return list(self._approvals)

                    return _S()

            return _R()

        class _R2:
            @staticmethod
            def scalar_one_or_none() -> ActionRequest | None:
                # Single approval per reaper iteration is enough for the test:
                # return the only matching ActionRequest if any.
                if self._action_requests:
                    return next(iter(self._action_requests.values()))
                return None

        return _R2()

    async def get(self, model: type[object], obj_id: UUID) -> object | None:
        if model is Job:
            return self._jobs.get(obj_id)
        return None

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_reaper_expires_pending_approvals_and_cascades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(hours=72)
    approval_id = uuid4()
    job_id = uuid4()
    action_request_id = uuid4()

    approval = HumanApproval(
        id=approval_id,
        status="pending",
        action="execute_action_request",
        requested_action=f"execute_action_request:{action_request_id}",
        args_redacted={},
        requested_by="operator-1",
        job_id=job_id,
        created_at=old,
        updated_at=old,
    )
    job = Job(
        id=job_id,
        job_type="external_action",
        status="waiting_approval",
        progress=0,
        metadata_json={},
        created_at=old,
        updated_at=old,
    )
    action_request = ActionRequest(
        id=action_request_id,
        action_type="computer_organize",
        status="pending_approval",
        requested_by="operator-1",
        approval_id=approval_id,
        job_id=job_id,
        payload_redacted={},
        payload_executable={},
        preview={},
        result={},
        created_at=old,
        updated_at=old,
    )

    fake = _FakeSession([approval], {job_id: job}, {action_request_id: action_request})

    @asynccontextmanager
    async def fake_session_scope():
        yield fake

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)

    reaped = await ActionRequestService(
        Settings(approval_pending_max_hours=48)
    ).reap_stale_pending_approvals()

    assert reaped == 1
    assert approval.status == "expired"
    assert approval.decided_at is not None
    assert job.status == "rejected"
    assert job.progress == 100
    assert action_request.status == "rejected"
    assert action_request.error == "Approval expired before decision"
    assert any(
        isinstance(item, JobEvent) and item.event_type == "approval_expired" for item in fake.added
    )
    assert any(
        isinstance(item, AuditEvent) and item.action == "approval.expired" for item in fake.added
    )

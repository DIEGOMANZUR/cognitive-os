"""Regression for the shared `actions.service.decide_approval` helper.

Both the REST endpoint (`/approvals/{id}/{approve|reject}`) and the Telegram
bot now go through this helper, so the same cascade-to-Job, four-eyes guard
and AuditEvent emission apply to both surfaces.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

import pytest

import cognitive_os.actions.service as action_service_module
from cognitive_os.actions.service import (
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
    ApprovalSelfDecisionError,
    decide_approval,
)
from cognitive_os.db.models import ActionRequest, AuditEvent, HumanApproval, Job, JobEvent


@pytest.mark.asyncio
async def test_decide_approval_rejected_cascades_to_job_and_action_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    approval_id = UUID("11111111-1111-1111-1111-111111111111")
    job_id = UUID("22222222-2222-2222-2222-222222222222")
    action_request_id = UUID("33333333-3333-3333-3333-333333333333")
    approval = HumanApproval(
        id=approval_id,
        status="pending",
        action="execute_action_request",
        requested_action=f"execute_action_request:{action_request_id}",
        args_redacted={},
        requested_by="operator",
        job_id=job_id,
        created_at=now,
        updated_at=now,
    )
    job = Job(
        id=job_id,
        job_type="external_action",
        status="waiting_approval",
        progress=0,
        metadata_json={},
        created_at=now,
        updated_at=now,
    )
    action_request = ActionRequest(
        id=action_request_id,
        action_type="computer_organize",
        status="pending_approval",
        requested_by="operator",
        approval_id=approval_id,
        job_id=job_id,
        payload_redacted={},
        payload_executable={},
        preview={},
        result={},
        created_at=now,
        updated_at=now,
    )
    added: list[object] = []

    class FakeSession:
        async def get(self, model: type[object], obj_id: UUID) -> object | None:
            if model is HumanApproval:
                return approval
            if model is Job:
                return job
            return None

        async def execute(self, _stmt: object) -> object:
            class _R:
                @staticmethod
                def scalar_one_or_none() -> ActionRequest:
                    return action_request

            return _R()

        def add(self, obj: object) -> None:
            added.append(obj)

        async def flush(self) -> None:
            return None

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)

    result = await decide_approval(
        approval_id,
        status_value="rejected",
        approver_user_id="telegram",
    )

    assert result.approval.status == "rejected"
    assert result.approval.approver_user_id == "telegram"
    assert result.openshell_dispatch is None
    assert job.status == "rejected"
    assert action_request.status == "rejected"
    assert action_request.error == "Human approval rejected"
    assert any(
        isinstance(item, JobEvent) and item.event_type == "approval_rejected" for item in added
    )
    audit_events = [item for item in added if isinstance(item, AuditEvent)]
    assert len(audit_events) == 1
    assert audit_events[0].action == "approval.rejected"
    assert audit_events[0].actor_id == "telegram"


@pytest.mark.asyncio
async def test_decide_approval_self_decision_blocked_by_four_eyes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    approval_id = UUID("44444444-4444-4444-4444-444444444444")
    approval = HumanApproval(
        id=approval_id,
        status="pending",
        action="execute_action_request",
        requested_action="execute_action_request:demo",
        args_redacted={},
        requested_by="telegram",
        created_at=now,
        updated_at=now,
    )

    class FakeSession:
        async def get(self, model: type[object], obj_id: UUID) -> object | None:
            return approval if model is HumanApproval else None

        def add(self, _obj: object) -> None:
            raise AssertionError("must not mutate state on self-decision")

        async def flush(self) -> None:
            raise AssertionError("must not flush on self-decision")

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(action_service_module.settings, "approval_require_four_eyes", True)

    with pytest.raises(ApprovalSelfDecisionError):
        await decide_approval(
            approval_id,
            status_value="approved",
            approver_user_id="telegram",
        )

    assert approval.status == "pending"


@pytest.mark.asyncio
async def test_decide_approval_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSession:
        async def get(self, _model: type[object], _obj_id: UUID) -> object | None:
            return None

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)

    with pytest.raises(ApprovalNotFoundError):
        await decide_approval(
            UUID("55555555-5555-5555-5555-555555555555"),
            status_value="approved",
            approver_user_id="telegram",
        )


@pytest.mark.asyncio
async def test_decide_approval_already_decided(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    approval_id = UUID("66666666-6666-6666-6666-666666666666")
    approval = HumanApproval(
        id=approval_id,
        status="approved",
        action="execute_action_request",
        requested_action="execute_action_request:demo",
        args_redacted={},
        requested_by="operator",
        created_at=now,
        updated_at=now,
    )

    class FakeSession:
        async def get(self, model: type[object], _obj_id: UUID) -> object | None:
            return approval if model is HumanApproval else None

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)

    with pytest.raises(ApprovalAlreadyDecidedError) as exc_info:
        await decide_approval(
            approval_id,
            status_value="approved",
            approver_user_id="telegram",
        )
    assert exc_info.value.current_status == "approved"

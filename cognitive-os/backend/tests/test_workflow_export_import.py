"""Regression for `workflow.v1` export / import on ActionRequests.

The contract is the second of two ideas distilled from the Eko framework
review: operators can serialize an approved plan, edit/version-control it
and re-submit. The importer routes through the same `create_*_request`
carriles so all guardrails stay in place.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest

import cognitive_os.actions.service as action_service_module
import cognitive_os.api.app as api_app
from cognitive_os.actions.service import ActionRequestService
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.db.models import ActionRequest


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


@pytest.mark.asyncio
async def test_export_workflow_returns_redacted_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    row = ActionRequest(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        action_type="computer_organize",
        status="pending_approval",
        requested_by="operator-1",
        approval_id=UUID("22222222-2222-2222-2222-222222222222"),
        job_id=UUID("33333333-3333-3333-3333-333333333333"),
        idempotency_key="key",
        payload_redacted={"root_path": "/tmp", "secret_key": "[REDACTED]"},
        payload_executable={},
        preview={"status": "ok", "operations": []},
        result={},
        created_at=now,
        updated_at=now,
    )

    class FakeSession:
        async def get(self, model: type[object], obj_id: UUID) -> object | None:
            assert model is ActionRequest
            assert obj_id == row.id
            return row

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)

    document = await ActionRequestService().export_workflow(row.id, exported_by="op-1")

    assert document is not None
    assert document.workflow_version == "1.0"
    assert document.action_type == "computer_organize"
    assert document.payload == row.payload_redacted
    assert document.preview == row.preview
    assert document.source is not None
    assert document.source.exported_by == "op-1"
    assert document.source.source_action_request_id == row.id


@pytest.mark.asyncio
async def test_export_workflow_rejects_non_exportable_action_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    row = ActionRequest(
        id=uuid4(),
        action_type="gmail_query",
        status="previewed",
        requested_by="op",
        payload_redacted={},
        payload_executable={},
        preview={},
        result={},
        created_at=now,
        updated_at=now,
    )

    class FakeSession:
        async def get(self, model: type[object], obj_id: UUID) -> object | None:
            del model, obj_id
            return row

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/actions/requests/{row.id}/workflow",
            headers=_headers(),
        )

    assert response.status_code == 409
    assert "workflow.v1" in response.json()["detail"]


@pytest.mark.asyncio
async def test_export_workflow_returns_404_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_id = UUID("99999999-9999-9999-9999-999999999999")

    class FakeSession:
        async def get(self, model: type[object], obj_id: UUID) -> object | None:
            del model, obj_id
            return None

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/actions/requests/{missing_id}/workflow",
            headers=_headers(),
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_from_workflow_routes_to_browser_preview_carril(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Import dispatches to the matching `create_*_request` method."""

    captured: dict[str, object] = {}

    async def fake_create_browser_preview_request(
        self: object,
        request: object,
        *,
        requested_by: str,
    ) -> object:
        del self
        captured["request"] = request
        captured["requested_by"] = requested_by
        from cognitive_os.actions.schemas import ActionRequestView

        return ActionRequestView(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            action_type="browser_preview",
            status="pending_approval",
            requested_by=requested_by,
            approval_id=None,
            job_id=None,
            payload_redacted={"url": "https://example.com"},
            preview={"status": "ok"},
            result={},
            error=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    monkeypatch.setattr(
        ActionRequestService,
        "create_browser_preview_request",
        fake_create_browser_preview_request,
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/requests/from-workflow",
            headers=_headers(),
            json={
                "workflow_version": "1.0",
                "action_type": "browser_preview",
                "payload": {"url": "https://example.com"},
                "notes": "smoke",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is False
    assert body["notes"] == "smoke"
    assert body["action_request"]["action_type"] == "browser_preview"
    assert captured["requested_by"] == "1"


@pytest.mark.asyncio
async def test_from_workflow_rejects_unsupported_version() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/requests/from-workflow",
            headers=_headers(),
            json={
                "workflow_version": "9.9",
                "action_type": "browser_preview",
                "payload": {},
            },
        )

    # Pydantic rejects the Literal mismatch with 422 — that's the contract.
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_from_workflow_requires_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/requests/from-workflow",
            json={
                "workflow_version": "1.0",
                "action_type": "browser_preview",
                "payload": {"url": "https://example.com"},
            },
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_workflow_export_endpoint_uses_real_carril(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end test of the export endpoint against an in-memory session."""
    now = datetime.now(UTC)
    row = ActionRequest(
        id=UUID("44444444-4444-4444-4444-444444444444"),
        action_type="document_generate",
        status="pending_approval",
        requested_by="operator-1",
        payload_redacted={"format": "docx", "output_filename": "out.docx"},
        payload_executable={},
        preview={"status": "ok"},
        result={},
        created_at=now,
        updated_at=now,
    )

    class FakeSession:
        async def get(self, model: type[object], obj_id: UUID) -> object | None:
            del model, obj_id
            return row

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)
    # The export endpoint calls ActionRequestService inside api.app — ensure
    # both module instances see the patched session_scope.
    monkeypatch.setattr(api_app, "session_scope", fake_session_scope, raising=False)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/actions/requests/{row.id}/workflow",
            headers=_headers(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_version"] == "1.0"
    assert body["action_type"] == "document_generate"
    assert body["payload"]["format"] == "docx"
    assert body["source"]["exported_by"] == "1"

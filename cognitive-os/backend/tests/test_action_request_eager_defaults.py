"""Regression tests for the MissingGreenlet 500 on `_view(action_request)`.

The bug: `actions/service.py::_view` reads `action_request.updated_at`
after `await session.flush()` in an async session. Without
`eager_defaults=True` on the ORM Base, the server-default for
`updated_at` is not loaded until first access, which triggers a
synchronous lazy refresh outside the greenlet boundary and raises
`sqlalchemy.exc.MissingGreenlet`. The fix is `eager_defaults=True` on
`core/db.py::Base`, which makes INSERT emit `RETURNING` for
server-defaulted columns.

These tests assert two things:

1. Reading `updated_at` after `flush()` in the same async session does
   not raise — proves `eager_defaults` is honoured.
2. The HTTP endpoint `POST /actions/browser/preview/request` returns
   200 with a populated `updated_at`. This is the actual production
   regression observed in the re-audit on 2026-05-23.

The endpoint is not mocked: this hits the real `ActionRequestService`
against the test DB. The auto-approve path (dedicated_local/full) is
short-circuited by deactivating the auto-approve setting in the test
override so the side-effect surface stays narrow.
"""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest

from cognitive_os.actions.schemas import BrowserPreviewRequest
from cognitive_os.actions.service import ActionRequestService
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import ActionRequest


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


@pytest.mark.asyncio
async def test_action_request_updated_at_is_eager_loaded_after_flush() -> None:
    """Server-side default `updated_at` must be populated by the INSERT
    RETURNING clause (eager_defaults=True), not lazily refreshed."""
    async with session_scope() as session:
        action_request = ActionRequest(
            action_type="browser_preview",
            status="pending_approval",
            requested_by="test-eager-defaults",
            idempotency_key="test-eager-defaults-key",
            payload_redacted={"url": "https://example.com"},
            payload_executable={"url": "https://example.com"},
            preview={"url": "https://example.com", "status": "ok"},
        )
        session.add(action_request)
        await session.flush()

        # The critical assertion: reading these attributes must NOT raise
        # MissingGreenlet, which would happen if eager_defaults=False.
        assert action_request.id is not None
        assert action_request.created_at is not None
        assert action_request.updated_at is not None
        assert isinstance(action_request.id, UUID)


@pytest.mark.asyncio
async def test_browser_preview_request_endpoint_returns_200_against_real_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for the re-audit P1 (2026-05-23): the endpoint hit the
    real DB through ActionRequestService and returned 500 because
    `_view(action_request)` accessed `updated_at` lazily after flush."""
    # Force the path through the real service (no FakeActionRequestService
    # monkeypatch). Keep auto-approve OFF so the test stops at the
    # `pending_approval` state without dispatching Celery.
    monkeypatch.setattr(
        settings,
        "auto_approve_reversible_actions",
        False,
        raising=False,
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/browser/preview/request",
            json={"url": "https://example.com"},
            headers=_headers(),
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["action_type"] == "browser_preview"
    assert payload["status"] in {"pending_approval", "queued", "running", "blocked"}
    assert payload["updated_at"] is not None
    assert payload["created_at"] is not None


@pytest.mark.asyncio
async def test_service_create_browser_preview_request_returns_view_with_updated_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct service call must not raise and must surface `updated_at`."""
    monkeypatch.setattr(
        settings,
        "auto_approve_reversible_actions",
        False,
        raising=False,
    )
    service = ActionRequestService()
    view = await service.create_browser_preview_request(
        BrowserPreviewRequest(url="https://example.com"),
        requested_by="test-direct-service",
    )
    assert view.id is not None
    assert view.updated_at is not None
    assert view.created_at is not None
    assert view.status in {"pending_approval", "queued", "running", "blocked"}

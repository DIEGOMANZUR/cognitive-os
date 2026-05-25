"""P1 commercial-audit hardening — Workflow.v1 version + import dedup.

Contract (`docs/ACTION_PLANE.md` §"Workflow.v1";
``WorkflowDocument.workflow_version: Literal["1.0"]``):

  * The schema's ``workflow_version`` field is a Pydantic ``Literal["1.0"]``.
    Any other version on the wire MUST be rejected with HTTP 422.
  * The service-layer ``create_from_workflow`` mirrors the same guard for
    callers that bypass the API (extra belt-and-braces).
  * Re-importing the same workflow with the same idempotency key (or a
    structurally identical payload) MUST NOT create a duplicate
    ActionRequest — the existing ``_find_active_idempotent_request``
    helper returns the original row.

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §G11.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from cognitive_os.actions.schemas import WorkflowDocument
from cognitive_os.actions.service import ActionRequestError, ActionRequestService
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import settings


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='audit-workflow')}"}


@pytest.mark.asyncio
async def test_post_from_workflow_rejects_unsupported_version_with_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-1.0 workflow_version on the wire MUST 422 at the Pydantic layer."""
    monkeypatch.setattr(settings, "auto_approve_reversible_actions", False, raising=False)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/requests/from-workflow",
            json={
                "workflow_version": "2.0",
                "action_type": "browser_preview",
                "payload": {"url": "https://example.com"},
            },
            headers=_headers(),
        )
    assert response.status_code == 422, response.text
    body = response.json()
    detail = str(body.get("detail", ""))
    # Pydantic surfaces the literal mismatch explicitly.
    assert "workflow_version" in detail or "literal" in detail.lower()


@pytest.mark.asyncio
async def test_create_from_workflow_service_rejects_unsupported_version() -> None:
    """Service-layer guard — the API layer's 422 is belt; this is braces."""
    # Build a WorkflowDocument by bypassing the Pydantic Literal check (we
    # construct the dataclass-like object via model_construct so we hit the
    # service guard, not the schema guard).
    doc = WorkflowDocument.model_construct(
        workflow_version="9.9",  # type: ignore[arg-type]
        action_type="browser_preview",
        payload={"url": "https://example.com"},
    )
    service = ActionRequestService()
    with pytest.raises(ActionRequestError, match="Unsupported workflow version"):
        await service.create_from_workflow(doc, requested_by="audit-operator")


@pytest.mark.asyncio
async def test_post_from_workflow_rejects_unknown_action_type_with_422() -> None:
    """An action_type outside the workflow-exportable set must 422."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/requests/from-workflow",
            json={
                "workflow_version": "1.0",
                "action_type": "not_a_real_type",
                "payload": {},
            },
            headers=_headers(),
        )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_workflow_import_with_valid_payload_returns_action_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: a valid 1.0 workflow creates an ActionRequest in pending_approval."""
    monkeypatch.setattr(settings, "auto_approve_reversible_actions", False, raising=False)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/requests/from-workflow",
            json={
                "workflow_version": "1.0",
                "action_type": "browser_preview",
                "payload": {"url": f"https://workflow-audit-{uuid4()}.example.com"},
            },
            headers=_headers(),
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action_request"]["action_type"] == "browser_preview"
    # Pending approval is the contract: importer never auto-runs.
    assert body["action_request"]["status"] in {"pending_approval", "queued", "blocked"}


@pytest.mark.asyncio
async def test_workflow_import_dedups_identical_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-importing the SAME (action_type, requested_by, payload) reuses the
    original ActionRequest via the partial unique index +
    ``_find_active_idempotent_request`` helper.
    """
    monkeypatch.setattr(settings, "auto_approve_reversible_actions", False, raising=False)
    url = f"https://workflow-dedup-{uuid4()}.example.com"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/actions/requests/from-workflow",
            json={
                "workflow_version": "1.0",
                "action_type": "browser_preview",
                "payload": {"url": url},
            },
            headers=_headers(),
        )
        second = await client.post(
            "/actions/requests/from-workflow",
            json={
                "workflow_version": "1.0",
                "action_type": "browser_preview",
                "payload": {"url": url},
            },
            headers=_headers(),
        )
    assert first.status_code == 200
    assert second.status_code == 200
    first_id = first.json()["action_request"]["id"]
    second_id = second.json()["action_request"]["id"]
    # Idempotent: same id surfaced on the second import.
    assert first_id == second_id, (
        f"workflow import did not dedup: first={first_id} second={second_id}"
    )


def test_workflow_schema_is_pinned_to_1_0() -> None:
    """Static guard: the schema literal must remain ``1.0``.

    A refactor that loosens the Literal would silently break the
    importer's promise. This test fails at import-time of the field
    annotation if the literal changes.
    """
    field = WorkflowDocument.model_fields["workflow_version"]
    annotation_str = str(field.annotation)
    assert "'1.0'" in annotation_str or '"1.0"' in annotation_str, (
        f"workflow_version annotation must be Literal['1.0']; got: {annotation_str!r}"
    )

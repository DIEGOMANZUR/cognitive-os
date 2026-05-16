from __future__ import annotations

from uuid import UUID

import httpx
import pytest

import cognitive_os.api.app as api_app
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


@pytest.mark.asyncio
async def test_openshell_status_endpoint_responds() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/sandbox/openshell/status", headers=_headers())

    assert response.status_code == 200
    assert response.json()["status"] in {
        "not_enabled",
        "vendor_missing",
        "gateway_unavailable",
        "ok",
    }


@pytest.mark.asyncio
async def test_openshell_run_endpoint_returns_needs_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = UUID("11111111-1111-1111-1111-111111111111")
    approval_id = UUID("22222222-2222-2222-2222-222222222222")

    async def fake_create_job(*args: object, **kwargs: object) -> tuple[UUID, UUID]:
        del args, kwargs
        return job_id, approval_id

    monkeypatch.setattr(api_app.settings, "enable_openshell_sandbox", True)
    monkeypatch.setattr(api_app, "requires_openshell_approval", lambda task, settings: True)
    monkeypatch.setattr(api_app, "_create_openshell_approval_job", fake_create_job)

    payload = {
        "task_id": "task-1",
        "thread_id": "thread-1",
        "user_id": None,
        "purpose": "code_test",
        "instruction": "run an isolated smoke check",
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/sandbox/openshell/run",
            json=payload,
            headers=_headers(),
        )

    assert response.status_code == 202
    assert response.json()["status"] == "needs_approval"
    assert response.json()["job_id"] == str(job_id)
    assert response.json()["approval_id"] == str(approval_id)

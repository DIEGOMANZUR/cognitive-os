"""P1 commercial-audit hardening — Calendar/Drive direct endpoints reject ``dry_run=false``.

Contract (`docs/ACTION_PLANE.md` §Calendar/§Drive):

  * ``POST /actions/calendar/events/create`` is preview-only. ``dry_run=false``
    MUST return HTTP 409 with a direct-writes-disabled message; real writes
    go through ``/actions/calendar/events/request`` (ActionRequest +
    approval + Celery).
  * ``POST /actions/drive/files/upload`` is preview-only. ``dry_run=false``
    MUST 409.
  * ``POST /actions/drive/folders/ensure`` and
    ``POST /actions/drive/organize/preview`` follow the same rule.

This matrix forces the gate for each direct write endpoint and verifies
the rejection message points the operator at the correct ActionRequest
route — fulfilling the "operator no tiene que adivinar" contract.

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §G8.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='audit-direct')}"}


@pytest.mark.asyncio
async def test_calendar_events_create_with_dry_run_false_returns_409() -> None:
    now = datetime.now(UTC)
    start = (now + timedelta(hours=1)).isoformat()
    end = (now + timedelta(hours=2)).isoformat()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/calendar/events/create",
            json={
                "summary": "Audit Direct Reject",
                "start": start,
                "end": end,
                "dry_run": False,
            },
            headers=_headers(),
        )

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "Direct Calendar writes are disabled" in detail
    assert "/actions/calendar/events/request" in detail


@pytest.mark.asyncio
async def test_drive_files_upload_with_dry_run_false_returns_409() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/drive/files/upload",
            json={
                "local_path": "/tmp/audit-direct-upload-source.pdf",
                "folder_name": "Cognitive OS Deliverables",
                "drive_name": "audit-direct-upload.pdf",
                "dry_run": False,
            },
            headers=_headers(),
        )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "Direct Drive uploads are disabled" in detail
    assert "/actions/drive/files/upload/request" in detail


@pytest.mark.asyncio
async def test_drive_folders_ensure_with_dry_run_false_returns_409() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/drive/folders/ensure",
            json={
                "folder_name": "Cognitive OS Deliverables",
                "dry_run": False,
            },
            headers=_headers(),
        )
    assert response.status_code == 409, response.text


@pytest.mark.asyncio
async def test_drive_organize_preview_with_dry_run_false_returns_409() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/drive/organize/preview",
            json={
                "target_folder_name": "Cognitive OS Deliverables",
                "query": "audit",
                "dry_run": False,
            },
            headers=_headers(),
        )
    assert response.status_code == 409, response.text


@pytest.mark.asyncio
async def test_calendar_dry_run_true_does_not_return_409() -> None:
    """Sanity: with dry_run=true the 409 gate does NOT fire (might 200/502/etc.)"""
    now = datetime.now(UTC)
    start = (now + timedelta(hours=1)).isoformat()
    end = (now + timedelta(hours=2)).isoformat()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/calendar/events/create",
            json={
                "summary": "Audit Dry Run",
                "start": start,
                "end": end,
                "dry_run": True,
            },
            headers=_headers(),
        )
    # Whatever happens with the upstream provider, the 409 gate must NOT fire.
    assert response.status_code != 409, response.text

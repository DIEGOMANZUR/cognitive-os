from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import cognitive_os.api.app as api_app
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import Job, JobEvent


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='operator')}"}


async def _create_job(
    *,
    status: str = "running",
    metadata_json: dict[str, object] | None = None,
) -> UUID:
    async with session_scope() as session:
        job = Job(
            job_type="deepagent_research",
            status=status,
            progress=10,
            metadata_json=metadata_json or {},
        )
        session.add(job)
        await session.flush()
        return job.id


@pytest.mark.asyncio
async def test_cancel_job_revokes_celery_task_and_records_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = await _create_job(metadata_json={"celery_task_id": "celery-123"})
    calls: list[dict[str, object]] = []

    def fake_revoke(task_id: str, *, terminate: bool, signal: str) -> None:
        calls.append({"task_id": task_id, "terminate": terminate, "signal": signal})

    monkeypatch.setattr(api_app.celery_app.control, "revoke", fake_revoke)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/jobs/{job_id}/cancel", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["celery_task_id"] == "celery-123"
    assert body["celery_revoke_requested"] is True
    assert body["celery_revoke_error"] is None
    assert calls == [{"task_id": "celery-123", "terminate": True, "signal": "SIGTERM"}]

    async with session_scope() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "cancelled"
        assert job.progress == 100
        assert job.metadata_json["celery_revoke_signal"] == "SIGTERM"
        events = (
            (await session.execute(select(JobEvent).where(JobEvent.job_id == job_id)))
            .scalars()
            .all()
        )
        assert [event.event_type for event in events] == ["job_cancelled"]
        assert events[0].metadata_json["celery_revoke_requested"] is True


@pytest.mark.asyncio
async def test_cancel_job_revoke_failure_leaves_job_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = await _create_job(metadata_json={"celery_task_id": "celery-err"})

    def fake_revoke(task_id: str, *, terminate: bool, signal: str) -> None:
        del task_id, terminate, signal
        raise RuntimeError("broker offline")

    monkeypatch.setattr(api_app.celery_app.control, "revoke", fake_revoke)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/jobs/{job_id}/cancel", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["celery_revoke_requested"] is False
    assert body["celery_revoke_error"] == "RuntimeError: broker offline"

    async with session_scope() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "running"
        assert job.metadata_json["celery_revoke_error_type"] == "RuntimeError"
        events = (
            (await session.execute(select(JobEvent).where(JobEvent.job_id == job_id)))
            .scalars()
            .all()
        )
        assert [event.event_type for event in events] == ["job_cancel_failed"]


def test_document_ingest_records_celery_task_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_path = tmp_path / "doc.pdf"
    document_path.write_bytes(b"%PDF-1.4\n% test\n")
    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))

    class FakeAsyncResult:
        id = "celery-ingest-1"

    def fake_apply_async(*, args: list[str], queue: str) -> FakeAsyncResult:
        assert args[0] == str(document_path.resolve())
        assert queue == "ingestion"
        return FakeAsyncResult()

    monkeypatch.setattr(api_app.ingest_pdf_task, "apply_async", fake_apply_async)
    client = TestClient(app)

    response = client.post(
        "/documents/ingest",
        json={"document_path": str(document_path)},
        headers=_headers(),
    )

    assert response.status_code == 202
    job_id = UUID(response.json()["job_id"])

    async def assert_job() -> None:
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            assert job is not None
            assert job.metadata_json["celery_task_id"] == "celery-ingest-1"
            assert job.metadata_json["celery_queue"] == "ingestion"
            events = (
                (await session.execute(select(JobEvent).where(JobEvent.job_id == job_id)))
                .scalars()
                .all()
            )
            assert [event.event_type for event in events] == [
                "job_queued",
                "document_ingestion_dispatch_submitted",
            ]

    asyncio.run(assert_job())

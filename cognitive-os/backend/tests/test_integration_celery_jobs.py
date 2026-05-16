from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import Job
from cognitive_os.workers.celery_app import celery_app
from cognitive_os.workers.tasks import debug_fast_task, health_check_task, ingest_pdf_task


def _docker_is_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )
    return result.returncode == 0


def _worker_is_active() -> bool:
    try:
        replies = celery_app.control.ping(timeout=1.0)
    except Exception:
        return False
    return bool(replies)


def _embeddings_are_configured() -> bool:
    return (
        os.environ.get("EMBEDDINGS_BASE_URL", "CHANGEME") != "CHANGEME"
        and os.environ.get("EMBEDDINGS_API_KEY", "CHANGEME") != "CHANGEME"
        and os.environ.get("EMBEDDINGS_MODEL", "CHANGEME") != "CHANGEME"
    )


def _create_pdf(path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=letter)
    pdf.drawString(72, 720, "Celery worker ingestion test. Articulo 8. RUT 12.345.678-9.")
    pdf.save()


async def _create_queued_job(document_path: Path) -> UUID:
    async with session_scope() as session:
        job = Job(
            job_type="document_ingestion",
            status="queued",
            progress=0,
            metadata_json={"document_path": str(document_path)},
        )
        session.add(job)
        await session.flush()
        return job.id


async def _get_job_status(job_id: UUID) -> str:
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        return job.status


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _docker_is_available(), reason="Docker is not available"),
]


def test_health_check_task_records_job() -> None:
    result = health_check_task.apply().get(timeout=10)

    assert result["ok"] is True
    assert UUID(result["job_id"])


def test_debug_fast_task() -> None:
    result = debug_fast_task.apply(args=["fast-ok"]).get(timeout=10)

    assert result["value"] == "fast-ok"
    assert UUID(result["job_id"])


def test_document_ingest_endpoint_creates_queryable_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "queued.pdf"
    _create_pdf(pdf_path)
    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    calls: list[dict[str, Any]] = []

    def fake_apply_async(*, args: list[str], queue: str) -> None:
        calls.append({"args": args, "queue": queue})

    monkeypatch.setattr(ingest_pdf_task, "apply_async", fake_apply_async)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {create_access_token(user_id='1')}"}

    response = client.post(
        "/documents/ingest",
        json={"document_path": str(pdf_path)},
        headers=headers,
    )

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert calls == [{"args": [str(pdf_path.resolve()), job_id], "queue": "ingestion"}]

    job_response = client.get(f"/jobs/{job_id}", headers=headers)
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "queued"

    events_response = client.get(f"/jobs/{job_id}/events", headers=headers)
    assert events_response.status_code == 200
    assert events_response.json()[0]["event_type"] == "job_queued"


def test_worker_ingests_pdf_when_active(tmp_path: Path) -> None:
    if not _worker_is_active():
        pytest.skip("Celery worker is not active")
    if not _embeddings_are_configured():
        pytest.skip("Embeddings provider is not configured for real worker ingestion")

    pdf_path = tmp_path / "worker.pdf"
    _create_pdf(pdf_path)
    job_id = asyncio.run(_create_queued_job(pdf_path))

    ingest_pdf_task.apply_async(args=[str(pdf_path), str(job_id)], queue="ingestion")

    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        status = asyncio.run(_get_job_status(job_id))
        if status in {"completed", "failed"}:
            break
        time.sleep(1)

    assert asyncio.run(_get_job_status(job_id)) == "completed"


def test_document_ingest_rejects_path_outside_allowed_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {create_access_token(user_id='1')}"}
    response = client.post(
        "/documents/ingest",
        json={"document_path": "/etc/passwd"},
        headers=headers,
    )
    assert response.status_code == 400

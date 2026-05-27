from __future__ import annotations

from pathlib import Path
from uuid import UUID

import httpx
import pytest

import cognitive_os.api.app as api_app
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


def _payload() -> dict[str, object]:
    return {
        "task_id": "task-1",
        "thread_id": "thread-1",
        "user_id": None,
        "case_id": None,
        "doc_ids": ["doc-a"],
        "query": "Analiza los hechos principales y arma matriz con citas",
        "modes": ["evidence_matrix"],
        "output_formats": ["json", "markdown"],
    }


@pytest.mark.asyncio
async def test_run_endpoint_creates_job(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = UUID("11111111-1111-1111-1111-111111111111")
    captured: dict[str, object] = {}

    async def fake_create_job(*args: object, **kwargs: object) -> UUID:
        del args, kwargs
        return job_id

    def fake_apply_async(*args: object, **kwargs: object) -> None:
        captured["args"] = args
        captured["kwargs"] = kwargs

    # Regression F-P2-002: under hermetic stress the original test relied on
    # the implicit `await session.get(Job, job_id)` inside
    # `_record_celery_dispatch_outcome` short-circuiting on `None` (the fake
    # `_create_document_analysis_job` returns a UUID without ever inserting a
    # `Job` row). In `stress-qa.sh 5` we observed an intermittent failure (1/5)
    # — when another test leaves DB connection pool saturation or transient
    # backend latency, that session lookup can raise, the dispatch helper
    # propagates 500 and the assertions never see `captured`. Patching the
    # outcome recorder to a no-op makes the test deterministic about what it
    # actually asserts: the API surface routes the request to the right Celery
    # queue with the right payload. The full `_record_celery_dispatch_outcome`
    # behaviour is exercised by `test_action_request_workers.py` and
    # `test_integration_celery_jobs.py`.
    async def fake_record_outcome(**kwargs: object) -> None:
        del kwargs

    monkeypatch.setattr(api_app, "_create_document_analysis_job", fake_create_job)
    monkeypatch.setattr(api_app, "_record_celery_dispatch_outcome", fake_record_outcome)
    monkeypatch.setattr(api_app.run_document_analysis_task_async, "apply_async", fake_apply_async)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/document-analysis/run",
            json=_payload(),
            headers=_headers(),
        )

    assert response.status_code == 202, response.text
    assert response.json()["job_id"] == str(job_id)
    assert captured["kwargs"]["queue"] == "agent_longrun"
    assert captured["kwargs"]["args"][0]["task_id"] == "task-1"


@pytest.mark.asyncio
async def test_report_requires_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/document-analysis/task-1/report")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_downloads_do_not_expose_absolute_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report = tmp_path / "report.md"
    report.write_text("# Reporte\nsin ruta absoluta\n", encoding="utf-8")
    monkeypatch.setattr(api_app, "_analysis_file_path", lambda task_id, filename: report)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/document-analysis/task-1/download/markdown",
            headers=_headers(),
        )

    assert response.status_code == 200
    assert str(tmp_path) not in response.text
    assert "report.md" in response.headers["content-disposition"]

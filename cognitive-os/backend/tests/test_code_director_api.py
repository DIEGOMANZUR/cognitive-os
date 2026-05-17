"""F6 regression: Code Director REST endpoints.

Covers the four endpoints without a real DB or real coding agent:
- POST /code-director/run rejects the fake adapter and the unauthenticated
  caller, and returns the plan + approval id on success.
- GET /code-director/{id} 404s for a non-code_build job.
- GET /code-director/{id}/download enforces the artifact-path containment.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest

import cognitive_os.api.app as api_app
from cognitive_os.api.app import app
from cognitive_os.code_director.schemas import BuildPlan, SubtaskSpec
from cognitive_os.core.auth import create_access_token


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


def _valid_body(adapter: str = "claude_code") -> dict[str, object]:
    return {
        "objective": "Build a tiny CLI calculator with tests" + " " * 60,
        "adapter_preference": {"default_adapter": adapter, "default_model": "claude-opus-4-7"},
    }


@pytest.mark.asyncio
async def test_run_requires_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/code-director/run", json=_valid_body())
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_run_rejects_fake_adapter() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/code-director/run", headers=_headers(), json=_valid_body("fake"))
    assert resp.status_code == 400
    assert "reserved for tests" in resp.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role_key",
    ["planner_adapter", "coder_adapter", "reviewer_adapter", "tester_adapter"],
)
async def test_run_rejects_fake_adapter_in_any_role(role_key: str) -> None:
    """An operator can't smuggle the fake adapter in via a non-default role."""
    body = _valid_body("claude_code")
    body["adapter_preference"][role_key] = "fake"  # type: ignore[index]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/code-director/run", headers=_headers(), json=body)
    assert resp.status_code == 400, role_key
    assert "reserved for tests" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_run_returns_plan_and_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid4()
    approval_id = uuid4()
    plan = BuildPlan(
        workspace_dir="/tmp/storage/workspaces/code_builds/cb-demo",
        subtasks=[
            SubtaskSpec(
                subtask_id="st-1",
                title="scaffold",
                description="do it",
                role="coder",
                adapter="claude_code",
            )
        ],
        estimated_runtime_minutes=10,
        estimated_calls=3,
    )

    class FakeService:
        async def create_build(self, request: object, *, requested_by: str) -> object:
            del request
            assert requested_by == "1"
            return job_id, approval_id, plan

    monkeypatch.setattr(api_app, "CodeDirectorService", lambda *a, **k: FakeService())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/code-director/run", headers=_headers(), json=_valid_body())
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == str(job_id)
    assert body["approval_id"] == str(approval_id)
    assert body["build_id"] == "cb-demo"
    assert body["plan"]["subtasks"][0]["subtask_id"] == "st-1"


@pytest.mark.asyncio
async def test_get_build_404_for_non_code_build_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cognitive_os.db.models import Job

    now = datetime.now(UTC)
    other_job = Job(
        id=UUID("12121212-1212-1212-1212-121212121212"),
        job_type="document_ingestion",
        status="completed",
        progress=100,
        metadata_json={},
        created_at=now,
        updated_at=now,
    )

    class FakeSession:
        async def get(self, model: type[object], _obj_id: UUID) -> object | None:
            return other_job if model is Job else None

    @asynccontextmanager
    async def fake_scope():
        yield FakeSession()

    monkeypatch.setattr(api_app, "session_scope", fake_scope)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/code-director/{other_job.id}", headers=_headers())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_rejects_artifact_outside_output_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cognitive_os.db.models import Job

    now = datetime.now(UTC)
    job = Job(
        id=UUID("34343434-3434-3434-3434-343434343434"),
        job_type="code_build",
        status="completed",
        progress=100,
        metadata_json={
            "build_id": "cb-x",
            "result": {"artifact_path": "/etc/passwd"},  # escapes output root
        },
        created_at=now,
        updated_at=now,
    )

    class FakeSession:
        async def get(self, model: type[object], _obj_id: UUID) -> object | None:
            return job if model is Job else None

    @asynccontextmanager
    async def fake_scope():
        yield FakeSession()

    monkeypatch.setattr(api_app, "session_scope", fake_scope)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/code-director/{job.id}/download", headers=_headers())
    assert resp.status_code == 400
    assert "escapes" in resp.json()["detail"]

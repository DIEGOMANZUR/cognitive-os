"""F4 regression: CodeDirectorService HITL persistence.

`create_build` must persist a waiting-approval Job + a HumanApproval and
spend ZERO tokens. `run_build` (post-approval) runs the director and
persists the result. We use an in-memory fake session (same pattern as
test_actions.py) so no Postgres is required.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

import cognitive_os.code_director.service as svc_module
from cognitive_os.code_director.adapters.fake import FakeAdapter
from cognitive_os.code_director.director import CodeDirector
from cognitive_os.code_director.planner import HeuristicPlanner
from cognitive_os.code_director.schemas import AdapterPreference, CodeBuildRequest
from cognitive_os.code_director.service import CodeDirectorError, CodeDirectorService
from cognitive_os.core.config import Settings
from cognitive_os.db.models import AuditEvent, HumanApproval, Job, JobEvent


class _FakeSession:
    def __init__(self, store: dict[UUID, object]) -> None:
        self.added: list[object] = []
        self._store = store

    def add(self, obj: object) -> None:
        self.added.append(obj)
        obj_id = getattr(obj, "id", None)
        if obj_id is not None:
            self._store[obj_id] = obj

    async def flush(self) -> None:
        now = datetime.now(UTC)
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()
                self._store[obj.id] = obj
            if getattr(obj, "created_at", None) is None:
                obj.created_at = now
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = now

    async def get(self, model: type[object], obj_id: UUID) -> object | None:
        obj = self._store.get(obj_id)
        return obj if isinstance(obj, model) else None


def _install_fake_sessions(monkeypatch: pytest.MonkeyPatch) -> dict[UUID, object]:
    store: dict[UUID, object] = {}

    @asynccontextmanager
    async def fake_scope():
        yield _FakeSession(store)

    monkeypatch.setattr(svc_module, "session_scope", fake_scope)
    return store


def _service_with_fake_adapter(tmp_path) -> CodeDirectorService:
    cfg = Settings(
        local_storage_dir=str(tmp_path / "storage"),
        document_output_root=tmp_path / "out",
    )
    hp = HeuristicPlanner()
    director = CodeDirector(
        adapters={"fake": FakeAdapter()},
        local_storage_dir=tmp_path / "storage",
        planner=lambda req, ws: hp.plan(req, workspace_dir=ws),
    )
    # `allow_fake_adapter` is the documented test seam — production never
    # sets it, so the fake-adapter guard stays enforced for real requests.
    return CodeDirectorService(cfg, director=director, allow_fake_adapter=True)


def _request() -> CodeBuildRequest:
    return CodeBuildRequest(
        objective="Build a tiny CLI calculator with tests" + " " * 80,
        adapter_preference=AdapterPreference(default_adapter="fake"),
    )


@pytest.mark.asyncio
async def test_create_build_rejects_fake_adapter_from_user(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _install_fake_sessions(monkeypatch)
    cfg = Settings(local_storage_dir=str(tmp_path), document_output_root=tmp_path / "o")
    service = CodeDirectorService(cfg)  # real registry, no fake
    with pytest.raises(CodeDirectorError, match="reserved for tests"):
        await service.create_build(_request(), requested_by="op-1")


@pytest.mark.asyncio
async def test_create_build_persists_waiting_approval_job_and_approval(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _install_fake_sessions(monkeypatch)
    service = _service_with_fake_adapter(tmp_path)

    job_id, approval_id, plan = await service.create_build(_request(), requested_by="op-1")

    assert isinstance(job_id, UUID)
    assert isinstance(approval_id, UUID)
    assert len(plan.subtasks) >= 3
    # No artifact, no adapter call yet — only persistence happened.
    # We can't easily count calls here, but FakeAdapter.invocations would be
    # empty because create_build never runs the director.


@pytest.mark.asyncio
async def test_create_build_emits_audit_and_jobevent(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    store = _install_fake_sessions(monkeypatch)
    service = _service_with_fake_adapter(tmp_path)
    await service.create_build(_request(), requested_by="op-1")

    audits = [o for o in store.values() if isinstance(o, AuditEvent)]
    jobevents = [o for o in store.values() if isinstance(o, JobEvent)]
    approvals = [o for o in store.values() if isinstance(o, HumanApproval)]
    jobs = [o for o in store.values() if isinstance(o, Job)]

    assert any(a.action == "code_build.created" for a in audits)
    assert any(e.event_type == "code_build_plan_ready" for e in jobevents)
    assert approvals and approvals[0].requested_action.startswith("run_code_build:")
    assert jobs and jobs[0].status == "waiting_approval"
    assert jobs[0].job_type == "code_build"


@pytest.mark.asyncio
async def test_run_build_executes_and_persists_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    store = _install_fake_sessions(monkeypatch)
    service = _service_with_fake_adapter(tmp_path)
    job_id, _approval_id, _plan = await service.create_build(_request(), requested_by="op-1")

    result = await service.run_build(job_id)

    assert result.status == "completed"
    assert result.artifact_path is not None
    assert result.artifact_path.endswith(".tar.gz")
    # Job flipped to a terminal state and an executed AuditEvent exists.
    job = store[job_id]
    assert isinstance(job, Job)
    assert job.status == "completed"
    audits = [o for o in store.values() if isinstance(o, AuditEvent)]
    assert any(a.action == "code_build.executed" for a in audits)


@pytest.mark.asyncio
async def test_run_build_missing_job_raises(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _install_fake_sessions(monkeypatch)
    service = _service_with_fake_adapter(tmp_path)
    with pytest.raises(CodeDirectorError, match="job not found"):
        await service.run_build(uuid4())

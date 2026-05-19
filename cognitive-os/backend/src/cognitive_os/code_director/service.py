"""Persistence + HITL wrapper around the pure `CodeDirector` loop.

This is the only module the rest of the backend imports. It enforces the
commercial contract the rest of Cognitive OS already guarantees:

1. `create_build()` — validates the request, produces the plan, and
   persists a `Job(job_type="code_build", status="waiting_approval")`
   plus a `HumanApproval` whose `args_redacted` carries the plan. NO
   adapter is invoked, NO token is spent until the operator approves.
2. `run_build()` — called by the Celery worker AFTER the approval is
   accepted. Re-loads the plan from the job, runs the director,
   persists JobEvents per build event, packages the workspace into a
   tar.gz and records an AuditEvent.

Reusing `Job`/`HumanApproval`/`AuditEvent` (instead of a new table) keeps
the audit trail uniform with every other approved action and means the
existing reaper, four-eyes guard and AuditEvent symmetry apply unchanged.
"""

from __future__ import annotations

import json
import tarfile
import time
from pathlib import Path
from uuid import UUID

import structlog

from cognitive_os.code_director.director import CodeDirector, DirectorError, default_registry
from cognitive_os.code_director.schemas import (
    BuildEvent,
    BuildPlan,
    CodeBuildRequest,
    CodeBuildResult,
)
from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import AuditEvent, HumanApproval, Job, JobEvent

_log = structlog.get_logger(__name__)

_FORBIDDEN_ADAPTER = "fake"
JOB_TYPE = "code_build"


class CodeDirectorError(RuntimeError):
    """Raised when a build cannot be created or run."""


class CodeDirectorService:
    def __init__(
        self,
        app_settings: Settings = settings,
        *,
        director: CodeDirector | None = None,
        allow_fake_adapter: bool = False,
    ) -> None:
        self._settings = app_settings
        self._director = director or CodeDirector(
            adapters=default_registry(),
            local_storage_dir=Path(app_settings.local_storage_dir),
        )
        # Tests inject a director backed by FakeAdapter; production never
        # passes a director nor sets this flag, so the fake guard stays
        # enforced for real requests.
        self._allow_fake_adapter = allow_fake_adapter

    # ---- create (HITL gate #1: plan approval) ----------------------------

    async def create_build(
        self,
        request: CodeBuildRequest,
        *,
        requested_by: str,
    ) -> tuple[UUID, UUID, BuildPlan]:
        """Validate + plan + persist. Returns (job_id, approval_id, plan).

        No coding agent runs here. The operator must approve the returned
        approval before `run_build` is dispatched.
        """
        self._reject_fake(request)
        build_id = self._director.make_build_id()
        try:
            plan = self._director.plan(request, build_id=build_id)
        except DirectorError as exc:
            raise CodeDirectorError(str(exc)) from exc

        # Confirm every adapter the plan references is actually available so
        # the operator approves a plan that can actually run.
        unavailable = self._unavailable_adapters(plan)
        plan_payload = plan.model_dump(mode="json")
        plan_payload["unavailable_adapters"] = unavailable

        async with session_scope() as session:
            job = Job(
                job_type=JOB_TYPE,
                status="waiting_approval",
                progress=0,
                metadata_json={
                    "build_id": build_id,
                    "requested_by": requested_by,
                    "request": request.model_dump(mode="json"),
                    "plan": plan_payload,
                },
            )
            session.add(job)
            await session.flush()
            approval = HumanApproval(
                action="run_code_build",
                requested_action=f"run_code_build:{build_id}",
                args_redacted={
                    "build_id": build_id,
                    "objective_preview": request.objective[:280],
                    "subtask_count": len(plan.subtasks),
                    "adapters": sorted({s.adapter for s in plan.subtasks}),
                    "estimated_runtime_minutes": plan.estimated_runtime_minutes,
                    "estimated_calls": plan.estimated_calls,
                    "estimated_cost_usd": plan.estimated_cost_usd,
                    "unavailable_adapters": unavailable,
                },
                requested_by=requested_by,
                job_id=job.id,
                metadata_json={"build_id": build_id},
            )
            session.add(approval)
            await session.flush()
            job.metadata_json = {**job.metadata_json, "approval_id": str(approval.id)}
            session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="code_build_plan_ready",
                    status="waiting_approval",
                    message=(
                        f"Plan ready: {len(plan.subtasks)} subtasks across "
                        f"{len(set(s.adapter for s in plan.subtasks))} adapter(s). "
                        "Awaiting human approval."
                    ),
                    metadata_json={"build_id": build_id, "approval_id": str(approval.id)},
                )
            )
            session.add(
                AuditEvent(
                    actor_id=requested_by,
                    action="code_build.created",
                    resource_type="code_build",
                    resource_id=build_id,
                    metadata_json={
                        "job_id": str(job.id),
                        "subtask_count": len(plan.subtasks),
                    },
                )
            )
            await session.flush()
            return job.id, approval.id, plan

    # ---- run (post-approval, called by Celery) ---------------------------

    async def run_build(self, job_id: UUID) -> CodeBuildResult:
        """Execute an approved build. The Celery task calls this only after
        the linked HumanApproval reached `approved`."""
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                msg = f"code_build job not found: {job_id}"
                raise CodeDirectorError(msg)
            meta = dict(job.metadata_json or {})
            build_id = str(meta.get("build_id", ""))
            request_dict = meta.get("request")
            plan_dict = meta.get("plan")
            if (
                not build_id
                or not isinstance(request_dict, dict)
                or not isinstance(plan_dict, dict)
            ):
                msg = "code_build job metadata is incomplete; cannot run."
                raise CodeDirectorError(msg)
            request_payload: dict[str, object] = dict(request_dict)
            plan_payload: dict[str, object] = dict(plan_dict)

        request = CodeBuildRequest.model_validate(request_payload)
        # Drop the synthetic key we added for the operator UI.
        plan_payload.pop("unavailable_adapters", None)
        plan = BuildPlan.model_validate(plan_payload)

        events: list[BuildEvent] = []

        def _sink(ev: BuildEvent) -> None:
            events.append(ev)

        result = self._director.run(request, plan, build_id=build_id, emit=_sink)

        artifact_path: str | None = None
        if result.status in {"completed", "partial"}:
            artifact_path = self._package_workspace(build_id, Path(result.workspace_dir))
            result.artifact_path = artifact_path

        await self._persist_result(job_id, build_id, result, events)
        return result

    # ---- helpers ---------------------------------------------------------

    def _reject_fake(self, request: CodeBuildRequest) -> None:
        if self._allow_fake_adapter:
            return
        pref = request.adapter_preference
        candidates = [
            pref.default_adapter,
            pref.planner_adapter,
            pref.coder_adapter,
            pref.reviewer_adapter,
            pref.tester_adapter,
        ]
        if any(c == _FORBIDDEN_ADAPTER for c in candidates):
            msg = "The 'fake' adapter is reserved for tests and cannot be requested."
            raise CodeDirectorError(msg)

    def _unavailable_adapters(self, plan: BuildPlan) -> list[str]:
        registry = self._director._adapters  # noqa: SLF001 - same package
        seen: set[str] = set()
        unavailable: list[str] = []
        for st in plan.subtasks:
            if st.adapter in seen:
                continue
            seen.add(st.adapter)
            adapter = registry.get(st.adapter)
            if adapter is None or not adapter.is_available():
                unavailable.append(st.adapter)
        return unavailable

    def _package_workspace(self, build_id: str, workspace: Path) -> str:
        out_dir = Path(self._settings.document_output_root).expanduser().resolve() / "code_builds"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        archive = out_dir / f"{build_id}-{stamp}.tar.gz"

        files_list: list[Path] = []
        total_bytes = 0
        max_files = self._settings.code_director_package_max_files
        max_bytes = self._settings.code_director_package_max_bytes
        if workspace.exists():
            for entry in workspace.rglob("*"):
                if not entry.is_file():
                    continue
                files_list.append(entry)
                if len(files_list) > max_files:
                    msg = (
                        f"Workspace has more than {max_files} files — refusing to "
                        "package. Raise `CODE_DIRECTOR_PACKAGE_MAX_FILES` or trim "
                        "the workspace."
                    )
                    raise DirectorError(msg)
                try:
                    total_bytes += entry.stat().st_size
                except OSError:
                    continue
                if total_bytes > max_bytes:
                    msg = (
                        f"Workspace exceeds {max_bytes} bytes uncompressed — "
                        "refusing to package. Raise `CODE_DIRECTOR_PACKAGE_MAX_BYTES` "
                        "or trim the workspace."
                    )
                    raise DirectorError(msg)
        manifest = {
            "build_id": build_id,
            "workspace": str(workspace),
            "files": sorted(str(p.relative_to(workspace)) for p in files_list),
            "package_bytes_uncompressed": total_bytes,
        }
        (workspace / "_codedirector_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        with tarfile.open(archive, "w:gz") as tar:
            if workspace.exists():
                tar.add(str(workspace), arcname=build_id)
        return str(archive)

    async def _persist_result(
        self,
        job_id: UUID,
        build_id: str,
        result: CodeBuildResult,
        events: list[BuildEvent],
    ) -> None:
        terminal = {
            "completed": "completed",
            "partial": "completed",
            "failed": "failed",
            "cancelled": "cancelled",
        }.get(result.status, "failed")
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return
            job.status = terminal
            job.progress = 100
            job.metadata_json = {
                **(job.metadata_json or {}),
                "result": result.model_dump(mode="json"),
            }
            # One JobEvent per build event keeps the operator timeline rich.
            for ev in events:
                session.add(
                    JobEvent(
                        job_id=job_id,
                        event_type=f"code_build_{ev.kind}",
                        status=job.status,
                        message=ev.kind,
                        metadata_json={"build_id": build_id, **ev.payload},
                    )
                )
            session.add(
                JobEvent(
                    job_id=job_id,
                    event_type="code_build_finished",
                    status=job.status,
                    message=f"Code build finished: {result.status}",
                    metadata_json={
                        "build_id": build_id,
                        "artifact_path": result.artifact_path,
                        "budget": result.budget.model_dump(mode="json"),
                    },
                )
            )
            session.add(
                AuditEvent(
                    actor_id="system.code_director",
                    action="code_build.executed",
                    resource_type="code_build",
                    resource_id=build_id,
                    metadata_json={
                        "job_id": str(job_id),
                        "status": result.status,
                        "artifact_path": result.artifact_path,
                    },
                )
            )
            await session.flush()

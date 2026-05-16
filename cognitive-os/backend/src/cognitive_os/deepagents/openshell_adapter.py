from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import httpx

from cognitive_os.agents.state import HumanReviewItem
from cognitive_os.agents.state import ToolRiskLevel as ReviewRiskLevel
from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import AuditEvent, JobEvent
from cognitive_os.deepagents.openshell_policy import (
    OpenShellPolicyViolation,
    redact_openshell_payload,
    sanitize_input_file_paths,
    validate_openshell_task,
)
from cognitive_os.deepagents.openshell_schemas import (
    OpenShellApprovalRequest,
    OpenShellResult,
    OpenShellTask,
)


class OpenShellDeepAgentNotInstalled(RuntimeError):  # noqa: N818 - required public API name.
    """Raised when the OpenShell DeepAgent vendor checkout is missing."""


class OpenShellAdapter:
    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    async def status(self) -> dict[str, Any]:
        if not self._settings.enable_openshell_sandbox:
            return {"status": "not_enabled"}
        vendor = self._vendor_dir()
        if not vendor.exists():
            return {"status": "vendor_missing", "vendor_dir": str(vendor)}
        if shutil.which("docker") is None:
            return {"status": "gateway_unavailable", "reason": "docker_missing"}
        docker_info = await self._run_command(["docker", "info"], timeout=5)
        if docker_info.returncode != 0:
            return {"status": "gateway_unavailable", "reason": "docker_not_running"}
        if self._settings.openshell_gateway_url:
            try:
                async with httpx.AsyncClient(
                    timeout=2.0,
                    verify=self._settings.openshell_gateway_tls_verify,
                ) as client:
                    response = await client.get(self._settings.openshell_gateway_url)
                gateway_status = "ok" if response.status_code < 500 else "gateway_unavailable"
            except Exception:
                gateway_status = "gateway_unavailable"
        else:
            openshell_status = await self._run_command(
                ["uv", "run", "openshell", "status"],
                cwd=vendor,
                timeout=15,
            )
            gateway_status = "ok" if openshell_status.returncode == 0 else "gateway_unavailable"
        return {
            "status": gateway_status,
            "vendor_dir": str(vendor),
            "sandbox_name": self._settings.openshell_sandbox_name,
        }

    async def ensure_available(self) -> None:
        current_status = await self.status()
        if current_status["status"] == "not_enabled":
            raise OpenShellPolicyViolation("OpenShell sandbox is disabled.")
        if current_status["status"] == "vendor_missing":
            raise OpenShellDeepAgentNotInstalled("OpenShell DeepAgent vendor checkout is missing.")
        if current_status["status"] != "ok":
            msg = "OpenShell gateway unavailable. Run scripts/openshell_start_gateway.sh."
            raise RuntimeError(msg)

    async def run_task(self, task: OpenShellTask, job_id: str | None = None) -> OpenShellResult:
        if not self._settings.enable_openshell_sandbox:
            return _result(task, "not_enabled", "OpenShell sandbox is disabled.", job_id=job_id)
        vendor = self._vendor_dir()
        if not vendor.exists():
            return _result(task, "failed", "OpenShellDeepAgentNotInstalled", job_id=job_id)
        try:
            validate_openshell_task(task, self._settings)
        except OpenShellPolicyViolation as exc:
            return _result(task, "blocked", str(exc), job_id=job_id)

        if requires_openshell_approval(task, self._settings):
            approval = OpenShellApprovalRequest(
                task_id=task.task_id,
                reason="OpenShell sandbox execution requires human approval.",
                requested_files=task.input_files,
                network_requested=task.allow_network,
                estimated_risk=_estimated_risk(task),
            )
            return OpenShellResult(
                task_id=task.task_id,
                thread_id=task.thread_id,
                status="needs_approval",
                summary=approval.reason,
                stdout_preview=None,
                stderr_preview=None,
                output_files=[],
                exit_code=None,
                sandbox_name=self._settings.openshell_sandbox_name,
                job_id=job_id,
                warnings=[approval.model_dump_json()],
                audit_event_id=None,
            )

        status = await self.status()
        if status["status"] != "ok":
            return _result(
                task,
                "gateway_unavailable",
                "OpenShell gateway unavailable. Run scripts/openshell_start_gateway.sh.",
                job_id=job_id,
            )

        await self._stage_inputs(task)
        await self._record_audit(task, job_id)
        return OpenShellResult(
            task_id=task.task_id,
            thread_id=task.thread_id,
            status="failed",
            summary=(
                "OpenShell gateway is available, but the inspected vendor CLI exposes gateway "
                "and LangGraph server commands rather than a safe one-shot task runner."
            ),
            stdout_preview=None,
            stderr_preview=None,
            output_files=[],
            exit_code=None,
            sandbox_name=self._settings.openshell_sandbox_name,
            job_id=job_id,
            warnings=[
                "Start the vendor LangGraph app with uv run langgraph dev --allow-blocking "
                "and connect through an explicit gateway URL before real execution."
            ],
            audit_event_id=None,
        )

    def _vendor_dir(self) -> Path:
        return (self._settings.openshell_project_dir / "vendor" / "openshell-deepagent").resolve()

    async def _stage_inputs(self, task: OpenShellTask) -> None:
        input_files = sanitize_input_file_paths(
            task.input_files,
            self._settings.openshell_allowed_input_dir,
        )
        if not input_files:
            return
        staging_dir = (
            self._settings.openshell_allowed_output_dir / task.thread_id / task.task_id / "input"
        )
        staging_dir.mkdir(parents=True, exist_ok=True)
        for source in input_files:
            shutil.copy2(source, staging_dir / source.name)

    async def _run_command(
        self,
        args: list[str],
        *,
        timeout: int,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return await asyncio.to_thread(
            subprocess.run,
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    async def _record_audit(self, task: OpenShellTask, job_id: str | None) -> None:
        async with session_scope() as session:
            event = AuditEvent(
                actor_id=task.user_id,
                action="openshell.run_task",
                resource_type="openshell_task",
                resource_id=task.task_id,
                metadata_json=redact_openshell_payload(
                    {"task": task.model_dump(mode="json"), "job_id": job_id}
                ),
            )
            session.add(event)


async def record_openshell_job_event(
    job_id: str,
    *,
    event_type: str,
    status: str,
    message: str,
    metadata_json: dict[str, Any] | None = None,
) -> None:
    active_job_id = UUID(job_id)
    async with session_scope() as session:
        session.add(
            JobEvent(
                job_id=active_job_id,
                event_type=event_type,
                status=status,
                message=message,
                metadata_json=metadata_json or {},
            )
        )


def run_sandboxed_code_task(task: OpenShellTask) -> OpenShellResult:
    return asyncio.run(OpenShellAdapter().run_task(task))


def openshell_human_review_item(task: OpenShellTask) -> HumanReviewItem:
    return HumanReviewItem(
        reason="OpenShell sandbox execution requires approval.",
        risk_level=ReviewRiskLevel.HIGH,
        proposed_action="run_sandboxed_code_task",
        payload=redact_openshell_payload(task.model_dump(mode="json")),
    )


def requires_openshell_approval(task: OpenShellTask, app_settings: Settings) -> bool:
    instruction = task.instruction.lower()
    risky_instruction = any(
        marker in instruction
        for marker in ("install", "pip ", "npm ", "scrape", "filesystem", "archivo", "file")
    )
    sensitive_instruction = any(marker in instruction for marker in ("judicial", "personal"))
    return (
        app_settings.openshell_require_human_approval
        or bool(task.input_files)
        or task.allow_network
        or risky_instruction
        or sensitive_instruction
        or app_settings.environment == "production"
    )


def _estimated_risk(task: OpenShellTask) -> Literal["high", "low", "medium"]:
    if task.allow_network or task.input_files:
        return "high"
    if any(marker in task.instruction.lower() for marker in ("install", "scrape", "filesystem")):
        return "medium"
    return "low"


def _result(
    task: OpenShellTask,
    status_value: Literal["blocked", "failed", "gateway_unavailable", "not_enabled"],
    summary: str,
    *,
    job_id: str | None,
) -> OpenShellResult:
    return OpenShellResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status=status_value,
        summary=summary,
        stdout_preview=None,
        stderr_preview=None,
        output_files=[],
        exit_code=None,
        sandbox_name=settings.openshell_sandbox_name,
        job_id=job_id,
        warnings=[],
        audit_event_id=None,
    )


def _truncate(value: str, max_bytes: int) -> str:
    encoded = value.encode()
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode(errors="ignore") + "\n[truncated]"

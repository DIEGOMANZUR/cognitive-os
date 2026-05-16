from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OpenShellTask(BaseModel):
    task_id: str
    thread_id: str
    user_id: str | None = None
    purpose: Literal["code_test", "data_analysis", "script_generation", "debugging", "other"]
    instruction: str
    input_files: list[str] = Field(default_factory=list)
    allow_network: bool = False
    max_runtime_seconds: int = 300
    max_output_bytes: int = 200000
    require_human_approval: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class OpenShellResult(BaseModel):
    task_id: str
    thread_id: str
    status: Literal[
        "ok",
        "blocked",
        "failed",
        "not_enabled",
        "gateway_unavailable",
        "needs_approval",
    ]
    summary: str
    stdout_preview: str | None = None
    stderr_preview: str | None = None
    output_files: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    sandbox_name: str | None = None
    job_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
    audit_event_id: str | None = None


class OpenShellApprovalRequest(BaseModel):
    task_id: str
    reason: str
    requested_files: list[str] = Field(default_factory=list)
    network_requested: bool = False
    estimated_risk: Literal["low", "medium", "high"]

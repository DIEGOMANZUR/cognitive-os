"""Schemas for the Code Director carril.

These types are the public contract between callers (API endpoints, Celery
tasks, frontend) and the director. They are deliberately framework-neutral
(no FastAPI, no SQLAlchemy) so the director module can be unit-tested in
isolation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Public enums / type aliases
# ---------------------------------------------------------------------------

AdapterChoice = Literal[
    "claude_code",
    "codex",
    "kimi",
    "deepagent",
    "fake",  # test-only adapter (never selectable from the API)
]
"""All coding agents the director knows how to drive.

`fake` is the in-memory adapter used by tests; the API layer rejects it.
"""

SubtaskStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
    "cancelled",
]

CodeBuildStatus = Literal[
    "queued",
    "planning",
    "awaiting_plan_approval",
    "running",
    "synthesizing",
    "awaiting_delivery_approval",
    "completed",
    "failed",
    "cancelled",
    "partial",  # budget hit before completion
    "blocked",  # validation rejected the request
]

BuildEventKind = Literal[
    "build_started",
    "plan_ready",
    "subtask_started",
    "subtask_finished",
    "adapter_invocation",
    "budget_warning",
    "budget_exceeded",
    "delivery_packaged",
    "packaging_failed",
    "build_completed",
    "build_failed",
    "build_partial",
    "build_cancelled",
]


# ---------------------------------------------------------------------------
# Request: what the operator submits
# ---------------------------------------------------------------------------


class BudgetSpec(BaseModel):
    """Hard limits the director honours during a build.

    Hitting any limit stops the build with status=`partial` and emits a
    `budget_exceeded` event. The operator can then decide whether to extend
    or abandon.
    """

    max_runtime_minutes: int = Field(default=120, ge=1, le=24 * 60)
    max_total_llm_calls: int = Field(default=200, ge=1, le=5000)
    max_calls_per_subtask: int = Field(default=20, ge=1, le=200)
    # Optional explicit USD cap. None = rely on per-adapter `--max-budget-usd`
    # (Claude Code) or no cap (other adapters).
    max_total_cost_usd: float | None = Field(default=None, ge=0.0, le=10_000.0)


class AdapterPreference(BaseModel):
    """Operator's preference for which adapter handles which role.

    The director keeps four conceptual roles. Each can be pinned to an
    adapter+model pair. Roles not pinned fall back to the adapter listed in
    `default_adapter`.
    """

    default_adapter: AdapterChoice
    default_model: str | None = None

    planner_adapter: AdapterChoice | None = None
    planner_model: str | None = None

    coder_adapter: AdapterChoice | None = None
    coder_model: str | None = None

    reviewer_adapter: AdapterChoice | None = None
    reviewer_model: str | None = None

    tester_adapter: AdapterChoice | None = None
    tester_model: str | None = None

    # NOTE: 'fake' is technically a valid AdapterChoice for unit tests, but the
    # API layer must reject it before constructing this model. We do not enforce
    # the rejection here so that tests can build an `AdapterPreference` with
    # the fake adapter directly. The API layer in `api/app.py` filters out
    # `fake` from accepted requests.

    def for_role(
        self, role: Literal["planner", "coder", "reviewer", "tester"]
    ) -> tuple[AdapterChoice, str | None]:
        """Return the (adapter, model) tuple to use for `role`."""
        adapter = getattr(self, f"{role}_adapter") or self.default_adapter
        model = getattr(self, f"{role}_model") or self.default_model
        return adapter, model


class CodeBuildRequest(BaseModel):
    """High-level user-facing build spec.

    The director consumes this to produce a `BuildPlan`, which the operator
    then approves before any tokens are spent.
    """

    objective: str = Field(min_length=10, max_length=20_000)
    """Natural-language description of what to build."""

    notes: str | None = Field(default=None, max_length=4_000)
    """Free-form extra context (style guides, conventions, constraints)."""

    adapter_preference: AdapterPreference
    budget: BudgetSpec = Field(default_factory=BudgetSpec)

    # If set, the director keeps iterating tester→coder until tests pass or
    # the budget is exhausted. If False, the director stops after the first
    # pass of all subtasks.
    iterate_until_tests_pass: bool = True

    # If True, the director runs generated tests inside `openshell_sandbox`
    # (requires `ENABLE_OPENSHELL_SANDBOX=true` and an approved task). If
    # False, the director emits the tests but does not execute them.
    run_tests_in_sandbox: bool = False

    # Optional pre-existing workspace seed (a tar.gz path inside
    # `LOCAL_STORAGE_DIR`). When None the director starts from an empty
    # workspace.
    workspace_seed_path: str | None = None


# ---------------------------------------------------------------------------
# Plan: what the director produces from the request
# ---------------------------------------------------------------------------


class SubtaskSpec(BaseModel):
    """One unit of work the director will dispatch to an adapter."""

    subtask_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=8_000)
    role: Literal["planner", "coder", "reviewer", "tester"]
    adapter: AdapterChoice
    model: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    # File globs the subtask is expected to touch (informational, helps the
    # frontend diff view target the right files).
    expected_paths: list[str] = Field(default_factory=list)


class BuildPlan(BaseModel):
    """Director's decomposition. Operator approves THIS before any token is spent."""

    workspace_dir: str
    """Absolute path to the isolated workspace for this build."""

    subtasks: list[SubtaskSpec]
    estimated_runtime_minutes: int = Field(ge=0)
    estimated_calls: int = Field(ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    rationale: str = Field(default="", max_length=8_000)
    """One-paragraph explanation of why this decomposition + adapter mix."""


# ---------------------------------------------------------------------------
# Adapter contract (Protocol implementations live in adapters/)
# ---------------------------------------------------------------------------


class AgentSession(BaseModel):
    """Opaque handle returned by `CodingAgentAdapter.start_session`.

    Adapters may attach arbitrary state via `state` (e.g. subprocess pid,
    HTTP thread id). The director does not inspect it.
    """

    session_id: str
    adapter: AdapterChoice
    workspace: str
    model: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)


class StepResult(BaseModel):
    """One adapter invocation's outcome."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration_ms: int = 0
    estimated_input_tokens: int | None = None
    estimated_output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    files_touched: list[str] = Field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# Streaming events (SSE-friendly)
# ---------------------------------------------------------------------------


class BuildEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    build_id: str
    kind: BuildEventKind
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Final result
# ---------------------------------------------------------------------------


class SubtaskOutcome(BaseModel):
    subtask_id: str
    status: SubtaskStatus
    adapter: AdapterChoice
    model: str | None = None
    duration_ms: int = 0
    llm_calls: int = 0
    estimated_cost_usd: float | None = None
    notes: str | None = None


class BudgetSnapshot(BaseModel):
    runtime_minutes_used: float = 0.0
    llm_calls_used: int = 0
    cost_usd_used: float = 0.0
    runtime_exhausted: bool = False
    calls_exhausted: bool = False
    cost_exhausted: bool = False


class CodeBuildResult(BaseModel):
    """End-of-build summary."""

    build_id: str
    status: CodeBuildStatus
    workspace_dir: str
    artifact_path: str | None = None
    """Absolute path to the packaged tar.gz, set on `completed` / `partial`."""

    subtasks: list[SubtaskOutcome] = Field(default_factory=list)
    budget: BudgetSnapshot = Field(default_factory=BudgetSnapshot)
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def workspace_for_build(local_storage_dir: Path, build_id: str) -> Path:
    """Canonical workspace directory for a build_id.

    Centralised here so adapters and the director resolve the path identically.
    """
    return (local_storage_dir / "workspaces" / "code_builds" / build_id).resolve()

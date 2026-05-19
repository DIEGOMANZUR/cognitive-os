"""Code Director core loop.

The director consumes a `CodeBuildRequest`, produces a `BuildPlan`, and
runs the plan by dispatching each subtask to a `CodingAgentAdapter`. It
emits `BuildEvent`s along the way and respects the operator's `BudgetSpec`
hard limits.

This module is pure logic: no DB writes, no FastAPI, no Celery. The
service layer (`service.py`) wraps it with persistence, HITL approvals and
SSE streaming so the loop here stays unit-testable in milliseconds.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from cognitive_os.code_director.adapters.base import (
    AdapterRegistry,
    CodingAgentAdapter,
)
from cognitive_os.code_director.prompt_builder import build_subtask_prompt
from cognitive_os.code_director.schemas import (
    AdapterChoice,
    BudgetSnapshot,
    BudgetSpec,
    BuildEvent,
    BuildEventKind,
    BuildPlan,
    CodeBuildRequest,
    CodeBuildResult,
    CodeBuildStatus,
    StepResult,
    SubtaskOutcome,
    SubtaskSpec,
    workspace_for_build,
)

EventSink = Callable[[BuildEvent], None]


class DirectorError(RuntimeError):
    """Raised when the director cannot produce a plan or dispatch a subtask."""


# Planning lives in `code_director/planner.py` (HeuristicPlanner +
# LLMPlanner). The director only holds a `planner` callable so it stays
# testable without an LLM.

# ---------------------------------------------------------------------------
# Execution loop
# ---------------------------------------------------------------------------


class _BudgetTracker:
    """Single-build accounting; raises a sentinel when any cap is hit."""

    def __init__(self, spec: BudgetSpec, *, mode: str = "soft") -> None:
        self._spec = spec
        # "soft" (default) = budget is a guideline; the build ends `partial`
        # between subtasks but a subtask is never killed mid-call.
        # "hard" = callers gate every adapter call on status() first.
        self.mode = mode if mode in {"soft", "hard"} else "soft"
        self._started_at = time.monotonic()
        self.snapshot = BudgetSnapshot()

    def record(self, *, calls: int = 0, cost_usd: float = 0.0) -> None:
        self.snapshot.runtime_minutes_used = (time.monotonic() - self._started_at) / 60.0
        self.snapshot.llm_calls_used += calls
        self.snapshot.cost_usd_used += cost_usd

    def status(self) -> tuple[bool, str | None]:
        """Return (within_budget, reason_if_exceeded).

        Recomputes elapsed runtime so a *pre-call* check (hard mode) is
        accurate even when no `record()` happened since the last call.
        """
        self.snapshot.runtime_minutes_used = (time.monotonic() - self._started_at) / 60.0
        if self.snapshot.runtime_minutes_used >= self._spec.max_runtime_minutes:
            self.snapshot.runtime_exhausted = True
            return False, "runtime_exhausted"
        if self.snapshot.llm_calls_used >= self._spec.max_total_llm_calls:
            self.snapshot.calls_exhausted = True
            return False, "calls_exhausted"
        cap = self._spec.max_total_cost_usd
        if cap is not None and self.snapshot.cost_usd_used >= cap:
            self.snapshot.cost_exhausted = True
            return False, "cost_exhausted"
        return True, None

    def remaining_runtime_seconds(self) -> float:
        """Seconds left under the runtime cap, recomputed live (>=0)."""
        elapsed_minutes = (time.monotonic() - self._started_at) / 60.0
        remaining_minutes = max(0.0, self._spec.max_runtime_minutes - elapsed_minutes)
        return remaining_minutes * 60.0


def _topological_order(subtasks: list[SubtaskSpec]) -> list[SubtaskSpec]:
    """Stable topological sort. Raises `DirectorError` on cycles or unknown deps."""
    by_id = {s.subtask_id: s for s in subtasks}
    remaining = {s.subtask_id: set(s.depends_on) for s in subtasks}
    for deps in remaining.values():
        for dep in deps:
            if dep not in by_id:
                msg = f"Subtask references unknown dependency: {dep}"
                raise DirectorError(msg)
    order: list[SubtaskSpec] = []
    pending = list(subtasks)  # preserve original order for stability
    while pending:
        progress = False
        next_pending: list[SubtaskSpec] = []
        for s in pending:
            if not remaining[s.subtask_id]:
                order.append(s)
                progress = True
                for r in remaining.values():
                    r.discard(s.subtask_id)
            else:
                next_pending.append(s)
        pending = next_pending
        if not progress and pending:
            msg = "Subtask plan has a dependency cycle: " + ", ".join(s.subtask_id for s in pending)
            raise DirectorError(msg)
    return order


class CodeDirector:
    """Plans + runs a code-build using injected coding-agent adapters."""

    def __init__(
        self,
        *,
        adapters: AdapterRegistry,
        local_storage_dir: Path,
        planner: Callable[[CodeBuildRequest, Path], BuildPlan] | None = None,
    ) -> None:
        self._adapters = adapters
        self._local_storage_dir = local_storage_dir
        if planner is not None:
            self._planner = planner
        else:
            # Default: LLM-driven planner with deterministic heuristic
            # fallback (no key / circuit open / bad JSON -> heuristic).
            from cognitive_os.code_director.planner import (  # noqa: PLC0415
                default_planner,
            )

            _p = default_planner()
            self._planner = lambda req, ws: _p.plan(req, workspace_dir=ws)

    # ---- planning surface -------------------------------------------------

    def make_build_id(self) -> str:
        return f"cb-{uuid4()}"

    def plan(self, request: CodeBuildRequest, *, build_id: str) -> BuildPlan:
        workspace = workspace_for_build(self._local_storage_dir, build_id)
        # Don't create the directory here — the service layer does that
        # *after* the operator approves the plan, so a rejected plan never
        # touches disk.
        return self._planner(request, workspace)

    # ---- execution surface ------------------------------------------------

    def run(
        self,
        request: CodeBuildRequest,
        plan: BuildPlan,
        *,
        build_id: str,
        emit: EventSink | None = None,
    ) -> CodeBuildResult:
        """Execute the plan. The caller persists the result + events."""
        sink = emit or (lambda _ev: None)
        workspace = Path(plan.workspace_dir)
        workspace.mkdir(parents=True, exist_ok=True)
        from cognitive_os.core.config import settings as _settings  # noqa: PLC0415

        tracker = _BudgetTracker(request.budget, mode=_settings.code_director_budget_mode)
        started_at = datetime.now(UTC)
        outcomes: list[SubtaskOutcome] = []
        status: CodeBuildStatus = "running"
        error: str | None = None

        sink(
            BuildEvent(
                build_id=build_id,
                kind="build_started",
                payload={"plan": plan.model_dump(mode="json")},
            )
        )

        try:
            ordered = _topological_order(plan.subtasks)
        except DirectorError as exc:
            return CodeBuildResult(
                build_id=build_id,
                status="failed",
                workspace_dir=str(workspace),
                error=str(exc),
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )

        # Map of subtask_id -> outcome status, used for downstream skip logic.
        completed: dict[str, SubtaskOutcome] = {}
        # Map of subtask_id -> (spec, last StepResult) so a subtask can be
        # prompted with what its dependencies actually produced (F9b).
        prior_results: dict[str, tuple[SubtaskSpec, StepResult]] = {}
        for subtask in ordered:
            # Skip if any dependency failed.
            blocked = [
                d
                for d in subtask.depends_on
                if completed.get(d) and completed[d].status != "completed"
            ]
            if blocked:
                outcome = SubtaskOutcome(
                    subtask_id=subtask.subtask_id,
                    status="skipped",
                    adapter=subtask.adapter,
                    model=subtask.model,
                    notes=f"Skipped because dependencies failed: {', '.join(blocked)}",
                )
                outcomes.append(outcome)
                completed[subtask.subtask_id] = outcome
                continue

            upstream = [prior_results[d] for d in subtask.depends_on if d in prior_results]
            outcome, last = self._run_subtask(
                build_id=build_id,
                subtask=subtask,
                workspace=workspace,
                request=request,
                tracker=tracker,
                emit=sink,
                upstream=upstream,
            )
            outcomes.append(outcome)
            completed[subtask.subtask_id] = outcome
            if last is not None:
                prior_results[subtask.subtask_id] = (subtask, last)

            within, reason = tracker.status()
            if not within:
                sink(
                    BuildEvent(
                        build_id=build_id, kind="budget_exceeded", payload={"reason": reason}
                    )
                )
                status = "partial"
                error = f"Budget exceeded: {reason}"
                break

        if status == "running":
            failed = [o for o in outcomes if o.status == "failed"]
            status = "completed" if not failed else "failed"
            if failed:
                error = f"{len(failed)} subtask(s) failed: " + ", ".join(
                    o.subtask_id for o in failed
                )

        finished_at = datetime.now(UTC)
        # Map the build's final status to a precise event kind so the timeline
        # tells the truth. Pre-Fase 71 anything that wasn't `completed`/
        # `failed` was emitted as `build_cancelled` — including soft-budget
        # `partial` runs, which is misleading. (Fase 71 P2.K.9.)
        event_kind: BuildEventKind
        if status == "completed":
            event_kind = "build_completed"
        elif status == "failed":
            event_kind = "build_failed"
        elif status == "partial":
            event_kind = "build_partial"
        else:
            event_kind = "build_cancelled"
        sink(
            BuildEvent(
                build_id=build_id,
                kind=event_kind,
                payload={"status": status},
            )
        )

        return CodeBuildResult(
            build_id=build_id,
            status=status,
            workspace_dir=str(workspace),
            subtasks=outcomes,
            budget=tracker.snapshot,
            error=error,
            started_at=started_at,
            finished_at=finished_at,
        )

    # ---- per-subtask --------------------------------------------------------

    def _run_subtask(
        self,
        *,
        build_id: str,
        subtask: SubtaskSpec,
        workspace: Path,
        request: CodeBuildRequest,
        tracker: _BudgetTracker,
        emit: EventSink,
        upstream: list[tuple[SubtaskSpec, StepResult]] | None = None,
    ) -> tuple[SubtaskOutcome, StepResult | None]:
        upstream = upstream or []
        adapter = self._adapters.get(subtask.adapter)
        if adapter is None or not adapter.is_available():
            emit(
                BuildEvent(
                    build_id=build_id,
                    kind="subtask_finished",
                    payload={
                        "subtask_id": subtask.subtask_id,
                        "status": "failed",
                        "reason": f"adapter unavailable: {subtask.adapter}",
                    },
                )
            )
            return (
                SubtaskOutcome(
                    subtask_id=subtask.subtask_id,
                    status="failed",
                    adapter=subtask.adapter,
                    model=subtask.model,
                    notes=f"Adapter {subtask.adapter} is unavailable on this host.",
                ),
                None,
            )

        emit(
            BuildEvent(
                build_id=build_id,
                kind="subtask_started",
                payload={
                    "subtask_id": subtask.subtask_id,
                    "adapter": subtask.adapter,
                    "model": subtask.model,
                    "role": subtask.role,
                },
            )
        )

        session = adapter.start_session(
            workspace=workspace,
            objective=subtask.title,
            model=subtask.model,
        )
        calls_this_subtask = 0
        cost_this_subtask = 0.0
        last_result: StepResult | None = None
        try:
            for _iteration in range(request.budget.max_calls_per_subtask):
                # The prompt is rebuilt every iteration: it injects the live
                # workspace + upstream outputs (F9b) and, on a retry, the
                # previous attempt's error so the agent corrects instead of
                # replaying the same failing approach (F9c).
                prompt = build_subtask_prompt(
                    subtask=subtask,
                    request=request,
                    workspace=workspace,
                    upstream=upstream,
                    attempt=_iteration,
                    last_result=last_result,
                )
                emit(
                    BuildEvent(
                        build_id=build_id,
                        kind="adapter_invocation",
                        payload={
                            "subtask_id": subtask.subtask_id,
                            "adapter": subtask.adapter,
                            "model": subtask.model,
                            "prompt_chars": len(prompt),
                        },
                    )
                )
                if tracker.mode == "hard":
                    # Gate BEFORE spending the call: in hard mode an exceeded
                    # cap aborts the subtask immediately (no extra cost).
                    within_pre, reason_pre = tracker.status()
                    if not within_pre:
                        emit(
                            BuildEvent(
                                build_id=build_id,
                                kind="budget_exceeded",
                                payload={
                                    "subtask_id": subtask.subtask_id,
                                    "reason": reason_pre,
                                    "phase": "pre_call",
                                },
                            )
                        )
                        break
                # Hard mode: cap the subprocess wall-clock to whatever runtime
                # is left in the budget. Soft mode keeps the adapter default
                # (600s) so a long-running subtask is never killed mid-flight.
                if tracker.mode == "hard":
                    effective_timeout = min(600.0, tracker.remaining_runtime_seconds())
                    if effective_timeout <= 0.0:
                        emit(
                            BuildEvent(
                                build_id=build_id,
                                kind="budget_exceeded",
                                payload={
                                    "subtask_id": subtask.subtask_id,
                                    "reason": "runtime_exhausted",
                                    "phase": "pre_call_timeout_zero",
                                },
                            )
                        )
                        break
                    result = adapter.send_prompt(session, prompt, timeout_seconds=effective_timeout)
                else:
                    result = adapter.send_prompt(session, prompt)
                last_result = result
                calls_this_subtask += 1
                cost_this_subtask += result.estimated_cost_usd or 0.0
                tracker.record(calls=1, cost_usd=result.estimated_cost_usd or 0.0)
                if result.success or not request.iterate_until_tests_pass:
                    break
                within, _ = tracker.status()
                if not within:
                    break
        finally:
            adapter.cleanup(session)

        success = bool(last_result and last_result.success)
        emit(
            BuildEvent(
                build_id=build_id,
                kind="subtask_finished",
                payload={
                    "subtask_id": subtask.subtask_id,
                    "status": "completed" if success else "failed",
                    "llm_calls": calls_this_subtask,
                    "cost_usd": cost_this_subtask,
                },
            )
        )
        return (
            SubtaskOutcome(
                subtask_id=subtask.subtask_id,
                status="completed" if success else "failed",
                adapter=subtask.adapter,
                model=subtask.model,
                duration_ms=last_result.duration_ms if last_result else 0,
                llm_calls=calls_this_subtask,
                estimated_cost_usd=cost_this_subtask,
                notes=last_result.error if last_result and last_result.error else None,
            ),
            last_result,
        )


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------


def default_registry() -> AdapterRegistry:
    """Return the production adapter registry.

    Each adapter is constructed lazily so unavailable CLIs do not crash
    import. The fake adapter is intentionally **not** included here —
    tests build their own registry. The director's preflight calls
    `is_available()` on each, so an adapter whose binary/stack is missing
    is reported (not crashed) and the operator is told before approving.
    """
    from cognitive_os.code_director.adapters.claude_code import ClaudeCodeAdapter
    from cognitive_os.code_director.adapters.codex import CodexAdapter
    from cognitive_os.code_director.adapters.deepagent import DeepAgentAdapter
    from cognitive_os.code_director.adapters.kimi import KimiAdapter

    registry: AdapterRegistry = {
        "deepagent": DeepAgentAdapter(),
        "claude_code": ClaudeCodeAdapter(),
        "codex": CodexAdapter(),
        "kimi": KimiAdapter(),
    }
    return registry


def adapter_or_raise(registry: AdapterRegistry, choice: AdapterChoice) -> CodingAgentAdapter:
    adapter = registry.get(choice)
    if adapter is None:
        msg = f"No adapter registered for {choice!r}"
        raise DirectorError(msg)
    return adapter

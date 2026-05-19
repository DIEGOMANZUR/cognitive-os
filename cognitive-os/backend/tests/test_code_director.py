"""Regression for the Code Director loop (F1: schemas + Protocol + FakeAdapter).

The director plans a `CodeBuildRequest` into a `BuildPlan` and dispatches
each subtask through a `CodingAgentAdapter`. F1 tests cover only the
in-memory loop using `FakeAdapter`; later phases add real-adapter tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cognitive_os.code_director.adapters.fake import FakeAdapter
from cognitive_os.code_director.director import (
    CodeDirector,
    DirectorError,
    _topological_order,
)
from cognitive_os.code_director.planner import HeuristicPlanner
from cognitive_os.code_director.schemas import (
    AdapterPreference,
    AgentSession,
    BudgetSpec,
    BuildEvent,
    CodeBuildRequest,
    StepResult,
    SubtaskSpec,
)


def _request(**overrides: object) -> CodeBuildRequest:
    """Build a minimal valid CodeBuildRequest for tests."""
    base: dict[str, object] = {
        "objective": "Build a tiny CLI tool with tests" + " " * 100,
        "adapter_preference": AdapterPreference(default_adapter="fake"),
    }
    base.update(overrides)
    return CodeBuildRequest(**base)


def _director(adapter: FakeAdapter, tmp_path: Path) -> CodeDirector:
    # Pin the heuristic planner: these tests assert the deterministic
    # scaffold→implement→review shape and must never touch a real LLM.
    hp = HeuristicPlanner()
    return CodeDirector(
        adapters={"fake": adapter},
        local_storage_dir=tmp_path,
        planner=lambda req, ws: hp.plan(req, workspace_dir=ws),
    )


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


def test_heuristic_plan_emits_three_subtasks_by_default(tmp_path: Path) -> None:
    d = _director(FakeAdapter(), tmp_path)
    plan = d.plan(_request(), build_id="cb-test-1")
    assert [s.subtask_id for s in plan.subtasks] == ["st-scaffold", "st-implement", "st-review"]
    assert plan.subtasks[1].depends_on == ["st-scaffold"]
    assert plan.subtasks[2].depends_on == ["st-implement"]


def test_heuristic_plan_adds_sandbox_test_when_requested(tmp_path: Path) -> None:
    d = _director(FakeAdapter(), tmp_path)
    plan = d.plan(_request(run_tests_in_sandbox=True), build_id="cb-test-2")
    ids = [s.subtask_id for s in plan.subtasks]
    assert "st-test" in ids
    assert plan.subtasks[-1].depends_on == ["st-review"]


def test_plan_respects_per_role_adapter_override(tmp_path: Path) -> None:
    pref = AdapterPreference(
        default_adapter="fake",
        reviewer_adapter="fake",
        reviewer_model="reviewer-model",
        coder_adapter="fake",
        coder_model="coder-model",
    )
    d = _director(FakeAdapter(), tmp_path)
    plan = d.plan(_request(adapter_preference=pref), build_id="cb-test-3")
    assert plan.subtasks[0].model == "coder-model"
    assert plan.subtasks[2].model == "reviewer-model"


# ---------------------------------------------------------------------------
# Topological order
# ---------------------------------------------------------------------------


def test_topological_order_resolves_dependencies() -> None:
    specs = [
        SubtaskSpec(
            subtask_id="c",
            title="c",
            description="c",
            role="reviewer",
            adapter="fake",
            depends_on=["a", "b"],
        ),
        SubtaskSpec(
            subtask_id="b",
            title="b",
            description="b",
            role="coder",
            adapter="fake",
            depends_on=["a"],
        ),
        SubtaskSpec(subtask_id="a", title="a", description="a", role="coder", adapter="fake"),
    ]
    order = [s.subtask_id for s in _topological_order(specs)]
    assert order == ["a", "b", "c"]


def test_topological_order_rejects_cycles() -> None:
    specs = [
        SubtaskSpec(
            subtask_id="a",
            title="a",
            description="a",
            role="coder",
            adapter="fake",
            depends_on=["b"],
        ),
        SubtaskSpec(
            subtask_id="b",
            title="b",
            description="b",
            role="coder",
            adapter="fake",
            depends_on=["a"],
        ),
    ]
    with pytest.raises(DirectorError, match="cycle"):
        _topological_order(specs)


def test_topological_order_rejects_unknown_dependency() -> None:
    specs = [
        SubtaskSpec(
            subtask_id="a",
            title="a",
            description="a",
            role="coder",
            adapter="fake",
            depends_on=["ghost"],
        ),
    ]
    with pytest.raises(DirectorError, match="unknown dependency"):
        _topological_order(specs)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def test_run_completes_happy_path(tmp_path: Path) -> None:
    fake = FakeAdapter()
    d = _director(fake, tmp_path)
    req = _request()
    bid = d.make_build_id()
    plan = d.plan(req, build_id=bid)
    events: list[BuildEvent] = []
    result = d.run(req, plan, build_id=bid, emit=events.append)

    assert result.status == "completed"
    assert all(o.status == "completed" for o in result.subtasks)
    assert {e.kind for e in events} >= {
        "build_started",
        "build_completed",
        "subtask_started",
        "subtask_finished",
    }
    # Workspace was created on the disk.
    assert Path(result.workspace_dir).exists()


def test_run_records_budget_usage_per_call(tmp_path: Path) -> None:
    fake = FakeAdapter()
    d = _director(fake, tmp_path)
    req = _request()
    bid = d.make_build_id()
    plan = d.plan(req, build_id=bid)
    result = d.run(req, plan, build_id=bid)
    # One call per subtask in F1 happy path.
    assert result.budget.llm_calls_used == len(plan.subtasks)


def test_run_stops_when_call_budget_exceeded(tmp_path: Path) -> None:
    # Force a 1-call total budget; the first subtask consumes it, the rest skip.
    fake = FakeAdapter()
    d = _director(fake, tmp_path)
    req = _request(budget=BudgetSpec(max_total_llm_calls=1, max_calls_per_subtask=1))
    bid = d.make_build_id()
    plan = d.plan(req, build_id=bid)
    events: list[BuildEvent] = []
    result = d.run(req, plan, build_id=bid, emit=events.append)
    assert result.status == "partial"
    assert result.budget.calls_exhausted is True
    assert any(e.kind == "budget_exceeded" for e in events)


def test_run_skips_subtasks_whose_dependency_failed(tmp_path: Path) -> None:
    def responder(_session: AgentSession, _prompt: str) -> StepResult:
        return StepResult(success=False, error="simulated failure", stdout="")

    fake = FakeAdapter(responder=responder)
    d = _director(fake, tmp_path)
    # Disable iteration to keep failures deterministic.
    req = _request(iterate_until_tests_pass=False)
    bid = d.make_build_id()
    plan = d.plan(req, build_id=bid)
    result = d.run(req, plan, build_id=bid)
    # First fails, dependents skip.
    assert result.subtasks[0].status == "failed"
    assert result.subtasks[1].status == "skipped"
    assert result.subtasks[2].status == "skipped"
    assert result.status == "failed"


def test_run_marks_failed_when_adapter_unavailable(tmp_path: Path) -> None:
    fake = FakeAdapter(available=False)
    d = _director(fake, tmp_path)
    req = _request(iterate_until_tests_pass=False)
    bid = d.make_build_id()
    plan = d.plan(req, build_id=bid)
    result = d.run(req, plan, build_id=bid)
    assert result.status == "failed"
    assert result.subtasks[0].status == "failed"
    assert "unavailable" in (result.subtasks[0].notes or "")


def test_run_iterates_until_success_within_budget(tmp_path: Path) -> None:
    """When `iterate_until_tests_pass=True`, a subtask retries until the
    adapter returns success or the per-subtask budget is hit."""
    state = {"attempts": 0}

    def responder(_session: AgentSession, _prompt: str) -> StepResult:
        state["attempts"] += 1
        return StepResult(success=state["attempts"] >= 3, stdout="ok")

    fake = FakeAdapter(responder=responder)
    d = _director(fake, tmp_path)
    req = _request(
        iterate_until_tests_pass=True,
        budget=BudgetSpec(max_total_llm_calls=20, max_calls_per_subtask=5),
    )
    bid = d.make_build_id()
    plan = d.plan(req, build_id=bid)
    # Limit to one subtask so the assertion is unambiguous.
    plan.subtasks = plan.subtasks[:1]
    result = d.run(req, plan, build_id=bid)
    assert result.status == "completed"
    assert result.subtasks[0].llm_calls == 3


# -- Fase 69 P0.5 — Budget hard timeout effective at the subprocess ----------


def test_budget_tracker_remaining_runtime_seconds_clamps_to_zero() -> None:
    """`remaining_runtime_seconds()` never returns a negative value, so a
    blown budget produces timeout=0 and the caller short-circuits."""
    import time as _time  # noqa: PLC0415

    from cognitive_os.code_director.director import _BudgetTracker  # noqa: PLC0415

    spec = BudgetSpec(max_runtime_minutes=1, max_total_llm_calls=10)
    tracker = _BudgetTracker(spec, mode="hard")
    # Force elapsed > spec by rewinding `_started_at` two minutes back.
    tracker._started_at = _time.monotonic() - 120.0
    assert tracker.remaining_runtime_seconds() == 0.0


def test_budget_hard_passes_clamped_timeout_to_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `code_director_budget_mode='hard'` the director must forward
    `timeout_seconds` to `send_prompt` clamped to the runtime remaining (not
    the 600s default)."""
    from cognitive_os.code_director.director import AdapterRegistry  # noqa: PLC0415
    from cognitive_os.code_director.schemas import (  # noqa: PLC0415
        CodeBuildRequest,
    )

    received_timeouts: list[float] = []

    class TimeoutCapturingAdapter(FakeAdapter):
        def send_prompt(
            self,
            session: object,
            prompt: str,
            *,
            timeout_seconds: float = 600.0,
        ) -> StepResult:
            received_timeouts.append(timeout_seconds)
            return super().send_prompt(session, prompt, timeout_seconds=timeout_seconds)

    # The director re-imports `settings` inside `_run_subtasks`. Patch the
    # canonical Settings instance attribute so the import picks up our value.
    from cognitive_os.core.config import settings as _runtime_settings  # noqa: PLC0415

    monkeypatch.setattr(_runtime_settings, "code_director_budget_mode", "hard")

    adapter = TimeoutCapturingAdapter()
    registry = AdapterRegistry({"fake": adapter})
    d = CodeDirector(adapters=registry, local_storage_dir=Path("/tmp"))
    req = CodeBuildRequest(
        objective="hard budget timeout" + " " * 100,
        budget=BudgetSpec(max_runtime_minutes=2, max_total_llm_calls=3),
        adapter_preference=AdapterPreference(default_adapter="fake"),
    )
    plan = HeuristicPlanner().plan(req, workspace_dir=Path("/tmp"))
    plan.subtasks = plan.subtasks[:1]
    d.run(req, plan, build_id="test-budget-hard")

    assert received_timeouts, "send_prompt must be called at least once in hard mode"
    # 2 minutes budget = 120s; subprocess default cap is 600s → min(600, ~120)
    assert 0.0 < received_timeouts[0] <= 120.0

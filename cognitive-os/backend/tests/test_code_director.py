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
    return CodeDirector(adapters={"fake": adapter}, local_storage_dir=tmp_path)


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

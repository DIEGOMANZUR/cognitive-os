"""F9a regression: LLM-driven planner with heuristic fallback.

The LLM is injected as a deterministic stub so these tests never spend a
token. We verify: real decomposition from valid JSON, fenced-JSON
extraction, hallucinated-dependency pruning, role/adapter assignment,
subtask cap, and fallback-to-heuristic on every failure mode.
"""

from __future__ import annotations

from pathlib import Path

from cognitive_os.code_director.planner import (
    HeuristicPlanner,
    LLMPlanner,
    _extract_json,
)
from cognitive_os.code_director.schemas import AdapterPreference, CodeBuildRequest


def _request(**ov: object) -> CodeBuildRequest:
    base: dict[str, object] = {
        "objective": "Build an app with two RAGs and a Next.js frontend" + " " * 40,
        "adapter_preference": AdapterPreference(
            default_adapter="claude_code",
            default_model="claude-opus-4-7",
            reviewer_adapter="codex",
            reviewer_model="gpt-5-codex",
        ),
    }
    base.update(ov)
    return CodeBuildRequest(**base)


# ---- heuristic still works -------------------------------------------------


def test_heuristic_planner_three_stages(tmp_path: Path) -> None:
    plan = HeuristicPlanner().plan(_request(), workspace_dir=tmp_path)
    assert [s.subtask_id for s in plan.subtasks] == [
        "st-scaffold",
        "st-implement",
        "st-review",
    ]


def test_heuristic_planner_adds_test_stage(tmp_path: Path) -> None:
    plan = HeuristicPlanner().plan(_request(run_tests_in_sandbox=True), workspace_dir=tmp_path)
    assert plan.subtasks[-1].subtask_id == "st-test"
    assert plan.subtasks[-1].role == "tester"


# ---- JSON extraction -------------------------------------------------------


def test_extract_json_plain() -> None:
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_prose_and_fence() -> None:
    raw = 'Sure! Here is the plan:\n```json\n{"subtasks": []}\n```\nDone.'
    assert _extract_json(raw) == {"subtasks": []}


def test_extract_json_balanced_nested() -> None:
    raw = 'prefix {"a": {"b": [1,2]}, "c": 3} suffix'
    assert _extract_json(raw) == {"a": {"b": [1, 2]}, "c": 3}


# ---- LLM planner: happy path ----------------------------------------------


def test_llm_planner_decomposes_from_valid_json(tmp_path: Path) -> None:
    llm_json = """
    {
      "subtasks": [
        {"subtask_id": "schema", "title": "DB schema",
         "description": "SQLAlchemy models", "role": "coder",
         "depends_on": [], "expected_paths": ["models.py"]},
        {"subtask_id": "rag1", "title": "RAG transactions",
         "description": "index tx", "role": "coder",
         "depends_on": ["schema"]},
        {"subtask_id": "final-review", "title": "Review",
         "description": "check everything", "role": "reviewer",
         "depends_on": ["rag1"]}
      ],
      "rationale": "schema first, then RAG, then review"
    }
    """
    planner = LLMPlanner(llm_completion=lambda _p: llm_json)
    plan = planner.plan(_request(), workspace_dir=tmp_path)

    assert [s.subtask_id for s in plan.subtasks] == ["schema", "rag1", "final-review"]
    # Per-role adapter assignment from AdapterPreference.
    assert plan.subtasks[0].adapter == "claude_code"
    assert plan.subtasks[2].adapter == "codex"  # reviewer override
    assert plan.subtasks[2].model == "gpt-5-codex"
    assert plan.subtasks[1].depends_on == ["schema"]
    assert "schema first" in plan.rationale


def test_llm_planner_prunes_hallucinated_dependencies(tmp_path: Path) -> None:
    llm_json = """
    {"subtasks": [
      {"subtask_id": "a", "title": "A", "description": "a", "role": "coder",
       "depends_on": ["ghost", "a"]},
      {"subtask_id": "b", "title": "B", "description": "b", "role": "reviewer",
       "depends_on": ["a"]}
    ], "rationale": "x"}
    """
    planner = LLMPlanner(llm_completion=lambda _p: llm_json)
    plan = planner.plan(_request(), workspace_dir=tmp_path)
    # 'ghost' (unknown) and self-dep 'a' are pruned; 'a' kept for b.
    assert plan.subtasks[0].depends_on == []
    assert plan.subtasks[1].depends_on == ["a"]


def test_llm_planner_caps_subtasks_at_12(tmp_path: Path) -> None:
    many = ",".join(
        f'{{"subtask_id":"s{i}","title":"t","description":"d","role":"coder"}}' for i in range(20)
    )
    planner = LLMPlanner(llm_completion=lambda _p: f'{{"subtasks":[{many}]}}')
    plan = planner.plan(_request(), workspace_dir=tmp_path)
    assert len(plan.subtasks) == 12


def test_llm_planner_keeps_tail_reviewer_when_truncating(tmp_path: Path) -> None:
    """The cap must not drop the reviewer if the LLM put it at the tail."""
    head = ",".join(
        f'{{"subtask_id":"s{i}","title":"t","description":"d","role":"coder"}}' for i in range(14)
    )
    reviewer = (
        '{"subtask_id":"final-qa","title":"QA","description":"check",'
        '"role":"reviewer","depends_on":["s13"]}'
    )
    planner = LLMPlanner(llm_completion=lambda _p: f'{{"subtasks":[{head},{reviewer}]}}')
    plan = planner.plan(_request(), workspace_dir=tmp_path)
    assert len(plan.subtasks) == 12
    # The reviewer survived the truncation and is the last subtask.
    assert plan.subtasks[-1].subtask_id == "final-qa"
    assert plan.subtasks[-1].role == "reviewer"


# ---- LLM planner: fallback paths ------------------------------------------


def test_llm_planner_falls_back_when_llm_unavailable(tmp_path: Path) -> None:
    # llm_completion=None and no real model resolvable in this seam: we
    # force unavailability by injecting a resolver that returns None via a
    # planner whose _resolve_llm yields None (simulated by raising in stub).
    def boom(_p: str) -> str:
        raise RuntimeError("no key")

    planner = LLMPlanner(llm_completion=boom, fallback=HeuristicPlanner())
    plan = planner.plan(_request(), workspace_dir=tmp_path)
    # Heuristic shape proves the fallback fired.
    assert [s.subtask_id for s in plan.subtasks] == [
        "st-scaffold",
        "st-implement",
        "st-review",
    ]


def test_llm_planner_falls_back_on_malformed_json(tmp_path: Path) -> None:
    planner = LLMPlanner(
        llm_completion=lambda _p: "not json at all, sorry",
        fallback=HeuristicPlanner(),
    )
    plan = planner.plan(_request(), workspace_dir=tmp_path)
    assert plan.subtasks[0].subtask_id == "st-scaffold"


def test_llm_planner_falls_back_on_empty_subtasks(tmp_path: Path) -> None:
    planner = LLMPlanner(
        llm_completion=lambda _p: '{"subtasks": [], "rationale": "x"}',
        fallback=HeuristicPlanner(),
    )
    plan = planner.plan(_request(), workspace_dir=tmp_path)
    assert plan.subtasks[0].subtask_id == "st-scaffold"

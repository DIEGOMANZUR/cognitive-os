"""F9 smoke E2E: LLM-driven plan + context-aware prompts, end to end.

Proves the F9 capability difference without spending a token:

1. With the LLM planner (injected deterministic stub) the director runs
   the LLM's *custom* decomposition — not the fixed heuristic
   scaffold→implement→review shape.
2. The prompt each subtask's adapter receives carries live workspace
   state and what upstream subtasks produced (F9b), and a failed first
   attempt yields a *different*, error-directed retry prompt (F9c).

A real coding CLI is replaced by a fake adapter that writes files and
records every prompt it was handed, so the whole director→planner→
prompt-builder→adapter→workspace path is exercised offline.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from cognitive_os.code_director.adapters.base import CodingAgentAdapter
from cognitive_os.code_director.director import CodeDirector
from cognitive_os.code_director.planner import HeuristicPlanner, LLMPlanner
from cognitive_os.code_director.schemas import (
    AdapterPreference,
    AgentSession,
    BudgetSpec,
    CodeBuildRequest,
    StepResult,
)

_LLM_PLAN = """
{
  "subtasks": [
    {"subtask_id": "db", "title": "Design DB schema",
     "description": "SQLAlchemy models for the two RAG corpora",
     "role": "coder", "depends_on": [], "expected_paths": ["models.py"]},
    {"subtask_id": "rag-a", "title": "Build RAG A",
     "description": "ingest + retrieve corpus A", "role": "coder",
     "depends_on": ["db"]},
    {"subtask_id": "rag-b", "title": "Build RAG B",
     "description": "ingest + retrieve corpus B", "role": "coder",
     "depends_on": ["db"]},
    {"subtask_id": "api", "title": "FastAPI surface",
     "description": "wire both RAGs behind /ask", "role": "coder",
     "depends_on": ["rag-a", "rag-b"]},
    {"subtask_id": "qa", "title": "Final review",
     "description": "verify the whole build", "role": "reviewer",
     "depends_on": ["api"]}
  ],
  "rationale": "schema first; the two RAGs are independent; API joins them"
}
"""


class _RecordingAdapter(CodingAgentAdapter):
    """Writes a file per subtask and records every prompt it received."""

    name = "fake"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def is_available(self) -> bool:
        return True

    def start_session(
        self, *, workspace: Path, objective: str, model: str | None = None
    ) -> AgentSession:
        del objective, model
        return AgentSession(
            session_id=str(uuid4()),
            adapter="fake",
            workspace=str(workspace),
            state={"n": 0},
        )

    def send_prompt(
        self, session: AgentSession, prompt: str, *, timeout_seconds: float = 600.0
    ) -> StepResult:
        del timeout_seconds
        self.prompts.append(prompt)
        ws = Path(session.workspace)
        ws.mkdir(parents=True, exist_ok=True)
        n = int(session.state.get("n", 0)) + 1
        session.state["n"] = n
        target = ws / f"step_{n}.py"
        target.write_text(f"# step {n}\n")
        return StepResult(success=True, stdout=f"wrote {target.name}", files_touched=[target.name])

    def cleanup(self, session: AgentSession) -> None:
        del session


def _request() -> CodeBuildRequest:
    return CodeBuildRequest(
        objective="Build an app with two RAGs and a FastAPI surface" + " " * 40,
        adapter_preference=AdapterPreference(default_adapter="fake"),
    )


def test_llm_plan_runs_custom_decomposition_not_heuristic(tmp_path: Path) -> None:
    adapter = _RecordingAdapter()
    director = CodeDirector(
        adapters={"fake": adapter},
        local_storage_dir=tmp_path,
        planner=lambda req, ws: LLMPlanner(llm_completion=lambda _p: _LLM_PLAN).plan(
            req, workspace_dir=ws
        ),
    )
    req = _request()
    bid = director.make_build_id()
    plan = director.plan(req, build_id=bid)

    # The LLM's custom shape, NOT the heuristic scaffold/implement/review.
    assert [s.subtask_id for s in plan.subtasks] == [
        "db",
        "rag-a",
        "rag-b",
        "api",
        "qa",
    ]
    heuristic = HeuristicPlanner().plan(req, workspace_dir=tmp_path)
    assert [s.subtask_id for s in plan.subtasks] != [s.subtask_id for s in heuristic.subtasks]

    result = director.run(req, plan, build_id=bid)
    assert result.status == "completed"
    assert all(o.status == "completed" for o in result.subtasks)

    # F9b: a downstream subtask's prompt sees upstream outputs + workspace.
    api_prompt = adapter.prompts[3]
    assert "CURRENT WORKSPACE FILES:" in api_prompt
    assert "WHAT UPSTREAM SUBTASKS PRODUCED" in api_prompt
    assert "rag-a" in api_prompt and "rag-b" in api_prompt


def test_failed_first_attempt_produces_error_directed_retry(tmp_path: Path) -> None:
    """F9c end-to-end: the retry prompt differs and carries the error."""
    state = {"n": 0}

    class _FlakyAdapter(_RecordingAdapter):
        def send_prompt(
            self, session: AgentSession, prompt: str, *, timeout_seconds: float = 600.0
        ) -> StepResult:
            del timeout_seconds
            self.prompts.append(prompt)
            state["n"] += 1
            if state["n"] == 1:
                return StepResult(
                    success=False,
                    error="ImportError: cannot import name 'Retriever'",
                    stderr="  File rag.py, line 3\n",
                    exit_code=1,
                )
            return StepResult(success=True, stdout="fixed", files_touched=["rag.py"])

    adapter = _FlakyAdapter()
    hp = HeuristicPlanner()
    director = CodeDirector(
        adapters={"fake": adapter},
        local_storage_dir=tmp_path,
        planner=lambda req, ws: hp.plan(req, workspace_dir=ws),
    )
    req = CodeBuildRequest(
        objective="Build a single RAG module with a retriever" + " " * 40,
        adapter_preference=AdapterPreference(default_adapter="fake"),
        iterate_until_tests_pass=True,
        budget=BudgetSpec(max_total_llm_calls=20, max_calls_per_subtask=4),
    )
    bid = director.make_build_id()
    plan = director.plan(req, build_id=bid)
    plan.subtasks = plan.subtasks[:1]  # isolate the retry assertion
    result = director.run(req, plan, build_id=bid)

    assert result.status == "completed"
    assert result.subtasks[0].llm_calls == 2
    first, retry = adapter.prompts[0], adapter.prompts[1]
    assert "PREVIOUS ATTEMPT" not in first
    assert "PREVIOUS ATTEMPT (#1) FAILED (exit code 1)" in retry
    assert "ImportError: cannot import name 'Retriever'" in retry
    assert first != retry  # the director did not replay the same prompt

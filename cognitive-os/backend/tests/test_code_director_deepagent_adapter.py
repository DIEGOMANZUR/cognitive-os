"""F2 regression: DeepAgentAdapter maps DeepAgents results onto StepResult.

The adapter wraps the in-process DeepAgents `research` runner. We inject a
fake runner so the test never touches the heavy stack — the contract under
test is the result mapping and the never-raise guarantee.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cognitive_os.code_director.adapters.deepagent import DeepAgentAdapter
from cognitive_os.code_director.director import CodeDirector, default_registry
from cognitive_os.code_director.schemas import AdapterPreference, CodeBuildRequest


class _FakeResult:
    def __init__(self, status: str, answer: str, files: list[str]) -> None:
        self.status = status
        self.answer = answer
        self.generated_files = files


def test_adapter_is_available_with_injected_runner() -> None:
    adapter = DeepAgentAdapter(runner=lambda _d: _FakeResult("ok", "done", []))
    assert adapter.is_available() is True


def test_send_prompt_maps_ok_status_to_success(tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def runner(task_dict: dict[str, Any]) -> _FakeResult:
        captured.update(task_dict)
        return _FakeResult("ok", "implemented the calculator", ["calc.py", "test_calc.py"])

    adapter = DeepAgentAdapter(runner=runner)
    session = adapter.start_session(workspace=tmp_path, objective="calc", model=None)
    result = adapter.send_prompt(session, "write a calculator")

    assert result.success is True
    assert result.exit_code == 0
    assert "calc.py" in result.files_touched
    assert result.stdout == "implemented the calculator"
    # The adapter forwards the prompt as the DeepAgents query.
    assert captured["query"] == "write a calculator"
    assert captured["task_type"] == "research"
    assert captured["metadata"]["code_director"] is True
    adapter.cleanup(session)


def test_send_prompt_maps_failed_status(tmp_path: Path) -> None:
    adapter = DeepAgentAdapter(runner=lambda _d: _FakeResult("failed", "nope", []))
    session = adapter.start_session(workspace=tmp_path, objective="x", model=None)
    result = adapter.send_prompt(session, "do it")
    assert result.success is False
    assert result.exit_code == 1
    assert "status=failed" in (result.error or "")


def test_send_prompt_never_raises_on_runner_exception(tmp_path: Path) -> None:
    def boom(_d: dict[str, Any]) -> _FakeResult:
        raise RuntimeError("simulated DeepAgents crash")

    adapter = DeepAgentAdapter(runner=boom)
    session = adapter.start_session(workspace=tmp_path, objective="x", model=None)
    result = adapter.send_prompt(session, "do it")
    assert result.success is False
    assert "RuntimeError" in (result.error or "")


def test_needs_more_info_counts_as_success(tmp_path: Path) -> None:
    adapter = DeepAgentAdapter(runner=lambda _d: _FakeResult("needs_more_info", "partial", []))
    session = adapter.start_session(workspace=tmp_path, objective="x", model=None)
    result = adapter.send_prompt(session, "do it")
    assert result.success is True


def test_default_registry_includes_deepagent() -> None:
    registry = default_registry()
    assert "deepagent" in registry
    assert registry["deepagent"].name == "deepagent"


def test_director_runs_end_to_end_with_deepagent_fake_runner(tmp_path: Path) -> None:
    """The director can drive a full build through DeepAgentAdapter."""
    calls: list[str] = []

    def runner(task_dict: dict[str, Any]) -> _FakeResult:
        calls.append(str(task_dict["query"])[:40])
        return _FakeResult("ok", "subtask done", ["main.py"])

    registry = {"deepagent": DeepAgentAdapter(runner=runner)}
    director = CodeDirector(adapters=registry, local_storage_dir=tmp_path)
    request = CodeBuildRequest(
        objective="Build a tiny CLI calculator with tests" + " " * 60,
        adapter_preference=AdapterPreference(default_adapter="deepagent"),
    )
    build_id = director.make_build_id()
    plan = director.plan(request, build_id=build_id)
    result = director.run(request, plan, build_id=build_id)

    assert result.status == "completed"
    assert all(o.status == "completed" for o in result.subtasks)
    assert len(calls) == len(plan.subtasks)

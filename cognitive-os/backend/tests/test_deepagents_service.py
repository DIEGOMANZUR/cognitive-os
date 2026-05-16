from __future__ import annotations

import cognitive_os.deepagents.service as service
from cognitive_os.deepagents.policies import DeepAgentPolicyViolation
from cognitive_os.deepagents.schemas import DeepAgentResult, DeepAgentTask


def _task() -> DeepAgentTask:
    return DeepAgentTask(
        task_id="task-1",
        thread_id="thread-1",
        task_type="research",
        query="investiga",
    )


def test_run_deepagent_task_with_invalid_task_type_fails_controlled() -> None:
    task = DeepAgentTask.model_construct(
        task_id="bad",
        thread_id="thread",
        task_type="invalid",
        query="x",
        allowed_doc_ids=[],
        web_allowed=False,
        max_iterations=12,
        budget_usd_limit=3.0,
        require_citations=True,
        metadata={},
    )

    result = service.run_deepagent_task(task)

    assert result.status == "failed"
    assert "Unsupported" in result.answer


def test_research_with_deepagent_mock_returns_result(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    expected = DeepAgentResult(
        task_id="task-1",
        thread_id="thread-1",
        status="ok",
        answer="ok",
        findings=["finding"],
    )
    monkeypatch.setattr(service, "run_research_deepagent", lambda task: expected)

    assert service.run_deepagent_task(_task()) == expected


def test_deepagent_exception_returns_failed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fail(task: DeepAgentTask) -> DeepAgentResult:
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "run_research_deepagent", fail)

    assert service.run_deepagent_task(_task()).status == "failed"


def test_policy_violation_returns_blocked(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def blocked(task: DeepAgentTask) -> DeepAgentResult:
        raise DeepAgentPolicyViolation("blocked")

    monkeypatch.setattr(service, "run_research_deepagent", blocked)

    assert service.run_deepagent_task(_task()).status == "blocked"

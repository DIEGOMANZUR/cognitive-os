from __future__ import annotations

import cognitive_os.deepagents.service as service
from cognitive_os.deepagents.policies import DeepAgentPolicyViolation
from cognitive_os.deepagents.schemas import DeepAgentResult, DeepAgentTask
from cognitive_os.memory.retrieval import RetrievedContext


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
    monkeypatch.setattr(service, "retrieve_context", lambda query: [])

    assert service.run_deepagent_task(_task()).status == "failed"


def test_research_exception_uses_local_rag_fallback(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fail(task: DeepAgentTask) -> DeepAgentResult:
        raise TimeoutError("provider timed out")

    monkeypatch.setattr(service, "run_research_deepagent", fail)
    monkeypatch.setattr(
        service,
        "retrieve_context",
        lambda query: [
            RetrievedContext(
                text="Mail remains read-only and automatic drafts are blocked.",
                citation="fixture.pdf:2-2",
                score=0.91,
                metadata={
                    "doc_id": "doc-1",
                    "chunk_id": "chunk-2",
                    "source_path": "/hidden/fixture.pdf",
                    "page_start": 2,
                    "page_end": 2,
                },
            )
        ],
    )

    result = service.run_deepagent_task(_task())

    assert result.status == "ok"
    assert "local RAG fallback" in result.answer
    assert result.citations[0].doc_id == "doc-1"
    assert result.citations[0].chunk_id == "chunk-2"
    assert "direct_local_rag_fallback_used" in result.uncertainty_notes


def test_failed_research_result_uses_allowed_doc_rag_fallback(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    task = _task().model_copy(update={"allowed_doc_ids": ["doc-allowed"]})

    monkeypatch.setattr(
        service,
        "run_research_deepagent",
        lambda _task: DeepAgentResult(
            task_id=task.task_id,
            thread_id=task.thread_id,
            status="failed",
            answer="timeout",
            uncertainty_notes=["provider timeout"],
        ),
    )
    calls: list[dict[str, str] | None] = []

    def fake_retrieve(query: str, filters: dict[str, str] | None = None) -> list[RetrievedContext]:
        calls.append(filters)
        return [
            RetrievedContext(
                text="Allowed document evidence.",
                citation="allowed.pdf:1-1",
                score=0.5,
                metadata={
                    "doc_id": "doc-allowed",
                    "chunk_id": "chunk-1",
                    "source_path": "/hidden/allowed.pdf",
                    "page_start": 1,
                    "page_end": 1,
                },
            )
        ]

    monkeypatch.setattr(service, "retrieve_context", fake_retrieve)

    result = service.run_deepagent_task(task)

    assert result.status == "ok"
    assert calls == [{"doc_id": "doc-allowed"}]
    assert result.citations[0].doc_id == "doc-allowed"


def test_policy_violation_returns_blocked(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def blocked(task: DeepAgentTask) -> DeepAgentResult:
        raise DeepAgentPolicyViolation("blocked")

    monkeypatch.setattr(service, "run_research_deepagent", blocked)

    assert service.run_deepagent_task(_task()).status == "blocked"

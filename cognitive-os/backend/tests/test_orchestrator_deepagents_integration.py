from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from cognitive_os.agents.graph import build_graph, cast_state, initial_state, research_node
from cognitive_os.deepagents.schemas import DeepAgentCitation, DeepAgentResult, DeepAgentTask


def ok_runner(task: DeepAgentTask) -> DeepAgentResult:
    return DeepAgentResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="ok",
        answer="deep answer",
        findings=["deep finding"],
        citations=[
            DeepAgentCitation(
                source_type="local_doc",
                doc_id="doc-1",
                chunk_id="chunk-1",
                page_start=1,
                page_end=1,
                quote="quote",
            )
        ],
    )


def test_research_node_calls_run_deepagent_task() -> None:
    calls: list[str] = []

    def runner(task: DeepAgentTask) -> DeepAgentResult:
        calls.append(task.query)
        return ok_runner(task)

    result = research_node(initial_state("investiga", thread_id="t"), deepagent_runner=runner)

    assert calls == ["investiga"]
    assert result["agent_result"].content == "deep answer"


def test_deepagent_result_is_added_to_messages() -> None:
    graph = build_graph(
        checkpointer=MemorySaver(),
        deepagent_runner=ok_runner,
        retriever=lambda query: [],
    )

    result = cast_state(
        graph.invoke(
            initial_state("investiga", thread_id="deep-message"),
            config={"configurable": {"thread_id": "deep-message"}},
        )
    )

    assert result["messages"][-1].content.startswith("deep answer")


def test_requested_external_actions_generate_interrupt() -> None:
    def runner(task: DeepAgentTask) -> DeepAgentResult:
        return DeepAgentResult(
            task_id=task.task_id,
            thread_id=task.thread_id,
            status="ok",
            answer="needs action",
            requested_external_actions=[{"tool": "send_email"}],
        )

    graph = build_graph(
        checkpointer=MemorySaver(),
        deepagent_runner=runner,
        retriever=lambda query: [],
    )
    result = graph.invoke(
        initial_state("investiga", thread_id="deep-interrupt"),
        config={"configurable": {"thread_id": "deep-interrupt"}},
    )

    assert "__interrupt__" in result


def test_fallback_works_when_deepagent_fails() -> None:
    def runner(task: DeepAgentTask) -> DeepAgentResult:
        return DeepAgentResult(
            task_id=task.task_id,
            thread_id=task.thread_id,
            status="failed",
            answer="failed",
            uncertainty_notes=["boom"],
        )

    result = research_node(initial_state("investiga", thread_id="t"), deepagent_runner=runner)

    assert "fallback" in result["agent_result"].content.lower()

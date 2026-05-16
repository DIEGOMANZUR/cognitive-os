from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from cognitive_os.agents.graph import (
    build_graph,
    cast_state,
    deterministic_route,
    initial_state,
    resume_graph,
)
from cognitive_os.agents.research import ReadOnlyResearchTools, ResearchAgent
from cognitive_os.agents.state import RetrievalCitation, RouterDecision
from cognitive_os.deepagents.schemas import DeepAgentResult, DeepAgentTask
from cognitive_os.memory.retrieval import RetrievedContext


class FakeStructuredRouter:
    def __init__(self, decision: RouterDecision) -> None:
        self._decision = decision

    def invoke(self, messages: list[tuple[str, str]]) -> RouterDecision:
        assert messages
        return self._decision


class FakeRouterLLM:
    def __init__(self, decision: RouterDecision) -> None:
        self._decision = decision

    def with_structured_output(self, schema: Any) -> FakeStructuredRouter:
        assert schema is RouterDecision
        return FakeStructuredRouter(self._decision)


class EmptyWebClient:
    def search(self, query: str) -> list[object]:
        del query
        return []


def fake_retriever(query: str) -> list[RetrievedContext]:
    return [
        RetrievedContext(
            text=f"context for {query}",
            citation="/tmp/source.pdf:2-3",
            score=0.9,
            metadata={
                "source_path": "/tmp/source.pdf",
                "page_start": 2,
                "page_end": 3,
            },
        )
    ]


def fake_retriever_with_ids(query: str) -> list[RetrievedContext]:
    return [
        RetrievedContext(
            text=f"local evidence for {query}",
            citation="/tmp/source.pdf:2-3",
            score=0.9,
            metadata={
                "doc_id": "22222222-2222-2222-2222-222222222222",
                "chunk_id": "chunk-2",
                "source_path": "/tmp/source.pdf",
                "page_start": 2,
                "page_end": 3,
            },
        )
    ]


def failing_retriever(query: str) -> list[RetrievedContext]:
    raise RuntimeError(f"retriever failed for {query}")


def failed_deepagent_runner(task: DeepAgentTask) -> DeepAgentResult:
    return DeepAgentResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="failed",
        answer="mocked failure",
        findings=[],
        citations=[],
        uncertainty_notes=["mocked"],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=None,
    )


def test_deterministic_routing() -> None:
    assert deterministic_route("Necesito analizar un contrato legal").route == "legal"
    assert deterministic_route("Redacta un email").route == "comm"
    assert deterministic_route("Prepara un post social").route == "social"
    assert deterministic_route("Investiga Cognitive OS").route == "research"


def test_routing_with_mock_llm() -> None:
    graph = build_graph(
        checkpointer=MemorySaver(),
        router_llm=FakeRouterLLM(RouterDecision(route="legal", confidence=0.99, reason="mocked")),
        retriever=fake_retriever,
    )

    result = cast_state(
        graph.invoke(
            initial_state("route this", thread_id="mock-route"),
            config={"configurable": {"thread_id": "mock-route"}},
        )
    )

    assert result["active_route"] == "legal"
    assert result["agent_result"].route == "legal"
    assert result["retrieved_context"] == [
        RetrievalCitation(
            source_path="/tmp/source.pdf",
            page_start=2,
            page_end=3,
            quote="context for route this",
        )
    ]


def test_research_node_returns_report_from_local_context() -> None:
    graph = build_graph(
        checkpointer=MemorySaver(),
        retriever=fake_retriever_with_ids,
        research_agent=ResearchAgent(
            tools=ReadOnlyResearchTools(
                local_search=fake_retriever_with_ids,
                web_client=EmptyWebClient(),
            )
        ),
        deepagent_runner=failed_deepagent_runner,
    )

    result = cast_state(
        graph.invoke(
            initial_state("investiga evidencia local", thread_id="research-context"),
            config={"configurable": {"thread_id": "research-context"}},
        )
    )

    assert result["agent_result"].route == "research"
    assert "Respuesta de investigación" in result["agent_result"].content
    assert result["agent_result"].citations[0].doc_id == "22222222-2222-2222-2222-222222222222"
    assert result["agent_result"].citations[0].chunk_id == "chunk-2"
    assert result["last_research_report"]["used_sources"] == [
        "local:22222222-2222-2222-2222-222222222222:chunk-2"
    ]


def _stub_drafters(monkeypatch: Any) -> None:
    """Avoid calling the real LLM during interrupt/resume flow tests."""
    monkeypatch.setattr(
        "cognitive_os.agents.graph._draft_communication",
        lambda query, citations: "stub-comm-draft",
    )
    monkeypatch.setattr(
        "cognitive_os.agents.graph._draft_social_post",
        lambda query, citations, *, platform: "stub-social-draft",
    )


def test_interrupt_and_resume_approve(monkeypatch: Any) -> None:
    _stub_drafters(monkeypatch)
    graph = build_graph(checkpointer=MemorySaver(), retriever=fake_retriever)
    config = {"configurable": {"thread_id": "interrupt-approve"}}

    interrupted = graph.invoke(
        initial_state("enviar un email externo", thread_id="interrupt-approve"),
        config=config,
    )
    assert "__interrupt__" in interrupted

    resumed = cast_state(resume_graph(graph, thread_id="interrupt-approve", action="approve"))
    assert "agent_result" in resumed
    assert resumed["agent_result"].route == "comm"
    assert resumed["agent_result"].content == "stub-comm-draft"


def test_resume_reject(monkeypatch: Any) -> None:
    _stub_drafters(monkeypatch)
    graph = build_graph(checkpointer=MemorySaver(), retriever=fake_retriever)
    config = {"configurable": {"thread_id": "interrupt-reject"}}

    interrupted = graph.invoke(
        initial_state("publicar en social", thread_id="interrupt-reject"),
        config=config,
    )
    assert "__interrupt__" in interrupted

    resumed = cast_state(resume_graph(graph, thread_id="interrupt-reject", action="reject"))
    assert resumed["agent_result"].content == "Request rejected by human reviewer."


def test_error_recovery() -> None:
    graph = build_graph(checkpointer=MemorySaver(), retriever=failing_retriever)

    result = cast_state(
        graph.invoke(
            initial_state("investiga algo", thread_id="error-recovery"),
            config={"configurable": {"thread_id": "error-recovery"}},
        )
    )

    assert result["agent_result"].route == "error"
    assert result["error_count"] == 1


def test_explicit_doc_ids_force_legal_route_and_pass_case_id() -> None:
    captured: dict[str, Any] = {}

    def fake_runner(task: Any) -> Any:
        captured["doc_ids"] = list(task.doc_ids)
        captured["case_id"] = task.case_id
        captured["modes"] = list(task.modes)
        from cognitive_os.deepagents.document_analysis.schemas import DocumentAnalysisResult

        return DocumentAnalysisResult(
            task_id=task.task_id,
            thread_id=task.thread_id,
            status="ok",
            executive_summary="resumen",
            generated_files=["result.json"],
        )

    graph = build_graph(
        checkpointer=MemorySaver(),
        retriever=fake_retriever,
        document_analysis_runner=fake_runner,
    )

    state = initial_state(
        "Cuéntame qué dicen estos PDFs",
        thread_id="explicit-doc-ids",
        doc_ids=["22222222-2222-2222-2222-222222222222"],
        case_id="case-RIT-79",
    )
    result = cast_state(
        graph.invoke(state, config={"configurable": {"thread_id": "explicit-doc-ids"}})
    )

    assert result["active_route"] == "legal"
    assert captured["doc_ids"] == ["22222222-2222-2222-2222-222222222222"]
    assert captured["case_id"] == "case-RIT-79"

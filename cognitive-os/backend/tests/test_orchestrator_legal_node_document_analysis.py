from __future__ import annotations

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from cognitive_os.agents.graph import build_graph, deterministic_route, initial_state, legal_node
from cognitive_os.deepagents.document_analysis.schemas import (
    DocumentAnalysisResult,
    DocumentAnalysisTask,
    EvidenceCitation,
)


def _result(*, draft: bool = False) -> DocumentAnalysisResult:
    citation = EvidenceCitation(
        doc_id="doc-a",
        chunk_id="chunk-a",
        page_start=1,
        page_end=1,
        quote="El hecho ocurrió el 10 de noviembre de 2023.",
    )
    return DocumentAnalysisResult(
        task_id="task-1",
        thread_id="thread-1",
        status="ok",
        executive_summary="Resumen legal documental.",
        evidence_matrix=[],
        timeline=[],
        contradictions=[],
        missing_evidence=[],
        draft_sections={"hechos": "Borrador con citas."} if draft else {},
        citations=[citation],
        uncertainty_notes=["Sin incertidumbres adicionales."],
        generated_files=["report.md"],
        human_review_required=draft,
        warnings=[],
        raw_agent_summary=None,
    )


def test_deterministic_route_sends_document_analysis_to_legal() -> None:
    decision = deterministic_route("haz matriz hecho evidencia doc_id=doc-a")

    assert decision.route == "legal"


def test_legal_node_calls_document_analysis_service() -> None:
    captured: dict[str, DocumentAnalysisTask] = {}

    def runner(task: DocumentAnalysisTask) -> DocumentAnalysisResult:
        captured["task"] = task
        return _result()

    state = {
        "messages": [HumanMessage(content="analiza documentos doc_id=doc-a con matriz")],
        "thread_id": "thread-1",
        "user_id": "user-1",
    }

    output = legal_node(state, document_analysis_runner=runner)

    assert captured["task"].doc_ids == ["doc-a"]
    assert output["agent_result"].content.startswith("Resumen legal documental.")


def test_legal_node_draft_generates_human_review() -> None:
    def runner(task: DocumentAnalysisTask) -> DocumentAnalysisResult:
        del task
        return _result(draft=True)

    state = {
        "messages": [HumanMessage(content="ayúdame con borrador con citas doc_id=doc-a")],
        "thread_id": "thread-1",
    }

    output = legal_node(state, document_analysis_runner=runner)

    assert output["pending_human_review"] is not None


def test_graph_adds_document_analysis_result_to_messages() -> None:
    def runner(task: DocumentAnalysisTask) -> DocumentAnalysisResult:
        del task
        return _result()

    graph = build_graph(
        checkpointer=MemorySaver(),
        retriever=lambda query: [],
        document_analysis_runner=runner,
    )
    result = graph.invoke(
        initial_state("analiza documentos doc_id=doc-a con matriz", thread_id="thread-1"),
        config={"configurable": {"thread_id": "thread-1"}},
    )

    assert "Resumen legal documental." in str(result["messages"][-1].content)

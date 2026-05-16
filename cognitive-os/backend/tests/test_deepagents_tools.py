from __future__ import annotations

from unittest.mock import MagicMock, patch

from cognitive_os.deepagents.schemas import DeepAgentToolPolicy, DeepAgentWorkspace
from cognitive_os.deepagents.tools import (
    graph_query_readonly,
    read_document_pages,
    search_local_docs,
    search_web,
    write_workspace_file,
)
from cognitive_os.ingestion.neo4j import Neo4jGraphReader
from cognitive_os.memory.retrieval import RetrievedContext


def fake_retriever(query: str) -> list[RetrievedContext]:
    return [
        RetrievedContext(
            text=f"evidence for {query}",
            citation="/hidden/source.pdf:1-1",
            score=0.9,
            metadata={
                "doc_id": "doc-1",
                "chunk_id": "chunk-1",
                "page_start": 1,
                "page_end": 1,
            },
        )
    ]


def many_fake_results(query: str) -> list[RetrievedContext]:
    return [
        RetrievedContext(
            text=f"evidence {index} for {query}",
            citation=f"/hidden/source.pdf:{index + 1}-{index + 1}",
            score=0.9,
            metadata={
                "doc_id": "doc-1",
                "chunk_id": f"chunk-{index}",
                "page_start": index + 1,
                "page_end": index + 1,
            },
        )
        for index in range(50)
    ]


def test_search_local_docs_with_mock_retrieval() -> None:
    result = search_local_docs(
        "alpha",
        policy=DeepAgentToolPolicy(),
        local_retriever=fake_retriever,
    )

    assert result["results"][0]["doc_id"] == "doc-1"
    assert result["citations"][0]["chunk_id"] == "chunk-1"
    assert "/hidden" not in str(result["citations"][0])


def test_search_local_docs_clamps_excessive_limit() -> None:
    result = search_local_docs(
        "alpha",
        limit=999,
        policy=DeepAgentToolPolicy(),
        local_retriever=many_fake_results,
    )

    assert len(result["results"]) == 20
    assert len(result["citations"]) == 20


def test_read_document_pages_rejects_non_positive_page_numbers() -> None:
    result = read_document_pages(
        "11111111-1111-1111-1111-111111111111",
        0,
        1,
        policy=DeepAgentToolPolicy(),
    )

    assert result["error"] == "invalid_page_range"


def test_read_document_pages_maximum_20_pages() -> None:
    result = read_document_pages(
        "11111111-1111-1111-1111-111111111111",
        1,
        21,
        policy=DeepAgentToolPolicy(),
    )

    assert result["error"] == "too_many_pages"


def test_search_web_disabled_returns_controlled_error() -> None:
    result = search_web("latest", policy=DeepAgentToolPolicy(allow_web=False))

    assert result["error"] == "policy_violation"


def test_graph_query_readonly_rejects_free_cypher() -> None:
    result = graph_query_readonly("MATCH (n) RETURN n", policy=DeepAgentToolPolicy())

    assert result["error"] == "unsupported_graph_query"


def test_write_workspace_file_allows_relative_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    workspace = DeepAgentWorkspace(root_dir=tmp_path, thread_id="t", task_id="task")
    result = write_workspace_file(
        "report.md",
        "hello",
        policy=DeepAgentToolPolicy(),
        workspace=workspace,
    )

    assert result["relative_path"] == "report.md"
    assert (tmp_path / "report.md").read_text(encoding="utf-8") == "hello"


def test_graph_query_readonly_returns_not_configured_when_no_reader() -> None:
    with patch(
        "cognitive_os.deepagents.tools._build_default_neo4j_reader",
        return_value=None,
    ):
        result = graph_query_readonly(
            "find entity named Acme",
            policy=DeepAgentToolPolicy(allow_neo4j_read=True),
            neo4j_reader=None,
        )
    assert result.get("available") is False
    assert result.get("reason") == "neo4j_not_configured"


def test_graph_query_readonly_returns_results_from_real_reader() -> None:
    mock_reader = MagicMock(spec=Neo4jGraphReader)
    mock_reader.is_available.return_value = True
    mock_reader.find_entities.return_value = [{"kind": "ORG", "value": "Acme Corp"}]

    result = graph_query_readonly(
        "busca entidad Acme Corp",
        policy=DeepAgentToolPolicy(allow_neo4j_read=True),
        neo4j_reader=mock_reader,
    )

    assert result["query_type"] == "find_entities"
    assert result["results"] == [{"kind": "ORG", "value": "Acme Corp"}]
    assert result["warnings"] == []

from __future__ import annotations

from pydantic import SecretStr

from cognitive_os.agents.research import (
    ReadOnlyResearchTools,
    ResearchAgent,
    WebSearchResult,
)
from cognitive_os.core.config import Settings
from cognitive_os.memory.retrieval import RetrievedContext


class FakeWebClient:
    def __init__(self, results: list[WebSearchResult] | None = None) -> None:
        self.calls: list[str] = []
        self._results = results or []

    def search(self, query: str) -> list[WebSearchResult]:
        self.calls.append(query)
        return self._results


class ExplodingWebClient:
    def search(self, query: str) -> list[WebSearchResult]:
        raise AssertionError(f"web search should be disabled, got {query}")


def fake_local_search(query: str) -> list[RetrievedContext]:
    return [
        RetrievedContext(
            text=f"El documento confirma el antecedente consultado sobre {query}.",
            citation="/tmp/causa.pdf:4-4",
            score=0.91,
            metadata={
                "doc_id": "11111111-1111-1111-1111-111111111111",
                "chunk_id": "chunk-4-a",
                "source_path": "/tmp/causa.pdf",
                "page_start": 4,
                "page_end": 4,
            },
        )
    ]


def empty_local_search(query: str) -> list[RetrievedContext]:
    assert query
    return []


def test_research_uses_local_docs_with_required_citations() -> None:
    tools = ReadOnlyResearchTools(
        local_search=fake_local_search,
        web_client=ExplodingWebClient(),
        app_settings=Settings(web_search_enabled=False),
    )
    report = ResearchAgent(tools=tools).run("antecedente principal")

    assert "Respuesta de investigación" in report.answer
    assert report.bullet_findings
    assert report.citations[0].doc_id == "11111111-1111-1111-1111-111111111111"
    assert report.citations[0].chunk_id == "chunk-4-a"
    assert report.citations[0].page_start == 4
    assert report.used_sources == ["local:11111111-1111-1111-1111-111111111111:chunk-4-a"]


def test_research_without_evidence_returns_uncertainty() -> None:
    tools = ReadOnlyResearchTools(
        local_search=empty_local_search,
        web_client=ExplodingWebClient(),
        app_settings=Settings(web_search_enabled=False),
    )
    report = ResearchAgent(tools=tools).run("tema sin documentos")

    assert "No hay evidencia suficiente" in report.answer
    assert report.citations == []
    assert report.uncertainty_notes
    assert report.used_sources == []


def test_web_disabled_does_not_call_web_client() -> None:
    tools = ReadOnlyResearchTools(
        local_search=empty_local_search,
        web_client=ExplodingWebClient(),
        app_settings=Settings(web_search_enabled=False),
    )

    assert tools.search_web("no llamar web") == []


def test_web_enabled_with_mock_cites_source() -> None:
    web_client = FakeWebClient(
        [
            WebSearchResult(
                title="Fuente oficial",
                url="https://example.test/fuente",
                snippet="Contenido verificado por la fuente externa.",
                date="2026-04-30",
                score=0.8,
            )
        ]
    )
    tools = ReadOnlyResearchTools(
        local_search=empty_local_search,
        web_client=web_client,
        app_settings=Settings(
            web_search_enabled=True,
            tavily_api_key=SecretStr("CHANGEME"),
        ),
    )
    report = ResearchAgent(tools=tools).run("consulta web")

    assert web_client.calls == ["consulta web"]
    assert report.citations[0].url == "https://example.test/fuente"
    assert report.citations[0].title == "Fuente oficial"
    assert report.citations[0].date == "2026-04-30"
    assert report.used_sources == ["web:https://example.test/fuente"]

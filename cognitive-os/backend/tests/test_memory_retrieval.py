from __future__ import annotations

from collections.abc import Sequence

from cognitive_os.memory.reranker import LocalReranker
from cognitive_os.memory.retrieval import retrieve_context
from cognitive_os.memory.weaviate_store import SearchResult


def _result(chunk_id: str, text: str, page_start: int = 1) -> SearchResult:
    return SearchResult(
        doc_id="doc-1",
        chunk_id=chunk_id,
        text=text,
        source_path="/tmp/source.pdf",
        doc_type="pdf",
        page_start=page_start,
        page_end=page_start,
        sha256="a" * 64,
        metadata_json={"section": chunk_id},
        score=0.5,
        explain_score="mock",
    )


class FakeStore:
    def __init__(self) -> None:
        self.last_exclude_doc_types: tuple[str, ...] | None = None

    def hybrid_search(
        self,
        query: str,
        filters: dict[str, object] | None = None,
        alpha: float = 0.5,
        limit: int = 10,
        *,
        exclude_doc_types: Sequence[str] | None = None,
    ) -> list[SearchResult]:
        assert query == "alpha"
        assert filters == {"doc_type": "pdf"}
        assert alpha == 0.5
        assert limit == 30
        self.last_exclude_doc_types = tuple(exclude_doc_types or ())
        return [
            _result("low", "unrelated text", 2),
            _result("high", "alpha matching text", 4),
        ]


def test_retrieve_context_returns_citations() -> None:
    contexts = retrieve_context(
        "alpha",
        filters={"doc_type": "pdf"},
        store=FakeStore(),  # type: ignore[arg-type]
        reranker=LocalReranker(enabled=True, model_name="missing-local-model"),
    )

    # Citations render the basename of source_path so the absolute filesystem
    # path of the ingestor is never leaked to the user; the full path remains
    # available via context.metadata["source_path"].
    assert [context.citation for context in contexts] == [
        "source.pdf:4-4",
        "source.pdf:2-2",
    ]
    assert contexts[0].metadata["chunk_id"] == "high"
    assert contexts[0].metadata["source_path"] == "/tmp/source.pdf"


def test_retrieve_context_forwards_exclude_doc_types() -> None:
    store = FakeStore()
    retrieve_context(
        "alpha",
        filters={"doc_type": "pdf"},
        store=store,  # type: ignore[arg-type]
        reranker=LocalReranker(enabled=False, model_name="ignored"),
        exclude_doc_types=("web",),
    )
    assert store.last_exclude_doc_types == ("web",)

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from cognitive_os.core.config import settings
from cognitive_os.memory.embeddings import (
    EmbeddingProvider,
    build_embedding_provider_from_settings,
)
from cognitive_os.memory.reranker import LocalReranker
from cognitive_os.memory.weaviate_store import FilterValue, SearchResult, WeaviateStore


@dataclass(frozen=True)
class RetrievedContext:
    text: str
    citation: str
    score: float | None
    metadata: dict[str, Any]


def build_embedding_provider() -> EmbeddingProvider:
    return build_embedding_provider_from_settings()


def build_weaviate_store(embedding_provider: EmbeddingProvider | None = None) -> WeaviateStore:
    return WeaviateStore(
        base_url=settings.weaviate_url,
        api_key=settings.weaviate_api_key,
        embedding_provider=embedding_provider or build_embedding_provider(),
    )


def retrieve_context(
    query: str,
    filters: dict[str, FilterValue] | None = None,
    *,
    store: WeaviateStore | None = None,
    reranker: LocalReranker | None = None,
    exclude_doc_types: Sequence[str] | None = None,
) -> list[RetrievedContext]:
    """Hybrid retrieval with reranking. Pass `exclude_doc_types=("web",)` to keep
    web-indexed snippets out of local-only searches (default: include everything)."""
    active_store = store or build_weaviate_store()
    candidates = active_store.hybrid_search(
        query,
        filters=filters,
        alpha=0.5,
        limit=30,
        exclude_doc_types=exclude_doc_types,
    )
    active_reranker = reranker or LocalReranker(
        enabled=settings.reranker_enabled,
        model_name=settings.reranker_model,
    )
    selected = active_reranker.rerank(query, candidates, limit=8)
    return [_to_context(result) for result in selected]


def _to_context(result: SearchResult) -> RetrievedContext:
    return RetrievedContext(
        text=result.text,
        citation=result.citation,
        score=result.score,
        metadata={
            "doc_id": result.doc_id,
            "chunk_id": result.chunk_id,
            "source_path": result.source_path,
            "doc_type": result.doc_type,
            "page_start": result.page_start,
            "page_end": result.page_end,
            "sha256": result.sha256,
            **result.metadata_json,
        },
    )

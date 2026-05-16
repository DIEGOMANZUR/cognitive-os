"""Index web search results back into the Weaviate vector store.

This module implements the RAG growth loop: every time a DeepAgent performs a
web search, the retrieved snippets are embedded and stored in Weaviate with
doc_type="web".  Future retrieval calls will surface these chunks alongside
locally-ingested PDFs, so the system's knowledge base grows continuously.

Duplicates are handled by the deterministic uuid5 key in WeaviateStore —
re-indexing the same URL is a no-op at the vector-store level.

Failures are logged (not raised) because the indexer is fire-and-forget from
the caller's perspective; the previous `except: pass` made debugging Weaviate
outages invisible. With structlog we can grep "web_indexer_failed" instead.
"""

from __future__ import annotations

import hashlib
import threading
from typing import Any

import structlog

from cognitive_os.memory.retrieval import build_weaviate_store
from cognitive_os.memory.weaviate_store import ChunkRecord

logger = structlog.get_logger(__name__)


def index_web_results_async(
    *,
    query: str,
    results: list[Any],
    min_snippet_chars: int = 80,
) -> None:
    """Spawn a daemon thread to index web results; returns immediately."""
    if not results:
        return
    thread = threading.Thread(
        target=_index_blocking,
        args=(query, results, min_snippet_chars),
        daemon=True,
        name="web-rag-indexer",
    )
    thread.start()


def _index_blocking(query: str, results: list[Any], min_snippet_chars: int) -> None:
    try:
        store = build_weaviate_store()
        store.ensure_collection()
        for result in results:
            snippet = _snippet(result)
            if len(snippet) < min_snippet_chars:
                continue
            chunk = ChunkRecord(
                doc_id=_url_id(result),
                chunk_id=_chunk_id(result),
                text=snippet,
                source_path=str(getattr(result, "url", "") or ""),
                doc_type="web",
                page_start=1,
                page_end=1,
                sha256=hashlib.sha256(snippet.encode()).hexdigest(),
                metadata_json={
                    "title": str(getattr(result, "title", "") or ""),
                    "url": str(getattr(result, "url", "") or ""),
                    "date": str(getattr(result, "date", "") or ""),
                    "query": query,
                    "providers": list(getattr(result, "all_providers", [])),
                    "score": float(getattr(result, "score", 0.0) or 0.0),
                },
            )
            store.insert_chunk(chunk)
    except Exception as exc:  # noqa: BLE001 - daemon thread: log and exit
        logger.warning(
            "web_indexer_failed",
            error_type=type(exc).__name__,
            error=str(exc),
            query_length=len(query),
            result_count=len(results),
        )


def _snippet(result: Any) -> str:
    parts: list[str] = []
    title = str(getattr(result, "title", "") or "").strip()
    snippet = str(getattr(result, "snippet", "") or "").strip()
    if title:
        parts.append(title)
    if snippet:
        parts.append(snippet)
    return "\n".join(parts)


def _url_id(result: Any) -> str:
    url = str(getattr(result, "url", "") or "unknown")
    return hashlib.sha256(url.encode()).hexdigest()[:36]


def _chunk_id(result: Any) -> str:
    url = str(getattr(result, "url", "") or "unknown")
    return f"web:{hashlib.sha256(url.encode()).hexdigest()[:16]}"

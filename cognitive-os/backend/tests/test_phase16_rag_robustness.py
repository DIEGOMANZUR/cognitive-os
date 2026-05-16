"""Regression tests for Phase 16 RAG robustness fixes.

- Pipeline order: chunks land in Postgres as `pending_index`; they only flip to
  `indexed` after Weaviate confirms. A Weaviate failure must not leave Postgres
  claiming the chunks are indexed.
- sha256 dedup: re-ingesting a PDF whose sha256 already has a fully-indexed
  Document returns the existing rows instead of duplicating everything.
- Weaviate batch insert: a 100-chunk ingestion produces O(N/batch) HTTP calls,
  not O(N), and uses the embeddings batch endpoint.
- BM25-only fallback: when the embeddings provider is down, `hybrid_search`
  must still return keyword hits with alpha=0 and no vector.
- `ensure_collection` is goroutine-safe under concurrent first-callers.
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import SecretStr

from cognitive_os.memory.weaviate_store import ChunkRecord, WeaviateStore


class _FakeEmbeddings:
    def __init__(self, *, fail_on: str | None = None, dimension: int = 4) -> None:
        self.calls: list[tuple[str, int]] = []
        self._fail_on = fail_on
        self._dimension = dimension

    def embed_text(self, text: str, *, kind: str = "document") -> list[float]:
        if self._fail_on == kind:
            msg = f"embeddings outage for kind={kind}"
            raise RuntimeError(msg)
        self.calls.append((kind, 1))
        return [0.1] * self._dimension

    def embed_texts(
        self,
        texts: list[str],
        *,
        kind: str = "document",
    ) -> list[list[float]]:
        if self._fail_on == kind:
            msg = f"embeddings outage for kind={kind}"
            raise RuntimeError(msg)
        self.calls.append((kind, len(texts)))
        return [[0.1] * self._dimension for _ in texts]


class _FakeHttpResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        json_body: Any = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._json = json_body if json_body is not None else {}
        self.text = text

    def json(self) -> Any:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"http {self.status_code}",
                request=MagicMock(),
                response=MagicMock(status_code=self.status_code),
            )


def _make_store(*, embeddings: _FakeEmbeddings, http_handler: Any) -> WeaviateStore:
    store = WeaviateStore(
        base_url="http://weaviate.local",
        api_key=SecretStr("test"),
        embedding_provider=embeddings,  # type: ignore[arg-type]
    )
    store._request = http_handler  # type: ignore[attr-defined]
    return store


# ---------------------------------------------------------------------------
# Weaviate batch insert
# ---------------------------------------------------------------------------


def test_batch_insert_uses_v1_batch_objects_endpoint() -> None:
    requests: list[tuple[str, str, dict[str, Any]]] = []

    def handler(method: str, path: str, **kwargs: Any) -> _FakeHttpResponse:
        requests.append((method, path, dict(kwargs)))
        if path == "/v1/schema/DocumentChunk":
            return _FakeHttpResponse(status_code=200)
        if path == "/v1/batch/objects":
            objects = kwargs["json"]["objects"]
            return _FakeHttpResponse(json_body=[{"result": {"status": "SUCCESS"}} for _ in objects])
        return _FakeHttpResponse(status_code=200)

    embeddings = _FakeEmbeddings()
    store = _make_store(embeddings=embeddings, http_handler=handler)
    chunks = [
        ChunkRecord(
            doc_id="doc-1",
            chunk_id=f"chunk-{idx}",
            text=f"text-{idx}",
            source_path="/tmp/x.pdf",
            doc_type="pdf",
            page_start=1,
            page_end=1,
            sha256="a" * 64,
            metadata_json={},
        )
        for idx in range(120)
    ]
    ids = store.batch_insert_chunks(chunks, batch_size=50)

    assert len(ids) == 120
    # 1 ensure_collection GET + 3 batch POSTs (ceil(120/50) == 3)
    batch_calls = [r for r in requests if r[1] == "/v1/batch/objects"]
    assert len(batch_calls) == 3
    # Embeddings provider also called 3 times in batch mode
    assert embeddings.calls == [("document", 50), ("document", 50), ("document", 20)]


def test_batch_insert_raises_on_per_object_failure() -> None:
    def handler(method: str, path: str, **kwargs: Any) -> _FakeHttpResponse:
        if path == "/v1/schema/DocumentChunk":
            return _FakeHttpResponse(status_code=200)
        if path == "/v1/batch/objects":
            return _FakeHttpResponse(
                json_body=[
                    {"result": {"status": "SUCCESS"}},
                    {
                        "result": {
                            "status": "FAILED",
                            "errors": {"error": [{"message": "schema mismatch"}]},
                        }
                    },
                ]
            )
        return _FakeHttpResponse(status_code=200)

    embeddings = _FakeEmbeddings()
    store = _make_store(embeddings=embeddings, http_handler=handler)
    chunks = [
        ChunkRecord(
            doc_id="doc",
            chunk_id=f"c-{idx}",
            text=f"t-{idx}",
            source_path="/tmp/x.pdf",
            doc_type="pdf",
            page_start=1,
            page_end=1,
            sha256="a" * 64,
            metadata_json={},
        )
        for idx in range(2)
    ]
    with pytest.raises(RuntimeError, match="batch insert failed"):
        store.batch_insert_chunks(chunks)


# ---------------------------------------------------------------------------
# BM25-only fallback
# ---------------------------------------------------------------------------


def test_hybrid_search_falls_back_to_bm25_when_embeddings_fail() -> None:
    captured_graphql: list[str] = []

    def handler(method: str, path: str, **kwargs: Any) -> _FakeHttpResponse:
        if path == "/v1/schema/DocumentChunk":
            return _FakeHttpResponse(status_code=200)
        if path == "/v1/graphql":
            captured_graphql.append(kwargs["json"]["query"])
            return _FakeHttpResponse(
                json_body={
                    "data": {
                        "Get": {
                            "DocumentChunk": [
                                {
                                    "doc_id": "d",
                                    "chunk_id": "c",
                                    "text": "kw hit",
                                    "source_path": "/tmp/a.pdf",
                                    "doc_type": "pdf",
                                    "page_start": 1,
                                    "page_end": 1,
                                    "sha256": "a" * 64,
                                    "metadata_json": "{}",
                                    "_additional": {"score": 0.5, "explainScore": "bm25"},
                                }
                            ]
                        }
                    }
                }
            )
        return _FakeHttpResponse(status_code=200)

    embeddings = _FakeEmbeddings(fail_on="query")  # embed_text(kind="query") will raise
    store = _make_store(embeddings=embeddings, http_handler=handler)
    results = store.hybrid_search("contract violations")
    assert len(results) == 1
    assert results[0].text == "kw hit"
    # The fallback GraphQL must NOT include a `vector:` line and must use alpha=0.
    assert captured_graphql
    rendered = captured_graphql[0]
    assert "vector:" not in rendered, rendered
    assert "alpha: 0.0" in rendered or "alpha: 0" in rendered


# ---------------------------------------------------------------------------
# ensure_collection thread safety
# ---------------------------------------------------------------------------


def test_ensure_collection_runs_create_only_once_under_concurrency() -> None:
    schema_get_count = 0
    schema_post_count = 0
    lock = threading.Lock()
    barrier = threading.Barrier(parties=4, timeout=5)

    def handler(method: str, path: str, **kwargs: Any) -> _FakeHttpResponse:
        nonlocal schema_get_count, schema_post_count
        # Slow the schema POST so contention is observable.
        if path == "/v1/schema/DocumentChunk":
            with lock:
                schema_get_count += 1
            return _FakeHttpResponse(status_code=404)
        if path == "/v1/schema" and method == "POST":
            with lock:
                schema_post_count += 1
            return _FakeHttpResponse(status_code=200)
        return _FakeHttpResponse(status_code=200)

    embeddings = _FakeEmbeddings()
    store = _make_store(embeddings=embeddings, http_handler=handler)

    def worker() -> None:
        barrier.wait()
        store.ensure_collection()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one creation attempt regardless of contention.
    assert schema_post_count == 1
    # Subsequent ensure_collection calls also do not re-hit the server.
    store.ensure_collection()
    store.ensure_collection()
    assert schema_post_count == 1


def test_ensure_collection_handles_concurrent_create_422() -> None:
    """Two stores racing to create the schema must accept 422 'already exists'."""

    state = {"first_post": True}

    def handler(method: str, path: str, **kwargs: Any) -> _FakeHttpResponse:
        if path == "/v1/schema/DocumentChunk":
            return _FakeHttpResponse(status_code=404)
        if path == "/v1/schema" and method == "POST":
            if state["first_post"]:
                state["first_post"] = False
                return _FakeHttpResponse(status_code=200)
            return _FakeHttpResponse(
                status_code=422,
                text="class DocumentChunk already exists in schema",
            )
        return _FakeHttpResponse(status_code=200)

    embeddings = _FakeEmbeddings()
    store_a = _make_store(embeddings=embeddings, http_handler=handler)
    store_b = _make_store(embeddings=embeddings, http_handler=handler)
    store_a.ensure_collection()
    # The second store doing the same GET-then-POST race must not raise.
    store_b.ensure_collection()

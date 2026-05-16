from __future__ import annotations

import json
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import httpx
from pydantic import SecretStr

from cognitive_os.core.config import settings
from cognitive_os.core.resilience import retry_transient_http
from cognitive_os.memory.embeddings import EmbeddingProvider

COLLECTION_NAME = "DocumentChunk"


@dataclass(frozen=True)
class ChunkRecord:
    doc_id: str
    chunk_id: str
    text: str
    source_path: str
    doc_type: str
    page_start: int
    page_end: int
    sha256: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class SearchResult:
    doc_id: str
    chunk_id: str
    text: str
    source_path: str
    doc_type: str
    page_start: int
    page_end: int
    sha256: str
    metadata_json: dict[str, Any]
    score: float | None
    explain_score: str | None

    @property
    def citation(self) -> str:
        # Render the source as a basename so user-facing citations don't leak the
        # ingestor's absolute filesystem path. The full `source_path` is still
        # available via the metadata for traceability.
        title = self.metadata_json.get("title")
        if isinstance(title, str) and title.strip():
            return f"{title.strip()}:{self.page_start}-{self.page_end}"
        last_slash = max(self.source_path.rfind("/"), self.source_path.rfind("\\"))
        display = self.source_path[last_slash + 1 :] if last_slash >= 0 else self.source_path
        return f"{display}:{self.page_start}-{self.page_end}"


FilterValue = str | int | bool


class WeaviateStore:
    """Weaviate-backed store for document chunks with external vectors."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: SecretStr,
        embedding_provider: EmbeddingProvider,
        collection_name: str = COLLECTION_NAME,
        timeout: float | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._embedding_provider = embedding_provider
        self._collection_name = collection_name
        self._timeout = timeout or settings.http_timeout_seconds
        self._collection_ensured = False
        # Lock guards the read-then-create-then-set sequence in ensure_collection().
        # Without it, two threads (e.g., the ingest pipeline plus the web_indexer
        # daemon thread) can both observe `_collection_ensured=False`, race to POST
        # /v1/schema, and the second POST 422s with a noisy error.
        self._collection_lock = threading.Lock()

    def ensure_collection(self) -> None:
        if self._collection_ensured:
            return
        with self._collection_lock:
            if self._collection_ensured:
                return
            response = self._request("GET", f"/v1/schema/{self._collection_name}")
            if response.status_code == 200:
                self._collection_ensured = True
                return
            if response.status_code != 404:
                response.raise_for_status()

            schema = {
                "class": self._collection_name,
                "description": "Cognitive OS document chunks indexed with external embeddings.",
                "vectorizer": "none",
                "properties": [
                    {"name": "doc_id", "dataType": ["text"]},
                    {"name": "chunk_id", "dataType": ["text"]},
                    {"name": "text", "dataType": ["text"]},
                    {"name": "source_path", "dataType": ["text"]},
                    {"name": "doc_type", "dataType": ["text"]},
                    {"name": "page_start", "dataType": ["int"]},
                    {"name": "page_end", "dataType": ["int"]},
                    {"name": "sha256", "dataType": ["text"]},
                    {"name": "metadata_json", "dataType": ["text"]},
                ],
            }
            create_response = self._request("POST", "/v1/schema", json=schema)
            # Another worker may have already created the collection between our
            # GET and POST: treat 422 with `already exists` as a benign no-op.
            if create_response.status_code in (200, 201):
                self._collection_ensured = True
                return
            if (
                create_response.status_code == 422
                and "already exists" in (create_response.text or "").lower()
            ):
                self._collection_ensured = True
                return
            create_response.raise_for_status()
            self._collection_ensured = True

    def insert_chunk(self, chunk: ChunkRecord) -> str:
        self.ensure_collection()
        vector = self._embedding_provider.embed_text(chunk.text, kind="document")
        object_id = self._object_id(chunk)
        payload = {
            "id": object_id,
            "class": self._collection_name,
            "properties": self._properties_for(chunk),
            "vector": vector,
        }
        self._request("POST", "/v1/objects", json=payload).raise_for_status()
        return object_id

    def batch_insert_chunks(
        self,
        chunks: Sequence[ChunkRecord],
        *,
        batch_size: int = 50,
    ) -> list[str]:
        """Insert many chunks using `/v1/batch/objects` with batched embeddings.

        Replaces N HTTP calls + N embedding calls with ceil(N/batch_size) of each.
        Critical for PDFs of hundreds of chunks. We still embed and POST in
        bounded batches because the embeddings provider has its own rate limits
        and the GraphQL `objects` array becomes unwieldy past ~50 items.
        """
        if not chunks:
            return []
        self.ensure_collection()
        ids: list[str] = []
        chunk_list = list(chunks)
        for offset in range(0, len(chunk_list), max(1, batch_size)):
            window = chunk_list[offset : offset + batch_size]
            vectors = self._embedding_provider.embed_texts(
                [chunk.text for chunk in window],
                kind="document",
            )
            if len(vectors) != len(window):
                msg = (
                    f"Embedding provider returned {len(vectors)} vectors for "
                    f"{len(window)} chunks; refusing to insert partial batch."
                )
                raise RuntimeError(msg)
            objects: list[dict[str, Any]] = []
            for chunk, vector in zip(window, vectors, strict=True):
                object_id = self._object_id(chunk)
                objects.append(
                    {
                        "id": object_id,
                        "class": self._collection_name,
                        "properties": self._properties_for(chunk),
                        "vector": vector,
                    }
                )
                ids.append(object_id)
            response = self._request("POST", "/v1/batch/objects", json={"objects": objects})
            response.raise_for_status()
            # Weaviate batch returns per-object status; surface the first failure
            # so callers know which chunk to retry instead of trusting HTTP 200.
            for item in response.json():
                result = item.get("result") or {}
                errors = (result.get("errors") or {}).get("error") or []
                if errors:
                    msg = f"Weaviate batch insert failed: {errors}"
                    raise RuntimeError(msg)
        return ids

    def _object_id(self, chunk: ChunkRecord) -> str:
        return str(uuid5(NAMESPACE_URL, f"{chunk.doc_id}:{chunk.chunk_id}"))

    def _properties_for(self, chunk: ChunkRecord) -> dict[str, Any]:
        return {
            "doc_id": chunk.doc_id,
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "source_path": chunk.source_path,
            "doc_type": chunk.doc_type,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "sha256": chunk.sha256,
            "metadata_json": json.dumps(chunk.metadata_json, sort_keys=True),
        }

    def hybrid_search(
        self,
        query: str,
        filters: dict[str, FilterValue] | None = None,
        alpha: float = 0.5,
        limit: int = 10,
        *,
        exclude_doc_types: Sequence[str] | None = None,
    ) -> list[SearchResult]:
        """Hybrid search with optional doc_type exclusion and BM25-only fallback.

        If the embeddings provider raises (transient outage, missing key, quota
        exhausted), we degrade to BM25-only (alpha=0, empty vector) instead of
        failing the whole search. This keeps `/chat` and `/research` responsive
        when the embeddings tier is down, at the cost of pure-keyword recall.
        """
        self.ensure_collection()
        try:
            query_embedding = self._embedding_provider.embed_text(query, kind="query")
            effective_alpha = alpha
        except Exception:
            query_embedding = []
            effective_alpha = 0.0
        graphql = self._build_hybrid_query(
            query=query,
            query_embedding=query_embedding,
            filters=filters or {},
            alpha=effective_alpha,
            limit=limit,
            exclude_doc_types=list(exclude_doc_types or ()),
        )
        response = self._request("POST", "/v1/graphql", json={"query": graphql})
        response.raise_for_status()
        payload = response.json()
        errors = payload.get("errors")
        if errors:
            msg = f"Weaviate hybrid search failed: {errors}"
            raise RuntimeError(msg)
        rows = payload["data"]["Get"].get(self._collection_name, [])
        return [self._result_from_row(row) for row in rows]

    def delete_by_doc_id(self, doc_id: str) -> None:
        where_filter = {
            "path": ["doc_id"],
            "operator": "Equal",
            "valueText": doc_id,
        }
        self._request(
            "DELETE",
            f"/v1/batch/objects?class={self._collection_name}",
            json={"match": {"class": self._collection_name, "where": where_filter}},
        ).raise_for_status()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return retry_transient_http(
            lambda: httpx.request(
                method,
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                timeout=self._timeout,
                **kwargs,
            )
        )

    def _build_hybrid_query(
        self,
        *,
        query: str,
        query_embedding: list[float],
        filters: dict[str, FilterValue],
        alpha: float,
        limit: int,
        exclude_doc_types: list[str] | None = None,
    ) -> str:
        where_clause = self._build_where_clause(filters, exclude_doc_types=exclude_doc_types or [])
        where_arg = f"\n        where: {where_clause}" if where_clause else ""
        # Omit `vector:` when we have no embedding (BM25-only fallback) so Weaviate
        # doesn't reject an empty vector. With alpha=0 Weaviate uses keyword search
        # regardless of the vector field, but emitting an empty `vector: []`
        # produces a schema error in some Weaviate versions.
        vector_arg = (
            f"\n                vector: {json.dumps(query_embedding)}" if query_embedding else ""
        )
        return f"""
        {{
          Get {{
            {self._collection_name}(
              hybrid: {{
                query: {json.dumps(query)}{vector_arg}
                alpha: {alpha}
              }}
              limit: {limit}{where_arg}
            ) {{
              doc_id
              chunk_id
              text
              source_path
              doc_type
              page_start
              page_end
              sha256
              metadata_json
              _additional {{
                score
                explainScore
              }}
            }}
          }}
        }}
        """

    def _build_where_clause(
        self,
        filters: dict[str, FilterValue],
        *,
        exclude_doc_types: list[str] | None = None,
    ) -> str | None:
        operands = [self._where_operand(key, value) for key, value in filters.items()]
        for excluded in exclude_doc_types or []:
            operands.append(self._where_not_equal_operand("doc_type", excluded))
        if not operands:
            return None
        if len(operands) == 1:
            return operands[0]
        return "{operator: And, operands: [" + ", ".join(operands) + "]}"

    def _where_operand(self, key: str, value: FilterValue) -> str:
        if isinstance(value, bool):
            value_field = f"valueBoolean: {str(value).lower()}"
        elif isinstance(value, int):
            value_field = f"valueInt: {value}"
        else:
            value_field = f"valueText: {json.dumps(value)}"
        return f"{{path: [{json.dumps(key)}], operator: Equal, {value_field}}}"

    def _where_not_equal_operand(self, key: str, value: str) -> str:
        return f"{{path: [{json.dumps(key)}], operator: NotEqual, valueText: {json.dumps(value)}}}"

    def _result_from_row(self, row: dict[str, Any]) -> SearchResult:
        additional = row.get("_additional", {})
        metadata_raw = row.get("metadata_json") or "{}"
        metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
        return SearchResult(
            doc_id=str(row["doc_id"]),
            chunk_id=str(row["chunk_id"]),
            text=str(row["text"]),
            source_path=str(row["source_path"]),
            doc_type=str(row["doc_type"]),
            page_start=int(row["page_start"]),
            page_end=int(row["page_end"]),
            sha256=str(row["sha256"]),
            metadata_json=metadata,
            score=_parse_optional_float(additional.get("score")),
            explain_score=additional.get("explainScore"),
        )


def _parse_optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float | str):
        return float(value)
    msg = f"Cannot parse float from {type(value).__name__}"
    raise TypeError(msg)

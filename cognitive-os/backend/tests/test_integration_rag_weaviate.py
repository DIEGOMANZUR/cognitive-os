from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretStr

from cognitive_os.memory.embeddings import EmbeddingProvider
from cognitive_os.memory.retrieval import retrieve_context
from cognitive_os.memory.weaviate_store import ChunkRecord, WeaviateStore

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class HashEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int = 8) -> None:
        self._dimension = dimension

    def embed_text(self, text: str, *, kind: str = "document") -> list[float]:
        del kind
        digest = hashlib.sha256(text.lower().encode("utf-8")).digest()
        return [(digest[index] / 255.0) for index in range(self._dimension)]

    def embed_texts(self, texts: list[str], *, kind: str = "document") -> list[list[float]]:
        return [self.embed_text(text, kind=kind) for text in texts]


def _docker_is_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )
    return result.returncode == 0


def _load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (PROJECT_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _docker_is_available(), reason="Docker is not available"),
]


def _store() -> WeaviateStore:
    env = _load_env()
    return WeaviateStore(
        base_url=env.get("WEAVIATE_URL", os.environ.get("WEAVIATE_URL", "http://localhost:8081")),
        api_key=SecretStr(env["WEAVIATE_API_KEY"]),
        embedding_provider=HashEmbeddingProvider(),
        collection_name=f"IntegrationDocumentChunk{uuid4().hex}",
    )


def test_insert_chunk_and_hybrid_search() -> None:
    store = _store()
    doc_id = f"doc-{uuid4()}"
    try:
        store.insert_chunk(
            ChunkRecord(
                doc_id=doc_id,
                chunk_id="chunk-1",
                text="Cognitive OS stores operational memory in a vector database.",
                source_path="/tmp/rag-test.md",
                doc_type="markdown",
                page_start=1,
                page_end=1,
                sha256="b" * 64,
                metadata_json={"kind": "integration"},
            )
        )
        store.insert_chunk(
            ChunkRecord(
                doc_id=doc_id,
                chunk_id="chunk-2",
                text="A cooking recipe talks about salt and tomatoes.",
                source_path="/tmp/rag-test.md",
                doc_type="markdown",
                page_start=2,
                page_end=2,
                sha256="c" * 64,
                metadata_json={"kind": "integration"},
            )
        )

        results = store.hybrid_search(
            "operational memory vector database",
            filters={"doc_id": doc_id},
            alpha=0.5,
            limit=5,
        )

        assert results
        assert results[0].doc_id == doc_id
        assert results[0].metadata_json["kind"] == "integration"
        # Citation now renders the basename (no absolute path leak).
        assert results[0].citation.startswith("rag-test.md:")
        assert results[0].source_path == "/tmp/rag-test.md"
    finally:
        store.delete_by_doc_id(doc_id)


def test_retrieve_context_with_weaviate() -> None:
    store = _store()
    doc_id = f"doc-{uuid4()}"
    try:
        store.insert_chunk(
            ChunkRecord(
                doc_id=doc_id,
                chunk_id="ctx-1",
                text="LangGraph agents need cited context from reliable retrieval.",
                source_path="/tmp/context-test.md",
                doc_type="markdown",
                page_start=3,
                page_end=4,
                sha256="d" * 64,
                metadata_json={"kind": "context"},
            )
        )

        contexts = retrieve_context(
            "cited context retrieval",
            filters={"doc_id": doc_id},
            store=store,
        )

        assert contexts
        assert contexts[0].citation == "context-test.md:3-4"
        assert contexts[0].metadata["source_path"] == "/tmp/context-test.md"
    finally:
        store.delete_by_doc_id(doc_id)

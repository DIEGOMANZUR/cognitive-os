from __future__ import annotations

import os

import pytest

from cognitive_os.memory.reranker import LocalReranker
from cognitive_os.memory.weaviate_store import SearchResult


def _result(chunk_id: str, text: str) -> SearchResult:
    return SearchResult(
        doc_id="doc",
        chunk_id=chunk_id,
        text=text,
        source_path="/tmp/source.txt",
        doc_type="text",
        page_start=1,
        page_end=1,
        sha256="e" * 64,
        metadata_json={},
        score=None,
        explain_score=None,
    )


@pytest.mark.slow
@pytest.mark.skipif(os.environ.get("RUN_SLOW_RERANKER") != "1", reason="slow reranker disabled")
def test_real_reranker_or_fallback_does_not_download() -> None:
    reranker = LocalReranker(enabled=True, model_name="BAAI/bge-reranker-base")

    ranked = reranker.rerank(
        "alpha beta",
        [
            _result("a", "alpha beta gamma"),
            _result("b", "unrelated words"),
        ],
        limit=1,
    )

    assert ranked[0].chunk_id == "a"

"""Regression tests covering all bugs fixed in this session."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from cognitive_os.agents.state import BudgetState, RetrievalCitation
from cognitive_os.deepagents.memory_consolidation import (
    DeepAgentMemoryConsolidator,
    _is_learning_event,
    _lesson_from_event,
)
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService
from cognitive_os.deepagents.research_deepagent import _report_markdown
from cognitive_os.deepagents.schemas import DeepAgentCitation, DeepAgentResult
from cognitive_os.ingestion.pipeline import DocumentIngestionPipeline
from cognitive_os.memory.weaviate_store import WeaviateStore

# ---------------------------------------------------------------------------
# BudgetState.max_tokens
# ---------------------------------------------------------------------------


def test_budget_state_default_max_tokens_fits_gpt5() -> None:
    budget = BudgetState()
    assert budget.max_tokens >= 100_000, (
        f"max_tokens={budget.max_tokens} is too low for gpt-5; should be >= 100_000"
    )


# ---------------------------------------------------------------------------
# final_response citation formatting (newlines, not spaces)
# ---------------------------------------------------------------------------


def test_final_response_citation_uses_newlines() -> None:
    from cognitive_os.agents.graph import final_response_node
    from cognitive_os.agents.state import AgentResult, CognitiveState

    state: CognitiveState = {
        "agent_result": AgentResult(
            route="research",
            content="Here is the answer.",
            citations=[
                RetrievalCitation(source_path="/a/b.pdf", page_start=1, page_end=2),
                RetrievalCitation(source_path="/a/c.pdf", page_start=3, page_end=4),
            ],
        ),
        "messages": [],
        "thread_id": "t1",
        "user_id": "u1",
        "error_count": 0,
    }

    updated = final_response_node(state)
    ai_content = updated["messages"][0].content  # type: ignore[index]
    # Citations must be on separate lines, not space-joined
    assert "\n-" in ai_content, "Citations should be newline-separated list items"
    # Citations use the basename (b.pdf) rather than the absolute path (/a/b.pdf)
    # so we never leak the ingestor's filesystem layout to the user.
    assert ai_content.count("b.pdf") == 1
    assert ai_content.count("c.pdf") == 1
    assert "/a/" not in ai_content, "absolute path should not leak into citation"


# ---------------------------------------------------------------------------
# _report_markdown — readable citation format
# ---------------------------------------------------------------------------


def test_report_markdown_citations_are_readable() -> None:
    result = DeepAgentResult(
        task_id="t",
        thread_id="th",
        status="ok",
        answer="The answer.",
        findings=["Finding 1"],
        citations=[
            DeepAgentCitation(
                source_type="local_doc",
                doc_id="aaaa-bbbb",
                chunk_id="chunk-1",
                title="My Document",
                page_start=2,
                page_end=3,
                quote="Relevant snippet",
            )
        ],
        uncertainty_notes=[],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=None,
    )
    report = _report_markdown(result)

    # Should NOT contain raw Python dict representation
    assert "model_dump" not in report
    assert "{'source_type'" not in report
    # Should contain readable fields
    assert "doc_id=aaaa-bbbb" in report
    assert "chunk_id=chunk-1" in report
    assert "Relevant snippet" in report


# ---------------------------------------------------------------------------
# WeaviateStore.ensure_collection caching
# ---------------------------------------------------------------------------


def test_weaviate_ensure_collection_cached_after_first_call() -> None:
    mock_request = MagicMock()
    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200

    mock_embedding_provider = MagicMock()
    from pydantic import SecretStr

    store = WeaviateStore(
        base_url="http://fake-weaviate:8080",
        api_key=SecretStr("fake-key"),
        embedding_provider=mock_embedding_provider,
    )
    store._request = mock_request  # type: ignore[method-assign]
    mock_request.return_value = mock_response_200

    store.ensure_collection()
    store.ensure_collection()
    store.ensure_collection()

    # Should only make ONE real HTTP call after caching
    assert mock_request.call_count == 1, (
        f"Expected 1 HTTP call after caching, got {mock_request.call_count}"
    )


def test_weaviate_ensure_collection_flag_starts_false() -> None:
    from pydantic import SecretStr

    store = WeaviateStore(
        base_url="http://fake:8080",
        api_key=SecretStr("x"),
        embedding_provider=MagicMock(),
    )
    assert store._collection_ensured is False


# ---------------------------------------------------------------------------
# Memory consolidation learns from successes AND failures
# ---------------------------------------------------------------------------


def test_is_learning_event_captures_failures() -> None:
    assert _is_learning_event("agent_failed", "Fallback triggered") is True
    assert _is_learning_event("ingestion_failed", "Weaviate down") is True


def test_is_learning_event_captures_successes() -> None:
    assert _is_learning_event("ingestion_completed", "3 chunks indexed") is True
    assert _is_learning_event("deepagent_research_finished", "ok") is True


def test_lesson_from_event_labels_positive_vs_negative() -> None:
    positive = _lesson_from_event("ingestion_completed", "100 chunks indexed")
    negative = _lesson_from_event("agent_failed", "Weaviate timeout")

    assert "Success pattern" in positive
    assert "Failure pattern" in negative


@pytest.mark.asyncio
async def test_consolidation_learns_from_success_event() -> None:
    service = DeepAgentMemoryService(use_database=False)
    consolidator = DeepAgentMemoryConsolidator(
        service,
        job_events=[
            {
                "thread_id": "thread-success",
                "agent_name": "research",
                "event_type": "ingestion_completed",
                "message": "Document indexed with 42 chunks.",
                "created_at": None,
            }
        ],
    )

    proposals = await consolidator.consolidate_thread("thread-success")

    assert len(proposals) == 1
    assert "Success pattern" in proposals[0].proposed_content


# ---------------------------------------------------------------------------
# web_indexer module exists and is importable
# ---------------------------------------------------------------------------


def test_web_indexer_importable() -> None:
    from cognitive_os.memory.web_indexer import index_web_results_async

    assert callable(index_web_results_async)


def test_web_indexer_noop_for_empty_results() -> None:
    from cognitive_os.memory.web_indexer import index_web_results_async

    # Should not raise even with empty list
    index_web_results_async(query="anything", results=[])


# ---------------------------------------------------------------------------
# Ingestion failures are finalized consistently
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingestion_finalizes_failed_job_when_extraction_crashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% intentionally incomplete")
    document_id = uuid4()
    job_id = uuid4()
    finalizations: list[dict[str, object]] = []
    pipeline = DocumentIngestionPipeline(storage_dir=tmp_path / "storage")

    async def create_record(*args: object, **kwargs: object) -> tuple[object, object]:
        del args, kwargs
        return document_id, job_id

    def copy_original(*args: object, **kwargs: object) -> Path:
        del kwargs
        return Path(args[0])

    def extract_pages(*args: object, **kwargs: object) -> list[object]:
        del args, kwargs
        raise RuntimeError("extract failed")

    async def finalize_job(**kwargs: object) -> None:
        finalizations.append(kwargs)

    monkeypatch.setattr(pipeline, "_create_document_record", create_record)
    monkeypatch.setattr(pipeline, "_copy_original", copy_original)
    monkeypatch.setattr(pipeline, "_extract_pages", extract_pages)
    monkeypatch.setattr(pipeline, "_finalize_job", finalize_job)

    with pytest.raises(RuntimeError, match="extract failed"):
        await pipeline.ingest_pdf_for_job(pdf_path, job_id=job_id)

    assert finalizations == [
        {
            "job_id": job_id,
            "document_id": document_id,
            "status": "failed",
            "event_message": "Ingestion failed: RuntimeError: extract failed",
        }
    ]

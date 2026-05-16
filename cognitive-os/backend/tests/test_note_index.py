from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import httpx
import pytest

from cognitive_os.api.app import app
from cognitive_os.assist.note_index import NOTE_DOC_TYPE, NoteIndexService
from cognitive_os.assist.schemas import PersonalNoteView
from cognitive_os.memory.weaviate_store import ChunkRecord, FilterValue, SearchResult


class FakeNoteStore:
    """In-memory stand-in for `WeaviateStore` satisfying the `NoteVectorStore` Protocol."""

    def __init__(self, *, raise_on: set[str] | None = None) -> None:
        self.objects: dict[str, ChunkRecord] = {}
        self.raise_on = raise_on or set()
        self.deleted: list[str] = []

    def insert_chunk(self, chunk: ChunkRecord) -> str:
        if "insert" in self.raise_on:
            raise RuntimeError("weaviate insert down")
        self.objects[chunk.doc_id] = chunk
        return chunk.doc_id

    def delete_by_doc_id(self, doc_id: str) -> None:
        if "delete" in self.raise_on:
            raise RuntimeError("weaviate delete down")
        self.deleted.append(doc_id)
        self.objects.pop(doc_id, None)

    def hybrid_search(
        self,
        query: str,
        filters: dict[str, FilterValue] | None = None,
        alpha: float = 0.5,
        limit: int = 10,
        *,
        exclude_doc_types: Sequence[str] | None = None,
    ) -> list[SearchResult]:
        if "search" in self.raise_on:
            raise RuntimeError("weaviate search down")
        results: list[SearchResult] = []
        for chunk in self.objects.values():
            if filters and filters.get("doc_type") not in (None, chunk.doc_type):
                continue
            results.append(
                SearchResult(
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    source_path=chunk.source_path,
                    doc_type=chunk.doc_type,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    sha256=chunk.sha256,
                    metadata_json=chunk.metadata_json,
                    score=0.9,
                    explain_score=None,
                )
            )
        return results[:limit]


def _note(note_id: str, user_id: str, title: str, body: str = "") -> PersonalNoteView:
    now = datetime.now(UTC)
    return PersonalNoteView(
        id=note_id,
        user_id=user_id,
        title=title,
        body_markdown=body,
        tags=["personal"],
        created_at=now,
        updated_at=now,
    )


def test_index_note_writes_note_doc_type_and_is_idempotent() -> None:
    store = FakeNoteStore()
    service = NoteIndexService(store=store)

    assert service.index_note(_note("n1", "user-a", "Groceries", "milk and eggs")) is True
    chunk = store.objects["n1"]
    assert chunk.doc_type == NOTE_DOC_TYPE
    assert chunk.metadata_json["user_id"] == "user-a"
    assert "milk and eggs" in chunk.text

    # Re-indexing (update path) deletes the stale vector first, then re-inserts.
    assert service.index_note(_note("n1", "user-a", "Groceries", "milk, eggs, bread")) is True
    assert store.deleted.count("n1") == 2
    assert "bread" in store.objects["n1"].text


def test_index_note_degrades_gracefully_when_store_raises() -> None:
    store = FakeNoteStore(raise_on={"insert"})
    service = NoteIndexService(store=store)
    assert service.index_note(_note("n2", "user-a", "Title")) is False


def test_remove_note_calls_store_delete() -> None:
    store = FakeNoteStore()
    service = NoteIndexService(store=store)
    service.index_note(_note("n3", "user-a", "Title"))
    assert service.remove_note("n3") is True
    assert "n3" in store.deleted
    assert "n3" not in store.objects


def test_search_notes_post_filters_by_user_and_caps_limit() -> None:
    store = FakeNoteStore()
    service = NoteIndexService(store=store)
    service.index_note(_note("a1", "user-a", "Alpha", "shared keyword"))
    service.index_note(_note("a2", "user-a", "Beta", "shared keyword"))
    service.index_note(_note("b1", "user-b", "Gamma", "shared keyword"))

    hits = service.search_notes("user-a", "shared keyword", limit=10)
    assert {hit.note_id for hit in hits} == {"a1", "a2"}
    assert all(hit.title for hit in hits)

    capped = service.search_notes("user-a", "shared keyword", limit=1)
    assert len(capped) == 1


def test_search_notes_empty_query_and_store_failure_return_empty() -> None:
    store = FakeNoteStore()
    service = NoteIndexService(store=store)
    service.index_note(_note("c1", "user-a", "Title", "body"))
    assert service.search_notes("user-a", "   ", limit=5) == []

    failing = NoteIndexService(store=FakeNoteStore(raise_on={"search"}))
    assert failing.search_notes("user-a", "anything", limit=5) == []


@pytest.mark.asyncio
async def test_search_notes_endpoint_requires_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/assist/notes/search", params={"q": "anything"})
    assert resp.status_code == 401

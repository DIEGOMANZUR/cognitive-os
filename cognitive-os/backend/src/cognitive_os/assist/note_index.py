from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Protocol

import structlog

from cognitive_os.assist.schemas import PersonalNoteSearchHit, PersonalNoteView
from cognitive_os.memory.retrieval import build_weaviate_store
from cognitive_os.memory.weaviate_store import ChunkRecord, FilterValue, SearchResult

log = structlog.get_logger(__name__)

NOTE_DOC_TYPE = "note"


class NoteVectorStore(Protocol):
    """Subset of `WeaviateStore` used by `NoteIndexService`.

    A Protocol keeps the indexer testable without a live Weaviate: tests inject
    an in-memory fake that satisfies these three calls.
    """

    def insert_chunk(self, chunk: ChunkRecord) -> str: ...

    def delete_by_doc_id(self, doc_id: str) -> None: ...

    def hybrid_search(
        self,
        query: str,
        filters: dict[str, FilterValue] | None = None,
        alpha: float = 0.5,
        limit: int = 10,
        *,
        exclude_doc_types: Sequence[str] | None = None,
    ) -> list[SearchResult]: ...


def _note_text(title: str, body_markdown: str) -> str:
    title = title.strip()
    body = body_markdown.strip()
    return f"{title}\n\n{body}" if body else title


class NoteIndexService:
    """Indexes `PersonalNote` rows into Weaviate (`doc_type='note'`) for semantic recall.

    Every operation is best-effort: a Weaviate outage must never break note CRUD,
    so mutations swallow errors and the search path degrades to an empty list.
    This mirrors the `_safe_retriever` degradation policy in the chat path.

    User isolation: the Weaviate `DocumentChunk` schema has no per-user property,
    so `user_id` is stored inside `metadata_json` and search post-filters in
    Python after a `doc_type='note'` hybrid query. Personal-assistant scale makes
    the over-fetch (`limit * 5` candidates) negligible.
    """

    def __init__(self, store: NoteVectorStore | None = None) -> None:
        self._store = store
        self._store_resolved = store is not None

    def _resolve_store(self) -> NoteVectorStore | None:
        if self._store_resolved:
            return self._store
        self._store_resolved = True
        try:
            self._store = build_weaviate_store()
        except Exception as exc:  # pragma: no cover - depends on runtime config
            log.warning("note_index_store_unavailable", error=str(exc))
            self._store = None
        return self._store

    def index_note(self, note: PersonalNoteView) -> bool:
        """Idempotently (re)index a note. Returns False when indexing was skipped."""
        store = self._resolve_store()
        if store is None:
            return False
        text = _note_text(note.title, note.body_markdown)
        record = ChunkRecord(
            doc_id=note.id,
            chunk_id=note.id,
            text=text,
            source_path=f"note://{note.id}",
            doc_type=NOTE_DOC_TYPE,
            page_start=1,
            page_end=1,
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            metadata_json={
                "note_id": note.id,
                "user_id": note.user_id,
                "title": note.title,
                "tags": list(note.tags),
            },
        )
        try:
            # delete-then-insert: Weaviate rejects re-POSTing an existing object id,
            # so an update must clear the old vector first. Deleting a missing
            # doc_id is a no-op, so this also covers first-time create.
            store.delete_by_doc_id(note.id)
            store.insert_chunk(record)
        except Exception as exc:
            log.warning("note_index_failed", note_id=note.id, error=str(exc))
            return False
        return True

    def remove_note(self, note_id: str) -> bool:
        store = self._resolve_store()
        if store is None:
            return False
        try:
            store.delete_by_doc_id(note_id)
        except Exception as exc:
            log.warning("note_index_delete_failed", note_id=note_id, error=str(exc))
            return False
        return True

    def search_notes(
        self,
        user_id: str,
        query: str,
        *,
        limit: int = 10,
    ) -> list[PersonalNoteSearchHit]:
        store = self._resolve_store()
        scoped_user = user_id.strip()
        if store is None or not query.strip() or not scoped_user:
            return []
        capped = max(1, min(limit, 50))
        try:
            results = store.hybrid_search(
                query,
                filters={"doc_type": NOTE_DOC_TYPE},
                limit=capped * 5,
            )
        except Exception as exc:
            log.warning("note_search_failed", error=str(exc))
            return []
        hits: list[PersonalNoteSearchHit] = []
        for result in results:
            meta = result.metadata_json or {}
            if str(meta.get("user_id", "")) != scoped_user:
                continue
            hits.append(
                PersonalNoteSearchHit(
                    note_id=str(meta.get("note_id") or result.doc_id),
                    title=str(meta.get("title") or ""),
                    snippet=result.text[:500],
                    tags=[str(tag) for tag in (meta.get("tags") or [])],
                    score=result.score,
                )
            )
            if len(hits) >= capped:
                break
        return hits

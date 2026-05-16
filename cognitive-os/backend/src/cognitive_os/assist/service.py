from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import nullslast, select, update

from cognitive_os.assist.note_index import NoteIndexService
from cognitive_os.assist.schemas import (
    PersonalNoteCreate,
    PersonalNoteSearchHit,
    PersonalNoteUpdate,
    PersonalNoteView,
    PersonalTaskCreate,
    PersonalTaskUpdate,
    PersonalTaskView,
)
from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import PersonalNote, PersonalTask


class PersonalAssistDisabledError(RuntimeError):
    """Raised when ENABLE_PERSONAL_ASSISTANT_API is false."""


class PersonalAssistService:
    """CRUD helpers for personal Tasks/Notes (scoped per API user id / Telegram-derived id)."""

    def __init__(
        self,
        app_settings: Settings = settings,
        note_indexer: NoteIndexService | None = None,
    ) -> None:
        self._settings = app_settings
        self._note_indexer = note_indexer or NoteIndexService()

    async def _index_note_safe(self, view: PersonalNoteView) -> None:
        """Best-effort vector indexing off the event loop; never raises."""
        await asyncio.to_thread(self._note_indexer.index_note, view)

    async def _unindex_note_safe(self, note_id: str) -> None:
        await asyncio.to_thread(self._note_indexer.remove_note, note_id)

    def _require_enabled(self) -> None:
        if not getattr(self._settings, "enable_personal_assistant_api", True):
            msg = "Personal assistant API disabled."
            raise PersonalAssistDisabledError(msg)

    @staticmethod
    def _serialize_tags(raw: object) -> list[str]:
        if isinstance(raw, list):
            return [str(x) for x in raw][:64]
        return []

    async def create_task(self, user_id: str, body: PersonalTaskCreate) -> PersonalTaskView:
        self._require_enabled()
        row = PersonalTask(
            user_id=user_id.strip(),
            title=body.title.strip(),
            description=body.description.strip() if body.description else None,
            status="pending",
            priority=body.priority,
            due_at=body.due_at,
            remind_at=body.remind_at,
            tags=body.tags,
        )
        async with session_scope() as session:
            session.add(row)
            await session.flush()
            return self._task_to_view(row)

    async def list_tasks(
        self,
        user_id: str,
        *,
        statuses: list[str] | None = None,
        limit: int = 80,
    ) -> list[PersonalTaskView]:
        self._require_enabled()
        capped = max(1, min(limit, 200))
        stmt = (
            select(PersonalTask)
            .where(PersonalTask.user_id == user_id.strip())
            .order_by(
                nullslast(PersonalTask.due_at),
                PersonalTask.priority,
                PersonalTask.created_at.desc(),
            )
        )
        if statuses:
            stmt = stmt.where(PersonalTask.status.in_(statuses))
        stmt = stmt.limit(capped)
        async with session_scope() as session:
            result = await session.execute(stmt)
            return [self._task_to_view(r) for r in result.scalars().all()]

    async def get_task(self, user_id: str, task_id: UUID) -> PersonalTaskView | None:
        self._require_enabled()
        async with session_scope() as session:
            row = await session.get(PersonalTask, task_id)
            if row is None or row.user_id != user_id.strip():
                return None
            return self._task_to_view(row)

    async def update_task(
        self,
        user_id: str,
        task_id: UUID,
        body: PersonalTaskUpdate,
    ) -> PersonalTaskView | None:
        self._require_enabled()
        async with session_scope() as session:
            row = await session.get(PersonalTask, task_id)
            if row is None or row.user_id != user_id.strip():
                return None

            vals: dict[str, object] = {}
            if body.title is not None:
                vals["title"] = body.title.strip()
            if body.description is not None:
                vals["description"] = body.description.strip() or None
            if body.status is not None:
                vals["status"] = body.status
                if body.status == "done":
                    vals["completed_at"] = datetime.now(UTC)
            if body.priority is not None:
                vals["priority"] = body.priority
            if body.due_at is not None:
                vals["due_at"] = body.due_at
            if body.remind_at is not None:
                vals["remind_at"] = body.remind_at
                meta = dict(row.metadata_json or {})
                meta.pop("reminder_sent_for", None)
                vals["metadata_json"] = meta
            if body.tags is not None:
                vals["tags"] = body.tags

            if vals:
                await session.execute(
                    update(PersonalTask).where(PersonalTask.id == task_id).values(**vals)
                )
            await session.refresh(row)
            return self._task_to_view(row)

    async def delete_task(self, user_id: str, task_id: UUID) -> bool:
        self._require_enabled()
        async with session_scope() as session:
            row = await session.get(PersonalTask, task_id)
            if row is None or row.user_id != user_id.strip():
                return False
            await session.delete(row)
        return True

    async def create_note(self, user_id: str, body: PersonalNoteCreate) -> PersonalNoteView:
        self._require_enabled()
        row = PersonalNote(
            user_id=user_id.strip(),
            title=body.title.strip(),
            body_markdown=body.body_markdown,
            tags=body.tags,
        )
        async with session_scope() as session:
            session.add(row)
            await session.flush()
            view = self._note_to_view(row)
        await self._index_note_safe(view)
        return view

    async def search_notes(
        self,
        user_id: str,
        query: str,
        *,
        limit: int = 10,
    ) -> list[PersonalNoteSearchHit]:
        self._require_enabled()
        return await asyncio.to_thread(
            self._note_indexer.search_notes,
            user_id.strip(),
            query,
            limit=limit,
        )

    async def list_notes(self, user_id: str, *, limit: int = 50) -> list[PersonalNoteView]:
        self._require_enabled()
        capped = max(1, min(limit, 100))
        async with session_scope() as session:
            result = await session.execute(
                select(PersonalNote)
                .where(PersonalNote.user_id == user_id.strip())
                .order_by(PersonalNote.updated_at.desc())
                .limit(capped)
            )
            return [self._note_to_view(r) for r in result.scalars().all()]

    async def get_note(self, user_id: str, note_id: UUID) -> PersonalNoteView | None:
        self._require_enabled()
        async with session_scope() as session:
            row = await session.get(PersonalNote, note_id)
            if row is None or row.user_id != user_id.strip():
                return None
            return self._note_to_view(row)

    async def update_note(
        self,
        user_id: str,
        note_id: UUID,
        body: PersonalNoteUpdate,
    ) -> PersonalNoteView | None:
        self._require_enabled()
        async with session_scope() as session:
            row = await session.get(PersonalNote, note_id)
            if row is None or row.user_id != user_id.strip():
                return None
            vals: dict[str, object] = {}
            if body.title is not None:
                vals["title"] = body.title.strip()
            if body.body_markdown is not None:
                vals["body_markdown"] = body.body_markdown
            if body.tags is not None:
                vals["tags"] = body.tags
            if vals:
                await session.execute(
                    update(PersonalNote).where(PersonalNote.id == note_id).values(**vals)
                )
                await session.refresh(row)
            view = self._note_to_view(row)
        await self._index_note_safe(view)
        return view

    async def delete_note(self, user_id: str, note_id: UUID) -> bool:
        self._require_enabled()
        async with session_scope() as session:
            row = await session.get(PersonalNote, note_id)
            if row is None or row.user_id != user_id.strip():
                return False
            await session.delete(row)
        await self._unindex_note_safe(str(note_id))
        return True

    def _task_to_view(self, row: PersonalTask) -> PersonalTaskView:
        return PersonalTaskView(
            id=str(row.id),
            user_id=row.user_id,
            title=row.title,
            description=row.description,
            status=row.status,
            priority=int(row.priority),
            due_at=row.due_at,
            remind_at=row.remind_at,
            completed_at=row.completed_at,
            tags=self._serialize_tags(row.tags),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _note_to_view(self, row: PersonalNote) -> PersonalNoteView:
        return PersonalNoteView(
            id=str(row.id),
            user_id=row.user_id,
            title=row.title,
            body_markdown=row.body_markdown,
            tags=self._serialize_tags(row.tags),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

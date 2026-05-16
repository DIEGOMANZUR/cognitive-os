from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cognitive_os.db.models import Document, DocumentPage


@dataclass(frozen=True)
class DocumentPageCreate:
    page_number: int
    sha256: str | None = None
    text: str | None = None
    metadata_json: dict[str, Any] | None = None


class DocumentRepository:
    """Minimal CRUD operations for documents."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        source_path: str,
        sha256: str,
        title: str | None = None,
        status: str = "pending",
        pages: list[DocumentPageCreate] | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> Document:
        document = Document(
            source_path=source_path,
            sha256=sha256,
            title=title,
            status=status,
            metadata_json=metadata_json or {},
        )
        self._session.add(document)
        await self._session.flush()

        for page in pages or []:
            self._session.add(
                DocumentPage(
                    document_id=document.id,
                    page_number=page.page_number,
                    sha256=page.sha256,
                    text=page.text,
                    status=status,
                    metadata_json=page.metadata_json or {},
                )
            )

        await self._session.flush()
        return document

    async def get(self, document_id: UUID) -> Document | None:
        return await self._session.get(Document, document_id)

    async def get_with_pages(self, document_id: UUID) -> Document | None:
        result = await self._session.execute(
            select(Document).options(selectinload(Document.pages)).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

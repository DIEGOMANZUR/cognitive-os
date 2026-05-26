from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from sqlalchemy import select

from cognitive_os.core.db import session_scope
from cognitive_os.db.models import AuditEvent, Document, DocumentChunk, DocumentPage


CANONICAL_DOCUMENTS = [
    "README.md",
    "docs/COGNITIVE_OS_GUIDE.md",
    "docs/USER_GUIDE.md",
    "docs/ARCHITECTURE.md",
    "docs/RUNBOOK.md",
    "docs/CURRENT_STATE.md",
]

CHUNK_SIZE = 1800
CHUNK_OVERLAP = 180


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def chunk_text(text: str) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + CHUNK_SIZE)
        if end < len(normalized):
            paragraph_break = normalized.rfind("\n\n", start, end)
            if paragraph_break > start + 400:
                end = paragraph_break
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(0, end - CHUNK_OVERLAP)
    return chunks


async def seed() -> None:
    root = repo_root()
    inserted = 0
    skipped = 0

    async with session_scope() as session:
        for relative in CANONICAL_DOCUMENTS:
            path = (root / relative).resolve()
            if not path.exists():
                continue
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            sha256 = hashlib.sha256(raw).hexdigest()
            source_path = str(path)

            existing = await session.scalar(
                select(Document).where(
                    Document.sha256 == sha256,
                    Document.source_path == source_path,
                )
            )
            if existing is not None:
                skipped += 1
                continue

            chunks = chunk_text(text)
            document = Document(
                source_path=source_path,
                sha256=sha256,
                title=path.stem.replace("_", " ").replace("-", " ").title(),
                status="indexed",
                metadata_json={
                    "page_count": 1,
                    "document_kind": "markdown",
                    "bootstrap_source": "canonical_project_documentation",
                    "source_relative_path": relative,
                },
            )
            session.add(document)
            await session.flush()

            page = DocumentPage(
                document_id=document.id,
                page_number=1,
                sha256=sha256,
                text=text,
                extraction_method="markdown",
                confidence_score=100,
                warnings=[],
                metadata_json={
                    "document_kind": "markdown",
                    "source_relative_path": relative,
                },
            )
            session.add(page)
            await session.flush()

            for index, chunk in enumerate(chunks):
                session.add(
                    DocumentChunk(
                        document_id=document.id,
                        page_id=page.id,
                        chunk_id=f"{sha256[:16]}-{index:04d}",
                        chunk_index=index,
                        page_start=1,
                        page_end=1,
                        sha256=hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                        text=chunk,
                        source_path=source_path,
                        doc_type="markdown",
                        status="indexed",
                        metadata_json={
                            "document_sha256": sha256,
                            "source_relative_path": relative,
                        },
                    )
                )
            inserted += 1

        if inserted:
            session.add(
                AuditEvent(
                    actor_id="local-operator",
                    action="documents.bootstrap_canonical_knowledge",
                    resource_type="documents",
                    resource_id="canonical_project_documentation",
                    metadata_json={
                        "inserted": inserted,
                        "skipped": skipped,
                        "source": "backend/scripts/seed_canonical_knowledge.py",
                        "documents": CANONICAL_DOCUMENTS,
                    },
                )
            )

    print(f"canonical knowledge seed complete: inserted={inserted} skipped={skipped}")


if __name__ == "__main__":
    asyncio.run(seed())

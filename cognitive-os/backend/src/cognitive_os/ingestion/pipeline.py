from __future__ import annotations

import asyncio
import hashlib
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import fitz  # type: ignore[import-untyped]
import pytesseract  # type: ignore[import-untyped]
from langchain_text_splitters import RecursiveCharacterTextSplitter
from PIL import Image

from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import Document, DocumentChunk, DocumentPage, Job, JobEvent
from cognitive_os.ingestion.entities import ExtractedEntity, extract_entities
from cognitive_os.ingestion.neo4j import Neo4jEntityWriter
from cognitive_os.memory.retrieval import build_weaviate_store
from cognitive_os.memory.weaviate_store import ChunkRecord, WeaviateStore

MIN_NATIVE_TEXT_CHARS = 20
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150


@dataclass(frozen=True)
class PageExtraction:
    page_number: int
    text: str
    extraction_method: str
    status: str
    sha256: str | None
    confidence_score: int | None
    warnings: list[str]


@dataclass(frozen=True)
class IngestedChunk:
    chunk_id: str
    chunk_index: int
    text: str
    page_start: int
    page_end: int
    sha256: str
    citation: str
    entities: list[ExtractedEntity]


@dataclass(frozen=True)
class IngestionResult:
    document_id: UUID
    job_id: UUID
    sha256: str
    stored_path: Path
    pages: list[PageExtraction]
    chunks: list[IngestedChunk]
    warnings: list[str]


class DocumentIngestionPipeline:
    def __init__(
        self,
        *,
        storage_dir: Path | None = None,
        weaviate_store: WeaviateStore | None = None,
        neo4j_writer: Neo4jEntityWriter | None = None,
        ocr_enabled: bool = True,
        native_text_min_chars: int = MIN_NATIVE_TEXT_CHARS,
    ) -> None:
        self._storage_dir = Path(storage_dir or settings.local_storage_dir)
        self._weaviate_store = weaviate_store
        self._neo4j_writer = neo4j_writer
        self._ocr_enabled = ocr_enabled
        self._native_text_min_chars = native_text_min_chars
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    async def ingest_pdf(self, pdf_path: Path | str) -> IngestionResult:
        return await self.ingest_pdf_for_job(pdf_path)

    async def ingest_pdf_for_job(
        self,
        pdf_path: Path | str,
        *,
        job_id: UUID | None = None,
    ) -> IngestionResult:
        source_path = Path(pdf_path).expanduser().resolve()
        if source_path.suffix.lower() != ".pdf":
            msg = f"Expected PDF file, got: {source_path}"
            raise ValueError(msg)
        if not source_path.exists():
            msg = f"PDF does not exist: {source_path}"
            raise FileNotFoundError(msg)

        document_sha = self._sha256_file(source_path)
        # Re-ingestion dedup: if a previous Document has the same sha256 AND finished
        # cleanly (status=indexed), return that one rather than duplicating pages,
        # chunks and vectors. Documents stuck in "processing"/"failed"/"needs_ocr"
        # are not reused — the user explicitly wants to retry.
        existing = await self._existing_indexed_document(document_sha, source_path)
        if existing is not None:
            return existing

        document_id, active_job_id = await self._create_document_record(
            source_path,
            document_sha,
            job_id=job_id,
        )
        try:
            stored_path = self._copy_original(source_path, document_id)
            pages = self._extract_pages(stored_path)
            chunks = self._chunk_pages(source_path=source_path, doc_id=document_id, pages=pages)
            warnings = [warning for page in pages for warning in page.warnings]
            # First pass writes pages + chunks as `pending_index` so a Weaviate
            # failure cannot leave Postgres claiming "indexed" with no vector.
            entity_warnings = await self._persist_traceability(
                document_id=document_id,
                job_id=active_job_id,
                source_path=source_path,
                stored_path=stored_path,
                pages=pages,
                chunks=chunks,
                document_sha=document_sha,
            )
            warnings.extend(entity_warnings)
            self._insert_weaviate_chunks(
                document_id=document_id,
                job_id=active_job_id,
                source_path=source_path,
                chunks=chunks,
            )
            # Only mark chunks as indexed AFTER Weaviate confirms the insert.
            await self._mark_chunks_indexed(document_id=document_id, job_id=active_job_id)
        except Exception as exc:
            await self._finalize_job(
                job_id=active_job_id,
                document_id=document_id,
                status="failed",
                event_message=f"Ingestion failed: {type(exc).__name__}: {exc}",
            )
            raise

        await self._finalize_job(
            job_id=active_job_id,
            document_id=document_id,
            status="completed",
            event_message=f"Ingestion fully complete: {len(chunks)} chunks indexed in Weaviate",
        )
        return IngestionResult(
            document_id=document_id,
            job_id=active_job_id,
            sha256=document_sha,
            stored_path=stored_path,
            pages=pages,
            chunks=chunks,
            warnings=warnings,
        )

    async def _existing_indexed_document(
        self,
        document_sha: str,
        source_path: Path,
    ) -> IngestionResult | None:
        """Look up a previously indexed Document with the same sha256.

        The dedup contract is intentionally strict: we only reuse rows whose
        document.status == 'indexed' AND whose chunks are all 'indexed'. Anything
        else (failed, processing, pending_index, needs_ocr) means the prior run
        is incomplete and the user wants to retry.

        Best-effort: any DB error degrades to "no dedup" rather than crashing the
        ingestion. The worst case is one extra ingest, which the user explicitly
        asked for.
        """
        from sqlalchemy import select

        try:
            async with session_scope() as session:
                stmt = (
                    select(Document)
                    .where(Document.sha256 == document_sha)
                    .where(Document.status == "indexed")
                )
                document = (await session.execute(stmt)).scalars().first()
                if document is None:
                    return None
                # Fetch pages and chunks; only reuse if EVERY chunk is indexed.
                chunks_stmt = select(DocumentChunk).where(DocumentChunk.document_id == document.id)
                chunk_rows = (await session.execute(chunks_stmt)).scalars().all()
                if not chunk_rows or any(chunk.status != "indexed" for chunk in chunk_rows):
                    return None
                pages_stmt = (
                    select(DocumentPage)
                    .where(DocumentPage.document_id == document.id)
                    .order_by(DocumentPage.page_number)
                )
                page_rows = (await session.execute(pages_stmt)).scalars().all()
        except Exception:
            return None

        stored_path = self._storage_dir / "originals" / f"{document.id}.pdf"
        pages = [
            PageExtraction(
                page_number=row.page_number,
                text=row.text or "",
                extraction_method=row.extraction_method,
                status=row.status,
                sha256=row.sha256,
                confidence_score=row.confidence_score,
                warnings=list(row.warnings),
            )
            for row in page_rows
        ]
        chunks = [
            IngestedChunk(
                chunk_id=row.chunk_id,
                chunk_index=row.chunk_index,
                text=row.text,
                page_start=row.page_start,
                page_end=row.page_end,
                sha256=row.sha256,
                citation=str(row.metadata_json.get("citation") or "")
                or f"{source_path.name}:{row.page_start}-{row.page_end}",
                entities=[],  # rehydration of entities would require extra joins
            )
            for row in chunk_rows
        ]
        return IngestionResult(
            document_id=document.id,
            job_id=document.id,  # no new job is created on dedup hit
            sha256=document_sha,
            stored_path=stored_path,
            pages=pages,
            chunks=chunks,
            warnings=["existing_document_reused_by_sha256"],
        )

    async def _mark_chunks_indexed(
        self,
        *,
        document_id: UUID,
        job_id: UUID,
    ) -> None:
        """Promote chunks from `pending_index` to `indexed` after Weaviate confirms.

        Run as a small, fast UPDATE inside its own session so the (potentially
        slow) Weaviate insert does not hold the session_scope open for long. If
        Weaviate failed before we got here, the chunks stay in `pending_index`
        and the caller marks the job `failed` — operators can then re-run.
        """
        from sqlalchemy import update

        async with session_scope() as session:
            await session.execute(
                update(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .where(DocumentChunk.status == "pending_index")
                .values(status="indexed")
            )
            session.add(
                JobEvent(
                    job_id=job_id,
                    event_type="chunks_promoted_to_indexed",
                    status="indexed",
                    message="All chunks promoted to indexed after Weaviate confirmation",
                )
            )

    async def _create_document_record(
        self,
        source_path: Path,
        document_sha: str,
        *,
        job_id: UUID | None = None,
    ) -> tuple[UUID, UUID]:
        async with session_scope() as session:
            document = Document(
                source_path=str(source_path),
                sha256=document_sha,
                title=source_path.name,
                status="processing",
                metadata_json={"ingestion_status": "started"},
            )
            session.add(document)
            await session.flush()

            if job_id is None:
                active_job = Job(
                    job_type="document_ingestion",
                    status="running",
                    metadata_json={
                        "document_id": str(document.id),
                        "source_path": str(source_path),
                    },
                )
                session.add(active_job)
            else:
                existing_job = await session.get(Job, job_id)
                if existing_job is None:
                    msg = f"Job not found for ingestion: {job_id}"
                    raise ValueError(msg)
                existing_job.status = "running"
                existing_job.progress = 5
                existing_job.metadata_json = {
                    **existing_job.metadata_json,
                    "document_id": str(document.id),
                    "source_path": str(source_path),
                }
                active_job = existing_job
                session.add(
                    JobEvent(
                        job_id=active_job.id,
                        event_type="ingestion_started",
                        status="running",
                        message=f"Started PDF ingestion for {source_path.name}",
                    )
                )
            await session.flush()
            return document.id, active_job.id

    def _copy_original(self, source_path: Path, document_id: UUID) -> Path:
        target_dir = self._storage_dir / "originals"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{document_id}.pdf"
        shutil.copy2(source_path, target_path)
        return target_path

    def _extract_pages(self, pdf_path: Path) -> list[PageExtraction]:
        document = fitz.open(pdf_path)
        try:
            return [self._extract_page(page, index + 1) for index, page in enumerate(document)]
        finally:
            document.close()

    def _extract_page(self, page: Any, page_number: int) -> PageExtraction:
        native_text = str(page.get_text("text")).strip()
        if len(native_text) >= self._native_text_min_chars:
            return PageExtraction(
                page_number=page_number,
                text=native_text,
                extraction_method="native_pdf",
                status="extracted",
                sha256=self._sha256_text(native_text),
                confidence_score=None,
                warnings=[],
            )

        if not self._ocr_enabled or not self._tesseract_available():
            return PageExtraction(
                page_number=page_number,
                text=native_text,
                extraction_method="failed",
                status="needs_ocr",
                sha256=self._sha256_text(native_text) if native_text else None,
                confidence_score=None,
                warnings=["page_needs_ocr_tesseract_unavailable"],
            )

        try:
            ocr_text = self._ocr_page(page).strip()
        except Exception as exc:
            return PageExtraction(
                page_number=page_number,
                text=native_text,
                extraction_method="failed",
                status="needs_ocr",
                sha256=self._sha256_text(native_text) if native_text else None,
                confidence_score=None,
                warnings=[f"tesseract_ocr_failed:{type(exc).__name__}"],
            )

        return PageExtraction(
            page_number=page_number,
            text=ocr_text,
            extraction_method="tesseract_ocr",
            status="extracted" if ocr_text else "needs_ocr",
            sha256=self._sha256_text(ocr_text) if ocr_text else None,
            confidence_score=None,
            warnings=[] if ocr_text else ["tesseract_ocr_empty"],
        )

    def _ocr_page(self, page: Any) -> str:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        return str(pytesseract.image_to_string(image, lang="spa+eng"))

    def _tesseract_available(self) -> bool:
        return shutil.which("tesseract") is not None

    def _chunk_pages(
        self,
        *,
        source_path: Path,
        doc_id: UUID,
        pages: list[PageExtraction],
    ) -> list[IngestedChunk]:
        chunks: list[IngestedChunk] = []
        chunk_index = 0
        for page in pages:
            if page.status != "extracted" or not page.text.strip():
                continue
            page_chunks = self._splitter.split_text(page.text)
            for page_chunk in page_chunks:
                chunk_id = f"{doc_id}:p{page.page_number}:c{chunk_index}"
                entities = extract_entities(page_chunk)
                chunks.append(
                    IngestedChunk(
                        chunk_id=chunk_id,
                        chunk_index=chunk_index,
                        text=page_chunk,
                        page_start=page.page_number,
                        page_end=page.page_number,
                        sha256=self._sha256_text(page_chunk),
                        citation=f"{source_path}:{page.page_number}-{page.page_number}",
                        entities=entities,
                    )
                )
                chunk_index += 1
        return chunks

    async def _persist_traceability(
        self,
        *,
        document_id: UUID,
        job_id: UUID,
        source_path: Path,
        stored_path: Path,
        pages: list[PageExtraction],
        chunks: list[IngestedChunk],
        document_sha: str,
    ) -> list[str]:
        warnings: list[str] = []
        async with session_scope() as session:
            document = await session.get(Document, document_id)
            if document is None:
                msg = f"Document disappeared during ingestion: {document_id}"
                raise RuntimeError(msg)
            job = await session.get(Job, job_id)
            if job is None:
                msg = f"Job disappeared during ingestion: {job_id}"
                raise RuntimeError(msg)

            page_ids: dict[int, UUID] = {}
            for page in pages:
                session.add(
                    JobEvent(
                        job_id=job_id,
                        event_type="page_extracted",
                        status=page.status,
                        message=f"Page {page.page_number} extracted via {page.extraction_method}",
                        metadata_json={
                            "page_number": page.page_number,
                            "warnings": page.warnings,
                        },
                    )
                )
                db_page = DocumentPage(
                    document_id=document_id,
                    page_number=page.page_number,
                    sha256=page.sha256,
                    text=page.text,
                    status=page.status,
                    extraction_method=page.extraction_method,
                    confidence_score=page.confidence_score,
                    warnings=page.warnings,
                    metadata_json={
                        "citation": f"{source_path}:{page.page_number}-{page.page_number}"
                    },
                )
                session.add(db_page)
                await session.flush()
                page_ids[page.page_number] = db_page.id

            for chunk in chunks:
                page_id = page_ids.get(chunk.page_start)
                session.add(
                    DocumentChunk(
                        document_id=document_id,
                        page_id=page_id,
                        chunk_id=chunk.chunk_id,
                        chunk_index=chunk.chunk_index,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        sha256=chunk.sha256,
                        text=chunk.text,
                        source_path=str(source_path),
                        doc_type="pdf",
                        # Pending until Weaviate confirms. `_mark_chunks_indexed` flips this
                        # only after the vector store insert succeeds, keeping Postgres and
                        # Weaviate consistent even if the second leg of the dual-write fails.
                        status="pending_index",
                        metadata_json={
                            "citation": chunk.citation,
                            "entities": [asdict(entity) for entity in chunk.entities],
                        },
                    )
                )

            session.add(
                JobEvent(
                    job_id=job_id,
                    event_type="chunks_created",
                    status="indexed",
                    message=f"Created {len(chunks)} chunks",
                    metadata_json={"chunk_count": len(chunks)},
                )
            )
            document.status = (
                "needs_ocr" if any(page.status == "needs_ocr" for page in pages) else "processing"
            )
            document.metadata_json = {
                **document.metadata_json,
                "stored_path": str(stored_path),
                "sha256": document_sha,
                "page_count": len(pages),
                "chunk_count": len(chunks),
            }
            job.status = "running"
            job.progress = 60
            job.metadata_json = {**job.metadata_json, "document_status": document.status}
            session.add(
                JobEvent(
                    job_id=job_id,
                    event_type="db_traceability_saved",
                    status="running",
                    message=f"DB records saved — {len(chunks)} chunks ready for vector indexing",
                    metadata_json={
                        "document_id": str(document_id),
                        "page_count": len(pages),
                        "chunk_count": len(chunks),
                    },
                )
            )

            neo4j_warning = self._write_entities_to_neo4j(
                doc_id=str(document_id),
                source_path=str(source_path),
                entities=[entity for chunk in chunks for entity in chunk.entities],
            )
            if neo4j_warning is not None:
                warnings.append(neo4j_warning)
                session.add(
                    JobEvent(
                        job_id=job_id,
                        event_type="neo4j_entity_warning",
                        status="warning",
                        message=neo4j_warning,
                    )
                )
        return warnings

    def _write_entities_to_neo4j(
        self,
        *,
        doc_id: str,
        source_path: str,
        entities: list[ExtractedEntity],
    ) -> str | None:
        writer = self._neo4j_writer or self._build_default_neo4j_writer()
        if writer is None:
            return None
        try:
            writer.write_entities(doc_id=doc_id, source_path=source_path, entities=entities)
        except Exception as exc:
            return f"neo4j_entity_persistence_failed:{type(exc).__name__}"
        return None

    async def _finalize_job(
        self,
        *,
        job_id: UUID,
        document_id: UUID,
        status: str,
        event_message: str,
    ) -> None:
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return
            document = await session.get(Document, document_id)
            job.status = status
            job.progress = 100 if status == "completed" else job.progress
            event_type = "ingestion_completed" if status == "completed" else "ingestion_failed"
            session.add(
                JobEvent(
                    job_id=job_id,
                    event_type=event_type,
                    status=status,
                    message=event_message,
                    metadata_json={"document_id": str(document_id)},
                )
            )
            if document is not None and status == "completed" and document.status == "processing":
                # Promote document from "processing" to "indexed" (or keep "needs_ocr")
                document.status = "indexed"
            if document is not None:
                document.metadata_json = {
                    **document.metadata_json,
                    "ingestion_status": status,
                }
                if status != "completed":
                    document.status = "failed"

    def _build_default_neo4j_writer(self) -> Neo4jEntityWriter | None:
        if settings.neo4j_password.get_secret_value() == "CHANGEME":
            return None
        return Neo4jEntityWriter(
            http_url=f"http://localhost:{settings.neo4j_http_port}",
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )

    def _insert_weaviate_chunks(
        self,
        *,
        document_id: UUID,
        job_id: UUID,
        source_path: Path,
        chunks: list[IngestedChunk],
    ) -> None:
        if not chunks:
            return
        store = self._weaviate_store or build_weaviate_store()
        records = [
            ChunkRecord(
                doc_id=str(document_id),
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                source_path=str(source_path),
                doc_type="pdf",
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                sha256=chunk.sha256,
                metadata_json={
                    "citation": chunk.citation,
                    "job_id": str(job_id),
                    "entities": [asdict(entity) for entity in chunk.entities],
                },
            )
            for chunk in chunks
        ]
        # Batched insertion: one embeddings call per `batch_size` chunks and one
        # `/v1/batch/objects` POST per window. For a 500-chunk PDF this drops 500
        # HTTP round-trips to 10 and matches the embeddings provider's batch API.
        store.batch_insert_chunks(records, batch_size=50)

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _sha256_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def ingest_pdf_cli(path: str) -> None:
    result = await DocumentIngestionPipeline().ingest_pdf(path)
    print(f"document_id={result.document_id}")
    print(f"sha256={result.sha256}")
    print(f"stored_path={result.stored_path}")
    print(f"pages={len(result.pages)} chunks={len(result.chunks)} warnings={len(result.warnings)}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Ingest a PDF into Cognitive OS.")
    parser.add_argument("pdf_path")
    args = parser.parse_args()
    asyncio.run(ingest_pdf_cli(args.pdf_path))


if __name__ == "__main__":
    main()

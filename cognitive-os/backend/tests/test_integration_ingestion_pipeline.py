from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from PIL import Image, ImageDraw
from pydantic import SecretStr
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import select

from cognitive_os.core.db import session_scope
from cognitive_os.db.models import Document, DocumentChunk, DocumentPage
from cognitive_os.ingestion.pipeline import DocumentIngestionPipeline
from cognitive_os.memory.embeddings import EmbeddingProvider
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


class RecordingStore:
    def __init__(self) -> None:
        self.chunks: list[ChunkRecord] = []

    def ensure_collection(self) -> None:
        return None

    def insert_chunk(self, chunk: ChunkRecord) -> str:
        self.chunks.append(chunk)
        return chunk.chunk_id


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


def _weaviate_store() -> WeaviateStore:
    env = _load_env()
    return WeaviateStore(
        base_url=env.get("WEAVIATE_URL", os.environ.get("WEAVIATE_URL", "http://localhost:8081")),
        api_key=SecretStr(env["WEAVIATE_API_KEY"]),
        embedding_provider=HashEmbeddingProvider(),
        collection_name=f"IntegrationDocumentChunk{uuid4().hex}",
    )


def _create_native_pdf(path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=letter)
    pdf.drawString(
        72,
        720,
        "Contrato legal pagina uno. Articulo 5. RUT 12.345.678-9. Monto $ 1.000.",
    )
    pdf.showPage()
    pdf.drawString(
        72,
        720,
        "Segunda pagina con RIT C-1234-2024 y fecha 2026-04-30 para citas.",
    )
    pdf.save()


def _create_image_pdf(path: Path, image_path: Path) -> None:
    image = Image.new("RGB", (900, 300), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 120), "Texto OCR pagina imagen 2026-04-30", fill="black")
    image.save(image_path)

    pdf = canvas.Canvas(str(path), pagesize=letter)
    pdf.drawImage(str(image_path), 72, 520, width=450, height=150)
    pdf.save()


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _docker_is_available(), reason="Docker is not available"),
]


async def _load_document_counts(
    document_id: UUID,
) -> tuple[str, list[DocumentPage], list[DocumentChunk]]:
    async with session_scope() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        pages = list(
            (
                await session.execute(
                    select(DocumentPage)
                    .where(DocumentPage.document_id == document_id)
                    .order_by(DocumentPage.page_number)
                )
            )
            .scalars()
            .all()
        )
        chunks = list(
            (
                await session.execute(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == document_id)
                    .order_by(DocumentChunk.chunk_index)
                )
            )
            .scalars()
            .all()
        )
        return document.status, pages, chunks


@pytest.mark.asyncio
async def test_ingests_native_pdf_with_page_citations(tmp_path: Path) -> None:
    pdf_path = tmp_path / "native.pdf"
    _create_native_pdf(pdf_path)
    store = _weaviate_store()

    result = await DocumentIngestionPipeline(
        storage_dir=tmp_path / "storage",
        weaviate_store=store,
    ).ingest_pdf(pdf_path)

    try:
        assert result.stored_path.exists()
        assert len(result.pages) == 2
        assert all(page.extraction_method == "native_pdf" for page in result.pages)
        assert {chunk.page_start for chunk in result.chunks} == {1, 2}
        assert any(entity.kind == "rut" for chunk in result.chunks for entity in chunk.entities)

        status, pages, chunks = await _load_document_counts(result.document_id)
        assert status == "indexed"
        assert [page.page_number for page in pages] == [1, 2]
        assert pages[0].metadata_json["citation"].endswith(":1-1")
        assert chunks
        assert chunks[0].metadata_json["citation"].endswith(":1-1")

        search_results = store.hybrid_search(
            "contrato articulo rut monto",
            filters={"doc_id": str(result.document_id)},
            limit=3,
        )
        assert search_results
        assert search_results[0].citation.endswith(":1-1")
    finally:
        store.delete_by_doc_id(str(result.document_id))


@pytest.mark.asyncio
@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed")
async def test_ingests_image_pdf_with_tesseract_when_available(tmp_path: Path) -> None:
    pdf_path = tmp_path / "image.pdf"
    _create_image_pdf(pdf_path, tmp_path / "image.png")
    store = RecordingStore()

    result = await DocumentIngestionPipeline(
        storage_dir=tmp_path / "storage",
        weaviate_store=store,  # type: ignore[arg-type]
        ocr_enabled=True,
    ).ingest_pdf(pdf_path)

    assert result.pages[0].extraction_method == "tesseract_ocr"
    assert result.pages[0].status == "extracted"
    assert store.chunks


@pytest.mark.asyncio
async def test_image_pdf_without_ocr_marks_needs_ocr(tmp_path: Path) -> None:
    pdf_path = tmp_path / "image-needs-ocr.pdf"
    _create_image_pdf(pdf_path, tmp_path / "image-needs-ocr.png")
    store = RecordingStore()

    result = await DocumentIngestionPipeline(
        storage_dir=tmp_path / "storage",
        weaviate_store=store,  # type: ignore[arg-type]
        ocr_enabled=False,
    ).ingest_pdf(pdf_path)

    assert result.pages[0].status == "needs_ocr"
    assert result.pages[0].extraction_method == "failed"
    assert result.warnings == ["page_needs_ocr_tesseract_unavailable"]
    assert store.chunks == []

    status, pages, chunks = await _load_document_counts(result.document_id)
    assert status == "needs_ocr"
    assert pages[0].status == "needs_ocr"
    assert chunks == []

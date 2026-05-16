from __future__ import annotations

from pathlib import Path

import pytest

from cognitive_os.core.config import Settings
from cognitive_os.core.path_policy import IngestPathPolicyError, resolve_ingest_document_path


def test_ingest_path_allowed_under_local_storage(tmp_path: Path) -> None:
    cfg = Settings.model_construct(local_storage_dir=str(tmp_path))
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 minimal")
    assert resolve_ingest_document_path(str(pdf), cfg) == pdf.resolve()


def test_ingest_path_allowed_under_extra_prefix(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    cfg = Settings.model_construct(
        local_storage_dir=str(tmp_path / "empty"),
        document_ingest_allowed_prefixes=[str(vault)],
    )
    pdf = vault / "external.pdf"
    pdf.write_bytes(b"x")
    assert resolve_ingest_document_path(str(pdf), cfg) == pdf.resolve()


def test_ingest_path_rejects_outside_roots(tmp_path: Path) -> None:
    cfg = Settings.model_construct(local_storage_dir=str(tmp_path))
    with pytest.raises(IngestPathPolicyError):
        resolve_ingest_document_path("/etc/passwd", cfg)

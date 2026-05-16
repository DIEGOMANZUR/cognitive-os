"""Regression for atomic document generation.

`DocumentActionService.execute` writes to a `.tmp` sibling before renaming
onto the final path. Two guarantees we verify:

1. Happy path leaves only the final document on disk (no `.tmp` lingering).
2. A writer crash leaves the original final path unchanged and removes the
   staging file — the operator never sees a half-written report.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cognitive_os.actions import documents as documents_module
from cognitive_os.actions.documents import DocumentActionService
from cognitive_os.actions.schemas import DocumentGenerateRequest, DocumentSection
from cognitive_os.core.config import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        enable_document_generation=True,
        document_output_root=tmp_path / "out",
    )


def test_successful_write_leaves_no_tmp_files(tmp_path: Path) -> None:
    service = DocumentActionService(_settings(tmp_path))
    request = DocumentGenerateRequest(
        format="docx",
        output_filename="reports/a.docx",
        title="A",
        docx_sections=[DocumentSection(heading="x", paragraphs=["hello"])],
    )

    result = service.execute(request)

    assert result.status == "completed"
    out_root = tmp_path / "out"
    final_path = out_root / "reports" / "a.docx"
    assert final_path.exists()
    # No leftover staging files.
    tmp_files = list(out_root.rglob(".*.tmp"))
    assert tmp_files == []


def test_writer_failure_does_not_corrupt_existing_final(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = DocumentActionService(_settings(tmp_path))
    request = DocumentGenerateRequest(
        format="docx",
        output_filename="reports/b.docx",
        title="B",
        docx_sections=[DocumentSection(heading="x", paragraphs=["pre-existing"])],
    )

    # First, generate a known-good doc.
    pre = service.execute(request)
    assert pre.status == "completed"
    final_path = tmp_path / "out" / "reports" / "b.docx"
    original_bytes = final_path.read_bytes()

    # Now poison the writer so it raises mid-write.
    def _exploding_writer(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated writer crash")

    monkeypatch.setattr(documents_module, "_write_docx", _exploding_writer)

    result = service.execute(request)

    assert result.status == "failed"
    # Final document is unchanged (atomic rename never happened).
    assert final_path.read_bytes() == original_bytes
    # No `.tmp` lingering after the crash.
    tmp_files = list((tmp_path / "out").rglob(".*.tmp"))
    assert tmp_files == []

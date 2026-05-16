from __future__ import annotations

from pathlib import Path

from cognitive_os.core.config import Settings


class IngestPathPolicyError(ValueError):
    """Raised when a document ingest path is outside configured roots."""


def resolve_ingest_document_path(raw: str, app_settings: Settings) -> Path:
    """Resolve and confine ingest paths to LOCAL_STORAGE_DIR plus optional extras.

    Prevents arbitrary server-readable paths (e.g. /etc/passwd) from being queued
    via `/documents/ingest` by authenticated users.
    """
    path = Path(raw).expanduser().resolve()
    roots = _ingest_roots(app_settings)
    for root in roots:
        if path == root or path.is_relative_to(root):
            return path
    msg = "document_path must be under LOCAL_STORAGE_DIR or DOCUMENT_INGEST_ALLOWED_PREFIXES"
    raise IngestPathPolicyError(msg)


def _ingest_roots(app_settings: Settings) -> list[Path]:
    roots: list[Path] = [Path(app_settings.local_storage_dir).expanduser().resolve()]
    for raw in app_settings.document_ingest_allowed_prefixes:
        s = raw.strip()
        if s:
            roots.append(Path(s).expanduser().resolve())
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique

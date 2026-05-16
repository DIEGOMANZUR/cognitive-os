"""Smoke tests for the settings registry dump script (operator checklist)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND_ROOT / "scripts" / "dump_settings_registry.py"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_dump_settings_registry_markdown_contains_core_aliases() -> None:
    proc = _run_script()
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "| `database_url` | `DATABASE_URL` |" in out
    assert "| `jwt_secret` | `JWT_SECRET` |" in out
    assert out.startswith("| `Settings` attribute |")


def test_dump_settings_registry_secrets_lists_production_fields() -> None:
    proc = _run_script("--secrets")
    assert proc.returncode == 0, proc.stderr
    assert "| `jwt_secret` | yes | `JWT_SECRET` |" in proc.stdout
    assert "| `database_url` | yes | `DATABASE_URL` |" in proc.stdout


def test_dump_settings_registry_tsv_row_count_matches_settings_fields() -> None:
    from cognitive_os.core.config import Settings

    proc = _run_script("--tsv")
    assert proc.returncode == 0, proc.stderr
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    model_aliases = sum(
        1
        for name, finfo in Settings.model_fields.items()
        if not name.startswith("_") and finfo.alias
    )
    assert len(lines) == model_aliases


def test_settings_registry_table_markdown_matches_generated_body() -> None:
    """Fails if docs/SETTINGS_REGISTRY_TABLE.md was not regenerated after editing Settings."""
    table_path = BACKEND_ROOT.parent / "docs" / "SETTINGS_REGISTRY_TABLE.md"
    on_disk = table_path.read_text(encoding="utf-8")
    lines = on_disk.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("| `Settings` attribute |"))
    body_on_disk = "\n".join(lines[start:]) + "\n"
    proc = _run_script()
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == body_on_disk

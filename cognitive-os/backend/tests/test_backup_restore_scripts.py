from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1].parent


def test_restore_scripts_are_shell_syntax_valid() -> None:
    scripts = [
        ROOT / "scripts" / "restore_postgres.sh",
        ROOT / "scripts" / "restore_storage.sh",
        ROOT / "scripts" / "restore_neo4j.sh",
        ROOT / "scripts" / "backup_all.sh",
        ROOT / "scripts" / "backup_postgres.sh",
        ROOT / "scripts" / "backup_storage.sh",
        ROOT / "scripts" / "backup_neo4j.sh",
    ]
    for script in scripts:
        subprocess.run(["bash", "-n", str(script)], check=True)


def test_restore_scripts_require_explicit_confirmation() -> None:
    for name in ["restore_postgres.sh", "restore_storage.sh", "restore_neo4j.sh"]:
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "CONFIRM_RESTORE" in text
        assert "YES" in text


def test_restore_scripts_verify_sha256_when_available() -> None:
    for name in ["restore_postgres.sh", "restore_storage.sh", "restore_neo4j.sh"]:
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "sha256sum -c" in text


def test_storage_restore_keeps_safety_copy_before_overwrite() -> None:
    text = (ROOT / "scripts" / "restore_storage.sh").read_text(encoding="utf-8")
    assert ".pre_restore_" in text
    assert 'mv "${STORAGE_ROOT}" "${SAFETY_COPY}"' in text

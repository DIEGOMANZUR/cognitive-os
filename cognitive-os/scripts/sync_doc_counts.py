#!/usr/bin/env python3
"""Mantiene los conteos canónicos del proyecto sincronizados con el código.

AUDIT-2026-G: `README.md` y `USER_GUIDE.md` arrastraban conteos de snapshots
viejas (endpoints, tareas Celery, migraciones). Esos números deben derivarse
del código, no escribirse a mano.

Este script calcula los conteos estructurales (todos por inspección de
archivos, sin levantar servicios ni DB) y reescribe el bloque marcado en
`docs/CURRENT_STATE.md`, el documento canónico de estado:

    <!-- AUTO:counts:start -->
    ...tabla generada...
    <!-- AUTO:counts:end -->

Uso:
    python scripts/sync_doc_counts.py            # reescribe el bloque
    python scripts/sync_doc_counts.py --check    # falla si está desincronizado
    python scripts/sync_doc_counts.py --print    # solo imprime los conteos
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_API_DIR = _ROOT / "backend" / "src" / "cognitive_os" / "api"
_APP_PY = _API_DIR / "app.py"
_TASKS_PY = _ROOT / "backend" / "src" / "cognitive_os" / "workers" / "tasks.py"
_MIGRATIONS_DIR = _ROOT / "backend" / "alembic" / "versions"
_VIEWS_DIR = _ROOT / "frontend" / "app" / "views"
_CURRENT_STATE = _ROOT / "docs" / "CURRENT_STATE.md"

_START = "<!-- AUTO:counts:start -->"
_END = "<!-- AUTO:counts:end -->"

_ENDPOINT_RE = re.compile(
    r"^@(app|router)\.(get|post|put|patch|delete|websocket)\(",
    re.MULTILINE,
)
_TASK_RE = re.compile(r'name="cognitive_os\.')
_REVISION_RE = re.compile(r'^revision(?:\s*:\s*str)?\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_DOWN_RE = re.compile(
    r'^down_revision(?:\s*:[^=]+)?\s*=\s*["\']([^"\']+)["\']', re.MULTILINE
)


def _count_endpoints() -> int:
    total = 0
    for path in sorted(_API_DIR.glob("*.py")):
        total += len(_ENDPOINT_RE.findall(path.read_text(encoding="utf-8")))
    return total


def _count_celery_tasks() -> int:
    return len(_TASK_RE.findall(_TASKS_PY.read_text(encoding="utf-8")))


def _migration_files() -> list[Path]:
    return sorted(p for p in _MIGRATIONS_DIR.glob("*.py") if p.name != "__init__.py")


def _count_migrations() -> int:
    return len(_migration_files())


def _alembic_head() -> str:
    """The revision that no other migration declares as its down_revision."""
    revisions: set[str] = set()
    down_revisions: set[str] = set()
    for path in _migration_files():
        text = path.read_text(encoding="utf-8")
        rev = _REVISION_RE.search(text)
        if rev:
            revisions.add(rev.group(1))
        down_revisions.update(_DOWN_RE.findall(text))
    heads = revisions - down_revisions
    if len(heads) == 1:
        return next(iter(heads))
    if not heads:
        return "desconocido (sin head)"
    return "MÚLTIPLES HEADS: " + ", ".join(sorted(heads))


def _count_views() -> int:
    return len(list(_VIEWS_DIR.glob("*.tsx")))


def collect_counts() -> dict[str, str]:
    return {
        "Endpoints REST (`@app.*`/`@router.*` en `api/`)": str(_count_endpoints()),
        "Tareas Celery (`workers/tasks.py`)": str(_count_celery_tasks()),
        "Migraciones Alembic (`alembic/versions/`)": str(_count_migrations()),
        "Head Alembic": _alembic_head(),
        "Vistas frontend (`frontend/app/views/*.tsx`)": str(_count_views()),
    }


def render_block(counts: dict[str, str]) -> str:
    lines = [
        _START,
        "<!-- Generado por scripts/sync_doc_counts.py — no editar a mano. -->",
        "",
        "| Conteo canónico | Valor |",
        "|---|---|",
    ]
    lines.extend(f"| {label} | {value} |" for label, value in counts.items())
    lines.append(_END)
    return "\n".join(lines)


def _replace_block(text: str, block: str) -> str | None:
    """Return text with the AUTO block replaced, or None if no change/markers."""
    if _START not in text or _END not in text:
        return None
    pattern = re.compile(re.escape(_START) + r".*?" + re.escape(_END), re.DOTALL)
    new_text = pattern.sub(lambda _m: block, text, count=1)
    return new_text if new_text != text else text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if out of sync")
    parser.add_argument("--print", action="store_true", help="only print counts")
    args = parser.parse_args()

    counts = collect_counts()

    if args.print:
        for label, value in counts.items():
            print(f"{label}: {value}")
        return 0

    block = render_block(counts)
    if not _CURRENT_STATE.is_file():
        print(f"ERROR: no existe {_CURRENT_STATE}", file=sys.stderr)
        return 1
    text = _CURRENT_STATE.read_text(encoding="utf-8")

    if _START not in text or _END not in text:
        print(
            f"ERROR: faltan los marcadores {_START} / {_END} en "
            f"{_CURRENT_STATE.relative_to(_ROOT)}.",
            file=sys.stderr,
        )
        return 1

    new_text = _replace_block(text, block)
    assert new_text is not None  # markers checked above  # noqa: S101

    if args.check:
        if new_text != text:
            print(
                "FAIL: los conteos en docs/CURRENT_STATE.md están "
                "desincronizados. Corré: python scripts/sync_doc_counts.py",
                file=sys.stderr,
            )
            return 1
        print("OK: conteos canónicos sincronizados.")
        return 0

    if new_text == text:
        print("OK: conteos ya estaban sincronizados.")
        return 0
    _CURRENT_STATE.write_text(new_text, encoding="utf-8")
    print(f"Actualizado el bloque de conteos en {_CURRENT_STATE.relative_to(_ROOT)}:")
    for label, value in counts.items():
        print(f"  {label}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

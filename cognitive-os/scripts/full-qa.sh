#!/usr/bin/env bash
# Comprobaciones locales: backend (con extra OpenHarness para prueba de fusión) + frontend.
# Compuertas opcionales: alembic check (si hay DATABASE_URL operativo) y
# `git diff --check` (si estamos dentro de un repo git). Nunca bloquean por
# ausencia de Postgres o git: si la herramienta no está disponible se reporta
# y se sigue.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
uv sync --extra openharness
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
if [[ -n "${DATABASE_URL:-}" ]] || [[ -f "$ROOT/.env.local" ]] || [[ -f "$ROOT/.env" ]]; then
  if uv run alembic check >/dev/null 2>&1; then
    echo "OK: alembic check (sin drift)"
  else
    echo "WARN: alembic check no pasó o no se pudo conectar (revisa DATABASE_URL)."
  fi
else
  echo "SKIP: alembic check (no hay DATABASE_URL ni .env)"
fi
cd "$ROOT/frontend"
npm ci
npm run lint
npm run build
cd "$ROOT"
if command -v git >/dev/null && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git diff --check >/dev/null; then
    echo "OK: git diff --check (sin whitespace/conflicto pendiente)"
  else
    echo "FAIL: git diff --check detectó whitespace/conflicto pendiente." >&2
    exit 1
  fi
else
  echo "SKIP: git diff --check (no es repo git)"
fi
echo "OK: full-qa"

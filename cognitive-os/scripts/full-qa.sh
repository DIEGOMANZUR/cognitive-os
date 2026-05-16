#!/usr/bin/env bash
# Comprobaciones locales: backend (con extra OpenHarness para prueba de fusión) + frontend.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
uv sync --extra openharness
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
cd "$ROOT/frontend"
npm ci
npm run lint
npm run build
echo "OK: full-qa"

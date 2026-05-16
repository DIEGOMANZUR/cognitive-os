#!/usr/bin/env bash
# Verificación local antes de cargar credenciales en producción.
# Uso: desde backend/ → bash scripts/verify_operator_ready.sh
set -euo pipefail
cd "$(dirname "$0")/.."
uv run ruff check src tests
uv run mypy src
uv run pytest -q --tb=no
echo "=== settings registry dump ==="
uv run python scripts/dump_settings_registry.py --tsv >/dev/null
echo "OK: dump_settings_registry"
echo "=== alembic (requiere Postgres y DATABASE_URL) ==="
uv run alembic current
echo "Head esperado:"
uv run alembic heads
echo "=== frontend ==="
pushd ../frontend >/dev/null
npm run lint
npm run build
popd >/dev/null
echo "OK: suite estática + migración consultable. Ejecuta: uv run alembic upgrade head"

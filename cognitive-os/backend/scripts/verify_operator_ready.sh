#!/usr/bin/env bash
# Verificación local antes de cargar credenciales en producción.
# Uso: bash backend/scripts/verify_operator_ready.sh
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --extra openharness
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q --tb=no
echo "=== settings registry dump ==="
uv run python scripts/dump_settings_registry.py --tsv >/dev/null
echo "OK: dump_settings_registry"
echo "=== alembic (requiere Postgres y DATABASE_URL) ==="
current_revision="$(uv run alembic current 2>/dev/null | tail -n 1 | awk '{print $1}')"
head_revision="$(uv run alembic heads 2>/dev/null | tail -n 1 | awk '{print $1}')"
echo "Current: ${current_revision:-unknown}"
echo "Head: ${head_revision:-unknown}"
if [[ -z "${current_revision}" || -z "${head_revision}" || "${current_revision}" != "${head_revision}" ]]; then
  echo "Alembic no está en head. Ejecuta desde backend/: uv run alembic upgrade head" >&2
  exit 1
fi
uv run alembic check
echo "=== frontend ==="
pushd ../frontend >/dev/null
npm ci
npm run lint
npm run build
popd >/dev/null
echo "OK: suite estática + migraciones en head sin drift"

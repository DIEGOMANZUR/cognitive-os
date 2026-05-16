#!/usr/bin/env bash
# Repite el backend test suite N veces para detectar flakiness (por defecto 3).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
RUNS="${1:-3}"
uv sync --extra openharness
for i in $(seq 1 "$RUNS"); do
  echo "=== pytest run $i / $RUNS ==="
  uv run pytest -q --tb=no
done
echo "OK: stress-qa ($RUNS runs)"

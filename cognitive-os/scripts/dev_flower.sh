#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

bash scripts/init_env.sh >/dev/null
cd backend
if ! uv run python -c "import flower" >/dev/null 2>&1; then
  echo "Flower is optional. Install it with: cd backend && uv add --dev flower" >&2
  exit 0
fi
uv run celery -A cognitive_os.workers.celery_app:celery_app flower

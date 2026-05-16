#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

bash scripts/init_env.sh >/dev/null
cd backend
uv run celery -A cognitive_os.workers.celery_app:celery_app beat --loglevel=INFO

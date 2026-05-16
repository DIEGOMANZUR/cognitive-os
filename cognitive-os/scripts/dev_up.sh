#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

bash scripts/init_env.sh
docker compose --env-file .env -f infra/docker-compose.yml up -d
bash infra/wait_for_services.sh

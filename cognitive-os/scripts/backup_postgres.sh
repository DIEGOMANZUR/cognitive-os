#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f .env ]]; then
  echo "No existe .env. Ejecuta scripts/init_env.sh primero." >&2
  exit 1
fi

set -a
source .env
set +a

BACKUP_ROOT="${BACKUP_DIR:-./backups}/postgres"
mkdir -p "${BACKUP_ROOT}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BACKUP_ROOT}/postgres_${POSTGRES_DB}_${STAMP}.dump"

docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" cognitive_os_postgres \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --format=custom > "${OUT}"

sha256sum "${OUT}" > "${OUT}.sha256"
echo "Backup Postgres creado: ${OUT}"

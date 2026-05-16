#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
  echo "Restore abortado. Ejecuta con CONFIRM_RESTORE=YES para continuar." >&2
  exit 2
fi

if [[ ! -f .env ]]; then
  echo "No existe .env. Ejecuta scripts/init_env.sh primero." >&2
  exit 1
fi

DUMP_PATH="${1:-}"
if [[ -z "${DUMP_PATH}" || ! -f "${DUMP_PATH}" ]]; then
  echo "Uso: CONFIRM_RESTORE=YES bash scripts/restore_postgres.sh backups/postgres/ARCHIVO.dump" >&2
  exit 1
fi

if [[ -f "${DUMP_PATH}.sha256" ]]; then
  sha256sum -c "${DUMP_PATH}.sha256"
else
  echo "Advertencia: no existe ${DUMP_PATH}.sha256; restore continua sin verificacion." >&2
fi

set -a
source .env
set +a

echo "Restaurando Postgres en ${POSTGRES_DB} desde ${DUMP_PATH}..."
docker exec -i -e PGPASSWORD="${POSTGRES_PASSWORD}" cognitive_os_postgres \
  pg_restore -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --clean --if-exists < "${DUMP_PATH}"

echo "Restore Postgres completado."

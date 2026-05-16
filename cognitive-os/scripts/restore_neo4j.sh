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
  echo "Uso: CONFIRM_RESTORE=YES bash scripts/restore_neo4j.sh backups/neo4j/.../neo4j.dump" >&2
  exit 1
fi

if [[ "$(basename "${DUMP_PATH}")" != "neo4j.dump" ]]; then
  echo "El archivo debe llamarse neo4j.dump para neo4j-admin database load." >&2
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

DATA_VOLUME="$(
  docker inspect cognitive_os_neo4j \
    --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}'
)"

if [[ -z "${DATA_VOLUME}" ]]; then
  echo "No se pudo detectar el volumen /data de cognitive_os_neo4j." >&2
  exit 1
fi

DUMP_DIR="$(cd "$(dirname "${DUMP_PATH}")" && pwd)"

echo "Deteniendo Neo4j para restore consistente..."
docker compose --env-file .env -f infra/docker-compose.yml stop neo4j >/dev/null
restart_neo4j() {
  docker compose --env-file .env -f infra/docker-compose.yml start neo4j >/dev/null
}
trap restart_neo4j EXIT

docker run --rm \
  -v "${DATA_VOLUME}:/data" \
  -v "${DUMP_DIR}:/backups" \
  neo4j:5-community \
  neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true

echo "Restore Neo4j completado desde ${DUMP_PATH}."

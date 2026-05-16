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

BACKUP_ROOT="${BACKUP_DIR:-./backups}/neo4j"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${BACKUP_ROOT}/neo4j_${STAMP}"
mkdir -p "${OUT_DIR}"
chmod 0777 "${OUT_DIR}"
DATA_VOLUME="$(
  docker inspect cognitive_os_neo4j \
    --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}'
)"

if [[ -z "${DATA_VOLUME}" ]]; then
  echo "No se pudo detectar el volumen /data de cognitive_os_neo4j." >&2
  exit 1
fi

echo "Deteniendo Neo4j para dump consistente..."
docker compose --env-file .env -f infra/docker-compose.yml stop neo4j >/dev/null
restart_neo4j() {
  docker compose --env-file .env -f infra/docker-compose.yml start neo4j >/dev/null
}
trap restart_neo4j EXIT

docker run --rm \
  -v "${DATA_VOLUME}:/data" \
  -v "$(pwd)/${OUT_DIR}:/backups" \
  neo4j:5-community \
  neo4j-admin database dump neo4j --to-path=/backups --overwrite-destination=true

sha256sum "${OUT_DIR}/neo4j.dump" > "${OUT_DIR}/neo4j.dump.sha256"
echo "Backup Neo4j creado: ${OUT_DIR}/neo4j.dump"

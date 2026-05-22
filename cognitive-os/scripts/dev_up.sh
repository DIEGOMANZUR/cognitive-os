#!/usr/bin/env bash
# Levanta la infraestructura local (Postgres/Redis/Weaviate/Neo4j) vía Docker
# Compose.
#
# AUDIT-2026-H: `docker compose` interpola `${VAR}` con string vacío cuando la
# variable no está definida y NO falla. Una `.env` con `POSTGRES_PASSWORD=`
# vacío arrancaría Postgres sin contraseña en silencio. Por eso este wrapper
# valida — después de `init_env.sh` — que toda variable que el compose consume
# SIN default esté presente y no sea un placeholder, y aborta con un mensaje
# claro si falta alguna. Comando único correcto documentado en `RUNBOOK.md`.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
ENV_FILE="${ROOT_DIR}/.env"

bash scripts/init_env.sh

# Variables que `infra/docker-compose.yml` interpola SIN `:-default`. Si una de
# estas queda vacía, el contenedor arranca mal configurado y sin avisar.
REQUIRED_COMPOSE_VARS=(
  POSTGRES_USER
  POSTGRES_PASSWORD
  POSTGRES_DB
  WEAVIATE_API_KEY
  NEO4J_USER
  NEO4J_PASSWORD
)

missing=()
for var in "${REQUIRED_COMPOSE_VARS[@]}"; do
  value="$(grep -E "^${var}=" "${ENV_FILE}" | tail -1 | cut -d= -f2- || true)"
  if [[ -z "${value}" || "${value}" == "CHANGEME" ]]; then
    missing+=("${var}")
  fi
done

if (( ${#missing[@]} > 0 )); then
  echo "ERROR: variables requeridas vacías o con placeholder CHANGEME en .env:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  echo "" >&2
  echo "docker compose las interpolaría como string vacío sin fallar." >&2
  echo "Corré 'bash scripts/init_env.sh' o completá esos valores en .env" >&2
  echo "antes de levantar la infraestructura." >&2
  exit 1
fi

docker compose --env-file .env -f infra/docker-compose.yml up -d
bash infra/wait_for_services.sh

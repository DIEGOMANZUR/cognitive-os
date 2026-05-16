#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"
SERVICES=(postgres redis weaviate neo4j)
STARTED_AT="$(date +%s)"

service_health() {
  local service_name="$1"
  local container_id
  container_id="$(docker compose --env-file .env -f infra/docker-compose.yml ps -q "${service_name}")"
  if [[ -z "${container_id}" ]]; then
    echo "missing"
    return
  fi
  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
    "${container_id}"
}

while true; do
  all_healthy=true
  for service in "${SERVICES[@]}"; do
    status="$(service_health "${service}")"
    if [[ "${status}" != "healthy" ]]; then
      all_healthy=false
      echo "Waiting for ${service}: ${status}"
    fi
  done

  if [[ "${all_healthy}" == "true" ]]; then
    echo "All services are healthy"
    exit 0
  fi

  now="$(date +%s)"
  elapsed=$((now - STARTED_AT))
  if (( elapsed >= TIMEOUT_SECONDS )); then
    echo "Timed out waiting for services after ${TIMEOUT_SECONDS}s" >&2
    for service in "${SERVICES[@]}"; do
      echo "===== ${service} logs =====" >&2
      docker compose --env-file .env -f infra/docker-compose.yml logs --tail=120 "${service}" >&2 || true
    done
    exit 1
  fi

  sleep 5
done

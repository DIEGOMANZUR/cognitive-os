#!/usr/bin/env bash
# Wrapper para arrancar el MCP `mcp-weaviate` contra el contenedor local
# cognitive_os_weaviate (puerto HTTP 8081, gRPC 50052).
#
# Credenciales via .env.local / entorno. No guardar API keys aqui.
#
# Modo: solo "local" (Docker / self-hosted).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Re-aplicar parches a mcp-weaviate 0.2.0 si el cache de uv los descartó.
# (bug upstream: el cliente local ignora --api-key; lo arreglamos in-place.)
"${SCRIPT_DIR}/patch-mcp-weaviate.sh" >/dev/null 2>&1 || true

# Cargar .env.local si existe (compat para usos fuera de opencode).
if [[ -f "${REPO_ROOT}/.env.local" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "${REPO_ROOT}/.env.local"
  set +a
fi

# Defaults no secretos (contenedor cognitive_os_weaviate del compose).
WEAVIATE_URL="${WEAVIATE_URL:-http://localhost:8081}"
WEAVIATE_API_KEY="${WEAVIATE_API_KEY:-}"
WEAVIATE_GRPC_PORT="${WEAVIATE_GRPC_PORT:-50052}"

# Parsear host y puerto desde WEAVIATE_URL.
url_no_scheme="${WEAVIATE_URL#*://}"
hostport="${url_no_scheme%%/*}"
host="${hostport%%:*}"
port="${hostport##*:}"
if [[ "${host}" == "${port}" ]]; then
  port=8080
fi

args=(
  mcp-weaviate
  --connection-type local
  --host "${host}"
  --port "${port}"
  --grpc-port "${WEAVIATE_GRPC_PORT}"
)

if [[ -n "${WEAVIATE_API_KEY}" ]]; then
  args+=(--api-key "${WEAVIATE_API_KEY}")
fi

exec uvx "${args[@]}"

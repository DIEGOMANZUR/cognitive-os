#!/usr/bin/env bash
# Prepara TestSprite MCP para auditorías (Prompt 1+).
# Corrige el fallo observado: generateCodeAndExecute crudo con testIds=[] y
# serverMode mezclado hace que el túnel TestSprite interprete rutas OpenAPI
# (/health, /jobs, …) como hostnames en :80.
#
# Uso:
#   bash scripts/testsprite_mcp_prepare.sh
#   bash scripts/full-testsprite.sh          # preferido para ejecución completa
#   # o MCP: testsprite_bootstrap → plan → generate_code_and_execute con testIds explícitos
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# Optional: load TESTSPRITE_API_KEY safely (never source full .env — cron lines break bash).
SKILL_ENV="${ROOT_DIR}/.cursor/skills/testsprite-cognitive-os/scripts/load_testsprite_env.sh"
if [[ -f "${SKILL_ENV}" ]]; then
  # shellcheck disable=SC1091
  source "${SKILL_ENV}" "${ROOT_DIR}"
fi

FRONTEND_URL="${TESTSPRITE_LOCAL_ENDPOINT:-http://localhost:3001/}"
BACKEND_HEALTH="${TESTSPRITE_BACKEND_HEALTH_URL:-http://127.0.0.1:8000/health}"
CONFIG="${ROOT_DIR}/testsprite_tests/tmp/config.json"
PLAN="${ROOT_DIR}/qa/testsprite/frontend_commercial_plan.json"

log() { printf '[testsprite_mcp_prepare] %s\n' "$*"; }

# 1. Resolver API key sin imprimirla
if [[ -z "${API_KEY:-}" && -z "${TESTSPRITE_API_KEY:-}" ]]; then
  if [[ -f "${CONFIG}" ]]; then
    API_KEY="$(python3 - <<'PY'
import json, sys
from pathlib import Path
p = Path("testsprite_tests/tmp/config.json")
data = json.loads(p.read_text())
key = data.get("executionArgs", {}).get("envs", {}).get("API_KEY", "")
if key and key not in ("<redacted>", ""):
    print(key)
PY
)"
    export API_KEY
  fi
fi
export API_KEY="${API_KEY:-${TESTSPRITE_API_KEY:-}}"
if [[ -z "${API_KEY}" || "${API_KEY}" == "<redacted>" ]]; then
  echo "ERROR: export API_KEY or TESTSPRITE_API_KEY (cuenta TestSprite)." >&2
  exit 2
fi

# 2. Matar runners huérfanos de generateCodeAndExecute (>15 min o sin lock útil)
if pgrep -u "$USER" -f "generateCodeAndExecute" >/dev/null 2>&1; then
  log "terminando runner TestSprite huérfano"
  pkill -u "$USER" -f "generateCodeAndExecute" 2>/dev/null || true
  sleep 2
fi

# 3. Limpiar locks y artefactos stale de corrida abortada
rm -f "${ROOT_DIR}/testsprite_tests/tmp/execution.lock"
rm -f "${ROOT_DIR}/testsprite_tests/tmp/mcp.log"

# 4. Preflight stack local
curl -fsS "${BACKEND_HEALTH}" >/dev/null || {
  echo "ERROR: backend no responde en ${BACKEND_HEALTH}" >&2
  exit 1
}
curl -fsS "${FRONTEND_URL%/}/" >/dev/null || {
  echo "ERROR: frontend no responde en ${FRONTEND_URL}" >&2
  exit 1
}
log "stack OK frontend+backend"

# 5. Copiar plan canónico al runtime path que usa el runner
if [[ ! -f "${PLAN}" ]]; then
  echo "ERROR: falta plan canónico ${PLAN}" >&2
  exit 1
fi
mkdir -p "${ROOT_DIR}/testsprite_tests"
cp "${PLAN}" "${ROOT_DIR}/testsprite_tests/testsprite_frontend_test_plan.json"
TC_COUNT="$(python3 -c "import json; print(len(json.load(open('${PLAN}'))))")"
log "plan canónico ${TC_COUNT} casos → testsprite_tests/testsprite_frontend_test_plan.json"

# 6. Escribir config coherente (serverMode production en ambos niveles; sin URLs crudas en instrucciones)
mkdir -p "${ROOT_DIR}/testsprite_tests/tmp"
python3 - <<PY
import json
from pathlib import Path

root = Path(${ROOT_DIR@Q})
config_path = root / "testsprite_tests/tmp/config.json"
data = {
    "status": "init",
    "scope": "codebase",
    "type": "frontend",
    "localEndpoint": ${FRONTEND_URL@Q},
    "serverMode": "production",
    "executionArgs": {
        "projectName": root.name,
        "projectPath": str(root),
        "testIds": [],
        "serverMode": "production",
        "additionalInstruction": (
            "Cognitive OS audit. Profile dedicated_local/full on a dedicated local PC. "
            "Frontend is the local cockpit on port 3001; API auth via POST /auth/local-token. "
            "ZERO FRICTION: do not add SaaS confirmation friction. "
            "DO NOT send mail, create drafts, perform real DNS writes, or external provider writes. "
            "Mail digest read-only or honest disabled state is PASS. "
            "Empty tables with clear empty states are PASS. Fail on crash, white screen, hidden errors, or unsafe writes."
        ),
        "envs": {"API_KEY": ${API_KEY@Q}},
    },
}
config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\\n")
print(f"config written: {config_path}")
PY

log "listo. Ejecutar:"
log "  bash scripts/full-testsprite.sh"
log "  # o un batch acotado:"
log "  TESTSPRITE_TEST_IDS=TC001 bash scripts/full-testsprite.sh"

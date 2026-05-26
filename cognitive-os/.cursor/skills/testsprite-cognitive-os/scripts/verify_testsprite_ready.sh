#!/usr/bin/env bash
# Preflight TestSprite — fail-closed antes de cualquier corrida.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "${ROOT_DIR}"

SKILL_DIR="${ROOT_DIR}/.cursor/skills/testsprite-cognitive-os"
MODE="${TESTSPRITE_VERIFY_MODE:-runtime}"  # stack | runtime | full
fail=0
ok() { printf 'OK: %s\n' "$*"; }
bad() { printf 'FAIL: %s\n' "$*" >&2; fail=1; }

# shellcheck disable=SC1091
source "${SKILL_DIR}/scripts/load_testsprite_env.sh" "${ROOT_DIR}"

# --- Stack ---
curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1 && ok "backend /health" || bad "backend :8000/health down"
curl -fsS "http://127.0.0.1:3001/" >/dev/null 2>&1 && ok "frontend :3001" || bad "frontend :3001 down"

# --- Plan ---
if [[ -f qa/testsprite/frontend_commercial_plan.json ]]; then
  n="$(python3 -c "import json; print(len(json.load(open('qa/testsprite/frontend_commercial_plan.json'))))")"
  [[ "${n}" -eq 28 ]] && ok "plan canónico 28 casos" || bad "plan tiene ${n} casos, esperado 28"
else
  bad "falta qa/testsprite/frontend_commercial_plan.json"
fi

# --- Scripts / skill ---
for s in \
  scripts/testsprite_audit.sh \
  scripts/testsprite_mcp_prepare.sh \
  scripts/full-testsprite.sh \
  .cursor/skills/testsprite-cognitive-os/scripts/assert_testsprite_run.py \
  .cursor/skills/testsprite-cognitive-os/scripts/validate_testsprite_config.py \
  .cursor/skills/testsprite-cognitive-os/scripts/load_testsprite_env.sh; do
  [[ -f "${s}" ]] && ok "${s}" || bad "falta ${s}"
done

# --- Runners huérfanos / locks ---
pgrep -u "$USER" -f "generateCodeAndExecute" >/dev/null && bad "runner generateCodeAndExecute huérfano — prepare.sh" || ok "sin runner huérfano"
[[ -f testsprite_tests/tmp/execution.lock ]] && bad "execution.lock — prepare.sh" || ok "sin execution.lock"

# --- Playwright race (full-qa) ---
if pgrep -u "$USER" -f "${ROOT_DIR}/frontend/node_modules/.*playwright" >/dev/null 2>&1; then
  bad "Playwright del repo corriendo — no lanzar TestSprite en paralelo"
else
  ok "sin Playwright concurrente del repo"
fi

if [[ "${MODE}" == "stack" ]]; then
  if [[ "${fail}" -ne 0 ]]; then
    echo >&2
    echo "Recovery:" >&2
    echo "  bash scripts/dev_up.sh  # si stack down" >&2
    exit 1
  fi
  echo "STACK READY → bash scripts/testsprite_audit.sh"
  exit 0
fi

# --- API key (runtime/full) ---
key_ok=false
[[ -n "${API_KEY:-${TESTSPRITE_API_KEY:-}}" ]] && key_ok=true
if ! $key_ok && [[ -f testsprite_tests/tmp/config.json ]]; then
  python3 - <<'PY' && key_ok=true
import json, sys
from pathlib import Path
k = json.loads(Path("testsprite_tests/tmp/config.json").read_text()).get("executionArgs", {}).get("envs", {}).get("API_KEY", "")
sys.exit(0 if k and k not in ("", "<redacted>") else 1)
PY
fi
$key_ok && ok "API key presente" || bad "falta TESTSPRITE_API_KEY — añadir a .env o repoblar vía prepare"

# --- Config validate ---
if [[ -f testsprite_tests/tmp/config.json ]]; then
  if python3 "${SKILL_DIR}/scripts/validate_testsprite_config.py"; then
    ok "config.json validado"
  else
    bad "config.json inválido — bash scripts/testsprite_mcp_prepare.sh"
  fi
else
  bad "sin config.json — ejecutar prepare.sh primero"
fi

if [[ "${fail}" -ne 0 ]]; then
  echo >&2
  echo "Recovery:" >&2
  echo "  export TESTSPRITE_API_KEY=...  # si falta key" >&2
  echo "  bash scripts/testsprite_mcp_prepare.sh" >&2
  echo "  bash scripts/testsprite_audit.sh" >&2
  exit 1
fi

echo "READY → bash scripts/testsprite_audit.sh"
exit 0

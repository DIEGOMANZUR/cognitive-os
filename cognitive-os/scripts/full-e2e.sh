#!/usr/bin/env bash
# Playwright E2E gate for the local Cognitive OS cockpit.
#
# This is intentionally separate from full-qa.sh: Playwright needs the API and
# frontend runtime already serving on the local ports. Token bootstrap lives in
# frontend/tests/e2e/_global-setup.ts and must exercise POST /auth/local-token
# in dedicated_local/full instead of bypassing that route from this script.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_BASE="${COGOS_API_BASE:-http://127.0.0.1:8000}"
WEB_BASE="${COGOS_BASE_URL:-http://localhost:3001}"

cd "$ROOT/frontend"
if [[ "${COGOS_E2E_NPM_CI:-0}" == "1" ]]; then
  npm ci
elif [[ ! -d node_modules ]]; then
  echo "FAIL: frontend/node_modules is missing." >&2
  echo "Run npm ci in frontend/ first, or set COGOS_E2E_NPM_CI=1 before starting the frontend." >&2
  exit 1
else
  echo "OK: frontend deps already installed (skip npm ci; server must stay alive)"
fi

if [[ "${COGOS_SKIP_PLAYWRIGHT_INSTALL:-0}" != "1" ]]; then
  npx playwright install --with-deps chromium
fi

if ! curl -fsS "$API_BASE/health" >/dev/null; then
  echo "FAIL: API is not reachable at $API_BASE." >&2
  echo "Start the stack first, e.g. ~/Escritorio/Levantar\\ Cognitive\\ OS.sh" >&2
  exit 1
fi

if ! curl -fsSI "$WEB_BASE/" >/dev/null; then
  echo "FAIL: frontend is not reachable at $WEB_BASE." >&2
  echo "Start the stack first, e.g. ~/Escritorio/Levantar\\ Cognitive\\ OS.sh" >&2
  exit 1
fi

cors_headers="$(mktemp)"
trap 'rm -f "$cors_headers"' EXIT
cors_status="$(
  curl -sS -o /dev/null -D "$cors_headers" -w "%{http_code}" \
    -X OPTIONS "$API_BASE/health/dashboard" \
    -H "Origin: ${WEB_BASE%/}" \
    -H "Access-Control-Request-Method: GET" || true
)"
if [[ "$cors_status" -lt 200 || "$cors_status" -ge 400 ]] || ! grep -qi '^access-control-allow-origin:' "$cors_headers"; then
  echo "FAIL: API CORS does not allow frontend origin ${WEB_BASE%/}." >&2
  echo "      Add it to CORS_ALLOW_ORIGINS or run the frontend on an allowed local port." >&2
  exit 1
fi

COGOS_API_BASE="$API_BASE" COGOS_BASE_URL="$WEB_BASE" npx playwright test "$@"
echo "OK: full-e2e"

#!/usr/bin/env bash
# Read-only static/security API toolchain. Uses uvx so Bandit, Semgrep and
# Schemathesis do not become permanent project dependencies or mutate lockfiles.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:---scan}"
API_BASE="${COGOS_API_BASE:-http://127.0.0.1:8000}"
OPENAPI_URL="${COGOS_OPENAPI_URL:-$API_BASE/openapi.json}"
SCHEMATHESIS_MAX_EXAMPLES="${SCHEMATHESIS_MAX_EXAMPLES:-15}"
SCHEMATHESIS_REQUEST_TIMEOUT="${SCHEMATHESIS_REQUEST_TIMEOUT:-5.0}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/security-readonly-qa.sh --tool-smoke
  bash scripts/security-readonly-qa.sh --scan

Modes:
  --tool-smoke  Print versions for ephemeral Bandit/Semgrep/Schemathesis tools.
  --scan        Run read-only Bandit, Semgrep, local secret scan, and optional
                GET-only Schemathesis when COGOS_SCHEMATHESIS_LIVE_READONLY=1.

Schemathesis is opt-in because it performs live HTTP requests. It is constrained
to GET, a small example budget, and a request timeout.

Optional live-readonly knobs:
  COGOS_SCHEMATHESIS_AUTH_HEADER='Authorization: Bearer <jwt>'
  COGOS_SCHEMATHESIS_EXCLUDE_PATH_REGEX='^/test/'
EOF
}

run_step() {
  local name="$1"
  shift
  echo "=== $name ==="
  "$@"
}

if [[ "$MODE" == "-h" || "$MODE" == "--help" ]]; then
  usage
  exit 0
fi

cd "$ROOT"

case "$MODE" in
  --tool-smoke)
    run_step bandit-version uvx --from bandit bandit --version
    run_step semgrep-version uvx --from semgrep semgrep --version
    run_step schemathesis-version uvx --from schemathesis schemathesis --version
    ;;
  --scan)
    run_step bandit-readonly uvx --from bandit bandit \
      --severity-level high \
      --confidence-level medium \
      -q -r backend/src -x backend/tests
    run_step semgrep-readonly uvx --from semgrep semgrep scan --config p/python --quiet backend/src backend/tests
    run_step local-secret-scan bash scripts/scan-local-artifacts-for-secrets.sh
    if [[ "${COGOS_SCHEMATHESIS_LIVE_READONLY:-0}" == "1" ]]; then
      schemathesis_args=(
        run "$OPENAPI_URL"
        --include-method GET
        --max-examples "$SCHEMATHESIS_MAX_EXAMPLES"
        --request-timeout "$SCHEMATHESIS_REQUEST_TIMEOUT"
        --continue-on-failure
      )
      if [[ -n "${COGOS_SCHEMATHESIS_AUTH_HEADER:-}" ]]; then
        schemathesis_args+=(--header "${COGOS_SCHEMATHESIS_AUTH_HEADER}")
      fi
      if [[ -n "${COGOS_SCHEMATHESIS_EXCLUDE_PATH_REGEX:-}" ]]; then
        schemathesis_args+=(--exclude-path-regex "${COGOS_SCHEMATHESIS_EXCLUDE_PATH_REGEX}")
      fi
      run_step schemathesis-get-readonly \
        uvx --from schemathesis schemathesis "${schemathesis_args[@]}"
    else
      echo "SKIP: schemathesis live-readonly disabled."
      echo "      Run with COGOS_SCHEMATHESIS_LIVE_READONLY=1 when the API target is safe."
    fi
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

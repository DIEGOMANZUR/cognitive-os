#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${COMMERCIAL_QA_REPORT_DIR:-$ROOT/qa/reports}"
API_BASE="${COGOS_API_BASE:-http://127.0.0.1:8000}"
STRESS_RUNS="${COMMERCIAL_QA_STRESS_RUNS:-1}"
mkdir -p "$REPORT_DIR"

run_step() {
  local name="$1"
  shift
  local log="$REPORT_DIR/${name}.log"
  echo "=== $name ==="
  set +e
  "$@" 2>&1 | tee "$log"
  local status="${PIPESTATUS[0]}"
  set -e
  if [[ "$status" -ne 0 ]]; then
    echo "FAIL: $name (see $log)" >&2
    exit "$status"
  fi
}

fixture_live_probe() {
  local log="$REPORT_DIR/fixtures-live.log"
  echo "=== fixtures-live ==="
  {
    echo "POST /test/fixtures/reset"
    status="$(curl -sS -o "$REPORT_DIR/fixtures-reset.json" -w "%{http_code}" \
      -X POST "$API_BASE/test/fixtures/reset" || true)"
    if [[ "$status" == "200" ]]; then
      for scenario in empty degraded populated pending_approval failed_job retryable_job mail_digest_disabled mail_digest_read_only malformed_api_state mobile_friendly_state; do
        curl -fsS -X POST "$API_BASE/test/fixtures/seed/$scenario" \
          -o "$REPORT_DIR/fixtures-seed-$scenario.json"
      done
      curl -fsS "$API_BASE/test/fixtures/state" -o "$REPORT_DIR/fixtures-state.json"
      curl -fsS -X POST "$API_BASE/test/fixtures/reset" -o "$REPORT_DIR/fixtures-reset-final.json"
      echo "OK: live fixture reset/seed/reset completed"
      return 0
    fi
    echo "WARN: live fixture endpoints returned HTTP $status."
    echo "      Start the API with APP_ENV=test or COGOS_TEST_FIXTURES_ENABLED=true to exercise them live."
    echo "      Hermetic ASGI fixture tests run in fixtures-backend and are the hard gate."
    return 0
  } 2>&1 | tee "$log"
}

cd "$ROOT"

run_step full-qa bash scripts/full-qa.sh
run_step fixtures-backend bash -lc 'cd backend && uv run pytest tests/test_test_fixtures_api.py -q'
fixture_live_probe
run_step playwright-critical bash -lc 'cd frontend && COGOS_SKIP_PLAYWRIGHT_INSTALL="${COGOS_SKIP_PLAYWRIGHT_INSTALL:-1}" npx playwright test tests/e2e/commercial-fixtures-critical.spec.ts'
run_step full-e2e bash -lc 'COGOS_SKIP_PLAYWRIGHT_INSTALL="${COGOS_SKIP_PLAYWRIGHT_INSTALL:-1}" bash scripts/full-e2e.sh'
run_step stress-moderate bash scripts/stress-qa.sh "$STRESS_RUNS"
run_step qa-stack-health python3 scripts/probe-qa-stack-health.py --url "$API_BASE/health" --output "$REPORT_DIR/qa_stack_health.json"
run_step secret-scan bash scripts/scan-local-artifacts-for-secrets.sh

if [[ -n "${TESTSPRITE_API_KEY:-}" || -n "${API_KEY:-}" ]]; then
  run_step testsprite-batched bash scripts/full-testsprite.sh
else
  echo "WARN: TESTSPRITE_API_KEY/API_KEY not set; skipping TestSprite batched run." \
    | tee "$REPORT_DIR/testsprite-skipped.log"
  cat >"$REPORT_DIR/testsprite_latest_summary.md" <<EOF
# TestSprite Latest Summary

- Generated at UTC: \`$(date -u +%Y-%m-%dT%H:%M:%SZ)\`
- TestSprite package: \`${TESTSPRITE_PACKAGE:-@testsprite/testsprite-mcp@0.0.19}\`
- Canonical plan: \`qa/testsprite/frontend_commercial_plan.json\`
- Latest real execution status: **NOT_RUN_NO_API_KEY**
- Verdict: **BLOCKED**

## Blocking Error

- \`TESTSPRITE_API_KEY/API_KEY\` was not present in the environment for this gate run.
- The gate intentionally did not reuse stale ignored TestSprite results as a green signal.
EOF
fi

echo "OK: full-commercial-qa (reports: $REPORT_DIR)"

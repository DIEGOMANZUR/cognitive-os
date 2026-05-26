#!/usr/bin/env bash
# Único entrypoint canónico para auditorías TestSprite en Cognitive OS.
# Impone: stack verify → prepare → validate config → smoke TC001 → plan 28/28 → export.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

SKILL_DIR="${ROOT_DIR}/.cursor/skills/testsprite-cognitive-os"
SKILL_VERIFY="${SKILL_DIR}/scripts/verify_testsprite_ready.sh"
SKILL_VALIDATE="${SKILL_DIR}/scripts/validate_testsprite_config.py"
SKILL_ASSERT="${SKILL_DIR}/scripts/assert_testsprite_run.py"
SKILL_ENV="${SKILL_DIR}/scripts/load_testsprite_env.sh"
PHASE="${TESTSPRITE_AUDIT_PHASE:-all}"  # all | verify | smoke | full

log() { printf '[testsprite_audit] %s\n' "$*"; }
die() { printf '[testsprite_audit] ERROR: %s\n' "$*" >&2; exit 1; }

# shellcheck disable=SC1091
source "${SKILL_ENV}" "${ROOT_DIR}"

export TESTSPRITE_BATCH_SIZE="${TESTSPRITE_BATCH_SIZE:-1}"

run_stack_verify() {
  log "FASE 0 — verify stack (sin exigir config previa)"
  TESTSPRITE_VERIFY_MODE=stack bash "${SKILL_VERIFY}"
}

run_prepare() {
  log "FASE 1 — prepare (reset config, plan, locks)"
  bash scripts/testsprite_mcp_prepare.sh
  python3 "${SKILL_VALIDATE}"
}

run_runtime_verify() {
  log "FASE 1b — verify runtime (config + API key)"
  TESTSPRITE_VERIFY_MODE=runtime bash "${SKILL_VERIFY}"
}

run_smoke() {
  log "FASE 2 — smoke TC001 (gate obligatorio)"
  local logfile="${ROOT_DIR}/test-results/testsprite/smoke-tc001-$(date +%Y%m%d_%H%M%S).log"
  mkdir -p "$(dirname "${logfile}")"
  if ! TESTSPRITE_TEST_IDS=TC001 TESTSPRITE_BATCH_SIZE=1 bash scripts/full-testsprite.sh 2>&1 | tee "${logfile}"; then
    die "smoke TC001 failed — NO continuar al plan completo. Ver ${logfile}"
  fi
  python3 "${SKILL_ASSERT}" --mode smoke --log "${logfile}"
  log "smoke TC001 OK → ${logfile}"
}

run_full() {
  log "FASE 3 — plan completo serial (28 casos)"
  local logfile="${ROOT_DIR}/test-results/testsprite/full-plan-$(date +%Y%m%d_%H%M%S).log"
  mkdir -p "$(dirname "${logfile}")"
  unset TESTSPRITE_TEST_IDS
  export TESTSPRITE_BATCH_SIZE=1
  if ! bash scripts/full-testsprite.sh 2>&1 | tee "${logfile}"; then
    die "plan completo falló — ver ${logfile}"
  fi
  python3 "${SKILL_ASSERT}" --mode full --log "${logfile}"
  log "plan completo OK → ${logfile}"
}

export_artifacts() {
  log "FASE 4 — export evidencia"
  local ts_dir="${ROOT_DIR}/test-results/testsprite/audit-$(date +%Y%m%d_%H%M%S)"
  mkdir -p "${ts_dir}"
  for f in test_results.json raw_report.md batched_results.json; do
    [[ -f "testsprite_tests/tmp/${f}" ]] && cp "testsprite_tests/tmp/${f}" "${ts_dir}/"
  done
  cp qa/reports/testsprite_latest_summary.md "${ts_dir}/" 2>/dev/null || true
  log "artefactos → ${ts_dir}"
  log "VERDICT TestSprite: PASS (28/28, smoke gate OK)"
}

case "${PHASE}" in
  verify)
    run_stack_verify
    run_prepare
    run_runtime_verify
    ;;
  smoke)
    run_stack_verify
    run_prepare
    run_runtime_verify
    run_smoke
    log "VERDICT TestSprite: PARTIAL (smoke TC001 OK)"
    ;;
  full)
    run_stack_verify
    run_prepare
    run_runtime_verify
    run_smoke
    run_full
    export_artifacts
    ;;
  all)
    run_stack_verify
    run_prepare
    run_runtime_verify
    run_smoke
    run_full
    export_artifacts
    log "AUDIT TestSprite COMPLETE"
    ;;
  *)
    die "TESTSPRITE_AUDIT_PHASE inválido: ${PHASE} (use verify|smoke|full|all)"
    ;;
esac

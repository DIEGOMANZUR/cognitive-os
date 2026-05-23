#!/usr/bin/env bash
# Comprobaciones locales: backend (con extra OpenHarness para prueba de fusión) + frontend.
# Alembic es un gate real cuando el repo tiene DB configurada (.env/.env.local
# o DATABASE_URL). Solo se omite en clones sin ninguna configuracion DB.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QA_NEXT_DIST=".next-qa"
cleanup_qa_artifacts() {
  rm -rf "$ROOT/frontend/$QA_NEXT_DIST"
}
trap cleanup_qa_artifacts EXIT
cleanup_qa_artifacts
cd "$ROOT/backend"
uv sync --extra openharness
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
if [[ -n "${DATABASE_URL:-}" ]] || [[ -f "$ROOT/.env.local" ]] || [[ -f "$ROOT/.env" ]]; then
  uv run alembic check
  echo "OK: alembic check (sin drift)"
else
  echo "SKIP: alembic check (no hay DATABASE_URL ni .env)"
fi
cd "$ROOT/frontend"
# Guard: `npm ci` deletes + rebuilds `node_modules/`. If THIS repo's
# Playwright is running concurrently it loses
# `node_modules/playwright/lib/worker/workerProcessEntry.js` mid-flight
# and every spec crashes with `Cannot find module ...`. The 2026-05-23
# TestSprite re-audit caught this exact race. Abort with a clear message
# so the operator picks one or the other.
#
# The pattern is narrow on purpose: only Playwright that runs FROM this
# repo's node_modules (`cognitive-os/frontend/node_modules/...`). Other
# `playwright`/`ms-playwright-go` processes from unrelated workspaces
# do not affect this `npm ci` and should not trigger a false abort.
QA_PW_PATTERN="${ROOT}/frontend/node_modules/.*(@playwright/test|playwright)/.*(cli|worker)"
if pgrep -u "$USER" -f "$QA_PW_PATTERN" >/dev/null 2>&1; then
  echo "FAIL: another Playwright run from this repo is in flight." >&2
  echo "      'npm ci' would wipe its node_modules/ mid-run and crash it." >&2
  echo "      Wait for Playwright to finish, then re-run scripts/full-qa.sh." >&2
  exit 1
fi
npm ci
npm run lint
rm -rf "$QA_NEXT_DIST"
# Build in an isolated Next dist dir so QA never invalidates a live
# `next start` process serving frontend/.next on the dedicated PC.
NEXT_DIST_DIR="$QA_NEXT_DIST" npm run build
rm -rf "$QA_NEXT_DIST"
cd "$ROOT"
# Conteos canónicos de docs sincronizados con el código (AUDIT-2026-G).
if python3 scripts/sync_doc_counts.py --check; then
  echo "OK: sync_doc_counts --check"
else
  echo "FAIL: docs/CURRENT_STATE.md tiene conteos desincronizados." >&2
  echo "      Corré: python3 scripts/sync_doc_counts.py" >&2
  exit 1
fi
if command -v git >/dev/null && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git diff --check >/dev/null; then
    echo "OK: git diff --check (sin whitespace/conflicto pendiente)"
  else
    echo "FAIL: git diff --check detectó whitespace/conflicto pendiente." >&2
    exit 1
  fi
else
  echo "SKIP: git diff --check (no es repo git)"
fi
echo "OK: full-qa"

#!/usr/bin/env bash
set -u

OUT_DIR="${1:-.codex-audit/logs}"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/safe-verify.txt"
: > "$OUT"

run_cmd() {
  name="$1"
  shift
  echo "" | tee -a "$OUT"
  echo "== $name ==" | tee -a "$OUT"
  echo "COMMAND: $*" | tee -a "$OUT"
  "$@" >> "$OUT" 2>&1
  code=$?
  echo "EXIT_CODE: $code" | tee -a "$OUT"
  return 0
}

echo "Safe verification started at $(date -Iseconds 2>/dev/null || date)" | tee -a "$OUT"

if [ -f package.json ]; then
  if command -v npm >/dev/null 2>&1; then
    run_cmd "npm scripts" npm run
  fi

  if command -v pnpm >/dev/null 2>&1 && [ -f pnpm-lock.yaml ]; then
    run_cmd "pnpm scripts" pnpm run
  fi

  if command -v yarn >/dev/null 2>&1 && [ -f yarn.lock ]; then
    run_cmd "yarn scripts" yarn run
  fi
fi

if [ -f pyproject.toml ] || [ -f requirements.txt ]; then
  if command -v python3 >/dev/null 2>&1; then
    run_cmd "python version" python3 --version
  elif command -v python >/dev/null 2>&1; then
    run_cmd "python version" python --version
  fi
fi

if [ -f docker-compose.yml ] || [ -f compose.yml ]; then
  if command -v docker >/dev/null 2>&1; then
    run_cmd "docker compose config" docker compose config
  fi
fi

if [ -f Dockerfile ]; then
  echo "Dockerfile present. Build not run automatically unless auditor decides it is safe." | tee -a "$OUT"
fi

#!/usr/bin/env bash
set -u

OUT_DIR="${1:-.codex-audit/raw}"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/detect-stack.txt"
: > "$OUT"

log() {
  echo "$1" | tee -a "$OUT"
}

log "== Stack detection =="

for f in package.json pnpm-lock.yaml yarn.lock package-lock.json pyproject.toml requirements.txt poetry.lock go.mod Cargo.toml Dockerfile docker-compose.yml compose.yml Makefile; do
  if [ -f "$f" ]; then
    log "FOUND: $f"
  fi
done

log ""
log "== Tool availability =="
for cmd in git node npm pnpm yarn bun python python3 pip pip3 poetry pytest ruff mypy go cargo docker docker-compose rg grep awk sed jq semgrep gitleaks trufflehog; do
  if command -v "$cmd" >/dev/null 2>&1; then
    log "AVAILABLE: $cmd -> $(command -v "$cmd")"
  else
    log "MISSING: $cmd"
  fi
done

log ""
log "== package.json scripts =="
if [ -f package.json ]; then
  if command -v jq >/dev/null 2>&1; then
    jq '.scripts // {}' package.json | tee -a "$OUT"
  else
    grep -n '"scripts"' -A 40 package.json | tee -a "$OUT" || true
  fi
else
  log "No package.json"
fi

log ""
log "== Python project metadata =="
if [ -f pyproject.toml ]; then
  grep -nE "^\[tool\.|^\[project\]|dependencies|pytest|ruff|mypy|poetry" pyproject.toml | tee -a "$OUT" || true
fi

log ""
log "== Docker/Compose =="
if [ -f docker-compose.yml ] || [ -f compose.yml ]; then
  if command -v docker >/dev/null 2>&1; then
    docker compose config >/tmp/codex_compose_config.txt 2>/tmp/codex_compose_config.err
    code=$?
    log "docker compose config exit code: $code"
    cat /tmp/codex_compose_config.err | tee -a "$OUT" || true
  else
    log "Docker missing"
  fi
fi

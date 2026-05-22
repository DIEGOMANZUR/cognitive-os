#!/usr/bin/env bash
set -u

OUT_DIR="${1:-.codex-audit/raw}"
mkdir -p "$OUT_DIR"

echo "== pwd ==" | tee "$OUT_DIR/inventory.txt"
pwd | tee -a "$OUT_DIR/inventory.txt"

echo "" | tee -a "$OUT_DIR/inventory.txt"
echo "== uname ==" | tee -a "$OUT_DIR/inventory.txt"
uname -a 2>/dev/null | tee -a "$OUT_DIR/inventory.txt" || true

echo "" | tee -a "$OUT_DIR/inventory.txt"
echo "== git status ==" | tee -a "$OUT_DIR/inventory.txt"
git status --short 2>/dev/null | tee -a "$OUT_DIR/inventory.txt" || echo "No git repo or git unavailable" | tee -a "$OUT_DIR/inventory.txt"

echo "" | tee -a "$OUT_DIR/inventory.txt"
echo "== top-level files ==" | tee -a "$OUT_DIR/inventory.txt"
find . -maxdepth 2 \
  -path "./.git" -prune -o \
  -path "./node_modules" -prune -o \
  -path "./.venv" -prune -o \
  -path "./venv" -prune -o \
  -path "./dist" -prune -o \
  -path "./build" -prune -o \
  -print 2>/dev/null | sort | tee -a "$OUT_DIR/inventory.txt"

echo "" | tee -a "$OUT_DIR/inventory.txt"
echo "== important files ==" | tee -a "$OUT_DIR/inventory.txt"
find . -maxdepth 4 -type f \( \
  -name "package.json" -o \
  -name "pnpm-lock.yaml" -o \
  -name "yarn.lock" -o \
  -name "package-lock.json" -o \
  -name "pyproject.toml" -o \
  -name "requirements.txt" -o \
  -name "poetry.lock" -o \
  -name "go.mod" -o \
  -name "Cargo.toml" -o \
  -name "Dockerfile" -o \
  -name "docker-compose.yml" -o \
  -name "compose.yml" -o \
  -name ".env" -o \
  -name ".env.example" -o \
  -name "AGENTS.md" -o \
  -name "CLAUDE.md" -o \
  -name "README.md" \
\) 2>/dev/null | sort | tee -a "$OUT_DIR/inventory.txt"

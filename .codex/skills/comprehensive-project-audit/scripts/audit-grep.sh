#!/usr/bin/env bash
set -u

OUT_DIR="${1:-.codex-audit/raw}"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/audit-grep.txt"
: > "$OUT"

if command -v rg >/dev/null 2>&1; then
  SEARCH="rg"
else
  SEARCH="grep -RIn"
fi

echo "== Suspicious markers ==" | tee -a "$OUT"
$SEARCH "TODO|FIXME|HACK|XXX|BUG|TEMP|temporary|workaround|console\.log|debugger|eslint-disable|ts-ignore|any" . \
  --glob '!node_modules/**' \
  --glob '!.git/**' \
  --glob '!dist/**' \
  --glob '!build/**' \
  --glob '!.venv/**' \
  2>/dev/null | tee -a "$OUT" || true

echo "" | tee -a "$OUT"
echo "== Possible secrets / sensitive tokens ==" | tee -a "$OUT"
$SEARCH "api[_-]?key|secret|token|password|passwd|private[_-]?key|BEGIN RSA|BEGIN OPENSSH|JWT_SECRET|DATABASE_URL|OPENAI_API_KEY|ANTHROPIC_API_KEY|GEMINI_API_KEY" . \
  --glob '!node_modules/**' \
  --glob '!.git/**' \
  --glob '!dist/**' \
  --glob '!build/**' \
  --glob '!.venv/**' \
  2>/dev/null | tee -a "$OUT" || true

echo "" | tee -a "$OUT"
echo "== Risky backend patterns ==" | tee -a "$OUT"
$SEARCH "eval\(|exec\(|spawn\(|child_process|subprocess|os\.system|pickle\.loads|yaml\.load|innerHTML|dangerouslySetInnerHTML|raw SQL|SELECT \*|cors\(|allow_origins=\[\"\*\"\]" . \
  --glob '!node_modules/**' \
  --glob '!.git/**' \
  --glob '!dist/**' \
  --glob '!build/**' \
  --glob '!.venv/**' \
  2>/dev/null | tee -a "$OUT" || true

#!/usr/bin/env bash
# Carga segura de TESTSPRITE_API_KEY / API_KEY desde .env sin `source` completo.
# Evita fallos por líneas cron (p.ej. DEEPAGENTS_MEMORY_CONSOLIDATION_CRON=0 3 * * *).
set -euo pipefail

ROOT_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)}"
ENV_FILE="${ROOT_DIR}/.env"

if [[ -n "${TESTSPRITE_API_KEY:-}" || -n "${API_KEY:-}" ]]; then
  exit 0
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  exit 0
fi

while IFS= read -r export_line; do
  [[ -z "${export_line}" ]] && continue
  # shellcheck disable=SC2163
  export "${export_line?}"
done < <(
  python3 - "${ENV_FILE}" <<'PY'
import re
import shlex
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)

for raw in path.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    match = re.match(r"^(?:export\s+)?(TESTSPRITE_API_KEY|API_KEY)=(.*)$", line)
    if not match:
        continue
    name, value = match.group(1), match.group(2).strip()
    if not value or value in ('""', "''"):
        continue
    if (value[0], value[-1]) in {('"', '"'), ("'", "'")}:
        value = value[1:-1]
    print(f"{name}={shlex.quote(value)}")
PY
)

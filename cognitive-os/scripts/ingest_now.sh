#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/ingest_now.sh PATH_AL_PDF" >&2
  exit 2
fi

PDF_PATH="$1"
if [[ "${PDF_PATH}" != /* ]]; then
  PDF_PATH="$(pwd)/${PDF_PATH}"
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

bash scripts/init_env.sh >/dev/null
cd backend
uv run python -m cognitive_os.ingestion.pipeline "${PDF_PATH}"

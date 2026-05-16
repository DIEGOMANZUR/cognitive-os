#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_DIR="${ROOT_DIR}/experiments/openshell-deepagent/vendor/openshell-deepagent"

if [ ! -d "${VENDOR_DIR}" ]; then
  echo "OpenShell vendor repo missing."
  exit 1
fi

cd "${VENDOR_DIR}"
uv run openshell gateway stop
echo "Gateway stop requested. Outputs are left intact."

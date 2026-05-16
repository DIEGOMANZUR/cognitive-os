#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_DIR="${ROOT_DIR}/experiments/openshell-deepagent/vendor/openshell-deepagent"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not in PATH."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running."
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed or not in PATH."
  exit 1
fi

if [ ! -d "${VENDOR_DIR}" ]; then
  echo "OpenShell vendor repo missing at ${VENDOR_DIR}."
  echo "Run: git clone --depth 1 https://github.com/langchain-ai/openshell-deepagent ${VENDOR_DIR}"
  exit 1
fi

cd "${VENDOR_DIR}"
uv sync
uv run openshell --version
echo "OpenShell vendor is installed. NVIDIA_API_KEY is only required for real agent execution."

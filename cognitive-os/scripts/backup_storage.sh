#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

BACKUP_ROOT="${BACKUP_DIR:-./backups}/storage"
STORAGE_ROOT="${LOCAL_STORAGE_DIR:-./storage}"
mkdir -p "${BACKUP_ROOT}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BACKUP_ROOT}/storage_${STAMP}.tar.gz"

if [[ ! -d "${STORAGE_ROOT}" ]]; then
  echo "No existe storage local en ${STORAGE_ROOT}; creando backup vacío trazable."
  mkdir -p "${STORAGE_ROOT}"
fi

tar -czf "${OUT}" -C "$(dirname "${STORAGE_ROOT}")" "$(basename "${STORAGE_ROOT}")"
sha256sum "${OUT}" > "${OUT}.sha256"
echo "Backup storage creado: ${OUT}"

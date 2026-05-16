#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
  echo "Restore abortado. Ejecuta con CONFIRM_RESTORE=YES para continuar." >&2
  exit 2
fi

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

ARCHIVE_PATH="${1:-}"
if [[ -z "${ARCHIVE_PATH}" || ! -f "${ARCHIVE_PATH}" ]]; then
  echo "Uso: CONFIRM_RESTORE=YES bash scripts/restore_storage.sh backups/storage/ARCHIVO.tar.gz" >&2
  exit 1
fi

if [[ -f "${ARCHIVE_PATH}.sha256" ]]; then
  sha256sum -c "${ARCHIVE_PATH}.sha256"
else
  echo "Advertencia: no existe ${ARCHIVE_PATH}.sha256; restore continua sin verificacion." >&2
fi

STORAGE_ROOT="${LOCAL_STORAGE_DIR:-./storage}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

if [[ -d "${STORAGE_ROOT}" ]]; then
  SAFETY_COPY="${STORAGE_ROOT}.pre_restore_${STAMP}"
  echo "Moviendo storage actual a ${SAFETY_COPY}..."
  mv "${STORAGE_ROOT}" "${SAFETY_COPY}"
fi

mkdir -p "$(dirname "${STORAGE_ROOT}")"
tar -xzf "${ARCHIVE_PATH}" -C "$(dirname "${STORAGE_ROOT}")"

echo "Restore storage completado en ${STORAGE_ROOT}."

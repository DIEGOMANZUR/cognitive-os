#!/usr/bin/env bash
# Read-only smoke test for the desktop launchers used to operate Cognitive OS.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${COGOS_REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
DESKTOP_DIR="${COGOS_DESKTOP_DIR:-${HOME}/Escritorio}"
MASTER="${COGOS_MASTER:-${DESKTOP_DIR}/cognitive-os.sh}"
OPEN_TERMINAL="${COGOS_OPEN_TERMINAL:-${DESKTOP_DIR}/cognitive-os-open-terminal.sh}"

failures=0

fail() {
    echo "FAIL: $*" >&2
    failures=$((failures + 1))
}

check_file() {
    local path="$1"
    if [[ ! -f "${path}" ]]; then
        fail "missing file: ${path}"
        return 1
    fi
    return 0
}

check_executable() {
    local path="$1"
    if [[ ! -x "${path}" ]]; then
        fail "not executable: ${path}"
        return 1
    fi
    return 0
}

check_bash_syntax() {
    local path="$1"
    if ! bash -n "${path}"; then
        fail "bash syntax failed: ${path}"
    fi
}

check_desktop_file() {
    local label="$1"
    local wrapper="$2"
    local desktop_file="${DESKTOP_DIR}/${label}.desktop"

    check_file "${desktop_file}" || return
    check_executable "${desktop_file}"
    if ! grep -Fq "Type=Application" "${desktop_file}"; then
        fail "${desktop_file} is missing Type=Application"
    fi
    if ! grep -Fq "Exec=" "${desktop_file}"; then
        fail "${desktop_file} is missing Exec="
    fi
    if ! grep -Fq "${wrapper}" "${desktop_file}"; then
        fail "${desktop_file} does not reference wrapper ${wrapper}"
    fi
    if grep -Fq "${OPEN_TERMINAL}" "${desktop_file}"; then
        check_file "${OPEN_TERMINAL}" && check_executable "${OPEN_TERMINAL}" && check_bash_syntax "${OPEN_TERMINAL}"
    fi
}

check_wrapper() {
    local label="$1"
    local mode="$2"
    local wrapper="${DESKTOP_DIR}/${label}.sh"

    check_file "${wrapper}" || return
    check_executable "${wrapper}"
    check_bash_syntax "${wrapper}"
    if ! grep -Fq "MASTER=\"${MASTER}\"" "${wrapper}"; then
        fail "${wrapper} does not target master ${MASTER}"
    fi
    if ! grep -Eq "\"\\$\\{MASTER\\}\"[[:space:]]+${mode}|\"\\$MASTER\"[[:space:]]+${mode}" "${wrapper}"; then
        fail "${wrapper} does not invoke master mode ${mode}"
    fi
    check_desktop_file "${label}" "${wrapper}"
}

check_file "${REPO_ROOT}/infra/docker-compose.yml"
check_file "${REPO_ROOT}/backend/pyproject.toml"
check_file "${REPO_ROOT}/frontend/package.json"

check_file "${MASTER}" && check_executable "${MASTER}" && check_bash_syntax "${MASTER}"

check_wrapper "Levantar Cognitive OS" "start"
check_wrapper "Reiniciar Cognitive OS" "restart"
check_wrapper "Detener Cognitive OS" "stop"
check_wrapper "Estado Cognitive OS" "status"

if (( failures > 0 )); then
    echo "Desktop launcher verification failed with ${failures} issue(s)." >&2
    exit 1
fi

echo "Desktop launchers OK: ${DESKTOP_DIR}"

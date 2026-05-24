#!/usr/bin/env bash
# Report status of the TestSprite Web Portal stack: PIDs, ports, local and
# public health.
#
# Intentionally NOT `set -e`: this script reports on possibly-broken state, so
# individual probe failures must not abort the rest of the report.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs/testsprite_web"

bold() { printf '\n=== %s ===\n' "$*"; }

bold "Processes"
report_svc() {
  local svc="$1" pattern="$2"
  local pids
  pids="$(pgrep -f "${pattern}" 2>/dev/null | head -3 | tr '\n' ',' | sed 's/,$//')"
  if [ -n "${pids}" ]; then
    printf '%-12s : running (PID %s)\n' "${svc}" "${pids}"
  else
    printf '%-12s : NOT running\n' "${svc}"
  fi
}
report_svc backend     "uvicorn.*cognitive_os.api.app:app"
report_svc worker      "celery.*worker"
report_svc beat        "celery.*beat"
# next-server reparents to init and drops the `-p 3001` arg from the process
# name, so identify by listening port instead.
frontend_pid="$(ss -tlnp 2>/dev/null | awk '/127\.0\.0\.1:3001/ {print $NF}' | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2 || true)"
if [ -n "${frontend_pid}" ]; then
  printf '%-12s : running (PID %s, bound to :3001)\n' "frontend" "${frontend_pid}"
else
  printf '%-12s : NOT running\n' "frontend"
fi
report_svc cloudflared "cloudflared tunnel.*cognitive-os-testsprite"

bold "Ports"
ss -ltn 2>/dev/null | awk 'NR==1 || /:(3001|8000|20241) /'

bold "Local health"
curl -sS -o /dev/null -w "  http://127.0.0.1:8000/health        %{http_code}\n" http://127.0.0.1:8000/health  || echo "  backend unreachable"
curl -sS -o /dev/null -w "  http://127.0.0.1:3001/              %{http_code}\n" http://127.0.0.1:3001/         || echo "  frontend unreachable"

bold "Public health"
curl -sS -o /dev/null -w "  https://cognitive-api.doctormanzur.com/health  %{http_code}\n" https://cognitive-api.doctormanzur.com/health || echo "  public backend unreachable"
curl -sS -o /dev/null -w "  https://cognitive.doctormanzur.com/            %{http_code}\n" https://cognitive.doctormanzur.com/         || echo "  public frontend unreachable"

bold "Cloudflared connections (last 5 lines)"
[ -f "${LOG_DIR}/cloudflared.log" ] && tail -n 5 "${LOG_DIR}/cloudflared.log" || echo "  no cloudflared.log yet"

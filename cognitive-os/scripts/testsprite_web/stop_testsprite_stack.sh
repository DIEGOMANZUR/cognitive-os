#!/usr/bin/env bash
# Stop the TestSprite Web Portal stack started by start_testsprite_stack.sh.
# Sends SIGTERM, waits 5s, then SIGKILL. Does NOT touch Docker (infra stays up
# for other workflows; run scripts/dev_down.sh manually if you want it gone).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs/testsprite_web"

log() { printf '[stop_testsprite_stack] %s\n' "$*"; }

kill_group_or_pattern() {
  # Kill by process-group id if possible (services are started under `setsid`),
  # falling back to pgrep-by-pattern if the pidfile is stale.
  local svc="$1"; local pattern="$2"
  local pidfile="${LOG_DIR}/${svc}.pid"

  local pgid=""
  if [ -f "${pidfile}" ]; then
    local pid
    pid="$(cat "${pidfile}" 2>/dev/null || true)"
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
      pgid="$(ps -o pgid= -p "${pid}" 2>/dev/null | tr -d ' ' || true)"
    fi
  fi

  if [ -n "${pgid}" ]; then
    log "${svc}: SIGTERM process group ${pgid}"
    kill -TERM -- "-${pgid}" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 -- "-${pgid}" 2>/dev/null || break
      sleep 1
    done
    kill -KILL -- "-${pgid}" 2>/dev/null || true
  fi

  # Fallback / belt-and-suspenders: kill anything matching the service pattern.
  if [ -n "${pattern}" ]; then
    local pids
    pids="$(pgrep -f "${pattern}" 2>/dev/null || true)"
    if [ -n "${pids}" ]; then
      log "${svc}: killing leftovers matching '${pattern}': ${pids//$'\n'/, }"
      pkill -TERM -f "${pattern}" 2>/dev/null || true
      sleep 2
      pkill -KILL -f "${pattern}" 2>/dev/null || true
    fi
  fi

  rm -f "${pidfile}"
}

# Stop tunnel first so we stop serving the public endpoint, then the app.
kill_group_or_pattern cloudflared "cloudflared tunnel.*cognitive-os-testsprite"
# The next-server process drops the original `next start -p 3001` parent and
# reparents to init, so match it by the port it is bound to.
frontend_pid="$(ss -tlnp 2>/dev/null | awk '/127\.0\.0\.1:3001/ {print $NF}' | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2 || true)"
if [ -n "${frontend_pid}" ]; then
  log "frontend: SIGTERM PID ${frontend_pid} (bound to :3001)"
  kill "${frontend_pid}" 2>/dev/null || true
  sleep 2
  kill -9 "${frontend_pid}" 2>/dev/null || true
fi
rm -f "${LOG_DIR}/frontend.pid"
kill_group_or_pattern beat        "celery.*beat"
kill_group_or_pattern worker      "celery.*worker"
kill_group_or_pattern backend     "uvicorn.*cognitive_os.api.app:app"

log "stack stopped (Docker infra left running; use scripts/dev_down.sh to stop containers)"

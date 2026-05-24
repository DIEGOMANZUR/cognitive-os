#!/usr/bin/env bash
# Bring up the full Cognitive OS local stack + Cloudflare Tunnel for TestSprite
# Web Portal. The tunnel publishes:
#   - https://cognitive.doctormanzur.com      -> http://localhost:3001 (Next.js)
#   - https://cognitive-api.doctormanzur.com  -> http://localhost:8000 (FastAPI)
#
# Idempotent: re-running stops orphan PIDs from a previous run before launching
# new ones. Logs and PIDs land under logs/testsprite_web/. Frontend is rebuilt
# every time so NEXT_PUBLIC_API_BASE_URL is baked into the bundle.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

LOG_DIR="${ROOT_DIR}/logs/testsprite_web"
mkdir -p "${LOG_DIR}"

TUNNEL_NAME="cognitive-os-testsprite"
TUNNEL_CFG="${HOME}/.cloudflared/${TUNNEL_NAME}.yml"
FRONTEND_PUBLIC_API="${FRONTEND_PUBLIC_API:-https://cognitive-api.doctormanzur.com}"

log() { printf '[start_testsprite_stack] %s\n' "$*"; }

# 1. Pre-flight: cloudflared + tunnel config
if ! command -v cloudflared >/dev/null 2>&1; then
  log "ERROR: cloudflared not installed"; exit 1
fi
if ! cloudflared tunnel list 2>/dev/null | grep -q "${TUNNEL_NAME}"; then
  log "ERROR: tunnel '${TUNNEL_NAME}' not found. Run setup once (see scripts/testsprite_web/README.md)"
  exit 1
fi
if [ ! -f "${TUNNEL_CFG}" ]; then
  log "ERROR: missing tunnel config ${TUNNEL_CFG}"
  exit 1
fi

# 2. Stop any orphan PIDs from a previous run
for svc in backend worker beat frontend cloudflared; do
  pidfile="${LOG_DIR}/${svc}.pid"
  if [ -f "${pidfile}" ]; then
    oldpid="$(cat "${pidfile}" 2>/dev/null || true)"
    if [ -n "${oldpid}" ] && kill -0 "${oldpid}" 2>/dev/null; then
      log "stopping orphan ${svc} PID ${oldpid}"
      kill "${oldpid}" 2>/dev/null || true
      sleep 1
      kill -9 "${oldpid}" 2>/dev/null || true
    fi
    rm -f "${pidfile}"
  fi
done
# Beat lockfile from a prior crash blocks the next beat instance.
rm -f "${ROOT_DIR}/backend/celerybeat-schedule" || true

# 3. Infra (Docker) + migrations
log "starting Docker infra"
bash scripts/dev_up.sh

log "applying alembic migrations"
( cd backend && uv run alembic upgrade head )

# `setsid` makes each child a session/process-group leader so stop_script can
# tear down the whole group with `kill -- -<pgid>` instead of chasing forks.
launch() {
  local name="$1"; shift
  local cmd="$*"
  nohup setsid bash -c "${cmd}" > "${LOG_DIR}/${name}.log" 2>&1 &
  echo $! > "${LOG_DIR}/${name}.pid"
}

# 4. Backend (FastAPI, uvicorn, no reload)
log "starting backend"
launch backend "cd '${ROOT_DIR}/backend' && exec uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000"

# 5. Worker
log "starting Celery worker"
launch worker "exec bash '${ROOT_DIR}/scripts/dev_worker.sh'"

# 6. Beat
log "starting Celery beat"
launch beat "exec bash '${ROOT_DIR}/scripts/dev_beat.sh'"

# 7. Frontend (production build with public API URL baked in)
log "rebuilding frontend with NEXT_PUBLIC_API_BASE_URL=${FRONTEND_PUBLIC_API}"
( cd frontend && rm -rf .next && NEXT_PUBLIC_API_BASE_URL="${FRONTEND_PUBLIC_API}" npm run build > "${LOG_DIR}/frontend_build.log" 2>&1 )

log "starting frontend"
launch frontend "cd '${ROOT_DIR}/frontend' && exec npx next start -H 127.0.0.1 -p 3001"

# 8. Cloudflare tunnel
log "starting cloudflare tunnel (${TUNNEL_NAME})"
launch cloudflared "exec cloudflared tunnel --config '${TUNNEL_CFG}' run '${TUNNEL_NAME}'"

# 9. Health checks (local first, then public)
log "waiting for services to become healthy"
sleep 6
ok=true

curl -sS -o /dev/null -w "local backend  /health  %{http_code}\n" http://127.0.0.1:8000/health || ok=false
curl -sS -o /dev/null -w "local frontend /        %{http_code}\n" http://127.0.0.1:3001/ || ok=false
curl -sS -o /dev/null -w "public backend /health  %{http_code}\n" https://cognitive-api.doctormanzur.com/health || ok=false
curl -sS -o /dev/null -w "public frontend /       %{http_code}\n" https://cognitive.doctormanzur.com/ || ok=false

echo ""
log "URLs:"
echo "  Frontend: https://cognitive.doctormanzur.com"
echo "  Backend:  https://cognitive-api.doctormanzur.com"
echo ""
log "Logs:"
echo "  tail -f ${LOG_DIR}/backend.log"
echo "  tail -f ${LOG_DIR}/frontend.log"
echo "  tail -f ${LOG_DIR}/cloudflared.log"

if $ok; then
  log "STACK UP"
else
  log "WARNING: at least one health probe failed; inspect logs above"
fi

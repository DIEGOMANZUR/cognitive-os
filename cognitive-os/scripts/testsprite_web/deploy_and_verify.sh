#!/usr/bin/env bash
# One-shot deploy + verify for TestSprite re-runs.
#
# What this script does, in order:
#   1. Stops the previous stack cleanly (idempotent).
#   2. Brings the full stack back up via start_testsprite_stack.sh
#      (re-builds the Next.js bundle so the latest commits land in
#      production, then exposes localhost via the Cloudflare tunnel).
#   3. Waits for the public endpoint to actually answer 200.
#   4. Verifies the deployed bundle carries the responsive-boot script
#      and the cache-bust marker introduced by the latest commit.
#   5. Prints the exact rerun checklist the operator needs.
#
# Re-runnable: if anything fails it prints what to inspect and exits
# with the failing component's status so a retry can be scripted.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs/testsprite_web"

PUBLIC_FRONTEND="https://cognitive.doctormanzur.com"
PUBLIC_BACKEND="https://cognitive-api.doctormanzur.com"
CACHE_MARKER="cogos-v2026-05-26e-status-cards"

# --- pretty output helpers -------------------------------------------------
say() { printf "\n\033[1;36m▸ %s\033[0m\n" "$*"; }
ok()  { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
warn(){ printf "  \033[1;33m⚠\033[0m %s\n" "$*"; }
err() { printf "  \033[1;31m✗\033[0m %s\n" "$*"; }

# --- 1. stop previous stack -------------------------------------------------
say "1/5 · Parando stack anterior (si existe)"
if bash "${ROOT_DIR}/scripts/testsprite_web/stop_testsprite_stack.sh" >>"${LOG_DIR}/deploy_and_verify.log" 2>&1; then
  ok "stop_testsprite_stack.sh OK"
else
  warn "stop_testsprite_stack.sh reportó error — continúo (puede ser que no haya nada corriendo)"
fi

# --- 2. start fresh stack ---------------------------------------------------
say "2/5 · Levantando stack nuevo (rebuild frontend con commits actuales)"
if ! bash "${ROOT_DIR}/scripts/testsprite_web/start_testsprite_stack.sh" 2>&1 | tee -a "${LOG_DIR}/deploy_and_verify.log"; then
  err "start_testsprite_stack.sh devolvió error"
  err "Revisá: tail -100 ${LOG_DIR}/deploy_and_verify.log"
  exit 2
fi
ok "start_testsprite_stack.sh terminó"

# --- 3. wait for public endpoint -------------------------------------------
say "3/5 · Esperando a que ${PUBLIC_FRONTEND} responda 200"
ready=false
for attempt in $(seq 1 30); do
  http_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "${PUBLIC_FRONTEND}/" || echo "000")"
  if [ "${http_code}" = "200" ]; then
    ok "frontend público respondió 200 (intento ${attempt})"
    ready=true
    break
  fi
  printf "    intento %d/30 → HTTP %s\n" "${attempt}" "${http_code}"
  sleep 2
done
if ! $ready; then
  err "frontend público no respondió 200 después de 60s"
  err "Revisá:"
  err "  tail -100 ${LOG_DIR}/frontend.log"
  err "  tail -100 ${LOG_DIR}/cloudflared.log"
  exit 3
fi

backend_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "${PUBLIC_BACKEND}/health" || echo "000")"
if [ "${backend_code}" = "200" ]; then
  ok "backend público /health respondió 200"
else
  warn "backend público /health respondió ${backend_code} (TestSprite solo necesita el frontend, pero igual conviene chequear)"
fi

# --- 4. verify deployed bundle is the current build ------------------------
say "4/5 · Verificando que el bundle desplegado es el commit actual"

# Service worker bump is bumped on every commit that ships fixes, so
# finding the current marker in /sw.js proves Cloudflare and Next.js
# are serving the build that left our local machine — not a stale
# CDN copy or a pre-rebuild bundle.
sw_text="$(curl -sS --max-time 10 "${PUBLIC_FRONTEND}/sw.js" || true)"
if printf '%s' "${sw_text}" | grep -q "${CACHE_MARKER}"; then
  ok "service worker incluye el cache-bust marker (${CACHE_MARKER})"
else
  err "no encontré el marker ${CACHE_MARKER} en sw.js — el bundle desplegado es viejo"
  err "Verificá que el build terminó OK: tail -100 ${LOG_DIR}/frontend_build.log"
  err "Si el frontend build fue OK, esperá 1-2 min para que Cloudflare invalide el cache."
  exit 4
fi

# Sanity check: the data-cogos-active-tab attribute is always present on
# <main> after hydration, so its presence in the SSR markup means we are
# at least serving the cockpit SPA shell and not a stub page.
homepage_html="$(curl -sS --max-time 10 "${PUBLIC_FRONTEND}/" || true)"
if printf '%s' "${homepage_html}" | grep -q "data-cogos-active-tab"; then
  ok "cockpit SPA shell servida en la raíz"
else
  err "el HTML servido no incluye la cockpit shell (data-cogos-active-tab ausente)"
  exit 4
fi

# --- 5. print operator handoff ---------------------------------------------
say "5/5 · LISTO para re-correr TestSprite"
cat <<'EOF'

╔══════════════════════════════════════════════════════════════════════════════╗
║  STACK DESPLEGADO Y VERIFICADO                                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Lo que tenés que hacer ahora — UN SOLO PASO HUMANO:                         ║
║                                                                              ║
║  1) Abrí el portal web de TestSprite donde corriste la prueba anterior.      ║
║  2) Buscá la corrida del último PDF (la de 20.21hrs).                        ║
║  3) Apretá el botón "Rerun".                                                 ║
║  4) NO toques el PRD ni las instructions — mismo setup que antes.            ║
║  5) Esperá a que termine y pasame el PDF nuevo.                              ║
║                                                                              ║
║  Verificación visual opcional (si querés):                                   ║
║    https://cognitive.doctormanzur.com/  en pestaña INCÓGNITA                 ║
║    Chrome/Edge → Ctrl+Shift+N                                                ║
║    Firefox     → Ctrl+Shift+P                                                ║
║                                                                              ║
║  Esperás ver:                                                                ║
║    • Shell oscuro con sidebar a la izquierda                                 ║
║    • Hotkey "3" enfoca DeepAgents                                            ║
║    • Ctrl+K abre la paleta y "Ir a Chat" la deja abierta para tipear         ║
║    • Achicar la ventana abajo de 920px colapsa el sidebar y muestra          ║
║      la barra inferior móvil                                                 ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Logs en vivo si querés observar:
  tail -f /home/jgonz/Escritorio/PROYECTO\ COGNITIVE\ OS/cognitive-os/logs/testsprite_web/frontend.log

EOF

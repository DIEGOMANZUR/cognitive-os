#!/usr/bin/env bash
# Carril de smokes LIVE read-only (AUDIT-2026-E).
#
# A diferencia de `full-qa.sh` (hermético, nunca toca un API real), esto dialoga
# con los proveedores externos reales en modo SOLO LECTURA: un completion LLM
# mínimo, GET de dominios GoDaddy, login IMAP + EHLO SMTP, getMe de Telegram,
# ping del WebBridge y list_tools de MCP. Nunca envía, escribe ni modifica nada.
#
# Es OPT-IN deliberado: requiere LIVE_TESTS_ENABLED=1. Cada test se auto-saltea
# si su credencial/feature no está configurada, así que es seguro correrlo
# aunque falten proveedores. Coste estimado: ~US$0.001 (solo el ping LLM).
#
# Uso:
#   bash scripts/full-qa-live.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
export LIVE_TESTS_ENABLED=1
echo "== Live read-only smokes (LIVE_TESTS_ENABLED=1) =="
uv run pytest -m live_readonly tests/live -v
echo "OK: full-qa-live"

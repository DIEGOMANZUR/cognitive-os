#!/usr/bin/env bash
# Wrapper para arrancar el MCP de Exa.
# La credencial debe venir de .env.local / entorno. No guardar claves aqui.
set -euo pipefail

EXA_API_KEY="${EXA_API_KEY:-}"

if [[ -z "${EXA_API_KEY}" ]]; then
  printf 'EXA_API_KEY is required for Exa MCP\n' >&2
  exit 1
fi

tools="web_search_exa,web_search_advanced_exa,web_fetch_exa"
exec npx -y mcp-remote "https://mcp.exa.ai/mcp?exaApiKey=${EXA_API_KEY}&tools=${tools}"

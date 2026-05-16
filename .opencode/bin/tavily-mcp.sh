#!/usr/bin/env bash
# Wrapper para arrancar el MCP de Tavily.
# La credencial debe venir de .env.local / entorno. No guardar claves aqui.
set -euo pipefail

TAVILY_API_KEY="${TAVILY_API_KEY:-}"

if [[ -z "${TAVILY_API_KEY}" ]]; then
  printf 'TAVILY_API_KEY is required for Tavily MCP\n' >&2
  exit 1
fi

exec npx -y mcp-remote "https://mcp.tavily.com/mcp/?tavilyApiKey=${TAVILY_API_KEY}"

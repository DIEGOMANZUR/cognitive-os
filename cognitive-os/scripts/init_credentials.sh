#!/usr/bin/env bash
# init_credentials.sh — wizard de bootstrap de credenciales operador.
#
# Comportamiento:
#  1) Asegura que `.env` exista (delega en init_env.sh la primera vez).
#  2) Consulta `/system/credentials-status` si el API local responde, o cae a
#     llamada directa a `build_credentials_status()` vía Python si no.
#  3) Imprime checklist con tres columnas: nombre, configurada (✓/✗), cómo
#     obtenerla. Termina con resumen y exit code != 0 si quedan credenciales
#     requeridas pendientes.
#  4) Nunca muestra valores; sólo booleans + how_to_obtain.
#
# Uso:
#   bash scripts/init_credentials.sh [--ci]
#
# Flags:
#   --ci  →  exit 1 si quedan credenciales requeridas o si el JWT no se puede
#            generar (modo apto para CI/CD). Sin la flag el script siempre
#            imprime el reporte y retorna 0 cuando "nada bloqueante" falta.

set -uo pipefail

CI_MODE=0
for arg in "$@"; do
    case "$arg" in
        --ci) CI_MODE=1 ;;
        -h|--help)
            sed -n '1,30p' "$0"
            exit 0
            ;;
        *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
    esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
ENV_FILE="${ROOT_DIR}/.env"

if [[ -t 1 ]]; then
    C_OK="\033[32m"; C_WARN="\033[33m"; C_ERR="\033[31m"; C_DIM="\033[90m"
    C_BOLD="\033[1m"; C_END="\033[0m"
else
    C_OK=""; C_WARN=""; C_ERR=""; C_DIM=""; C_BOLD=""; C_END=""
fi
printf "${C_BOLD}=== Cognitive OS · wizard de credenciales ===${C_END}\n"
printf "${C_DIM}Reporta qué credenciales están configuradas y cuáles faltan, con\nlas instrucciones exactas. No imprime valores.${C_END}\n\n"

# 1) .env existe (init_env.sh lo crea con secretos locales: JWT, DB, etc.)
if [[ ! -f "${ENV_FILE}" ]]; then
    printf "${C_WARN}⚠ %s no existe — ejecutando scripts/init_env.sh primero.${C_END}\n" "${ENV_FILE}"
    bash "${ROOT_DIR}/scripts/init_env.sh" || {
        printf "${C_ERR}✗ init_env.sh falló. Revisá el output y reintentá.${C_END}\n"
        exit 1
    }
fi

# 2) Obtener el status. Camino preferido: API viva. Fallback: invocar build_status
#    en Python directamente (no necesita Postgres).
report_json=""
if curl -fs --max-time 2 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    token=$(cd "${BACKEND_DIR}" && uv run python -c "from cognitive_os.core.auth import create_access_token; print(create_access_token(user_id='wizard', roles=['admin']))" 2>/dev/null || true)
    if [[ -n "$token" ]]; then
        report_json=$(curl -fs -H "Authorization: Bearer ${token}" \
            http://127.0.0.1:8000/system/credentials-status 2>/dev/null || true)
    fi
fi

if [[ -z "$report_json" ]]; then
    printf "${C_DIM}(API local no disponible — consulto el inventario inline.)${C_END}\n"
    report_json=$(cd "${BACKEND_DIR}" && uv run python -c "
import json
from cognitive_os.core.credentials_inventory import build_status
print(build_status().model_dump_json())
" 2>/dev/null) || {
        printf "${C_ERR}✗ No pude obtener el inventario. Verificá que 'uv sync' haya completado.${C_END}\n"
        exit 1
    }
fi

# 3) Imprimir checklist. Usamos jq cuando está disponible; si no, fallback a
#    Python embebido para no añadir más dependencias forzadas.
parse_with_python() {
    python3 - "$report_json" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
for it in data["items"]:
    mark = "OK " if it["configured"] else ("REQ" if not it["optional"] else "OPT")
    print(f"{mark}\t{it['name']}\t{it['enables']}\t{it['how_to_obtain']}")
print(f"__SUMMARY__\t{data['total']}\t{data['configured']}\t{data['missing_required']}")
PY
}

if command -v jq >/dev/null 2>&1; then
    parsed=$(echo "$report_json" | jq -r '
        (.items[] | [
            (if .configured then "OK" else (if .optional then "OPT" else "REQ" end) end),
            .name, .enables, .how_to_obtain
        ] | @tsv),
        "__SUMMARY__\t\(.total)\t\(.configured)\t\(.missing_required)"
    ')
else
    parsed=$(parse_with_python)
fi

printf "${C_BOLD}%-6s %-44s %s${C_END}\n" "ESTADO" "CREDENCIAL" "QUÉ HABILITA"
printf "${C_DIM}%-6s %-44s %s${C_END}\n" "──────" "──────────────" "─────────────"
missing_required=0
missing_optional=0
while IFS=$'\t' read -r status name enables howto; do
    if [[ "$status" == "__SUMMARY__" ]]; then
        # status name=total, enables=configured, howto=missing_required
        total="$name"; configured="$enables"; missing_required="$howto"
        continue
    fi
    case "$status" in
        OK)   color="${C_OK}";  symbol="✓" ;;
        REQ)  color="${C_ERR}"; symbol="✗" ;;
        OPT)  color="${C_WARN}"; symbol="○" ;;
        *)    color="";          symbol="?" ;;
    esac
    [[ "$status" == "OPT" ]] && ((missing_optional+=1))
    printf "${color}%-2s %-3s${C_END} %-44s %s\n" "$symbol" "$status" "$name" "$enables"
    if [[ "$status" != "OK" ]]; then
        printf "       ${C_DIM}→ %s${C_END}\n" "$howto"
    fi
done <<< "$parsed"

printf "\n${C_BOLD}Resumen:${C_END} ${total:-?} total · ${configured:-?} configuradas · "
if (( missing_required > 0 )); then
    printf "${C_ERR}%d requeridas faltantes${C_END}" "$missing_required"
else
    printf "${C_OK}0 requeridas faltantes${C_END}"
fi
if (( missing_optional > 0 )); then
    printf " · ${C_WARN}%d opcionales por completar${C_END}\n" "$missing_optional"
else
    printf " · ${C_OK}todas las opcionales configuradas${C_END}\n"
fi

if (( missing_required > 0 )); then
    printf "\n${C_WARN}Las credenciales REQ son bloqueantes para grado comercial.${C_END}\n"
    printf "${C_DIM}Completalas en .env (o en el sistema externo indicado) y volvé a correr este wizard.${C_END}\n"
    if (( CI_MODE == 1 )); then
        exit 1
    fi
fi

if (( missing_required == 0 )) && (( missing_optional > 0 )); then
    printf "\n${C_DIM}Las credenciales OPT habilitan integraciones específicas (Google, mail, voz, web search). Completá las que vas a usar; el resto puede quedar pendiente.${C_END}\n"
fi

exit 0

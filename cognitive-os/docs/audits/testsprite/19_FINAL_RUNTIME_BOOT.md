# 19 - Final Runtime Boot

Fecha local: 2026-05-24T20:32:41-04:00

## Secuencia ejecutada

1. `/home/jgonz/Escritorio/cognitive-os.sh stop`
2. `bash scripts/dev_down.sh`
3. Verificacion de puertos antiguos: 8000, 3001, 5432, 6379, 8081, 50052,
   7475, 7688 sin listeners.
4. `bash scripts/dev_up.sh`
5. `cd backend && uv run alembic upgrade head`
6. `cd backend && uv run alembic check`
7. `/home/jgonz/Escritorio/cognitive-os.sh start`

## Resultado de arranque

| Componente | Estado | Evidencia |
|---|---|---|
| Docker infra | running | `dev_up.sh` + `wait_for_services.sh`: all services healthy |
| Alembic upgrade | PASS | sin migraciones pendientes |
| Alembic check | PASS | `No new upgrade operations detected` |
| API | running | pid launcher `1786075`, listener python `1786087`, `127.0.0.1:8000` |
| Celery worker | running | pid `1786348`, colas `default,ingestion,agent_longrun,maintenance,mail` |
| Celery beat | running | pid `1786363` |
| Frontend | running | pid `1786392`, `127.0.0.1:3001` |
| Telegram | running | pid `1786485` |
| Kimi WebBridge | running | pid `1786630`, `127.0.0.1:10086`, extension connected |
| Edge DevTools | running | `127.0.0.1:9222` |

## Verificaciones HTTP

JWT temporal guardado localmente en `/tmp/cognitive_os_final_release_jwt.txt`
con permisos `600`. No se imprime el token en reportes.

| Check | Resultado |
|---|---|
| `GET /health` | 200 `{"status":"ok","service":"cognitive-os"}` |
| `GET /system/info` | 200, `operator_profile=dedicated_local`, git `5459ec5a7382` |
| `GET /system/readiness` | 200, `Sin fricción. Todas las capacidades del perfil están activas.`, 14/14, gaps 0 |
| `GET /health/dashboard` | 200, 18 componentes, overall `configured`, sin degraded |
| `POST /health/verify` | 200, 18 componentes, overall `configured`; `mcp_client` queda `configured` con instruccion de live status en `/system/mcp` |
| `GET /system/mcp` | 200, 5/5 connected, 67 tools (`mem`, `gh`, `fs`, `cc`, `gem`) |
| `GET /openapi.json` | 200, OpenAPI 3.1.0, 143 paths |
| `HEAD frontend /` | 200 |

## Perfil operativo

Validado por runtime:

- `OPERATOR_PROFILE=dedicated_local`
- `/system/readiness.local_autonomy_mode=full`
- `CODE_DIRECTOR_BUDGET_MODE=soft` presente en `.env`
- Mail send deshabilitado y approval requerida.
- GoDaddy DNS dry-run forzado.
- MCP habilitado y conectado.
- Kimi/Edge operativo.

## Errores y fixes durante boot

Incidencia no producto:

- Primer script de resumen HTTP fallo por sintaxis Node 22 al mezclar
  `require()` con top-level `await`. Se corrigio envolviendo el bloque en una
  IIFE async y se repitio la verificacion completa con PASS.

No se aplicaron fixes de producto en esta fase.

## Lectura del estado

El runtime quedo levantado desde cero y es apto para ejecutar gates oficiales,
TestSprite y flujos criticos. Health es honesto: el estado `configured` no se
declara `ok` cuando hay componentes configurados pero no verificados por diseño.

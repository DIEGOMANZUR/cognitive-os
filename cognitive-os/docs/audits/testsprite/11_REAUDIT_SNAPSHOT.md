# 11 · Re-Audit Snapshot — 2026-05-23 05:04 UTC-4 (Chile)

## Fecha/hora

`sáb 23 may 2026 05:04:35 -04`

## Git

- Branch: `codex/commercial-zero-friction-hardening`
- Commit (HEAD): `9b22f771edf3cb4df8e55953721633fb44a69032`
- `git status --short`:

  ```
   M cognitive-os/docs/qa/RUNBOOK.md
   M cognitive-os/frontend/playwright.config.ts
   M cognitive-os/frontend/tests/e2e/_helpers.ts
  ?? cognitive-os/docs/audits/testsprite/
  ?? cognitive-os/frontend/tests/e2e/_global-setup.ts
  ?? cognitive-os/test-results/
  ```

  Cambios pertenecen a la primera pasada (auto-mint JWT + RUNBOOK +
  10 docs nuevos). No hay residuos de QA en tracking.

## Versiones

- Python 3.12.3
- uv 0.11.6
- Node v22.22.0
- npm 10.9.4
- Docker 29.5.2

## Puertos LISTEN (todos `127.0.0.1`, ningún bind público)

```
3001  next-server (v16.2.6)   pid 1507145
8000  uvicorn / FastAPI       pid 1506984
5432  postgres (docker)
6379  redis (docker)
7475  neo4j HTTP (docker)
7688  neo4j Bolt (docker)
8081  weaviate HTTP (docker)
50052 weaviate gRPC (docker)
10086 kimi-webbridge          pid 1507551
```

## Procesos activos

```
uvicorn ............ 1506978 / 1506984
celery worker ...... 1507107 (queues: default,ingestion,agent_longrun,maintenance,mail)
celery beat ........ 1507123
next-server ........ 1507145
telegram_bot ....... 1507328 / 1507354
kimi-webbridge ..... 1507551 (Node) + 1075410 (MCP bridge)
```

## TestSprite MCP

- Cliente CLI: `@testsprite/testsprite-mcp` instalado vía npx.
- Config: `~/.config/@testsprite/testsprite-mcp-nodejs/config.json` (apiKey
  presente).
- Project config: `cognitive-os/testsprite_tests/tmp/config.json`.
- Plan: `cognitive-os/testsprite_tests/testsprite_frontend_test_plan.json`
  (28 TC generados en la primera pasada).
- Cuenta: Diego Manzur, Starter, **520 - N credits** (consumidos algunos
  en primera pasada).

## URLs

- Frontend: `http://localhost:3001` (HTTP/1.1 200)
- Backend: `http://127.0.0.1:8000` (`/health` 200)
- OpenAPI: `http://127.0.0.1:8000/docs` (Swagger UI)
- Kimi: `http://127.0.0.1:10086`

## Perfil operativo detectado (vivo)

```
operator_profile = dedicated_local
local_autonomy_mode = full        (de /system/readiness)
git_commit = 9b22f771edf3         (HEAD ✓)
alembic_head = 202605200003
approval_require_four_eyes = false
require_human_approval_for_external_actions = false
action_payload_encryption_required = false
target_capabilities_unlocked = 14/14
gaps = []
summary = "Sin friccion. Todas las capacidades del perfil estan activas."
```

## Variables clave de `.env` (redacted)

```
OPERATOR_PROFILE=dedicated_local        ✓
TELEGRAM_ENABLED=true                   ✓
ENABLE_EMAIL_SEND=false                 ✓ (no auto-send)
MAIL_REQUIRE_APPROVAL_FOR_SEND=true     ✓
KIMI_WEBBRIDGE_URL=http://127.0.0.1:10086
KIMI_WEBBRIDGE_REQUIRE_APPROVAL=true    ✓ (mutaciones bajo approval)
KIMI_WEBBRIDGE_ALLOW_MUTATIONS=false    ✓
KIMI_WEBBRIDGE_ALLOWED_DOMAINS=*        ✓ (local-permissive)
KIMI_WEBBRIDGE_REQUEST_TIMEOUT_SECONDS=20
GODADDY_DNS_DRY_RUN_ONLY=true           ✓ (DNS dry-run forzado)
ENABLE_MCP_CLIENT=true                  ✓
LIVE_TESTS_ENABLED=<no presente>        → live tests opt-out
MAIL_ALLOW_EXPLICIT_SEND=<no presente>  → escape hatch cerrado
```

## Confirmaciones rápidas

| Pregunta | Respuesta |
|---|---|
| ¿`dedicated_local/full` activo? | **SÍ** (`operator_profile=dedicated_local`, readiness reporta `local_autonomy_mode=full`) |
| ¿Kimi WebBridge disponible? | **SÍ** (puerto 10086 listen, status `ready` en health) |
| ¿Telegram habilitado? | **SÍ** (`TELEGRAM_ENABLED=true`, proceso vivo) |
| ¿Live tests habilitados? | **NO** (no en `.env`, no se ejecutarán por defecto) |
| ¿Mail send bloqueado? | **SÍ** (`ENABLE_EMAIL_SEND=false`, `MAIL_ALLOW_EXPLICIT_SEND` ausente, escape hatch necesita 3 flags simultáneas + frase) |
| ¿MCP funcionando? | **SÍ** (5/5 servers conectados, 67 tools totales) |
| ¿Health honesto? | **SÍ** (overall=`configured`, no `ok`, porque LLM/embeddings/mail/mcp_client sólo cableados sin probe live) |
| ¿Backlog operacional sano? | **SÍ** (componente `operational_backlog: ok`) |

## No se requiere restart

El runtime ya carga HEAD `9b22f77` (validado en `/system/info`); los
puertos están limpios (sin acumulación de CLOSE-WAIT como tras TestSprite
de la primera pasada). Procedo con gates sin tocar procesos vivos.

# 01 · Discovery Map — Cognitive OS

Fecha: 2026-05-23
Branch / HEAD: `codex/commercial-zero-friction-hardening` @ `9b22f77`
Runtime live binary (`/system/info.git_commit`): `2c3cff6` (3 commits atrás
de HEAD — solo cambios de docs + `core/config.py` + `mcp_client.py` +
`hooks.ts`; ver §10).

Conteos confirmados vivos con `scripts/sync_doc_counts.py --check` (OK):

| Conteo | Valor |
|---|---|
| Endpoints REST (`@app.*` en `api/app.py`) | **147** |
| Tareas Celery (`workers/tasks.py`) | **23** |
| Colas Celery | **5** (`default`, `ingestion`, `agent_longrun`, `maintenance`, `mail`) |
| Beat schedule entries | **13** (10 condicionales por flags + 3 reapers siempre activos) |
| Migraciones Alembic | **20** (head `202605200003`) |
| Vistas frontend | **20** |
| Slash commands Telegram | **37** (verificado en `tests/test_telegram_bot.py::ALL_TELEGRAM_COMMANDS`) |
| Componentes `/health/dashboard` | **18** (verificado vivo) |
| MCP servers configurados | **5** (verificado vivo, 67 tools totales) |

## 1. Endpoints FastAPI

Archivo: `backend/src/cognitive_os/api/app.py` — **147 decoradores REST**.

Familias principales:

- `/health`, `/health/dashboard`, `/health/verify`
- `/auth/local-token`
- `/system/info`, `/system/readiness`, `/system/mcp`, `/system/credentials-status`
- `/chat`, `/threads/*`
- `/documents/*`, `/document-analysis/*`
- `/jobs/*`
- `/approvals/*`
- `/actions/*` (browser, computer, document, gmail, mail, maps, calendar,
  drive, godaddy, kimi, workflow, requests)
- `/research/*`
- `/code-director/*`
- `/mail/*`
- `/deepagents/*`
- `/sandbox/*`

## 2. Tareas Celery (`workers/tasks.py`)

23 tareas; routing en `workers/celery_app.py::task_routes`. Por cola:

- **default**: `debug_fast`
- **ingestion**: `ingest_pdf`
- **agent_longrun**: deepagent research, document analysis, code build,
  failure post-mortem scanner, nightly reflection, skill promoter, recipe
  extractor
- **maintenance**: health_check, cleanup_old_jobs, consolidate deepagent memory,
  3 reapers (action_request, approval, stale_jobs), tool scorecard aggregator,
  personal assistant reminders
- **mail**: `sync_personal_mail`, `build_personal_mail_digest`,
  `telegram_gmail_digest`

## 3. Beat schedule (`celery_app.py::beat_schedule`)

Reapers siempre activos:

- `action-request-reaper`
- `approval-reaper`
- `stale-jobs-reaper`

Jobs condicionales por feature flag:

- `consolidate-deepagent-memory-all`
- `failure-postmortem-scanner`
- `nightly-reflection`
- `personal-assistant-reminders`
- `personal-mail-digest` (10:00 y 20:00 Chile)
- `personal-mail-sync`
- `recipe-extractor`
- `skill-promoter`
- `telegram-gmail-digest`
- `tool-scorecard-aggregator`

## 4. Migraciones Alembic

20 archivos en `backend/alembic/versions/`; head `202605200003`. Recientes
relevantes:

- `202605170001` — añade `drive_ensure_folder`/`drive_organize_files` al
  CHECK `ck_ar_action_type` (corrige bug de Fase 65).
- `202605200001` — `jobs.extracted_recipe_at`.
- `202605200002` — `tool_invocation_metrics`.
- `202605200003` — `procedure_invocation_log` (Fase B, F80).

`alembic check` corre en `full-qa.sh` y debe quedar verde.

## 5. Vistas frontend (`frontend/app/views/`)

20 archivos `*View.tsx`:

```
Agents · Approvals · Assist · Audit · Chat · CodeDirector · Configuration ·
Dashboard · DocumentAnalysis · Documents · GoogleOps · Health · Jobs ·
LangSmith · MailInbox · Memory · Research · Sandbox · Settings · Skills
```

SPA con un único route segment (`app/page.tsx`); tab activo en
`localStorage["cogos.tab"]`.

## 6. Hooks y utilidades frontend críticas

- `usePolledFetch` — pausa offline/hidden, reintento al volver.
- `useKeyboard` (registrado en capture phase para `Ctrl/Cmd+K`).
- `asArray<T>` — defensa contra payloads no-iterables.
- `<Icon name=… />` — iconos estructurales.
- `StatePrimitives` — skeleton/empty/error.
- `useFocusTrap` — modales.

## 7. Tests existentes

- Backend: **123 archivos** `test_*.py` en `backend/tests/`.
- Carril live: 8 smokes en `backend/tests/live/` (opt-in
  `LIVE_TESTS_ENABLED=1`).
- Playwright: **20 spec files** en `frontend/tests/e2e/` (suite oficial:
  31 tests passed).

## 8. Scripts oficiales

Operacionales:

- `init_env.sh`, `init_credentials.sh`, `dev_up.sh`, `dev_down.sh`,
  `dev_worker.sh`, `dev_beat.sh`, `dev_flower.sh`, `dev_logs.sh`,
  `dev_telegram.sh`.

QA gates:

- `full-qa.sh` (gate principal — backend + frontend `.next-qa` aislado).
- `full-e2e.sh` (Playwright separado).
- `stress-qa.sh` (loop N veces para detectar flakiness).
- `full-qa-live.sh` (opt-in, read-only).
- `verify_desktop_launchers.sh`.
- `sync_doc_counts.py --check`.

Sandbox/OpenShell: `openshell_setup`, `openshell_start_gateway`,
`openshell_stop_gateway`, `openshell_status`, `openshell_run_smoke.py`.

Backups: `backup_all.sh`, `backup_postgres.sh`, `backup_neo4j.sh`,
`backup_storage.sh`, `restore_*.sh`.

## 9. Comandos Telegram (37)

Lista canónica en `backend/tests/test_telegram_bot.py::ALL_TELEGRAM_COMMANDS`,
verificada contra `telegram_bot.COMMAND_HANDLERS`:

```
agents · approvals · approve · audit · calendar · cancel · capabilities ·
chat · codebuild · config · consolidate · documents · done · drive ·
freebusy · gmaildigest · health · help · ingest · job · jobs · mail · maps ·
memory · note · notes · reject · research · reset · runs · sandbox ·
skills · start · stats · task · tasks · threads
```

Test matrix existente cubre auth-deny + no-crash + flag-gated por
parametrización (~78 tests).

## 10. Variables de entorno relevantes (`.env` real verificado)

Setting | Valor actual | Esperado (zero-friction)
---|---|---
`OPERATOR_PROFILE` | `dedicated_local` | `dedicated_local` ✅
`LOCAL_AUTONOMY_MODE` | (default = `full`) | `full` ✅ (readiness reporta `full`)
`CODE_DIRECTOR_BUDGET_MODE` | (default = `soft`) | `soft` ✅
`TELEGRAM_ENABLED` | `true` | habilitado ✅
`KIMI_WEBBRIDGE_REQUIRE_APPROVAL` | `true` | sigue requiriendo approval para mutaciones ✅
`KIMI_WEBBRIDGE_ALLOWED_DOMAINS` | `*` | `*` permitido en local ✅
`GODADDY_DNS_DRY_RUN_ONLY` | `true` | dry-run forzado ✅
`ENABLE_MCP_CLIENT` | `true` | MCP habilitado ✅
`MAIL_ALLOW_EXPLICIT_SEND` | (no presente → default `false`) | `false` ✅ (mail no envía en flujo normal)
`MAIL_BACKGROUND_SYNC_ENABLED` | (no presente → default `false`) | `false` ✅
`MAIL_REQUIRE_APPROVAL_FOR_SEND` | `true` | ✅

Conclusión: `.env` está alineado con `ZERO_FRICTION_OPERATING_MODEL.md`.

## 11. Runtime vivo vs HEAD (riesgo de drift)

- HEAD: `9b22f77` (`docs: sync current commercial state`).
- Backend running (`/system/info.git_commit`): `2c3cff6` (3 commits atrás).
- Delta de **código** (no docs) entre `2c3cff6` y `9b22f77`:
  - `backend/src/cognitive_os/core/config.py` — default
    `MCP_INVENTORY_TIMEOUT_SECONDS=30` (subió de 10 → 30 en `5953b40`).
  - `backend/src/cognitive_os/integrations/mcp_client.py` — inventario MCP
    paralelo.
  - `backend/tests/test_config.py`, `backend/tests/test_mcp_client.py` —
    cobertura.
  - `frontend/app/lib/hooks.ts` — `useKeyboard` capture phase.

**Riesgo:** los tests TestSprite/Playwright/pytest deben correr contra el
código de HEAD, no contra el binario en memoria. Para gates pytest no es un
problema (corren contra el código del filesystem). Para Playwright contra el
runtime vivo, debería verificarse que el frontend cuelgue del build más
reciente (lo está, dado el `next-server (v16.2.6)` se reinició dentro de la
ventana del fix). Para TestSprite contra `:3001`, el inventario MCP del
binario backend antiguo está OK porque el efecto observable (5/5 servers, 67
tools) ya funciona — el cambio fue de performance, no de superficie.

Verificación rápida en runtime:

```
GET /system/mcp → enabled=true, 5 servers (mem/gh/fs/cc/gem), 67 tools.
GET /system/readiness → ready: zero gaps, 14/14 capacidades activas.
GET /health/dashboard → status=configured (LLM/embeddings/mail/mcp_client
solo `configured`; resto `ok`/`ready`).
```

## 12. Stack vivo confirmado (a 2026-05-23 04:00 UTC)

Procesos:

- `uvicorn` → 127.0.0.1:8000
- `next-server (v16.2.6)` → 127.0.0.1:3001
- Celery worker (5 colas)
- Celery beat
- Telegram bot
- Docker compose: `cognitive_os_postgres` (5432), `cognitive_os_redis` (6379),
  `cognitive_os_weaviate` (8081 / 50052), `cognitive_os_neo4j` (7475/7688)

Otros contenedores Docker irrelevantes: `LibreChat`, `rag_api`,
`agente_neo4j`, `agente_weaviate`, `vectordb`, `chat-mongodb`,
`chat-meilisearch`. No interfieren porque Cognitive OS lockea sus puertos en
`127.0.0.1:5432/6379/7475/7688/8081`.

## 13. Lista "NO RESTRINGIR SIN MOTIVO" (en este host)

Capacidades amplias en `dedicated_local/full` que **NO** debe restringirse
salvo razón documentada en `findings`:

- Filesystem local (`/home/jgonz` o equivalente) para el agente.
- Edge real / Kimi WebBridge (mutaciones solo si
  `KIMI_WEBBRIDGE_ALLOW_MUTATIONS=true`).
- Telegram conversacional sin `/`.
- Auto-resolución de approvals internas pre-validadas.
- Command palette `Ctrl/Cmd+K` desde cualquier foco.
- Bypass de four-eyes en `dedicated_local/full`
  (`APPROVAL_REQUIRE_FOUR_EYES=false`).
- Aprobaciones de Code Director con budget soft, no por subproceso.
- JWT local long-lived (10 años, `/auth/local-token`).
- Acceso amplio MCP (memoria, GitHub, fs, cc, gem).

## 14. Huecos de cobertura conocidos (entrada al plan)

- TestSprite MCP tuvo solo smoke advisory 3/3 en gate previo; corresponde
  ampliar matriz en fase 6/7.
- `/health/dashboard` `overall=configured` con LLM/embeddings/mail/mcp_client
  en `configured` (cableado, no probado). El operador puede pulsar
  "Verificar en vivo" → `/health/verify` (es contrato, no bug).
- Sin smoke E2E de `/action-requests` dispatch concurrente desde UI (cubierto
  por backend `jobs-approvals-action-lifecycle.spec.ts` + tests Python).
- Sin smoke TestSprite para Telegram (matriz pytest sí existe).

## 15. Riesgos funcionales priorizados (a confirmar en Fase 9)

1. Runtime vivo a 3 commits atrás de HEAD → reiniciar antes de cierre.
2. MCP gem/cc connection a confirmar con tools (cc=1 tool, gem=6 — fueron 6
   y 3 en algunos snapshots; no es bug, depende de tools expuestas por servidor).
3. Drift documental: `docs/qa/MAP.md`/`FINAL_AUDIT_REPORT.md` mencionan
   "17 componentes" en párrafos históricos; el snapshot vivo dice 18.
4. Mail real: `MAIL_GODADDY_PASSWORD` en `.env` plaintext es decisión
   documentada del operador ("hardcode credentials" memory) — no es
   hallazgo de seguridad para este host.

## 16. Siguientes pasos

→ Fase 2: confirmar TestSprite MCP operativo y plan.
→ Fase 5: correr `full-qa.sh`, Playwright y stress como baseline.
→ Fase 6: master test plan basado en este inventario.

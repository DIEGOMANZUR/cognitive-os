# Scripts

> **Estado actual (2026-05-25 post-activación funcional, base `0f8232a` —
> APTO COMERCIAL LOCAL-FIRST · FUNCTIONAL WITH WARNINGS):** scripts shell verificados para la
> instalación local dedicada. La operación normal prioriza fricción casi
> nula: los launchers de escritorio levantan Docker, API, worker, beat,
> frontend, Telegram cuando aplica y Kimi WebBridge sin exigir pasos
> manuales extra. La seguridad estricta queda en perfiles/flags
> conservadores; el objetivo diario es arranque reproducible, diagnóstico
> visible y recuperación rápida.
>
> `full-qa.sh` está actualizado al ciclo vigente post-remediación P0:
> backend con **1200 passed**, 1 skipped, 28 deselected (1190 base + 2
> regresión `test_clean_slate_fixture_covers_all_fks.py` que cerró la
> flakiness ~33% del gate hermético — root cause: orden FK del fixture
> `clean_slate`); `stress-qa.sh 5` -> **5/5 verde × 1200 passed**,
> flakiness post-fix = 0%; ruff/format/mypy/Alembic verdes, frontend
> lint/build verde, `sync_doc_counts --check` y `git diff --check`
> finales. El build frontend de QA usa `NEXT_DIST_DIR=.next-qa` para no
> invalidar un `next start` vivo. Carril opt-in `full-qa-live.sh` para
> smokes read-only contra proveedores reales, último gate documentado
> **8 passed**. Playwright runner zero-friction: `npx playwright test`
> mintea el JWT automáticamente via `POST /auth/local-token` en
> `dedicated_local/full`. `full-qa-live.sh` cubre `/system/mcp`; tras
> `5953b40` el inventario MCP carga en paralelo con timeout 30s. Runtime
> actual verificado: 6/6 servers y 69 tools, incluyendo el MCP local
> read-only `time`.
>
> **Detalle de scripts:** `dev_worker.sh` escucha **5 queues**:
> `default,ingestion,agent_longrun,maintenance,mail`. `full-qa.sh` y
> `stress-qa.sh` instalan el extra OpenHarness; `full-qa.sh` además
> ejecuta `alembic check` como gate real cuando hay DB configurada y
> `git diff --check` como guards finales. Ejecutables de escritorio
> endurecidos (`Levantar/Reiniciar/Detener/Estado Cognitive OS.{sh,desktop}`)
> envuelven `cognitive-os.sh` con lock `flock`, preflight de
> dependencias, anti PID-recycle, kill graceful, rotación de logs y
> modo `doctor`; el frontend corre en `:3001` (`:3000` lo ocupa
> OpenChamber) con chequeo de liveness por puerto. Telegram arranca si
> `TELEGRAM_ENABLED=true`. `verify_desktop_launchers.sh` es el smoke-test
> read-only de los 4 launchers. Wizard `init_credentials.sh [--ci]`:
> checklist REQ/OPT/OK de credenciales. **Fase 73:** `auth_google.py` +
> `auth_gmail.py` son los flows OAuth one-time (detectan scope drift y
> piden re-consent automáticamente).

## Bootstrap y operación

- `init_env.sh`: crea `.env` local y genera secretos si están en `CHANGEME`.
- `dev_up.sh`: levanta infraestructura local y espera health checks. Antes de
  invocar `docker compose` valida que las variables que el compose interpola
  **sin default** (`POSTGRES_USER/PASSWORD/DB`, `WEAVIATE_API_KEY`,
  `NEO4J_USER/PASSWORD`) no estén vacías ni en `CHANGEME` — `docker compose`
  las trataría como string vacío sin fallar (AUDIT-2026-H).
- `dev_down.sh`: apaga infraestructura local.
- `dev_logs.sh SERVICE_NAME`: muestra logs de un servicio Docker.
- `dev_worker.sh`: levanta worker Celery para `default`, `ingestion`, `agent_longrun`, `maintenance` y `mail`.
- `dev_beat.sh`: levanta beat Celery (jobs periódicos: consolidación de memoria, cleanup, action_request reaper, sync mail si `MAIL_ENABLED=true`, digest Gmail/Telegram si está activo).
- `ingest_now.sh PATH_AL_PDF`: ingesta inmediata de PDF dentro de `LOCAL_STORAGE_DIR` o un prefijo permitido.

## Backups y restore

- `backup_postgres.sh`: dump custom de PostgreSQL.
- `backup_neo4j.sh`: dump offline consistente de Neo4j community.
- `backup_storage.sh`: tar.gz de storage local.
- `backup_all.sh`: ejecuta los tres backups.
- `restore_postgres.sh`: restaura un dump Postgres con `CONFIRM_RESTORE=YES`.
- `restore_neo4j.sh`: restaura `neo4j.dump` con Neo4j detenido y checksum.
- `restore_storage.sh`: restaura storage local, dejando copia previa de seguridad.

## Calidad reproducible

- `full-qa.sh`: `cd backend && uv sync --extra openharness && pytest -q && ruff check . && ruff format --check . && mypy src && alembic check && cd ../frontend && npm ci && npm run lint && NEXT_DIST_DIR=.next-qa npm run build`, más `sync_doc_counts.py --check` y `git diff --check` como guards finales. Usa `.next-qa` para no invalidar un `next start` vivo que esté sirviendo `frontend/.next`. `alembic check` solo se omite en clones sin `.env`, `.env.local` ni `DATABASE_URL`.
- `full-e2e.sh`: gate Playwright separado para el cockpit local. Requiere API y frontend ya corriendo; si falta `COGOS_JWT`, el `globalSetup` de Playwright lo obtiene vía `POST /auth/local-token` para probar el camino zero-friction real. Instala Chromium salvo `COGOS_SKIP_PLAYWRIGHT_INSTALL=1` y ejecuta `npx playwright test`.
- `full-testsprite.sh`: gate TestSprite separado para el cockpit local. Requiere
  `API_KEY` o `TESTSPRITE_API_KEY`. Usa como plan canonico versionado
  `qa/testsprite/frontend_commercial_plan.json`, lo copia al runtime ignorado
  `testsprite_tests/testsprite_frontend_test_plan.json`, ejecuta en micro-lotes
  seriales (`TESTSPRITE_BATCH_SIZE=1` por defecto) y fija por defecto
  `TESTSPRITE_PACKAGE=@testsprite/testsprite-mcp@0.0.19` (override permitido,
  nunca `@latest` por defecto). Valida `/health` antes/despues de cada lote,
  aplica idle-timeout/reintentos/split adaptativo, redacciona
  `testsprite_tests/tmp/config.json` al salir y genera
  `qa/reports/testsprite_latest_summary.md`. La ultima corrida completa
  documentada quedo en **28 passed**.
- `full-commercial-qa.sh`: gate orquestador comercial. Corre `full-qa`,
  tests backend de fixtures, fixture live probe si el API fue arrancado con
  `APP_ENV=test` o `COGOS_TEST_FIXTURES_ENABLED=true`, Playwright critico,
  `full-e2e`, stress moderado, health probe de saturacion, secret scan local y
  TestSprite batched si hay `TESTSPRITE_API_KEY`/`API_KEY`. Logs van a
  `qa/reports/`.
- `scan-local-artifacts-for-secrets.sh`: escanea artefactos locales ignorados
  (`testsprite_tests/tmp`, `backend/storage/mail_digests`, logs/traces,
  Playwright y `qa/reports`) sin recorrer `node_modules`; falla ante tokens o
  secrets criticos y tolera placeholders obvios.
- `probe-qa-stack-health.py`: probe de concurrencia moderada para distinguir
  `healthy`, `degraded`, `overloaded` y `failing` sin saturar artificialmente
  el stack local.
- `stress-qa.sh [N]`: ejecuta `pytest -q --tb=no` N veces (default 3) con el mismo extra OpenHarness para detectar flakiness.
- `full-qa-live.sh`: carril **opt-in** de smokes read-only contra los proveedores reales (LLM ping, GoDaddy GET domains, IMAP/SMTP handshake, Telegram `getMe`, Kimi status, MCP `list_tools`, Google OAuth/freebusy). Requiere invocación explícita `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh`; el script no habilita el flag por sí mismo. Verificado con **8 passed** en el último gate live documentado. Excluido de `full-qa.sh`. Cada test se auto-saltea si su credencial no está configurada. Coste ≈ US$0.001.
- `sync_doc_counts.py`: recalcula los conteos canónicos (endpoints, tareas Celery, migraciones, head Alembic, vistas frontend) desde el código y reescribe el bloque `<!-- AUTO:counts -->` de `docs/CURRENT_STATE.md`. `--check` falla si están desincronizados (lo usa `full-qa.sh`); `--print` solo los imprime.

## Otros

- `dump_settings_registry.py` (en `backend/scripts/`): regenera `docs/SETTINGS_REGISTRY_TABLE.md`. Hay un test que falla si la tabla y `Settings` divergen.
- `verify_operator_ready.sh` (en `backend/scripts/`): validación operativa previa a producción; ahora ejecuta ruff, mypy, pytest, dump de settings, Alembic current/heads, `alembic check` y frontend lint/build.
- Ejecutables de escritorio fuera del repo activo (`/home/jgonz/Escritorio`): `Levantar Cognitive OS.sh`, `Reiniciar Cognitive OS.sh`, `Detener Cognitive OS.sh`, `Estado Cognitive OS.sh` y sus `.desktop` envuelven `cognitive-os.sh` para operar API, frontend, worker, beat, Docker y Kimi WebBridge.

Consulta `docs/RUNBOOK.md` para el flujo completo de operacion, restore y
troubleshooting.

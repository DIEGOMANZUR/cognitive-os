# Scripts

> **Estado actual (2026-05-22):** scripts shell verificados para la
> instalación local dedicada. La operación normal prioriza fricción casi
> nula: los launchers de escritorio levantan Docker, API, worker, beat,
> frontend, Telegram cuando aplica y Kimi WebBridge sin exigir pasos
> manuales extra. La seguridad estricta queda en perfiles/flags
> conservadores; el objetivo diario es arranque reproducible, diagnóstico
> visible y recuperación rápida.
>
> `full-qa.sh` está actualizado al ciclo vigente (commit `647f103`):
> backend con **947 passed**, 1 skipped, 28 deselected (944 históricos
> + 3 nuevos por el fix `eager_defaults`); ruff/format/mypy/Alembic
> verdes, frontend lint/build verde, `sync_doc_counts --check` y
> `git diff --check` finales. El build frontend de QA usa
> `NEXT_DIST_DIR=.next-qa` para no invalidar un `next start` vivo.
> Carril opt-in `full-qa-live.sh` para smokes read-only contra
> proveedores reales, verificado con **8 passed**. Playwright runner
> zero-friction: `npx playwright test` mintea el JWT automáticamente
> via `POST /auth/local-token` en `dedicated_local/full`.
> `full-qa-live.sh` cubre `/system/mcp`; tras `5953b40` el inventario MCP
> carga en paralelo con timeout 30s y runtime verificado 5/5 servers.
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
- `full-e2e.sh`: gate Playwright separado para el cockpit local. Requiere API y frontend ya corriendo, minta `COGOS_JWT` si no existe, instala Chromium salvo `COGOS_SKIP_PLAYWRIGHT_INSTALL=1` y ejecuta `npx playwright test`.
- `stress-qa.sh [N]`: ejecuta `pytest -q --tb=no` N veces (default 3) con el mismo extra OpenHarness para detectar flakiness.
- `full-qa-live.sh`: carril **opt-in** de smokes read-only contra los proveedores reales (LLM ping, GoDaddy GET domains, IMAP/SMTP handshake, Telegram `getMe`, Kimi status, MCP `list_tools`, Google OAuth/freebusy). Verificado con **8 passed**. Excluido de `full-qa.sh`. Cada test se auto-saltea si su credencial no está configurada. Coste ≈ US$0.001.
- `sync_doc_counts.py`: recalcula los conteos canónicos (endpoints, tareas Celery, migraciones, head Alembic, vistas frontend) desde el código y reescribe el bloque `<!-- AUTO:counts -->` de `docs/CURRENT_STATE.md`. `--check` falla si están desincronizados (lo usa `full-qa.sh`); `--print` solo los imprime.

## Otros

- `dump_settings_registry.py` (en `backend/scripts/`): regenera `docs/SETTINGS_REGISTRY_TABLE.md`. Hay un test que falla si la tabla y `Settings` divergen.
- `verify_operator_ready.sh` (en `backend/scripts/`): validación operativa previa a producción; ahora ejecuta ruff, mypy, pytest, dump de settings, Alembic current/heads, `alembic check` y frontend lint/build.
- Ejecutables de escritorio fuera del repo activo (`/home/jgonz/Escritorio`): `Levantar Cognitive OS.sh`, `Reiniciar Cognitive OS.sh`, `Detener Cognitive OS.sh`, `Estado Cognitive OS.sh` y sus `.desktop` envuelven `cognitive-os.sh` para operar API, frontend, worker, beat, Docker y Kimi WebBridge.

Consulta `docs/RUNBOOK.md` para el flujo completo de operacion, restore y
troubleshooting.

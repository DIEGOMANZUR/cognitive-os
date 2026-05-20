# Scripts

> **Estado actual (2026-05-20, Fase 74):** scripts shell verificados.
> `dev_worker.sh` escucha **5 queues**:
> `default,ingestion,agent_longrun,maintenance,mail`. `full-qa.sh` y
> `stress-qa.sh` instalan el extra OpenHarness; `full-qa.sh` además
> ejecuta `alembic check` (tolerante a Postgres apagado) y
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
- `dev_up.sh`: levanta infraestructura local y espera health checks.
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

- `full-qa.sh`: `cd backend && uv sync --extra openharness && pytest -q && ruff check . && ruff format --check . && mypy src && cd ../frontend && npm ci && npm run lint && npm run build`.
- `stress-qa.sh [N]`: ejecuta `pytest -q --tb=no` N veces (default 3) con el mismo extra OpenHarness para detectar flakiness.

## Otros

- `dump_settings_registry.py` (en `backend/scripts/`): regenera `docs/SETTINGS_REGISTRY_TABLE.md`. Hay un test que falla si la tabla y `Settings` divergen.
- `verify_operator_ready.sh` (en `backend/scripts/`): validación operativa previa a producción; ahora ejecuta ruff, mypy, pytest, dump de settings, Alembic current/heads, `alembic check` y frontend lint/build.
- Ejecutables de escritorio fuera del repo activo (`/home/jgonz/Escritorio`): `Levantar Cognitive OS.sh`, `Reiniciar Cognitive OS.sh`, `Detener Cognitive OS.sh`, `Estado Cognitive OS.sh` y sus `.desktop` envuelven `cognitive-os.sh` para operar API, frontend, worker, beat, Docker y Kimi WebBridge.

Consulta `docs/RUNBOOK.md` para el flujo completo de operacion, restore y
troubleshooting.

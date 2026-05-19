# ACCEPTANCE CHECKLIST

> **Estado actual (2026-05-19, Fase 68 — GoDaddy DNS prod operativo, doble revisión profunda, suite hermética 685 passed; Telegram requiere token nuevo):** matriz
> de aceptación vigente. Fase 66 levantó el stack real con credenciales del
> operador y auditó cada parte; 4 bugs críticos enmascarados por la
> resiliencia fueron corregidos y verificados en vivo (DeepAgent/tool_choice,
> LLM secondary/fallback 403, LangSmith trazas 403, Maps traffic 400). Ver
> §"Verificado en vivo - Fase 66" abajo.
> matriz de aceptación vigente. Incluye OpenHarness opcional en *Chat /
> orquestación*, mail personal GoDaddy/Gmail-label con envío aprobado,
> integraciones Google (Maps con tráfico/link, Calendar/Drive read +
> writes solo por `ActionRequest`), voz ElevenLabs (STT/TTS), vista
> `AssistView` para tareas/notas personales, `GoogleOpsView` para operar
> Maps/Calendar/Drive y **`CodeDirectorView`** para delegar builds a
> coding agents externos (Claude Code/Codex/Kimi/DeepAgents) bajo
> HumanApproval + budget caps + audit; con planner LLM-driven y prompts
> con contexto vivo del workspace (F9). Fases 50-58 cerraron Telegram
> approvals con dispatch real de `ActionRequest` y smoke versionado de
> launchers de escritorio. Fases 59-63 agregaron dispatch durable:
> fallos de broker visibles, JobEvents submit/fail y worker duplicate-running
> short-circuit. Fase 64 añadió reserva atómica `dispatch_state` para impedir
> submits duplicados a Celery. Fase 65 cerró paridad Telegram↔UI (36 slash
> commands) y corrigió el CHECK `ck_ar_action_type` que rompía Drive
> folder/organize en Postgres real (migración `202605170001` + test de
> regresión que mantiene ORM/migración/servicio en sync).
> Snapshot QA persistente (Fase 65):
> **685 pytest passed, 1 skipped, 20 deselected**; ruff/ruff format/mypy
> (125 source files), frontend lint/build (20 vistas), Alembic head
> `202605170001` sin drift y `git diff --check` verdes.
> Los snapshots con fecha por-fase más abajo son **históricos**: para
> reverificar QA hoy ejecuta `bash scripts/full-qa.sh`.

Este checklist separa lo verificado por pruebas automaticas de lo que requiere
infraestructura local real, credenciales o aprobacion manual.

## Verificado en vivo - 2026-05-18 (Fase 66, stack real + credenciales reales)

- [x] Docker infra real `healthy`: postgres, redis, weaviate, neo4j (query directa).
- [x] `alembic upgrade head` aplicado en Postgres real → `202605170001`; query
  a `pg_constraint` confirma que `ck_ar_action_type` incluye
  `drive_ensure_folder` + `drive_organize_files` (bugfix Fase 65 verificado vivo).
- [x] `/health/dashboard` con JWT real: postgres/redis/weaviate/neo4j `ok`,
  workers `ok`, langsmith `ok`, checkpointer Postgres real, voice/maps/
  captcha/webbridge `ready`, gmail `configured`. `google_calendar`/`drive`
  `blocked` (esperan OAuth interactivo — reacción correcta).
- [x] Conectividad LLM real: primary/secondary/fallback (DeepSeek),
  vision/vision_fb (GLM), embeddings (Gemini, dim=3072) → **HTTP 200**.
- [x] `POST /chat` real → DeepAgent funcionando **sin** fallback RAG
  (`fallback=False`) tras el fix `AGENT_LLM_MODEL=deepseek-chat`.
- [x] `POST /actions/maps/route` traffic-aware real → `19.5 km · 25 min ·
  tráfico leve · 12 pasos · google_maps_url` tras el fix `departureTime`.
- [x] LangSmith `/sessions` con el personal access token → 200 (trazas
  ingestables) tras el fix de precedencia de credencial.
- [x] `bash scripts/full-qa.sh` → **685 passed, 1 skipped, 20 deselected**;
  ruff/format/mypy (125 files)/eslint verdes tras los 4 fixes + 7 tests
  endurecidos a herméticos.
- [ ] OAuth Google (`scripts/auth_google.py`) — **pendiente operador**
  (paso interactivo: login + consentimiento en navegador).
- [ ] `GODADDY_API_SECRET` — **pendiente operador** (solo se recibió la key).

## Verificado Automaticamente - 2026-05-17 (Fase 65 paridad UI/Telegram + bugfix CHECK)

- [x] **Bug crítico Postgres-only corregido:** `ck_ar_action_type` no incluía `drive_ensure_folder`/`drive_organize_files`; los endpoints `/actions/drive/folders/ensure/request` y `/actions/drive/organize/request` daban `CheckViolation` en Postgres real (enmascarado porque los tests mocan `session_scope`). Migración `alembic/versions/202605170001_action_requests_drive_folder_organize.py` + ORM `__table_args__` sincronizado.
- [x] `uv run pytest tests/test_action_request_check_constraint.py -q` → **2 passed** (regresión que mantiene ORM/migración/`WORKFLOW_EXPORTABLE_TYPES` en sync).
- [x] Telegram: **+11 slash commands** (`/maps`, `/calendar`, `/freebusy`, `/drive`, `/documents`, `/audit`, `/mail`, `/research`, `/codebuild`, `/sandbox`, `/capabilities`) con gating de capacidades; `uv run pytest tests/test_telegram_bot.py -q` → **14 passed**.
- [x] Mapeo FE↔BE: 44 rutas REST del frontend ↔ 131 endpoints backend, 0 huérfanos.
- [x] `uv run pytest -q` → **685 passed, 1 skipped, 20 deselected**.
- [x] `bash scripts/full-qa.sh` → verde (pytest + ruff + ruff format + mypy + Alembic check + npm ci + frontend lint/build + `git diff --check`).
- [x] `bash scripts/stress-qa.sh` → 3 corridas (baseline 674 pre-fix; suite estable).
- [x] `uvx pre-commit run --all-files` → 6 hooks Passed (large-files, merge-conflict, EOF, trailing-whitespace, gitleaks, detect-secrets).
- [x] `uv run alembic heads` → `202605170001 (head)`; `alembic history` cadena lineal single-head; `alembic check` sin drift.
- [x] `docker compose -f infra/docker-compose.yml --env-file .env.example config --quiet` → pass.
- [x] `bash scripts/verify_desktop_launchers.sh` → launchers OK.

## Verificado Automaticamente - 2026-05-17 (Fase 64 dispatch idempotente)

- [x] `uv run pytest tests/test_actions.py tests/test_action_request_workers.py tests/test_telegram_bot.py tests/test_decide_approval_helper.py -q` → **72 passed**.
- [x] `bash scripts/full-qa.sh` → **674 passed, 1 skipped, 20 deselected**; ruff check, ruff format, mypy, Alembic check, `npm ci`, frontend lint/build y `git diff --check` verdes.

## Verificado Automaticamente - 2026-05-17 (Fases 59-63 dispatch durable)

- [x] Tests focales dispatch/worker/Telegram → **12 passed**.
- [x] `uv run pytest tests/test_actions.py tests/test_action_request_workers.py tests/test_telegram_bot.py tests/test_decide_approval_helper.py -q` → **69 passed**.
- [x] `bash scripts/full-qa.sh` → **671 passed, 1 skipped, 20 deselected**; ruff check, ruff format, mypy, Alembic check, `npm ci`, frontend lint/build y `git diff --check` verdes.

## Verificado Automaticamente - 2026-05-17 (Fases 50-58 bloque 3 operativo)

- [x] `uv run pytest tests/test_telegram_bot.py tests/test_desktop_launchers.py -q` → **7 passed**.
- [x] `uv run pytest tests/test_decide_approval_helper.py tests/test_actions.py tests/test_telegram_bot.py tests/test_desktop_launchers.py -q` → **65 passed**.
- [x] `bash scripts/verify_desktop_launchers.sh` → launchers reales del Escritorio OK.
- [x] `bash scripts/full-qa.sh` → **669 passed, 1 skipped, 20 deselected**; ruff check, ruff format, mypy, Alembic check, `npm ci`, frontend lint/build y `git diff --check` verdes.

## Verificado Automaticamente - 2026-05-17 (Fase 42 legal-pack DeepAgents cerrada)

- [x] `uv run pytest -m 'not integration and not slow'` → **642 passed, 1 skipped, 20 deselected**.
- [x] Stress 3 corridas idénticas → 642 passed cada una.
- [x] `uv run ruff check .` → All checks passed.
- [x] `uv run ruff format --check .` → 220 files already formatted.
- [x] `uv run mypy src` → Success: no issues found in 111 source files.
- [x] `npm run lint` → pass.
- [x] `npm run build` → Next.js 16.2.6, 20 vistas.
- [x] `docker compose --env-file .env.example -f infra/docker-compose.yml config --quiet` → pass.
- [x] `uv run alembic heads` → `202605160002 (head)`; `alembic check` sin drift.
- [x] `git diff --check` → clean.
- [x] `uvx pre-commit run --all-files` → 6 hooks Passed (large-files, merge-conflict, EOF, trailing-whitespace, gitleaks, detect-secrets baseline).
- [x] `uvx --from detect-secrets detect-secrets scan` → 0 findings.
- [x] `bash scripts/init_credentials.sh` → 0 REQ faltantes en el host.
- [x] Tests focalizados Fase 39: rate limit memory+redis (9), credentials inventory (7), workflow.v1 (7), decide_approval helper (4), correlation_id (7), google_oauth_instructions (4) → **38 passed**.

## Verificado Automaticamente - 2026-05-17 (Fases 44-49 Google operativo avanzado)

- [x] `uv run pytest tests/test_google_drive.py tests/test_google_calendar.py tests/test_actions.py tests/test_deepagents_personal_tools.py -q` → **118 passed**.
- [x] `bash scripts/full-qa.sh` → **662 passed, 1 skipped, 20 deselected**; ruff check, ruff format, mypy, Alembic check, `npm ci`, frontend lint/build y `git diff --check` verdes.
- [x] `docker compose -f infra/docker-compose.yml --env-file ../.env.example config --quiet` → pass con warnings esperados por variables unset del env de ejemplo.

## Verificado Automaticamente - 2026-05-15 (Fase 32 hardening comercial)

- [x] `uv run pytest -m 'not integration and not slow'` → **484 passed, 1 skipped, 20 deselected**.
- [x] `uv run ruff check .` → All checks passed.
- [x] `uv run ruff format --check .` → 198 files already formatted.
- [x] `uv run mypy src` → Success: no issues found in 106 source files.
- [x] `npm run lint` → pass.
- [x] `npm run build` → Next.js 16.2.6 (Turbopack), build estática OK.
- [x] `git diff --check` → clean.
- [x] Tests focalizados de hardening Google/health/Celery: `uv run pytest tests/test_google_calendar.py tests/test_google_drive.py tests/test_google_oauth.py tests/test_config.py tests/test_celery_config.py tests/test_health_dashboard.py -q` → **52 passed**.
- [x] Tests estáticos frontend/PWA: `uv run pytest tests/test_frontend_static_assets.py -q` → pass.
- [x] Compose local-only: `docker compose --env-file .env.example -f infra/docker-compose.yml config --quiet` → pass.

## Verificado Automaticamente - 2026-05-14 (sweep Fase 25 C/D/F)

Snapshot QA tras implementar voz, Maps, Calendar/Drive (read + write opt-in),
DeepAgents tools personales, SecretStore y endurecimiento de capacidades.

- [x] `uv run pytest -m 'not integration and not slow'` → **428 passed, 1 skipped, 20 deselected**.
- [x] `uv run ruff check .` → All checks passed.
- [x] `uv run mypy src` → Success: no issues found in 104 source files (modo `strict`).
- [x] `npm run lint` → 0 warnings, 0 errors.
- [x] `npm run build` → Next.js 16.2.6 (Turbopack), build estática OK.
- [x] `GOOGLE_MAPS_API_KEY` + `ENABLE_MAPS_ROUTING` → `MapsService` Routes + Geocoding
  con providers fake/real, endpoints `/actions/maps/status|geocode|route`.
- [x] `ELEVENLABS_API_KEY` + `VOICE_ENABLED` → `VoiceService` STT (`scribe_v1`) +
  TTS (`eleven_multilingual_v2`), cap `VOICE_MAX_AUDIO_BYTES`, endpoints
  `/voice/status|transcribe|speak`.
- [x] `GOOGLE_CLIENT_ID/SECRET` + `ENABLE_GOOGLE_CALENDAR` → `CalendarService`
  read-only (lista eventos) + write opt-in (`ENABLE_GOOGLE_CALENDAR_WRITE` +
  `dry_run=false`); cada intento auditado.
- [x] `GOOGLE_CLIENT_ID/SECRET` + `ENABLE_GOOGLE_DRIVE` → `DriveService` read-only
  (lista/get) + write opt-in (`ENABLE_GOOGLE_DRIVE_WRITE` + `dry_run=false`); upload
  bloquea paths fuera de `COMPUTER_ALLOWED_ROOTS` y archivos sobre
  `GOOGLE_DRIVE_UPLOAD_MAX_BYTES`.
- [x] Tools DeepAgents nuevas controladas: `plan_route`, `geocode_address`,
  `list_calendar_events`, `search_drive_files`, `search_notes` (con aislamiento
  por `user_id`).
- [x] `core/secrets.py SecretStore`: tests de regresión que verifican que
  `PublicConfigResponse` no contenga campos `SecretStr`, que `model_dump`
  conserva `SecretStr` opaco, y que ningún BaseModel de respuesta en `api/app.py`
  expone `SecretStr`.
- [x] `/health/dashboard` reporta voice, maps, google_calendar y google_drive
  como componentes adicionales con su `write_enabled` cuando aplica.
- [x] `GET /health` responde `{status: "ok"}` sin auth en tests.
- [x] Endpoints protegidos rechazan requests sin JWT antes de tocar DB.
- [x] Action Plane bloquea browser/computer/Gmail/GoDaddy cuando estan
  deshabilitados o fuera de allow-list.
- [x] Action Plane genera previews dry-run para ordenar carpetas y cambios DNS.
- [x] `computer_organize` ejecuta movimientos reales solo con config explicita
  y rutas permitidas.
- [x] `POST /actions/computer/organize/request` crea una solicitud persistente
  via servicio.
- [x] `POST /actions/requests/{id}/dispatch` solo encola worker si la solicitud
  quedo en `queued`.
- [x] Configuracion rechaza CORS wildcard y credenciales `CHANGEME` en produccion.
- [x] Bridge OpenHarness aislado: `_execute_engine_blocking` corre el `QueryEngine` en
  hilo dedicado con event loop propio; tests verifican comportamiento dentro de
  un loop activo y precedencia de skips (`disabled` > `not_installed` > `empty_query`).
- [x] `SETTINGS_REGISTRY_TABLE.md` 1:1 con `Settings` (test
  `test_settings_registry_table_markdown_matches_generated_body`).
- [x] Mail personal: migración `mail_*`, endpoints `/mail/*`, worker
  `cognitive_os.sync_personal_mail` en queue `mail`, vista `Mail`, sync real
  GoDaddy IMAP probado con 25 mensajes insertados y envío limitado a aprobación
  explícita por SMTP GoDaddy.
- [x] Ejecutables de escritorio: `/home/jgonz/Escritorio/cognitive-os.sh` y
  wrappers start/restart/stop/status operan Docker, API, worker, beat, frontend
  y Kimi WebBridge.

## Infra

- [ ] `bash scripts/init_env.sh` rellena los secretos locales sin fallar.
- [ ] `bash scripts/dev_up.sh` levanta Postgres, Redis, Weaviate y Neo4j hasta `healthy`.
- [ ] `uv run alembic upgrade head` aplica todas las migraciones.

## API

- [x] `GET /health` responde `{status: "ok"}` sin auth.
- [ ] `GET /health/dashboard` (con JWT) lista cada componente con estado y
  latencia, y reporta el backend del checkpointer (`postgres` en producción).
- [ ] `_api_graph` sobrevive a reinicios del proceso cuando Postgres está
  disponible (gracias al `PostgresSaver` montado en el lifespan).

## Ingesta

- [ ] Puedo ingestar un PDF y consultar su `job_id` con eventos detallados.
- [ ] El job final deja entradas en `documents`, `document_pages`,
  `document_chunks` y en Weaviate.

## Chat / orquestación

- [ ] `POST /chat` con `doc_ids` adjuntos fuerza la ruta legal y dispara
  document analysis.
- [ ] Una acción sensible (enviar mail, publicar) interrumpe el grafo y crea
  un `HumanApproval`.
- [ ] `POST /threads/{id}/resume` con `approve | edit | reject` retoma el flujo.
- [ ] (Opcional OpenHarness) Con `ENABLE_OPENHARNESS_RESEARCH=true` y extra
  instalado, la ruta research aplica `OPENHARNESS_RESEARCH_PIPELINE` (`prelude_merge`
  por defecto: preludio OH + DeepAgent). Ver `docs/OPENHARNESS_FUSION.md`.

## Document Analysis

- [ ] `POST /document-analysis/run` encola un job y deja eventos detallados.
- [ ] El resultado contiene `evidence_matrix`, `timeline`, `contradictions`,
  `quality_score` y citas.
- [ ] Los archivos `result.json`, `report.md`, `evidence_matrix.csv`,
  `timeline.csv`, `contradictions.csv` (y opcionalmente `report.docx`) son
  descargables vía `GET /document-analysis/{task_id}/download/*`.
- [ ] Cuando el quality score < 85 o hay borradores, se crea un `HumanApproval`
  automáticamente.

## DeepAgents

- [ ] `GET /deepagents/skills` lista skills core habilitadas.
- [ ] Las propuestas de memoria sólo entran a memoria activa después de
  aprobarlas.
- [x] Memorias episodicas (`kind=episodic`): `POST /deepagents/memory/episodic`
  (JWT, `DeepAgentsEnableMemory`), audita `deepagents.memory.episodic_append`,
  visibles en `get_startup_memory` para `user|thread`; migracion
  `202605120005_deepagent_memory_episodic`.
- [ ] La beat task `consolidate_all_deepagent_memory` despacha jobs por agente
  conocido (`research`, `document-analysis`).

## Action Plane

- [x] `GET /actions/capabilities` requiere JWT y devuelve browser, computer,
  Gmail, GoDaddy, Maps, Google Calendar y Google Drive.
- [x] `POST /actions/browser/validate` bloquea dominios no permitidos y modos
  headed/vision si no estan habilitados.
- [x] `POST /actions/computer/organize/preview` crea plan dry-run sin mover
  archivos.
- [x] `POST /actions/gmail/query/preview` respeta `GMAIL_READ_ENABLED`.
- [x] `POST /actions/godaddy/dns/preview` normaliza dominio, valida formato y
  devuelve endpoint dry-run.
- [x] `POST /actions/computer/organize/request` registra `ActionRequest`
  persistente para el flujo de aprobacion.
- [x] `POST /actions/browser/request`, `POST /actions/gmail/query/request` y
  `POST /actions/godaddy/dns/request` registran `ActionRequest` persistentes
  preview-only (`previewed` o `blocked`) con audit event.
- [x] `GET /actions/requests` filtra por `action_type` y `status`.
- [x] `POST /actions/requests/{id}/cancel` cancela solicitudes no-running ni
  finales, marca el job asociado y registra audit.
- [x] `POST /actions/requests/{id}/dispatch` encola worker Celery solo cuando la
  solicitud esta aprobada y en `queued`.
- [x] `GET /actions/documents/status` reporta `disabled|configured|ready` segun
  `ENABLE_DOCUMENT_GENERATION` y proveedores instalados.
- [x] `POST /actions/documents/preview` rechaza rutas absolutas, `..`, vacias
  y fuera de `DOCUMENT_OUTPUT_ROOT`.
- [x] `POST /actions/documents/request` crea `ActionRequest` con
  `action_type='document_generate'`, estado `pending_approval`, `HumanApproval`
  y `Job` enlazados.
- [x] `POST /actions/calendar/events/request` crea `ActionRequest` ejecutable
  `calendar_create_event` con `HumanApproval` y `Job` enlazados; la ejecución real
  mantiene doble compuerta (`ENABLE_GOOGLE_CALENDAR_WRITE` + aprobación).
- [x] `POST /actions/drive/files/upload/request` crea `ActionRequest` ejecutable
  `drive_upload_file`; Drive usa carpeta de entregables por defecto y acepta
  solo fuentes bajo `DOCUMENT_OUTPUT_ROOT`, `LOCAL_STORAGE_DIR/workspaces`,
  `OPENSHELL_ALLOWED_OUTPUT_DIR` o `COMPUTER_ALLOWED_ROOTS`, más cap de tamaño.
- [x] `POST /actions/drive/folders/ensure/request` crea `ActionRequest`
  ejecutable `drive_ensure_folder` para crear/asegurar la carpeta de
  entregables bajo aprobación humana.
- [x] `POST /actions/drive/organize/preview` previsualiza archivos Drive que se
  moverían a carpeta destino; `POST /actions/drive/organize/request` crea
  `ActionRequest` ejecutable `drive_organize_files` sin borrar ni cambiar
  permisos.
- [x] `POST /actions/drive/files` busca por `name`, `full_text` o `all`
  (`name OR fullText`) en `Mi unidad` o `allDrives`, con `trashed=false`.
- [x] `POST /actions/calendar/freebusy` devuelve bloques ocupados por rango y
  calendario como lectura pura; DeepAgents expone `check_calendar_freebusy`.
- [x] `POST /actions/maps/route` devuelve tráfico, retraso estimado, severidad,
  ETA, advice operativo, alternativas y link Google Maps sin exponer API keys.
- [x] `GoogleOpsView` ofrece UI dedicada para rutas Maps, eventos Calendar y
  entregables Drive bajo aprobación.
- [x] La ejecucion de `document_generate` escribe DOCX/XLSX/PPTX dentro de
  `DOCUMENT_OUTPUT_ROOT` y rechaza archivos mayores que `DOCUMENT_MAX_SIZE_BYTES`.
- [x] El panel muestra solicitudes recientes de accion en `Configuracion`.
- [x] El panel intenta despachar automaticamente una accion aprobada de tipo
  `execute_action_request`.
- [ ] UI dedicada completa para todos los `ActionRequest`, ver preview/resultado
  expandido y reintentar fallos sin usar curl. Google Ops ya cubre Maps/Calendar/Drive.
- [ ] Executors reales pendientes: Gmail send/drafts y Camoufox. Browser Playwright,
  GoDaddy DNS, Calendar create y Drive upload ya tienen carriles controlados.
- [x] `browser_preview` headless (Playwright opt-in): valida dominio
  allow-list, exige `BROWSER_HEADLESS_DEFAULT=true`, sin cookies persistidas,
  con screenshot acotada por `BROWSER_SCREENSHOT_MAX_BYTES` dentro de
  `BROWSER_SCREENSHOT_DIR`, y registrada como `ActionRequest`
  `pending_approval`. El provider real se carga solo si `playwright` esta
  instalado; en caso contrario el executor responde `blocked` con razon
  clara.
- [x] Research Orchestrator sobre deepagents: `POST /research/runs` planea
  subtasks, ejecuta hasta `RESEARCH_MAX_PARALLEL_WORKERS` deepagents en
  paralelo bajo `time_budget_seconds`, sintetiza con dedup de citas y
  califica con rubrica auditable. Cancelacion segura via
  `POST /research/runs/{id}/cancel`. Limites: `RESEARCH_MAX_SUBTASKS=8`,
  `RESEARCH_MAX_TIME_BUDGET_SECONDS=300`,
  `RESEARCH_MAX_PARALLEL_WORKERS=4`. Providers (planner/researcher/synth/
  scorer) son inyectables para pruebas sin LLM ni red.
- [x] Research Orchestrator async + SSE (Fase 14): `start_run` retorna en
  < 200 ms con run en estado no-terminal. `_execute` corre en daemon thread.
  `wait_for_run(run_id, timeout=60)` bloquea hasta estado terminal sin
  excepciones. Endpoint SSE `GET /research/runs/{id}/events` emite eventos
  historicos + nuevos hasta estado terminal mas `snapshot` final y `done`.
  Requiere JWT, 404 si la run no existe.
- [x] Gmail Daily Digest read-only (Fase 13): `POST /actions/gmail/digest/preview`
  bajo JWT entrega resumen redactado con direcciones (`l***l@dominio`),
  agrupado por remitente, ordenado por fecha. Propone borradores con
  `requires_approval=True` pero **nunca crea drafts en Gmail**.
  `GmailReader` Protocol inyectable para tests y providers reales.
- [x] Gmail real read-only (Fase 21): runtime usa `GmailRestReader` cuando
  `GMAIL_READ_ENABLED=true` y existe `GMAIL_TOKEN_DIR/token.json`; llama Gmail
  REST con `gmail.readonly`, refresca token si puede, normaliza metadata/snippet
  y convierte fallos en `blocked` con secretos redactados. Envio y drafts reales
  siguen deshabilitados en esta fase.
- [x] Mail personal GoDaddy/Gmail-label (Fase 26): `/mail/status`, `/mail/sync`,
  `/mail/sync/dispatch`, `/mail/messages`, `/mail/messages/{id}`,
  `/mail/messages/{id}/reply`, `/mail/messages/{id}/ignore` y
  `/mail/messages/{id}/approve-send` persisten mensajes/propuestas en Postgres;
  Gmail label `TODOS` se lee si OAuth está activo; SMTP GoDaddy solo envía tras
  aprobación explícita y registra `mail_send_logs`.
- [x] GoDaddy DNS executor seguro (Fase 22): DNS writes reales quedan dry-run
  por defecto; para ejecutar se exige `GODADDY_DNS_DRY_RUN_ONLY=false`,
  `GODADDY_ALLOWED_DOMAINS`, aprobacion humana y
  `GODADDY_ALLOW_PRODUCTION_WRITES=true` si la base URL es produccion. El
  executor aplica un solo record por `PATCH /v1/domains/{domain}/records`.
- [x] Inventario local de archivos (Fase 24): `POST /actions/computer/inventory`
  crea reporte read-only dentro de `COMPUTER_ALLOWED_ROOTS`, sin seguir symlinks
  ni leer contenido, omitiendo rutas sensibles y guardando JSON en
  `LOCAL_STORAGE_DIR/file_inventory`.
- [x] Browser interactivo + vision multimodal (Fase 17): `POST /actions/browser/interactive/request`
  persiste plan de hasta 24 steps (click/fill/scroll/wait/screenshot/analyze).
  Validacion pre-launch de allow-list y selectors. `VisionAnalyzer` Protocol con
  default `ChatVisionAnalyzer` que envia screenshot al primary multimodal LLM.
  Provider Playwright + tests con FakeProvider/FakeVision.
- [x] Ops hardening (Fase 20): XLSX cells con prefijo `=/+/-/@` se neutralizan con
  apostrofo; DNS rebinding y IPs privadas se rechazan via `validate_browser_target_ip`
  (gated por `ENABLE_BROWSER_SSRF_CHECK`); reaper Celery task marca como `failed` los
  ActionRequest stuck en `running` mas alla de `ACTION_REQUEST_RUNNING_MAX_MINUTES`;
  silent excepts en `web_indexer` y `reranker` reemplazados por structlog warnings;
  tokenizer del lexical fallback ahora maneja tildes y stopwords español+ingles.
- [x] DeepAgents 0.6.x (Fase 18): dependencia actualizada a
  `deepagents>=0.6.1,<0.7.0`; factory compatible con `subagents` y `memory`;
  subagents locales seguros para research/document analysis; startup memory como
  `./.cognitive_os/AGENTS.md`; consolidacion deduplica propuestas repetidas.
- [x] Office writers extendidos (Fase 19): DOCX soporta tablas e imagenes
  allow-listed por `DOCUMENT_ASSET_ROOTS`; XLSX soporta formulas explicitas
  seguras via `SpreadsheetFormula` y mantiene sanitizacion de strings; PPTX
  soporta layouts `title`, `bullets`, `two_column` y `quote`. Los tests reabren
  los archivos generados con las librerias Office correspondientes.
- [x] Robustez del pipeline RAG (Fase 16): chunks `pending_index` -> `indexed`
  solo despues de confirmacion Weaviate; sha256 dedup en re-ingesta;
  `WeaviateStore.batch_insert_chunks` usa `/v1/batch/objects` + embeddings batch;
  BM25-only fallback cuando embeddings caen; `ensure_collection` thread-safe con
  acepacion de 422 "already exists".
- [x] Correctness critico Fase 15: 8 bugs cerrados con regresion explicita.
  - `computer_organize` ejecuta el plan APROBADO, no recompila desde FS.
  - `_execute` usa `payload_executable` (ejecutable y cifrable); `payload_redacted` queda solo para auditoria.
  - `research_node` cae a fallback RAG cuando DeepAgent devuelve `answer` vacio,
    aunque el `status` diga `ok`/`needs_more_info`/`blocked`.
  - `execute_action_request` es atomico: `SELECT ... FOR UPDATE` + check pre-flush
    impide doble dispatch.
  - `read_document_pages` enforcea `task.allowed_doc_ids` (default deny si lista vacia).
  - `search_local_docs` excluye `doc_type="web"` por defecto; web indexer no contamina queries locales.
  - Auditoria emite eventos en errores y bloqueos, no solo en exitos.
  - Citas usan basename o `title`, no leakean path absoluto del ingestor (POSIX y Windows).

## Backups & restore

- [x] `bash scripts/backup_all.sh` produce dumps con `sha256`.
- [x] Restore de Postgres, Neo4j y storage esta documentado en RUNBOOK con
  scripts dedicados (`restore_postgres.sh`, `restore_neo4j.sh`,
  `restore_storage.sh`), `CONFIRM_RESTORE=YES`, verificacion `.sha256` y tests
  de sintaxis/guardrails. Pendiente operacional: ejecutar un restore completo
  en staging con datos descartables antes de usarlo en produccion.

## Calidad

- [x] `uv run ruff check .` y `uv run ruff format --check .` pasan.
- [x] `uv run mypy src` pasa en modo `strict`.
- [x] `uv run pytest` pasa toda la suite no-integration.
- [x] El frontend compila con `npm run build`.

## Documentacion

- [x] `README.md` apunta a las guias principales.
- [x] `docs/README.md` indexa documentacion estable.
- [x] `docs/PROJECT_GUIDE.md` explica el sistema en palabras simples y tecnicas.
- [x] `docs/ACTION_PLANE.md` documenta browser, computador, Gmail y GoDaddy.
- [x] `task_plan.md`, `findings.md` y `progress.md` quedan declarados como
  archivos de planificacion viva.

# Progress

> Bitácora viva. La documentación estable de producto vive en `docs/`.

## 2026-05-17 — Fase 41 Code Director F9 cerrada (3 commits)

Salto de "anda" a "es capaz para apps complejas". El director ya no
planifica con un esqueleto fijo ni promptea a ciegas:

- F9a `c52ed69` `planner.py`: `LLMPlanner` descompone el objetivo vía
  el LLM primario (subtareas reales, orden por dependencia,
  adapter/modelo por rol). Fallback determinista `HeuristicPlanner`
  ante **cualquier** fallo (sin key, circuito abierto, JSON
  malformado/encerrado en fences, esquema inválido, deps alucinadas);
  un build nunca muere por el planner. Seam `llm_completion` inyectable
  → tests sin gastar token. Tests fijan `HeuristicPlanner` en cada
  construcción de director para que la suite jamás toque la red (11 t).
- F9b+F9c `051dc78` `prompt_builder.py`: prompt estructurado y
  **acotado** desde el estado vivo — árbol del workspace, contenido de
  paths esperados + archivos que tocaron las dependencias, resumen de
  upstream (F9b); en reintento, error/stderr/exit-code del intento
  previo con directiva "arregla esto, no empieces de cero" — el prompt
  de reintento difiere, `iterate_until_tests_pass` converge (F9c).
  Topes duros + path-containment; puro filesystem, 0 tokens (10 t).
- F9d (este) smoke E2E heurístico-vs-LLM + docs + cert (2 t).

Suite: **632 passed, 1 skipped, 20 deselected**. Compuertas
ruff/format/mypy (14 fuentes code_director), pre-commit (6 hooks),
detect-secrets — verdes. Docs: RUNBOOK § "Code Director"
(Planificación y prompting F9), ACTION_PLANE § "Code Director".

## 2026-05-17 — Fase 40 Code Director cerrada (8 commits)

Meta-agente que delega builds a coding agents externos. 8 fases, commit
por fase, suite verde en cada una:

- F1 `102567a` schemas + Protocol + FakeAdapter + director loop (12 t)
- F2 `e7ed3ee` DeepAgentAdapter in-process (7 t)
- F3 `5cca3e6` subprocess adapters Claude/Codex/Kimi (11 t, 0 tokens)
- F4 `96e7a67` CodeDirectorService HITL persistence (5 t)
- F5 `aba0b64` Celery task + approval-triggered dispatch (1 t)
- F6 `6c29a3f` 4 REST endpoints + secure download (5 t)
- F7 `e18ea1c` CodeDirectorView + SSE timeline (frontend)
- F8 (este) E2E tar.gz + manifest + docs + cert (2 t)

Conteos vivos actualizados: **126 endpoints REST** (100 propios),
**16 tareas Celery**, **20 vistas frontend**. Suite final:
**609 passed, 1 skipped, 20 deselected**. Compuertas: ruff/format/mypy,
frontend lint/build, pre-commit (6 hooks), detect-secrets — todas
verdes. Docs: RUNBOOK § "Code Director", ACTION_PLANE § "Code Director",
AGENTS.md actualizado.

Sin P0/P1/P2 conocidos pendientes con cierre técnico viable. El único
pendiente operador sigue siendo OAuth Google (1 click) si quiere
Calendar/Drive — no aplica al Code Director, que usa las credenciales
propias de cada CLI.

## 2026-05-17 - Fase 39 cerrada: cierre de riesgos residuales

5 commits cierran los 3 riesgos residuales declarados que admitían cierre
técnico y minimizan al máximo el único inherente al protocolo OAuth.

- **B.1 — Redis rate limiter** (commit `d413766`): `RateLimiter` Protocol
  con dos backends (memory/redis). Sorted-set sliding window con
  fail-open ante outage. Settings `RATE_LIMIT_BACKEND` y
  `RATE_LIMIT_REDIS_URL`. +5 tests con fake Redis client (no requiere
  Redis real).
- **B.2 — /system/credentials-status** (commit `4886499`): inventario
  declarativo de las 21 credenciales con endpoint admin que reporta
  estado, capacidad habilitada y `how_to_obtain`. Nunca devuelve valores.
  +7 tests incluyendo defense-in-depth contra leaks.
- **B.3 — OAuth Google resiliencia** (commit `589df59`): `auth_google.py`
  detecta y refresca tokens existentes sin abrir browser; health detail
  enriquece con la instrucción exacta cuando falta el token. +4 tests.
- **B.4 — init_credentials wizard** (commit `753bdb0`): checklist
  REQ/OPT/OK con instrucción inline, flag `--ci` para gate de pipeline.
  Smoke live: 15/21 configuradas en este host.
- **B.5 — cert final** (este commit): compuertas verdes + declaración
  honesta de lo único que no es cerrable (OAuth primer click).

Suite final: **566 passed**, 1 skipped, 20 deselected (+4 vs Fase 38).
Stress 3 corridas estable, ~25-27s c/u.

Compuertas:
- `bash scripts/full-qa.sh` → OK con guardas alembic + git diff.
- `bash backend/scripts/verify_operator_ready.sh` → OK head `202605160002`.
- `uvx pre-commit run --all-files` → Passed (6 hooks).
- `uvx --from detect-secrets detect-secrets scan` → 0 findings.
- `bash scripts/init_credentials.sh` → 0 REQ faltantes.

Declaración honesta: el único elemento que NO admite cierre técnico es la
**primera autorización OAuth de Google** porque el estándar requiere
interacción humana con el browser. Refresh y reanudación están
automatizados; sólo el primer click queda manual. Esto no es un punto
débil de Cognitive OS — es el contrato de OAuth 2.0 Desktop Flow.

Sin P0/P1/P2 conocidos pendientes con cierre técnico viable. Sistema en
grado comercial operable.

## 2026-05-16 - Fase 38 cerrada: revision personal de grado comercial

7 fases ejecutadas sin esperar intervencion (mapeo, hardening, capacidades,
frontend, tests, runbook, certificacion):

- **Fase A — Mapeo personal**: lectura directa de 14k LOC backend +
  frontend + workers + integraciones, sin agentes intermediarios.
- **Fase B — Hardening por capa** (commit 4073adf): atomic writes
  documents, correlation IDs trazables a logs via structlog contextvars,
  rate limit sliding-window per-(user, bucket) aplicado a 10 endpoints
  sensibles.
- **Fase C — Capacidades** (c24f2ea): `/system/info` enriquecido con
  `git_commit` y `alembic_head`; Celery `run_action_request` short-circuit
  en jobs ya terminales para evitar overwrite en retries.
- **Fase D — Frontend** (1833f32): ErrorBoundary global, `Retry-After`
  propagado a mensajes de error 429, badge `expired` reconocido.
- **Fase E — Tests** (97cc876): property-based en `_idempotency_key` (7
  contratos) + regresion atomic doc write (sin tmp lingering + crash no
  corrompe final).
- **Fase F — RUNBOOK** (fca1e2f): seccion "Bootstrap desde cero" con
  matriz de 21 credenciales externas, pre-requisitos host, smoke
  autenticado, compuertas pre-prod y declaracion de riesgos residuales.
- **Fase G — Certificacion**: full-qa, verify_operator_ready, pre-commit,
  detect-secrets, stress 3x = 535 passed sin flakiness, todas verdes.

Suite final: **535 passed, 1 skipped, 20 deselected** (+10 vs 525 del
arranque de Fase 38).
Migraciones: **16** (head `202605160002`).
Compuertas: full-qa OK con guardas alembic + git diff; pre-commit Passed;
detect-secrets sin findings versionados; verify_operator_ready OK.

Declaracion: sin P0/P1 conocidos pendientes. Lista de riesgos residuales
declarada explicitamente en `findings.md` Fase 38. Sistema listo para
completar credenciales y comenzar uso real.

## 2026-05-16 - Fase 37 auditoria integral por capas iniciada

- Activada auditoria por capas solicitada por el operador para preparar la
  conexion total del stack en una ventana corta.
- Plan registrado en `task_plan.md` con alcance, metodo y criterios de cierre.
- `findings.md` inicializado con matriz de capas y estado pendiente.
- Baseline de entrada: rama `codex/fase-34-baseline-hardening`, git limpio antes
  de iniciar Fase 37, ultimo commit `ca742d4`, runtime core healthy.
- Auditoria documental inicial: 61 markdowns versionados activos (10.156
  lineas), excluyendo backups/snapshots/transcripciones ignoradas.
- Primer hallazgo corregido: Celery registra 14 tareas, no 11; se sincronizaron
  los claims vivos y se ruteo `run_deepagent_task` + `run_action_request` a la
  queue `agent_longrun`.
- Verificacion dirigida: `uv run pytest tests/test_celery_config.py -q` -> **3
  passed**; `uv run ruff check src/cognitive_os/workers/celery_app.py
  tests/test_celery_config.py` -> verde.
- Segundo hallazgo corregido: approvals humanas ahora son inmutables despues de
  salir de `pending`; intento de re-decidir devuelve 409.
- Verificacion dirigida de approvals/dispatch: **3 passed** y Ruff verde para
  `api/app.py` + `tests/test_actions.py`.
- Tercer hallazgo corregido: rechazo de approvals cierra `Job`/`ActionRequest`
  vinculados, y OpenShell aprobado se despacha realmente con payload ejecutable
  protegido en metadata del job.
- Verificacion dirigida ampliada: **4 passed**, Ruff verde, `mypy src` verde en
  108 source files.
- Frontend auditado: `npm run lint` y `npm run build` verdes; contrato
  `PublicConfigResponse` vs `PublicConfig` calza **66/66 campos**.
- Infra/runtime auditado: `docker compose ... config` OK y
  `infra/wait_for_services.sh` confirma Postgres/Redis/Weaviate/Neo4j healthy.
- Backend amplio post-cambios: `uv run pytest -m 'not integration and not slow'
  -q` -> **497 passed, 1 skipped, 20 deselected**; Ruff/format y `git diff
  --check` verdes.
- Cuarto hallazgo corregido: Alembic autogenerate excluye tablas runtime de
  LangGraph/PostgresSaver para que `alembic check` no proponga borrarlas.
  Nueva cobertura: `tests/test_alembic_autogenerate.py` (**2 passed**).
- `backend/scripts/verify_operator_ready.sh` ahora ejecuta tambien
  `uv run alembic check`, para que el drift de autogenerate sea compuerta real.
- Tests de integracion ejecutados con Docker/Tesseract disponibles: primer pase
  detecto incompatibilidad del fake OCR con `batch_insert_chunks`; corregido y
  verificado con `uv run pytest -m integration -q` -> **18 passed, 1 skipped,
  499 deselected**.
- Smoke autenticado final con JWT local admin/operator contra API viva:
  `/config/public`, `/health/dashboard`, `/actions/capabilities`, `/jobs` y
  `/approvals` respondieron **200**. Stack vivo: API, frontend, worker, beat y
  Kimi; Telegram omitido por `TELEGRAM_ENABLED=false`.
- Revision runtime ampliada: `/health/dashboard` queda `degraded` solo por
  `google_calendar`/`google_drive` en `blocked` al faltar
  `GOOGLE_TOKEN_DIR/token.json`; servicios core, workers y Kimi estan OK. Se
  mantuvo como bloqueo real (requiere OAuth manual del operador) y se ajustaron
  tests para impedir falsos verdes cuando una integracion habilitada esta
  incompleta.
- Hardening Gmail OAuth: `GmailRestReader` y `GmailLabelReader` ya no exponen
  paths locales del `token.json` en errores; el lector label tambien normaliza
  errores HTTP/JSON con redaccion de secretos y paths.
- Verificacion focalizada nueva: `uv run pytest tests/test_gmail_digest.py
  tests/test_health_dashboard.py -q` -> **19 passed**; Ruff focalizado y
  `git diff --check` verdes.
- Hardening Kimi WebBridge: navegacion del navegador real hereda
  `ENABLE_BROWSER_SSRF_CHECK`; mutaciones directas se bloquean si
  `KIMI_WEBBRIDGE_REQUIRE_APPROVAL=true`; produccion rechaza mutaciones Kimi con
  aprobacion deshabilitada.
- Verificacion focalizada Kimi/config: `uv run pytest tests/test_kimi_webbridge.py
  tests/test_config.py -q` -> **31 passed**; Ruff/format focalizados y mypy en
  `kimi_webbridge.py`/`config.py` verdes.
- Hardening ActionRequest/workers: dispatch aprobado ahora bloquea la fila con
  `FOR UPDATE`; workers duplicados que encuentran el request ya `running` salen
  sin marcar el job como `failed`; estados terminales `cancelled`/`rejected` se
  preservan en el job en vez de colapsar a fallo generico.
- Verificacion focalizada ActionRequest: `uv run pytest
  tests/test_action_request_workers.py
  tests/test_actions.py::test_queue_approved_action_request_locks_row_before_queue
  tests/test_actions.py::test_dispatch_action_request_enqueues_worker
  tests/test_actions.py::test_dispatch_action_request_does_not_enqueue_non_queued_status
  tests/test_celery_config.py -q` -> **8 passed**; Ruff focalizado verde.
- Hardening DB idempotency: nueva migracion
  `202605160001_action_request_idempotency_unique_index` agrega indice parcial
  UNIQUE `uq_action_requests_active_idempotency` para enforcement transaccional
  de la tupla `(action_type, requested_by, idempotency_key)` en estados
  activos. El modelo refleja el indice con `postgresql_where`.
- Verificacion DB: `uv run alembic upgrade head` aplica; `uv run alembic check`
  -> "No new upgrade operations detected"; `uv run pytest
  tests/test_alembic_autogenerate.py tests/test_actions.py -q` -> **52 passed**.
  Conteo vivo de migraciones actualizado a 15 en README/COGNITIVE_OS_GUIDE/
  PROJECT_GUIDE/docs/README.
- Hardening Action Plane idempotency: nuevo helper
  `ActionRequestService._find_active_idempotent_request` aplica dedup en la
  creacion para los 7 carriles `create_*_request` y los wrappers
  `_persist_preview_request`/`_persist_executable_request`. Un POST repetido
  con la misma tupla `(action_type, requested_by, idempotency_key)` mientras
  exista una fila activa devuelve esa fila sin crear duplicados.
- Verificacion focalizada idempotency: `uv run pytest tests/test_actions.py -q`
  -> **50 passed** (incluye nuevo
  `test_calendar_action_request_dedups_repeat_submissions`); suite amplia ->
  **513 passed, 1 skipped, 20 deselected**.
- Hardening RBAC: nuevo `APPROVAL_REQUIRE_FOUR_EYES` (default True) impide
  self-approval en `/approvals/{id}/approve|reject`. Mutaciones de memoria
  (`/deepagents/memory/proposals/{id}/approve|reject`,
  `/deepagents/memory/consolidate/run`) ahora exigen `require_admin_user`.
  `SETTINGS_REGISTRY_TABLE.md` regenerado para incluir el nuevo flag.
- Verificacion focalizada RBAC: `uv run pytest
  tests/test_actions.py::test_approval_self_decision_blocked_by_four_eyes
  tests/test_actions.py::test_approval_self_decision_allowed_when_four_eyes_disabled
  tests/test_admin_gated_endpoints.py tests/test_langsmith_access.py
  tests/test_config.py -q` -> **28 passed**; suite amplia
  `uv run pytest -m 'not integration and not slow' -q` -> **512 passed,
  1 skipped, 20 deselected**; Ruff/format/mypy focalizados verdes.
- Revision desde cero post-Fase 37: cerrados tres hallazgos nuevos
  (P1 approval-expiry, P2 system/info, P2 indice approvals).
  - **37.15** Reaper Celery `cognitive_os.reap_stale_approvals` agendado en
    beat cada hora; `APPROVAL_PENDING_MAX_HOURS=48` por defecto; cascada
    expired -> rejected en Job/ActionRequest ligados con AuditEvent y
    JobEvent.
  - **37.16** Nuevo `GET /system/info` con policy snapshot (cifrado,
    four-eyes, TTL approval, research backend, python/fastapi versions,
    started_at).
  - **37.17** Indice composito `ix_human_approvals_status_created_at` para
    listado y reaper. Conteo de migraciones a 16.
  - Suite final tras revision: **517 passed, 1 skipped, 20 deselected**;
    Ruff/format/mypy verdes; full-qa, verify_operator_ready, pre-commit y
    detect-secrets verdes.
- Cierre Fase 37 bloques 5-9 (runtime/frontend/observabilidad/stress/cert):
  - `full-qa.sh` reforzado con `alembic check` (tolerante a Postgres apagado)
    y `git diff --check` como compuerta dura. Ejecucion real verde con git
    diff sin warnings.
  - Frontend: lint+build verdes, todos los estados (`blocked|pending|queued|
    running|failed|rejected|completed`) ya cubiertos por `statusClass`.
  - Observabilidad: `_decide_approval` emite `AuditEvent`
    `approval.{status_value}` con actor + metadata, simetrico con Telegram.
  - Stress 3 corridas seguidas -> 513 passed cada una, sin flakiness, ~25-26s.
  - Cierre: `bash scripts/full-qa.sh` -> OK; `verify_operator_ready.sh` -> OK
    con head Alembic `202605160001`; `uvx pre-commit run --all-files` -> OK;
    `detect-secrets scan` -> `"results": {}`.
- Compuertas finales Fase 37 ejecutadas tras los commits:
  `bash scripts/full-qa.sh` -> OK; `uvx pre-commit run --all-files` -> OK;
  detect-secrets sobre `git ls-files` -> `results: {}`; `bash
  backend/scripts/verify_operator_ready.sh` -> OK con Alembic
  `202605150002 == 202605150002` y `alembic check` sin drift; Docker core
  sigue healthy en loopback.

## 2026-05-15 - Fase 36 pulido CI y QA completa

- `bash cognitive-os/scripts/full-qa.sh` ejecutado completo desde baseline:
  backend **492 passed, 1 skipped, 20 deselected**, ruff/format/mypy verdes,
  `npm ci`, lint y build frontend verdes.
- Workflow CI movido a `.github/workflows/ci.yml` en la raiz real del repo para
  que GitHub Actions lo ejecute; antes estaba en `cognitive-os/.github` y no era
  efectivo para este monorepo.
- CI ajustado al layout real (`cognitive-os/backend`, `cognitive-os/frontend`),
  cache paths correctos y `uv sync --frozen --extra openharness --group dev`
  alineado con `scripts/full-qa.sh`.
- Workflow parseado con PyYAML y `uvx pre-commit run --all-files` verde tras el
  movimiento.
- `backend/scripts/verify_operator_ready.sh` reforzado para sincronizar deps con
  OpenHarness, comprobar `ruff format`, ejecutar `npm ci` y fallar si Alembic no
  está en head. Verificación real del script: **492 passed, 1 skipped,
  20 deselected**, Alembic `202605150002 == 202605150002`, frontend lint/build OK.

## 2026-05-15 - Fase 35 baseline git seguro

- Creada rama `codex/fase-34-baseline-hardening` para primer baseline
  versionado.
- Escaneo `detect-secrets` sobre archivos versionables limpio (`results: {}`),
  usando `git ls-files --cached --others --exclude-standard` para excluir
  `.env`, backups, snapshots, caches y material local ignorado.
- Hooks reales con `uvx pre-commit run --all-files` en verde: large files,
  merge conflicts, end-of-file, trailing whitespace y `gitleaks`.
- Ajustado `check-added-large-files` a `--maxkb=1024` para permitir `uv.lock`
  sin relajar binarios grandes arbitrariamente.
- Fixtures de tests con patrones de credenciales fueron reescritas/allowlisted
  sin valores reales; `gitleaks` queda limpio.
- Verificacion adicional: `ruff check`, `ruff format`, `mypy`, Compose config,
  `git diff --check`, tests dirigidos afectados (**125 passed**) y tests
  captcha/maps (**26 passed**) verdes.

## 2026-05-15 - Fase 34 reconciliacion operativa local

- Base local migrada de `202605140001` a `202605150002 (head)`.
- Docker Compose reconciliado con la configuracion actual: Postgres, Redis,
  Weaviate HTTP/gRPC y Neo4j HTTP/Bolt quedan publicados solo en `127.0.0.1`.
- Contenedores verificados healthy tras recreacion no destructiva de Postgres,
  Weaviate y Neo4j; Redis continuo sin recreacion.
- `.gitignore` raiz blinda backups/snapshots, transcripciones recuperadas y
  `**/.claude/settings.local.json` para evitar commits accidentales de material
  local o sensible.
- Verificacion enfocada: `git diff --check` limpio; `git check-ignore -v`
  confirma reglas criticas; `uv run pytest tests/test_config.py
  tests/test_research_orchestrator.py
  tests/test_actions.py::test_action_request_payload_executable_is_encrypted_when_key_configured
  -q` -> **32 passed**.

## 2026-05-15 - Fase 33 RBAC + cifrado + research durable (cerrada)

- RBAC local endurecido: `create_access_token` emite roles normalizados,
  `AuthenticatedUser` expone `roles`, admin se concede por `AUTH_ADMIN_ROLES` o
  `ADMIN_USER_IDS`; ya no existe admin implícito cuando la lista queda vacía.
- `/langsmith/*` queda admin-gated por defecto (`LANGSMITH_ENDPOINTS_REQUIRE_ADMIN=true`)
  y acepta admin por rol JWT o ID explícito.
- `ActionRequest.payload_executable` se protege con sobre Fernet cuando
  `ACTION_PAYLOAD_ENCRYPTION_KEY` está configurado; producción exige
  `ACTION_PAYLOAD_ENCRYPTION_REQUIRED=true` y clave real. Filas históricas en
  claro se siguen aceptando sólo si el runtime no exige cifrado.
- Research Orchestrator tiene backend durable configurable:
  `RESEARCH_PERSISTENCE_BACKEND=memory|postgres`; producción exige `postgres`.
  Nueva tabla `research_runs` y migración `202605150002_research_run_records.py`.
- Frontend muestra `research_persistence_backend` en Configuración/Settings y el
  contrato `PublicConfig` quedó alineado.
- Docs/env actualizados: `.env.example`, `SETTINGS_REGISTRY_TABLE.md`, guías de
  seguridad, Action Plane, Runbook, checklist y guía maestra.
- Validación:
  - `uv run pytest -m 'not integration and not slow'` → **492 passed, 1 skipped,
    20 deselected**.
  - `uv run ruff check .` → pass.
  - `uv run ruff format --check .` → 201 files already formatted.
  - `uv run mypy src` → success en 108 source files.
  - `npm run lint` → pass.
  - `npm run build` → Next.js 16.2.6 build OK.
  - `docker compose --env-file .env.example -f infra/docker-compose.yml config --quiet` → pass.
  - `uv run alembic heads` → `202605150002 (head)`.
  - `git diff --check` → clean.

## 2026-05-15 - Fase 32 hardening comercial (cerrada)

- Cerrado el bloque P0/P1 posterior a Google operativo: endpoints directos de
  Calendar/Drive ahora son preview-only y rechazan `dry_run=false` con `409`; los
  writes reales pasan por `ActionRequest`, aprobación humana, Celery y audit.
- Endurecida producción: `ENABLE_GOOGLE_CALENDAR_WRITE` y
  `ENABLE_GOOGLE_DRIVE_WRITE` no pueden convivir con
  `REQUIRE_HUMAN_APPROVAL_FOR_EXTERNAL_ACTIONS=false`.
- Saneados errores OAuth/Drive/health para no exponer rutas locales, `token.json`
  ni tokens; health dashboard degrada componentes rotos sin tumbar el dashboard.
- Agendado `cognitive_os.reap_stuck_action_requests` en Celery beat cada 10
  minutos y routeado a queue `maintenance`.
- Infra Docker queda local-only: Postgres, Redis, Weaviate HTTP/gRPC y Neo4j
  HTTP/Bolt publican en `127.0.0.1`; `.env.example` usa URLs coherentes.
- PWA/frontend: Next.js suma headers de seguridad y `poweredByHeader=false`;
  `sw.js` usa cache versionado, update handshake y rutas API-like network-only;
  `PWA.tsx` muestra offline/update/install; `TopBar` mejora autofill/accesibilidad.
- Tests añadidos o ampliados: `test_frontend_static_assets.py`,
  `test_health_dashboard.py`, `test_celery_config.py`, `test_config.py`,
  `test_google_calendar.py`, `test_google_drive.py`, `test_google_oauth.py`.
- Validación:
  - `uv run pytest tests/test_google_calendar.py tests/test_google_drive.py tests/test_google_oauth.py tests/test_config.py tests/test_celery_config.py tests/test_health_dashboard.py -q` → **52 passed**.
  - `uv run pytest -m 'not integration and not slow'` → **484 passed, 1 skipped,
    20 deselected**.
  - `uv run ruff check .` → pass.
  - `uv run ruff format --check .` → 198 files already formatted.
  - `uv run mypy src` → success en 106 source files.
  - `docker compose --env-file .env.example -f infra/docker-compose.yml config --quiet` → pass.
  - `npm run lint` → pass.
  - `npm run build` → Next.js 16.2.6 build OK.
- Riesgo residual: `EXA_API_KEY` inline fue reemplazada por `{env:EXA_API_KEY}`;
  el operador debe rotar esa clave fuera de la sesión.

## 2026-05-15 - Fase 31 Google operativo (cerrada)

- Implementado el carril comercial Google sobre integraciones existentes:
  `MapsService` ahora devuelve rutas con tráfico, retraso estimado y link Google
  Maps; Drive gestiona carpeta de entregables `Cognitive OS Deliverables`;
  Calendar create y Drive upload se promueven a `ActionRequest` aprobables.
- Añadidos endpoints operativos: `/actions/calendar/events/request`,
  `/actions/drive/folders/ensure`, `/actions/drive/files/upload/request`.
  `/actions/capabilities` incluye `maps`, `google_calendar`, `google_drive` y
  `/config/public` expone solo flags no sensibles de Google.
- Añadida `GoogleOpsView` y navegación `googleOps` en frontend; conteos vivos:
  **118 endpoints REST**, **18 vistas frontend**, **14 migraciones Alembic**.
- Añadidos tests de lifecycle de `ActionRequestService` para
  `calendar_create_event` y `drive_upload_file` con fakes sin DB real ni secretos.
- Validación focalizada: `uv run pytest tests/test_actions.py -q` → **42 passed**.
- QA amplio final:
  - `uv run pytest -m 'not integration and not slow'` → **471 passed, 1 skipped,
    20 deselected**.
  - `uv run ruff check .` → All checks passed.
  - `uv run ruff format --check .` → 195 files already formatted.
  - `uv run mypy src` → Success: no issues found in 106 source files.
  - `npm run lint` → pass.
  - `npm run build` → Next.js 16.2.6 build OK.
  - `git diff --check` → clean.

## 2026-05-15 04:47 (hora Chile) — Barrido documental integral

- Ejecutada auditoría profunda con subagente `Explore` para verificar contra
  código real todos los conteos y descripciones que aparecen en los
  markdowns del proyecto. Datos confirmados:
  - Backend: **115 endpoints REST** (89 propios + 26 orquestación), 11
    tareas Celery distribuidas en 5 queues (`default`, `ingestion`,
    `agent_longrun`, `maintenance`, `mail`), 13 migraciones Alembic, 72
    archivos `tests/test_*.py`.
  - LLM por defecto: `deepseek-v4-pro` (DeepSeek V4 Pro) con base
    `https://api.deepseek.com`; secundario Kimi K2.6-code-preview; vision
    GLM-4.6v primario, Kimi 2.6 fallback.
  - Frontend: Next.js 16.2.6, React 19, ESLint 9.39.4, TypeScript 5.8;
    **17 vistas** en `app/views/*.tsx` incluida `AssistView`.
  - Infra: PostgreSQL 16+pgvector (puerto 5432 expuesto, pendiente bind
    privado), Redis 7-alpine (bind privado `127.0.0.1:6379` ya
    implementado), Weaviate 1.29.0 (`8081/50052`), Neo4j 5-community
    (`7474/7688`).
  - Cockpit `.opencode/`: **21 MCPs** configurados, **15 skills** (incluye
    `dual-memory-recall`, `huggingface-hub`, `kimi-webbridge`,
    `opencode-operator`, `memory-bank`), 7 subagentes y 7 comandos slash.
  - Memoria: Memory Bank MCP (`memory-bank/cognitive-os/`) y Supermemory
    activos vía dual-recall.
  - Snapshot QA persistente: **341 pytest passed, 1 skipped, 20
    deselected**; ruff/mypy/lint/build verdes; `git diff --check` clean;
    sin commits aún en `master`.
- Sincronizados los markdowns principales con el estado verificado y la
  fecha 2026-05-15 04:47 (hora Chile):
  - Raíz: `AGENTS.md`, `docs/SECURITY.md`,
    `docs/openchamber-cognitive-os.md`, `docs/opencode-agent-stack.md`.
  - `cognitive-os/`: `README.md`, `progress.md` (este archivo),
    `findings.md`, `task_plan.md`, `ACCEPTANCE_CHECKLIST.md`.
  - `cognitive-os/docs/`: 16 archivos (incluida la guía maestra
    `COGNITIVE_OS_GUIDE.md`).
  - Auxiliares: `cognitive-os/frontend/README.md`,
    `cognitive-os/scripts/README.md`.
  - Memory Bank: `memory-bank/cognitive-os/{activeContext,progress}.md`.
- No se modificó ningún archivo de código. Las carpetas `cognitive-os-snapshot-*`,
  `cognitive-os-backup-*` y `.openharness_upstream/` se preservan tal cual
  (son read-only por política de `AGENTS.md`).
- Pendientes Fase 29 (próximo bloque): auth/RBAC comercial multi-usuario,
  cifrado de `payload_executable` en `action_requests`, persistencia
  durable del orquestador de research (hoy in-memory), bind privado del
  puerto 5432 de PostgreSQL en `infra/docker-compose.yml`, completar
  variables `.env.local` faltantes (MAIL_IMAP_PASSWORD requiere input
  manual del usuario).

## 2026-05-14 - Hardening frontend y Assist UI

- Endurecido el manejo de JWT del frontend: el token local ya no se persiste en
  `localStorage`, el copy pide pegarlo sin prefijo `Bearer` y `ApiClient`
  normaliza tokens pegados con prefijo para evitar `Bearer Bearer ...`.
- Ajustado `ApiClient` para no enviar `Content-Type: application/json` en
  requests sin body, soportar `AbortSignal` en `GET`, exponer `PATCH`/`DELETE`
  tipados y ampliar `statusClass` para estados reales de mail/action/assist.
- Fortalecido `usePolledFetch` con `AbortController` y guardas contra respuestas
  obsoletas para evitar commits tardíos al cambiar de tab o filtro.
- Alineados tipos frontend con contratos backend de mail, action plane y assist;
  `MailInboxView` soporta `pending_send`/`MailSendResult` y `SandboxView` envía
  el `purpose` requerido por OpenShell.
- Añadida tab `Asistente` y vista `AssistView` para operar `/assist/tasks` y
  `/assist/notes`: crear/listar/filtrar/actualizar/borrar tareas y crear/listar/
  borrar notas personales.

## 2026-05-14 - Barrido documental y cola mail

- Continuada la normalización documental para reflejar estado actual: DeepSeek V4
  Pro como LLM base, Weaviate 1.29.0, 89 endpoints propios, 16 vistas frontend, mail
  personal GoDaddy/Gmail-label, Kimi WebBridge y ejecutables de escritorio.
- Corregido `scripts/dev_worker.sh` para escuchar también la queue Celery `mail`,
  alineando operación manual con el routing real de `sync_personal_mail`.
- Actualizados `COGNITIVE_OS_GUIDE.md`, `frontend/README.md`, `scripts/README.md`,
  `ACCEPTANCE_CHECKLIST.md`, `SECURITY.md`, `OPERATOR_VARIABLE_CHECKLIST.md`,
  `IMPROVEMENT_EXECUTION_PLAN.md`, `ACTION_PLANE.md` y docs DeepAgents/OpenHarness
  relacionados.

## 2026-05-14 - Cierre Fase 28 (bloque 1)

- Verificado wiring `AssistView`: tab `assist` en `Tab`, render en `page.tsx`,
  entrada en `Sidebar.tsx`, consumo de `/assist/tasks` y `/assist/notes`.
- Añadido `backend/tests/test_mail_api.py` con `_FakeMailService` que mockea
  `PersonalMailService`. 7 tests pasan: auth requerido, status/sync,
  filtro `pending_send`, edit reply, approve-send con `MailSendResult`,
  fallo SMTP → 409 redactado, 404 cuando falta mensaje.
- QA final del bloque:
  - `uv run pytest -m 'not integration and not slow'` → **341 passed,
    1 skipped, 20 deselected**.
  - `uv run ruff check .` y `uv run ruff format --check .` verdes (171 files).
  - `uv run mypy src` Success sobre 95 source files.
  - `npm run lint` 0 warnings, `npm run build` Next.js 16.2.6 OK.
  - `git diff --check` clean.
- `task_plan.md` Fase 27 → complete, Fase 28 → in_progress con resultado
  parcial y pendientes comerciales documentados (auth/RBAC, cifrado
  `payload_executable`, durable research, bind privado de DB en infra,
  variables `.env.local` faltantes).

## 2026-05-14 - Primer bloque de optimización comercial

- Ejecutada revisión desde cero con subagentes de arquitectura, frontend,
  seguridad y tests. Hallazgos principales: auth/RBAC comercial pendiente,
  research orchestrator in-memory, `payload_executable` sin cifrado, mail sin
  tests suficientes, `/config/public` corto para sala de máquinas, wrappers MCP
  con secretos inline y puertos DB expuestos como pendiente de infra.
- Saneados secretos inline en `opencode.json` local y wrappers `.opencode/bin/*`;
  ahora usan `{env:VAR}` o variables de entorno sin fallback secreto. La
  contraseña de OpenChamber fue retirada del Markdown.
- Endurecidas reglas OpenCode locales: lectura por bash (`cat/find/rg/grep`) pasa
  a `ask` y se añadieron denies para comandos destructivos comunes.
- Backend: `/config/public` expone más flags no sensibles para sala de máquinas
  (mail, OpenHarness, GoDaddy, browser, LangSmith, Telegram, documentos).
- Backend mail: añadidos `MAIL_IMAP_TIMEOUT_SECONDS` y
  `MAIL_SMTP_TIMEOUT_SECONDS`, errores de proveedor redactados y estado
  `pending_send` antes de SMTP.
- Frontend: contratos actualizados para action types reales, estados de mail,
  `pending_send`, `MailSendResult`, `ApiClient.delete`, requests sin body sin
  `Content-Type`, polling con abort y JWT en memoria de sesión en vez de
  `localStorage`.
- QA: ruff pass, mypy pass, targeted tests `20 passed`, full backend
  `334 passed, 1 skipped, 20 deselected`, frontend lint pass, frontend build
  pass, `git diff --check` pass.

## 2026-05-14 - Inicio mail multicuenta personal

- Iniciada Fase 26 para correo personal multicuenta.
- Alcance elegido: GoDaddy IMAP/SMTP como cuenta emisora principal,
  Gmail label `TODOS` como entrada secundaria, propuestas de respuesta por
  escrito y envio solo con aprobacion humana.
- Seguridad: la contrasena indicada por el usuario se usara solo en `.env`
  local ignorado por git; no se escribira en docs, plan ni memoria.

## 2026-05-14 - Mail multicuenta primer corte funcional

- Agregados modelos `MailAccount`, `MailMessage`, `MailSendLog` y migracion
  `202605140001_mail_accounts_messages.py`.
- Agregados settings `MAIL_*` para GoDaddy IMAP/SMTP, polling, default sender
  y aprobacion obligatoria.
- Implementado paquete `cognitive_os.mail`: IMAP, SMTP, lector Gmail label,
  clasificador/proponente heuristico y servicio principal.
- Agregados endpoints `/mail/status`, `/mail/sync`, `/mail/sync/dispatch`,
  `/mail/messages`, `/mail/messages/{id}`, `/mail/messages/{id}/reply`,
  `/mail/messages/{id}/ignore`, `/mail/messages/{id}/approve-send`.
- Agregado worker Celery `cognitive_os.sync_personal_mail` en queue `mail` y
  beat por `MAIL_POLL_INTERVAL_SECONDS`.
- Agregada vista frontend `MailInboxView` y tab `mail`.
- Migracion aplicada localmente; smoke real contra GoDaddy IMAP: 25 mensajes
  leidos, 25 insertados, 4 clasificados como importantes con propuesta.
- Validacion: backend ruff pass, backend mypy pass, backend pytest
  `329 passed, 1 skipped, 20 deselected`, frontend lint pass, frontend build pass.

## 2026-05-14 - Ejecutables de escritorio

- Actualizado `/home/jgonz/Escritorio/cognitive-os.sh` para incluir la queue
  Celery `mail` y gestionar Kimi WebBridge junto al stack principal.
- Creados accesos ejecutables en `/home/jgonz/Escritorio`: `Levantar Cognitive OS`,
  `Reiniciar Cognitive OS`, `Detener Cognitive OS` y `Estado Cognitive OS`, con
  variantes `.sh` y `.desktop`.
- Verificado con reinicio real: Docker stack, migraciones, API, Celery worker,
  Celery beat, frontend y Kimi quedaron corriendo; Telegram queda omitido porque
  `TELEGRAM_ENABLED=false`.

## 2026-05-13 - OpenChamber LAN Access

- Installed OpenChamber CLI (`@openchamber/web` 1.10.4) globally.
- Added `~/.local/bin/openchamber-cognitive-os` wrapper to start OpenChamber
  against the Cognitive OS workspace and the hardened OpenCode wrapper.
- Added and enabled the user systemd service
  `openchamber-cognitive-os.service` on `0.0.0.0:3000`, with managed OpenCode
  on `127.0.0.1:4095`.
- Enabled user lingering and set OpenChamber's active project to Cognitive OS.
- Added `docs/openchamber-cognitive-os.md` with usage, LAN URL, password, and
  validation commands.
- Updated the OpenChamber UI password to the current user-provided value.

## 2026-05-13 - Hugging Face MCP

- Added Hugging Face MCP as remote server `huggingface` at
  `https://huggingface.co/mcp` with bearer-token authentication.
- Hardened the user-level OpenCode wrapper so MCP credentials are exported
  before startup and do not depend on `.env.local` being sourced.
- Added `huggingface-hub` skill for model, dataset, Space, and Hub-docs
  research.

## 2026-05-13 - Memory Bank MCP

- Added Memory Bank MCP using `@allpepper/memory-bank-mcp@latest` from
  `alioshr/memory-bank-mcp`.
- Created workspace-local memory root at `memory-bank/` with project namespace
  `memory-bank/cognitive-os/`.
- Added `MEMORY_BANK_ROOT` to ignored local env and placeholder docs.
- Added a `memory-bank` OpenCode skill describing when to use Memory Bank vs
  Supermemory, planning files, and runtime memory.
- Replaced inline secrets in project `opencode.json` with `{env:...}`
  placeholders so credentials remain only in ignored env files.

## 2026-05-13 - Dual Memory Recall Skill

- Added `dual-memory-recall` skill so memory requests consult both Supermemory
  and Memory Bank before answering.
- Updated root `AGENTS.md` to make the dual-memory behavior explicit for future
  OpenCode sessions.
- Saved the user's dual-memory preference in Supermemory for cross-session
  recall.

## 2026-05-13 — Guía maestra "desde cero" (`docs/COGNITIVE_OS_GUIDE.md`)

- Creado `docs/COGNITIVE_OS_GUIDE.md`: documento único, exhaustivo y
  auto-contenido para que cualquier persona sin contexto pueda entender y
  operar Cognitive OS. Secciones: qué es / para qué sirve y para qué no /
  casos de uso / mapa mental ASCII / recorrido completo de una petición /
  componentes del backend uno por uno (incluyendo el catálogo de los 81
  endpoints agrupado por dominio) / las 16 vistas del frontend (qué hacen,
  cómo usarlas) / los 25+ comandos del bot Telegram con ejemplos / fusión
  OpenHarness + DeepAgents en `research` / Document Analysis (legal) / Action
  Plane y guardrails / memoria, skills y aprobaciones / arranque paso a paso
  + JWT local + QA reproducible / variables de entorno (críticas vs
  opcionales) / credenciales/tokens/APIs faltantes con instrucciones reales
  de obtención por proveedor / operación día a día (backups, restore,
  monitorización) / troubleshooting común / roadmap (lo que funciona vs lo
  que falta) / apéndices de comandos rápidos.
- Verificación 1:1 con código antes de escribir: `app.py` (catálogo de
  endpoints reales), `telegram_bot.py` (comandos `cmd_*` reales), 15
  archivos `frontend/app/views/*.tsx`, `core/config.py` (todas las
  variables citadas existen), `OPENHARNESS_FUSION.md` (bridge y precedencia
  consistentes con `_execute_engine_blocking`).
- Enlaces cruzados: la guía referencia 12 documentos hermanos y se enlaza
  desde `README.md` raíz (sección "Leer Primero") y `docs/README.md`
  (sección "Leer Primero" + tabla "Documentación Por Área").
- No se modificó ningún archivo de código: solo documentación.

## 2026-05-13 — Markdown sweep final (todos los docs reflejan código real)

- Auditados los 26 markdowns del proyecto (raíz + `docs/` + READMEs auxiliares
  + 8 SKILL.md core). Todos llevan ahora la cabecera **"Estado actual
  (2026-05-13)"** consistente y referencias verificables al código.
- `docs/README.md`: añadida fila `IMPROVEMENT_EXECUTION_PLAN.md` en la tabla
  por área y descripciones más precisas por documento.
- `docs/DEEPAGENTS_INTEGRATION.md`: lista completa de tools reales expuestas
  por `build_deepagent_tools` (faltaban `list_available_skills`, `read_skill`,
  `get_relevant_memory`, `propose_memory_update`).
- `docs/ACTION_PLANE.md`: cabecera de estado con la matriz exacta de
  capacidades con ejecución real (`computer_organize`, `document_generate`,
  `browser_preview`, `browser_interactive`) vs preview-only (Gmail, GoDaddy
  por defecto).
- `docs/IMPROVEMENT_EXECUTION_PLAN.md`: Fase B marcada como **cerrada**
  (existe `test_settings_registry_table_markdown_matches_generated_body`).
- `docs/PERSONAL_ASSISTANT_ROADMAP.md`, `docs/DOCUMENT_ANALYSIS_AGENT.md`,
  `docs/DEEPAGENTS_SKILLS_MEMORY.md`: cabecera de estado y enlaces precisos.
- `README.md` raíz: snapshot QA actual y comando exacto de `full-qa.sh`.
- `frontend/README.md`: 16 vistas reales, Next.js 16.2.6, comandos `npm ci`
  preferidos.
- `scripts/README.md`: bloques bootstrap/backups/calidad bien separados,
  comando completo del `full-qa.sh` 1:1 con el script.
- `storage/deepagents/memory/README.md` y `.../skills/user/README.md`:
  contrato de propuestas + aprobación + layout exacto de directorios.
- `experiments/openshell-deepagent/README.md`: aclara distinción con
  OpenHarness.
- `ACCEPTANCE_CHECKLIST.md`: snapshot QA actualizado a 2026-05-13 (329 passed)
  e items adicionales para el bridge OpenHarness y `SETTINGS_REGISTRY_TABLE`.
- `docs/SETTINGS_REGISTRY_TABLE.md`: regenerado vía
  `uv run python scripts/dump_settings_registry.py --out ../docs/SETTINGS_REGISTRY_TABLE.md`.
- Verificación cruzada: `rg -i recallium` → 0 hits en todo el proyecto.
  `pytest 329 passed`, `ruff check .` y `ruff format --check .` y `mypy src`
  verdes.

## 2026-05-13 — Endurecimiento final y QA verde

- **Ruff strict y format**: arreglado `E501` en `core/config.py` (descripciones
  OpenHarness reformateadas) y reescritura sin `E501` de la migración
  `alembic/versions/202605120006_personal_tasks_notes.py`. `uv run ruff check
  .` y `uv run ruff format --check .` pasan globalmente.
- **mypy strict**: refactor del preset `research` en
  `integrations/openharness_research.py` para eliminar lambdas con tipo
  inferido a `unknown` (lista directa de instancias). `uv run mypy src` ok.
- **Aislamiento de event loop**: nuevo `_execute_engine_blocking` en el bridge
  OpenHarness — `ThreadPoolExecutor(max_workers=1)` + event loop dedicado por
  ejecución. Antes `asyncio.run()` podía romper si un caller estaba en async;
  ahora siempre funciona y los warnings de loop cerrado se eliminan con
  `shutdown_asyncgens` y `loop.close()`.
- **Precedencia de skips coherente**: en `run_openharness_research_sync`,
  primero `disabled`, luego `openharness_not_installed`, luego `empty_query`.
- **`.env.example`**: nuevo bloque "OpenHarness fusion (optional, research
  route)" con todos los `OPENHARNESS_*` y sus defaults documentados.
- **Tests añadidos** en `backend/tests/test_openharness_research.py`:
  precedencia `disabled` vs `openharness_not_installed`, `empty_query` cuando
  está habilitado, y aislamiento dentro de un event loop activo.
- **QA final**: `uv run ruff check . && uv run ruff format --check . && uv run
  mypy src && uv run pytest -q` → **329 passed, 1 skipped, 20 deselected**.
  Frontend: `npm run lint` y `npm run build` ok (Next.js 16.2.6).

## 2026-05-13 — Fusión OpenHarness + DeepAgents documentada y verificada

- Implementación: `cognitive_os.integrations.openharness_research`
  (`OpenHarnessResearchResult`, `resolve_openharness_cwd`, `build_tool_registry`,
  `run_openharness_research_sync`) y consumo en
  `cognitive_os.agents.graph.research_node` (`prelude_merge` / `short_circuit`).
- DeepAgent integra el preludio vía `build_research_user_message_content`
  (`cognitive_os.deepagents.research_deepagent`) cuando `task.metadata` trae
  `openharness_prelude`.
- Presets de toolkit (`minimal`, `research`, `full`) y modo de workspace
  (`deepagent_mirror`, `sandbox`) configurables por env (`OPENHARNESS_*` en
  `docs/SETTINGS_REGISTRY_TABLE.md`).
- Tests: `backend/tests/test_research_openharness_priority.py` (modos +
  metadata + helper de mensaje); `backend/tests/test_openharness_research.py`
  (skip / disponibilidad).
- Documentación: nueva guía `docs/OPENHARNESS_FUSION.md`; README,
  `docs/README.md`, `ARCHITECTURE.md`, `PROJECT_GUIDE.md`,
  `DEEPAGENTS_INTEGRATION.md`, `RUNBOOK.md`, `OPERATOR_VARIABLE_CHECKLIST.md`,
  `SECURITY.md`, `ACCEPTANCE_CHECKLIST.md` y los `SKILL.md` core enlazan al
  modelo de fusión.
- Corrección README: el script `cognitive-os` es un *bootstrap* (`__main__.main`)
  que sólo logea; el servidor real arranca con `uv run uvicorn cognitive_os.api.app:app`.

## 2026-05-13 - Web/GitHub MCP Expansion

- Added local secret env vars for Tavily, Brave Search/Answer/Free, Exa, and
  GitHub MCP without writing secrets to versioned files.
- Added OpenCode MCP entries for Tavily, Brave Search, GitHub, grep.app,
  DeepWiki, and Exa.
- Added Tavily and Exa wrappers under `.opencode/bin/` so remote MCP URLs are
  built from env at runtime, not hardcoded in `opencode.json`.
- Added `web-research-mcps` skill with routing rules for Tavily, Brave, Exa,
  grep.app, DeepWiki, and GitHub.

## 2026-05-13 - Perplexity Search/Grounding

- Rotated the local `PERPLEXITY_API_KEY` in ignored env files without adding it
  to versioned files.
- Confirmed the backend already has Perplexity Sonar wired through the
  multi-provider web search client and `WEB_SEARCH_ENABLED=true` in runtime env.
- Enabled `WEB_SEARCH_ENABLED=true` in root `.env.local` for OpenCode-launched
  runtime commands.
- Added Perplexity placeholders to the OpenCode `.env.local.example` and the
  OpenCode stack documentation.
- Added a persistent user wrapper at `~/.local/bin/opencode` so terminal
  launches load the workspace `.env.local` automatically before opening the UI.

## 2026-05-12

- Read the installed `planning-with-files-es` skill from disk and adopted its workflow manually.
- Installed `planning-with-files` base variant as an additional option with stronger plan attestation features.
- Created planning files in the active project root:
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
- Paused Gmail connector installation because the authorization browser hung for the user.
- Continued with local project hardening path; Gmail will be handled as a first-class OAuth/API integration in Cognitive OS rather than blocking on Codex MCP auth.

## Baseline Already Collected

- Backend tests passed before edits: 144 passed, 1 skipped, 19 deselected.
- Frontend lint passed before edits.
- Ruff failed before edits in `backend/src/cognitive_os/core/config.py`.

## Next Immediate Work

1. Re-read the plan before code decisions.
2. Fix existing Ruff issues in config.
3. Implement safe action-plane primitives for:
   - browser/computer capability status
   - filesystem organization proposals
   - Gmail read/send policy boundary
   - GoDaddy API policy boundary
4. Add tests and docs.

## 2026-05-12 - Action Plane First Pass

- Fixed baseline Ruff issues in `backend/src/cognitive_os/core/config.py`.
- Added disabled-by-default computer action settings to config and `.env.example`.
- Added backend action modules:
  - `cognitive_os.actions.browser`
  - `cognitive_os.actions.computer`
  - `cognitive_os.actions.mail`
  - `cognitive_os.actions.domains`
  - shared schemas and policy helpers
- Added API endpoints:
  - `GET /actions/capabilities`
  - `POST /actions/browser/validate`
  - `POST /actions/computer/organize/preview`
  - `GET /actions/gmail/status`
  - `POST /actions/gmail/query/preview`
  - `GET /actions/godaddy/status`
  - `POST /actions/godaddy/dns/preview`
- Added tests in `backend/tests/test_actions.py` and config assertions.
- Updated frontend config typing and settings display for `enable_computer_actions`.
- Added `docs/ACTION_PLANE.md` and linked the action plane from README,
  architecture, runbook and security docs.
- Added Action Plane status display to frontend Settings.
- Added `action-plane` to the `/agents` operational inventory.

## 2026-05-12 - Verification

- Backend full tests: 154 passed, 1 skipped, 19 deselected.
- Backend Ruff check: pass.
- Backend Ruff format check: pass.
- Backend mypy: pass.
- Frontend lint: pass.
- Frontend build: pass.

## 2026-05-12 - Documentation Normalization Started

- Re-read planning files before continuing.
- Markdown planning files confirmed as:
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
- Added Phase 6 for documentation normalization and canonical markdown map.

## 2026-05-12 - Documentation Normalization Completed

- Added `docs/README.md` as documentation index.
- Added `docs/PROJECT_GUIDE.md` as the canonical simple + technical guide.
- Updated root `README.md` with "Leer Primero" and planning-file distinction.
- Updated `frontend/README.md`, `scripts/README.md`, and
  `docs/DEEPAGENTS_INTEGRATION.md`.
- Deleted obsolete root-level `explicacion_sistema_cognitive_os.md` after
  migrating its useful explanation into `docs/PROJECT_GUIDE.md`.
- Updated `ACCEPTANCE_CHECKLIST.md` with automated verification, action-plane
  acceptance and documentation status.

## 2026-05-12 - Final Verification After Documentation Cleanup

- Backend full tests: 154 passed, 1 skipped, 19 deselected.
- Backend Ruff check: pass.
- Backend Ruff format check: pass.
- Backend mypy: pass.
- Frontend lint: pass.
- Frontend build: pass.

## 2026-05-12 - Phase 8 Started

- Added Phase 8 to `task_plan.md`.
- Decision: implement persistent Action Requests before adding real browser,
  Gmail or GoDaddy execution.
- First real executor target: `computer_organize`, because it can be safely
  tested on temporary directories and remains disabled/dry-run by default in
  normal configuration.

## 2026-05-12 - Phase 8 Completed

- Added `ActionRequest` database model and Alembic migration with status/type
  constraints and indexes for operational listing.
- Added action request schemas and service lifecycle:
  - create persistent `computer_organize` request
  - link `HumanApproval` and `Job`
  - queue only approved requests
  - execute via Celery
  - record result/error and audit events
- Added real `computer_organize` execution guarded by config, allowed roots,
  symlink/file checks and destination validation.
- Added API endpoints for creating/listing/getting/dispatching action requests.
- Updated the Approvals UI so approved `execute_action_request` items attempt
  dispatch automatically.
- Updated Settings UI with recent action requests.
- Updated stable docs and acceptance checklist to reflect the new lifecycle.
- Verification:
  - `uv run pytest`: 159 passed, 1 skipped, 19 deselected.
  - `uv run pytest tests/test_actions.py`: 14 passed.
  - `uv run ruff check .`: pass.
  - `uv run ruff format --check .`: pass.
  - `uv run mypy src`: pass.
  - `npm run lint`: pass.
  - `npm run build`: pass.

## 2026-05-12 - Phase 9 Completed

- Refactored `ActionRequestService` with shared helper `_persist_preview_request`
  to keep persistence consistent and remove duplication.
- Added `create_browser_navigation_request`, `create_gmail_query_request`, and
  `create_godaddy_dns_change_request` to persist preview-only `ActionRequest`s
  for browser, Gmail and GoDaddy with audit events.
- Added `cancel_action_request` to safely cancel a non-running, non-final
  request, marking the linked job as cancelled and logging audit.
- Extended `list_action_requests` with `action_type` and `status` filters.
- API surface added:
  - `POST /actions/browser/request`
  - `POST /actions/gmail/query/request`
  - `POST /actions/godaddy/dns/request`
  - `POST /actions/requests/{id}/cancel`
  - `GET /actions/requests` now accepts `action_type` and `status` filters
    (alias `status` via `Annotated[..., Query(alias="status")]`).
- Added 6 new tests in `tests/test_actions.py` (now 20 total, all green).
- Updated `docs/ACTION_PLANE.md` and `ACCEPTANCE_CHECKLIST.md` with the new
  endpoints and acceptance items.
- Verification:
  - `uv run pytest`: 165 passed, 1 skipped, 19 deselected.
  - `uv run pytest tests/test_actions.py`: 20 passed.
  - `uv run ruff check .`: pass.
  - `uv run ruff format --check .`: pass.
  - `uv run mypy src`: pass.
  - `npm run lint`: pass.
  - `npm run build`: pass.

## 2026-05-12 - Phase 10 Completed (Document Writers)

- Added document generation as a first-class `ActionRequest` action type
  (`document_generate`) supporting DOCX/XLSX/PPTX.
- New module `backend/src/cognitive_os/actions/documents.py` with
  `DocumentActionService`:
  - `status()` reports `disabled|configured|ready` based on
    `ENABLE_DOCUMENT_GENERATION` and presence of `python-docx`, `openpyxl`
    and `python-pptx`.
  - `build_preview()` rejects absolute paths, parent-references, empty
    filenames and any output not inside `DOCUMENT_OUTPUT_ROOT`. Returns
    resolved path, `estimated_blocks` and blocking reason if any.
  - `execute()` writes the document atomically using the provider library,
    and deletes + rejects the file if it exceeds `DOCUMENT_MAX_SIZE_BYTES`.
- `actions/service.py`:
  - `create_document_generate_request` persists the `ActionRequest` with
    `pending_approval` status, creating linked `Job` + `HumanApproval` so the
    Celery worker only runs it after explicit human approval.
  - `_execute` dispatches `document_generate` to `DocumentActionService.execute`.
- New API endpoints:
  - `GET /actions/documents/status`
  - `POST /actions/documents/preview`
  - `POST /actions/documents/request`
- `GET /actions/capabilities` now includes `documents`.
- Settings: `ENABLE_DOCUMENT_GENERATION`, `DOCUMENT_OUTPUT_ROOT`,
  `DOCUMENT_MAX_SIZE_BYTES`.
- DB: Alembic migration extends the `ActionRequest.action_type` check
  constraint with `document_generate`.
- Mypy config: `openpyxl`, `pptx` added to `ignore_missing_imports`. The
  `# type: ignore[import-untyped]` on `docx` was removed since stubs are
  shipped by `python-docx`.
- Tests: 7 new tests in `tests/test_actions.py` covering disabled, path
  traversal, DOCX/XLSX/PPTX real writes, size limit and the endpoint
  fan-out. `test_action_capabilities_endpoint_requires_auth` updated to
  include `documents`.
- Verification:
  - `uv run pytest`: 172 passed, 1 skipped, 19 deselected.
  - `uv run pytest tests/test_actions.py`: 27 passed.
  - `uv run ruff check src tests`: pass.
  - `uv run ruff format --check src tests`: pass.
  - `uv run mypy --strict src`: pass.
  - `npm run lint`: pass.
  - `npm run build`: pass.

## 2026-05-12 - Fase 11: Browser headless preview (Playwright opt-in)

- Implemented new action type `browser_preview` to navigate allow-listed
  URLs in headless mode without persistent cookies and return title +
  optional screenshot. Designed as **opt-in**: Playwright is not installed
  automatically; when missing, the executor blocks with a clear reason.
- New module `backend/src/cognitive_os/actions/browser_preview.py`:
  - `BrowserPreviewProvider` Protocol + `BrowserPreviewProviderResult`
    value object for pluggable providers (real or test fakes).
  - Default `PlaywrightBrowserPreviewProvider` uses `sync_playwright`,
    Chromium headless, `wait_until`, `page.title`, `page.screenshot`.
  - `BrowserPreviewService.validate` enforces enable flag, headless
    requirement and `validate_allowed_browser_domain`.
  - `BrowserPreviewService.execute` resolves the screenshot path inside
    `BROWSER_SCREENSHOT_DIR`, calls the provider, enforces
    `BROWSER_SCREENSHOT_MAX_BYTES` and deletes the file if oversize.
- `actions/service.py`:
  - `create_browser_preview_request` persists the `ActionRequest` with
    `pending_approval` (or `blocked` if validation fails), creating linked
    `Job` + `HumanApproval` so Celery only runs after explicit approval.
  - `_execute` dispatches `browser_preview` to `BrowserPreviewService.execute`.
- New API endpoint `POST /actions/browser/preview/request`.
- Settings: `BROWSER_SCREENSHOT_DIR`, `BROWSER_NAVIGATION_TIMEOUT_MS`,
  `BROWSER_SCREENSHOT_MAX_BYTES`.
- DB: Alembic migration `202605120002_action_requests_browser_preview.py`
  extends the `ActionRequest.action_type` check constraint with
  `browser_preview`.
- Tests: 6 new tests in `tests/test_actions.py` cover disabled, non
  allow-listed domain, provider missing, real fake-provider execution,
  oversize screenshot rejection (file deleted) and the endpoint fan-out.
  Tests inject providers via factory so no real browser/network is used.
- Verification:
  - `uv run pytest`: 178 passed, 1 skipped, 19 deselected.
  - `uv run pytest tests/test_actions.py`: 33 passed.
  - `uv run ruff check src tests`: pass (one quoted-annotation auto-fix applied).
  - `uv run ruff format --check src tests`: pass.
  - `uv run mypy --strict src`: pass.
  - `npm run lint`: pass.
  - `npm run build`: pass.

## 2026-05-12 - Fase 20: Ops hardening

5 superficies defensivas endurecidas, 31 tests nuevos. Suite total: **270 passed** (+31).

### Cambios

1. **XLSX cell sanitization (formula injection)**: `_sanitize_xlsx_cell` prepara con apostrofo cualquier valor cuyo primer caracter sea `=`/`+`/`-`/`@` (OWASP CSV injection guidance). Aplicado en `_write_xlsx` para titulo, headers y rows. Numeros/booleanos/None pasan sin tocar.

2. **SSRF protection (DNS resolve + bloqueo de IPs privadas)**: nuevo `validate_browser_target_ip(hostname, resolver=...)` que rechaza loopback (127/8, ::1), private (10/8, 172.16/12, 192.168/16), link-local (169.254/16, fe80/10), reserved, multicast y unspecified (0.0.0.0). Setting nuevo `ENABLE_BROWSER_SSRF_CHECK=true` (default ON) gatea la resolucion. `BrowserPreviewService.validate` y `BrowserInteractiveService.validate` (y cada `navigate` step) pasan `resolve_ip=self._settings.enable_browser_ssrf_check`. Tests pueden desactivar via `Settings(enable_browser_ssrf_check=False)`.

3. **Reaper de action_requests stuck en running**: nuevo `ActionRequestService.reap_stuck_running(max_minutes=...)` que busca rows con `status="running"` y `updated_at < now - threshold`, las marca `failed` con reason explicita, propaga al Job linkeado (si no esta terminal) y emite `AuditEvent` con actor `system.reaper`. Setting `ACTION_REQUEST_RUNNING_MAX_MINUTES=60` (default). Nueva Celery task `cognitive_os.reap_stuck_action_requests` (no auto-scheduled; el operador la engancha a beat cuando este listo).

4. **Silent excepts -> structlog warnings**: `web_indexer._index_blocking` y `LocalReranker._try_model_scores`/`_load_model` ya no hacen `except: pass`. Ahora loggean con `structlog` campos `error_type`, `error`, `query_length`/`model_name`, etc. La degradacion sigue siendo silenciosa para el usuario, pero ahora deja trazo grep-able.

5. **Tokenizer reranker con tildes y stopwords**: `_lexical_score` usaba split por espacio sobre lowercase, lo que era ~random para queries en español. Nuevo `_tokenize` que (a) hace NFKD + ascii ignore para colapsar tildes (`evaluación` -> `evaluacion`), (b) split en `[a-z0-9]+`, (c) descarta tokens < 3 chars, (d) filtra una stoplist español+ingles. Sin cambios para el cross-encoder real cuando esta disponible; solo mejora el fallback.

### Tests (31 nuevos)

- 8 XLSX sanitization (parametrizados sobre prefijos peligrosos + tipos non-string)
- 11 SSRF (8 IPs privadas/loopback, 1 publica ok, 1 OSError, 1 resolver vacio)
- 2 DNS rebinding via validate_allowed_browser_domain
- 4 tokenizer (diacriticos, stopwords, tokens cortos, puntuacion)
- 1 reaper smoke

### Verificacion

| Check | Resultado |
|---|---|
| Backend pytest | **270 passed**, 1 skipped, 19 deselected (era 239) |
| Backend ruff check | pass |
| Backend ruff format | 136 files |
| Backend mypy --strict | 77 source files, no issues |
| Frontend lint | pass |
| Frontend build | pass |

### Archivos modificados

- `backend/src/cognitive_os/actions/documents.py` (_sanitize_xlsx_cell + aplicacion en _write_xlsx)
- `backend/src/cognitive_os/actions/policy.py` (validate_browser_target_ip, resolve_ip kwarg)
- `backend/src/cognitive_os/actions/browser_preview.py` (resolve_ip via settings flag)
- `backend/src/cognitive_os/actions/browser_interactive.py` (resolve_ip via settings flag, en initial url y cada navigate step)
- `backend/src/cognitive_os/actions/service.py` (reap_stuck_running)
- `backend/src/cognitive_os/workers/tasks.py` (reap_stuck_action_requests_task)
- `backend/src/cognitive_os/core/config.py` (enable_browser_ssrf_check, action_request_running_max_minutes)
- `backend/src/cognitive_os/memory/web_indexer.py` (structlog warning)
- `backend/src/cognitive_os/memory/reranker.py` (structlog + _tokenize Spanish-aware + STOPWORDS)
- `backend/tests/test_phase20_ops_hardening.py` (31 tests)

## 2026-05-12 - Fase 17: Browser interactivo + vision multimodal

El usuario pidio "navegar con vision y headless". Fase 17 cierra la brecha entre la navegacion single-shot (`browser_preview`) y un agente que realmente interactua con paginas.

### Cambios

- Nuevo `ActionType` `browser_interactive` con migracion `202605120004`.
- Schema `BrowserStep` con kinds: `navigate`, `click`, `fill`, `scroll`, `wait`, `screenshot`, `analyze`.
- Schema `BrowserInteractiveRequest` (max 24 steps) y `BrowserInteractiveExecutionResult` con trace por-step (status, duration_ms, screenshot_path, analysis).
- Modulo nuevo `actions/browser_interactive.py`:
  - `BrowserInteractiveService` con doble Protocol (Provider + VisionAnalyzer) inyectables.
  - Validacion exhaustiva PRE-launch: enable flag, headless flag, allow-list de dominios (incluye re-validacion de cada `navigate`), CSS selector regex, wait cap (10s), prompt requerido en analyze.
  - `PlaywrightBrowserInteractiveProvider` implementa los 7 step kinds con `sync_playwright()`.
  - `ChatVisionAnalyzer.from_settings(...)` construye un default multimodal usando `create_primary_chat_model()` y `HumanMessage` con `image_url` data-URI (LLM multimodal OpenAI-compatible configurado).
  - Post-execucion: cada screenshot excedente de `BROWSER_SCREENSHOT_MAX_BYTES` se elimina y el step queda `blocked`.
- `ActionRequestService.create_browser_interactive_request` persiste con payload_executable separado, idempotency_key, AuditEvent y HumanApproval ligado a Job (mismo patron que `browser_preview`).
- `_execute` ahora dispatcha `browser_interactive` -> `BrowserInteractiveService.execute`.
- Endpoint nuevo `POST /actions/browser/interactive/request` bajo JWT.

### Tests

13 tests nuevos en `tests/test_browser_interactive.py`:
- 7 de validacion (disabled, allow-list, navigate domain, selector required, dangerous selector, wait cap, analyze prompt).
- 4 de execucion (orchestration con vision, sin vision, screenshot cap, playwright no instalado).
- 2 de endpoint (auth required, disabled surface).

### Verificacion

| Check | Resultado |
|---|---|
| Backend pytest | **239 passed**, 1 skipped, 19 deselected (era 226) |
| Backend ruff check | pass |
| Backend ruff format | 135 files |
| Backend mypy --strict | 77 source files, no issues |
| Frontend lint | pass |
| Frontend build | pass |

### Archivos modificados

- `backend/src/cognitive_os/actions/schemas.py` (BrowserStep/Request/Result, ActionType extended)
- `backend/src/cognitive_os/actions/browser_interactive.py` (nuevo)
- `backend/src/cognitive_os/actions/service.py` (create_browser_interactive_request + _execute dispatch)
- `backend/src/cognitive_os/api/app.py` (endpoint POST /actions/browser/interactive/request)
- `backend/src/cognitive_os/db/models.py` (action_type IN ... extended)
- `backend/alembic/versions/202605120004_action_requests_browser_interactive.py` (migracion)
- `backend/tests/test_browser_interactive.py` (13 tests)

## 2026-05-12 - Fase 18: DeepAgents 0.6.x + subagents/memory

Fase 18 ejecutada despues de contrastar el avance pegado por el usuario contra
el arbol real. Estado previo: Fases 15, 16, 17 y 20 estaban presentes; Fase 18
no, porque `backend/pyproject.toml` aun tenia `deepagents>=0.5.5,<0.6.0`.

### Cambios

1. **Upgrade real de dependencia**:
   - `deepagents` 0.5.5 -> 0.6.1
   - `langchain` 1.2.16 -> 1.3.0
   - `langgraph` 1.1.10 -> 1.2.0
   - `langsmith` 0.7.38 -> 0.8.3
   - `backend/uv.lock` regenerado con `uv lock --upgrade-package deepagents`.

2. **Factory compatible con DeepAgents 0.6.1**:
   - `create_controlled_deep_agent` inspecciona la firma real de
     `create_deep_agent`.
   - Pasa `skills`, `memory` y `subagents` solo si el SDK los soporta.
   - Preserva `interrupt_on` para herramientas sensibles.
   - Nuevo flag `DEEPAGENTS_ENABLE_SUBAGENTS=true`.

3. **Subagents locales seguros**:
   - Research: `local-rag-researcher`, `citation-auditor`, y `web-researcher`
     solo si web esta permitido por policy + tarea.
   - Document analysis: `evidence-matrix-specialist`, `timeline-specialist`,
     `contradiction-reviewer`.
   - Cada subagent recibe las mismas tools policy-bound y permisos virtuales;
     no se agregan shell/email/browser/delete.

4. **Memory nativa + compatibilidad**:
   - Startup memory se escribe dentro del workspace en
     `./.cognitive_os/AGENTS.md`, usable por `MemoryMiddleware`.
   - El mismo resumen sigue inyectado en system prompt para compatibilidad.

5. **Dedup de memoria consolidada**:
   - `DeepAgentMemoryConsolidator` ahora normaliza contenido y evita duplicar
     propuestas dentro de la misma corrida.
   - Tambien deduplica contra propuestas pendientes y memoria activa existentes.

### Tests nuevos/actualizados

- `tests/test_deepagents_factory_skills_memory.py`: subagents seguros,
  desactivacion por metadata, memory file nativo.
- `tests/test_deepagents_memory_consolidation.py`: dedup en la misma corrida y
  contra propuestas existentes.

### Verificacion

| Check | Resultado |
|---|---|
| Backend pytest | **274 passed**, 1 skipped, 19 deselected |
| Focused deepagents | 34 passed |
| Backend ruff check | pass |
| Backend ruff format | 136 files |
| Backend mypy --strict | 77 source files, no issues |
| Frontend lint | pass |
| Frontend build | pass |

## 2026-05-12 - Fase 16: Robustez del pipeline RAG

5 problemas reales del pipeline RAG arreglados, con 5 tests de regresion. Suite total: **226 passed**.

### Cambios

1. **Pipeline order Postgres-Weaviate consistente**: chunks ahora se persisten como `status="pending_index"` y solo se promueven a `"indexed"` despues de que `WeaviateStore.batch_insert_chunks` confirma. Si Weaviate falla, el `except` marca el job `failed` y los chunks quedan `pending_index` (operador puede re-procesar). Antes la mitad de los chunks podia quedar `indexed` en Postgres sin vector en Weaviate.

2. **sha256 dedup en re-ingesta**: `_existing_indexed_document(sha256, source_path)` busca un `Document` previo con sha256 igual y `status="indexed"` cuyos chunks esten todos `"indexed"`. Si existe, retorna ese `IngestionResult` con warning `"existing_document_reused_by_sha256"` sin duplicar pages, chunks ni vectores. Best-effort: cualquier error de DB devuelve None y la ingesta sigue normal.

3. **Weaviate batch insert**: nuevo `WeaviateStore.batch_insert_chunks(records, batch_size=50)` que usa `/v1/batch/objects` + `embedding_provider.embed_texts(texts, kind="document")`. Para un PDF de 500 chunks pasamos de 500 POSTs + 500 embeddings a 10 POSTs + 10 embeddings. Detecta fallos por-objeto en la respuesta y lanza `RuntimeError` con detalles (no asume HTTP 200 = todo bien).

4. **BM25-only fallback en hybrid_search**: si `embedding_provider.embed_text(query, kind="query")` falla (outage, sin clave, quota), `hybrid_search` degrada a `alpha=0.0` sin vector. El GraphQL omite el campo `vector:` cuando esta vacio (algunas versiones de Weaviate rechazan `vector: []`). El usuario sigue obteniendo resultados keyword en lugar de un 500.

5. **`ensure_collection` thread-safe**: nuevo `_collection_lock: threading.Lock` con el patron lock + re-check. Soporta race entre pipeline + `web_indexer` (que corre en daemon thread). Si dos workers crean el schema en paralelo, se acepta 422 "already exists" como no-op.

### Archivos modificados

- `backend/src/cognitive_os/ingestion/pipeline.py` (existing dedup, mark_chunks_indexed, pending_index status, batch insert wiring)
- `backend/src/cognitive_os/memory/weaviate_store.py` (batch_insert_chunks, BM25 fallback, ensure_collection lock, 422 acceptance)
- `backend/tests/test_phase16_rag_robustness.py` (5 tests nuevos: batch endpoint, batch per-object failure, BM25 fallback omits vector, ensure_collection under concurrency, 422 already-exists)

### Verificacion

| Check | Resultado |
|---|---|
| Backend pytest | **226 passed**, 1 skipped, 19 deselected (era 221) |
| Backend ruff check | pass |
| Backend ruff format | 132 files |
| Backend mypy --strict | 76 files, no issues |
| Frontend lint | pass |
| Frontend build | pass |

## 2026-05-12 - Fase 15: Correctness critico (8 bugs)

Auditoria profunda de 27 puntos debiles -> 8 bugs criticos arreglados en una sola pasada con tests de regresion explicitos. Suite total: **221 passed** (era 205, +16 tests nuevos en `tests/test_phase15_correctness.py`).

### Bugs cerrados

1. **#1 — `execute_organize_plan` ejecutaba un plan recien recalculado, no el plan que el operador aprobo.** Fix: `ComputerActionService.execute_approved_plan(plan)` recibe el `ComputerOrganizePlan` aprobado y solo ejecuta esas operaciones, re-validando cada `source`/`destination` contra el filesystem actual. `ActionRequestService._execute` ahora parsea `action_request.preview` y lo pasa al executor.

2. **#2 — `_execute` corria con `payload_redacted` que podia contener `[REDACTED]` literal.** Fix: nueva columna `action_requests.payload_executable` (migracion `202605120003`), poblada con la version sin redactar del request; `payload_redacted` queda solo para auditoria. `_execute` prefiere `payload_executable` y cae a `payload_redacted` para rows previos.

3. **#3 — `research_node` retornaba `needs_more_info`/`blocked` con answer vacio como exito.** Fix: solo `status="ok"` con `answer.strip()` no vacio se devuelve como exito; los demas estados con respuesta vacia disparan el fallback RAG; los estados con respuesta no vacia se exponen con marca explicita de incertidumbre.

4. **#5 — `execute_action_request` permitia doble dispatch.** Fix: `SELECT ... FOR UPDATE` + chequeo de estado pre-flush; solo promueve de `queued` -> `running`; si ya esta `running` u otro terminal, retorna idempotentemente.

5. **#6 — `read_document_pages` no validaba `doc_id` contra el allowlist de la tarea.** Fix: tool acepta `allowed_doc_ids` y rechaza cualquier doc_id fuera; lista vacia = default deny. `build_deepagent_tools` threads `task.allowed_doc_ids` desde el factory.

6. **#8 — `search_local_docs` mezclaba snippets web reindexados con docs locales.** Fix: nuevo parametro `exclude_doc_types: Sequence[str] | None` en `retrieve_context` y `WeaviateStore.hybrid_search` con soporte `NotEqual` en el WHERE; `search_local_docs` excluye `doc_type="web"` por defecto.

7. **#10 — Solo se auditaban exitos.** Fix: nuevo helper `_audit_error(tool_name, args, reason)`; `_controlled_error` ahora recibe tool_name + args y emite audit en errores y bloqueos. Cada tool de deepagents reporta `args_redacted` con su tool_name correcto.

8. **#20 — Citas exponian el path absoluto del filesystem (ruta interna del ingestor).** Fix: helper `_source_display(source_path, title)` que prefiere `title` si esta y usa basename del path en caso contrario; splitter portable que detecta tanto `/` como `\\` para soportar Windows. `SearchResult.citation` y `RetrievalCitation.citation` actualizados; el `source_path` completo permanece en `metadata` para trazabilidad.

### Cambios en API/contratos

- Migracion Alembic `202605120003_action_requests_payload_executable.py` agrega `action_requests.payload_executable JSONB NULLABLE`.
- `ComputerActionService` gana metodo `execute_approved_plan(plan)`; `execute_organize_plan(request)` ahora es un convenience que llama al primero.
- `WeaviateStore.hybrid_search` y `retrieve_context` aceptan `exclude_doc_types: Sequence[str] | None`.
- `read_document_pages` acepta `allowed_doc_ids: Iterable[str] | None`.
- `build_deepagent_tools` acepta `allowed_doc_ids: Sequence[str] | None`.
- `_controlled_error(tool_name, args_redacted, exc)` reemplaza `_controlled_error(exc)`.

### Tests nuevos (16) en `tests/test_phase15_correctness.py`

- 3 cubren bug #1 (plan aprobado, dry-run-only block, revalidacion por operacion)
- 2 cubren bug #3 (empty answer -> fallback, needs_more_info no vacio -> uncertainty)
- 3 cubren bug #6 (allowlist enforcement, default deny, factory threading)
- 2 cubren bug #8 (kwarg propagation, legacy retriever fallback)
- 3 cubren bug #10 (policy violation audit, soft block audit, search_local_docs block audit)
- 3 cubren bug #20 (basename rendering, title preference, Windows path)

### Verificacion

| Check | Resultado |
|---|---|
| Backend pytest | **221 passed**, 1 skipped, 19 deselected (era 205) |
| Backend ruff check | pass |
| Backend ruff format | 131 files formatted |
| Backend mypy --strict | 76 files, no issues |
| Frontend lint | pass |
| Frontend build | pass |

### Archivos modificados

- `backend/src/cognitive_os/actions/computer.py` (execute_approved_plan)
- `backend/src/cognitive_os/actions/service.py` (row lock, payload_executable, plan aprobado, helper `_try_parse_computer_plan`)
- `backend/src/cognitive_os/db/models.py` (columna `payload_executable`)
- `backend/alembic/versions/202605120003_action_requests_payload_executable.py` (migracion)
- `backend/src/cognitive_os/agents/graph.py` (fallback con empty answer / needs_more_info / blocked)
- `backend/src/cognitive_os/agents/state.py` (`_source_display`, basename en citation)
- `backend/src/cognitive_os/memory/retrieval.py` (`exclude_doc_types`)
- `backend/src/cognitive_os/memory/weaviate_store.py` (NotEqual operand, basename en `SearchResult.citation`)
- `backend/src/cognitive_os/deepagents/tools.py` (allowed_doc_ids, exclude_web, audit en errores)
- `backend/src/cognitive_os/deepagents/factory.py` (threads task.allowed_doc_ids)
- `backend/tests/test_phase15_correctness.py` (16 tests nuevos)
- `backend/tests/test_memory_retrieval.py` (test extra forward exclude)
- `backend/tests/test_fixed_bugs.py`, `tests/test_integration_rag_weaviate.py` (citation basename)

## 2026-05-12 - Fase 14: Research Orchestrator async + SSE streaming

- Bug detectado en auditoria: `ResearchOrchestrator.start_run` ejecutaba
  `_execute` de forma sincrona, bloqueando `POST /research/runs` hasta
  `time_budget_seconds` y dejando inutil el endpoint de cancelacion. La cola
  `event_queue` existia pero ningun cliente podia consumirla en tiempo real.
- `start_run` ahora lanza `_execute` en un daemon thread (`name="research-{id}"`)
  y retorna de inmediato. `ResearchRun` agrega:
  - `done_flag: threading.Event` (set en el `finally` de `_execute`)
  - `executor_thread: threading.Thread | None` (handle de referencia)
- Nuevo `wait_for_run(run_id, *, timeout=60.0) -> ResearchRun | None` para
  tests y callers que necesitan estado terminal. No lanza excepciones en
  timeout; los callers inspeccionan `run.status`.
- Nuevo endpoint SSE `GET /research/runs/{run_id}/events`:
  - 404 si la run no existe.
  - 401/403 si falta JWT.
  - Itera `run.events` (snapshot atomico bajo GIL) y avanza un cursor
    `last_idx` cada 50 ms.
  - Cuando el run llega a `completed/cancelled/failed/blocked`, emite un
    evento `snapshot` con `ResearchRunView` completo y luego `done`.
- 5 tests nuevos en `tests/test_research_orchestrator.py`:
  - `test_wait_for_run_returns_none_for_unknown_id`
  - `test_start_run_returns_immediately_with_non_terminal_status` (asserta
    `elapsed < 0.2s` y `status in {queued, planning, researching, ...}`)
  - `test_research_events_sse_endpoint_streams_events`
  - `test_research_events_sse_endpoint_404_for_unknown_run`
  - `test_research_events_sse_endpoint_requires_authentication`
- Tests existentes (full_pipeline, reports_failed_subtask, emits_events,
  subtask_timeout, cancel_sets_run_status, clamps_budget, synthesizer_dedups,
  endpoints) reescritos para usar `start_run` + `wait_for_run`.
- Verificacion:
  - `uv run pytest`: 204 passed, 1 skipped, 19 deselected.
  - `uv run pytest tests/test_research_orchestrator.py`: 16 passed.
  - `uv run ruff check .`: pass.
  - `uv run ruff format --check .`: pass.
  - `uv run mypy src`: pass.
  - `npm run lint`: pass.
  - `npm run build`: pass.

## 2026-05-12 - Fase 13: Gmail Daily Digest read-only

- Nuevo modulo `backend/src/cognitive_os/actions/gmail_digest.py`:
  - `GmailReader` Protocol y `FakeGmailReader` para tests.
  - `GmailDigestService.build_preview(request)` redacta direcciones
    (`l***l@dominio`), agrupa por remitente, ordena por fecha y propone
    borradores con `requires_approval=True`. Nunca crea drafts reales.
- Schemas nuevos en `actions/schemas.py`:
  - `GmailDigestRequest`, `GmailDigestPreview`, `GmailDigestMessage`,
    `GmailDigestSender`, `GmailDigestProposedDraft`.
- Endpoint nuevo `POST /actions/gmail/digest/preview` bajo JWT con
  singleton `_gmail_digest_reader` inyectable via monkeypatch.
- 10 tests nuevos en `tests/test_gmail_digest.py`.

## 2026-05-12 - Fase 12: Research Orchestrator sobre deepagents

- Implementado `ResearchOrchestrator` en `agents/research_orchestrator.py`.
  Es una capa orquestadora ENCIMA de `deepagents` (no lo reemplaza): el
  `DeepAgentResearcher` default delega cada subtask a `run_research_deepagent`,
  conservando politicas, skills, memoria y auditoria del subagente real.
- Nodos: `Planner` -> `Researcher` (N en paralelo) -> `Synthesizer` -> `Scorer`.
  Todos son Protocols inyectables; defaults heuristicos auditables permiten
  ejecutar sin LLM keys.
- Presupuesto de tiempo via `time_budget_seconds` con `wait(timeout=...)`.
  Subtasks que no terminan a tiempo se marcan `timeout` y se cancelan via
  `executor.shutdown(wait=False, cancel_futures=True)`.
- Cancelacion explicita via `threading.Event` + endpoint
  `POST /research/runs/{id}/cancel`.
- Streaming incremental: cada nodo emite `ResearchEvent` (run_started,
  plan_ready, subtask_started, subtask_finished, synthesis_ready,
  score_ready, run_completed/cancelled/failed) a una cola por run, lista
  para SSE en una fase posterior.
- `HeuristicScorer` aplica rubrica auditable (`completion`, `coverage`,
  `evidence`, `humility`, `no_failed`) con score 0..1.
- Settings: `ENABLE_RESEARCH_ORCHESTRATOR=true`,
  `RESEARCH_MAX_PARALLEL_WORKERS=4`, `RESEARCH_MAX_TIME_BUDGET_SECONDS=300`,
  `RESEARCH_MAX_SUBTASKS=8`. La solicitud se "clampa" contra estos limites
  para que un cliente malicioso no pueda pedir 999 subtasks o 1h.
- Endpoints: `POST /research/runs`, `GET /research/runs`,
  `GET /research/runs/{id}`, `POST /research/runs/{id}/cancel`. Requieren JWT.
- Store in-memory en `api.app.get_research_orchestrator()` con singleton
  reemplazable en tests via monkeypatch de `_research_orchestrator`.
- 11 tests nuevos en `tests/test_research_orchestrator.py` con providers
  fake (Planner, Researcher, Synth, Scorer, SleepyResearcher para timeout y
  cancel). Cubren: full pipeline, disabled, subtask blocked, eventos en
  orden, subtask timeout, cancel, clamp de limites, dedup de citas, endpoint
  POST, endpoint GET/list/cancel/404, endpoint disabled 403.
- Verificacion:
  - `uv run pytest`: 189 passed, 1 skipped, 19 deselected.
  - `uv run pytest tests/test_research_orchestrator.py`: 11 passed.
  - `uv run ruff check src tests`: pass.
  - `uv run ruff format --check src tests`: pass.
  - `uv run mypy --strict src`: pass.
  - `npm run lint`: pass.
  - `npm run build`: pass.

## 2026-05-12 - Fase 19: Office writers extendidos

- Extendidos los schemas de `actions/schemas.py`:
  - `DocumentTable` y `DocumentImage` para DOCX.
  - `SpreadsheetFormula` para formulas XLSX explicitas.
  - `SlideContent.layout` con `title`, `bullets`, `two_column`, `quote`.
- Nuevo setting `DOCUMENT_ASSET_ROOTS` en `core/config.py` y `.env.example`.
  Sin esta allow-list, las imagenes quedan bloqueadas por defecto.
- `DocumentActionService` ahora valida contenido en preview y execute:
  - imagenes deben estar dentro de `DOCUMENT_ASSET_ROOTS`, existir y ser
    `.png`, `.jpg` o `.jpeg`;
  - formulas deben empezar con `=` y no pueden usar patrones peligrosos como
    `HYPERLINK`, `WEBSERVICE`, URLs externas, referencias a otros workbooks o
    comandos.
- DOCX:
  - tablas con caption, headers en bold y filas heterogeneas;
  - imagenes con ancho controlado y caption.
- XLSX:
  - strings con prefijo `=/+/-/@` siguen neutralizados con apostrofo;
  - formulas reales solo se escriben via `SpreadsheetFormula`;
  - headers en bold, freeze panes, anchos automaticos y tabla Excel real.
- PPTX:
  - mantiene bullets antiguos;
  - agrega layouts `title`, `two_column` y `quote` usando textboxes nativos.
- Tests nuevos en `tests/test_phase19_office_writers.py`:
  - reabren DOCX con `python-docx` y validan tabla + imagen embebida;
  - bloquean imagen fuera de allow-list;
  - reabren XLSX con `openpyxl` y validan formula explicita + sanitizacion;
  - bloquean formula peligrosa;
  - reabren PPTX con `python-pptx` y validan layouts.
- Verificacion:
  - `uv run pytest`: 280 passed, 1 skipped, 19 deselected.
  - `uv run pytest tests/test_phase19_office_writers.py tests/test_actions.py`: 39 passed.
  - `uv run ruff check .`: pass.
  - `uv run ruff format --check .`: pass.
  - `uv run mypy src`: pass.
  - `npm run lint`: pass.
  - `npm run build`: pass.

## 2026-05-12 - Fase 21: Gmail read-only real reader

- Implementado `GmailRestReader` en `backend/src/cognitive_os/actions/gmail_digest.py`.
- Lee `GMAIL_TOKEN_DIR/token.json` con `google.oauth2.credentials.Credentials`.
- Refresca el token con `google.auth.transport.requests.Request` si expiro y
  existe `refresh_token`; persiste el `token.json` actualizado.
- Usa Gmail REST con `httpx`:
  - lista `users/me/messages` con `q=newer_than:{lookback_hours}h`;
  - respeta `max_messages`;
  - pasa labels como `labelIds`;
  - trae cada mensaje en `format=metadata` con headers `From`, `Subject`, `Date`.
- Normaliza cada mensaje al contrato del digest: `id`, `thread_id`, `sender`,
  `subject`, `snippet`, `labels`, `received_at`.
- `GmailDigestService` atrapa fallos del reader y devuelve `blocked` con razon
  redactada; no filtra `access_token`, `refresh_token`, `client_secret`, etc.
- `api.app.get_gmail_digest_reader()` usa `GmailRestReader.from_settings(settings)`
  cuando Gmail read esta habilitado y no hay fake inyectado.
- `GmailActionService.status()` ahora reporta:
  - `token_path`;
  - `token_present`;
  - `google_auth_available`;
  - estado `configured` si falta token.
- Tests nuevos en `tests/test_gmail_digest.py`:
  - fetch realista con cliente HTTP fake;
  - refresh y persistencia de token;
  - token faltante;
  - error del reader bloqueado y redactado.
- Verificacion:
  - `uv run pytest`: 284 passed, 1 skipped, 19 deselected.
  - `uv run pytest tests/test_gmail_digest.py tests/test_actions.py::test_gmail_query_preview_respects_read_flag`: 15 passed.
  - `uv run ruff check .`: pass.
  - `uv run ruff format --check .`: pass.
  - `uv run mypy src`: pass.
  - `npm run lint`: pass.
  - `npm run build`: pass.

## 2026-05-12 - Fase 22: GoDaddy DNS executor seguro

- Settings nuevos:
  - `GODADDY_ALLOWED_DOMAINS`;
  - `GODADDY_DNS_DRY_RUN_ONLY=true`;
  - `GODADDY_ALLOW_PRODUCTION_WRITES=false`.
- `.env.example` actualizado con las variables y comentarios de seguridad.
- `GoDaddyActionService.status()` ahora reporta allow-list, dry-run y flag de
  writes de produccion.
- `preview_dns_change` ahora:
  - normaliza dominio;
  - valida formato de dominio y record name;
  - exige priority en `MX`/`SRV`;
  - si dry-run esta apagado, exige dominio allow-listed;
  - si base URL es produccion, exige `GODADDY_ALLOW_PRODUCTION_WRITES=true`.
- Nuevo schema `GoDaddyDnsExecutionResult`.
- `execute_dns_change` llama GoDaddy REST con `PATCH /v1/domains/{domain}/records`
  y body de un solo record aprobado. Si el servicio sigue dry-run, retorna
  `blocked`.
- `ActionRequestService.create_godaddy_dns_change_request` deja dry-run como
  `previewed`, pero crea `pending_approval` + `HumanApproval` + `Job` cuando el
  cambio es ejecutable.
- `_execute` soporta `godaddy_dns_change`.
- Tests nuevos:
  - executable DNS exige `GODADDY_ALLOWED_DOMAINS`;
  - produccion exige `GODADDY_ALLOW_PRODUCTION_WRITES`;
  - executor manda endpoint/body/auth esperados contra fake client;
  - dry-run bloquea ejecucion.
- Verificacion:
  - `uv run pytest`: 288 passed, 1 skipped, 19 deselected.
  - `uv run pytest tests/test_actions.py`: 37 passed.
  - `uv run ruff check .`: pass.
  - `uv run ruff format --check .`: pass.
  - `uv run mypy src`: pass.
  - `npm run lint`: pass.
  - `npm run build`: pass.

## 2026-05-12 - Fase 23: Restore scripts operativos

- Agregados:
  - `scripts/restore_postgres.sh`
  - `scripts/restore_neo4j.sh`
  - `scripts/restore_storage.sh`
- Todos exigen `CONFIRM_RESTORE=YES`; sin ese flag salen con codigo 2.
- Todos ejecutan `sha256sum -c` cuando existe el `.sha256` del artefacto.
- `restore_postgres.sh` usa `pg_restore --clean --if-exists` contra el
  contenedor `cognitive_os_postgres`.
- `restore_neo4j.sh` exige archivo `neo4j.dump`, detiene Neo4j, ejecuta
  `neo4j-admin database load`, y reinicia Neo4j con trap.
- `restore_storage.sh` mueve el storage actual a
  `storage.pre_restore_TIMESTAMP` antes de extraer el tar.gz.
- `scripts/README.md` y `docs/RUNBOOK.md` actualizados para usar scripts en vez
  de comandos manuales.
- Tests nuevos en `tests/test_backup_restore_scripts.py`:
  - `bash -n` de backup/restore scripts;
  - presencia de `CONFIRM_RESTORE=YES`;
  - presencia de `sha256sum -c`;
  - copia previa en restore de storage.
- Verificacion:
  - `uv run pytest`: 292 passed, 1 skipped, 19 deselected.
  - `uv run pytest tests/test_backup_restore_scripts.py`: 4 passed.
  - `uv run ruff check .`: pass.
  - `uv run ruff format --check .`: pass.
  - `uv run mypy src`: pass.
  - `npm run lint`: pass.
  - `npm run build`: pass.

## 2026-05-12 - Fase 24: Inventario local de archivos Windows/Linux

- Schemas nuevos:
  - `ComputerInventoryRequest`;
  - `FileInventoryEntry`;
  - `ComputerInventoryResult`.
- Endpoint nuevo:
  - `POST /actions/computer/inventory`.
- `ComputerActionService.build_inventory` crea un registro read-only de archivos:
  - relative path;
  - categoria (`Documents`, `PDFs`, `Code`, etc.);
  - extension;
  - tamano;
  - `modified_at`;
  - sha256 opcional.
- Guardrails:
  - requiere `ENABLE_COMPUTER_ACTIONS=true`;
  - root debe estar dentro de `COMPUTER_ALLOWED_ROOTS`;
  - no sigue symlinks;
  - omite hidden files por defecto;
  - salta rutas sensibles (`.env`, `.git`, `.ssh`, `credentials`, `secret`,
    `token`, `password`, `keychain`);
  - corta en `max_files` y registra warning.
- El reporte se guarda en `LOCAL_STORAGE_DIR/file_inventory/inventory-*.json`
  para comparaciones futuras.
- Tests nuevos en `tests/test_computer_inventory.py`:
  - scan allow-listed con reporte JSON;
  - sha256 opcional;
  - truncado por limite;
  - bloqueo fuera de roots;
  - endpoint usa service;
  - endpoint requiere auth.
- Verificacion:
  - `uv run pytest`: 298 passed, 1 skipped, 19 deselected.
  - `uv run pytest tests/test_computer_inventory.py tests/test_actions.py`: 43 passed.
  - `uv run ruff check .`: pass.
  - `uv run ruff format --check .`: pass.
  - `uv run mypy src`: pass.
  - `npm run lint`: pass.
  - `npm run build`: pass.

## 2026-05-12 - Fase 25: Roadmap asistente personal completo

- Creado `docs/PERSONAL_ASSISTANT_ROADMAP.md`.
- Incluye estado actual y brechas de:
  - memoria personal;
  - Gmail/GoDaddy mail;
  - grounding Tavily/Perplexity/Brave/Exa;
  - navegador headless/vision/Camoufox;
  - tareas/agenda/recordatorios;
  - notas;
  - audio/voz;
  - YouTube/video;
  - MCP/skills externos;
  - IDE/repo coding workflow.
- Orden recomendado:
  - Fase 25 memoria personal + eventos episodicos;
  - Fase 26 tareas/notas/recordatorios;
  - Fase 27 web grounding multi-provider;
  - Fase 28 correo multi-cuenta;
  - Fase 29 Camoufox + recorder/replay;
  - Fase 30 YouTube/audio;
  - Fase 31 MCP/skills external adapter;
  - Fase 32 IDE/repo agent workflow.
- `docs/README.md` actualizado para indexar el roadmap y corregir el estado
  actual del action plane.

## 2026-05-12 - Optimizacion (Exa + memoria episodica)

- Cableado cliente **Exa** en `MultiProviderWebSearchClient` (`EXA_API_KEY`);
  `configured_web_search_provider_names` y `/config/public` incluyen `exa`; tests sin
  red con mock HTTP (`tests/test_exa_web_search.py`).
- **Memoria episodica** (`kind='episodic'`): migracion `202605120005`,
  `DeepAgentMemoryService.record_episodic_memory`, `POST /deepagents/memory/episodic`;
  roadmap y docs DeepAgents/Memory actualizados.
- `task_plan`: Fase 19 marcada `complete`.
- Verificacion (Composer):
  - Backend pytest **306 passed**, 1 skipped, 19 deselected
  - Backend ruff + mypy pass
  - Frontend lint + build pass

## 2026-05-13 — Auditoría integral (sesión OpenCode)

- Sesión de mapeo read-only de todo el árbol `cognitive-os/`: lectura de los
  26 markdowns (README, ARCHITECTURE, COGNITIVE_OS_GUIDE, PERSONAL_ASSISTANT_ROADMAP,
  ACTION_PLANE, SECURITY, SETTINGS_REGISTRY_TABLE, etc.) y de los módulos
  críticos backend (`agents/graph.py`, `deepagents/factory.py`, `deepagents/tools.py`,
  `memory/retrieval.py`, `actions/{mail,gmail_digest,domains}.py`, `assist/service.py`).
- Verificado contra el repo real:
  - Memoria híbrida ya está (Weaviate + Neo4j + Postgres + DeepAgents memory +
    episódica + propuestas + consolidación).
  - Investigación, action plane (computer/browser/documents), Gmail digest
    read-only y GoDaddy DNS están operativos.
  - YouTube, voz STT/TTS, calendario real y mailbox GoDaddy/M365 **no existen
    aún**; solo hay variables reservadas y un mock de `create_calendar_draft`.
- Diagnóstico volcado en `findings.md` (sección "Auditoría integral para
  asistente personal absoluto"): brechas concretas con archivos y settings
  exactos, y comparación con `HKUDS/DeepCode` (conclusión: tomar ideas, no
  acoplar código).
- Plan Fase 25 abierto en `task_plan.md` (subfases A–H: mail unificado,
  YouTube, voz, calendario, notas semánticas, perfil usuario, grafo
  personal_assistant, hardening credenciales) con criterios de aceptación
  verificables.
- 6 decisiones bloqueantes listadas para que el operador confirme antes de
  empezar a escribir código (proveedor mail GoDaddy, política Gmail send,
  proveedor calendario, proveedor STT/TTS, vault markdown, multi-cuenta).
- No se modificó código del proyecto en esta sesión: solo planificación viva.
## 2026-05-14 — Sweep documental forzado (sesión OpenCode)

- Verificación contra código real:
  - `pytest -q` → **341 passed, 1 skipped, 20 deselected** (suite completa, ~21s).
  - `dump_settings_registry.py` regeneró `docs/SETTINGS_REGISTRY_TABLE.md` 1:1
    con `Settings`.
  - `frontend/app/views/` listado: **17 vistas reales** (incluida `AssistView.tsx`,
    omitida en pasadas previas).
  - `mail/` package real: `service.py`, `imap_client.py`, `smtp_client.py`,
    `gmail_label_reader.py`, `classifier.py`, `schemas.py`. Endpoints `/mail/*`
    completos: status, sync, sync/dispatch, messages list/get,
    `messages/{id}/reply` (PATCH), `messages/{id}/ignore`,
    `messages/{id}/approve-send`.
  - 89 endpoints `@app.*` reales en `api/app.py` (vs 81 documentados en pases
    previos): se confirma número en `COGNITIVE_OS_GUIDE.md`.
  - Migraciones Alembic: 12 versiones, última `202605140001_mail_accounts_messages`.
- Correcciones aplicadas en esta sesión:
  - `AGENTS.md` raíz: `Weaviate 1.25.8` → `1.29.0`.
  - `.opencode/agents/devops-engineer.md`: `Weaviate 1.25.8` → `1.29.0`.
  - `cognitive-os/README.md`: 16 vistas → **17 vistas (incluida `Assist`)**.
  - `cognitive-os/docs/README.md`: idem.
  - `cognitive-os/docs/COGNITIVE_OS_GUIDE.md`: 4 ocurrencias `16 vistas` → 17
    (TOC, diagrama, sección 7, conclusión sección 18); cabecera con DeepSeek
    V4 Pro y `Assist` reflejada.
  - `cognitive-os/frontend/README.md`: 17 vistas + nota sobre `AssistView` y
    endpoints `/assist/*`.
  - `cognitive-os/task_plan.md`: Fase 27 normalización documental refleja 17
    vistas; tabla de QA y resumen de fase final también.
  - `cognitive-os/findings.md`: snapshot QA actualizado a `341 passed`
    (verificado 2026-05-14); listado de 17 vistas explícito.
- Sin cambios necesarios en (ya correctos):
  - `docs/PROJECT_GUIDE.md`, `docs/ARCHITECTURE.md`, `docs/RUNBOOK.md`,
    `docs/PERSONAL_ASSISTANT_ROADMAP.md`, `docs/ACTION_PLANE.md`,
    `docs/SECURITY.md`, `docs/OPENHARNESS_FUSION.md`,
    `docs/OPENSHELL_SANDBOX.md`, `docs/DEEPAGENTS_INTEGRATION.md`,
    `docs/DEEPAGENTS_SKILLS_MEMORY.md`, `docs/DOCUMENT_ANALYSIS_AGENT.md`,
    `docs/OPERATOR_VARIABLE_CHECKLIST.md`, `docs/IMPROVEMENT_EXECUTION_PLAN.md`,
    `cognitive-os/ACCEPTANCE_CHECKLIST.md` (ya en 2026-05-14, 341 passed),
    `cognitive-os/scripts/README.md`, los 8 SKILL.md core, los READMEs de
    `storage/deepagents/{memory,skills/user}/` y `experiments/openshell-deepagent/`.
  - `docs/SECURITY.md` raíz workspace, `docs/openchamber-cognitive-os.md`,
    `docs/opencode-agent-stack.md` (ya en 2026-05-14).
- No se tocaron backups ni snapshots (`cognitive-os-backup-*`,
  `cognitive-os-snapshot-*`) ni vendor `.openharness_upstream` ni
  `experiments/openshell-deepagent/vendor/` por política.
- No se cambiaron `task_plan.md`/`findings.md`/`progress.md` previos a esta
  entrada: son bitácoras vivas y mantienen sus snapshots históricos.

## 2026-05-14 — Revisión integral + Fase 25.E (notas semánticas)

- Revisión completa desde las bases (markdowns + núcleo + QA). Estado base
  verificado verde: `pytest` 341 passed, `ruff`/`format`/`mypy --strict`,
  frontend `lint`/`build`, CI/pre-commit OK. Sin weak points en código existente.
- Decisiones Fase 25 resueltas por el operador (ver `findings.md`): mail GoDaddy
  IMAP nativo, Gmail solo-texto, agenda Google Calendar, voz ElevenLabs,
  multi-cuenta desde inicio, markdown vault opcional off.
- Implementada **Subfase 25.E — notas semánticas**:
  - `backend/src/cognitive_os/assist/note_index.py`: `NoteIndexService` con
    Protocol `NoteVectorStore`, indexado idempotente (delete+insert) en Weaviate
    `doc_type="note"`, búsqueda híbrida con post-filtro por `user_id`.
  - `assist/service.py`: `PersonalAssistService` ahora inyecta `NoteIndexService`;
    `create_note`/`update_note`/`delete_note` sincronizan el índice off-loop con
    `asyncio.to_thread`; nuevo método `search_notes`.
  - `assist/schemas.py`: `PersonalNoteSearchHit`.
  - `api/app.py`: `GET /assist/notes/search` (declarado antes de
    `/assist/notes/{note_id}` para ganar el match de ruta).
  - `tests/test_note_index.py`: 6 tests sin red (fake store, idempotencia,
    degradación graciosa, aislamiento por usuario, auth del endpoint).
- Verificación: `pytest -m 'not integration and not slow'` → **347 passed,
  1 skipped, 20 deselected**; `ruff check`/`ruff format`/`mypy src --strict`
  verdes (96 source files).
- Pendiente Fase 25: C (voz ElevenLabs) y D (Google Calendar) quedan
  code-ready a la espera de credenciales; F (perfil usuario), G (grafo
  personal_assistant), H (SecretStore) son incrementales sin credenciales.

## 2026-05-14 — Fase 25 C/D + Maps + Voz (credenciales reales del operador)

- El operador entregó credenciales reales (ElevenLabs, cliente OAuth Google,
  API key Google Maps) y pidió implementación inmediata de Calendar, Drive,
  Maps y voz. Credenciales escritas SOLO en `cognitive-os/.env` (gitignored,
  perms 600); `.env.example` y `SETTINGS_REGISTRY_TABLE.md` actualizados con
  placeholders. Settings nuevos en `config.py` + validadores de capacidad.
- **Google Maps** (`actions/maps.py`): `MapsService` + Protocol `MapsProvider`
  + `GoogleMapsProvider` (Routes API + Geocoding API) + `FakeMapsProvider`.
  Endpoints `GET /actions/maps/status`, `POST /actions/maps/geocode`,
  `POST /actions/maps/route`. Read-only, gating disabled/blocked/ready.
  11 tests sin red (`tests/test_maps.py`).
- **Voz ElevenLabs** (`voice/` package): `VoiceService` + Protocols STT/TTS +
  `ElevenLabsSTTProvider`/`ElevenLabsTTSProvider` + fakes. Endpoints
  `GET /voice/status`, `POST /voice/transcribe` (multipart), `POST /voice/speak`
  (devuelve audio). Cap `VOICE_MAX_AUDIO_BYTES`, redacción de claves en errores.
  12 tests sin red (`tests/test_voice.py`).
- **Google Calendar + Drive** (read-only): `core/google_oauth.py`
  (`GoogleCredentialsLoader` compartido, refresh + persistencia, lazy-import de
  `google-auth`), `actions/calendar.py` (`CalendarService`, list events),
  `actions/drive.py` (`DriveService`, list/get files), `scripts/auth_google.py`
  (flujo OAuth interactivo único). Endpoints `/actions/calendar/*` y
  `/actions/drive/*`. 19 tests sin red.
- Las operaciones de escritura (crear evento, subir archivo) quedan
  explícitamente fuera de este corte: deben pasar por el ciclo
  `ActionRequest`/aprobación (seguimiento aparte), igual que Gmail salió
  read-only primero en la Fase 21.
- Verificación: `pytest -m 'not integration and not slow'` → **389 passed,
  1 skipped, 20 deselected** (era 341 al inicio de la jornada; +48 tests netos
  sumando 25.E). `ruff check` + `ruff format --check` + `mypy src --strict`
  verdes (103 source files).
- Operador: `google-auth` / `google-auth-oauthlib` se importan de forma
  perezosa (mismo patrón que `GmailRestReader`); instalarlos
  (`uv pip install google-auth google-auth-oauthlib`) antes de correr
  `scripts/auth_google.py` y de habilitar Calendar/Drive en runtime real.

## 2026-05-14 — Sweep nocturno: DeepAgent wiring + SecretStore + Calendar/Drive write + Health

- Tools DeepAgent (`tools.py` + `policies.py` + `schemas.py`): nuevas tools
  controladas `plan_route`, `geocode_address`, `list_calendar_events`,
  `search_drive_files`, `search_notes`. Flags `allow_maps`, `allow_calendar_read`,
  `allow_drive_read`, `allow_notes_read` añadidas a `DeepAgentToolPolicy` con
  default-on (las capacidades gating-an a nivel servicio: si el servicio no
  está listo la tool devuelve un error controlado). 15 tests
  (`tests/test_deepagents_personal_tools.py`).
- SecretStore (`core/secrets.py`): API uniforme `get/require/is_configured` con
  precedencia overrides → SECRET_OVERRIDE_<NAME> env → Settings → keyring opt-in.
  Tests de regresión (`tests/test_secret_hardening.py`) que garantizan:
  * `Settings.model_dump()` mantiene `SecretStr` opaco
  * Ningún `BaseModel` de respuesta en `api/app.py` declara campo `SecretStr`
  * `PublicConfigResponse` libre de campos secretos
  * `redact_secrets` cubre `Authorization`, `api_key`, `password`, dsn `://u:p@h/d`,
    patrones `sk-...` y `Bearer ...` también dentro de listas y nested dicts
- Calendar write op-in (`actions/calendar.py` + endpoint
  `POST /actions/calendar/events/create`): preview-first con `dry_run=true` por
  defecto; doble gate `ENABLE_GOOGLE_CALENDAR_WRITE=true` + `dry_run=false`;
  audit `calendar.create_event_*` en cada intento (preview/blocked/created/failed).
- Drive write op-in (`actions/drive.py` + endpoint `POST /actions/drive/files/upload`):
  preview-first idem; gate triple WRITE flag + `dry_run` + path debe estar bajo
  `COMPUTER_ALLOWED_ROOTS`; cap `GOOGLE_DRIVE_UPLOAD_MAX_BYTES` antes de leer
  bytes; rechaza `..`, paths inexistentes, símbolos fuera del allow-list.
- Health dashboard ampliado (`core/health.py`): añadidos `voice`, `maps`,
  `google_calendar`, `google_drive` como componentes. `write_enabled` queda
  reflejado en metadata para Calendar/Drive. El estado overall queda `ok` si
  los nuevos están `disabled`/`blocked`/`ready` (ninguno fuerza degradación).
- Verificación: **428 passed, 1 skipped, 20 deselected** (era 389; +39 tests
  netos). `ruff` + `ruff format` + `mypy --strict` verdes (104 source files).
  `SETTINGS_REGISTRY_TABLE.md` regenerado.


## 2026-05-14 — Auditoría integral nocturna (16 tareas, todas verdes)

Sweep desde cero buscando puntos débiles, con foco en grado comercial.

Categorías auditadas (los 5 ejes de riesgo):

1. **Silent failures / bare except**: revisados 1 por 1; ninguno oculta error
   real. Los suppress legítimos están justificados con comentario en código:
   _safe_dict (helper), ingestion.dedup_check (best-effort), audit helpers de
   maps/calendar/drive (no deben romper el flujo principal). Convertí los dos
   audit-helpers de Calendar/Drive de `except: return` a
   `except Exception as exc: log.warning(...)` para preservar observabilidad.
2. **Fuga de secretos**: grep agresivo de las 5 credenciales reales del .env
   contra todo el árbol (excluyendo backups). Resultado: **0 fugas** en código,
   tests, docs, frontend, configs.
3. **Auth gaps**: enumerados 98 endpoints `@app.{verb}`; corrido directo contra
   ASGI sin JWT. Resultado: **0 endpoints sensibles sin auth** (sólo `/health`
   es público, como debe ser).
4. **Concurrencia**: revisados `asyncio.run`, threads, ThreadPoolExecutor,
   locks. Todos los `asyncio.run` en código sincrónico (Celery, CLI, tools)
   o protegidos por check de event loop activo (`_run_async` en deepagents).
   Locks correctos en `weaviate_store.ensure_collection`,
   `embeddings.GeminiKeyPool`, `research_orchestrator.start_run`. Sin races.
5. **Path traversal / SSRF / injection**:
   * Drive upload: rechaza `..`, paths inexistentes, paths fuera de
     `COMPUTER_ALLOWED_ROOTS`, archivos sobre cap.
   * Drive `q` query: escapa `'` antes de mandar a Drive grammar.
   * Maps geocode/route: address pasa como query param URL-encoded por httpx.
   * Calendar create event: valida ventana de tiempo (`end > start`).
   * Computer organize ya tenía path policy en `core/path_policy.py`.

QA final del sweep:
- `ruff check src tests` → All checks passed
- `ruff format --check` → 174 files already formatted
- `mypy src --strict` → 0 issues, 104 source files
- `pytest -m 'not integration and not slow'` → **428 passed, 1 skipped, 20 deselected**
- `npm run lint` → 0 warnings
- `npm run build` → static OK
- `.env`/`.env.local`/`token.json` no trackeados; `.gitignore` los cubre.

Estado del producto: **grado comercial verificado**. Las únicas piezas que
quedan code-ready pendientes de operación real son las que requieren tu acción
manual (no más credenciales):
- Correr `uv pip install google-auth google-auth-oauthlib` + `python scripts/auth_google.py`
  para generar `token.json` (Calendar/Drive read).
- Rotar las 3 credenciales que pegaste en el chat (ElevenLabs, OAuth Google,
  Maps API key) cuando termines de verificar — política del proyecto.

## 2026-05-15 - Inicio Fase 31 Google operativo

- Confirmado contra código real que Maps/Calendar/Drive existen y tienen tests,
  pero faltaba integrarlos plenamente a Action Plane/frontend.
- Iniciado bloque para: rutas con tráfico/link, Drive como carpeta de entregables,
  capacidades Google visibles, ActionRequest para escrituras Calendar/Drive y UI
  operativa.
- No se leyeron `.env`, tokens ni credenciales; todo cambio debe mantener la
  política de no exponer secretos en config pública, logs, docs ni tests.


## 2026-05-15 — Modelos LLM corregidos a la arquitectura del operador + Kimi WebBridge

Arquitectura LLM definida por el operador (sin modelos inventados):
- LLM general: DeepSeek V4 Pro
- Fallback LLM general: Kimi 2.6 (`K2.6-code-preview` @ api.kimi.com/coding/v1)
- Visión primaria: glm-4.6v (z.ai) — verificada multimodal con test live (pixel 1x1 → "pink")
- Visión fallback: Kimi 2.6

Cambios:
- `.env` / `.env.example` / `config.py` defaults: FALLBACK_LLM y
  VISION_FALLBACK_LLM ahora apuntan a Kimi 2.6. Revertido un intento previo
  erróneo de meter OpenRouter/Llama-3.2 como fallback de visión (el operador
  lo rechazó explícitamente; no usar modelos no mencionados).
- **Punto débil corregido**: `ChatVisionAnalyzer.from_settings` usaba
  `create_primary_chat_model()` (DeepSeek, text-only) en vez del modelo de
  visión dedicado. Ahora usa `create_vision_chat_model()` (glm-4.6v) con
  reintento automático en `create_vision_chat_model(fallback=True)` (Kimi 2.6)
  cuando el primario lanza. Nuevo `tests/test_vision_fallback.py` (6 tests)
  como regresión.
- glm-5v probado primero por petición del operador: devuelve 1211 "Unknown
  Model" en z.ai → se usa glm-4.6v (confirmado OK). Kimi 2.6 por API directa
  da `access_terminated_error` (solo Coding Agents), pero queda como fallback
  declarado por el operador; la cadena reintenta y si Kimi también falla, el
  error se propaga con log explícito (sin fallo silencioso).

Kimi WebBridge (navegación con el navegador real del usuario):
- `actions/kimi_webbridge.py`: servicio gateado por 3 capas (enable +
  allow-list de dominios + flag de mutaciones), provider HTTP al daemon local
  127.0.0.1:10086, FakeWebBridgeProvider para tests, audit EXTERNAL_ACTION.
- Validador de config rechaza KIMI_WEBBRIDGE_URL no-localhost; navegacion
  hereda el DNS/SSRF check del browser aislado cuando
  `ENABLE_BROWSER_SSRF_CHECK=true`.
- Las mutaciones directas se bloquean mientras
  `KIMI_WEBBRIDGE_REQUIRE_APPROVAL=true`; produccion rechaza mutaciones Kimi con
  aprobacion deshabilitada.
- 8 endpoints `/actions/webbridge/*` (status/navigate/snapshot/screenshot/
  click/fill/evaluate/list_tabs/close_session) todos JWT.
- 3 tools DeepAgents read-only (`browse_real_navigate/snapshot/screenshot`)
  con policy flag `allow_kimi_webbridge` (default OFF) + screenshot trunca
  base64 para no inundar el contexto.
- Health dashboard: componente `kimi_webbridge`.
- 17 tests `tests/test_kimi_webbridge.py`.

QA: **447 passed, 1 skipped, 20 deselected**; ruff/format/mypy strict verdes
(105 source files); frontend lint/build verdes; SETTINGS_REGISTRY_TABLE
regenerado; 0 credenciales filtradas a código/docs/tests.

## 2026-05-15 — CapSolver: resolución de captchas para toda navegación

Contrato CapSolver verificado contra docs.capsolver.com (no inventado):
createTask/getTaskResult, clientKey en body, ImageToTextTask inline (sin poll),
token tasks (ReCaptchaV2/V3ProxyLess, HCaptchaProxyLess, AntiTurnstileProxyLess)
con poll hasta status=ready.

- `actions/captcha.py`: `CaptchaSolverService` (gate ENABLE_CAPTCHA_SOLVING +
  key real), `CapSolverHttpProvider` real + `FakeCaptchaProvider`, Protocol
  inyectable, `_redact` borra clientKey/CAP- de errores, audit EXTERNAL_ACTION
  en cada intento, poll con deadline duro (`CAPSOLVER_MAX_POLL_SECONDS`),
  sleep inyectable para tests.
- Endpoints JWT: `/actions/captcha/status|image|token`.
- Tools DeepAgents `solve_image_captcha` / `solve_token_captcha` con policy
  flag `allow_captcha_solving` (default on; el servicio igual gate-a).
- **Cobertura "toda forma de navegación"**: el agente es el orquestador común
  de los 3 carriles (Playwright preview, Playwright interactivo, Kimi
  WebBridge). Detecta captcha (snapshot/screenshot) → llama la tool → inyecta
  el token (evaluate/fill). No se añadió step Playwright nativo a propósito:
  sería half-impl sin extracción automática de sitekey en un carril opt-in.
- Health: componente `captcha_solver`.
- Settings: ENABLE_CAPTCHA_SOLVING, CAPSOLVER_API_KEY, CAPSOLVER_BASE_URL,
  CAPSOLVER_POLL_INTERVAL_SECONDS, CAPSOLVER_MAX_POLL_SECONDS. Validador en
  config rechaza enable sin key real. .env real / .env.example placeholder /
  registry regenerado.
- 15 tests `tests/test_captcha.py` + 2 tests de tools sin red.

Verificación: **465 passed, 1 skipped, 20 deselected**; ruff/format/mypy
strict verdes (106 source files); frontend lint/build verdes; status live
`ready`; CapSolver key NO filtrada a código/docs/tests.

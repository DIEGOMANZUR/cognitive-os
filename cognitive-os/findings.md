# Findings

> Bitácora viva. Para producto: ver `docs/`.

## 2026-05-16 - Fase 37 auditoria integral por capas

Arranque:

- El operador pidio no limitarse a scripts y revisar el proyecto entero parte
  por parte antes de conectar todo.
- Criterio epistemico: no prometer "no hay nada mas por mejorar"; convertirlo
  en evidencia: cero P0/P1 abiertos, QA reproducible, contratos alineados y
  riesgos residuales explicitos.
- Baseline vigente: rama `codex/fase-34-baseline-hardening`, commits hasta
  `ca742d4`, full QA/readiness/pre-commit verdes, runtime core healthy.

Matriz de auditoria:

| Capa | Pregunta critica | Estado |
|---|---|---|
| Docs/claims | Lo que se promete coincide con codigo y comandos reales | in_progress: drift de Celery detectado y corregido |
| Backend/API | Endpoints, schemas, auth y errores son consistentes | pending |
| DB/migraciones | Modelos y Alembic estan en head y sin drift obvio | pending |
| Action Plane | Writes externos solo via approval + audit | pending |
| Agents/memory | LangGraph/DeepAgents/research/memoria no rompen contratos | pending |
| Frontend | Vistas/tipos/API client soportan estados reales | pending |
| Infra/runtime | Compose/scripts/health conectan sin exposicion accidental | pending |
| Seguridad | Secret hygiene, redaccion, cifrado, SSRF/path/RBAC | pending |
| QA/CI | Local y CI cubren lo que dicen cubrir | in_progress: test dirigido Celery verde |

Hallazgo 37.1 - Celery docs/runtime y rutas de tareas largas:

- Severidad: P1 operacional.
- Evidencia: el runtime registra 14 tareas `cognitive_os.*`, pero la
  documentacion viva todavia declaraba 11. Ademas,
  `cognitive_os.run_deepagent_task` y `cognitive_os.run_action_request`
  quedaban sin ruta explicita y por defecto podian caer en `default`, mezclando
  trabajo largo/externo con tareas rapidas.
- Correccion: documentacion principal sincronizada a 14 tareas; ambas tareas
  quedan ruteadas a `agent_longrun`.
- Verificacion: `uv run pytest tests/test_celery_config.py -q` -> **3 passed**;
  `uv run ruff check src/cognitive_os/workers/celery_app.py
  tests/test_celery_config.py` -> verde.

## 2026-05-15 - Pulido CI post-baseline

- El workflow CI estaba versionado bajo `cognitive-os/.github/workflows/ci.yml`.
  En el repo real, GitHub solo descubre workflows bajo `.github/workflows` en la
  raiz, por lo que ese CI no corria.
- Se movio a `.github/workflows/ci.yml` y se mantuvieron los working directories
  apuntando a `cognitive-os/backend` y `cognitive-os/frontend`.
- El job backend ahora instala con `--extra openharness`, igual que el full QA
  local, para evitar divergencia entre CI y operador.
- `verify_operator_ready.sh` era una verificacion parcial: no sincronizaba deps,
  no revisaba `ruff format`, no hacia `npm ci` y mostraba Alembic como dato
  informativo aunque estuviera detras de head. Ahora esas comprobaciones son
  compuertas reales.

## 2026-05-15 - Baseline git seguro

- `detect-secrets --all-files` sobre todo el workspace incluye tambien archivos
  ignorados; por eso reportaba `.env`, `.env.local`, `opencode.json`, vendor
  `.openharness_upstream` y `tsconfig.tsbuildinfo`. Esos no son versionables y
  estan cubiertos por `.gitignore`.
- El escaneo correcto para baseline usa `git ls-files --cached --others
  --exclude-standard` como fuente de archivos versionables. Ese escaneo quedo
  limpio (`results: {}`).
- `pre-commit` real detecto dos fixtures de redaccion con patrones de llave y
  un limite bajo para `uv.lock`; ambos quedaron corregidos. `gitleaks` pasa.
- Decisión: permitir `uv.lock` hasta 1024 KB en hooks para preservar lockfiles
  reproducibles sin abrir la puerta a artefactos grandes arbitrarios.

## 2026-05-15 - Reconciliacion runtime local

- El codigo ya tenia head Alembic `202605150002`, pero la base local seguia en
  `202605140001`. Se aplicaron `202605150001` y `202605150002` hasta quedar en
  `202605150002 (head)`.
- Los contenedores existentes habian sido creados con bindings antiguos:
  Postgres, Weaviate y Neo4j aparecian publicados en `0.0.0.0`. La configuracion
  vigente ya era loopback; `docker compose up -d` recreo solo los servicios
  necesarios y dejo todos los puertos criticos en `127.0.0.1`.
- El baseline git seguia propenso a incluir material no fuente:
  `cognitive-os-backup-*`, `cognitive-os-snapshot-*`, transcripciones
  recuperadas y `cognitive-os/.claude/settings.local.json`. Se agregaron reglas
  explicitas en `.gitignore` y fueron verificadas con `git check-ignore -v`.

## 2026-05-15 — Fase 33 RBAC + cifrado + research durable

Hallazgos confirmados antes de implementar:

- Auth local no tenía RBAC explícito: `create_access_token` emitía sólo `sub/iat/exp`,
  `AuthenticatedUser` sólo exponía `is_admin`, y `_is_admin_user` trataba lista
  `ADMIN_USER_IDS` vacía como admin para todos.
- `payload_executable` está separado de `payload_redacted`, pero persiste JSON
  ejecutable en claro. El cierre comercial requiere cifrado at-rest y fallback
  controlado para filas históricas.
- Research Orchestrator conserva runs/eventos en un dict en memoria. El API SSE
  funciona bien durante el proceso, pero lista/get no sobreviven restart si no se
  activa un backend durable.
- Fase 32 ya cerró varios riesgos detectados previamente: Google direct writes,
  loopback infra, reaper en beat, redacción OAuth/Drive/health y PWA hardening.

Resultado implementado:

- Admin implícito eliminado; JWT local soporta roles y LangSmith queda protegido
  por admin por defecto.
- `payload_executable` queda cifrable con Fernet y producción rechaza operar sin
  clave + `ACTION_PAYLOAD_ENCRYPTION_REQUIRED=true`.
- `research_runs` persiste snapshots/eventos de Research Orchestrator cuando
  `RESEARCH_PERSISTENCE_BACKEND=postgres`; producción exige ese backend.
- QA Fase 33: 492 passed, 1 skipped, 20 deselected; ruff/format/mypy/frontend
  lint/build/Compose/Alembic/diff verdes.

## 2026-05-15 — Fase 32 hardening comercial

Hallazgos P0/P1 cerrados tras Google operativo:

- **Secreto inline MCP**: `opencode.json` contenía `EXA_API_KEY` como valor
  directo. Se reemplazó por `{env:EXA_API_KEY}`. El valor debe rotarse fuera de
  esta sesión porque ya estuvo en un archivo local.
- **Bypass de aprobación Google**: los endpoints directos Calendar/Drive podían
  ejecutar con `dry_run=false` si el caller tenía JWT y flags activos. Ahora
  `events/create`, `files/upload` y `folders/ensure` son preview-only y devuelven
  `409` para writes directos; el carril real es `/request` + `HumanApproval` +
  Celery + audit.
- **Config peligrosa en producción**: producción ya no permite write flags de
  Calendar/Drive si `REQUIRE_HUMAN_APPROVAL_FOR_EXTERNAL_ACTIONS=false`.
- **Errores con metadata sensible**: OAuth/Drive/health podían reflejar rutas
  locales o detalles de token. Se redactan rutas absolutas, `token.json` y
  valores con forma de secreto.
- **Reaper no agendado**: `cognitive_os.reap_stuck_action_requests` quedó routeado
  a `maintenance` y agendado cada 10 minutos en Celery beat.
- **Infra expuesta por defecto**: Compose publica Postgres, Redis, Weaviate y
  Neo4j sólo en `127.0.0.1`; `.env.example` queda alineado con puertos reales.
- **PWA/comercial**: Next añade headers de seguridad, el service worker versiona
  cache y mantiene rutas API-like network-only, y el componente PWA muestra
  estados de offline/update/install.
- **QA**: targeted hardening `52 passed`; full backend `484 passed, 1 skipped,
  20 deselected`; ruff, format, mypy, frontend lint/build y Compose config verdes.

## 2026-05-15 04:47 (hora Chile) — Verificación de auditoría documental

Nota Fase 37: esta sección queda como snapshot histórico de ese instante. Los
conteos vigentes se verifican en la sección 2026-05-16.

Sweep autónomo no destructivo (solo docs). Conteos verificados contra
código real, no contra documentación previa:

- **Endpoints REST**: 115 totales sumando `@router.{get,post,put,patch,delete}`
  bajo `backend/src/cognitive_os/api/routes/`. La cifra histórica de "89
  endpoints" se refiere solo al subconjunto de propios Cognitive OS sin
  contar orquestación/transversales — ambas cifras son consistentes y se
  documentan explícitamente en `README.md` y `docs/COGNITIVE_OS_GUIDE.md`.
- **Vistas frontend**: 17 reales (no 16) tras sumar `AssistView` el
  2026-05-14. Verificadas con `ls frontend/app/views/*.tsx`.
- **Skills `.opencode/`**: 15 (no las 13 que ciertos docs antiguos
  mencionaban; las nuevas son `dual-memory-recall`, `huggingface-hub`,
  `kimi-webbridge`, `opencode-operator`, `memory-bank`).
- **MCPs**: 21 conectados/wrapped (`docs-langchain`, `weaviate-docs`,
  `sequential-thinking`, `playwright`, `chrome-devtools`,
  `github-official`, `tavily`, `brave-search`, `gh_grep`, `deepwiki`,
  `exa`, `huggingface`, `neo4j`, `weaviate`, `memory-bank`, `context7`,
  `langsmith`, `supermemory`, más wrappers locales).
- **Workers Celery**: 11 tareas registradas, 5 queues activas. La queue
  `mail` quedó incluida en `scripts/dev_worker.sh` el 2026-05-14.
- **Migraciones Alembic**: 13 archivos en
  `backend/src/cognitive_os/db/alembic/versions/` (la última es
  `202605140001_mail_accounts_messages`).
- **Sin discrepancias críticas** entre código y docs después de este sweep.
- **Sin secretos en árbol**: confirmado por grep del `.env.local` actual y
  reglas de pre-commit (`gitleaks`).

## 2026-05-14 — Auditoría integral grado comercial

Sweep autónomo en 5 ejes de riesgo. Cero hallazgos críticos abiertos; un
endurecimiento menor cerrado:

- **Silent failures**: los dos helpers de audit (`_audit_calendar`,
  `_audit_drive`) usaban `except Exception: return`. Convertidos a
  `except Exception as exc: log.warning(...)`. Los demás suppress del proyecto
  son legítimos (degradación documentada, predicates, cleanups en `finally`).
- **Secrets en árbol**: grep agresivo de los 5 valores reales del `.env`. 0 fugas.
- **Auth**: 98 endpoints enumerados. 0 sin proteger (sólo `/health` es público
  como debe ser). Verificado vía ASGI sin JWT — todos devuelven 401.
- **Concurrencia**: locks correctos, `asyncio.run` siempre en bordes sincrónicos
  o detrás de `_run_async()` que detecta loop activo y falla rápido.
- **Boundaries**: validación estricta en upload de Drive (path allow-list, cap
  de tamaño, traversal rechazado), Calendar (ventana temporal), Maps (URL
  params via httpx).
- QA final: 428 passed, ruff/mypy/format verdes (104 archivos), frontend lint y
  build verdes.

## 2026-05-14 — Fase 25 C/D + Maps + Voz implementadas

- **Riesgo de seguridad registrado**: el operador pegó credenciales reales
  (ElevenLabs, OAuth Google, API key Maps) directamente en el chat. Quedaron
  en el transcript de la conversación. Por la propia regla de `docs/SECURITY.md`
  ("rotar claves si aparecen en logs, prompts, reportes"), esas tres
  credenciales deben **rotarse** una vez verificado el funcionamiento. Se
  escribieron sólo en `cognitive-os/.env` (gitignored, perms 600); nunca en
  código, tests, docs ni en respuestas.
- Maps y voz son integraciones API-key puras → totalmente verificables por
  tests (providers fake, sin red). Calendar/Drive usan el patrón OAuth de
  `GmailRestReader`: `google-auth` se importa de forma perezosa, no se agregó
  a `pyproject.toml` para no tocar `uv.lock`/CI; el operador lo instala al
  habilitar la capacidad real.
- Decisión de alcance: Calendar/Drive salen **read-only** en este corte. Crear
  eventos o subir archivos son acciones externas y deben ir por
  `ActionRequest`/aprobación — se deja como seguimiento explícito, no como
  implementación a medias (mismo criterio que Gmail en Fase 21).
- La schema `DocumentChunk` de Weaviate no tiene propiedad per-usuario; Maps no
  la usa, pero se mantiene el criterio de la 25.E: si en el futuro se cachean
  rutas/lugares, el aislamiento por usuario va por post-filtro de metadata.
- QA tras la jornada completa: **389 passed, 1 skipped, 20 deselected**
  (inicio del día: 341); `ruff`/`ruff format`/`mypy --strict` y frontend
  `lint`/`build` verdes.

## 2026-05-14 — Revisión integral + decisiones Fase 25 resueltas

- Revisión desde cero (26 markdowns + núcleo backend + QA completo). Veredicto:
  el código implementado **ya es grado comercial**: `pytest` 341→347 passed,
  `ruff`/`ruff format`/`mypy --strict` verdes, frontend `lint`/`build` verdes,
  CI y pre-commit presentes, `.env`/`.env.local` no trackeados. No se hallaron
  bugs ni fugas de secretos ni anti-patrones en el código existente.
- **Decisiones bloqueantes Fase 25 resueltas por el operador**:
  1. Mail GoDaddy (`diego@doctormanzur.com`): **IMAP/SMTP nativo GoDaddy** →
     confirma que el carril `mail/` actual es la arquitectura correcta; falta
     solo hardening multicuenta.
  2. Política Gmail send: **solo proponer texto** (sin `gmail.compose`) →
     confirma el comportamiento read-only actual; no se añade scope nuevo.
  3. Agenda: **Google Calendar** (reusa OAuth Gmail). Requiere credenciales.
  4. Voz STT/TTS: **ElevenLabs**. Requiere `ELEVENLABS_API_KEY`.
  5. Multi-cuenta: **N desde el inicio** (default recomendado).
  6. Markdown vault de notas: **opcional, off por defecto** (default recomendado).
- **Subfase 25.E (notas semánticas) — IMPLEMENTADA y verde**:
  `assist/note_index.py` (`NoteIndexService` + Protocol `NoteVectorStore`),
  indexado best-effort en Weaviate (`doc_type="note"`) en create/update/delete
  de `PersonalAssistService`, endpoint `GET /assist/notes/search`, aislamiento
  por `user_id` vía post-filtro (la schema `DocumentChunk` no tiene propiedad
  per-user). Degradación graciosa: un Weaviate caído nunca rompe el CRUD de
  notas. 6 tests nuevos sin red (`tests/test_note_index.py`).
- Subfases 25.A/B confirmadas como mayormente existentes (mail GoDaddy ya está);
  25.C/D (voz ElevenLabs, Google Calendar) quedan code-ready pendientes de
  credenciales; 25.F/G/H pendientes de implementación incremental.

## 2026-05-14 - Hallazgos hardening frontend

- El frontend persistía el JWT local en `localStorage` (`cogos.jwt`), lo que era
  innecesario para el cockpit y aumentaba el riesgo de exposición. Se cambió a
  estado efímero en React y se mantuvo la persistencia sólo para preferencias no
  secretas como API base, tab y tema.
- `ApiClient` enviaba `Content-Type: application/json` incluso en requests sin
  body. Esto no siempre rompe FastAPI, pero es una señal incorrecta para GET y
  DELETE; ahora sólo se añade cuando existe body.
- El polling anterior no abortaba la petición HTTP en vuelo; sólo evitaba algunos
  commits obsoletos. `AbortController` reduce trabajo innecesario y evita errores
  visuales al cambiar rápido de vista/filtro.
- El contrato backend ya exponía CRUD personal `/assist/tasks` y `/assist/notes`,
  pero el frontend no tenía entrada operativa. La nueva vista Assist cubre ese
  flujo sin tocar backend.

## 2026-05-14 - Hallazgos normalización documental

- `scripts/dev_worker.sh` no escuchaba la queue `mail` aunque
  `sync_personal_mail` está ruteado a esa cola. Se corrigió para evitar que el
  flujo manual de desarrollo deje mail sin worker.
- La documentación viva debía subir al conteo real de 89 endpoints propios y 16
  vistas por la incorporación de `/mail/*` y `MailInboxView`.
- Las referencias a modelos OpenAI antiguos como runtime local son obsoletas para
  este workspace: el runtime base actual documentado y configurado es DeepSeek V4 Pro; vision se
  mantiene como LLM multimodal configurable.

## 2026-05-14 - Hallazgos mail personal

- El repo solo tiene Gmail OAuth read-only (`actions/gmail_digest.py`) y status
  preview en `actions/mail.py`; no existe soporte IMAP/SMTP ni multicuenta.
- `PersonalNote` existe como CRUD DB, pero no tiene vector/BM25 ni Notion sync.
- No se encontraron implementaciones backend para calendar, ElevenLabs TTS,
  YouTube o audio; las claves existen en config/env pero faltan servicios.
- Para el primer corte de mail no hace falta dependencia externa: IMAP/SMTP se
  puede resolver con `imaplib`, `smtplib` y `email` de stdlib, manteniendo
  mocks/testeo simple.
- GoDaddy IMAP acepto conexion y lectura real con las credenciales locales. El
  primer sync recupero 25 mensajes de carpetas configuradas y no reporto
  errores.
- Gmail `TODOS` queda soportado a nivel de servicio si `GMAIL_READ_ENABLED` y
  `token.json` estan configurados, pero en el `.env` actual no esta habilitado.

## 2026-05-13 — Endurecimiento del bridge OpenHarness

- **Punto débil corregido**: `run_openharness_research_sync` usaba
  `asyncio.run()` directo. Si el grafo se invocaba desde un caller con event
  loop activo (cualquier endpoint async, scripts, posibles workers async),
  fallaba con `RuntimeError: asyncio.run() cannot be called from a running
  event loop` y caía silenciosamente con `openharness_async_runtime_error`.
  Solución: `_execute_engine_blocking` aísla la ejecución en un hilo dedicado
  con su propio `new_event_loop`, cerrando con `shutdown_asyncgens`.
- **Punto débil corregido**: las lambdas en `build_tool_registry` (preset
  `research`) hacían fallar `mypy --strict` (`Call to untyped function`).
  Solución: instanciar directamente y registrar en bucle.
- **Punto débil corregido**: `OPENHARNESS_TOOLKIT_PRESET` y
  `OPENHARNESS_WORKSPACE_MODE` tenían descripciones >100 chars que rompían
  `ruff E501`. Reescritas en multilínea.
- **Punto débil corregido**: la migración `202605120006_personal_tasks_notes`
  tenía 4 columnas con server_default sa.func.now() en una sola línea (>100
  chars). Reescritas en multilínea idiomática.
- **Punto débil corregido**: `.env.example` no listaba ninguna variable
  `OPENHARNESS_*`; ahora incluye un bloque con defaults y comentarios alineados
  con `Settings`.
- **Hallazgo (no rompe)**: `/chat`, `/chat/stream`, `/threads/{id}/resume`
  ya invocan el grafo vía `asyncio.to_thread`, así que `research_node` corre
  en hilo y la versión anterior de `asyncio.run` "casualmente" funcionaba
  desde la API pública. La nueva implementación lo formaliza y permite uso
  desde cualquier contexto.

## 2026-05-13 — Fusión OpenHarness + DeepAgents (research)

- La ruta `research` combina LangGraph + OpenHarness opcional + DeepAgents.
  Pipeline por defecto **`prelude_merge`** (preludio OH inyectado al
  `HumanMessage` que recibe DeepAgent); alternativa **`short_circuit`** que
  devuelve sólo OpenHarness cuando responde válido.
- Workspace por defecto **`deepagent_mirror`**:
  `LOCAL_STORAGE_DIR/workspaces/{thread_id}/{thread_id}-research`.
- Presets de tools: `minimal | research | full`. `OPENHARNESS_INCLUDE_FILE_TOOLS`
  sólo afecta a `minimal` (en `research`/`full` los file tools ya están).
- Búsqueda web dentro de OpenHarness exige
  `WEB_SEARCH_ENABLED && OPENHARNESS_WEB_TOOLS`.
- Documentación canónica: `docs/OPENHARNESS_FUSION.md`. Tests:
  `backend/tests/test_research_openharness_priority.py` y
  `backend/tests/test_openharness_research.py`.

## 2026-05-13 — Corrección README sobre `cognitive-os`

- `uv run cognitive-os` apunta a `cognitive_os.__main__:main`, que sólo emite un
  log `Cognitive OS bootstrap OK`. **No** es el servidor API. Para arrancar el
  API real: `uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000`
  como ya documenta `docs/RUNBOOK.md`.

## 2026-05-12 - Initial Project Recon

- Active project appears to be `/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os`.
- Parent directory contains backups/snapshots; active tree has backend, frontend, infra, docs, scripts, storage and experiments.
- No `.git` directory was found in parent or active project during initial inspection.
- `planning-with-files-es` and `planning-with-files` are installed under `/home/jgonz/.codex/skills`.

## 2026-05-12 - Baseline Checks

- Backend pytest baseline passed: 144 passed, 1 skipped, 19 deselected.
- Frontend lint baseline passed.
- Backend Ruff baseline failed before any project edits:
  - `src/cognitive_os/core/config.py`: one line over 100 chars.
  - `src/cognitive_os/core/config.py`: three SIM102 nested-if simplifications.

## 2026-05-12 - Architecture Snapshot

- Backend uses FastAPI, LangGraph, Celery, Postgres, Redis, Weaviate, Neo4j, DeepAgents and OpenShell sandbox integration.
- Frontend is Next.js 16 / React 19 console with operational views.
- Existing settings already include browser automation, Gmail, Microsoft mail and GoDaddy flags.
- Existing policy layer has risk classes and human approval mechanics.
- Existing DeepAgents policy blocks shell/browser/email/social/delete by default.
- OpenShell sandbox exists but its adapter currently reports that a safe one-shot runner is not implemented.

## 2026-05-12 - External Capability Gap

- Browser/Gmail/GoDaddy variables exist, but the project needs a concrete "action plane" abstraction:
  - capability status
  - dry-run previews
  - allow-list validation
  - audit records
  - approval request generation
  - tests for dangerous paths/domains/scopes

## 2026-05-12 - Tooling Notes

- Browser and Chrome automation plugins are already available in Codex.
- Gmail plugin suggestion was attempted, but user reported the authorization browser hangs.
- No GoDaddy connector/plugin is available in the current discoverable tool list.

## 2026-05-12 - External Docs Checked

- Playwright Python official docs: persistent contexts use a dedicated user data directory for cookies/local storage; automating the user's default Chrome profile is not supported and a separate automation profile should be used.
- Playwright official docs: browser contexts are the isolation boundary and avoid cross-task state leakage.
- Camoufox official docs: Camoufox wraps the Playwright API and adds generated device/browser characteristics.
- Gmail official quickstart: production should use proper OAuth/auth review; quickstart uses `gmail.readonly`, stores OAuth tokens on disk, and uses Google client libraries.
- GoDaddy official Domains API docs: OTE base URL is `https://api.ote-godaddy.com`; production base URL is `https://api.godaddy.com`.
- GoDaddy official MCP page: public MCP endpoint exists at `https://api.godaddy.com/v1/domains/mcp`, but it is read-only and cannot modify DNS records or domain settings.

## 2026-05-12 - Documentation Cleanup

- Root-level `explicacion_sistema_cognitive_os.md` duplicated project explanation outside the canonical docs tree and was deleted after replacement by `docs/PROJECT_GUIDE.md`.
- `docs/README.md` now serves as the documentation index.
- `ACCEPTANCE_CHECKLIST.md` now separates automated verification from manual infra/credential acceptance.

## 2026-05-12 - Action Request Lifecycle

- The previous action plane was only validation/preview, which is safe but not
  enough for a commercial operator workflow.
- A persistent action unit is now present: `ActionRequest -> HumanApproval ->
  Job/Celery -> AuditEvent -> result/error`.
- `computer_organize` is the only real executor for now because it is local,
  deterministic and testable with temporary directories.
- Browser, Gmail and GoDaddy should remain preview/validation until their real
  executors include provider-specific authentication, rate limits, idempotency,
  token storage, diffs and rollback strategy where possible.
- UI now covers the first operational loop: approval of an action request can
  dispatch it, and recent requests are visible from `Configuracion`.

## 2026-05-12 - Phase 9 Insights

- Browser, Gmail and GoDaddy persistence was missing: no operator could see
  history of what the agent proposed nor why it was blocked.
- Reuse of the persistence path via `_persist_preview_request` keeps audit and
  redaction consistent. Each request stores `payload_redacted`, `preview`,
  `error` (only when blocked) and an `audit_event`.
- `cancel_action_request` must refuse to cancel `running` states because the
  Celery worker holds the only authoritative process; it must also be a no-op
  for terminal states (`completed`, `failed`, `cancelled`, `rejected`) to avoid
  redundant audit noise and accidental state churn.
- Filters on `GET /actions/requests` use FastAPI `Annotated[..., Query(alias=)]`
  to keep query parameter names operator-friendly (`status` instead of
  `request_status`) without colliding with the imported `status` symbol from
  FastAPI.

## 2026-05-12 - Phase 10 Insights (Documents)

- `document_generate` is a useful first real executor for an external-action
  loop beyond `computer_organize` because:
  - It only writes inside an allow-listed root (`DOCUMENT_OUTPUT_ROOT`).
  - It cannot exfiltrate data or call the network.
  - It has a clear size cap (`DOCUMENT_MAX_SIZE_BYTES`) that we enforce after
    write by deleting the offending file.
  - It composes cleanly with the existing `ActionRequest` lifecycle so the
    operator workflow (approve -> dispatch -> Celery -> audit) is reused.
- Path validation must reject absolute paths, `..` components and empty names
  before resolving against the allow-listed root. We also normalize the
  filename suffix to the requested format to avoid `report.docx -> .DOCX`
  inconsistencies and confused-deputy edge cases on case-insensitive FS.
- `python-docx` ships its own type stubs in current versions, so the
  `# type: ignore[import-untyped]` is rejected by mypy as unused. We keep
  `openpyxl` and `pptx` under `ignore_missing_imports` because they do not
  ship stubs.
- For PPTX, we build the title slide from layout 0 and bullet slides from
  layout 1. This avoids depending on theme-specific custom layouts and works
  with the default Office template that python-pptx provides.
- We keep `requires_approval=True` for `document_generate` even though the
  blast radius is small: it makes the executor symmetric with
  `computer_organize` and lets the operator see a preview before any bytes
  hit disk.

## 2026-05-12 - Phase 11 (Browser headless preview)

- Real browser execution is intentionally **opt-in**. The default code path
  does not require `playwright` to be installed; when it is missing, the
  executor returns `status="blocked"` with a clear reason and never raises
  an opaque ImportError to the operator. To activate real previews the
  operator must run `uv sync` and `playwright install chromium` on the host.
- The service uses a Protocol-based provider (`BrowserPreviewProvider`) and
  a factory hook (`provider_factory: Callable[[Settings], BrowserPreviewProvider]`).
  Tests inject Fake/Huge providers so they exercise the full lifecycle
  (validate -> ActionRequest -> execute -> bytes cap -> file cleanup) without
  spawning a browser or hitting the network.
- Validation refuses non allow-listed domains via the existing
  `validate_allowed_browser_domain` and refuses headed mode (this executor is
  headless-only by design; vision and credentialed profiles are kept out of
  Phase 11 until explicit human consent and per-site profiles are wired).
- The screenshot is written under `BROWSER_SCREENSHOT_DIR`, then checked
  against `BROWSER_SCREENSHOT_MAX_BYTES`. If it exceeds the cap, the file is
  deleted before returning `blocked` so we never leave oversize artifacts on
  disk after a failed run.
- A small ruff catch was that the `BrowserPreviewProvider.run` return type
  used quoted annotations (`"BrowserPreviewProviderResult"`) when forward
  reference was no longer required (the class is declared above the
  Protocol). Removed the quotes per `UP037`.

## 2026-05-12 - Phase 16 (RAG robustness) Insights

- **Dual-write inconsistencia**: el pipeline escribia `DocumentChunk.status="indexed"` en el mismo `session_scope` de traceabilidad, ANTES de tocar Weaviate. Si Weaviate fallaba, Postgres quedaba con chunks claimando estar indexados, pero queries devolvian cero. Lesson para futuros dual-writes: el sistema con menor garantia transaccional (Weaviate aqui) define el "fin de la operacion"; el otro lado solo se marca `pending` hasta que el primero confirma. Patron: `pending_index` -> verificacion del lado debil -> `indexed`.

- **Idempotencia por contenido**: re-ingerir el mismo PDF generaba duplicados completos (nuevo `Document`, nuevas chunks, nuevos vectores). Causa: la unique constraint era `(sha256, source_path)`, pero el usuario puede mover el archivo y la ruta cambia. El campo invariante es el `sha256`. Lesson: para dedup semantico, indexar por el hash del contenido, no por path/nombre. Fix: lookup explicito en `_existing_indexed_document(sha256)` antes de crear; reutiliza solo si el `Document` esta `indexed` y todos sus chunks tambien.

- **Costo de N HTTP**: ingerir un PDF de 500 chunks disparaba 500 POST + 500 embedding calls. Latencia, costo, y rate limits sufrian. Lesson: batchear es obligatorio cuando hay APIs externas detras. Fix: `embed_texts(list, kind=...)` ya existia; solo faltaba un consumidor que lo usara, y un endpoint Weaviate de batch (`/v1/batch/objects`) que devuelve status por-objeto. El gotcha es que Weaviate devuelve HTTP 200 incluso si algunos objetos fallaron — hay que inspeccionar `result.errors` por-item.

- **Resiliencia parcial**: si embeddings caia (clave invalida, quota, outage), el chat 500-eaba. La gente acepta busqueda peor a busqueda imposible: BM25-only es un downgrade aceptable. Lesson: sistemas RAG deben tener un modo "puro keyword" como fallback de degradacion. Fix: try/except alrededor del embed_text, alpha=0, omit `vector:` del GraphQL (algunas versiones rechazan vector vacio).

- **Lock pattern en double-checked init**: `if self._collection_ensured: return` sin lock es race. Dos hilos pueden hacer GET, GET ambos retornan 404, ambos POST, el segundo recibe 422. Fix correcto: lock + re-check dentro del lock + aceptar 422 "already exists" como no-op (defensa en profundidad por si OTRO proceso, no solo otro thread, gano la carrera).

## 2026-05-12 - Phase 15 (Correctness critico) Insights

- **HITL guarantee breach (bug #1)**: `execute_organize_plan` reconstruia el plan desde el filesystem en cada ejecucion. Sintoma: el operador aprobaba "mover A.pdf -> PDFs/", pero entre approval y dispatch alguien creaba B.pdf, y el worker movia AMBOS. Lesson: cualquier capa que se interponga entre "preview que el humano ve" y "lo que el worker hace" rompe el contrato de aprobacion. Fix: el plan aprobado se persiste en `action_request.preview`, se parsea con `ComputerOrganizePlan.model_validate`, y el executor ejecuta exactamente esas operaciones revalidando cada una contra el FS actual (si el source ya no existe, se reporta `failed`; no se re-deriva).

- **Redactor ataco la ejecucion (bug #2)**: `payload_redacted` se usaba como entrada del executor. Para schemas reales no se redactaba nada (ni `root_path` ni `output_filename` matchean patrones de secrets), pero un usuario que escribiera "password=foo" en un titulo de documento lo veria literalmente reemplazado por `[REDACTED]` en disco. Lesson: NO usar payloads redactados para ejecucion; redactar es una transformacion lossy para auditoria, no para reproducibilidad. Fix: columna `payload_executable` separa los dos roles.

- **Status semantica vaga (bug #3)**: `DeepAgentResult.status` mezclaba "ok pero no produje contenido" (empty answer) con "ok aqui esta la respuesta". El research_node trataba ambos igual. Lesson: un campo tipado no garantiza semantica clara; hay que validar el contenido tambien. Fix: agregar `.strip()` check sobre `deep_result.answer` antes de tratar `status="ok"` como exito.

- **Falta de row lock (bug #5)**: Dos workers podian leer `status="queued"`, ambos pasar a `running`, y ejecutar la accion dos veces. Lesson: en transiciones de estado donde mas de un actor puede actuar, `SELECT ... FOR UPDATE` no es una decoracion: es la primitiva que evita interleaving. Fix: `with_for_update()` + chequeo pre-flush; el primero gana, el resto retorna idempotente.

- **Default-allow vs default-deny (bug #6)**: `read_document_pages` aceptaba cualquier doc_id valido por UUID. La policy era binaria (allow_local_rag: bool), no scope-bound. Lesson: una tarea con doc_ids autorizados debe enforcement-ar esa lista en cada lectura; "lista vacia" debe significar "no podes leer nada", no "podes leer todo". Fix: factory threads `task.allowed_doc_ids` y la tool rechaza por defecto.

- **Polucion implicita del RAG (bug #8)**: `search_local_docs` y `retrieve_context` no filtraban `doc_type`. El web_indexer guardaba snippets con `doc_type="web"`, y queries "locales" recibian ambos mezclados. Lesson: separar fuentes en el indice no basta; el consumidor debe filtrar EXPLICITAMENTE. Fix: nuevo parametro `exclude_doc_types` y `WeaviateStore` soporta operador `NotEqual` para el WHERE GraphQL.

- **Auditoria asimetrica (bug #10)**: `_audit` se llamaba solo al final de la rama feliz. Policy violations y errores se enviaban al agent loop pero **nunca quedaban en el audit log**. Lesson: la auditoria de seguridad no puede vivir solo en el happy path; cualquier intento (exitoso o no) tiene que dejar trazo. Fix: `_audit_error(tool_name, args, reason)` se invoca en cada return de error en cada tool de deepagents.

- **Paths absolutos en respuestas al usuario (bug #20)**: `RetrievalCitation.citation` exponia `/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/.../doc.pdf` al usuario final. Esto leakea el layout interno del servidor. Lesson: para datos derivados de configuracion/host, distinguir entre "lo que guardas para trazabilidad" (full path en metadata) y "lo que mostras al usuario" (basename o titulo). Fix: helper `_source_display(source_path, title)` con splitter `/`-y-`\` portable.

- **`PurePosixPath` no detecta `\\` en Linux**: al implementar el splitter para citas, intente usar `PurePosixPath` + `PureWindowsPath` y quedarme con la mejor. Pero `PurePosixPath("C:\\foo").name` devuelve el string completo (Linux no trata `\\` como separador). Lesson: para portar codigo cross-platform sin tocar el FS, hacer el splitter a mano con `rfind("/")` y `rfind("\\")` es mas predecible que apoyarse en `pathlib`. El `pathlib` esta sesgado por el OS del intérprete.

## 2026-05-12 - Phase 14 (Research Orchestrator async + SSE) Insights

- Auditoria del orquestador encontro que `start_run` invocaba `_execute`
  sincronamente. El sintoma era que el `POST /research/runs` se bloqueaba hasta
  por `time_budget_seconds` (clamped a 300s por defecto, hasta 3600s). Esto
  hace que la cancelacion via `POST /research/runs/{id}/cancel` sea inalcanzable
  porque el cliente esta atrapado esperando la respuesta del POST. El bug fue
  invisible durante Fase 12 porque los tests usaban fakes rapidos.
- Fix elegido: ejecutar `_execute` en un `threading.Thread(daemon=True)` y
  retornar de inmediato con la run en estado no-terminal. Agregar
  `done_flag: threading.Event` para que `wait_for_run` pueda bloquear sin
  hacer polling. Daemon=True garantiza que el proceso pueda salir incluso
  si un run cuelga.
- Para el SSE endpoint el patron correcto es leer `run.events` (lista, no
  cola). El acceso a `list[X]` bajo CPython es atomico via GIL, asi que el
  snapshot `list(run.events)` es seguro contra modificaciones concurrentes
  del thread productor. El cursor `last_idx` se actualiza despues de
  consumir el snapshot, garantizando que ningun evento se pierde ni se
  duplica entre iteraciones. La alternativa con `Queue` no funciona para
  multiples clientes SSE (la cola es single-consumer).
- El poll interval del SSE es 50 ms: lo suficientemente corto para latencia
  baja en UI sin reventar la CPU. Para una run de 60 s eso son 1200 iteraciones,
  cada una con un `list()` corto y `await asyncio.sleep(0.05)` que cede el
  loop. Una notificacion via `asyncio.Event` por run seria mas eficiente
  pero requiere coordinar entre el productor (thread sincronico) y el
  consumidor (event loop), lo cual se logra con `asyncio.run_coroutine_threadsafe`.
  En esta fase se prefiere la simplicidad del polling corto.
- El bug demuestra que tener tests "verdes" no es suficiente cuando el
  feedback loop esta tomando shortcuts (fakes rapidos que ocultan el costo
  de produccion). Tests nuevos que asertan `elapsed < 0.2s` evitan regresion.

## 2026-05-12 - Phase 13 (Gmail Daily Digest) Insights

- El digest es preview-only por diseno: no toca Gmail ni siquiera para crear
  drafts. La forma correcta de probar la logica de redaccion y ordenamiento
  sin OAuth es inyectar un `GmailReader` Protocol y proveer
  `FakeGmailReader([message_dicts])` que devuelve datos preparados.
- Redaccion de direcciones: para `local` de tamano <= 2 chars se redacta a
  asteriscos completos; para mas largos se mantienen el primer y ultimo char.
  El dominio queda visible para que el operador pueda decidir riesgos de
  proveedor (`gmail.com` vs `proveedor-pequeno.tld`).
- `GmailDigestProposedDraft` lleva `requires_approval=True` siempre. El
  borrador no se persiste en Gmail aunque la flag de send este activa: la
  Fase 13 es un loop "leer -> proponer -> aprobacion humana antes de tocar
  el mailbox". El executor real (Fase futura) recogeria estos drafts solo
  bajo aprobacion.
- El singleton `_gmail_digest_reader` en `api/app.py` permite que la app
  arranque sin un reader configurado (estado `blocked` con razon clara). Los
  tests inyectan un FakeGmailReader via monkeypatch.

## 2026-05-12 - Phase 12 (Research Orchestrator)

- `deepagents>=0.5.5` ya estaba integrado con `run_research_deepagent` y
  politicas estrictas (`DeepAgentToolPolicy`). Construir un planner/research/
  synth/score independiente seria duplicar codigo y romper la auditoria del
  subagente real. Decision: la Fase 12 orquesta encima de deepagents, no lo
  sustituye. El `DeepAgentResearcher` default es un thin wrapper sobre
  `run_research_deepagent`.
- `concurrent.futures.ThreadPoolExecutor` usado como context manager (`with`)
  bloquea el `__exit__` hasta que todos los workers terminen. Eso rompe el
  presupuesto de tiempo cuando una subtask se queda esperando. Solucion:
  usar el executor explicitamente con `try/finally` + `executor.shutdown(
  wait=False, cancel_futures=True)` para devolver el control al orquestador
  apenas vence el deadline.
- Pydantic 2 rechaza `time_budget_seconds=1` y `max_subtasks=99` con
  `ge=5/le=32` definidos en `ResearchRunRequest`. Eso es deseable: el cliente
  no puede pedir parametros fuera de rango. Para pruebas de "clamping"
  contra Settings, se usan los limites externos validos del request (3600 y
  32) y se baja el `Settings` con `monkeypatch` para verificar que el
  orquestador aplica el min(settings, request).
- Ruff `N818` exige sufijo `Error` en excepciones; renombrar
  `ResearchOrchestratorDisabled` -> `ResearchOrchestratorDisabledError` y
  actualizar imports + `__all__`.
- El `HeuristicScorer` calcula un score 0..1 con rubrica auditable y sin
  LLM. Un futuro `LLMScorer` puede inyectarse via `scorer=` sin cambiar el
  orquestador.
- Store in-memory en `api.app._research_orchestrator` (singleton). En
  produccion convendra persistir runs en Postgres para retomar/auditar
  despues de un reinicio. Eso queda como Fase futura para no acoplar Fase 12
  a una nueva migracion.

## 2026-05-12 - Phase 18 (DeepAgents 0.6.1) Insights

- PyPI oficial muestra `deepagents 0.6.1` publicado el 12 de mayo de 2026. El
  upgrade local arrastro `langchain 1.3.0`, `langgraph 1.2.0` y `langsmith 0.8.3`.
- La firma real de `create_deep_agent` 0.6.1 soporta `subagents`, `skills`,
  `memory`, `permissions`, `backend`, `interrupt_on`, `response_format`,
  `checkpointer`, `store`, `cache` y `name`.
- La documentacion oficial confirma que DeepAgents trae `write_todos`,
  filesystem tools, `execute` y `task`. Cognitive OS mantiene `interrupt_on`
  y un backend virtual sin shell para que esos built-ins no rompan la politica.
- Async subagents existen, pero requieren Agent Protocol server / LangSmith
  Deployment o equivalente. No se activaron como ejecucion local silenciosa;
  la Fase 18 implementa subagents sincronicos seguros y deja async remoto para
  una fase de deployment.
- Memory nativa se alimenta con paths dentro del backend. Cognitive OS ahora
  escribe startup memory en `./.cognitive_os/AGENTS.md` dentro del workspace y
  conserva el resumen en system prompt como fallback.
- La memoria consolidada podia inflarse con propuestas repetidas. Ahora se
  deduplica por contenido normalizado antes de llamar a `propose_memory_update`.

## 2026-05-12 - Phase 19 (Office Writers) Insights

- Para XLSX hay que separar "texto que parece formula" de "formula aprobada".
  Si una celda normal contiene `=SUM(...)`, se neutraliza con apostrofo; solo
  `SpreadsheetFormula` escribe una formula real. Esto conserva seguridad sin
  quitar capacidad avanzada.
- Permitir imagenes en DOCX sin allow-list reintroduce lectura arbitraria de
  filesystem. `DOCUMENT_ASSET_ROOTS` deja el riesgo explicito: si esta vacio,
  image embedding queda deshabilitado; si se configura, cada path se resuelve y
  valida dentro de esas raices.
- Las formulas peligrosas no son solo `cmd|`; tambien hay funciones que exfiltran
  datos o abren conexiones (`HYPERLINK`, `WEBSERVICE`, URLs externas,
  referencias `[...]` a workbooks). La Fase 19 bloquea ese conjunto por defecto.
- Validar "archivo existe" no basta: los tests ahora vuelven a abrir cada salida
  con la libreria correspondiente. Esto detecta corrupcion estructural y no solo
  escritura de bytes.

## 2026-05-12 - Phase 21 (Gmail Read-only) Insights

- El punto fragil no era solo OAuth: era que el backend no tenia un reader real
  por defecto. Ahora el operador puede generar `token.json` por cualquier flujo
  Google estandar y Cognitive OS lo consume sin abrir navegador desde el backend.
- La lectura Gmail queda separada del envio. `GmailRestReader` solo consulta
  metadata/snippet con REST y el digest sigue produciendo borradores propuestos
  como texto, no drafts reales.
- Los errores de integracion suelen incluir tokens en trazas HTTP. La capa nueva
  redacta `authorization`, `bearer`, `access_token`, `refresh_token`,
  `client_secret` y `token` antes de exponer la razon en preview.
- No conviene depender de `google-api-python-client` para esta ruta: `httpx` +
  `google-auth` reduce superficie, hace tests simples y evita discovery clients
  pesados para una consulta read-only acotada.

## 2026-05-12 - Phase 22 (GoDaddy DNS Executor) Insights

- DNS writes necesitan un "arming sequence", no un boolean unico. La combinacion
  dry-run=false + domain allow-list + production flag separado reduce el riesgo
  de activar produccion por accidente.
- El preview debe producir el payload ejecutable normalizado. Si se ejecuta
  `change.domain` original (`Example.COM.`) en lugar del preview normalizado
  (`example.com`), la aprobacion humana deja de coincidir exactamente con lo
  ejecutado.
- MX/SRV sin priority son cambios incompletos: bloquear temprano evita que el
  operador apruebe algo que el proveedor luego rechaza o aplica de forma
  ambigua.
- El executor usa `PATCH /v1/domains/{domain}/records` segun el swagger oficial
  de GoDaddy Domains API. El body se limita a un record por solicitud para que
  preview, aprobacion y auditoria tengan granularidad clara.

## 2026-05-12 - Phase 23 (Restore Scripts) Insights

- Backups sin restore probado son solo media solucion. Un producto necesita el
  camino inverso empaquetado, documentado y con frenos contra ejecucion
  accidental.
- `CONFIRM_RESTORE=YES` es deliberadamente tosco: obliga a que el operador
  escriba una intencion explicita en el comando y evita ejecuciones por copy/paste
  incompleto.
- Storage es el restore mas facil de romper: antes de extraer, el script mueve
  el directorio actual a `storage.pre_restore_TIMESTAMP`, dejando una ruta de
  recuperacion local inmediata.
- Las pruebas no restauran infraestructura real; validan sintaxis shell y
  propiedades de seguridad. El restore real debe probarse manualmente en entorno
  de staging con datos descartables.

## 2026-05-12 - Phase 24 (Local File Inventory) Insights

- Ordenar archivos sin inventario previo no escala: el agente necesita una foto
  del filesystem para razonar, comparar cambios y proponer limpieza sin tocar
  bytes.
- La lectura de metadata tambien es sensible. Saltar `.env`, `.ssh`, `.git`,
  tokens y passwords evita que un simple inventario termine exponiendo rutas de
  credenciales en prompts o reportes.
- Guardar el reporte en `LOCAL_STORAGE_DIR/file_inventory` permite una futura
  fase de diff temporal: "que cambio desde ayer", "que archivos crecen mas",
  "que documentos quedaron duplicados".
- sha256 debe ser opcional: es util para deduplicacion, pero en arboles grandes
  puede ser costoso. Por defecto se registra metadata ligera.

## 2026-05-13 — Auditoría integral para "asistente personal absoluto"

### Lo que YA funciona (verificado en código)

- **Orquestación**: LangGraph (`agents/graph.py`) con `PostgresSaver` (fallback `MemorySaver`), nodos router/retrieve/research/legal/human_review/final, interrupts para HITL.
- **DeepAgents 0.6.x**: factory con `FilesystemBackend(virtual_mode=True)`, permisos `/**`, `interrupt_on` para tools sensibles (`execute`, `shell`, `bash`, `browser_action`, `send_email`, `publish_social_post`, `delete_file`, `edit_project_file`). Subagentes locales (`local-rag-researcher`, `citation-auditor`, `web-researcher`, `evidence-matrix-specialist`, `timeline-specialist`, `contradiction-reviewer`).
- **Memoria híbrida**:
  - Vectorial: Weaviate `1.29.0` con BM25 + vector híbrido (`alpha=0.5`), reranker local (`memory/reranker.py`).
  - Grafo: Neo4j 5 (`ingestion/neo4j.py` reader + writer, queries seguras pre-definidas).
  - Operacional: Postgres + pgvector (12 migraciones, `DeepAgentMemoryRecord`, `DeepAgentMemoryProposalRecord`, memoria episódica `kind=episodic`, `HumanApproval`, `AuditEvent`).
  - DeepAgents memory con propuestas → aprobación → consolidación (Celery beat).
- **Investigación**: `research_orchestrator` (planner → N DeepAgents paralelo → synth → scorer + SSE `/research/runs/{id}/events`); web search multi-provider (Tavily/Brave/Perplexity/Exa) con dedup canónico; fusión opcional **OpenHarness** (`prelude_merge` / `short_circuit`, workspace `deepagent_mirror`).
- **Action Plane (preview-first + ActionRequest persistente)**:
  - `computer_organize` (preview + ejecución real con allow-list + aprobación).
  - `computer_inventory` (read-only metadata).
  - `browser_preview` y `browser_interactive` headless con vision (`ChatVisionAnalyzer`).
  - `document_generate` DOCX/XLSX/PPTX con guardrails (allow-list paths, tamaño, fórmulas seguras).
  - `gmail_query` / `gmail_digest` **read-only** (token `gmail.readonly`, REST API directo, sin OAuth interactivo desde el backend).
  - `godaddy_dns_change` con dry-run, allow-list de dominios y `GODADDY_ALLOW_PRODUCTION_WRITES`.
- **Workers**: Celery con colas `default | ingestion | agent_longrun | maintenance`; beats: consolidación memoria, Gmail digest, reaper de `ActionRequest` stuck, ingest PDF.
- **Personal Assist**: `PersonalAssistService` + `PersonalTask`/`PersonalNote` (CRUD persistido), `assist/reminders.py` con scheduler Celery.
- **Telegram**: bot con 25+ comandos, digest, notify.
- **Frontend**: Next.js 16, **17 vistas** (Chat, Dashboard, Settings, Approvals, Memory, Jobs, Sandbox, Documents, DocumentAnalysis, Configuration, Mail, LangSmith, Agents, Skills, Health, Audit y **Assist**), PWA + service worker.
- **Observabilidad**: LangSmith opt-in con PII redaction; auditoría de cada tool call (éxito o error) en `audit_events`.
- **QA**: snapshot `341 pytest passed, 1 skipped, 20 deselected`, ruff + ruff format + mypy strict + frontend lint/build verdes (verificado 2026-05-14).

### Brechas reales para "asistente personal absoluto"

| # | Capacidad pedida | Estado actual | Falta concretamente |
|---|---|---|---|
| 1 | **Gmail diegomanzurn@gmail.com bandeja "todos" (categorizar, resumir por importancia, proponer respuestas)** | Digest read-only existe, redacta direcciones, propone borradores en texto pero NUNCA crea drafts en Gmail | Cuenta-by-account multi-mailbox (no global), filtros por label/categoría/importancia, propuestas de respuesta vinculadas a `ActionRequest` para envío (queda preview-only hasta que el usuario habilite send + apruebe); helper para crear borradores REALES en Gmail (`gmail.compose`) cuando el usuario lo apruebe |
| 2 | **GoDaddy diego@doctormanzur.com bandeja **Spam** solamente** | Cero: GoDaddy backend solo cubre DNS. No hay lectura de mailbox GoDaddy | Conector mail GoDaddy (IMAP `imap.secureserver.net` o SMTP+IMAP con app password, mejor: **OAuth Microsoft 365 / Graph API** si el dominio está en O365 — verificar). Settings `GODADDY_MAIL_*`. Filtro `folder=Spam` por defecto. Reusa modelo y digest existente |
| 3 | **YouTube: ver y resumir videos** | Solo variable `YOUTUBE_API_KEY` reservada; sin código | Servicio `actions/youtube.py`: metadata vía YouTube Data API v3, transcript vía `youtube-transcript-api`, resumen + capítulos con DeepAgent; cache por `video_id`. Fallback a Whisper (audio) cuando no hay transcript. Tool DeepAgents `summarize_youtube` |
| 4 | **Hablar y escuchar (TTS/STT)** | Solo variable `ELEVENLABS_API_KEY` reservada | `voice/stt.py` con OpenAI Whisper como default + ElevenLabs/Deepgram opcional; `voice/tts.py` con OpenAI TTS / ElevenLabs. Endpoints `/voice/transcribe`, `/voice/speak`. Tool DeepAgents `voice_speak` (interrupt). Wiring Telegram para audio in/out |
| 5 | **Agenda real (no mock)** | Solo `create_calendar_draft` mock en `tools/sensitive.py` | `actions/calendar.py` con Google Calendar API (OAuth, mismo token store que Gmail) y/o CalDAV. CRUD events, list por rango, sugerir slots libres. Fallback puramente local en `PersonalTask` con `due_at` y reminder cuando no haya cuenta |
| 6 | **Notas (sin app por defecto)** | `PersonalNote` CRUD sin búsqueda semántica ni vínculo a memoria | Indexar notas en Weaviate (`doc_type="note"`) automáticamente al crear/editar; tool DeepAgents `search_notes`; vincular nota↔tarea↔memoria por foreign key/etiqueta semántica |
| 7 | **Memoria que aprende de mí y de sí mismo** | Existe propuestas + consolidación + episódica; falta perfil unificado y "aprendizaje de correcciones" | `memory/profile.py` con perfil estructurado del usuario (preferencias, personas, horarios, decisiones); pipeline "feedback → propuesta de memoria" cuando el usuario corrige una respuesta del agente; tagging por kind (`factual | preference | procedure | warning | task`); separar TTL (`hoy/semana/mes/durable`) |
| 8 | **Despachar agentes para investigar / revisar correos / videos** | Existe research orchestrator y Celery; falta una orquestación "asistente personal" que combine investigación + email + agenda + notas | Nuevo grafo "personal_assistant" en LangGraph (router→capability subagents) que despache tareas paralelas y consolide en briefing/notas/tasks. Endpoint `/assist/briefing/daily` |
| 9 | **Robustez en credenciales** | Hay `.env.example` y settings registry, pero secretos viven en `.env` plano | Integrar secret manager local (e.g. `keyring` + dotenv encriptado, o `sops`) para Gmail/GoDaddy/calendar tokens. **No requiere** subir credenciales al repo |

### Riesgos detectados

- **Gmail send + GoDaddy mail OAuth**: ambos requieren consent del usuario. El backend NO debe abrir flujo OAuth interactivo (ya falló históricamente con MCP Gmail). Plan: script local `scripts/auth_gmail.py` y `scripts/auth_microsoft_mail.py` que el usuario corre una vez, generan `token.json`, lo dejan en `GMAIL_TOKEN_DIR` / `MICROSOFT_TOKEN_DIR`.
- **GoDaddy mailbox**: GoDaddy mail está hospedado en O365 (Outlook) en la mayoría de cuentas profesionales. Confirmar antes de elegir IMAP vs Microsoft Graph.
- **Costo/latencia STT/TTS**: Whisper-1 local vs API; ElevenLabs caro. Default API con cap por settings (`VOICE_MAX_AUDIO_BYTES`, `VOICE_MAX_REQUESTS_PER_MIN`).
- **YouTube transcript ToS**: `youtube-transcript-api` usa endpoint público, sin auth; estable pero no garantizado. Fallback: descarga audio (yt-dlp) + Whisper, solo bajo flag y con cap de duración.

### Sobre DeepCode (HKUDS/DeepCode)

- **Qué es**: pipeline "Research-to-Code": papers/docs → plan → código + tests. Multi-agent con MCP tools, Concise Memory Agent (single-file / multi-file batch), Streamlit/React UI propias.
- **¿Acoplarlo entero?** No. Es opinionated, heavy, y solapa con DeepAgents + OpenShell sandbox + research_orchestrator ya integrados. Acoplarlo metería dos jerarquías de agentes en paralelo y duplicaría memoria/orquestación.
- **¿Sacarle ideas?** Sí, tres concretas que valen para un futuro subagente `code_implementation`:
  1. **Concise Memory Agent multi-file batch**: comprimir el estado de un repo grande en una sola estructura JSON antes de planificar implementación. Aplicable como `code_repo_context_summarizer` tool.
  2. **Separación research→plan→implement→verify**: ya la tenemos en DeepAgents pero su pipeline explícito de "code plan with reference indexing" es buena referencia.
  3. **User-in-Loop Plugin System**: patrón para reabrir el plan a mitad de ejecución; lo nuestro ya lo hace vía `interrupt`, pero su API es más simple.

Conclusión: ideas sí, código no. Si en algún momento querés modo "programador de apps", la solución correcta es **un subagente DeepAgents `code_implementation` con permisos OpenShell sandbox**, no integrar DeepCode entero.

## 2026-05-15 - Fase 31 Google Maps/Drive/Calendar

- El código real ya tenía servicios backend `actions/maps.py`, `actions/calendar.py`
  y `actions/drive.py`, health checks y tools DeepAgents read-only. La brecha no
  era ausencia total, sino falta de promoción comercial: capacidades Google no
  aparecían en `/actions/capabilities`, no había vista frontend dedicada y las
  escrituras Calendar/Drive no pasaban por `ActionRequest` persistente.
- Maps usaba Google Routes, pero no solicitaba explícitamente tráfico ni devolvía
  un link navegable para que el operador abriera la ruta en Google Maps.
- Drive listaba/subía archivos, pero no modelaba una carpeta de entregables para
  que LangGraph/DeepAgents usen Drive como nube operativa del sistema.
- Decisión de diseño: Maps sigue read-only sin aprobación; Calendar create y
  Drive upload se promueven a `ActionRequest` para el carril comercial, dejando
  los endpoints directos con `dry_run` como API de bajo nivel.
- Verificación de implementación: el conteo real queda en **118 endpoints REST**,
  **18 vistas frontend** y **14 migraciones Alembic** tras sumar
  `GoogleOpsView`, endpoints `/actions/calendar/events/request`,
  `/actions/drive/folders/ensure`, `/actions/drive/files/upload/request` y la
  migración `202605150001_google_action_requests.py`.
- Tests unitarios añadidos: `ActionRequestService.create_calendar_event_request`
  y `create_drive_upload_request` persisten `ActionRequest`, `HumanApproval`,
  `Job`, `JobEvent` y `AuditEvent` usando fakes, sin DB real ni secretos.
- QA final Fase 31: **471 passed, 1 skipped, 20 deselected**; ruff, ruff format,
  mypy (106 source files), frontend lint/build y `git diff --check` verdes.

### Decisiones pendientes fuera de Fase 31

1. **GoDaddy mail**: ¿cuál es el proveedor real detrás de `diego@doctormanzur.com`? (GoDaddy nativo IMAP, GoDaddy hospedado por Microsoft 365/Workspace, otro). Determina IMAP vs Microsoft Graph.
2. **Política Gmail "send"**: ¿el agente debe crear *borradores* en Gmail (`gmail.compose`, requiere scope) o solo proponer texto en el digest y dejar el envío 100% manual?
3. **Agenda**: Google Calendar queda implementado en base; falta decidir si se suma CalDAV/Outlook.
4. **STT/TTS**: ElevenLabs queda implementado en backend; falta decidir UX completa y fallback OpenAI/otro.
5. **Notas**: PersonalNote + Weaviate queda implementado; falta decidir si además sincroniza con Markdown vault (Obsidian-like).
6. **Multi-cuenta Gmail/Mail**: el modelo mail multi-cuenta quedó listo; falta decidir Gmail send/drafts reales y Microsoft/Outlook.

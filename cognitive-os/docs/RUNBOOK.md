# RUNBOOK Cognitive OS

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-27, Prompt 7).** Esta rama `codex/commercial-zero-friction-hardening` queda certificada como **APTA COMERCIAL LOCAL-FIRST** para PC dedicado. Branch inicial Prompt 1: HEAD `2bb4966`. Working tree del Prompt 7 consolida los cambios de Prompts 3 (F-P2-001..006), 4 (F-P4-001 fix wrapper timeout mcp_client live probe) y 6 (V2-EVAL-001 DocAnalysis API consistency). El commit final del Prompt 7 firma todo el delta V2.0 sin push. Evidencia viva en `tmp/v2_07_absolute_release_closure_20260527_175541/`.
>
> **Hallazgos cerrados V2.0 (12):** F-P2-001 wildcard_allow_all transparency · F-P2-002 stress flake eliminado (0% en 5×1232) · F-P2-003 `?limit=` honored en `/approvals` y `/actions/drive/files` · F-P2-004 `/chat` 404/400 con `missing_doc_ids`/`invalid_doc_ids` · F-P2-005 docs sync (este bloque) · F-P2-006 `_check_mcp(verify_live=True)` → overall `ok` · F-P4-001 timeout wrapper +5s sobre `mcp_inventory_timeout_seconds` · F-P4-002 fallback heurístico DocAnalysis documentado · F-P4-003 Kimi extension boot oscillation documentado · V2-EVAL-001 `GET /document-analysis/{id}` mirror artefacto · V2-EVAL-004 endpoints memoria/aprendizaje live (303 proposals, 209 recipes, 94 warnings) · V2-EVAL-005 Code Director adapter=deepagent plan+approval+reject sin exec.
>
> **Gates V2.0 medidos antes del cierre absoluto:** `bash scripts/full-qa.sh` **1232 passed, 1 skipped, 28 deselected** (ruff/format/mypy/alembic/sync_doc_counts/git-diff verdes); `bash scripts/stress-qa.sh 5` **5/5 verde × 1232 passed**, flakiness **0%**; `cd frontend && npx playwright test` **44 passed**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/openapi_readonly_smoke.py` **70 GET / 0 failures**; `bash scripts/verify_desktop_launchers.sh` OK; security-readonly-qa (bandit/semgrep/secret-scan) clean; `POST /health/verify` overall **`ok`** con `mcp_client` live `ok` 6/6 y 69 tools; checklist 400 puntos ejecutada.
>
> **Criterio de verdad:** no se declara envío de correo, draft real ni escritura DNS. Mail queda normalizado como read-only (sync/list/classify/digest + proposed replies como texto). GoDaddy preview/dry-run. Action Plane mantiene `validate→preview→request→approve→dispatch→execute→audit` con idempotencia y reapers. El runtime corre en `127.0.0.1` sin exposición LAN/internet. El frontend `cognitive.doctormanzur.com` se levanta on-demand sólo con `scripts/testsprite_web/deploy_and_verify.sh`; Prompt 7 V2.0 no lo expone permanentemente. **Cognitive OS queda certificado en este commit como APTO COMERCIAL LOCAL-FIRST para PC dedicado, con funcionamiento real activado, documentación sincronizada, dos ciclos completos verdes posteriores al último cambio, Git ordenado y sin P0/P1/P2 abiertos.**

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


> **Estado canonico actual (2026-05-26, HEAD `8a33475`):**
> **COMERCIAL LOCAL-FIRST APROBADO** + hardening frontend/TestSprite web
> aplicado. Se mantiene la certificación local-first 2026-05-25 (matriz
> audit-commercial, flakiness P0 cerrada, activación funcional end-to-end y
> cierre comercial final), y se suma el ciclo público de UI: TopBar retirado,
> shell estable con `data-cogos-active-tab`, API pública resuelta por host,
> auth por `#cogos_token`, hotkey `3` reasignada a DeepAgents, command palette
> persistente para navegación, responsive comercial a 920px y estados
> loading/empty/error reales en Documents/Agents/Audit/Health/Mail. Operar este
> host como PC dedicado `dedicated_local/full`: **fricción casi nula por sobre
> seguridad estricta**, manteniendo trazabilidad, health honesto e idempotencia.
> Para estado, gates y contrato de mail ver `CURRENT_STATE.md`; para la postura
> operativa ver `ZERO_FRICTION_OPERATING_MODEL.md`; para pendientes vivos ver
> `corregir_cognitive.md`.
>
> **TestSprite web:** el comando canónico es
> `bash scripts/testsprite_web/deploy_and_verify.sh`. Reconstruye producción,
> levanta backend/worker/beat/frontend/tunnel, valida frontend público HTTP 200,
> backend `/health`, marker `cogos-v2026-05-26e-status-cards` en `/sw.js` y la
> shell raíz con `data-cogos-active-tab`. Si pasa, queda listo para apretar
> **Rerun** en el portal TestSprite con el mismo PRD/instructions. No declarar dos
> corridas web verdes hasta recibir los PDFs nuevos.
>
> **Snapshot vigente** (conteos por `scripts/sync_doc_counts.py`): backend
> FastAPI con **150 endpoints REST**, **23 tareas Celery** en **5 colas**
> (`default`, `ingestion`, `agent_longrun`, `maintenance`, `mail`) con hasta
> **13 jobs beat**, **20 migraciones Alembic** head `202605200003`, **37 slash
> commands Telegram**, `/health/dashboard` con 18 componentes +
> `POST /health/verify`. QA post-remediación: `full-qa.sh` **1200 passed**, 1
> skipped, 28 deselected; `stress-qa.sh 5` -> **5/5 verde × 1200 passed**
> (flakiness 0%); Playwright **43 passed** sin exportar `COGOS_JWT`
> (auto-mint via `_global-setup.ts`). `full-qa.sh` construye Next en `.next-qa`
> para no invalidar el `.next` que usa un `next start` vivo. Live read-only:
> `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed** (último gate
> documentado); `POST /health/verify` confirmó live `primary_llm`/`embeddings`/
> `mail` en `ok`. TestSprite histórico local corregido en batches: **28/28
> passed**; TestSprite web público queda en ciclo de rerun post-`8a33475`.
>
> **Runtime:** la ruta `research` está fusionada con OpenHarness opcional; el
> LLM es **gpt-5.5** (gateway openai-compatible, Responses API) como
> primary+agent, `gemini-3.1-pro-low` secondary/fallback, `glm-4.6v` visión.
> El stack incluye mail personal GoDaddy/Gmail-label con queue Celery `mail`.
> Para uso diario existen ejecutables endurecidos en `/home/jgonz/Escritorio`
> que levantan/reinician/detienen todo (Docker, migraciones, API, Celery worker
> multi-queue, beat, frontend y Kimi WebBridge); Telegram se omite si
> `TELEGRAM_ENABLED=false`. Endpoints operacionales: `/system/info`,
> `/system/credentials-status` (admin), `/system/mcp`. Wizard CLI:
> `bash scripts/init_credentials.sh`.
>
> **Plan de aprendizaje autónomo (Fases A-E del `AGENT_LEARNING_PLAN.md`):**
> en producción — recipe extractor, failure post-mortem, tool scorecard,
> skill promotion y nightly reflection, detrás de feature flags en el beat.
> El auto-promote de warnings de Fase D tiene kill switch
> `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED`.
>
> **Aislamiento de DB de test:** la suite corre contra `cognitive_os_test`,
> recreada por corrida — `pytest` nunca toca la base de producción.

## TL;DR Quick-Start

Para usuarios que ya conocen el repo y solo necesitan los 4 comandos que
levantan, validan, observan y apagan el stack:

```bash
# 1. Levantar todo (Docker + API + worker + beat + frontend + telegram + Kimi)
~/Escritorio/Reiniciar\ Cognitive\ OS.sh     # reset limpio
# (o `Levantar Cognitive OS.sh` si nada está corriendo)

# 2. Mint JWT operador (10 años, sin auth en dedicated_local/full)
JWT=$(curl -sX POST http://127.0.0.1:8000/auth/local-token | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# 3. Sanity check (debe ser todo verde)
curl -s http://127.0.0.1:8000/system/readiness -H "Authorization: Bearer $JWT" | \
  python3 -m json.tool
# → target_capabilities_unlocked: 14/14, gaps: []

# 4. Apagar todo limpio
~/Escritorio/Detener\ Cognitive\ OS.sh
```

Y para los gates QA locales:

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os"
bash scripts/full-qa.sh                          # 1200 passed post-remediación (≈70s)
cd frontend && unset COGOS_JWT && npx playwright test --reporter=list
# 43 passed (auto-mint JWT, no necesita exportar nada)
```

Y para dejar listo el stack público que usa TestSprite web:

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os"
bash scripts/testsprite_web/deploy_and_verify.sh
```

Ese último comando imprime el checklist humano final para abrir el portal y
presionar **Rerun**; no requiere comandos sueltos adicionales si todas sus
verificaciones pasan.

## Ejecutables de escritorio

En este PC hay wrappers ya probados (versión endurecida 2026-05-16):

- `/home/jgonz/Escritorio/Levantar Cognitive OS.sh`
- `/home/jgonz/Escritorio/Reiniciar Cognitive OS.sh`
- `/home/jgonz/Escritorio/Detener Cognitive OS.sh`
- `/home/jgonz/Escritorio/Estado Cognitive OS.sh`

También hay accesos `.desktop` equivalentes en el Escritorio. El script maestro
`/home/jgonz/Escritorio/cognitive-os.sh` acepta `start`, `restart`, `stop`,
`status`, **`doctor`** y `logs <api|frontend|worker|beat|telegram|kimi|docker|migrate>`.
Arranca Docker, migraciones (skip si current==head), FastAPI, Celery worker con
queue `mail`, Celery beat, frontend Next.js y Kimi WebBridge si está instalado.

Garantías:

- **Lock global con `flock`** impide doble-arranque simultáneo.
- **Preflight** verifica `docker`/`uv`/`lsof`/`curl`/`npm`/`.env`/`compose`
  antes de cambiar estado.
- **Anti PID-recycle**: cada PID se valida contra el cmdline esperado.
- **Kill graceful** SIGTERM → SIGKILL si sobrevive.
- **`pkill` restringido** a `-u $USER` y patrones específicos del stack.
- **Rotación de logs** >10 MB, retiene últimas 5 rotaciones por componente.
- **Header de sesión** por arranque en cada log.
- Detalles completos en `~/Escritorio/cognitive-os-launchers-README.md`.

Smoke reproducible sin levantar servicios:

```bash
bash cognitive-os/scripts/verify_desktop_launchers.sh
```

El smoke valida sintaxis Bash, permisos ejecutables y targets de
`cognitive-os.sh`, los cuatro wrappers `.sh` y los cuatro accesos `.desktop`.
Acepta overrides `COGOS_DESKTOP_DIR`, `COGOS_MASTER`, `COGOS_OPEN_TERMINAL` y
`COGOS_REPO_ROOT` para CI/tests.

## Levantar

1. `bash scripts/init_env.sh` — copia `.env.example` a `.env` y genera secretos
   locales (`JWT_SECRET`, `POSTGRES_PASSWORD`, `NEO4J_PASSWORD`,
   `WEAVIATE_API_KEY`).
2. `bash scripts/dev_up.sh` — **comando único correcto** para levantar
   Postgres, Redis, Weaviate y Neo4j. Llama `init_env.sh`, valida que las
   variables que `docker compose` interpola sin default no estén vacías
   (AUDIT-2026-H — `docker compose` no falla por sí solo ante variables
   vacías), arranca con `--env-file .env` y espera health checks. No invocar
   `docker compose` a mano sin `--env-file .env`.
3. En `backend`: `uv run alembic upgrade head` para aplicar migraciones.
4. API: `uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000`.
   El lifespan abre un `PostgresSaver` para los hilos de LangGraph; si falla,
   loguea `checkpointer_postgres_unavailable_fallback_memory` y sigue con
   `MemorySaver` (los hilos no sobreviven al reinicio en ese modo).
5. Worker Celery: `bash scripts/dev_worker.sh` o worker con queues
   `ingestion,agent_longrun,maintenance,mail,default`.
6. Beat (memoria diaria): `bash scripts/dev_beat.sh`.
7. Frontend: `cd frontend && npm install && PORT=3001 npm run dev` → <http://localhost:3001> (3000 lo usa OpenChamber).

## Apagar

1. `Ctrl+C` en API, worker, beat y frontend.
2. `bash scripts/dev_down.sh`.

## Credenciales

Las únicas variables que pueden quedarse en `CHANGEME` sin romper el sistema:

* `OPENSHELL_GATEWAY_URL` — solo si vas a habilitar el sandbox
  (`ENABLE_OPENSHELL_SANDBOX=true`).
* `TELEGRAM_BOT_TOKEN`, `TELEGRAM_AUTHORIZED_USER_IDS` — solo si vas a
  habilitar Telegram (`TELEGRAM_ENABLED=true`).
* `TAVILY_API_KEY` y demás claves de búsqueda web — solo si activas
  `WEB_SEARCH_ENABLED=true`.
* Claves de servicios externos opcionales (`ELEVENLABS_API_KEY`,
  `NOTION_API_KEY`, `YOUTUBE_API_KEY`, etc.) — futuras integraciones, no
  requeridas hoy.

Las críticas que **deben** quedar configuradas para operar:

* `JWT_SECRET` (lo genera `init_env.sh`).
* `POSTGRES_PASSWORD`, `DATABASE_URL`, `POSTGRES_*`.
* `WEAVIATE_API_KEY`, `WEAVIATE_URL`.
* `NEO4J_PASSWORD`, `NEO4J_URI`, `NEO4J_USER`.
* `PRIMARY_LLM_API_KEY`, `PRIMARY_LLM_BASE_URL`, `PRIMARY_LLM_MODEL`.
* `EMBEDDINGS_BASE_URL`, `EMBEDDINGS_API_KEY`, `EMBEDDINGS_MODEL`,
  `EMBEDDINGS_DIMENSION`.
* Si activas mail personal: `MAIL_GODADDY_PASSWORD`, `MAIL_GODADDY_USERNAME`,
  `MAIL_DEFAULT_SENDER`, `MAIL_REQUIRE_APPROVAL_FOR_SEND=true` y timeouts
  `MAIL_IMAP_TIMEOUT_SECONDS` / `MAIL_SMTP_TIMEOUT_SECONDS`.

`/health/dashboard` reporta cada componente con estado `ok`, `configured`
o `degraded` y latencia, además del backend del checkpointer.

## Generar JWT local

```python
from cognitive_os.core.auth import create_access_token
print(create_access_token(user_id="1"))
```

Pega el token en la barra superior del panel.

## Ingestar PDF

CLI rápido:

```bash
bash scripts/ingest_now.sh /ruta/documento.pdf
```

API/panel:

1. Pestaña `Documentos`.
2. Pega la ruta absoluta del PDF (visible para el backend).
3. El backend devuelve `job_id`; síguelo en `Jobs` (auto-refresh cada 3s).
4. Cuando el job complete, el documento queda chunked en Postgres + Weaviate
   y, si Neo4j está habilitado, las entidades extraídas se vuelcan al grafo.

## Chat con Cognitive OS

Pestaña `Chat`:

* `thread_id` — opcional; si lo dejas vacío se crea uno nuevo. Si
  `PostgresSaver` está activo, el thread persiste entre reinicios.
* `doc_ids` — UUIDs de documentos ya ingestados; al adjuntar al menos uno,
  el router fuerza la ruta legal y dispara document analysis.
* `case_id` — opcional; se propaga a `DocumentAnalysisTask.case_id`.
* Si la respuesta requiere aprobación humana (acciones externas, borrador
  legal, etc.), el panel muestra un cuadro amarillo con `Aprobar`,
   `Editar y re-enviar`, `Rechazar`. La acción `editar` requiere mensaje.

## Mail personal

Pestaña `Mail`:

1. `Sync por worker` llama `POST /mail/sync/dispatch` y encola
   `cognitive_os.sync_personal_mail` en la queue `mail`.
2. El worker lee Gmail `TODOS`/`SPAM` y GoDaddy `Spam` si las credenciales
   estan listas. No se confia en la clasificacion del proveedor: el agente
   reclasifica por contenido.
3. `Generar resumen 50` llama `POST /mail/digest/preview` con
   `sync_first=false`; usa mensajes locales persistidos y no bloquea el API
   leyendo IMAP/Gmail.
4. El digest programado `personal-mail-digest` corre 10:00 y 20:00
   `America/Santiago` y persiste artefactos bajo
   `LOCAL_STORAGE_DIR/mail_digests`.
5. Los mensajes se guardan en Postgres y quedan filtrables por estado:
   `new`, `reply_proposed`, `pending_send`, `ignored`, `sent`, `failed`.
6. Los importantes reciben `proposed_reply_text`; edítalo en pantalla.
7. `Guardar texto` llama `PATCH /mail/messages/{id}/reply`.
8. No hay boton normal de envio. El operador copia el texto y lo envia desde
   su cliente de correo.
9. El endpoint SMTP `/mail/messages/{id}/approve-send` queda como escape hatch:
   solo funciona con `ENABLE_EMAIL_SEND=true`, `MAIL_ALLOW_EXPLICIT_SEND=true`
   y `explicit_send_confirmation=SEND_THIS_EMAIL_EXPLICITLY`.
10. Nunca hay auto-send ni drafts automáticos.

## Ruta research: OpenHarness + DeepAgents

Documento de referencia: `docs/OPENHARNESS_FUSION.md`.

Pasos típicos para operar el camino **fusionado** (recomendado en CI con `bash scripts/full-qa.sh`):

1. `cd backend && uv sync --extra openharness`
2. `.env`: `ENABLE_OPENHARNESS_RESEARCH=true` y credenciales `PRIMARY_LLM_*`.
3. Opcional: `OPENHARNESS_RESEARCH_PIPELINE=prelude_merge` (por defecto) o `short_circuit`.
4. Opcional: `OPENHARNESS_TOOLKIT_PRESET` (`minimal` \| `research` \| `full`),
   `OPENHARNESS_WORKSPACE_MODE` (`deepagent_mirror` \| `sandbox`),
   `OPENHARNESS_WEB_TOOLS` y `WEB_SEARCH_ENABLED` alineados si quieres búsqueda web en el harness.

Los artefactos DeepAgent siguen en `storage/workspaces/{thread_id}/{task_id}/` cuando usas `deepagent_mirror`.

## Document Analysis

Pestaña `Document Analysis`:

1. Indica `doc_ids` autorizados, query y modos
   (`evidence_matrix`, `timeline`, `contradictions`, `full_report`,
   `legal_draft_support`, `case_summary`).
2. Selecciona formatos de salida: JSON, Markdown, CSV, DOCX.
3. `Ejecutar` encola un job en Celery (`agent_longrun`).
4. El panel hace polling cada 5s al endpoint
   `GET /document-analysis/{task_id}` hasta que el resultado aparece.
5. Botones de descarga generan `report.md`, `result.json`, `report.docx` y
   los tres CSV (`evidence_matrix.csv`, `timeline.csv`, `contradictions.csv`).
6. Cuando el quality score < 85 o hay borradores, el resultado queda en
   `partial`/`needs_human_review` y se crea un `HumanApproval` para
   revisión.

## Aprobaciones

Pestaña `Aprobaciones`:

* Lista todas las aprobaciones pendientes/decididas.
* Cada fila muestra acción, args redactados, solicitante, estado.
* Aprobar/Rechazar dispara `POST /approvals/{id}/{approve|reject}`. La
  aprobación queda firmada con `approver_user_id` (= JWT sub) y
  `decided_at`.

## Action Plane

El action plane esta documentado en `docs/ACTION_PLANE.md`.

Endpoint de estado:

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/actions/capabilities
```

Para habilitar capacidades:

1. Mantener todo desactivado hasta tener credenciales y allow-lists.
2. Browser: configurar `ENABLE_BROWSER_AUTOMATION=true` y
   `BROWSER_ALLOWED_DOMAINS=example.com`.
3. Computer: configurar `ENABLE_COMPUTER_ACTIONS=true` y
   `COMPUTER_ALLOWED_ROOTS=/ruta/permitida`.
4. Gmail: usar `GMAIL_READ_ENABLED=true` con scope readonly para digest/label.
   Para responder correos personales usar `/mail/*` con SMTP GoDaddy y aprobación.
5. GoDaddy: probar primero con `GODADDY_BASE_URL=https://api.ote-godaddy.com`;
   los cambios DNS deben pasar por preview y aprobacion.

Flujo operativo para ordenar una carpeta:

1. Previsualizar con `POST /actions/computer/organize/preview`.
2. Crear solicitud persistente con `POST /actions/computer/organize/request`.
3. Revisar la `HumanApproval` creada en la pestana `Aprobaciones`.
4. Aprobar desde el panel. Para solicitudes `execute_action_request`, el panel
   intenta despachar automaticamente despues de aprobar.
5. Si operas por API pura, aprobar con `POST /approvals/{id}/approve` y luego
   despachar con `POST /actions/requests/{id}/dispatch`.
6. Seguir el job en `Jobs` y revisar el historial reciente en `Configuracion`.
7. Revisar el resultado tecnico en
   `GET /actions/requests/{id}`.

Notas:

* Si `COMPUTER_ORGANIZE_DRY_RUN_ONLY=true`, la solicitud queda en `previewed`
  y no se puede despachar.
* Si la aprobacion se rechaza, la solicitud queda en `rejected` y no encola
  worker.
* El dispatch solo manda Celery cuando la solicitud esta en `queued`.
* Si Celery/Redis no acepta el job, el endpoint devuelve `dispatched=false`
  con una razón operativa; la solicitud queda `queued` para retry.
* Los eventos `action_request_dispatch_submitted` y
  `action_request_dispatch_failed` aparecen en `GET /jobs/{job_id}/events`.
* Una reserva atómica en `ActionRequest.metadata_json.dispatch_state` impide
  submits duplicados antes de Celery: `submitting` bloquea concurrencia,
  `submitted` espera al worker y `failed` permite reintentar.
* Si el broker entrega un task duplicado mientras el job ya esta `running`, el
  worker sale temprano y no agrega eventos confusos ni marca fallo.

## Code Director (delegación a coding agents externos)

El Code Director es un meta-agente: recibe un objetivo de alto nivel,
arma un plan de subtareas y **delega** cada una a un coding agent externo
(Claude Code CLI, Codex CLI, Kimi CLI, o DeepAgents in-process). El
director nunca codifica en su propio proceso ni gasta un token hasta que
el operador aprueba el plan.

Endpoints (todos JWT):

- `POST /code-director/run` — rate-limited (`action_request_create`,
  30/min). Body: `{objective, notes?, adapter_preference, budget?,
  run_tests_in_sandbox?}`. Devuelve `{job_id, approval_id, build_id,
  plan}` y persiste un `Job(job_type="code_build",
  status="waiting_approval")` + un `HumanApproval`
  (`run_code_build:<build_id>`). **No corre nada todavía.**
- `GET /code-director/{job_id}` — estado + plan + result.
- `GET /code-director/{job_id}/events` — SSE; reproduce el historial de
  JobEvents y luego tailing hasta estado terminal (`snapshot` + `done`).
- `GET /code-director/{job_id}/download` — `tar.gz` del workspace
  generado. La ruta se re-valida dentro de
  `DOCUMENT_OUTPUT_ROOT/code_builds/` (no se puede escapar).

`adapter_preference` admite pinning por rol:

```json
{
  "default_adapter": "claude_code",
  "default_model": "claude-opus-4-7",
  "coder_adapter": "codex",
  "reviewer_adapter": "claude_code"
}
```

Adapters: `claude_code` (`claude -p --add-dir <ws> --model M
--max-budget-usd N`), `codex` (`codex exec --cd <ws>
--sandbox workspace-write -m M -`), `kimi` (`kimi --print
--work-dir <ws> --prompt -`; Kimi toma el modelo de su propia config),
`deepagent` (in-process, mismo tool policy + budget que el resto).

`budget` impone topes duros: `max_runtime_minutes` (def 120),
`max_total_llm_calls` (def 200), `max_calls_per_subtask` (def 20),
`max_total_cost_usd` (opcional). Si se excede cualquiera, el build para
con estado `partial` y **igual entrega lo construido** hasta ese punto.

Flujo operativo:

1. `POST /code-director/run` con el objetivo y el adapter/modelo.
2. Revisa el plan (tabla de subtareas + estimación) en la pestaña
   **Code Director**.
3. Aprueba el `HumanApproval` desde **Aprobaciones** (hereda four-eyes y
   audit). Al aprobar, el director encola `cognitive_os.run_code_build`
   en la queue `agent_longrun`.
4. Sigue el build en vivo (SSE) o por polling.
5. Al completar (`completed`/`partial`), descarga el `tar.gz`.

Seguridad: el `fake` adapter (sólo tests) es rechazado con 400. El
workspace vive aislado en `LOCAL_STORAGE_DIR/workspaces/code_builds/`;
el código generado nunca toca tu repo ni se ejecuta en tu host (los
tests opcionales corren en `openshell_sandbox`). Cada CLI externo se
autentica con sus propias credenciales — el director no inyecta keys.

Pre-requisito: los CLIs que vayas a usar deben estar instalados y
autenticados en el host (`claude --version`, `codex --version`,
`kimi --version`). El preflight reporta los no disponibles en el plan
en vez de fallar al ejecutar.

Planificación y prompting (F9):

- **Planner LLM-driven** (`code_director/planner.py`): el plan ya no es
  el esqueleto fijo scaffold→implement→review. `LLMPlanner` pide al LLM
  primario configurado que descomponga el objetivo en subtareas reales,
  ordenadas por dependencia, con adapter/modelo por rol. Ante **cualquier**
  fallo (sin key, circuito abierto, JSON malformado, esquema inválido,
  dependencias alucinadas) cae al `HeuristicPlanner` determinista — un
  build nunca muere porque el LLM planificador hipó. El plan sigue
  pasando por `HumanApproval` antes de gastar un token.
- **Prompts con contexto** (`code_director/prompt_builder.py`): cada
  subtarea recibe el árbol vivo del workspace (no re-scaffoldea lo que
  ya existe), el contenido de los paths esperados y de los archivos que
  tocaron sus dependencias, y un resumen de lo que produjo cada upstream.
  En un reintento se inyecta el error/stderr/exit-code del intento
  anterior con la directiva explícita "arregla esto, no empieces de
  cero" — el prompt de reintento difiere del primero, así
  `iterate_until_tests_pass` converge en vez de repetir el mismo fallo.
  Todo está acotado por topes duros (entradas del árbol, bytes/líneas
  por archivo, total, colas de stdout/stderr) y con path-containment:
  jamás se lee fuera del workspace.

## Research Orchestrator (multi-agente)

Endpoint base: `/research/runs` (requiere JWT). Disponible cuando
`ENABLE_RESEARCH_ORCHESTRATOR=true`. En desarrollo puede operar con
`RESEARCH_PERSISTENCE_BACKEND=memory`; en producción la configuración exige
`RESEARCH_PERSISTENCE_BACKEND=postgres` para que snapshots/eventos sobrevivan
reinicios del proceso.

Flujo operativo:

1. `POST /research/runs` con `{query, time_budget_seconds, max_subtasks,
   web_allowed}`. Limites clamped contra
   `RESEARCH_MAX_TIME_BUDGET_SECONDS` y `RESEARCH_MAX_SUBTASKS`.
2. El endpoint retorna **inmediatamente** con `run_id` y estado no-terminal
   (`queued/planning/researching`). La ejecucion corre en un daemon thread.
3. Para ver eventos en vivo: `GET /research/runs/{run_id}/events` (SSE).
   Emite todos los eventos historicos + nuevos hasta estado terminal mas
   un `snapshot` con `ResearchRunView` completo y un `done`.
4. Para polling: `GET /research/runs/{run_id}` cada N segundos hasta estado
   terminal (`completed/cancelled/failed/blocked`).
5. Para cancelar: `POST /research/runs/{run_id}/cancel`. Setea `cancel_flag`;
   los subtasks corriendo no se interrumpen pero el run final queda como
   `cancelled` tras la sintesis/scoring.

Estados del run:

- `queued`, `planning`, `researching`, `synthesizing`, `scoring`: en curso.
- `completed`: pipeline ok.
- `cancelled`: `cancel_run` fue invocado.
- `failed`: excepcion en algun nodo (`run.error` redactado).
- `blocked`: la orquestacion fue rechazada (p.ej. flag global desactivada).

## Memoria DeepAgents

Pestaña `DeepAgents Memory`:

* Skills habilitadas (core + de usuario).
* Memoria activa por scope `user`.
* Propuestas pendientes (las generan los DeepAgents y la consolidación
  diaria de Celery beat). Aprobar las promueve a memoria activa.
* `Exportar` baja toda la memoria del scope `user` redactada.

## Health dashboard

Pestaña `Health` (también disponible vía `GET /health/dashboard`):

* Postgres, Redis, Weaviate, Neo4j (latencias).
* Primary LLM y embeddings (estado `configured` cuando hay credenciales).
* Workers (ping a Celery).
* `checkpointer` con `metadata.backend ∈ {postgres, memory}`.
* `mcp_client` como estado de configuración; el inventario real se valida en
  `GET /system/mcp`, que desde `5953b40` lista servidores en paralelo con
  `MCP_INVENTORY_TIMEOUT_SECONDS=30`.
* `operational_backlog` para approvals/jobs/action-requests atascados.

## Backups

```bash
bash scripts/backup_postgres.sh
bash scripts/backup_neo4j.sh
bash scripts/backup_storage.sh
# o
bash scripts/backup_all.sh
```

Artefactos en `backups/` con `sha256` por archivo.

## Restore

Los restore scripts son deliberadamente conservadores: todos exigen
`CONFIRM_RESTORE=YES` y verifican `.sha256` cuando el archivo existe.

### Postgres

```bash
bash scripts/dev_up.sh
CONFIRM_RESTORE=YES bash scripts/restore_postgres.sh backups/postgres/ARCHIVO.dump
```

### Neo4j

```bash
CONFIRM_RESTORE=YES bash scripts/restore_neo4j.sh backups/neo4j/neo4j_TIMESTAMP/neo4j.dump
```

### Storage

```bash
CONFIRM_RESTORE=YES bash scripts/restore_storage.sh backups/storage/ARCHIVO.tar.gz
```

`restore_storage.sh` mueve el storage actual a `storage.pre_restore_TIMESTAMP`
antes de extraer el backup.

## Rotar Claves

1. Detén API, worker, beat.
2. Edita `.env`. Si era una clave externa, revócala primero en el proveedor.
3. `bash scripts/dev_up.sh`.
4. `GET /health/dashboard` y verifica que el componente afectado muestre
   `status=ok`/`configured`.

## Privacidad

* `LANGSMITH_TRACING=false` por defecto.
* `TRACE_FULL_PAYLOADS=false` por defecto.
* Logs y `args_redacted` redactan secretos / patrones bearer / API keys.
* Documentos sensibles permanecen en `storage/originals/`; nunca se envían
  a servicios externos sin redacción previa (`_safe_metadata` redacta
  `source_path` antes de citar).

## Troubleshooting

* `checkpointer_postgres_unavailable_fallback_memory` en logs → revisa
  `DATABASE_URL`, que el contenedor `cognitive_os_postgres` esté `running`
  y que `alembic upgrade head` haya pasado.
* `retrieve_context_unavailable` en logs → revisa Weaviate (`/health/dashboard`)
  y las credenciales de embeddings.
* Job estancado en `running` → mira eventos en `Jobs` y, si el worker
  murió, reinicia con `bash scripts/dev_worker.sh`. `cleanup_old_jobs`
  cierra jobs terminados con > 30 días.
* `OpenShellPolicyViolation` → la tarea pidió acciones bloqueadas por
  política. Revisa `args_redacted` antes de aprobar.

## Wizard de bootstrap de credenciales

`bash scripts/init_credentials.sh` muestra un checklist con tres columnas
(estado / credencial / qué habilita) más la instrucción exacta para
obtener cada una. Si el API local está vivo consulta
`/system/credentials-status`; si no, llama al inventario inline en
Python (no requiere Postgres ni Redis).

- `OK ✓`  → configurada.
- `REQ ✗` → faltante y **bloqueante** para grado comercial.
- `OPT ○` → faltante pero opcional (habilita una integración específica).

Modo CI:

```bash
bash scripts/init_credentials.sh --ci
```

En `--ci` el script retorna `exit 1` si quedan credenciales `REQ`
faltantes, así puede usarse como gate de pipeline.

## Estado vivo de credenciales

El endpoint `GET /system/credentials-status` (admin) reporta en tiempo real
qué credenciales están configuradas y cuáles faltan, con un puntero exacto a
dónde obtenerlas. La fuente de verdad es
`backend/src/cognitive_os/core/credentials_inventory.py`: agregar una
credencial nueva es una entrada en `INVENTORY` y el endpoint la expone
automáticamente.

```bash
curl -fs -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/system/credentials-status | jq '
  {total, configured, missing_required,
   missing: [.items[] | select(.configured==false) | {name, optional, how_to_obtain}]}'
```

El endpoint **nunca** devuelve valores — solo booleanos y `how_to_obtain` —
así que es seguro consultarlo desde el panel.

## Workflow.v1 — clonar y re-ejecutar planes

Cualquier `ActionRequest` con `action_type` en la lista exportable se
serializa a JSON portable y se vuelve a someter:

```bash
# exportar
curl -fs -H "Authorization: Bearer $TOKEN" \
    "http://127.0.0.1:8000/actions/requests/$REQUEST_ID/workflow" \
    > workflow.json

# editar workflow.json a gusto (mismo schema redactado), luego importar
curl -fs -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    --data @workflow.json \
    http://127.0.0.1:8000/actions/requests/from-workflow
```

El import pasa por los mismos `create_*_request` que la UI, así que aprobación,
allow-lists, idempotency y cifrado se mantienen. Lista completa de tipos
exportables, formato JSON y guardrails: `docs/ACTION_PLANE.md` §
"Workflow.v1".

## Bootstrap desde cero (operador nuevo)

Esta sección asume que el operador clona el repo fresh y necesita levantar
Cognitive OS para uso real. Cubre solo los pasos que requieren input manual.

### 0. Pre-requisitos del host

- Linux con Docker + Docker Compose v2.
- Python 3.12+ via `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- Node.js 20+ y `npm` ≥ 10 para el frontend.
- 8 GB RAM libres recomendados (Postgres + Weaviate + Neo4j en local).

### 1. Variables locales: `.env.local`

```bash
cd cognitive-os
cp .env.example .env       # secretos generados automáticamente
cp .env.local.example .env.local
chmod 600 .env .env.local
```

`init_env.sh` se ejecuta al levantar la primera vez y completa los secretos
de infra (`JWT_SECRET`, `POSTGRES_PASSWORD`, `WEAVIATE_API_KEY`,
`NEO4J_PASSWORD`).

### 2. Credenciales externas — cómo obtener cada una

| Variable | Cómo se obtiene | Necesaria para |
|---|---|---|
| `PRIMARY_LLM_API_KEY` | Cuenta en DeepSeek (`https://platform.deepseek.com`) → API keys | Chat, research, analysis |
| `EMBEDDINGS_API_KEY` | Google AI Studio (`https://aistudio.google.com/apikey`) → generar API key Gemini | Búsqueda semántica, RAG |
| `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` | Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 client (Desktop app). Habilita la API "Gmail API" | Digest Gmail read-only |
| `GMAIL_TOKEN_DIR/token.json` | Ejecuta `uv run python backend/scripts/auth_google.py gmail` y completa el flujo OAuth en el navegador | Gmail digest real |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Mismo client de Cloud Console (puedes reutilizar el de Gmail si scopes lo permiten) | Calendar/Drive |
| `GOOGLE_TOKEN_DIR/token.json` | `uv run python backend/scripts/auth_google.py google` con scopes calendar.events + calendar.freebusy + drive | Calendar create/freebusy + Drive upload/organize |
| `GOOGLE_MAPS_API_KEY` | Google Cloud Console → APIs & Services → Maps API + Routes API habilitadas | `/actions/maps/route` |
| `ELEVENLABS_API_KEY` | `https://elevenlabs.io/app/settings/api-keys` | `/voice/speak`, `/voice/transcribe` |
| `GODADDY_API_KEY` / `GODADDY_API_SECRET` | `developer.godaddy.com` → Production keys (empezar con OTE) | `/actions/godaddy/dns/*` |
| `MAIL_GODADDY_USERNAME` / `MAIL_GODADDY_PASSWORD` | Webmail de GoDaddy → IMAP/SMTP creds. **Activa "Allow less-secure apps" o usa app password** | Mail personal |
| `TAVILY_API_KEY` | `https://app.tavily.com` → API keys | Web search |
| `BRAVE_SEARCH_API_KEY` | `https://api.search.brave.com/app/keys` | Web search fallback |
| `EXA_API_KEY` | `https://dashboard.exa.ai/api-keys` | Web search semántico |
| `HF_TOKEN` | `https://huggingface.co/settings/tokens` (read scope) | Reranker Hugging Face |
| `LANGSMITH_API_KEY` | `https://smith.langchain.com/settings` | Trazas runtime (opcional) |
| `TELEGRAM_BOT_TOKEN` | `@BotFather` → /newbot | Bot Telegram |
| `TELEGRAM_AUTHORIZED_USER_IDS` | `@userinfobot` te devuelve tu id numérico | Bot Telegram |
| `SUPERMEMORY_API_KEY` / `SUPERMEMORY_PROJECT` | `https://app.supermemory.ai/dashboard` | Memoria personal cross-sesión |
| `CONTEXT7_API_KEY` | `https://context7.com/dashboard` | MCP Context7 |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | `https://github.com/settings/tokens?type=beta` con `repo` read | MCP GitHub remoto |
| `ACTION_PAYLOAD_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` | Cifrado payload ejecutable (producción exige `ACTION_PAYLOAD_ENCRYPTION_REQUIRED=true`) |

Si una credencial no aparece, la capacidad asociada queda en `blocked` o
`disabled` en `/health/dashboard` — el resto del sistema sigue operativo.

### 3. Levantar y verificar

```bash
# desde la raíz del workspace
bash cognitive-os/scripts/dev_up.sh                # infra Docker
cd cognitive-os/backend
uv sync --extra openharness
uv run alembic upgrade head
uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000  &
bash ../scripts/dev_worker.sh &
bash ../scripts/dev_beat.sh &
cd ../frontend && npm ci && npm run dev &
```

Smoke autenticado:

```bash
TOKEN=$(uv run python -c "from cognitive_os.core.auth import create_access_token;print(create_access_token(user_id='1', roles=['admin']))")
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/system/info | jq
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/health/dashboard | jq '.status'
```

`/system/info` debe mostrar `approval_require_four_eyes=true`,
`action_payload_encryption_required=true` (producción) y el `git_commit`
actual.

### 4. Compuertas pre-producción

Antes de mover el cockpit fuera de tu host:

1. `bash cognitive-os/scripts/full-qa.sh` → backend + frontend verdes, alembic
   sin drift, `git diff --check` clean.
2. `bash cognitive-os/backend/scripts/verify_operator_ready.sh` → Alembic en
   head, frontend lint/build, sin drift.
3. `uvx pre-commit run --all-files` → secrets/format/whitespace verdes.
4. `uvx --from detect-secrets detect-secrets scan` → `results: {}`.
5. `bash cognitive-os/scripts/stress-qa.sh 3` → 3 pasadas pytest verdes.

### 5. Riesgos residuales conocidos

- **OAuth Google manual**: `GOOGLE_TOKEN_DIR/token.json` no se puede
  generar sin un operador frente al navegador la primera vez. Es OAuth de
  desktop por diseño; renovaciones son automáticas con refresh token.
- **Rate limit en proceso**: el limiter es local. Si despliegas múltiples
  réplicas del API necesitas un store compartido (Redis) — el módulo
  `core/rate_limit.py` expone la interfaz lista para ser sustituida.
- **Telegram approve**: cerrado en Fases 50-58. `/approve` y `/reject` aceptan
  UUID completo o prefijo único, firman como `telegram:<chat_id>`, comparten la
  cascada de `decide_approval()` y, al aprobar un `execute_action_request:<id>`,
  encolan y despachan la tarea Celery `run_action_request_task_async`.
- **OpenChamber / OpenCode**: son cockpit-only y no parte del runtime
  productivo. No hace falta exponerlos hacia internet.

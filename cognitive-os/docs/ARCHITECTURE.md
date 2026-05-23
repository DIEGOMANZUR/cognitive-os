# Cognitive OS — Arquitectura (referencia técnica completa)

> **Estado canónico actual (2026-05-23, commit `647f103`):** arquitectura
> local-first para un PC dedicado del operador, con prioridad explícita
> de fricción casi nula por sobre seguridad estricta. `strict` sigue
> existiendo como perfil conservador, pero el perfil operativo preferido
> es `dedicated_local/full`: usa Edge real/Kimi WebBridge, filesystem
> local y auto-resolución de aprobaciones cuando está configurado. La
> seguridad de perímetro no es el eje de esta instalación; sí lo son
> trazabilidad, idempotencia, observabilidad, recuperación y fallos
> explícitos.
>
> **Cambio reciente que afecta arquitectura (`647f103`):** la ORM `Base`
> (`backend/src/cognitive_os/core/db.py`) define
> `__mapper_args__ = {"eager_defaults": True}` para que SQLAlchemy 2.x
> emita `INSERT/UPDATE ... RETURNING` para las columnas con
> server-default (`created_at`, `updated_at`, etc.). Esto es **obligatorio
> en async sessions** porque sin `eager_defaults` un attribute lazy-load
> tras `await session.flush()` dispara SQL síncrono fuera del greenlet y
> rompe con `sqlalchemy.exc.MissingGreenlet`. Era la causa raíz de un P1
> en `/actions/browser/preview/request` y endpoints análogos.
>
> **Conteos verificados contra código** (generados por
> `scripts/sync_doc_counts.py`): **147 decoradores REST**, **23 tareas
> Celery** en **5 colas** (`default`, `ingestion`, `agent_longrun`,
> `maintenance`, `mail`) con hasta **13 jobs beat**, **20 migraciones
> Alembic** (head `202605200003`), **20 vistas Next.js** bajo
> `frontend/app/views/*.tsx`, **18 componentes** en `/health/dashboard`
> (17 checks + `checkpointer`), **37 slash commands** de Telegram, el set
> de tools built-in tipadas del DeepAgent más tools dinámicas MCP cuando
> `ENABLE_MCP_CLIENT=true`.
>
> **QA más reciente (commit `647f103`):** `bash scripts/full-qa.sh` verde
> con **947 passed**, 1 skipped, 28 deselected;
> ruff/format/mypy/Alembic/lint/build/`sync_doc_counts --check`/`git diff
> --check` OK; build frontend aislado con `NEXT_DIST_DIR=.next-qa`;
> Playwright **31 passed** sin exportar `COGOS_JWT` (auto-mint via
> `_global-setup.ts`); stress QA verde con 3 pasadas de **947 passed**;
> carril opt-in `tests/live/` verificado con **8 passed**; TestSprite MCP
> re-audit **10/10 passed** sobre dos batches.

---

## 0. Qué es Cognitive OS (en una frase y en un párrafo)

**En una frase:** Cognitive OS es un *sistema operativo cognitivo
local-first* — un agente de IA que vive en la PC del operador, con sus
credenciales reales, y que puede investigar, redactar, analizar
documentos, operar Google (Maps/Calendar/Drive), gestionar correo,
controlar el navegador real, organizar el filesystem y delegar tareas de
programación a CLIs de coding agents, todo bajo un plano de control
auditable con compuertas humanas alrededor de cualquier acción sensible.

**En un párrafo:** El sistema combina cuatro piezas. (1) **LangGraph**
orquesta el flujo: un grafo de estados con un router que clasifica cada
pedido y lo enruta a un subgrafo especializado. (2) **DeepAgents** hace el
trabajo profundo: subagentes controlados con un set de herramientas
tipadas, políticas por rol y memoria persistente. (3) **El Action Plane**
ejecuta acciones sobre el mundo real (Google, mail, browser, DNS,
filesystem, code builds) a través de `ActionRequest` persistentes,
preview-first cuando aplica y políticas de aprobación dependientes del
perfil: conservadoras en `strict`, de mínima fricción en
`dedicated_local/full`. Mail es la excepción: el flujo normal solo lee y
propone respuestas. (4) **La capa de
persistencia y retrieval** — PostgreSQL+pgvector (fuente de verdad
operacional), Weaviate (búsqueda híbrida BM25+vector sobre los chunks de
documentos), Neo4j (grafo de entidades, read-only) y Redis (broker de
Celery + backend del rate limiter). Todo expuesto vía una API FastAPI,
una consola Next.js y un bot de Telegram que comparten exactamente el
mismo servicio de negocio — y por lo tanto la misma `tool policy`, los
mismos `HumanApproval` y el mismo `AuditEvent`.

---

## 1. Cableado de alto nivel

```
┌──────────────┐   ┌──────────────┐   ┌────────────────────────────────────┐
│   Next.js    │   │   Telegram   │   │              FastAPI app           │
│  (panel web  │──▶│   bot (long  │──▶│  /chat /threads /documents          │
│   :3001)     │   │   poll)      │   │  /document-analysis /jobs           │
└──────────────┘   └──────────────┘   │  /approvals /actions/* /mail/*      │
                                      │  /research/* /code-director/*       │
                                      │  /system/* /health/* /deepagents/*  │
                                      └────────────────┬───────────────────┘
                                                       │
                          ┌────────────────────────────┼────────────────────┐
                          ▼                            ▼                    ▼
                  ┌──────────────┐            ┌──────────────┐      ┌──────────────┐
                  │  LangGraph   │            │ Celery tasks │      │  AsyncSQL    │
                  │ orquestador  │            │ + Redis cola │      │ (Postgres)   │
                  │ (checkpointer│            │ (5 colas)    │      │ +pgvector    │
                  │  Postgres)   │            └──────┬───────┘      └──────────────┘
                  └──────┬───────┘                   │
        ┌────────────────┼───────────┬───────────────┼──────────────────┐
        ▼                ▼           ▼               ▼                  ▼
 ┌────────────┐  ┌──────────────┐ ┌──────────┐ ┌────────────────┐ ┌──────────────┐
 │  retrieve  │  │  DeepAgents  │ │  Action  │ │ Document       │ │ OpenShell    │
 │ (Weaviate  │  │ (research +  │ │  Plane   │ │ Analysis       │ │ sandbox      │
 │  hybrid +  │  │  document_   │ │ (Google, │ │ (Evidence      │ │ (vendor,     │
 │  reranker) │  │  analysis) + │ │  mail,   │ │  Ledger +      │ │  opcional)   │
 │            │  │  MCP tools   │ │  browser,│ │  evaluators)   │ │              │
 │            │  │  dinámicas   │ │  DNS, fs)│ │                │ │              │
 └─────┬──────┘  └──────┬───────┘ └────┬─────┘ └────────┬───────┘ └──────┬───────┘
       ▼                ▼              ▼                ▼                ▼
 ┌────────────┐  ┌──────────────┐ ┌──────────┐ ┌────────────────┐ ┌──────────────┐
 │ Weaviate   │  │ skills +     │ │ Postgres │ │ workspaces/    │ │ docker host  │
 │ (chunks +  │  │ memoria +    │ │ Action   │ │   analysis/    │ │ contenedor   │
 │ embeddings)│  │ workspace fs │ │ Requests │ │   *.csv *.docx │ │ aislado      │
 └────────────┘  └──────────────┘ └──────────┘ └────────────────┘ └──────────────┘
```

**Servidores MCP externos** (Fase 73, cuando `ENABLE_MCP_CLIENT=true`):
el DeepAgent carga tools dinámicas de servidores MCP declarados en
`MCP_SERVERS` — Supermemory, GitHub, filesystem, o cualquier servidor que
hable Model Context Protocol. Ver §8.

---

## 2. Estado operacional (PostgreSQL como fuente de verdad)

PostgreSQL es la **única** fuente de verdad operacional. Todo lo
siguiente vive ahí, con el esquema versionado en
`backend/alembic/versions/`:

| Tabla | Qué guarda |
|---|---|
| `users` | identidad local (no hay multi-tenant real; es single-operator) |
| `threads` / `thread_messages` | conversaciones del orquestador |
| `documents` / `document_pages` / `document_chunks` | pipeline de ingesta de PDFs |
| `jobs` / `job_events` | toda tarea async (ingesta, deepagent, code build, mail sync, reapers) + su timeline |
| `human_approvals` | compuertas HITL (four-eyes opcional, cascada a Job/ActionRequest) |
| `audit_events` | trail de auditoría de toda acción importante |
| `action_requests` | el corazón del Action Plane: preview + payload cifrado + estado de dispatch |
| `deepagent_memory` / `deepagent_memory_proposals` | memoria del agente (proposal → approval → active) |
| `deepagent_memory_episodic` | memoria episódica |
| `deepagent_skill_usage` | registro de uso de skills |
| `tool_invocation_metrics` | rollup diario de confiabilidad por (agente, tool) — Fase C del plan de aprendizaje |
| `procedure_invocation_log` | uso de procedures (`kind=procedure`) por job + outcome — Fase B (skill promotion) |
| `document_analysis_results` | resultados del pipeline legal |
| `mail_accounts` / `mail_messages` / `mail_send_logs` | correo multicuenta |
| `personal_tasks` / `personal_notes` | asistente personal |
| `research_run_records` | runs de investigación persistentes |

> **Aislamiento de DB de test:** la suite `pytest` **nunca** escribe en
> esta base. `tests/conftest.py` redirige `DATABASE_URL` a una base
> `cognitive_os_test` dedicada que se dropea + recrea + migra a head en
> cada corrida (red de seguridad: se niega a correr si la URL apunta a
> producción). Ver `docs/qa/RUNBOOK.md §7`.

Las 20 migraciones forman una **cadena lineal sin ramas** (head
`202605200003`). `scripts/full-qa.sh` corre `alembic check` para detectar
drift.

---

## 3. Estado del thread de LangGraph (checkpointer)

El grafo compilado usa un *checkpointer* que persiste el estado de cada
conversación:

* **Producción / `uvicorn`:** el lifespan de FastAPI abre un
  `PostgresSaver` vía `cognitive_os.agents.graph.postgres_checkpointer()`.
  Los threads sobreviven reinicios de proceso; `/threads/{id}/resume`
  sigue funcionando. **Esto es lo que hace que el bot de Telegram
  recuerde la conversación** (Fase 70): cada chat tiene un `thread_id`
  determinista y su estado vive en Postgres.
* **Tests / fallback:** si Postgres no está disponible al arrancar, el
  lifespan loguea un warning y cae a `MemorySaver`. El grafo sigue usable;
  los threads simplemente no persisten entre reinicios.

El backend activo se reporta en `GET /health/dashboard` como el
componente `checkpointer` (`status=ok` para postgres, `configured` para
memory).

> **Honestidad de `/health/dashboard` (AUDIT-2026-B).** Cada componente
> reporta `ok`/`ready` (verificado en vivo o apagado), `configured`
> (cableado pero sin llamada real) o `degraded` (fallo). El overall es
> `ok` solo si **todo** está verificado; si algo está `configured` el
> overall es `configured`, no `ok`. `POST /health/verify` fuerza el probe
> real (completion LLM mínima, embedding real, login IMAP) bajo demanda.
> El componente `operational_backlog` vigila approvals/jobs/action-requests
> atascados y el lag del beat.

---

## 4. Nodos del orquestador (`agents/graph.py`)

* **`router_node`** — clasifica el pedido en `research` / `legal` /
  `comm` / `social`. Si el request trae `doc_ids` explícitos, fuerza
  `legal` sin pasar por el router LLM (señal inequívoca de análisis
  documental). El router LLM degrada con red:
  `agent → secondary → primary → deterministic_route`.
* **`deterministic_route`** — fallback por keywords cuando ningún LLM
  responde. **Fase 74:** `comm`/`social` ahora exigen un *verbo de
  acción* explícito (enviá, redactá, publicá...). Un mensaje
  informacional que sólo menciona un canal ("qué mensajes tengo") cae en
  `research` y responde directo, sin disparar un interrupt de
  human-review.
* **`retrieve_context_node`** — búsqueda híbrida en Weaviate + reranker
  lazy. Los errores se degradan a "sin contexto" en vez de matar el
  request.
* **`research_node`** — prelude opcional de **OpenHarness** `QueryEngine`
  (si `ENABLE_OPENHARNESS_RESEARCH` y el paquete están presentes), luego
  el subagente DeepAgent de research. Fallback determinístico citado si
  el DeepAgent no produce contenido sustantivo.
* **`legal_node`** — cuando se pide análisis documental, arma un
  `DocumentAnalysisTask` (con `doc_ids`, `case_id`, modos) y delega a
  `DocumentAnalysisService`. Los borradores siempre disparan un
  `HumanReviewItem`.
* **`comm_node`** / **`social_node`** — proponen comunicaciones; el envío
  real pasa por `HumanApproval`.
* **`human_review_node`** — interrumpe el grafo y espera
  approve/edit/reject.
* **`error_node`** / **`final_response_node`** — recuperación y
  serialización.

El **SystemMessage de identidad** (Fase 70): `initial_state()` prepende
el contenido de `docs/AGENT_SELF.md` como `SystemMessage` con id estable,
de modo que el agente siempre sabe quién es y qué puede hacer.

---

## 5. Conexiones en runtime

* **Frontend → FastAPI:** JWT bearer; CORS permite `localhost:3001` y
  `127.0.0.1:3001` (frontend real) más `:3000` (legacy/compat); el
  default cubre los 4, override vía `CORS_ALLOW_ORIGINS`.
* **Telegram → FastAPI:** el bot llama al **mismo servicio de negocio**
  que el REST. Mensaje con `/` → slash command; mensaje sin `/` en
  `dedicated_local` → carril `/chat` conversacional con thread
  persistente.
* **FastAPI → LangGraph:** `_api_graph` es un grafo compilado a nivel de
  módulo; el lifespan lo re-vincula a un grafo con checkpointer Postgres
  al arrancar.
* **FastAPI → Celery:** los jobs largos (`ingest_pdf`,
  `run_deepagent_task`, `run_openshell_task`, `run_code_build`,
  `run_action_request`, `sync_personal_mail`) van por colas Redis con
  routing keys separadas.
* **Celery → DeepAgents:** las tasks arman un `DeepAgentTask` y llaman a
  `run_deepagent_task` / `DocumentAnalysisService.run_analysis_as_job`.
  Cada tool call pasa por la capa de políticas (`tools/policy.py`) y se
  audita.
* **DeepAgents → MCP:** cuando `ENABLE_MCP_CLIENT=true`,
  `build_deepagent_tools` suma las tools de los servidores MCP a las
  built-in (ver §8).
* **DeepAgents → RAG:** `search_within_allowed_docs` filtra los hits de
  Weaviate al `allowed_doc_ids` del agente y a `allowed_page_ranges`.
* **Action Plane:** `backend/src/cognitive_os/actions/` expone los
  servicios preview-first (browser, computer, Gmail, GoDaddy, Maps,
  Calendar, Drive, captcha, Kimi WebBridge) más los `ActionRequest`
  persistentes.
* **Consolidación de memoria:** Celery beat dispara
  `consolidate_all_deepagent_memory` a diario.

---

## 6. Beat schedule — reapers, consolidación y aprendizaje

El beat de Celery agenda hasta **13 jobs** (todos detrás de feature
flags; el número exacto depende de qué flags estén activos). Los 3
reapers cubren clases de falla del Action Plane; las 5 tareas de
aprendizaje implementan las Fases A-E del `AGENT_LEARNING_PLAN.md`:

| Job beat | Cron | Qué hace |
|---|---|---|
| `reap_stale_approvals` | `:15` cada hora | rescata `HumanApproval` colgados > `APPROVAL_PENDING_MAX_HOURS` |
| `reap_stuck_action_requests` | `*/10` min | `ActionRequest` en `running` huérfanos + `dispatch_state` colgado |
| `reap_stale_running_jobs` | `03:30` diario | jobs zombie en `queued`/`running` > `STALE_JOB_MAX_HOURS` |
| `consolidate_all_deepagent_memory` | `03:00` diario | consolidación de memoria por agente |
| `extract_pending_recipes` | `*/30` min | **Fase A** — distila jobs exitosos en recetas `kind=procedure` |
| `nightly_reflection` | `03:00` diario | **Fase E** — el LLM propone preferences/lessons con evidencia literal |
| `scan_failure_postmortems` | `03:35` diario | **Fase D** — warnings desde patrones fallo→recuperación |
| `aggregate_tool_scorecard` | `04:15` diario | **Fase C** — rollup de confiabilidad por (agente, tool) |
| `evaluate_skill_promotions` | `04:45` diario | **Fase B** — promociones procedure→skill + rollback de skills flojos |
| `personal-mail-sync` / `telegram-gmail-digest` / `personal-assistant-reminders` | varios | correo, digest y recordatorios (gated por `MAIL_ENABLED` / `TELEGRAM_*`) |

El **dispatch durable** (Fase 59-64): REST y Telegram registran
`JobEvent` submitted/failed; un fallo del broker devuelve una razón de
retry controlada; reserva atómica `dispatch_state=submitting|submitted|
failed` antes de `apply_async` impide submits duplicados; reentrada de
worker corta circuito si el job ya está `running`.

---

## 7. Modos de falla y degradación elegante

| Componente caído | Efecto |
|---|---|
| Postgres | El lifespan cae a `MemorySaver`; jobs/auth fallan |
| Redis | La API responde igual; los jobs Celery no se encolan |
| Weaviate / embeddings | `_safe_retriever` retorna `[]`; el chat responde "sin evidencia" |
| Reranker ausente | Ranker léxico de fallback; cumple spec |
| Neo4j | La ingesta avisa y continúa; el chat no se afecta |
| Proveedor LLM | El router cae a ruteo determinístico por keywords |
| OpenHarness ausente/off | El research path saltea el QueryEngine; DeepAgents + fallback sin cambios |
| Mail IMAP/SMTP | `/mail/status` reporta degraded; nada de auto-send |
| Servidor MCP caído | Ese server se skipea con warning; los otros cargan igual; `/system/mcp` lo muestra. El inventario se carga en paralelo con timeout default 30s para evitar falsos timeouts por servers lentos |

---

## 8. Cliente MCP (Model Context Protocol) — Fase 73

Bajo `ENABLE_MCP_CLIENT=true`, el DeepAgent carga **tools dinámicas** de
servidores MCP externos, además de su set de tools built-in tipadas.

* **Declaración:** `MCP_SERVERS` en `.env`, CSV con sintaxis
  `name:transport:target[::extra=v,...]`. Transportes soportados: `sse`,
  `streamable_http`, `websocket` (target = URL), `stdio` (target =
  comando; extras `cwd=`, `env_KEY=`).
* **Módulo:** `integrations/mcp_client.py` — parser + loader async sobre
  `langchain_mcp_adapters.MultiServerMCPClient`. Las tools llegan
  prefijadas `<server>_<tool>` (sin colisiones con las built-in).
* **Inventario paralelo:** cada server se lista concurrentemente; un `stdio`
  frio o un `npx` lento no bloquea en serie a los demas. El timeout
  configurable `MCP_INVENTORY_TIMEOUT_SECONDS` default es 30s.
* **Fail-open por server:** si un server cae, se loguea warning y se
  skipea; los demás cargan igual.
* **Allow-list por subgrafo:** `MCP_ALLOWED_FOR_RESEARCH` /
  `MCP_ALLOWED_FOR_DOCUMENT_ANALYSIS` restringen qué servers ve qué
  carril. Vacío = todos.
* **Sólo `dedicated_local`:** las tools MCP son credenciales personales
  del operador; el wrapper sync corta circuito fuera de ese perfil.
* **Observabilidad:** `GET /system/mcp` dialoga con cada server y reporta
  `connected` + `tools_count`; `health/dashboard` tiene el componente
  `mcp_client` (config sin live RPC).
* **Runtime verificado:** `mem`, `gh`, `fs`, `cc` y `gem` conectados 5/5,
  con 67 tools inyectables.

Detalle completo: `docs/COGNITIVE_OS_GUIDE.md` §MCP.

---

## 9. Controles de seguridad

* Todo endpoint mutador requiere un JWT. El claim "admin" se exige cuando
  `ADMIN_USER_IDS` no está vacío o el rol está en `AUTH_ADMIN_ROLES`.
* Niveles de riesgo de tools: `READ_ONLY`, `REVERSIBLE_WRITE`,
  `EXTERNAL_ACTION`, `DANGEROUS`, `SANDBOX_EXECUTE`. Las acciones
  externas y las dangerous siempre pasan por `human_approvals` — salvo el
  whitelist de auto-approve reversible bajo `dedicated_local`
  (`drive_ensure_folder`, `drive_upload`, `computer_organize`).
* Redacción de PII por default en trazas LangSmith y metadata de
  auditoría. `payload_executable` de los `ActionRequest` se cifra
  (configurable, obligatorio en producción).
* OpenShell nunca toca `~`, `.env` ni la raíz del repo; corre en Docker
  aislado con approval explícito.
* El Action Plane arranca disabled + dry-run. Dominios de browser, roots
  de filesystem, scopes de Gmail, send de mail y writes de GoDaddy son
  superficies de política explícitas.

---

## 10. Dónde mirar después

* `backend/src/cognitive_os/api/app.py` — wiring, lifespan, 147 decoradores REST.
* `backend/src/cognitive_os/agents/graph.py` — nodos del orquestador y routing.
* `backend/src/cognitive_os/deepagents/` — factory de DeepAgents controlados, subagentes de research y document analysis.
* `backend/src/cognitive_os/integrations/mcp_client.py` — cliente MCP.
* `backend/src/cognitive_os/integrations/telegram_bot.py` — bot Telegram (37 commands + conversacional).
* `backend/src/cognitive_os/ingestion/pipeline.py` — PDF → pages → chunks → Weaviate + Neo4j.
* `backend/src/cognitive_os/workers/tasks.py` — definiciones de tasks Celery + reapers.
* `backend/src/cognitive_os/actions/` — Action Plane.
* `backend/src/cognitive_os/mail/` — correo personal IMAP/SMTP/Gmail.
* `backend/src/cognitive_os/core/health.py` — los 17 checks de `/health/dashboard` (+ `checkpointer` = 18 componentes) y `check_health_dashboard(verify_live=...)`.
* `docs/AGENT_SELF.md` — identidad del agente (lo carga como contexto).
* `docs/USER_GUIDE.md` — guía operativa de punta a punta.
* `docs/ACTION_PLANE.md`, `docs/SECURITY.md`, `docs/DEEPAGENTS_INTEGRATION.md`, `docs/DOCUMENT_ANALYSIS_AGENT.md`, `docs/OPENSHELL_SANDBOX.md`, `docs/OPENHARNESS_FUSION.md` — deep dives por dominio.

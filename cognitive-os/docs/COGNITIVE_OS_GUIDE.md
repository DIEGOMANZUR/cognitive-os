# Cognitive OS — Guía Maestra

> **Última actualización:** 2026-05-15, Fase 33 RBAC + cifrado + research durable.
> **Estado del producto:** monorepo en grado comercial operativo (backend FastAPI 0.115+ con **118 endpoints REST** —92 propios + 26 orquestación—, **14 tareas Celery** distribuidas en **5 colas** `default`/`ingestion`/`agent_longrun`/`maintenance`/`mail`, **14 migraciones Alembic**, LangGraph 1.1.10 + DeepAgents 0.6.x + Postgres 16+pgvector + Redis 7 + Weaviate 1.29.0 + Neo4j 5 ligados a `127.0.0.1` por defecto; consola Next.js 16.2.6 con **18 vistas** en `app/views/*.tsx` incluidas `AssistView` y `GoogleOpsView`; bot Telegram opcional; Kimi WebBridge; fusión opcional con OpenHarness en la ruta `research`). Runtime local: **DeepSeek V4 Pro** (`deepseek-v4-pro`) como LLM base; secundario Kimi K2.6-code-preview; vision GLM-4.6v primario. Mail personal GoDaddy IMAP/SMTP + Gmail label `TODOS` soportado + propuestas escritas; Google Maps/Calendar/Drive operables; envío y writes externos solo aprobados (`MAIL_REQUIRE_APPROVAL_FOR_SEND=true`). Asistente personal con `PersonalTask`/`PersonalNote` CRUD y reminders. Cockpit `.opencode/` con **21 MCPs**, **15 skills**, 7 subagentes y 7 comandos slash.
> **QA snapshot persistente:** 492 pytest passed, 1 skipped, 20 deselected (513 tests recogidos); ruff + ruff format + mypy (108 source files) + frontend lint + frontend build + Compose config + Alembic head + `git diff --check` → todo verde. Fase 33 aplica la Fase 29 comercial: RBAC local explícito, cifrado de payload ejecutable y persistencia configurable de research.
> **Para qué es este documento:** que **una sola persona, sin contexto previo**, pueda entender qué es Cognitive OS, qué hace, qué *no* hace, cómo se usa por web, por API y por Telegram, y qué le falta para dejar el sistema redondo. Cada afirmación tiene su archivo o variable de respaldo en el repo.

---

## Tabla de contenidos

1. [Qué es Cognitive OS (en una frase y en palabras simples)](#1-qué-es-cognitive-os)
2. [Para qué sirve y para qué NO sirve](#2-para-qué-sirve-y-para-qué-no-sirve)
3. [Casos de uso concretos](#3-casos-de-uso-concretos)
4. [Mapa mental: cómo encajan las piezas](#4-mapa-mental-cómo-encajan-las-piezas)
5. [El recorrido completo de una petición](#5-el-recorrido-completo-de-una-petición)
6. [Componentes del backend, uno por uno](#6-componentes-del-backend-uno-por-uno)
7. [Frontend: las 18 vistas y cómo usar cada una](#7-frontend-las-18-vistas-y-cómo-usar-cada-una)
8. [Telegram: cada comando con ejemplo](#8-telegram-cada-comando-con-ejemplo)
9. [La fusión OpenHarness + DeepAgents en `research`](#9-la-fusión-openharness--deepagents-en-research)
10. [Document Analysis (ruta legal)](#10-document-analysis-ruta-legal)
11. [Action Plane: acciones reales y guardrails](#11-action-plane-acciones-reales-y-guardrails)
12. [Memoria, skills y aprobaciones](#12-memoria-skills-y-aprobaciones)
13. [Cómo arrancar el sistema, paso a paso](#13-cómo-arrancar-el-sistema-paso-a-paso)
14. [Variables de entorno (qué es crítico, qué es opcional)](#14-variables-de-entorno)
15. [Credenciales, tokens y APIs externas: qué falta para completar](#15-credenciales-tokens-y-apis-externas-qué-falta)
16. [Operación día a día: backups, restore, monitorización](#16-operación-día-a-día)
17. [Troubleshooting común](#17-troubleshooting-común)
18. [Roadmap: lo que aún falta para "asistente personal absoluto"](#18-roadmap)

---

## 1. Qué es Cognitive OS

**En una frase:**
Cognitive OS es un **sistema operativo cognitivo local-first y auditable** que coordina LLMs, agentes y herramientas para investigar, analizar documentos con citas, recordar lo aprobado, preparar acciones reales (navegador, archivos, correo, DNS, documentos Office) y ejecutar tareas largas en background, **sin entregar el control a un solo modelo** y con **aprobación humana obligatoria** en cualquier acción sensible.

**En palabras simples:**
Imagina un equipo de trabajo dentro de tu computador:

- **Un orquestador (LangGraph)** decide qué tipo de tarea es la que pides y a quién pasársela.
- **Un investigador profundo (DeepAgents)** consulta documentos locales con citas, web cuando se permite, y entrega un informe estructurado.
- **Un analista legal** especializado para documentos: matrices hecho/evidencia/cita, líneas de tiempo, contradicciones.
- **Una mesa de aprobaciones** en la que un humano decide cuándo dejar que el sistema actúe en el mundo real.
- **Un panel web** desde el que operas todo.
- **Un bot de Telegram** opcional para usar el sistema desde el móvil.
- **Un motor de tareas largas (Celery)** que corre ingesta de PDFs, document analysis, memoria diaria, navegador headless, etc.
- **Capa de fusión OpenHarness** opcional: cuando se activa, el QueryEngine de OpenHarness corre **antes** del DeepAgent en la ruta `research`, comparten workspace y el DeepAgent integra el preludio en su informe.

Todo corre en tu infraestructura (Docker local), todas las acciones quedan auditadas en Postgres, los secretos no se loguean, y nada externo se ejecuta sin un flag explícito y normalmente sin aprobación humana.

**Lo que NO es:**

- No es un chatbot suelto.
- No es un agente "que hace todo solo y manda emails sin avisar".
- No es un reemplazo de un abogado, un periodista, un sysadmin o un editor de imágenes profesional.
- No es un servicio SaaS: corre en tu máquina o tu servidor, con tus credenciales.

---

## 2. Para qué sirve y para qué NO sirve

### Sirve para…

| Caso | Cómo lo resuelve |
| --- | --- |
| Investigar un tema con citas y trazabilidad | Ruta `research` (RAG local + opcional OpenHarness + DeepAgent + fallback determinista) |
| Analizar legalmente un set de documentos | Ruta `legal` (Document Analysis Agent: matriz, timeline, contradicciones, borradores) |
| Ingerir PDFs, dividirlos en páginas/chunks y dejarlos consultables con citas | `POST /documents/ingest` + worker Celery + Weaviate + Neo4j opcional |
| Tener "memoria" del usuario aprobada (preferencias, decisiones, ejemplos) | DeepAgents memory con propuestas → aprobación → memoria activa |
| Generar documentos `.docx`, `.xlsx`, `.pptx` con guardrails (paths, tamaño, fórmulas seguras) | Action Plane → `documents` |
| Ordenar carpetas locales con preview y aprobación humana antes de mover | Action Plane → `computer_organize` |
| Inventariar archivos de un disco bajo allow-list, sin leer contenido | Action Plane → `computer_inventory` |
| Previsualizar páginas web headless (titulo + screenshot) en dominios allow-listed | Action Plane → `browser_preview` |
| Ejecutar planes interactivos en navegador (click/fill/scroll/screenshot/analyze con vision) | Action Plane → `browser_interactive` |
| Leer Gmail en modo digest read-only (resumen redactado) sin enviar nada | Action Plane → Gmail `digest/preview` |
| Revisar correo personal multicuenta, proponer respuestas y enviarlas con aprobación | `/mail/*` + GoDaddy IMAP/SMTP + Gmail label `TODOS` |
| Planificar rutas con tráfico y link navegable | Action Plane → Google Maps `route` |
| Crear eventos Calendar y subir entregables a Drive con aprobación | Google Ops + `ActionRequest` (`calendar_create_event`, `drive_upload_file`) |
| Preparar cambios DNS en GoDaddy con dry-run, allow-list y aprobación | Action Plane → GoDaddy `dns/preview` + `request` |
| Coordinar **investigación multi-subtarea con presupuesto y SSE** | Research Orchestrator (`/research/runs`) con cancelación y eventos |
| Operar todo desde Telegram (móvil) | Bot opcional con 25+ comandos slash |
| Trazar runs en LangSmith (cuando se quiere observabilidad nube) | `/langsmith/*` |
| Grabar memoria episódica (qué hizo el agente y cuándo) | `POST /deepagents/memory/episodic` |

### NO sirve para…

| No haces esto con Cognitive OS | Por qué |
| --- | --- |
| Enviar correos automáticamente | Prohibido por política inicial. `/mail/messages/{id}/approve-send` exige aprobación humana y `MAIL_REQUIRE_APPROVAL_FOR_SEND=true`. |
| Publicar en redes sociales | `enable_social_posting=false` por defecto; no hay executor de redes implementado. |
| Cambiar DNS sin aprobación humana | Flujo `dry-run` por defecto, allow-list de dominios y aprobación obligatoria. |
| Dar acceso a tu navegador real con tu sesión | `browser_preview/interactive` corre en perfiles aislados, headless, allow-list de dominios. **Nunca** usa tu perfil de Chrome/Firefox real. |
| Tomar decisiones legales por ti | `legal_draft_support` siempre marca `needs_human_review`; los borradores son apoyo, no presentación final. |
| Reemplazar un IDE/repo agent profesional | OpenShell sandbox (vendor) puede ejecutar código aislado, pero no hay flujo "edita un repo entero por mí" implementado. |
| Procesar audio/voz | Backend STT/TTS ElevenLabs implementado; falta UX completa de voz en frontend/Telegram (ver §18). |
| Resumir vídeos de YouTube | Integración pendiente (ver §18). |
| Mover/borrar archivos del repo del proyecto, `.env`, `.ssh`, etc. | Bloqueado por allow-list y guardrails (`COMPUTER_ALLOWED_ROOTS` no incluye home por defecto). |

---

## 3. Casos de uso concretos

1. **"Quiero entender qué dicen estos 8 PDFs sobre el caso X y necesito una matriz hecho/evidencia/cita y una línea de tiempo."**
   1. Subes los PDFs vía panel `Documents` (o `POST /documents/ingest`).
   2. En `Document Analysis` seleccionas los `doc_ids`, los modos `evidence_matrix`, `timeline`, `contradictions`, `full_report`.
   3. El sistema encola un job Celery; cuando termina, descargas `report.md`, `result.json`, `evidence_matrix.csv`, `timeline.csv`, `contradictions.csv` y opcionalmente `report.docx`.
   4. Si hay borradores legales, el sistema crea una `HumanApproval` y no entrega resultado hasta tu OK.

2. **"Investiga este tema con mis docs y la web, dame un informe con citas."**
   1. En `Chat`, haces la pregunta sin adjuntar `doc_ids` (si fuerzas `doc_ids` → ruta `legal`).
   2. El router decide ruta `research`.
   3. (Opcional) Si activaste OpenHarness, primero corre el `QueryEngine` y deja un preludio en la metadata.
   4. DeepAgent investiga con RAG local + web (si `WEB_SEARCH_ENABLED=true`) y entrega informe con citas.
   5. Si DeepAgent no responde, fallback determinista RAG.

3. **"Necesito ordenar mi carpeta `~/Descargas`."**
   1. Activas `ENABLE_COMPUTER_ACTIONS=true`, añades la ruta a `COMPUTER_ALLOWED_ROOTS`.
   2. `POST /actions/computer/organize/preview` te devuelve el plan de movimientos.
   3. `POST /actions/computer/organize/request` crea una `ActionRequest` persistente.
   4. Apruebas en `Approvals`. Si `COMPUTER_ORGANIZE_DRY_RUN_ONLY=false`, Celery ejecuta los movimientos.
   5. Cada movimiento queda en `audit_events`.

4. **"Quiero revisar mi correo importante y aprobar respuestas."**
   1. En `Mail`, ejecutas `Sync ahora` o dejas Celery beat con `MAIL_ENABLED=true`.
   2. El sistema lee GoDaddy IMAP (`INBOX`, spam/junk/bulk) y, si OAuth está listo, Gmail label `TODOS`.
   3. Mensajes importantes quedan como `reply_proposed` con texto editable.
   4. `Aprobar y enviar` manda por SMTP GoDaddy y registra `MailSendLog`.
   5. No hay drafts ni auto-send.

5. **"Quiero un digest diario de Gmail por Telegram."**
   1. Activas `GMAIL_READ_ENABLED=true`, generas `token.json` con scopes `gmail.readonly` (Google quickstart) y lo dejas en `GMAIL_TOKEN_DIR`.
   2. Activas `TELEGRAM_GMAIL_DIGEST_ENABLED=true` con `TELEGRAM_GMAIL_DIGEST_CHAT_IDS`.
   3. Celery beat envía el digest a la hora `TELEGRAM_GMAIL_DIGEST_HOUR_UTC` mirando las últimas `LOOKBACK_HOURS` horas.
   4. **No envía respuestas**; solo lee y resume.

6. **"Necesito que el sistema funcione 100% offline para una tarea sensible."**
   1. Apaga `WEB_SEARCH_ENABLED`, `OPENHARNESS_WEB_TOOLS`, `LANGSMITH_TRACING`.
   2. Usa solo RAG local + Document Analysis + Skills.
   3. El sistema ya no hace ninguna llamada externa salvo a tu LLM (que tú apuntas a un endpoint local si quieres).

7. **"Necesito que un equipo de auditores revise lo que hace el agente."**
   1. Pestaña `Audit` → endpoint `/audit/events` con paginación.
   2. Cada tool call pasa por `record_audit_event` con `args_redacted`.
   3. `LANGSMITH_TRACING=true` con `TRACE_REDACT_PII=true` da trazas externas si quieres.

---

## 4. Mapa mental: cómo encajan las piezas

```
┌─────────────────┐                ┌─────────────────────────────────────────┐
│  Frontend       │                │ FastAPI app (92 propios / 118 REST)     │
│  Next.js 16     │ ─── REST/SSE ──│  /chat /chat/stream /threads/*          │
│  18 vistas      │ ◄── JWT ───────│  /documents/* /document-analysis/*      │
│  (panel web)    │                │  /jobs /approvals /audit /health/*      │
└─────────────────┘                │  /actions/* /deepagents/* /assist/*     │
                                   │  /research/* /langsmith/* /agents       │
                                   │  /mail/*                                │
┌─────────────────┐                │  /sandbox/openshell/*                   │
│ Telegram bot    │ ─── HTTP ─────►│                                         │
│ (opcional, 25+  │                └────────────────────┬────────────────────┘
│  comandos)      │                                     │
└─────────────────┘                                     │
                       ┌─────────────────────────────────┼─────────────────────────────┐
                       ▼                                 ▼                             ▼
                ┌──────────────┐                  ┌─────────────────┐            ┌──────────────┐
                │  LangGraph   │                  │  Celery worker  │            │  AsyncSQL    │
                │ orquestador  │                  │ + Redis cola    │            │ (Postgres +  │
                │ (router →    │                  │ (ingest, agent, │            │  pgvector)   │
                │ retrieve →   │                  │  document_an,   │            │              │
                │ research /   │                  │  memory consol, │            └──────────────┘
                │ legal / etc) │                  │  reaper jobs)   │
                └──────┬───────┘                  └─────────────────┘
                       │
        ┌──────────────┼─────────────┬───────────────┬───────────────┐
        ▼              ▼             ▼               ▼               ▼
   ┌─────────┐  ┌────────────┐ ┌──────────────┐ ┌─────────────┐ ┌─────────────┐
   │ retrieve│  │ DeepAgents │ │  Document    │ │  Action     │ │  OpenShell  │
   │ context │  │ research / │ │  Analysis    │ │  Plane      │ │  sandbox    │
   │ (RAG +  │  │ doc_an     │ │  (legal      │ │  (browser/  │ │  (vendor    │
   │ rerank) │  │ subagents  │ │  matrices,   │ │  computer/  │ │  externo,   │
   │         │  │ + memory + │ │  timelines,  │ │  mail/DNS/  │ │  Docker,    │
   │         │  │ skills)    │ │  contradicts)│ │  GoDaddy/   │ │  off por    │
   │         │  │            │ │              │ │  documents) │ │  defecto)   │
   └────┬────┘  └─────┬──────┘ └──────────────┘ └─────────────┘ └─────────────┘
        │             │                              │
        ▼             ▼                              ▼
   ┌──────────┐  ┌──────────────┐             ┌──────────────┐
   │ Weaviate │  │ workspaces/  │             │ HumanApproval│
   │ (chunks) │  │ thread/task/ │             │ + AuditEvent │
   │   +      │  │ report.md,   │             │  (Postgres)  │
   │  Neo4j   │  │ result.json  │             └──────────────┘
   └──────────┘  └──────────────┘
                          │
                          ▼ (en research, opcional)
                 ┌──────────────────────────┐
                 │ OpenHarness QueryEngine  │
                 │ (extra openharness-ai)   │
                 │ workspace mirror, presets│
                 │ tools, prelude_merge     │
                 └──────────────────────────┘
```

---

## 5. El recorrido completo de una petición

Sigue una petición típica `POST /chat/stream` con un mensaje "Investiga X" para entender la mecánica:

1. **Auth**: el header `Authorization: Bearer <jwt>` se verifica. Sin JWT, 401.
2. **Estado inicial**: `initial_state(message, thread_id, user_id, doc_ids?, case_id?)` construye `CognitiveState` con presupuesto, política de tools y mensaje del usuario.
3. **Stream**: el endpoint devuelve SSE; cada `data:` es un evento JSON (`thread_started`, `node_update`, `interrupt`, `final_response`, `error`, `done`).
4. **router_node**:
   - Si hay `doc_ids` explícitos → ruta `legal` (Document Analysis).
   - Si no, decide vía LLM con `RouterDecision` (research/legal/comm/social) o fallback determinista por keywords.
   - Si la solicitud es sensible (`enviar`, `publicar`, `borrar`), marca `needs_human_review`.
5. **retrieve_context_node** (en rutas que lo necesitan): Weaviate hybrid search + reranker (si está activo). Si Weaviate falla, devuelve `[]` sin tumbar la petición.
6. **research_node**:
   - Si `ENABLE_OPENHARNESS_RESEARCH=true` y el extra está instalado:
     - Resuelve `cwd` (mirror del DeepAgent) y llama `run_openharness_research_sync`.
     - El bridge corre el `QueryEngine` en un hilo aislado con event loop propio.
     - Si responde válido y pipeline = `short_circuit`, retorna esa respuesta (sin DeepAgent).
     - Si responde válido y pipeline = `prelude_merge` (default), guarda el preludio en `task.metadata["openharness_prelude"]`.
     - Si falla, log `openharness_research_fallback` y continúa sin preludio.
   - Llama `run_deepagent_task(task)`. El DeepAgent recibe el preludio (si existe) en su `HumanMessage`.
   - Si el DeepAgent pidió acciones externas → crea `HumanReviewItem` y el grafo se interrumpe.
   - Si el DeepAgent no respondió o respondió vacío → fallback `ResearchAgent` determinista con citas.
7. **human_review_node**: si hay `pending_human_review`, llama `interrupt(...)` y la petición espera (en SSE emite `interrupt`).
8. **final_response_node**: serializa `AgentResult` (route, content, citations, uncertainty) y lo emite por SSE como `final_response`.
9. **Persistencia**: `PostgresSaver` (LangGraph checkpointer) guarda el estado del thread; si Postgres no está, fallback a `MemorySaver` (in-memory, sin persistencia entre reinicios).
10. **Auditoría**: cada tool call relevante pasa por `record_audit_event` con `args_redacted`.

> Misma mecánica para `/chat` (no streaming) y `/threads/{id}/resume` (continúa un thread interrumpido por `human_review_node`).

---

## 6. Componentes del backend, uno por uno

### 6.1. API FastAPI (`backend/src/cognitive_os/api/app.py`)

118 endpoints REST agrupados por dominio (92 propios + 26 de orquestación/transversales; excluye `/docs`, `/redoc`, `/openapi.json` y `/docs/oauth2-redirect`). Catálogo resumido de rutas reales del código, todas requieren JWT excepto `/health`:

#### Salud y configuración
- `GET /health` — público, devuelve `{status: "ok"}`.
- `GET /health/dashboard` — Postgres/Redis/Weaviate/Neo4j/LLMs/Embeddings/Workers/Checkpointer con latencia.
- `GET /config/public` — flags no sensibles para que el frontend sepa qué encender/apagar.
- `GET /knowledge/stats` — número de documentos, páginas, chunks, jobs, aprobaciones.

#### Chat / threads
- `POST /chat` — síncrono.
- `POST /chat/stream` — SSE con eventos por nodo.
- `GET /threads` — recientes.
- `GET /threads/{thread_id}` — snapshot completo.
- `POST /threads/{thread_id}/resume` — `approve | edit | reject` para continuar después de `human_review_node`.

#### Documentos e ingesta
- `POST /documents/ingest` — encola job Celery `ingest_pdf`.
- `GET /documents` — lista paginada.
- `GET /documents/{document_id}/chunks` — chunks indexados.

#### Document Analysis
- `POST /document-analysis/run` — encola `DocumentAnalysisTask`.
- `GET /document-analysis/{task_id}` — estado y resultado.
- `GET /document-analysis/{task_id}/report` — Markdown plano.
- `GET /document-analysis/{task_id}/download/json|markdown|docx`.
- `GET /document-analysis/{task_id}/download/csv/{kind}` — `evidence_matrix`, `timeline`, `contradictions`.

#### DeepAgents (skills + memoria)
- `GET /deepagents/skills` y `GET /deepagents/skills/{name}`.
- `GET /deepagents/memory` (memoria activa) y `GET /deepagents/memory/proposals`.
- `POST /deepagents/memory/proposals/{id}/approve` y `POST /deepagents/memory/proposals/{id}/reject`.
- `POST /deepagents/memory/export` — JSON redactado.
- `POST /deepagents/memory/episodic` — añadir entrada `kind=episodic`.
- `POST /deepagents/memory/consolidate/run` — disparar consolidación manual.

#### Asistente personal (tasks/notes)
- `GET/POST/PATCH/DELETE /assist/tasks` y `/assist/tasks/{id}`.
- `GET/POST/PATCH/DELETE /assist/notes` y `/assist/notes/{id}`.

#### Jobs y aprobaciones
- `GET /jobs` y `GET /jobs/{id}`, `GET /jobs/{id}/events`, `POST /jobs/{id}/cancel`.
- `GET /approvals`, `POST /approvals/{id}/approve|reject`.

#### Auditoría
- `GET /audit/events` con filtros y paginación.

#### Action Plane (browser, computer, Gmail, Google, GoDaddy, documents)
- `GET /actions/capabilities` — estado por proveedor.
- `POST /actions/browser/validate|preview/request|interactive/request|request`.
- `POST /actions/computer/organize/preview|request`, `POST /actions/computer/inventory`.
- `GET/POST /actions/gmail/status|query/preview|query/request|digest/preview`.
- `GET/POST /actions/maps/status|geocode|route`.
- `GET/POST /actions/calendar/status|events|events/create|events/request`.
- `GET/POST /actions/drive/status|files|files/upload|files/upload/request|folders/ensure`; `GET /actions/drive/files/{file_id}`.
- `GET/POST /actions/godaddy/status|dns/preview|dns/request`.
- `GET/POST /actions/documents/status|preview|request`.
- `GET /actions/requests`, `GET /actions/requests/{id}`, `POST /actions/requests/{id}/dispatch|cancel`.

#### Mail personal GoDaddy/Gmail-label
- `GET /mail/status` — cuentas y flags no sensibles.
- `POST /mail/sync` — sincronización manual GoDaddy IMAP + Gmail label si OAuth está activo.
- `POST /mail/sync/dispatch` — encola sync en Celery queue `mail`.
- `GET /mail/messages`, `GET /mail/messages/{id}` — mensajes persistidos y propuestas.
- `PATCH /mail/messages/{id}/reply` — edita la propuesta escrita.
- `POST /mail/messages/{id}/ignore` — ignora un mensaje.
- `POST /mail/messages/{id}/approve-send` — envía por SMTP GoDaddy solo tras aprobación explícita.

#### Research Orchestrator
- `POST /research/runs`, `GET /research/runs`, `GET /research/runs/{id}`, `POST /research/runs/{id}/cancel`, `GET /research/runs/{id}/events` (SSE).

#### Sandbox
- `GET /sandbox/openshell/status` (vendor `openshell-deepagent` opcional, deshabilitado por defecto).

#### LangSmith
- `GET /langsmith/status|projects|runs|runs/{id}` — gobernado por `LANGSMITH_ENDPOINTS_REQUIRE_ADMIN`.

#### Agentes
- `GET /agents` — vista resumen del estado de agentes/políticas para el panel.

### 6.2. Orquestador LangGraph (`backend/src/cognitive_os/agents/graph.py`)

- Nodos: `router`, `retrieve_context`, `research`, `legal`, `comm`, `social`, `human_review`, `final_response`, `error`.
- Checkpointer: `PostgresSaver` en producción; fallback `MemorySaver` si Postgres no está disponible.
- `interrupt(...)` para human-in-the-loop; `Command(resume=...)` lo retoma.
- `research_node` orquesta la fusión OpenHarness + DeepAgents (ver §9).

### 6.3. DeepAgents (`backend/src/cognitive_os/deepagents/`)

Subagentes controlados con políticas (`DeepAgentToolPolicy`). Tools expuestas:

| Tool | Qué hace |
| --- | --- |
| `search_local_docs` | RAG con citas; filtra por `allowed_doc_ids` |
| `read_document_pages` | Lee páginas (max 20) desde Postgres |
| `graph_query_readonly` | Cypher predefinido sobre Neo4j |
| `search_web` | Solo si `WEB_SEARCH_ENABLED` y la tarea lo permite |
| `write_workspace_file` | Escribe en `storage/workspaces/{thread}/{task}/` |
| `list_available_skills` | Skills habilitadas (core + user) |
| `read_skill` | Devuelve un SKILL.md |
| `get_relevant_memory` | Memoria revisada por scope |
| `propose_memory_update` | **Propone**, no aprueba (requiere humano) |

Subagentes activos cuando `DEEPAGENTS_ENABLE_SUBAGENTS=true`:
- Research: `local-rag-researcher`, `citation-auditor`, `web-researcher`.
- Document analysis: `evidence-matrix-specialist`, `timeline-specialist`, `contradiction-reviewer`.

### 6.4. Document Analysis (`backend/src/cognitive_os/deepagents/document_analysis/`)

Subagente legal especializado. Modos verificados (Literal):
`evidence_matrix`, `timeline`, `contradictions`, `full_report`, `legal_draft_support`, `case_summary`.

Salida: `result.json`, `report.md`, `evidence_matrix.csv`, `timeline.csv`, `contradictions.csv`, opcional `report.docx`. Si `quality_score < 85` o hay borradores legales, crea `HumanApproval`.

### 6.5. Action Plane y mail personal (`backend/src/cognitive_os/actions/`, `backend/src/cognitive_os/mail/`)

8 dominios de acción con servicios independientes y un carril de mail personal:
- **Browser**: Playwright headless, `browser_preview` (titulo + screenshot) y `browser_interactive` (planes con vision opcional).
- **Computer**: `computer_organize` (mover archivos con preview/aprobación) y `computer_inventory` (read-only metadata).
- **Gmail**: `digest/preview` (read-only, redacta direcciones, **no** crea drafts).
- **Maps**: geocoding y rutas read-only con tráfico, duración base, retraso y link Google Maps.
- **Calendar**: listar eventos y crear eventos por `ActionRequest` aprobable (`calendar_create_event`).
- **Drive**: listar/get, asegurar carpeta de entregables y subir archivos allow-listed por `ActionRequest` (`drive_upload_file`).
- **GoDaddy**: DNS preview + executor real con dry-run, allow-list, aprobación.
- **Documents**: DOCX/XLSX/PPTX con guardrails de paths, tamaño, assets allow-listed, fórmulas XLSX no inyectables.
- **Mail personal**: GoDaddy IMAP/SMTP + Gmail label `TODOS` opcional, propuestas escritas, envío por SMTP GoDaddy solo con aprobación.

### 6.6. RAG / búsqueda (`backend/src/cognitive_os/memory/`, `ingestion/`)

- Embeddings: provider configurable (default Gemini); claves de fallback (`EMBEDDINGS_FALLBACK_API_KEYS`).
- Weaviate: hybrid search (BM25 + vector).
- Reranker: `BAAI/bge-reranker-base` opcional (`RERANKER_ENABLED=true`).
- Neo4j: relaciones entre entidades, complementa al RAG en preguntas relacionales.

### 6.7. Celery workers (`backend/src/cognitive_os/workers/`)

Colas: `ingestion`, `agent_longrun`, `maintenance`, `mail`, `default`. Tareas: `ingest_pdf`, `run_deepagent_task`, `run_openshell_task`, `run_document_analysis`, `sync_personal_mail`, `consolidate_all_deepagent_memory` (beat diaria), `cleanup_old_jobs`, reaper de `action_requests` colgados y digest Telegram Gmail si está activo.

### 6.8. OpenHarness bridge (`backend/src/cognitive_os/integrations/openharness_research.py`)

Ver §9. Usa `_execute_engine_blocking` (hilo dedicado + event loop propio) para no romper si el caller está dentro de un loop async.

### 6.9. Seguridad y políticas (`backend/src/cognitive_os/tools/policy.py`, `core/auth.py`, `core/path_policy.py`)

- JWT en cada endpoint protegido.
- Tool risk levels: `READ_ONLY`, `REVERSIBLE_WRITE`, `EXTERNAL_ACTION`, `DANGEROUS`, `SANDBOX_EXECUTE`.
- Validación de paths (no symlinks fuera de allow-list, no `..`, no rutas absolutas inesperadas).
- Redacción PII en trazas y `args_redacted` en `audit_events`.
- `reject_changeme_in_production`: si `ENVIRONMENT=production` y un secreto crítico sigue como `CHANGEME`, el backend no arranca.

---

## 7. Frontend: las 18 vistas y cómo usar cada una

Frontend en `frontend/`, Next.js 16 (Turbopack), React 19, ESLint 9. Vistas en `frontend/app/views/`. Cada vista habla con la API vía `ApiClient` (configurable desde `Settings` o `NEXT_PUBLIC_API_BASE_URL`).

| Vista | Para qué sirve | Cómo se usa |
| --- | --- | --- |
| **Chat** | Tu cara a cara con el orquestador | Escribes; opcionalmente adjuntas `doc_ids` (fuerza ruta legal) y `case_id`; ves nodos en streaming, citas y aprobaciones inline |
| **Dashboard** | Vista resumen | Estado general, salud, contadores |
| **Settings** | Configura conexión al backend, JWT y preferencias | Pega tu JWT, ajusta `API_BASE_URL` |
| **Approvals** | Bandeja de aprobaciones | Apruebas/rechazas; si la `HumanApproval` corresponde a un `ActionRequest` `execute_action_request`, el panel intenta `dispatch` automáticamente |
| **Memory** | Memoria DeepAgents | Ves memoria activa por scope `user`, propuestas pendientes, exportas en JSON redactado |
| **Jobs** | Workers Celery | Lista jobs recientes con auto-refresh; entrada en cada uno con eventos detallados |
| **Sandbox** | Estado OpenShell | `GET /sandbox/openshell/status`; si está deshabilitado lo dice; nada de escritura desde el panel sin aprobación |
| **Documents** | Ingesta de PDFs | Pegas ruta absoluta visible para el backend; te devuelve `job_id`; sigues progreso en `Jobs` |
| **DocumentAnalysis** | Pipeline legal | Eliges `doc_ids`, query, modos, formatos; encolas; cuando completa, descargas todos los artefactos |
| **Configuration** | Capacidades + ActionRequests recientes | Lista `/actions/capabilities`, recientes; despacha automáticamente al aprobar `execute_action_request` |
| **Mail** | Bandeja personal GoDaddy/Gmail-label | Sincronizas, filtras importantes, editas propuestas, ignoras o apruebas envío por SMTP GoDaddy |
| **Google Ops** | Operación Google Maps/Calendar/Drive | Calculas rutas con tráfico/link, creas requests aprobables de eventos Calendar y subes entregables a Drive |
| **LangSmith** | Trazas/proyectos/runs externos | Solo si `LANGSMITH_TRACING=true` y endpoints disponibles |
| **Agents** | Estado de agentes | Resumen `/agents`: políticas, recientes, capacidades |
| **Skills** | Skills DeepAgents | Listadas core + user; ves definición y `risk_level` |
| **Health** | Componentes y latencias | `/health/dashboard` con backend del checkpointer (`postgres` o `memory`) |
| **Audit** | Auditoría | `/audit/events` con filtros |

> En desarrollo, `NEXT_PUBLIC_API_BASE_URL` define la URL inicial del API; en runtime, `Settings` permite cambiarla sin rebuild.
> El JWT se mantiene en memoria de sesión del frontend, no en `localStorage`; si recargas, vuelve a pegarlo o implementa un flujo auth real.

---

## 8. Telegram: cada comando con ejemplo

El bot vive en `backend/src/cognitive_os/integrations/telegram_bot.py`. Se ejecuta como proceso aparte:

```bash
cd backend
uv run python -m cognitive_os.integrations.telegram_bot
```

Requiere:
- `TELEGRAM_ENABLED=true`
- `TELEGRAM_BOT_TOKEN=<token de @BotFather>`
- `TELEGRAM_AUTHORIZED_USER_IDS=<tu user_id>,...` (los user_ids de Telegram, no aliases)

Long-polling, no necesitas webhook (funciona detrás de NAT).

### Comandos disponibles

| Comando | Para qué | Ejemplo |
| --- | --- | --- |
| `/start`, `/help` | Bienvenida + lista de comandos | `/help` |
| `/health` | Resumen healthy/degraded de componentes | `/health` |
| `/stats` | Knowledge stats (docs/pages/chunks/jobs/approvals) | `/stats` |
| `/config` | Flags no sensibles | `/config` |
| `/agents` | Estado DeepAgents + política + actividad reciente | `/agents` |
| `/skills` | Skills habilitadas | `/skills` |
| `/memory` | Propuestas pendientes | `/memory` |
| `/consolidate` | Despacha consolidación de memoria ahora | `/consolidate` |
| `/jobs` | Jobs recientes | `/jobs` |
| `/job <id>` | Detalle + últimos eventos | `/job 7c8e…` |
| `/cancel <id>` | Cancela job (idempotente) | `/cancel 7c8e…` |
| `/approvals` | Aprobaciones pendientes | `/approvals` |
| `/approve <id>` | Aprueba (firmado con tu chat) | `/approve 1f0…` |
| `/reject <id>` | Rechaza | `/reject 1f0…` |
| `/threads` | Threads LangGraph recientes | `/threads` |
| `/chat <mensaje>` | Conversa con el orquestador (REST equivalente) | `/chat investiga LangGraph vs DeepAgents` |
| `/ingest <ruta>` | Encola un PDF (ruta visible para el backend) | `/ingest /home/me/docs/contrato.pdf` |
| `/runs` | Runs recientes en LangSmith (si está activo) | `/runs` |
| `/tasks` | Lista tus personal tasks | `/tasks` |
| `/task <título \| desc>` | Crea una tarea personal | `/task Llamar a Andrea \| pendiente del lunes` |
| `/done <id>` | Marca tarea como done | `/done 90f…` |
| `/notes` | Lista notas personales (Markdown) | `/notes` |
| `/note <título \| body>` | Crea una nota | `/note Recordatorio reunión \| traer las cifras Q3` |
| `/gmaildigest` | Digest Gmail read-only inmediato | `/gmaildigest` |

### Mapas (chat ↔ user)

- **`TELEGRAM_ASSIST_USER_MAP`**: pares `chat_id:user_id_api` para que `/tasks` y `/notes` se asocien a un `user_id` real del API.
- **`TELEGRAM_REMINDER_CHAT_MAP`**: pares `user_id_api:chat_id` para entrega de recordatorios proactivos (requiere `ENABLE_PERSONAL_REMINDER_DELIVERY=true`).
- **`TELEGRAM_GMAIL_DIGEST_CHAT_IDS`**: chats que reciben el digest automático diario; vacío ⇒ todos los `TELEGRAM_AUTHORIZED_USER_IDS`.

### Reglas de seguridad del bot

- Solo responde a IDs en `TELEGRAM_AUTHORIZED_USER_IDS`.
- Cada comando pasa por la **misma capa de servicio** que la API: no se saltea políticas de aprobación.
- Respuestas Markdown, capadas a 4000 chars (límite Telegram).
- Si un comando requiere acción sensible (ej. `/cancel`, `/approve`), queda registrado en `audit_events` con el `chat_id` como actor.

---

## 9. La fusión OpenHarness + DeepAgents en `research`

Documento canónico: [`OPENHARNESS_FUSION.md`](./OPENHARNESS_FUSION.md). Resumen ejecutivo:

- **OpenHarness** (HKUDS) es un motor de bucle de tools probado (`QueryEngine` + `ToolRegistry` + `PermissionChecker`).
- En Cognitive OS es **opcional**: requiere `uv sync --extra openharness` y `ENABLE_OPENHARNESS_RESEARCH=true`.
- En la ruta `research`, LangGraph ejecuta el `QueryEngine` **antes** del DeepAgent y le pasa el resultado como **preludio** dentro del `HumanMessage` (modo `prelude_merge` por defecto).
- Modos: **`prelude_merge`** (preludio + DeepAgent siempre) o **`short_circuit`** (devuelve solo OH si responde válido).
- Workspace: **`deepagent_mirror`** por defecto (mismo directorio que DeepAgent), o `sandbox` (`OPENHARNESS_WORKSPACE`).
- Presets de tools: **`minimal`** (grep/glob + opcional file/web), **`research`** (kit amplio: bash + file + skills + cron + agente + web), **`full`** (`create_default_tool_registry` upstream, sin MCP remoto).
- Web dentro del harness exige **dos** flags: `WEB_SEARCH_ENABLED && OPENHARNESS_WEB_TOOLS`.
- Puente con runner aislado: `_execute_engine_blocking` corre el QueryEngine en un hilo dedicado con `loop = asyncio.new_event_loop()`. Esto blinda el bridge contra callers async.
- Precedencia de skips: `disabled` > `openharness_not_installed` > `empty_query` (intención del operador antes que estado del entorno).
- Trazabilidad: `metadata["openharness_prelude"]` queda visible en el resultado final → cualquiera puede leer qué entró al informe.
- Por qué la fusión > cada uno por separado:
  - LangGraph mantiene política, persistencia y aprobaciones aunque el research use OpenHarness.
  - Workspace compartido: los archivos generados por OH son visibles para DeepAgent y viceversa.
  - Fallback determinista si ambos motores fallan.

---

## 10. Document Analysis (ruta legal)

Cuando adjuntas `doc_ids` o el router decide `legal`:

1. `legal_node` construye `DocumentAnalysisTask` (`task_id`, `thread_id`, `case_id?`, `doc_ids`, `query`, `modes`, `require_human_review_for_drafts=True`).
2. `DocumentAnalysisService` encola un job en `agent_longrun`.
3. Subagentes especializados ejecutan: `evidence-matrix-specialist`, `timeline-specialist`, `contradiction-reviewer` (con DeepAgent harness controlado).
4. Resultado: `DocumentAnalysisResult` con `evidence_matrix`, `timeline`, `contradictions`, `quality_score`, `citations`, `draft_sections?`.
5. Exportadores: `result.json`, `report.md`, `evidence_matrix.csv`, `timeline.csv`, `contradictions.csv`, opcional `report.docx`.
6. Si `quality_score < 85` o hay borradores → crea `HumanApproval` en `partial`/`needs_human_review`.

Detalle: [`DOCUMENT_ANALYSIS_AGENT.md`](./DOCUMENT_ANALYSIS_AGENT.md).

---

## 11. Action Plane: acciones reales y guardrails

Detalle: [`ACTION_PLANE.md`](./ACTION_PLANE.md).

**Capacidades con ejecución real ya implementada** (todas con flags y/o aprobación):
- `computer_organize` (con `dispatch` + aprobación + `dry_run=false`).
- `document_generate` (DOCX/XLSX/PPTX en `DOCUMENT_OUTPUT_ROOT`).
- `browser_preview` (Playwright headless, screenshot acotado).
- `browser_interactive` (Chromium headless, plan de pasos, vision opcional).
- `calendar_create_event` (Google Calendar por `ActionRequest`, flag write + aprobación).
- `drive_upload_file` (Google Drive por `ActionRequest`, allow-list de path + carpeta de entregables).
- `mail approve-send` (SMTP GoDaddy desde `/mail/messages/{id}/approve-send`, solo aprobación explícita).

**Capacidades read-only/preview por defecto:**
- Gmail digest (lee y resume, **nunca** crea drafts en el mailbox).
- Google Maps (geocode/route read-only, con tráfico y link navegable).
- GoDaddy DNS (`dry_run` por defecto; ejecución real exige `GODADDY_DNS_DRY_RUN_ONLY=false` + dominio en allow-list + aprobación + en producción `GODADDY_ALLOW_PRODUCTION_WRITES=true`).
- Browser request, Gmail query request → solo registra `ActionRequest`, no ejecuta.

**Ciclo de toda acción real:**
`Validate → Preview → Request (ActionRequest) → Approve (HumanApproval) → Dispatch (Celery) → Execute → Audit`.

---

## 12. Memoria, skills y aprobaciones

Detalle: [`DEEPAGENTS_SKILLS_MEMORY.md`](./DEEPAGENTS_SKILLS_MEMORY.md).

- **Skills core**: `backend/src/cognitive_os/deepagents/skills/core/` (8 SKILL.md). No se modifican desde fuera.
- **Skills user**: `storage/deepagents/skills/user/<user_id>/<skill_name>/SKILL.md`. Validadas, no pueden activar tools peligrosas por defecto.
- **Memoria**:
  - Activa: `deepagent_memory_records` (Postgres). Solo aprobada.
  - Propuestas: `deepagent_memory_proposals`. Generadas por subagentes (`propose_memory_update`) o por la consolidación diaria. Promoción → humano.
  - Episódica: `kind=episodic` vía `POST /deepagents/memory/episodic`. Persiste qué hizo el agente, cuándo y resultado.
  - Startup memory: cada DeepAgent lee al inicio la memoria aprobada para su scope.

- **Aprobaciones (`HumanApproval`)**:
  - Las crea el grafo o servicios (Action Plane, Document Analysis, propuestas de memoria sensibles).
  - Se aprueban/rechazan vía API o panel `Approvals`.
  - Una aprobación firma `approver_user_id` y `decided_at`.
  - Para `execute_action_request`, el panel intenta `dispatch` automáticamente al aprobar.

---

## 13. Cómo arrancar el sistema, paso a paso

### Pre-requisitos
- Python 3.12+ y [`uv`](https://docs.astral.sh/uv/).
- Node 22+ y `npm`.
- Docker + Docker Compose.

### Arranque local mínimo

```bash
# 1. Bootstrap de .env (genera secretos locales)
bash scripts/init_env.sh

# 2. Infra local (Postgres + Redis + Weaviate + Neo4j)
bash scripts/dev_up.sh

# 3. Migraciones
cd backend && uv run alembic upgrade head

# 4. (Opcional) extra OpenHarness para la fusión
uv sync --extra openharness

# 5. API
uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000

# 6. Worker Celery (otra terminal)
bash scripts/dev_worker.sh

# 7. Beat (jobs periódicos: consolidación memoria, cleanup, reaper)
bash scripts/dev_beat.sh

# 8. Frontend (otra terminal)
cd frontend && npm ci && npm run dev    # http://localhost:3000

# 9. (Opcional) Bot Telegram
cd backend && uv run python -m cognitive_os.integrations.telegram_bot
```

### Generar JWT local

```python
from cognitive_os.core.auth import create_access_token
print(create_access_token(user_id="1"))
```

Pega el token en el campo "JWT" del panel Next.js.

### Validación reproducible (antes de promover cambios)

```bash
bash scripts/full-qa.sh    # uv sync --extra openharness + pytest + ruff + format + mypy + npm ci + lint + build
bash scripts/stress-qa.sh  # repite pytest N veces (default 3) para detectar flakiness
```

---

## 14. Variables de entorno

Fuente de verdad: [`SETTINGS_REGISTRY_TABLE.md`](./SETTINGS_REGISTRY_TABLE.md) (generada 1:1 desde `Settings`). `.env.example` en raíz (`./.env.example`) tiene todos los grupos comentados.

### Críticas (sin esto el sistema no opera bien)

| Variable | Para qué |
| --- | --- |
| `JWT_SECRET` | Firmas JWT del API (lo genera `init_env.sh`). |
| `POSTGRES_USER/PASSWORD/DB/HOST/PORT/DATABASE_URL` | Persistencia Postgres. |
| `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Celery. |
| `WEAVIATE_URL`, `WEAVIATE_API_KEY` | RAG vectorial. |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Grafo. |
| `PRIMARY_LLM_BASE_URL/API_KEY/MODEL` | LLM principal (DeepAgents, OpenHarness, router). |
| `EMBEDDINGS_BASE_URL/API_KEY/MODEL/DIMENSION` | Embeddings (default Gemini). |

### LLMs adicionales (opcionales, mejoran)

| Variable | Para qué |
| --- | --- |
| `SECONDARY_LLM_*`, `FALLBACK_LLM_*` | Modelos de respaldo y router. |
| `VISION_LLM_*` | Análisis de imágenes (`browser_interactive` `analyze`). |
| `EMBEDDINGS_FALLBACK_API_KEYS` | Lista CSV de claves embeddings extra para rotación cuando una falla. |
| `RERANKER_ENABLED`, `RERANKER_MODEL` | Mejora ranking RAG (`BAAI/bge-reranker-base`). |

### Búsqueda web (opcional)

`WEB_SEARCH_ENABLED=true` + al menos uno de: `TAVILY_API_KEY`, `BRAVE_*`, `PERPLEXITY_API_KEY`, `EXA_API_KEY`, `SERPER_API_KEY`. El multi-provider deduplica por URL y rankea favoreciendo URLs presentes en varios proveedores.

### OpenHarness fusion (opcional)

`ENABLE_OPENHARNESS_RESEARCH=true` + `OPENHARNESS_RESEARCH_PIPELINE` + `OPENHARNESS_TOOLKIT_PRESET` + `OPENHARNESS_WORKSPACE_MODE` + `OPENHARNESS_WEB_TOOLS` + `OPENHARNESS_QUERY_TIMEOUT_SECONDS` + `OPENHARNESS_MAX_TURNS`. Detalle: [`OPENHARNESS_FUSION.md`](./OPENHARNESS_FUSION.md).

### Telegram (opcional)

`TELEGRAM_ENABLED=true` + `TELEGRAM_BOT_TOKEN` + `TELEGRAM_AUTHORIZED_USER_IDS` + (opcional) `TELEGRAM_ASSIST_USER_MAP`, `TELEGRAM_REMINDER_CHAT_MAP`, `TELEGRAM_GMAIL_DIGEST_*`.

### Action Plane (todo opt-in, deshabilitado por defecto)

| Dominio | Variables |
| --- | --- |
| Browser | `ENABLE_BROWSER_AUTOMATION`, `BROWSER_AUTOMATION_PROVIDER`, `BROWSER_ALLOWED_DOMAINS`, `BROWSER_HEADLESS_DEFAULT`, `BROWSER_ALLOW_HEADED`, `BROWSER_ALLOW_VISION`, `BROWSER_PROFILE_DIR`, `BROWSER_DOWNLOAD_DIR`, `BROWSER_SCREENSHOT_DIR`, `BROWSER_SCREENSHOT_MAX_BYTES`, `BROWSER_NAVIGATION_TIMEOUT_MS`, `ENABLE_BROWSER_SSRF_CHECK` |
| Computer | `ENABLE_COMPUTER_ACTIONS`, `COMPUTER_ALLOWED_ROOTS`, `COMPUTER_ORGANIZE_DRY_RUN_ONLY`, `COMPUTER_MAX_FILES_PER_PLAN` |
| Documents | `ENABLE_DOCUMENT_GENERATION`, `DOCUMENT_OUTPUT_ROOT`, `DOCUMENT_ASSET_ROOTS`, `DOCUMENT_MAX_SIZE_BYTES` |
| Gmail digest/label | `GMAIL_READ_ENABLED`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_TOKEN_DIR`, `GMAIL_SCOPES`, `GMAIL_SEND_ENABLED` (reservado; envío Gmail no implementado) |
| Google Maps/Calendar/Drive | `GOOGLE_MAPS_API_KEY`, `ENABLE_MAPS_GEOCODING`, `ENABLE_MAPS_ROUTING`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_TOKEN_DIR`, `ENABLE_GOOGLE_CALENDAR`, `ENABLE_GOOGLE_CALENDAR_WRITE`, `ENABLE_GOOGLE_DRIVE`, `ENABLE_GOOGLE_DRIVE_WRITE`, `GOOGLE_DRIVE_UPLOAD_MAX_BYTES`, `GOOGLE_DRIVE_DELIVERABLES_FOLDER_NAME` |
| Mail personal | `MAIL_ENABLED`, `MAIL_DEFAULT_SENDER`, `MAIL_REQUIRE_APPROVAL_FOR_SEND`, `MAIL_POLL_INTERVAL_SECONDS`, `MAIL_IMAP_TIMEOUT_SECONDS`, `MAIL_SMTP_TIMEOUT_SECONDS`, `MAIL_FETCH_MAX_PER_FOLDER`, `MAIL_GMAIL_LABEL`, `MAIL_GODADDY_*` |
| GoDaddy | `GODADDY_ENABLED`, `GODADDY_BASE_URL`, `GODADDY_API_KEY`, `GODADDY_API_SECRET`, `GODADDY_ALLOWED_DOMAINS`, `GODADDY_DNS_DRY_RUN_ONLY`, `GODADDY_ALLOW_PRODUCTION_WRITES`, `GODADDY_MAX_REQUESTS_PER_MINUTE` |
| Microsoft mail | `MICROSOFT_MAIL_ENABLED` (placeholder, integración pendiente) |

### Observabilidad / privacidad

| Variable | Para qué |
| --- | --- |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINTS_REQUIRE_ADMIN` | Trazas en LangSmith; endpoints admin-gated por defecto. |
| `AUTH_DEFAULT_ROLES`, `AUTH_ADMIN_ROLES`, `ADMIN_USER_IDS` | RBAC local para JWTs del cockpit/API. Admin ya no se infiere por lista vacía. |
| `ACTION_PAYLOAD_ENCRYPTION_KEY`, `ACTION_PAYLOAD_ENCRYPTION_REQUIRED` | Cifrado at-rest de payloads ejecutables de `ActionRequest`; requerido en producción. |
| `RESEARCH_PERSISTENCE_BACKEND` | `memory` para desarrollo/tests; `postgres` requerido en producción para snapshots/eventos de research. |
| `TRACE_REDACT_PII` (default `true`), `TRACE_FULL_PAYLOADS` (default `false`) | Redacción de payloads en trazas/audit. |
| `HTTP_TIMEOUT_SECONDS`, `HTTP_MAX_RETRIES`, `CIRCUIT_BREAKER_*` | HTTP cliente con retries y circuit breaker. |

---

## 15. Credenciales, tokens y APIs externas: qué falta

Si quieres que **cada capacidad documentada** funcione end-to-end, necesitas estas credenciales/tokens. La columna *"Cómo obtenerlo"* es lo que un operador real tiene que hacer.

### LLMs (al menos uno requerido)
| Servicio | Variable | Cómo obtenerlo |
| --- | --- | --- |
| LLM principal (OpenAI / DeepSeek / Kimi / GLM / OpenAI-compatible local) | `PRIMARY_LLM_BASE_URL`, `PRIMARY_LLM_API_KEY`, `PRIMARY_LLM_MODEL` | Proveedor de tu LLM. Si usas modelo local (vLLM/Ollama/llama.cpp) apunta a su URL OpenAI-compatible. |
| LLM secundario / fallback | `SECONDARY_LLM_*`, `FALLBACK_LLM_*` | Mismo patrón. Defaults vienen apuntando a Kimi y Z.AI; si no usas, deja `CHANGEME` (no rompe). |
| Vision | `VISION_LLM_*` | Para `browser_interactive` `analyze`. Default apunta a GLM 4.6V. |
| Embeddings | `EMBEDDINGS_BASE_URL/API_KEY/MODEL/DIMENSION` | Default Gemini (`generativelanguage.googleapis.com`). Necesitas API key Google AI Studio. |

### Búsqueda web (uno o varios)
| Proveedor | Variable | Cómo obtenerlo |
| --- | --- | --- |
| Tavily | `TAVILY_API_KEY` | https://tavily.com (free tier disponible) |
| Brave Search | `BRAVE_API_KEY`, `BRAVE_ANSWER_API_KEY`, `BRAVE_SEARCH_API_KEY`, `BRAVE_FREE_API_KEY` | https://api.search.brave.com |
| Perplexity | `PERPLEXITY_API_KEY` | https://docs.perplexity.ai |
| Exa | `EXA_API_KEY` | https://exa.ai |
| Serper | `SERPER_API_KEY` | https://serper.dev |

### Gmail
| Variable | Cómo obtenerlo |
| --- | --- |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` | Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client (Desktop). |
| `GMAIL_TOKEN_DIR` con `token.json` | Sigue el [quickstart oficial](https://developers.google.com/workspace/gmail/api/quickstart/python) con scope `https://www.googleapis.com/auth/gmail.readonly`. Pega el `token.json` resultante en esa carpeta. |
| `GMAIL_SCOPES` | Lista CSV de scopes; default solo `gmail.readonly`. Para `send`, añadir scope correspondiente (no implementado). |

### Google Maps / Calendar / Drive
| Variable | Cómo obtenerlo |
| --- | --- |
| `GOOGLE_MAPS_API_KEY` | Google Cloud Console con Routes API y Geocoding API habilitadas. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | OAuth desktop app en Google Cloud Console. Reusa el mismo proyecto que Gmail si conviene. |
| `GOOGLE_TOKEN_DIR/token.json` | `cd backend && uv run python scripts/auth_google.py`; requiere scopes Calendar/Drive configurados. |
| `ENABLE_GOOGLE_CALENDAR_WRITE`, `ENABLE_GOOGLE_DRIVE_WRITE` | Mantener `false` hasta que el operador quiera writes reales; aun activados, writes pasan por `ActionRequest` + aprobación. |
| `GOOGLE_DRIVE_DELIVERABLES_FOLDER_NAME` | Nombre de carpeta operativa para entregables, default `Cognitive OS Deliverables`. |

### Mail personal GoDaddy/Gmail-label
| Variable | Cómo obtenerlo |
| --- | --- |
| `MAIL_ENABLED` | Actívalo solo cuando las credenciales de correo estén listas. |
| `MAIL_GODADDY_USERNAME`, `MAIL_GODADDY_PASSWORD` | Usuario y contraseña/app password del buzón GoDaddy; guardar solo en `.env` local ignorado. |
| `MAIL_GODADDY_IMAP_HOST/PORT`, `MAIL_GODADDY_SMTP_HOST/PORT` | Valores del panel GoDaddy/Workspace Email. Defaults: IMAP 993, SMTP 465. |
| `MAIL_GODADDY_MONITOR_FOLDERS` | Carpetas a revisar, por ejemplo `INBOX,Bulk Mail,Junk Email,Spam`. |
| `MAIL_IMAP_TIMEOUT_SECONDS`, `MAIL_SMTP_TIMEOUT_SECONDS` | Timeouts de red para no dejar workers colgados ante proveedores lentos. |
| `MAIL_GMAIL_LABEL` | Label Gmail secundaria a leer si `GMAIL_READ_ENABLED=true`; default `TODOS`. |
| `MAIL_REQUIRE_APPROVAL_FOR_SEND` | Debe quedar `true` salvo pruebas controladas; el producto no auto-envía. |

### GoDaddy Domains/DNS
| Variable | Cómo obtenerlo |
| --- | --- |
| `GODADDY_API_KEY`, `GODADDY_API_SECRET` | https://developer.godaddy.com/keys (recomendado: empezar con OTE base URL para pruebas). |
| `GODADDY_BASE_URL` | `https://api.ote-godaddy.com` (sandbox) o `https://api.godaddy.com` (prod). |

### Telegram
| Variable | Cómo obtenerlo |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Crea el bot con [@BotFather](https://t.me/BotFather) → te entrega un token. |
| `TELEGRAM_AUTHORIZED_USER_IDS` | Tu user_id Telegram (numérico). Lo obtienes con bots como [@userinfobot](https://t.me/userinfobot). |

### LangSmith (opcional)
| Variable | Cómo obtenerlo |
| --- | --- |
| `LANGSMITH_API_KEY`, `LANGSMITH_PERSONAL_ACCESS_TOKEN`, `LANGSMITH_PROJECT` | Crear cuenta en https://smith.langchain.com y generar API key. |

### Sandbox OpenShell (opcional)
| Variable / Acción | Cómo obtenerlo |
| --- | --- |
| `ENABLE_OPENSHELL_SANDBOX=true` | Solo si quieres ejecutar código aislado. |
| Vendor en `experiments/openshell-deepagent/vendor/openshell-deepagent` | `git clone --depth 1 https://github.com/langchain-ai/openshell-deepagent ...` (ver `OPENSHELL_SANDBOX.md`). |
| `OPENSHELL_GATEWAY_URL` | URL local del gateway si arrancas el vendor. |
| `NVIDIA_API_KEY` | Solo si el vendor lo necesita; queda placeholder por defecto. |

### Capacidades pendientes (variables reservadas, integración no implementada)
- **YouTube**: `YOUTUBE_API_KEY` → no hay extractor implementado.
- **Microsoft Mail**: `MICROSOFT_MAIL_ENABLED` (flag) → sin executor real.
- **Notion / cuentas externas**: variables presentes pero sin pipeline en backend.

---

## 16. Operación día a día

### Ingesta de PDFs

```bash
bash scripts/ingest_now.sh /ruta/al/documento.pdf
```

o panel `Documents` → pega ruta absoluta visible al backend → `job_id`.

### Backups

```bash
bash scripts/backup_postgres.sh
bash scripts/backup_neo4j.sh
bash scripts/backup_storage.sh
# o
bash scripts/backup_all.sh
```

Salidas en `backups/` con `.sha256`.

### Restore (todos exigen `CONFIRM_RESTORE=YES`)

```bash
CONFIRM_RESTORE=YES bash scripts/restore_postgres.sh backups/postgres/ARCHIVO.dump
CONFIRM_RESTORE=YES bash scripts/restore_neo4j.sh backups/neo4j/neo4j_TIMESTAMP/neo4j.dump
CONFIRM_RESTORE=YES bash scripts/restore_storage.sh backups/storage/ARCHIVO.tar.gz
```

### Monitorización

- Panel `Health` o `GET /health/dashboard` → estado por componente y latencia.
- Panel `Jobs` o `GET /jobs/{id}/events` → eventos detallados de cada job.
- Panel `Audit` o `GET /audit/events` → trazabilidad.
- `LANGSMITH_TRACING=true` → trazas externas si quieres.

### Beat (jobs periódicos)

`bash scripts/dev_beat.sh` lanza Celery beat con: consolidación diaria de memoria DeepAgents, cleanup de jobs > 30 días, reaper de `action_requests` colgados en `running`, sync de mail personal si `MAIL_ENABLED=true`, digest Telegram Gmail si está activo.

---

## 17. Troubleshooting común

| Síntoma | Probable causa | Acción |
| --- | --- | --- |
| `checkpointer_postgres_unavailable_fallback_memory` | Postgres no arrancó / `DATABASE_URL` mal / migraciones no aplicadas | `bash scripts/dev_up.sh` y `uv run alembic upgrade head` |
| `retrieve_context_unavailable` | Weaviate down o embeddings sin credenciales | `GET /health/dashboard`; revisa `WEAVIATE_*` y `EMBEDDINGS_*` |
| Chat responde "sin evidencia" | RAG no encontró nada relevante | Verifica que el doc esté ingerido (`Documents`); prueba con query más específica |
| Job estancado en `running` | Worker murió | Reinicia con `bash scripts/dev_worker.sh`; el reaper Celery cierra los stuck > N min |
| `OpenShellPolicyViolation` | Tarea pidió acción bloqueada por policy | Revisa `args_redacted` en audit y ajusta input |
| `openharness_research_fallback` en logs | El bridge OH falló (timeout, RuntimeError, error de red) | Mira `error` en el log; el grafo siguió con DeepAgent + fallback igual |
| `openharness_query_timeout` | OH excedió `OPENHARNESS_QUERY_TIMEOUT_SECONDS` | Sube el timeout o cambia preset a `minimal` |
| Mail sync no trae mensajes | `MAIL_ENABLED=false`, credenciales GoDaddy incompletas, carpeta mal escrita o Gmail OAuth apagado | Revisa `GET /mail/status`, logs de worker queue `mail`, `MAIL_GODADDY_*`, `MAIL_GMAIL_LABEL` |
| Botón `Aprobar y enviar` falla | Falta SMTP GoDaddy o la propuesta está vacía | Edita propuesta, verifica `MAIL_DEFAULT_SENDER`, usuario SMTP y `MAIL_REQUIRE_APPROVAL_FOR_SEND=true` |
| Frontend devuelve 401 | JWT inválido o expirado | Genera otro y pégalo en `Settings` |
| `reject_changeme_in_production` impide arrancar | Hay secretos `CHANGEME` en prod | Reemplaza con secretos reales antes de poner `ENVIRONMENT=production` |

---

## 18. Roadmap

Lo que **funciona hoy** (verificado contra código y tests):

- Backend completo (92 endpoints propios; 118 REST totales) + frontend (18 vistas, incluye `Assist` y `Google Ops`).
- Ruta `research` con fusión opcional OpenHarness y fallback determinista.
- Ruta `legal` con Document Analysis y exportadores.
- Action Plane con `computer_organize`, `document_generate`, `browser_preview`, `browser_interactive`, Google Calendar create y Drive upload ejecutables sólo por `ActionRequest` aprobado; Maps read-only con tráfico/link; Gmail digest read-only; mail GoDaddy IMAP/SMTP con envío aprobado; GoDaddy DNS preview/executor con dry-run.
- Memoria DeepAgents con propuestas + aprobación + episódica.
- Bot Telegram con 25+ comandos.
- Research Orchestrator multi-subtarea con SSE y cancelación.
- QA reproducible actual: `uv run pytest -m 'not integration and not slow'` → 484 passed, 1 skipped, 20 deselected; ruff/ruff format/mypy/frontend lint/build verdes.

Lo que **falta** para llegar a "asistente personal absoluto" (detalle en [`PERSONAL_ASSISTANT_ROADMAP.md`](./PERSONAL_ASSISTANT_ROADMAP.md)):

| Brecha | Variables reservadas | Estado |
| --- | --- | --- |
| **Memoria personal temporal y semántica** (perfil, hábitos, decisiones expirables) | DeepAgents memory (extender) | Base lista, falta capa de perfil/expiración. |
| **Correo multi-cuenta completo** (Gmail send/drafts aprobados, Microsoft, acciones mailbox) | `GMAIL_SEND_ENABLED`, `MICROSOFT_MAIL_ENABLED`, `MAIL_*` | Primer corte fuerte listo: GoDaddy IMAP/SMTP, Gmail label `TODOS` si OAuth activo, propuestas escritas y envío aprobado desde GoDaddy. Falta Gmail send/drafts, Microsoft y acciones de archivo/label. |
| **Web grounding avanzado** (paneles de coste, cross-check sintético, presupuestos) | Multi-provider web search | Base multi-provider lista; falta UI/telemetría. |
| **Navegación completa** (Camoufox real, recorder/replay, login con secret manager) | `BROWSER_AUTOMATION_PROVIDER=camoufox` | Camoufox como flag; provider real falta. |
| **Agenda/tareas/recordatorios reales** (Google Calendar, scheduler, push) | Personal Assistant API (tasks/notes); `ENABLE_GOOGLE_CALENDAR`, `ENABLE_PERSONAL_REMINDER_DELIVERY` | Tasks/notes funcionando; Calendar list/create operativo bajo OAuth y aprobación. Falta scheduling/push proactivo completo. |
| **Notas semánticas con búsqueda** | Schemas listos | Indexación y búsqueda Weaviate ya implementadas; falta export/import y relación nota↔memoria↔tarea. |
| **Audio/voz** (STT/TTS) | `ELEVENLABS_*`, `OPENAI_AUDIO_*` | Endpoint STT/TTS ElevenLabs implementado; falta UX completa de voz en frontend/Telegram. |
| **YouTube/video** (transcripts, frame analysis) | `YOUTUBE_API_KEY` | Sin pipeline. |
| **Adaptador MCP/skills externos** | DeepAgents skill registry extensible | Skills core/user listas, falta importador MCP. |
| **IDE/repo agent** (modo proyecto, edición y testeo controlados) | OpenShell sandbox | Sandbox listo, flujo end-to-end no. |

Cada nueva capacidad debe traer: flag de configuración, provider fake para tests, tests unitarios + endpoint si aplica, redacción de secretos, `audit_event`, doc en `ACTION_PLANE.md` o guía dedicada y degradación clara (`blocked`, no excepción 500) cuando faltan credenciales.

---

## Apéndice A — Documentos hermanos

- [`ARCHITECTURE.md`](./ARCHITECTURE.md): wiring técnico, nodos del grafo, fallos y degradación.
- [`PROJECT_GUIDE.md`](./PROJECT_GUIDE.md): explicación corta y dual (simple + técnica).
- [`OPENHARNESS_FUSION.md`](./OPENHARNESS_FUSION.md): contrato exacto OpenHarness + LangGraph + DeepAgents.
- [`DEEPAGENTS_INTEGRATION.md`](./DEEPAGENTS_INTEGRATION.md): tools, policy, depuración del DeepAgent.
- [`DEEPAGENTS_SKILLS_MEMORY.md`](./DEEPAGENTS_SKILLS_MEMORY.md): skills + memoria + propuestas.
- [`DOCUMENT_ANALYSIS_AGENT.md`](./DOCUMENT_ANALYSIS_AGENT.md): subagente legal y modos.
- [`ACTION_PLANE.md`](./ACTION_PLANE.md): browser/computer/Gmail/Google/mail personal/GoDaddy/documents.
- [`OPENSHELL_SANDBOX.md`](./OPENSHELL_SANDBOX.md): sandbox vendor opcional.
- [`SECURITY.md`](./SECURITY.md): reglas obligatorias (incluye OpenHarness).
- [`RUNBOOK.md`](./RUNBOOK.md): operación diaria completa.
- [`OPERATOR_VARIABLE_CHECKLIST.md`](./OPERATOR_VARIABLE_CHECKLIST.md): mapeo ENV ↔ Settings + procedimiento operador.
- [`SETTINGS_REGISTRY_TABLE.md`](./SETTINGS_REGISTRY_TABLE.md): tabla generada (no editar a mano).
- [`PERSONAL_ASSISTANT_ROADMAP.md`](./PERSONAL_ASSISTANT_ROADMAP.md): roadmap de capacidades pendientes.
- [`IMPROVEMENT_EXECUTION_PLAN.md`](./IMPROVEMENT_EXECUTION_PLAN.md): mejoras continuas de configuración y docs.

---

## Apéndice B — Comandos rápidos para "lo quiero ahora"

```bash
# Levantar todo en local
bash scripts/init_env.sh && bash scripts/dev_up.sh
cd backend && uv run alembic upgrade head && uv run uvicorn cognitive_os.api.app:app --reload &
bash scripts/dev_worker.sh &
cd frontend && npm ci && npm run dev

# Ingestar un PDF
bash scripts/ingest_now.sh /ruta/al/pdf

# Activar OpenHarness en research
cd backend && uv sync --extra openharness
echo "ENABLE_OPENHARNESS_RESEARCH=true" >> ../.env
# (re-arrancar API)

# Bot Telegram
echo "TELEGRAM_ENABLED=true" >> .env
echo "TELEGRAM_BOT_TOKEN=..." >> .env
echo "TELEGRAM_AUTHORIZED_USER_IDS=123456789" >> .env
cd backend && uv run python -m cognitive_os.integrations.telegram_bot

# QA reproducible antes de promover
bash scripts/full-qa.sh
```

---

**Si solo lees una sección, lee la §5 ("El recorrido completo de una petición") y la §11 ("Action Plane"). Esas dos te dan la imagen completa de cómo Cognitive OS combina inteligencia, política y trazabilidad.**

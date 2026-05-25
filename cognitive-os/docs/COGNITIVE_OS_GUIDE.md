# Cognitive OS — Guía Maestra

> **Estado canónico actual (2026-05-23, commit `bbaaea8`):**
> **RELEASE APPROVED** — cuatro pasadas de auditoría independiente
> cerradas con cero defectos conocidos. Esta guía describe el sistema
> vivo después de:
>
> 1. Ciclos de hardening de frontend, mail, QA aislado y runtime local.
> 2. Doble auditoría TestSprite del 2026-05-23 que cazó un P1
>    (`MissingGreenlet` en `/actions/*/preview/request`) y eliminó la
>    fricción del Playwright runner con auto-mint JWT.
> 3. Tercera pasada de endurecimiento (LLM probe timeout específico,
>    race guard `full-qa`, anti-flake Ctrl+K, regression-critical
>    aceptar `degraded`).
> 4. Cuarta pasada de cierre absoluto: validación de 30 puntos
>    cero-fricción, 25 escenarios de degradación, 25 de idempotencia, 30
>    de UX comercial, drift sweep + bulk-fix, 17 documentos nuevos de
>    evidencia (18-34).
>
> Fuente corta: `docs/CURRENT_STATE.md`. Modelo operativo:
> `docs/ZERO_FRICTION_OPERATING_MODEL.md`. Cierre formal:
> [`audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md`](audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md).
>
> **Prioridad del producto en este PC dedicado:** fricción casi nula por
> sobre seguridad estricta. Cognitive OS está diseñado para usar el perfil
> real del operador, Edge real/Kimi WebBridge, filesystem local y
> auto-resolución de aprobaciones cuando el perfil `dedicated_local/full`
> lo permite. La seguridad tipo SaaS no es prioridad en esta instalación.
> Lo que sí sigue siendo no negociable es trazabilidad, diagnóstico,
> idempotencia, recuperación y no fallar en silencio.
>
> **Excepción dura de correo:** el flujo normal de mail **lee y redacta
> propuestas**, pero no crea drafts ni envía mensajes. Solo puede enviar si
> Diego lo pide de forma absolutamente explícita y además están activados
> `ENABLE_EMAIL_SEND=true`, `MAIL_ALLOW_EXPLICIT_SEND=true` y la request
> incluye `explicit_send_confirmation="SEND_THIS_EMAIL_EXPLICITLY"`.
>
> **Snapshot verificado** (conteos generados por
> `scripts/sync_doc_counts.py`): backend FastAPI con **147 decoradores
> REST**, **23 tareas Celery** en **5 colas** (`default`, `ingestion`,
> `agent_longrun`, `maintenance`, `mail`) con hasta **13 jobs beat**, **20
> migraciones Alembic** (head `202605200003`), frontend Next.js 16.2.6 con
> **20 vistas**, Telegram con **37 slash commands** (dispatch fail-closed),
> `/health/dashboard` con **18 componentes** + `POST /health/verify` para
> probe real. Mail: Gmail `diegomanzurn@gmail.com` `TODOS` + `SPAM`,
> GoDaddy `diego@doctormanzur.com` `Spam`, clasificación de spam por
> agente, digest 10:00/20:00 Chile, máximo 50 correos, respuestas sugeridas
> como campos de texto separados.
>
> **QA más reciente (rama `codex/commercial-zero-friction-hardening`):**
> `bash scripts/full-qa.sh` verde con **958 passed**, 1 skipped, 28 deselected
> (944 históricos + 14 nuevos: 3 `eager_defaults`, 3
> `health_llm_probe_timeout` y 3 guards QA/scripts/docs),
> ruff/format/mypy/Alembic/lint/build/`sync_doc_counts --check`/`git
> diff --check` OK; build frontend aislado con `NEXT_DIST_DIR=.next-qa`;
> Playwright **41 passed** sin exportar `COGOS_JWT` (auto-mint via
> `_global-setup.ts`); `bash scripts/stress-qa.sh` verde con 3 pasadas
> de **958 passed**; carril opt-in `tests/live/` verificado con **8
> passed**; TestSprite completo corregido en batches locales **28/28
> passed**.
>
> **Ajustes post-gate acumulados:**
> - `647f103` (re-audit): `eager_defaults=True` en `db.Base` corrige
>   `MissingGreenlet` 500 en endpoints `POST /actions/*/preview/request`;
>   Playwright runner zero-friction.
> - `5953b40`: `/system/mcp` carga inventario en paralelo con timeout
>   default 30s (`MCP_INVENTORY_TIMEOUT_SECONDS`); runtime verificado
>   inicialmente 5/5 servers y 67 tools. Estado actual tras `time`
>   (2026-05-25): 6/6 servers y 69 tools. `Ctrl/Cmd+K` del cockpit
>   estabilizado desde capture phase.
> **Para qué es este documento:** la **guía maestra técnica** "desde cero". Complementa la `USER_GUIDE.md` (orientada a operación cotidiana) con arquitectura detallada, mail multicuenta, escritorio, credenciales y troubleshooting profundo. Cada afirmación tiene su archivo o variable de respaldo en el repo.

---

## Tabla de contenidos

1. [Qué es Cognitive OS (en una frase y en palabras simples)](#1-qué-es-cognitive-os)
2. [Para qué sirve y para qué NO sirve](#2-para-qué-sirve-y-para-qué-no-sirve)
3. [Casos de uso concretos](#3-casos-de-uso-concretos)
4. [Mapa mental: cómo encajan las piezas](#4-mapa-mental-cómo-encajan-las-piezas)
5. [El recorrido completo de una petición](#5-el-recorrido-completo-de-una-petición)
6. [Componentes del backend, uno por uno](#6-componentes-del-backend-uno-por-uno)
7. [Frontend: las 20 vistas y cómo usar cada una](#7-frontend-las-20-vistas-y-cómo-usar-cada-una)
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
Cognitive OS es un **sistema operativo cognitivo local-first y auditable** que coordina LLMs, agentes y herramientas para investigar, analizar documentos con citas, recordar lo aprobado, preparar acciones reales (navegador, archivos, correo, DNS, documentos Office) y ejecutar tareas largas en background, **sin entregar el control a un solo modelo**. En el perfil actual `dedicated_local/full`, la prioridad es cero fricción: muchas acciones locales o de Google pueden auto-resolverse si están configuradas; en `strict`, vuelven a requerir aprobación humana. Mail queda fuera de esa relajación: no se envía ni se crean drafts salvo instrucción explícita de Diego.

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

Todo corre en tu infraestructura (Docker local), las acciones quedan auditadas en Postgres, los secretos no se loguean, y el comportamiento exacto depende del perfil operativo: `strict` prioriza compuertas humanas; `dedicated_local/full` prioriza velocidad y uso del PC real del operador. La obligación transversal es que el sistema diga qué hizo, por qué falló y cómo reintentarlo.

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
| Revisar correo personal multicuenta, resumir últimos 50, clasificar spam por agente y proponer respuestas importantes como texto | `/mail/*` + Gmail `TODOS`/`SPAM` + GoDaddy `Spam` |
| Planificar rutas con tráfico y link navegable | Action Plane → Google Maps `route` |
| Crear eventos Calendar, subir entregables y organizar Drive con aprobación | Google Ops + `ActionRequest` (`calendar_create_event`, `drive_upload_file`, `drive_organize_files`) |
| Preparar cambios DNS en GoDaddy con dry-run, allow-list y aprobación | Action Plane → GoDaddy `dns/preview` + `request` |
| Coordinar **investigación multi-subtarea con presupuesto y SSE** | Research Orchestrator (`/research/runs`) con cancelación y eventos |
| Operar todo desde Telegram (móvil) | Bot opcional con 37 comandos slash |
| Trazar runs en LangSmith (cuando se quiere observabilidad nube) | `/langsmith/*` |
| Grabar memoria episódica (qué hizo el agente y cuándo) | `POST /deepagents/memory/episodic` |

### NO sirve para…

| No haces esto con Cognitive OS | Por qué |
| --- | --- |
| Enviar correos automáticamente | No. El flujo normal nunca crea drafts ni envía. SMTP GoDaddy queda como escape hatch solo si Diego pide explícitamente un envío y se habilitan `ENABLE_EMAIL_SEND=true` + `MAIL_ALLOW_EXPLICIT_SEND=true` + confirmación por request. |
| Publicar en redes sociales | `enable_social_posting=false` por defecto; no hay executor de redes implementado. |
| Cambiar DNS sin aprobación humana | Flujo `dry-run` por defecto, allow-list de dominios y aprobación obligatoria. |
| Dar acceso a tu navegador real con tu sesión | En `strict`, `browser_preview/interactive` corre aislado/headless/allow-listed. En `dedicated_local/full`, Edge DevTools puede usar el Edge real del operador en este PC dedicado. |
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

4. **"Quiero revisar mi correo importante y recibir respuestas sugeridas."**
   1. En `Mail`, ejecutas `Generar resumen 50` o dejas Celery beat con `MAIL_ENABLED=true`.
   2. El sistema lee Gmail `TODOS`/`SPAM` y GoDaddy `Spam`; no confía en la carpeta, clasifica con el agente.
   3. El digest excluye solo lo que el agente marca como `spam`.
   4. Los correos importantes reciben propuesta de respuesta en un campo de texto separado.
   5. No hay drafts ni auto-send. Diego copia y envía manualmente salvo petición explícita futura.

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
│  Frontend       │                │ FastAPI app (150 endpoints REST)        │
│  Next.js 16     │ ─── REST/SSE ──│  /chat /chat/stream /threads/*          │
│  20 vistas      │ ◄── JWT ───────│  /documents/* /document-analysis/*      │
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

150 endpoints REST (147 `@app.*` + 3 `@router.*` del test_fixtures router) agrupados por dominio, verificados contra `backend/src/cognitive_os/api/app.py` el 2026-05-25 (conteo generado por `scripts/sync_doc_counts.py`). Incluye los endpoints `/deepagents/learning/*` del plan de aprendizaje (scorecard, skill-promotions, reflection) y los dispatchers de mail (`/mail/sync/dispatch`, `/mail/digest/dispatch`). Catálogo resumido de rutas reales del código, todas requieren JWT excepto `/health`:

#### Salud y configuración
- `GET /health` — público, devuelve `{status: "ok"}`.
- `GET /health/dashboard` — 18 componentes (Postgres/Redis/Weaviate/Neo4j/LLMs/Embeddings/Workers/Voice/Maps/Calendar/Drive/Kimi/Captcha/Mail/MCP/`operational_backlog`/Checkpointer) con latencia. El overall distingue `ok` de `configured` (cableado pero sin probe en vivo).
- `POST /health/verify` — health check LIVE bajo demanda del operador: hace una completion LLM mínima, un embedding real y un login IMAP. Convierte los `configured` en `ok` verificados.
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
- `GET/POST /actions/calendar/status|events|freebusy|events/create|events/request`.
- `GET/POST /actions/drive/status|files|files/upload|files/upload/request|folders/ensure|folders/ensure/request|organize/preview|organize/request`; `GET /actions/drive/files/{file_id}`.
- `GET/POST /actions/godaddy/status|dns/preview|dns/request`.
- `GET/POST /actions/documents/status|preview|request`.
- `GET /actions/requests`, `GET /actions/requests/{id}`, `POST /actions/requests/{id}/dispatch|cancel`.

#### Mail personal GoDaddy/Gmail-label
- `GET /mail/status` — cuentas y flags no sensibles.
- `POST /mail/sync` — sincronización directa legacy GoDaddy IMAP + Gmail; no es el camino preferido de UI.
- `POST /mail/sync/dispatch` — encola sync en Celery queue `mail`; camino preferido de UI para no bloquear el navegador.
- `POST /mail/digest/preview` — genera digest desde mensajes locales, resume los últimos 50 y devuelve respuestas propuestas separadas, sin drafts/sends. La UI lo llama con `sync_first=false`.
- `POST /mail/digest/dispatch` — encola digest programado/manual en Celery queue `mail`.
- `GET /mail/messages`, `GET /mail/messages/{id}` — mensajes persistidos y propuestas.
- `PATCH /mail/messages/{id}/reply` — edita la propuesta escrita.
- `POST /mail/messages/{id}/ignore` — ignora un mensaje.
- `POST /mail/messages/{id}/approve-send` — escape hatch SMTP; bloqueado salvo flags y confirmación explícita.

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
| `plan_route` / `geocode_address` | Google Maps read-only con rutas/tráfico y geocoding |
| `list_calendar_events` / `check_calendar_freebusy` | Google Calendar read-only |
| `search_drive_files` / `preview_drive_organization` | Google Drive read-only/preview, sin writes directos |

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
- **Calendar**: listar eventos, consultar free/busy y crear eventos por `ActionRequest` aprobable (`calendar_create_event`).
- **Drive**: listar/get, asegurar carpeta de entregables, subir archivos allow-listed y organizar archivos por `ActionRequest` (`drive_upload_file`, `drive_organize_files`).
- **GoDaddy**: DNS preview + executor real con dry-run, allow-list, aprobación.
- **Documents**: DOCX/XLSX/PPTX con guardrails de paths, tamaño, assets allow-listed, fórmulas XLSX no inyectables.
- **Mail personal**: Gmail `TODOS`/`SPAM` + GoDaddy `Spam`, propuestas escritas, sin drafts ni envío normal.

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

## 7. Frontend: las 20 vistas y cómo usar cada una

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
| **Mail** | Digest personal GoDaddy/Gmail | Resumen últimos 50, clasificación propia, propuestas de texto; sin drafts ni envío normal |
| **Google Ops** | Operación Google Maps/Calendar/Drive | Calculas rutas con tráfico/link, creas requests aprobables de eventos Calendar y subes entregables a Drive |
| **LangSmith** | Trazas/proyectos/runs externos | Solo si `LANGSMITH_TRACING=true` y endpoints disponibles |
| **Agents** | Estado de agentes | Resumen `/agents`: políticas, recientes, capacidades |
| **Skills** | Skills DeepAgents | Listadas core + user; ves definición y `risk_level` |
| **Health** | Componentes y latencias | `/health/dashboard` (18 componentes), botón "Verificar en vivo" → `POST /health/verify`, tile "Backlog operacional" |
| **Audit** | Auditoría | `/audit/events` con filtros |

> En desarrollo, `NEXT_PUBLIC_API_BASE_URL` define la URL inicial del API; en runtime, `Settings` permite cambiarla sin rebuild.
> El JWT se guarda en `localStorage` bajo `cogos.token`. El riesgo XSS se
> asume aceptable en un cockpit local mono-operador sin scripts de terceros
> (decisión consciente — ver `FRONTEND_ARCHITECTURE.md §8`).

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

Los **37 slash commands** (paridad real frente a la consola; el test
`test_every_view_has_at_least_one_slash_command` mantiene ambas superficies
sincronizadas):

| Comando | Para qué | Ejemplo |
| --- | --- | --- |
| `/start`, `/help` | Bienvenida + lista de comandos | `/help` |
| `/health` | Resumen healthy/degraded de componentes | `/health` |
| `/stats` | Knowledge stats (docs/pages/chunks/jobs/approvals) | `/stats` |
| `/config` | Flags no sensibles | `/config` |
| `/capabilities` | Estado de cada capacidad del Action Plane | `/capabilities` |
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
| `/reset` | Inicia un thread de conversación nuevo | `/reset` |
| `/ingest <ruta>` | Encola un PDF (ruta visible para el backend) | `/ingest /home/me/docs/contrato.pdf` |
| `/runs` | Runs recientes en LangSmith (si está activo) | `/runs` |
| `/tasks` | Lista tus personal tasks | `/tasks` |
| `/task <título \| desc>` | Crea una tarea personal | `/task Llamar a Andrea \| pendiente del lunes` |
| `/done <id>` | Marca tarea como done | `/done 90f…` |
| `/notes` | Lista notas personales (Markdown) | `/notes` |
| `/note <título \| body>` | Crea una nota | `/note Recordatorio reunión \| traer las cifras Q3` |
| `/gmaildigest` | Digest Gmail read-only inmediato | `/gmaildigest` |
| `/maps <origen \| destino>` | Ruta read-only con tráfico/ETA | `/maps Las Condes \| Providencia` |
| `/calendar [max]` | Próximos eventos de Google Calendar | `/calendar 5` |
| `/freebusy [días]` | Ventanas ocupadas read-only | `/freebusy 3` |
| `/drive <query>` | Busca archivos en Google Drive | `/drive contrato 2025` |
| `/documents [max]` | Documentos Office generados | `/documents` |
| `/audit [max]` | Eventos de auditoría recientes | `/audit 20` |
| `/mail [max]` | Digest de correo personal (read-only) | `/mail` |
| `/research [max]` | Runs del research orchestrator | `/research` |
| `/codebuild [max]` | Builds del Code Director | `/codebuild` |
| `/sandbox` | Estado del sandbox OpenShell | `/sandbox` |

En `dedicated_local`, un mensaje **sin** slash entra al orquestador como un
turno de `/chat` con thread persistente. Cada comando respeta sus feature
flags (Maps/Calendar/Drive status, `MAIL_ENABLED`, `ENABLE_OPENSHELL_SANDBOX`,
etc.) y reporta `disabled`/`blocked` en vez de fallar en silencio.

### Mapas (chat ↔ user)

- **`TELEGRAM_ASSIST_USER_MAP`**: pares `chat_id:user_id_api` para que `/tasks` y `/notes` se asocien a un `user_id` real del API.
- **`TELEGRAM_REMINDER_CHAT_MAP`**: pares `user_id_api:chat_id` para entrega de recordatorios proactivos (requiere `ENABLE_PERSONAL_REMINDER_DELIVERY=true`).
- **`TELEGRAM_GMAIL_DIGEST_CHAT_IDS`**: chats que reciben el digest automático diario; vacío ⇒ todos los `TELEGRAM_AUTHORIZED_USER_IDS`.

### Reglas de seguridad del bot

- **Dispatch fail-closed (AUDIT-2026-A):** solo responde a IDs en
  `TELEGRAM_AUTHORIZED_USER_IDS`. Una allowlist **vacía** rechaza a *todos*
  (no a nadie); además `main()` se niega a arrancar el bot con la allowlist
  vacía y lo dice en el log, en vez de quedar un bot vivo pero inútil.
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
- `drive_ensure_folder` y `drive_organize_files` (Drive folder/organización por `ActionRequest`, sin deletes ni cambios de permisos).
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

- **Skills core**: `backend/src/cognitive_os/deepagents/skills/core/` (13 SKILL.md). No se modifican desde fuera.
- **Skills user**: `storage/deepagents/skills/user/<user_id>/<skill_name>/SKILL.md`. Validadas, no pueden activar tools peligrosas por defecto. Las skills auto-promovidas por Fase B viven en `storage/deepagents/skills/user/_auto/<slug>/SKILL.md`.
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

- **Plan de aprendizaje autónomo (Fases A-E, `AGENT_LEARNING_PLAN.md`)**: el
  agente acumula capacidad sin tocar su system prompt. Fase A distila jobs
  exitosos en recetas (`kind=procedure`); Fase B promueve procedures usados a
  skills YAML con rollback automático; Fase C arma un scorecard de
  confiabilidad por tool; Fase D detecta patrones fallo→recuperación y propone
  warnings; Fase E es la reflexión nocturna con evidencia literal obligatoria.
  Todo pasa por el approval gate del operador, con **una única excepción
  acotada**: Fase D auto-promueve un *warning* (texto de contexto, nunca una
  acción) tras N detecciones del mismo patrón. Esa excepción tiene kill
  switch: `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED=false` fuerza toda warning
  por la puerta de aprobación. El panel `MemoryView` muestra el estado del
  flag y un badge en los registros auto-promovidos.

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
cd frontend && PORT=3001 npm ci && npm run dev    # http://localhost:3001 (3000=OpenChamber)

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
bash scripts/full-qa.sh       # uv sync --extra openharness + pytest + ruff + format + mypy + npm ci + lint + build + sync_doc_counts --check + git diff --check
bash scripts/stress-qa.sh     # repite pytest N veces (default 3) para detectar flakiness
bash scripts/full-qa-live.sh  # opt-in: smokes read-only contra proveedores reales (LIVE_TESTS_ENABLED=1)
```

Snapshot historico (commit `647f103`): `full-qa.sh` → **950 passed**, 1
skipped, 28 deselected; `stress-qa.sh 3` → 3 pasadas de 950; Playwright
**31 passed** sin exportar `COGOS_JWT` (auto-mint via
`_global-setup.ts`); `full-qa-live.sh` con `LIVE_TESTS_ENABLED=1` →
**8 passed**; TestSprite MCP re-audit → **10/10 passed** sobre dos
batches acotados.

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
| Mail personal | `MAIL_ENABLED`, `MAIL_DEFAULT_SENDER`, `MAIL_REQUIRE_APPROVAL_FOR_SEND`, `MAIL_ALLOW_EXPLICIT_SEND`, `MAIL_BACKGROUND_SYNC_ENABLED`, `MAIL_POLL_INTERVAL_SECONDS`, `MAIL_IMAP_TIMEOUT_SECONDS`, `MAIL_SMTP_TIMEOUT_SECONDS`, `MAIL_FETCH_MAX_PER_FOLDER`, `MAIL_GMAIL_MONITOR_LABELS`, `MAIL_DIGEST_*`, `MAIL_GODADDY_*` |
| GoDaddy | `GODADDY_ENABLED`, `GODADDY_BASE_URL`, `GODADDY_API_KEY`, `GODADDY_API_SECRET`, `GODADDY_ALLOWED_DOMAINS`, `GODADDY_DNS_DRY_RUN_ONLY`, `GODADDY_ALLOW_PRODUCTION_WRITES`, `GODADDY_MAX_REQUESTS_PER_MINUTE` |
| Kimi WebBridge | `ENABLE_KIMI_WEBBRIDGE`, `KIMI_WEBBRIDGE_URL` (solo localhost), `KIMI_WEBBRIDGE_ALLOWED_DOMAINS`, `KIMI_WEBBRIDGE_ALLOW_MUTATIONS`, `KIMI_WEBBRIDGE_REQUIRE_APPROVAL`, `KIMI_WEBBRIDGE_REQUEST_TIMEOUT_SECONDS` |
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

Fases 44-49 refuerzan esta capa: Maps devuelve `route_advice`, ETA, severidad de
tráfico y alternativas; Drive busca por nombre, contenido indexado (`fullText`)
o ambos sobre `Mi unidad`/`allDrives`, y la carpeta de entregables puede
crearse como `ActionRequest` `drive_ensure_folder` aprobable antes de subir
archivos. Drive upload acepta entregables generados bajo `DOCUMENT_OUTPUT_ROOT`,
`LOCAL_STORAGE_DIR/workspaces`, `OPENSHELL_ALLOWED_OUTPUT_DIR` o
`COMPUTER_ALLOWED_ROOTS`; la organización usa preview + `drive_organize_files`
aprobable y solo mueve archivos con `files.update`. Calendar suma `freebusy`
read-only para detectar ventanas ocupadas.

#### Por qué las credenciales de Google Cloud Console **no bastan** por sí solas

Una pregunta natural: si pegaste `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y
`GOOGLE_MAPS_API_KEY` desde tu proyecto Google Cloud (con Maps API, Drive API
y Calendar API habilitadas), ¿por qué Calendar/Drive aún aparecen como
bloqueados en `/health/dashboard`?

Porque OAuth 2.0 tiene **tres piezas distintas** y tu proyecto Cloud sólo
cubre dos:

1. **API Key Maps** (`GOOGLE_MAPS_API_KEY`) → Maps no usa OAuth. Auth es por
   clave de proyecto. **Funciona apenas la pegas en `.env`.**
2. **OAuth Client ID + Secret** (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)
   → Identifican a Cognitive OS como aplicación legítima ante Google.
   Vienen de tu Cloud Console.
3. **`token.json`** → Es el **consentimiento del usuario** (tú, dueño del
   calendario/Drive) autorizando a esta app específica a leer/escribir en
   tus datos. Sólo Google puede emitirlo, y sólo después de que tú apruebes
   en una pantalla de consentimiento en el navegador.

```
   Cloud Console te da:     ──┐
   - CLIENT_ID                │  "Cognitive OS existe como app"
   - CLIENT_SECRET            │
   - APIs habilitadas       ──┘
                                            │
                                            ▼
                              No alcanza para leer tus datos.
                                            │
                                            ▼
   Browser consent te da:   ──┐
   - access_token             │  "diegomanzurn@gmail.com permitió a
   - refresh_token            │   Cognitive OS leer SU calendar/drive"
   (en token.json)          ──┘
```

Razón de diseño: si bastara con el `CLIENT_SECRET`, cualquier desarrollador
con esas credenciales podría leer el Drive de cualquier persona. El
`token.json` prueba criptográficamente que **tú** autorizaste a **esta app**
para acceder a **tus** datos.

#### Cómo completar la autorización (una vez en toda la vida del deployment)

```bash
cd cognitive-os/backend
uv run python scripts/auth_google.py
```

Lo que ocurre paso a paso:

1. El script lee `GOOGLE_CLIENT_ID/SECRET` de `.env` y los scopes
   configurados en `GOOGLE_CALENDAR_SCOPES` / `GOOGLE_DRIVE_SCOPES`. El
   valor vigente de `GOOGLE_CALENDAR_SCOPES` es
   `https://www.googleapis.com/auth/calendar` (acceso completo: cubre
   `list_events`, `create_event` **y** `freebusy`). El scope `calendar.events`
   por sí solo NO autoriza la consulta free/busy — usarlo devuelve
   `HTTP 403 ACCESS_TOKEN_SCOPE_INSUFFICIENT`.
2. Abre tu navegador en una URL de Google con esos scopes.
3. Google muestra: *"Cognitive OS quiere acceder a tu Calendar y Drive —
   ¿Permitir?"* (con tu cuenta logueada). Click "Permitir".
4. El script captura el `refresh_token` que Google genera y lo guarda en
   `storage/oauth/google/token.json` con permisos `0o600`.
5. A partir de ese momento, `GoogleCredentialsLoader` refresca el
   `access_token` automáticamente cada hora usando el `refresh_token`.

Si vuelves a correr `scripts/auth_google.py` cuando el token todavía es
válido, el script **detecta que ya está autorizado**, refresca
silenciosamente y sale sin abrir el navegador. Sólo verás la pantalla de
consentimiento si:

- Es la primera vez en este host.
- Revocaste manualmente el acceso desde
  [myaccount.google.com/connections](https://myaccount.google.com/connections).
- Cambiaste los scopes que el backend pide (ej. agregaste write).

#### Gmail OAuth es separado (mismo principio)

`GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` están en `.env` como pareja
distinta históricamente, **pero puedes reutilizar el mismo OAuth client de
Google** si tu proyecto Cloud ya tiene Gmail API habilitada — basta con
copiar los valores de `GOOGLE_CLIENT_ID/SECRET` también a esas dos
variables. Luego corres el quickstart oficial para generar
`GMAIL_TOKEN_DIR/token.json` con scope `gmail.readonly`.

#### Diagnóstico rápido

| Síntoma | Causa | Acción |
|---|---|---|
| `/health/dashboard` muestra `google_calendar` o `google_drive` como `blocked` con `No token.json found; run scripts/auth_google.py once.` | Falta el `token.json`. | Corre `auth_google.py`. |
| Mismo, pero el detail menciona `refresh failed` | Token revocado o scopes nuevos. | Borra `token.json` y vuelve a correr el script. |
| Calendar/Drive responden 502 con `Cannot refresh Google token` | Refresh genuinamente falló (red, proyecto deshabilitado). | Verifica que el proyecto Cloud sigue activo y las APIs habilitadas. |
| `/system/credentials-status` reporta `GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET` configurada pero Calendar sigue blocked | Tienes la identidad de la app, falta tu consentimiento. | Mismo: `auth_google.py`. |
| `freeBusy` devuelve `HTTP 403 ACCESS_TOKEN_SCOPE_INSUFFICIENT` aunque `status()` diga `ready` | El token se emitió con un scope insuficiente (`calendar.events` no cubre free/busy). | Ampliar `GOOGLE_CALENDAR_SCOPES` a `https://www.googleapis.com/auth/calendar`, borrar `token.json` y re-correr `auth_google.py` para re-consentir. |

### Mail personal GoDaddy/Gmail-label
| Variable | Cómo obtenerlo |
| --- | --- |
| `MAIL_ENABLED` | Actívalo solo cuando las credenciales de correo estén listas. |
| `MAIL_GODADDY_USERNAME`, `MAIL_GODADDY_PASSWORD` | Usuario y contraseña/app password del buzón GoDaddy; guardar solo en `.env` local ignorado. |
| `MAIL_GODADDY_IMAP_HOST/PORT`, `MAIL_GODADDY_SMTP_HOST/PORT` | Valores del panel GoDaddy/Workspace Email. Defaults: IMAP 993, SMTP 465. |
| `MAIL_GODADDY_MONITOR_FOLDERS` | Carpetas GoDaddy a revisar; default `Spam` porque el resto reenvía a Gmail. |
| `MAIL_IMAP_TIMEOUT_SECONDS`, `MAIL_SMTP_TIMEOUT_SECONDS` | Timeouts de red para no dejar workers colgados ante proveedores lentos. |
| `MAIL_GMAIL_MONITOR_LABELS` | Labels Gmail a leer si `GMAIL_READ_ENABLED=true`; default `TODOS,SPAM`. |
| `MAIL_DIGEST_HOURS_LOCAL`, `MAIL_DIGEST_TIMEZONE`, `MAIL_DIGEST_MAX_MESSAGES` | Schedule del digest: 10:00 y 20:00 `America/Santiago`, últimos 50. |
| `MAIL_BACKGROUND_SYNC_ENABLED` | Default `false`: no hace polling continuo; el digest sincroniza a las horas pactadas. |
| `MAIL_REQUIRE_APPROVAL_FOR_SEND`, `MAIL_ALLOW_EXPLICIT_SEND` | El flujo normal no envía. Solo habilita SMTP si Diego pide explícitamente un envío específico. |

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

### Cliente MCP (Model Context Protocol) — Fase 73

El DeepAgent puede cargar **tools dinámicas** de servidores MCP externos,
sin tocar código. Esto extiende sus 21 tools built-in con todo lo que
expongan los servidores que el operador declare.

**Activación:**
| Variable | Valor / formato |
| --- | --- |
| `ENABLE_MCP_CLIENT` | `true` para encender el cliente |
| `MCP_SERVERS` | CSV de declaraciones (ver sintaxis abajo) |
| `MCP_CALL_TIMEOUT_SECONDS` | timeout por llamada (default 30) |
| `MCP_INVENTORY_TIMEOUT_SECONDS` | timeout de `/system/mcp` para listar tools reales (default 30; necesario para arranque frío de varios MCP stdio via `npx`) |
| `MCP_ALLOWED_FOR_RESEARCH` | allow-list de servers para el subgrafo research (vacío = todos) |
| `MCP_ALLOWED_FOR_DOCUMENT_ANALYSIS` | allow-list para el subgrafo legal |

**Sintaxis de cada declaración en `MCP_SERVERS`:**

```
nombre:transporte:destino[::extra=valor,extra=valor,...]
```

- **Transportes:** `sse`, `streamable_http`, `websocket` (destino = URL) o
  `stdio` (destino = comando shell).
- **Extras URL:** `header_Authorization=Bearer <token>` para auth.
- **Extras stdio:** `cwd=/ruta`, `env_CLAVE=valor`.

**Ejemplos reales:**

```bash
# Supermemory (HTTP streaming, con token en el header):
MCP_SERVERS=mem:streamable_http:https://api.supermemory.ai/mcp::header_Authorization=Bearer sm_xxxxx

# Varios servers a la vez, separados por coma:
MCP_SERVERS=mem:streamable_http:https://api.supermemory.ai/mcp::header_Authorization=Bearer sm_xxx,gh:streamable_http:https://api.githubcopilot.com/mcp::header_Authorization=Bearer ghp_xxx,fs:stdio:npx -y @modelcontextprotocol/server-filesystem /home/jgonz

# Time local de Cognitive OS (sin auth, sin red externa):
MCP_SERVERS=time:stdio:uv run python -m cognitive_os.integrations.time_mcp_server::cwd=/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/backend
```

**Cómo se ven las tools:** prefijadas `<server>_<toolname>` (p.ej.
`mem_search_memories`, `gh_list_issues`, `fs_read_file`,
`time_time_now`, `time_time_convert`) para no colisionar con las 21 built-in.

**Observabilidad:** `GET /system/mcp` dialoga con cada server y reporta
`{connected, tools_count, error}`. El panel `Settings` tiene el tile
"MCP servers". El `/health/dashboard` incluye el componente `mcp_client`.
Desde `5953b40`, el inventario se carga en paralelo por servidor y el timeout
default es 30s para evitar falsos timeouts cuando varios MCP `stdio` arrancan
en frio. Runtime verificado: `mem`, `gh`, `fs`, `cc`, `gem` y `time`
conectados 6/6, **69 tools** visibles.

**MCP local `time`:** se implemento dentro del backend con
`mcp.server.fastmcp.FastMCP` y transporte `stdio`; no depende del bridge de
Codex. Sirve para resolver hora actual y conversiones de zona horaria
(`America/Santiago` por defecto). Al cambiar `MCP_SERVERS` o el modulo del
server hay que reiniciar el stack, porque API/workers leen la configuracion al
arranque.

**Seguridad:** sólo se activa bajo `OPERATOR_PROFILE=dedicated_local`
(las tools MCP usan credenciales personales del operador); cada server se
conecta aislado (uno caído no rompe a los otros); declarar sólo
servidores de confianza — el sistema no puede auditar qué hace una tool
remota arbitraria.

### Capacidades pendientes (variables reservadas, integración no implementada)
- **YouTube**: `YOUTUBE_API_KEY` → no hay extractor implementado.
- **Microsoft Mail**: `MICROSOFT_MAIL_ENABLED` (flag) → sin executor real.
- **Notion / cuentas externas**: variables presentes pero sin pipeline en backend.
- **Servidor MCP general** (Cognitive OS *exponiendo* sus tools de producto a
  clientes externos): sigue pendiente. El MCP local `time` es un utilitario
  interno read-only consumido por el propio cliente MCP de Cognitive OS.

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

`bash scripts/dev_beat.sh` lanza Celery beat con hasta 13 jobs (según feature
flags): consolidación diaria de memoria DeepAgents; los 3 reapers
(`reap_stale_approvals`, `reap_stuck_action_requests`,
`reap_stale_running_jobs`); las 5 tareas de aprendizaje Fases A-E
(recipe extractor, failure post-mortem, tool scorecard, skill promoter,
nightly reflection); sync de mail personal y digest Telegram/Gmail si están
activos; y recordatorios del asistente personal. Ver `ARCHITECTURE.md §6`.

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
| Mail sync no trae mensajes | `MAIL_ENABLED=false`, credenciales GoDaddy incompletas, carpeta mal escrita o Gmail OAuth apagado | Revisa `GET /mail/status`, logs de worker queue `mail`, `MAIL_GODADDY_*`, `MAIL_GMAIL_MONITOR_LABELS` |
| Digest mail vacío | No hay mensajes persistidos, sync falló o el agente clasificó todo como spam | Ejecuta `Sync ahora`, revisa warnings del digest y valida OAuth/IMAP |
| Frontend devuelve 401 | JWT inválido o expirado | Genera otro y pégalo en `Settings` |
| `reject_changeme_in_production` impide arrancar | Hay secretos `CHANGEME` en prod | Reemplaza con secretos reales antes de poner `ENVIRONMENT=production` |

---

## 18. Roadmap

Lo que **funciona hoy** (verificado contra código y tests):

- Backend completo (150 endpoints REST) + frontend (20 vistas, incluye `Assist`, `Google Ops` y `Research`).
- Ruta `research` con fusión opcional OpenHarness y fallback determinista.
- Ruta `legal` con Document Analysis y exportadores.
- Action Plane con `computer_organize`, `document_generate`, `browser_preview`, `browser_interactive`, Google Calendar create y Drive upload/folder/organize ejecutables sólo por `ActionRequest` aprobado; Maps read-only con tráfico/link; Calendar free/busy read-only; Gmail digest read-only; mail GoDaddy/Gmail con digest y propuestas escritas sin envío normal; GoDaddy DNS preview/executor con dry-run.
- Memoria DeepAgents con propuestas + aprobación + episódica.
- Bot Telegram con 37 comandos slash.
- Research Orchestrator multi-subtarea con SSE y cancelación.
- QA reproducible actual: `bash scripts/full-qa.sh` → 958 passed, 1 skipped, 28 deselected; ruff/ruff format/mypy/frontend lint/build aislado en `.next-qa`, Alembic y `sync_doc_counts --check` verdes en esta rama.

Lo que **falta** para llegar a "asistente personal absoluto" (detalle en [`PERSONAL_ASSISTANT_ROADMAP.md`](./PERSONAL_ASSISTANT_ROADMAP.md)):

| Brecha | Variables reservadas | Estado |
| --- | --- | --- |
| **Memoria personal temporal y semántica** (perfil, hábitos, decisiones expirables) | DeepAgents memory (extender) | Base lista, falta capa de perfil/expiración. |
| **Correo multi-cuenta completo** (lectura Gmail/GoDaddy, digest, propuestas; send/drafts solo si Diego lo pide en el futuro) | `GMAIL_SEND_ENABLED`, `MICROSOFT_MAIL_ENABLED`, `MAIL_*` | Primer corte fuerte listo: Gmail `TODOS`/`SPAM`, GoDaddy `Spam`, propuestas escritas y digest 10:00/20:00. Falta Microsoft y acciones de archivo/label; Gmail/GoDaddy send queda fuera del flujo normal. |
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
- [`AGENT_LEARNING_PLAN.md`](./AGENT_LEARNING_PLAN.md): plan de aprendizaje autónomo del agente (Fases A-E, cerradas).

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

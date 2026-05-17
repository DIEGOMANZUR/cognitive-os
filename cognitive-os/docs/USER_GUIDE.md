# Cognitive OS — Guía de Usuario (comercial)

> Estado: **Fase 41 cerrada (2026-05-17)**. Pila operativa grado comercial.
> Snapshot QA: **632 pytest passed, 1 skipped, 20 deselected** ·
> ruff/format/mypy · frontend lint/build · pre-commit (6 hooks) ·
> detect-secrets — todo verde. **126 endpoints REST**, **16 tareas
> Celery** en 5 colas, **16 migraciones Alembic**, **20 vistas frontend**.

Este documento es **la** guía operativa. Si nunca viste el proyecto,
léelo de principio a fin. Si ya lo conocés, andá directo al capítulo
que necesites.

Índice:

1. [Qué es Cognitive OS, de principio a fin](#1-qué-es-cognitive-os-de-principio-a-fin)
2. [Cómo arranca y cómo se apaga](#2-cómo-arranca-y-cómo-se-apaga)
3. [El frontend, vista por vista](#3-el-frontend-vista-por-vista) — qué hace cada acción
4. [Pipelines internos (qué pasa cuando hacés click)](#4-pipelines-internos)
5. [Usarlo desde Telegram](#5-usarlo-desde-telegram)
6. [Ejemplos impresionantes para sacarle el máximo](#6-ejemplos-impresionantes)
7. [Qué hace el agente y qué NO hace](#7-qué-hace-el-agente-y-qué-no-hace)
8. [Cómo NO usar Cognitive OS](#8-cómo-no-usar-cognitive-os)
9. [Troubleshooting express](#9-troubleshooting-express)

---

## 1. Qué es Cognitive OS, de principio a fin

**Definición de una línea.** Cognitive OS es un sistema operativo
cognitivo local-first para vos, el operador: un cerebro de agentes
LangGraph + DeepAgents conectado a tu mail, tu navegador, tu
computador, tus documentos legales, Google Workspace, GoDaddy y a
coding agents externos — todo bajo aprobación humana, con auditoría y
budget caps, ejecutándose en `127.0.0.1`.

**De qué se compone, de arriba abajo:**

- **Backend FastAPI 0.115+** (Python 3.12, `uv`): **126 endpoints REST**
  bajo JWT, rate-limited. Es el cerebro y la sala de máquinas.
- **Orquestación LangGraph 1.1.10** con grafo principal
  (`Planner → Researcher → Synthesizer → Scorer`) y subgrafos
  especializados (mail, browser, computer, calendar, drive, social,
  legal). Cada nodo respeta `tool policy` y deja `JobEvent` + `AuditEvent`.
- **DeepAgents 0.6.x** con su `skills/` (core + user) y memoria
  persistida `DeepAgentMemoryService`. Las skills nuevas se proponen y
  esperan aprobación humana antes de activarse.
- **Action Plane** — la capa que convierte *intención* en *acción
  externa con rastro*: mail (GoDaddy IMAP/SMTP + Gmail label `TODOS`),
  Google Maps/Calendar/Drive, GoDaddy DNS (dry-run), navegador
  (Playwright + visión), computador local (organizar/inventario),
  documentos Office (DOCX/XLSX/PPTX), sandbox OpenShell opcional, y el
  **Code Director** (delegación a coding agents externos).
- **Celery 5.4** con 5 colas: `default`, `ingestion`, `agent_longrun`,
  `maintenance`, `mail`. Trabajos largos, ingesta de PDFs, builds de
  código, mantenimiento de tokens, envío diferido de correos.
- **Datos** ligados a loopback: **Postgres 16 + pgvector** (vectores +
  estado de grafo), **Redis 7** (cache, rate limit Redis backend
  opcional, broker Celery), **Weaviate 1.29.0** (búsqueda híbrida),
  **Neo4j 5** (grafo de conocimiento), **OpenSearch/Tantivy** (BM25).
- **Frontend Next.js 16.2.6** con **20 vistas** en `app/views/*.tsx`
  (ver §3). SSE-over-fetch para tiempo real, hotkeys 1-9, paleta
  Ctrl-K.
- **Canal humano fuera del panel**: bot de **Telegram** (long-poll, sin
  webhook). Espejado 1:1 con el REST — el mismo `AuditEvent` se escribe
  para una decisión hecha por panel o por bot.
- **Ejecutables de escritorio** (`Levantar/Reiniciar/Detener/Estado
  Cognitive OS.sh`) que levantan o apagan toda la pila incluyendo el
  worker `mail` y Kimi WebBridge.
- **Política transversal**: nada sensible se ejecuta sin
  `HumanApproval` + `AuditEvent`. Pendientes que envejecen >48 h los
  cierra el reaper. Decisiones críticas tienen four-eyes opcional.
  Correlación por `X-Request-ID`.

**Filosofía.** Tres líneas:

1. **Vos sos el dueño.** El sistema vive en tu máquina, con tus
   credenciales, en `127.0.0.1`. No hay tenant, no hay multi-cliente.
2. **Aprobás antes de gastar.** Tokens, dinero, mails y cambios
   externos pasan por `HumanApproval` o por `MAIL_REQUIRE_APPROVAL_FOR_SEND=true`.
3. **Si algo falla, falla con red, no en el aire.** Circuit breakers,
   fail-open en rate limit, fallback heurístico en planificación,
   manifest en cada artefacto.

**Lo nuevo de Fase 41 (Code Director F9).** El Code Director ya no
planifica con un esqueleto fijo: un **planner LLM-driven** descompone
tu objetivo en subtareas reales (con fallback heurístico determinista),
y cada subtarea se prompt-ea con el estado vivo del workspace + lo que
produjeron sus dependencias; los reintentos llevan el error del intento
anterior con "arregla esto, no empieces de cero". Detalle en §3
*Code Director* y §6 *Ejemplos*.

---

## 2. Cómo arranca y cómo se apaga

**Modo escritorio (recomendado, lo más simple):**

```
~/Escritorio/Levantar Cognitive OS.sh    # levanta backend + worker + mail + WebBridge + frontend
~/Escritorio/Estado Cognitive OS.sh      # ¿qué hay vivo?
~/Escritorio/Reiniciar Cognitive OS.sh   # ciclo limpio
~/Escritorio/Detener Cognitive OS.sh     # apaga todo
```

**Modo manual:**

```bash
cd cognitive-os/infra && docker compose --env-file ../.env up -d
cd ../backend
uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000
uv run celery -A cognitive_os.workers.celery_app worker -Q default,ingestion,agent_longrun,maintenance,mail
cd ../frontend && npm run dev
```

Abrir `http://localhost:3000`. Si nunca configuraste credenciales:
`bash scripts/init_credentials.sh` te dice qué falta (`--ci` para
gate en CI). El detalle por componente vive en `RUNBOOK.md`.

---

## 3. El frontend, vista por vista

20 vistas, agrupadas por la barra lateral. Para cada una: **qué hace
exactamente**, **qué cambia al hacer click**, **dónde queda registro**.

### Overview

#### Dashboard (◧, hotkey 1)
- **Qué hace:** snapshot vivo de la pila (health, jobs corriendo,
  aprobaciones pendientes, últimos audit events).
- **Click típico:** no produce cambios — es solo lectura.
- **Pipeline:** consulta `/health/detail`, `/jobs?recent=true`,
  `/approvals/pending`, `/audit/events?limit=...` cada N s.

### Agentes

#### Chat (◇, hotkey 2)
- **Qué hace:** conversación con el orquestador LangGraph (thread
  persistido). Modo `chat`, `agent_research`, `agent_research_legal`.
- **Click "Enviar":** crea o continúa un `LangGraph thread`, dispara el
  grafo, retorna mensaje + citas + score.
- **Si el grafo pide aprobación humana:** se detiene en
  `interrupt(...)`, vas a *Aprobaciones*, decidís, se reanuda.

#### DeepAgents (✱)
- **Qué hace:** estado del subagente DeepAgents (memoria, tools
  habilitadas, política, actividad reciente).
- **Click "Toggle skill":** propone activar/desactivar una skill →
  `HumanApproval` → al aprobar entra en `enabled_skills`.

#### Skills (✸)
- **Qué hace:** lista las skills core (`citation-discipline`,
  `contradiction-detector`, `evidence-matrix`, `legal-draft-careful`,
  `rag-research`, `report-writer`, `sandbox-code-analysis`,
  `timeline-builder`) y user. Permite proponer nueva skill desde un
  `SKILL.md` montado.
- **Click "Proponer":** crea propuesta + `HumanApproval`. Sin aprobar,
  la skill **no** se ejecuta.

#### Memoria (◉)
- **Qué hace:** consolidación, propuestas pendientes, búsqueda por
  query.
- **Click "Consolidar ahora":** dispara `cognitive_os.memory_consolidate`
  en la queue `maintenance`.
- **Click "Aprobar propuesta":** la promueve a memoria persistente.

#### Asistente (◌)
- **Qué hace:** vista de tareas y notas personales del operador
  (mapeo chat Telegram → user vía `TELEGRAM_ASSIST_USER_MAP`).
- **Click "+ Tarea":** crea entrada con due-date opcional; aparece
  también en `/tasks` por Telegram.

#### Mail (✉)
- **Qué hace:** inbox unificado GoDaddy IMAP + Gmail label `TODOS`.
  Propone respuestas redactadas por el agente.
- **Click "Enviar":** **NO envía directo** — pasa por
  `HumanApproval` (`MAIL_REQUIRE_APPROVAL_FOR_SEND=true`). Recién al
  aprobar, el worker `mail` hace el SMTP/Gmail send y deja
  `AuditEvent`.

### Conocimiento

#### Documentos (▦, hotkey 3)
- **Qué hace:** ingesta de PDFs y URLs al RAG (Postgres + pgvector +
  Weaviate + Neo4j para entidades).
- **Click "Ingestar":** encola
  `cognitive_os.ingest_document` en queue `ingestion`. Resultado vive
  en *Jobs*.

#### Document Analysis (◈, hotkey 4)
- **Qué hace:** análisis legal estructurado en 6 modos:
  `evidence_matrix`, `contradictions`, `timeline_builder`,
  `claim_chart`, `tabular_review`, `legal_draft`.
- **Click "Ejecutar":** crea job en queue `agent_longrun`, produce
  artefactos descargables (DOCX/XLSX) y eventos SSE en vivo.

### Operaciones

#### Jobs (▶, hotkey 5)
- **Qué hace:** lista todos los jobs (ingesta, research, code build,
  mail send, analysis...). Cada uno con estado, eventos SSE y
  artefactos.
- **Click "Cancelar":** envía `revoke` al worker; estado pasa a
  `cancelled`, queda en audit.

#### Aprobaciones (✓, hotkey 6)
- **Qué hace:** **la vista más importante**. Todo cambio sensible
  espera aquí.
- **Click "Aprobar":** desbloquea el job/grafo/correo.
- **Click "Rechazar":** corta la ejecución con razón persistida.
- Con `APPROVAL_REQUIRE_FOUR_EYES=true`, una decisión sola no alcanza
  para acciones críticas — necesita una segunda aprobación.
- Las que llevan >`APPROVAL_PENDING_MAX_HOURS=48` las cierra el reaper
  como `expired`.

#### Google Ops (⌖)
- **Qué hace:** Maps (read-only, con tráfico), Calendar (eventos +
  free/busy), Drive (listar/leer/escribir). Writes siempre vía
  `ActionRequest`.
- **Click "Crear evento":** crea `ActionRequest`, lo aprobás, recién
  ahí toca el calendario real.

#### Research (⌕)
- **Qué hace:** ejecuta investigación con plan animado en vivo (SSE).
  Si está activado, usa **OpenHarness** como preludio
  (`OPENHARNESS_RESEARCH_PIPELINE=prelude_merge` por defecto).
- **Click "Iniciar":** plan, N investigadores en paralelo, síntesis,
  scoring. Cada citation queda enlazada al documento fuente.

#### Code Director (⟐) — **Fase 41 (F9)**
- **Qué hace:** le das un objetivo de alto nivel y delega la
  codificación a **coding agents externos**: Claude Code CLI, Codex
  CLI, Kimi CLI o DeepAgents in-process. Vos no escribís ningún prompt.
- **Click "Planificar":** el **LLMPlanner** descompone el objetivo en
  subtareas reales (no el esqueleto fijo de antes) y arma un plan con
  adapter/modelo por rol. Si el LLM falla por cualquier razón
  (sin key, JSON malformado, dependencias alucinadas…), cae al
  `HeuristicPlanner` determinista. **No gasta tokens todavía.**
- **Aprobás** el plan en *Aprobaciones*.
- Al aprobar: encola `cognitive_os.run_code_build` en `agent_longrun`.
  Cada subtarea recibe un prompt **estructurado y acotado**: árbol del
  workspace + contenido relevante + lo que produjeron sus dependencias.
  Si una falla, el reintento lleva el error del anterior con "arregla
  esto, no empieces de cero" — converge en vez de repetir el fallo.
- **Click "Descargar":** `tar.gz` del workspace generado, con manifest.
- **Budget caps duros** (`max_runtime_minutes=120`,
  `max_total_llm_calls=200`, `max_calls_per_subtask=20`,
  `max_total_cost_usd`). Excederlos cierra el build como `partial` y
  **igual entrega lo construido**.

#### Sandbox (▢)
- **Qué hace:** ejecuta código aislado en **OpenShell** (opt-in con
  `ENABLE_OPENSHELL_SANDBOX=true`). Vendor-side, deshabilitado por
  defecto.
- **Click "Run":** crea cápsula efímera, captura stdout/stderr/exit.

### Observabilidad

#### LangSmith (⌬, hotkey 7)
- **Qué hace:** trazas en vivo de cada nodo del grafo. Útil para
  entender por qué un thread devolvió X.

#### Audit log (≡, hotkey 8)
- **Qué hace:** stream de `AuditEvent` filtrable por actor, acción,
  recurso. Todo cambio externo deja huella aquí, sin importar si
  vino de panel o de Telegram.

#### Health (♡, hotkey 9)
- **Qué hace:** salud por componente (db, redis, weaviate, neo4j,
  celery, broker, tokens Google, mail GoDaddy/Gmail). Si algo está
  `degraded`, te dice el comando exacto para arreglarlo.

### Configuración

#### Sistema (⚒)
- **Qué hace:** flags no-secretos (`policy`, feature toggles).
  Inventario de las 21 credenciales operador con estado, capacidad
  habilitada y *dónde obtenerlas*. **Nunca muestra valores**.

#### Conexión (⚙)
- **Qué hace:** apunta el panel a una API distinta (útil si querés
  consumir el backend desde otra máquina en la LAN). Persiste en
  `localStorage`.

---

## 4. Pipelines internos

Tres pipelines que hay que tener en la cabeza:

### A) Pipeline `Action Plane` (acciones externas)

```
Vista (frontend) ─► POST /actions/requests        (crea ActionRequest pendiente)
                  └─► POST /approvals             (HumanApproval ligada)
                       │
                       ▼
                  Aprobación (panel o /approve por Telegram)
                       │
                       ▼
                  Celery task en `agent_longrun` ó `mail`
                       │
                       ├─► Ejecutor (mail SMTP, Calendar API, Drive API, ...)
                       ├─► AuditEvent (qué, quién, cuándo)
                       └─► JobEvents (SSE) hasta estado terminal
```

Reglas: nada toca el mundo externo sin pasar por este pipe.

### B) Pipeline `Research` (lectura intensiva)

```
Chat / Research view
   └─► LangGraph: Planner → (Researcher × N en paralelo) → Synthesizer → Scorer
        ├─ Si ENABLE_OPENHARNESS_RESEARCH=true → preludio QueryEngine antes de DeepAgents
        ├─ Tools: RAG local (Postgres+pgvector), Weaviate, Neo4j, web fetch
        ├─ Cada citation está enlazada al documento fuente
        └─ Output: respuesta + citas + score (rúbrica)
```

### C) Pipeline `Code Director` (delegar a coding agents)

```
POST /code-director/run  (objective + adapter_preference + budget)
   └─► LLMPlanner.plan() → BuildPlan (subtareas reales)
        └─ fallback: HeuristicPlanner si el LLM falla
   └─► Job(code_build, waiting_approval) + HumanApproval
       (cero tokens hasta aquí)
   ──── Aprobás ─────────────────────────────────────────────
   └─► Celery run_code_build en `agent_longrun`
        └─ topo-sort subtareas → cada subtarea:
             ├─ build_subtask_prompt(workspace+upstream+last_error)
             ├─ Adapter (claude_code | codex | kimi | deepagent)
             │   ├─ STDIN-only para CLIs (no fuga en `ps`)
             │   └─ SIGTERM→SIGKILL del process group al timeout
             ├─ StepResult → si falla y iterate_until_tests_pass:
             │   └─ reintento con prompt error-dirigido (no replay)
             └─ budget tracker (calls/runtime/cost)
   └─► Empaqueta workspace en tar.gz + manifest
   └─► GET /code-director/{id}/download
```

---

## 5. Usarlo desde Telegram

> **Nota:** el sistema integra **Telegram** (long-poll, sin webhook,
> funciona detrás de NAT). **No** integra Instagram.

**Setup mínimo:** poné `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ENABLED=true` y
opcionalmente `TELEGRAM_ASSIST_USER_MAP` (mapea chat_id → user). El bot
arranca con la pila completa (`Levantar Cognitive OS.sh`).

**Comandos disponibles** (idénticos al panel, mismo `AuditEvent`):

| Comando | Hace |
|---|---|
| `/start`, `/help` | bienvenida + lista de comandos |
| `/health` | resumen componentes (ok/degraded) |
| `/stats` | docs/páginas/chunks/jobs/aprobaciones |
| `/config` | flags no-secretos |
| `/agents` | estado DeepAgents + policy + actividad |
| `/skills` | skills habilitadas |
| `/memory` | propuestas de memoria pendientes |
| `/consolidate` | encola consolidación de memoria |
| `/jobs` | jobs recientes |
| `/job <id>` | detalle + últimos eventos |
| `/cancel <id>` | cancela job (idempotente) |
| `/approvals` | aprobaciones pendientes |
| `/approve <id>` | aprueba (respeta four-eyes) |
| `/reject <id>` | rechaza con motivo |
| `/threads` | threads LangGraph recientes |
| `/chat <mensaje>` | habla con el orquestador (mismo grafo que la vista Chat) |
| `/ingest <ruta>` | encola ingesta de un PDF absoluto |
| `/runs` | últimas trazas LangSmith |
| `/tasks`, `/task <texto>`, `/done <id>` | tareas personales |
| `/notes`, `/note <texto>` | notas Markdown |
| `/gmaildigest` | digest Gmail (read-only, requiere `GMAIL_READ` + token) |

**Casos prácticos:**

- Te llega push "ApprovalPending #ab12cd…" → `/approve ab12cd` desde el
  bondi.
- "¿Qué está corriendo?" → `/jobs` + `/job <id>` para el detalle.
- Necesitás cancelar un build largo → `/cancel <id>`.
- Querés meter un PDF al RAG sin abrir el laptop → mandalo al bot,
  `/ingest /path/al/pdf`.

**Simetría garantizada:** un `/approve` por Telegram deja el mismo
`AuditEvent` (`actor="telegram:<chat_id>"`) que una aprobación por
panel. Los four-eyes y el reaper funcionan igual.

---

## 6. Ejemplos impresionantes

### 6.1 "Codificame una app con 2 RAGs y un frontend hermoso usando Claude Opus 4.7 en Claude Code"

1. **Frontend ►** *Code Director* → completar:
   - **Objetivo:** "App con 2 RAGs (uno transacciones, otro documentos
     legales) + frontend Next.js + FastAPI; tests; Docker compose."
   - **Adapter preference:** `default_adapter=claude_code`,
     `default_model=claude-opus-4-7`, `reviewer_adapter=codex`.
   - **Budget:** `max_total_llm_calls=80`,
     `max_total_cost_usd=20.00`.
2. Click **Planificar**. El LLMPlanner devuelve algo como:
   `db-schema → rag-tx → rag-legal → api → frontend → tests → review`
   (orden por dependencia, no el esqueleto fijo). **Cero tokens
   gastados todavía.**
3. **Aprobaciones ►** revisás el plan, **Aprobar**.
4. Mirás el timeline SSE: cada subtarea va a su CLI (`claude` para
   coder, `codex` para reviewer). Si `rag-legal` falla por
   `ImportError`, el reintento lleva el error literal del intento
   anterior y la directiva "no empieces de cero" → corrige en el
   segundo intento.
5. **Descargar `tar.gz`.** Adentro: workspace + `_codedirector_manifest.json`.

### 6.2 "Negociá mis reuniones de mañana sin que toque calendar yo"

1. **Chat ►** "Mirá mi calendar de mañana, contesta los pendings de
   GoDaddy/Gmail con horarios libres de la mañana; sugerime 3 slots
   por reunión, dejame aprobar antes de mandar."
2. El grafo: Calendar free/busy → mail inbox → drafter → propone 3
   slots por reunión → **te deja `HumanApproval` por cada borrador**.
3. Aprobás los que quieras desde *Aprobaciones* o desde
   `/approve <id>` en Telegram → el worker `mail` envía vía SMTP/Gmail
   API → `AuditEvent` queda.

### 6.3 "Análisis legal de 6 PDFs de demanda"

1. **Documentos ►** ingestá los 6 PDFs (encolan en `ingestion`).
2. **Document Analysis ►** modo `evidence_matrix` → seleccionás los
   docs → **Ejecutar**.
3. Sale una XLSX con matriz de evidencia + citas verificadas.
4. Modo `contradictions` con los mismos docs → DOCX con cada
   contradicción referenciada `doc/página`.
5. Modo `timeline_builder` → cronología consolidada.
6. Todo queda en *Jobs* descargable.

### 6.4 "Investigá X profundo, citado, en 4 minutos"

1. **Research ►** query + activá
   `ENABLE_OPENHARNESS_RESEARCH=true`.
2. Plan animado en vivo: Planner expone el árbol de subpreguntas,
   N Researchers corren en paralelo, Synthesizer arma respuesta,
   Scorer la puntúa contra rúbrica.
3. Cada citation es clickable al fragmento exacto del documento
   fuente.

### 6.5 "Ingestá este PDF mientras estoy en el subte"

```
Telegram → /ingest /home/jgonz/Descargas/contrato.pdf
Bot → "Encolado: job ab12cd…. Seguilo con /job ab12cd"
```

### 6.6 Modo "operador con manos atadas" (sin tocar el panel)

Todo lo de §5 corre por Telegram. Aprobaciones, cancelaciones,
ingestas, chat, jobs, health. Útil cuando estás fuera de casa o el
laptop está apagado pero el server queda corriendo.

---

## 7. Qué hace el agente y qué NO hace

### Hace

- **Investigación con citas verificadas** (RAG local + Weaviate + Neo4j
  + opcional OpenHarness preludio).
- **Análisis legal estructurado**: matriz evidencia, contradicciones,
  timeline, claim chart, tabular review, drafts cuidadosos.
- **Mail personal multicuenta** (GoDaddy IMAP/SMTP + Gmail label
  `TODOS`): leer, clasificar, redactar borradores. **Envía solo con
  aprobación humana.**
- **Google Workspace**: Maps (read-only con tráfico), Calendar
  (read + write bajo `ActionRequest`), Drive (read + write bajo
  `ActionRequest`).
- **Navegador**: `browser_preview` (screenshot/lectura, multimodal),
  `browser_interactive` (Playwright bajo allow-list).
- **Computador local**: `computer_organize` (mover/renombrar bajo
  política), `computer_inventory` (read-only).
- **Generar documentos Office**: DOCX/XLSX/PPTX con assets
  controlados (`DOCUMENT_OUTPUT_ROOT`, `DOCUMENT_MAX_SIZE_BYTES`).
- **Delegar codificación** (Code Director F9): Claude Code, Codex,
  Kimi CLIs o DeepAgents in-process; plan LLM-driven; prompts con
  contexto vivo; reintentos error-dirigidos.
- **Skills** (DeepAgents core/user) con propuesta + aprobación.
- **Memoria persistente** con propuesta + aprobación.
- **Sandbox de código** (OpenShell, opt-in).
- **Telegram bot** simétrico al panel (mismo audit).

### NO hace

- **No envía dinero ni hace pagos**. No hay integración financiera. Si
  vos automatizás eso vía Code Director, sos vos firmando el código.
- **No toca tu sistema operativo sin permiso**. `computer_organize`
  requiere política + allow-list de paths. Sin eso, es no-op.
- **No publica nada en redes sociales por su cuenta**. El subgrafo
  social *clasifica* texto y *propone* borradores; el envío no está
  cableado a ninguna API de Instagram/Twitter/LinkedIn.
- **No usa Instagram.** Punto. El único canal externo de
  interacción humana es Telegram.
- **No ejecuta código arbitrario fuera del sandbox.** El Code Director
  escribe archivos en su workspace aislado; los tests opcionales se
  corren en `openshell_sandbox`.
- **No sube nada a la nube de Anthropic/OpenAI/Moonshot salvo lo que
  vos autorices**. Las llamadas LLM van a los endpoints que
  configuraste; el código generado vive local hasta que vos lo subas.
- **No gasta tokens sin tu aprobación** en flujos críticos (Code
  Director, mail send, ActionRequest Google).
- **No tiene multi-tenant**. Es para vos, en `127.0.0.1`. No expongas
  el puerto 8000 a internet.
- **No reemplaza tu juicio**. Aprobás vos. El sistema no toma
  decisiones legales/financieras finales por vos.
- **No es Antigravity ni Claude Desktop**: esos están deliberadamente
  fuera porque no tienen modo headless; no son una debilidad, es una
  decisión.

---

## 8. Cómo NO usar Cognitive OS

Las siguientes son **anti-prácticas**. Si te encontrás haciendo
alguna, parate.

1. **No expongas el backend a internet.** Está atado a `127.0.0.1`
   por diseño. Si necesitás acceso remoto, usá WireGuard / Tailscale /
   SSH tunnel, no abras puerto.
2. **No metas `*` en `CORS_ALLOW_ORIGINS` con credenciales
   habilitadas.** La configuración lo rechaza, pero igual no lo
   intentes.
3. **No desactives `MAIL_REQUIRE_APPROVAL_FOR_SEND`.** Aunque sea
   "rápido para testear". Un mail mal mandado no se desmanda. Si vas a
   automatizar respuestas a clientes, lo hacés con `MAIL_AUTOSEND_ALLOWLIST` y
   plantillas, no quitando la barrera.
4. **No commitees `.env`, `token.json`, `client_secret.json` ni
   `storage/`.** Hay `detect-secrets` con baseline, pero la
   responsabilidad es tuya.
5. **No le pidas al Code Director cosas que requieren credenciales
   sensibles dentro del código.** El workspace se entrega como `tar.gz`
   — todo lo que vaya ahí queda en claro. Las keys las inyectás vos
   después, fuera del workspace.
6. **No apruebes sin leer.** Especialmente en *Aprobaciones* para
   mail, calendar writes y `payload_executable`. El sistema te ofrece
   diff/preview justamente para eso.
7. **No corras dos copias contra la misma DB.** Postgres es una sola
   verdad; dos backends apuntando al mismo `cognitive_os` pisan
   migraciones y estado.
8. **No subas el ZIP que generó Code Director a un repo público sin
   revisarlo.** Es código generado: revisalo, corré tests, mirá
   dependencias antes de empujarlo.
9. **No edites a mano `SETTINGS_REGISTRY_TABLE.md`.** Se regenera con
   `uv run python scripts/dump_settings_registry.py`.
10. **No ignores `Health: degraded`.** El detalle siempre trae el
    comando para arreglarlo (`auth_google.py`, `alembic upgrade head`,
    re-login GoDaddy, etc.). Operar en `degraded` es operar a ciegas.
11. **No uses el bot de Telegram en un grupo público.** El allowlist
    `TELEGRAM_ALLOWED_CHATS` está justamente para que solo vos (o tu
    círculo cerrado) opere.
12. **No le pidas que "haga un pago", "transfiera", "compre", "publique
    en Instagram".** No tiene esos canales. Si insistís, te lo va a
    decir y va a rechazar la acción.

---

## 9. Troubleshooting express

| Síntoma | Causa probable | Comando que arregla |
|---|---|---|
| Frontend dice `no-auth` | JWT vencido | re-login en *Conexión* o `POST /auth/token` |
| `Health: degraded · google` | token Google caducado | `uv run python scripts/auth_google.py` (self-healing si refresh sirve) |
| Build de Code Director queda `failed` con "adapter unavailable" | CLI no instalado / no logueado | `claude --version`, `codex --version`, `kimi --version` |
| `Approval pending >48h` desaparece sola | reaper la marcó `expired` | volvé a generarla |
| Mail nunca sale | `MAIL_REQUIRE_APPROVAL_FOR_SEND=true` y no aprobaste | *Aprobaciones* o `/approve <id>` |
| Rate limit Redis fail-open lo deja pasar todo | Redis caído | levantá Redis; nunca bloquea legit traffic |
| `detect-secrets` falso positivo en string de test | falta `# pragma: allowlist secret` | agregalo en esa línea |

Cualquier otra cosa rara: `bash scripts/full-qa.sh` debería volver
verde — si no, es una regresión real, no una rareza ambiental.

---

**Documentos relacionados:**

- `RUNBOOK.md` — operación: arrancar, detener, respaldar, restaurar
- `ACTION_PLANE.md` — detalle técnico de cada acción externa
- `ARCHITECTURE.md` — diagramas internos
- `SECURITY.md` — controles obligatorios
- `OPENHARNESS_FUSION.md` — fusión OpenHarness/LangGraph/DeepAgents en `research`
- `DOCUMENT_ANALYSIS_AGENT.md` — los 6 modos legales
- `DEEPAGENTS_SKILLS_MEMORY.md` — skills y memoria
- `OPERATOR_VARIABLE_CHECKLIST.md` — todas las ENV
- `SETTINGS_REGISTRY_TABLE.md` — tabla autogenerada desde `config.py`
- `../findings.md`, `../progress.md` — bitácora viva

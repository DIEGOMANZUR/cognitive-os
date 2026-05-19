# Cognitive OS — Guía de Usuario (comercial)

> Estado: **Fase 68 cerrada (2026-05-19)** — GoDaddy DNS de producción
> operativo y verificado en vivo (auth HTTP 200), doble revisión profunda,
> `.env.example` actualizado. Cadena LLM del operador verificada en vivo:
> **primary + agent = `gpt-5.5`** (gateway OpenAI-compatible),
> **secondary + fallback = `gemini-3.1-pro-low`** (mismo gateway),
> **visión = `glm-4.6v`** (z.ai). `kimi-k2.6` vía HTTP da 403 (solo el
> adapter CLI del Code Director). Las 21 tools del DeepAgent usan
> `args_schema` Pydantic tipado (válidas en gateways estrictos).
> Verificado en vivo: `/chat` → DeepAgent real sin fallback, router LLM
> decidiendo, 0 errores de tool_choice/schema; ruta Maps real con tráfico.
> Pila operativa grado comercial, verificada funcionando (no solo en
> tests). Snapshot QA: **685 pytest passed, 1 skipped, 20 deselected** ·
> ruff/format/mypy (125 source files) · frontend lint/build (20 vistas) ·
> Alembic head `202605170001` (aplicada en Postgres real) · `git diff
> --check` · pre-commit · detect-secrets (0 findings) — **todo verde** y
> **suite hermética por construcción** (ningún test hace llamadas LLM
> reales; guard autouse en `tests/conftest.py`). **131 endpoints REST**,
> **16 tareas Celery** en 5 colas, **17 migraciones Alembic**, **20
> vistas frontend**, **37 slash commands de Telegram** con paridad real.
>
> **Realidad del stack LLM (importante — entendé cómo reacciona el
> sistema):** todo está cableado en `.env`, no tenés que tocar nada; esto
> es para que entiendas el diseño.
>
> | Carril | Modelo | Endpoint | Para qué |
> |---|---|---|---|
> | Primary | `gpt-5.5` | gateway :8317 | chat / razonamiento |
> | Agent | `gpt-5.5` | gateway :8317 | DeepAgents + router (tool_choice forzado) |
> | Secondary | `gemini-3.1-pro-low` | gateway :8317 | tareas low-cost / 1er fallback |
> | Fallback | `gemini-3.1-pro-low` | gateway :8317 | si el circuit breaker del primary abre |
> | Visión | `glm-4.6v` | z.ai | screenshots / análisis multimodal |
> | Embeddings | `gemini-embedding-001` | Google | RAG / búsqueda semántica |
>
> El **carril de agente es el más sensible**: usa *structured output*
> (tool_choice forzado). Modelos *reasoner* (p.ej. `deepseek-v4-pro`) NO
> lo soportan y rompen todo DeepAgent en silencio (cae a RAG); por eso se
> usa `gpt-5.5` (verificado). `kimi-k2.6` por HTTP da 403 ("Kimi For
> Coding solo para coding agents") — solo sirve por el binario `kimi` CLI
> del Code Director (lee su propio `~/.kimi`, no el `.env`). Si el gateway
> cae, el router degrada con red: agent→secondary→primary→`deterministic_route`
> (sin crash) y el DeepAgent cae a RAG. Trazas LangSmith usan el *personal
> access token* (la API key scoped no puede ingestar).
>
> **Pendientes del operador (NO bloquean el resto del sistema):**
> 1. **Telegram:** el `TELEGRAM_BOT_TOKEN` del `.env` da **HTTP 401**
>    (revocado/erróneo) y `TELEGRAM_AUTHORIZED_USER_IDS` está vacío. Para
>    usar el bot: pedí un token nuevo a **@BotFather**, conseguí tu
>    user_id con **@userinfobot**, y poné en `.env`
>    `TELEGRAM_BOT_TOKEN=<nuevo>`, `TELEGRAM_AUTHORIZED_USER_IDS=<tu id>`,
>    `TELEGRAM_ENABLED=true`.
> 2. **Google Calendar/Drive/Gmail:** correr una vez
>    `uv run python scripts/auth_google.py` (OAuth interactivo: login +
>    consentimiento en el navegador) para pasarlos de `blocked` a `ready`.
> 3. **GoDaddy DNS:** ya operativo en modo seguro (dry-run + aprobación).
>    Para escrituras DNS reales: poné `GODADDY_DNS_DRY_RUN_ONLY=false` +
>    `GODADDY_ALLOW_PRODUCTION_WRITES=true` y ajustá
>    `GODADDY_ALLOWED_DOMAINS` a los dominios reales de tu cuenta.
>
> **Verificado en vivo** (con el stack levantado y credenciales reales):
> LLMs (chat real `gpt-5.5` + tool_choice forzado), DeepAgent real sin
> fallback RAG, router LLM decidiendo, RAG, Google Maps (ruta con
> tráfico), CORS panel→API. **Implementado y `ready` con flags/credenciales
> activas (no probado en vivo en este host):** voice (ElevenLabs), captcha
> (CapSolver), Kimi WebBridge, mail multicuenta, Code Director (adapters
> CLI necesitan los binarios instalados). Calendar/Drive/Gmail quedan
> `blocked` hasta el OAuth interactivo (`scripts/auth_google.py`).

Este documento es **la** guía operativa de punta a punta. Si nunca viste
el proyecto, leelo en orden: el capítulo 0 te lleva de cero a un sistema
funcionando. Si ya lo conocés, andá directo al capítulo que necesites.

**Índice**

0. [Arranque desde cero (primera vez)](#0-arranque-desde-cero-primera-vez)
1. [Qué es Cognitive OS, de principio a fin](#1-qué-es-cognitive-os-de-principio-a-fin)
2. [Cómo arranca y cómo se apaga](#2-cómo-arranca-y-cómo-se-apaga)
3. [El frontend, vista por vista](#3-el-frontend-vista-por-vista)
4. [Pipelines internos (qué pasa cuando hacés click)](#4-pipelines-internos)
5. [Usarlo desde Telegram (37 comandos)](#5-usarlo-desde-telegram-37-comandos)
6. [Ejemplos impresionantes para sacarle el máximo](#6-ejemplos-impresionantes)
7. [Qué hace el agente y qué NO hace](#7-qué-hace-el-agente-y-qué-no-hace)
8. [Perfiles de operación: estricto vs PC dedicado](#8-perfiles-de-operación-estricto-vs-pc-dedicado)
9. [Matriz de acciones (qué pide aprobación, cómo aflojarla)](#9-matriz-de-acciones-qué-pide-aprobación-cómo-aflojarla)
10. [Seguridad operativa en una página](#10-seguridad-operativa-en-una-página)
11. [Troubleshooting express](#11-troubleshooting-express)

---

## 0. Arranque desde cero (primera vez)

Esta sección te lleva de un repo recién clonado a un Cognitive OS
funcionando. Si seguís los pasos en orden, no necesitás saber nada más
para empezar.

### 0.1 Requisitos de la máquina

- **Python ≥ 3.12** y [`uv`](https://docs.astral.sh/uv/) (gestor de
  entornos/paquetes).
- **Node.js ≥ 22** y `npm`.
- **Docker** + `docker compose` (para Postgres, Redis, Weaviate, Neo4j).
- Linux o macOS. (En Windows, usá WSL2.)

Verificá: `uv --version`, `node --version`, `docker --version`.

### 0.2 Credenciales: qué es obligatorio y qué es opcional

El sistema arranca con **placeholders `CHANGEME`** y *degrada con
elegancia*: lo que no tiene credencial queda `disabled`/`blocked`, nunca
rompe el arranque. Hay dos clases de credencial:

- **REQ (requeridas para operar el núcleo):** secreto JWT, password de
  Postgres, key del LLM primario, key de embeddings. Sin estas el chat y
  el RAG no funcionan, pero la API igual levanta.
- **OPT (opcionales, habilitan capacidades):** Google
  (Calendar/Drive/Maps), GoDaddy DNS, Gmail, ElevenLabs (voz),
  LangSmith, Telegram, mail multicuenta. Cada una habilita su vista; sin
  ella, esa vista muestra `disabled` con el motivo exacto.

**El wizard te dice exactamente qué falta:**

```bash
cd cognitive-os
bash scripts/init_credentials.sh        # checklist REQ/OPT/OK legible
bash scripts/init_credentials.sh --ci   # exit≠0 si falta algún REQ (para CI)
```

Salida típica: una tabla con cada credencial, su estado
(`OK` / `falta` / `opcional`), qué capacidad habilita y **dónde
obtenerla** (URL del panel del proveedor). Nunca imprime valores.

### 0.3 Configurar el `.env`

```bash
cp .env.example .env          # plantilla con todas las variables comentadas
# editá .env y reemplazá al menos los REQ:
#   JWT_SECRET=<cadena larga aleatoria>
#   POSTGRES_PASSWORD=<password fuerte>
#   PRIMARY_LLM_API_KEY=<tu key del LLM>
#   EMBEDDINGS_API_KEY=<tu key de embeddings>
```

Cada variable está documentada 1:1 en
`docs/SETTINGS_REGISTRY_TABLE.md` (autogenerada desde `core/config.py`,
no se edita a mano) y explicada en
`docs/OPERATOR_VARIABLE_CHECKLIST.md`.

> **Regla de oro de seguridad:** en `ENVIRONMENT=production` la
> configuración **rechaza** el arranque si quedó algún `CHANGEME` en un
> campo sensible, si falta cifrado de `payload_executable`, o si una
> capacidad externa (browser/computer/mail/godaddy/calendar/drive) no
> exige aprobación humana. Es a propósito: producción no admite atajos.

### 0.4 Levantar la infraestructura de datos

```bash
cd infra
docker compose --env-file ../.env up -d
# Postgres 16+pgvector, Redis 7, Weaviate 1.29.0, Neo4j 5
# TODOS publicados solo en 127.0.0.1 (no expuestos a la LAN)
docker compose ps      # esperá a que estén healthy
```

### 0.5 Migraciones y backend

```bash
cd ../backend
uv sync                                  # instala dependencias del backend
uv run alembic upgrade head              # aplica las 17 migraciones
uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000
```

En otra terminal, el worker de Celery (procesa jobs largos, ingesta,
mail, code builds):

```bash
cd cognitive-os/backend
uv run celery -A cognitive_os.workers.celery_app worker \
  -Q default,ingestion,agent_longrun,maintenance,mail
```

Y el beat (tareas periódicas: reaper de aprobaciones, consolidación de
memoria, sync de mail, recordatorios):

```bash
uv run celery -A cognitive_os.workers.celery_app beat
```

### 0.6 Frontend

```bash
cd ../frontend
npm ci
PORT=3001 npm run dev   # http://localhost:3001 (los launchers ya usan 3001)
```

> **Puerto 3001 (no 3000):** desde Fase 68 el frontend corre en
> **`:3001`** porque el operador usa OpenChamber en `:3000`. Los
> ejecutables de escritorio ya lanzan en 3001 y el CORS del backend
> permite ambos. Un `npm run dev` sin `PORT` usaría 3000 por defecto
> (chocaría con OpenChamber); por eso se fija `PORT=3001`.

Abrí `http://localhost:3001`. Es una **PWA**: el navegador te va a
ofrecer "Instalar Cognitive OS" para usarla como app de escritorio, y
funciona offline para el shell (las APIs requieren conexión).

### 0.7 Conseguir un JWT y entrar

El frontend pide un **token JWT local** (sin prefijo `Bearer`) en el
TopBar. Generá uno:

```bash
cd cognitive-os/backend
uv run python -c "from cognitive_os.core.auth import create_access_token; \
print(create_access_token(user_id='operator', roles=['admin']))"
```

Pegá ese token en el TopBar del panel (o en la pestaña *Conexión*).
Listo: las consultas autenticadas se activan y el Dashboard empieza a
mostrar datos en vivo.

### 0.8 (Opcional) Google Calendar/Drive/Maps

Si vas a usar Google Ops:

```bash
# En .env: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, ENABLE_GOOGLE_CALENDAR=true, etc.
cd cognitive-os/backend
uv run python scripts/auth_google.py    # 1 click en el navegador, 1 sola vez
```

El script es **self-healing**: si ya hay un `token.json` válido, refresca
sin abrir navegador. Si falta, te da el comando exacto. Maps solo
necesita `GOOGLE_MAPS_API_KEY` (no OAuth).

### 0.9 (Opcional) Telegram

```bash
# En .env:
#   TELEGRAM_ENABLED=true
#   TELEGRAM_BOT_TOKEN=<token de @BotFather>
#   TELEGRAM_AUTHORIZED_USER_IDS=<tu user_id numérico de Telegram>
#   TELEGRAM_ASSIST_USER_MAP=<chat_id:user_id opcional para /tasks /notes>
cd cognitive-os/backend
uv run python -m cognitive_os.integrations.telegram_bot
```

(Los ejecutables de escritorio levantan el bot automáticamente si
`TELEGRAM_ENABLED=true`.) Mandale `/start` al bot: si tu user_id está en
la allow-list, te responde con los 37 comandos.

### 0.10 Verificación de que todo está sano

```bash
cd cognitive-os
bash scripts/full-qa.sh                  # pytest + ruff + mypy + frontend build
# Esperado: 685 passed, 1 skipped, 20 deselected; todo verde
```

En el panel, andá a **Health**: cada componente (db, redis, weaviate,
neo4j, celery, broker, Google tokens, mail) debe estar `ok` o
`disabled` (no `degraded`). Si algo está `degraded`, el detalle trae el
comando exacto para arreglarlo.

**A partir de acá ya tenés un Cognitive OS funcionando.** El resto de la
guía explica todo lo que podés hacer con él.

---

## 1. Qué es Cognitive OS, de principio a fin

**Definición de una línea.** Cognitive OS es un sistema operativo
cognitivo local-first para vos, el operador: un cerebro de agentes
LangGraph + DeepAgents conectado a tu mail, tu navegador, tu
computador, tus documentos legales, Google Workspace, GoDaddy y a
coding agents externos — todo bajo aprobación humana, con auditoría y
budget caps, ejecutándose en `127.0.0.1`.

**De qué se compone, de arriba abajo:**

- **Backend FastAPI 0.115+** (Python 3.12, `uv`): **131 endpoints REST**
  bajo JWT, rate-limited en los endpoints calientes. Es el cerebro y la
  sala de máquinas.
- **Orquestación LangGraph 1.1.10** con grafo principal
  (`Planner → Researcher → Synthesizer → Scorer`) y subgrafos
  especializados (mail, browser, computer, calendar, drive, social,
  legal). Cada nodo respeta la `tool policy` y deja `JobEvent` +
  `AuditEvent`.
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
  estado de grafo LangGraph), **Redis 7** (cache, rate limit backend
  opcional, broker Celery), **Weaviate 1.29.0** (búsqueda híbrida
  vectorial + BM25), **Neo4j 5** (grafo de conocimiento / GraphRAG).
- **Frontend Next.js 16.2.6** con **20 vistas** en `app/views/*.tsx`
  (ver §3). PWA instalable, SSE-over-fetch para tiempo real, hotkeys
  1-9, paleta de comandos Ctrl-K, tema claro/oscuro, nav móvil.
- **Canal humano fuera del panel**: bot de **Telegram** (long-poll, sin
  webhook, funciona detrás de NAT). Espejado con el REST — el mismo
  `AuditEvent` se escribe para una decisión hecha por panel o por bot.
- **Ejecutables de escritorio** (`Levantar/Reiniciar/Detener/Estado
  Cognitive OS.sh` y sus `.desktop`) que levantan o apagan toda la pila
  incluyendo el worker `mail` y Kimi WebBridge. Verificables sin
  levantar servicios con `bash scripts/verify_desktop_launchers.sh`.
- **Política transversal**: nada sensible se ejecuta sin
  `HumanApproval` + `AuditEvent`. Las pendientes que envejecen >48 h las
  cierra el reaper. Decisiones críticas tienen four-eyes opcional.
  Correlación por `X-Request-ID`. Dispatch a Celery es **idempotente**
  (reserva atómica `dispatch_state` antes de `apply_async`).

**Filosofía. Tres líneas:**

1. **Vos sos el dueño.** El sistema vive en tu máquina, con tus
   credenciales, en `127.0.0.1`. No hay tenant, no hay multi-cliente.
2. **Aprobás antes de gastar.** Tokens, dinero, mails y cambios
   externos pasan por `HumanApproval`. `dedicated_local` auto-aprueba
   sólo lo reversible (carpetas Drive, upload propio); todo lo
   irreversible (mail send, drive_organize, browser, code_build,
   openshell) sigue pidiendo tu OK.
3. **Si algo falla, falla con red, no en el aire.** Circuit breakers,
   fail-open en rate limit, fallback heurístico en planificación,
   manifest en cada artefacto, reaper para jobs colgados, dispatch
   idempotente.

---

## 2. Cómo arranca y cómo se apaga

**Modo escritorio (recomendado, lo más simple):**

```
~/Escritorio/Levantar Cognitive OS.sh    # backend + worker + beat + mail + WebBridge + frontend + Telegram*
~/Escritorio/Estado Cognitive OS.sh      # ¿qué hay vivo?
~/Escritorio/Reiniciar Cognitive OS.sh   # ciclo limpio
~/Escritorio/Detener Cognitive OS.sh     # apaga todo
```

\* Telegram solo arranca si `TELEGRAM_ENABLED=true`. Smoke reproducible
de estos launchers: `bash scripts/verify_desktop_launchers.sh` (no
levanta servicios; valida maestro + wrappers `.sh` + accesos `.desktop`).

**Modo manual:** ver §0.4–§0.6. El detalle por componente vive en
`docs/RUNBOOK.md`.

`uv run cognitive-os` es solo un bootstrap mínimo (imprime un log y
sale); **no** levanta la API.

---

## 3. El frontend, vista por vista

20 vistas, agrupadas en la barra lateral. Para cada una: **qué hace
exactamente**, **qué cambia al hacer click**, **dónde queda registro**.
Hotkeys 1-9 saltan a las vistas más usadas; Ctrl-K abre la paleta de
comandos (buscás cualquier vista o acción por nombre).

### Overview

#### Dashboard (◧, hotkey 1)
- **Qué hace:** snapshot vivo de la pila — health agregada, jobs
  corriendo, aprobaciones pendientes, últimos audit events, stats de
  conocimiento (docs/chunks).
- **Click típico:** solo lectura; los botones de navegación te llevan a
  la vista correspondiente.
- **Pipeline:** poll cada N s a `/health/dashboard`, `/jobs`,
  `/approvals`, `/audit/events`, `/knowledge/stats`.

### Agentes

#### Chat (◇, hotkey 2)
- **Qué hace:** conversación con el orquestador LangGraph (thread
  persistido en Postgres). Rutas: `chat`, `agent_research`,
  `agent_research_legal`, `document_analysis`.
- **Click "Enviar":** crea o continúa un thread, dispara el grafo,
  streamea tokens vía SSE, retorna mensaje + ruta + citas.
- **Si el grafo pide aprobación humana:** se detiene en `interrupt(...)`,
  vas a *Aprobaciones*, decidís, y el thread se reanuda con
  `/threads/{id}/resume`.

#### DeepAgents (✱)
- **Qué hace:** estado del subagente DeepAgents — memoria, tools
  habilitadas, política efectiva, actividad reciente por job_type.
- **Click "Toggle skill":** propone activar/desactivar una skill →
  `HumanApproval` → al aprobar entra en `enabled_skills`.

#### Skills (✸)
- **Qué hace:** lista las **13 skills core** + las user. Core:
  - **Generales:** `citation-discipline`, `contradiction-detector`,
    `evidence-matrix`, `legal-draft-careful`, `rag-research`,
    `report-writer`, `sandbox-code-analysis`, `timeline-builder`.
  - **Legal pack (adaptado de
    [claude-for-legal](https://github.com/anthropics/claude-for-legal),
    Apache 2.0):** `legal-hold`, `privilege-log-review`,
    `oss-license-review`, `worker-classification`, `matter-intake`.
- **Click "Proponer":** crea propuesta + `HumanApproval` desde un
  `SKILL.md` montado. Sin aprobar, **no se ejecuta**.

#### Memoria (◉)
- **Qué hace:** consolidación, propuestas pendientes, búsqueda por
  query, export.
- **Click "Consolidar ahora":** dispara
  `cognitive_os.consolidate_all_deepagent_memory` en `maintenance`.
- **Click "Aprobar propuesta":** la promueve a memoria persistente.

#### Asistente (◌)
- **Qué hace:** tareas y notas personales del operador. Mapeo
  chat Telegram → user vía `TELEGRAM_ASSIST_USER_MAP`.
- **Click "+ Tarea":** crea entrada con due-date/recordatorio
  opcional; aparece también en `/tasks` por Telegram. Las notas se
  indexan en Weaviate y son buscables (`/assist/notes/search`).

#### Mail (✉)
- **Qué hace:** inbox unificado GoDaddy IMAP + Gmail label `TODOS`.
  Clasifica (important/normal/spam/promo) y propone respuestas
  redactadas con su rationale.
- **Click "Enviar":** **NO envía directo** — pasa por `HumanApproval`
  (`MAIL_REQUIRE_APPROVAL_FOR_SEND=true`). Recién al aprobar, el worker
  `mail` hace el SMTP/Gmail send y deja `AuditEvent` + `mail_send_logs`.

### Conocimiento

#### Documentos (▦, hotkey 3)
- **Qué hace:** ingesta de PDFs al RAG (Postgres + pgvector + Weaviate +
  Neo4j para entidades). Dedup por sha256.
- **Click "Ingestar":** encola `cognitive_os.ingest_document` en
  `ingestion`. Los chunks quedan `pending_index` hasta que Weaviate
  confirma; ahí pasan a `indexed`. Resultado en *Jobs*.

#### Document Analysis (◈, hotkey 4)
- **Qué hace:** análisis legal estructurado en 6 modos:
  `evidence_matrix`, `timeline`, `contradictions`, `full_report`,
  `legal_draft_support`, `case_summary`.
- **Click "Ejecutar":** job en `agent_longrun`; produce artefactos
  descargables (JSON/MD/CSV/DOCX) y eventos SSE en vivo. Si el quality
  score < 85 o hay borradores, se crea `HumanApproval` automático.

### Operaciones

#### Jobs (▶, hotkey 5)
- **Qué hace:** lista todos los jobs (ingesta, research, code build,
  mail send, analysis, sandbox...). Cada uno con estado, progreso,
  eventos SSE y artefactos.
- **Click "Cancelar":** marca el job `cancelled` (idempotente), queda
  en audit.

#### Aprobaciones (✓, hotkey 6)
- **Qué hace:** **la vista más importante.** Todo cambio sensible
  espera aquí con su preview/diff.
- **Click "Aprobar":** desbloquea el job/grafo/correo/ActionRequest. Si
  era un `execute_action_request:<id>`, encola y despacha el worker.
- **Click "Rechazar":** corta la ejecución con razón persistida y
  cascada al Job/ActionRequest.
- Con `APPROVAL_REQUIRE_FOUR_EYES=true`, el aprobador debe ser distinto
  del solicitante.
- Las que superan `APPROVAL_PENDING_MAX_HOURS=48` las cierra el reaper.

#### Google Ops (⌖)
- **Qué hace:** Maps (read-only: tráfico, ETA, severidad, consejo de
  ruta, alternativas, link), Calendar (listar eventos + free/busy +
  solicitar evento), Drive (buscar por nombre/contenido, validar carpeta
  de entregables, solicitar upload, previsualizar/solicitar organización
  de archivos). **Todos los writes van por `ActionRequest` + aprobación.**
- **Click "Calcular ruta":** read-only, devuelve plan con tráfico.
- **Click "Crear solicitud aprobable" (evento):** crea
  `calendar_create_event`; recién al aprobar toca el calendario real
  (doble compuerta: `ENABLE_GOOGLE_CALENDAR_WRITE` + aprobación).
- **Click "Crear solicitud de carpeta":** crea `drive_ensure_folder`.
- **Click "Solicitar organización":** crea `drive_organize_files`; no
  borra archivos ni cambia permisos.

#### Research (⌕)
- **Qué hace:** investigación con plan animado en vivo (SSE). Con
  `ENABLE_OPENHARNESS_RESEARCH=true` usa **OpenHarness** como preludio
  (`OPENHARNESS_RESEARCH_PIPELINE=prelude_merge` por defecto).
- **Click "Iniciar":** Planner → N Researchers en paralelo (cap
  `RESEARCH_MAX_PARALLEL_WORKERS`) → Synthesizer (dedup de citas) →
  Scorer (rúbrica auditable). Cancelable. Cada citation enlaza al
  fragmento fuente.

#### Code Director (⟐)
- **Qué hace:** le das un objetivo de alto nivel y delega la
  codificación a coding agents externos: **Claude Code CLI, Codex CLI,
  Kimi CLI o DeepAgents in-process**. Vos no escribís ningún prompt.
- **Click "Planificar":** el **LLMPlanner** descompone el objetivo en
  subtareas reales con dependencias; si el LLM falla por cualquier razón
  (sin key, JSON malformado, deps alucinadas) cae al `HeuristicPlanner`
  determinista. **Cero tokens gastados todavía.**
- **Aprobás** el plan en *Aprobaciones*.
- Al aprobar: encola `cognitive_os.run_code_build` en `agent_longrun`.
  Cada subtarea recibe un prompt acotado con árbol del workspace +
  contenido relevante + output de sus dependencias. Si una falla, el
  reintento lleva el error literal con "arregla esto, no empieces de
  cero".
- **Click "Descargar":** `tar.gz` del workspace con manifest.
- **Budget caps duros**: exceder runtime/calls/cost cierra el build como
  `partial` y **igual entrega lo construido**. Adapters CLI: STDIN-only
  (no fuga en `ps`), `SIGTERM→SIGKILL` del process group al timeout.

#### Sandbox (▢)
- **Qué hace:** ejecuta código aislado en **OpenShell** (opt-in
  `ENABLE_OPENSHELL_SANDBOX=true`). Deshabilitado por defecto; en
  producción exige aprobación humana, runtime ≤900s y sin red.
- **Click "Run":** cápsula efímera, captura stdout/stderr/exit.

### Observabilidad

#### LangSmith (⌬, hotkey 7)
- **Qué hace:** trazas en vivo de cada nodo del grafo, proyectos y runs.
  Útil para entender por qué un thread devolvió X. Puede exigir admin
  (`LANGSMITH_ENDPOINTS_REQUIRE_ADMIN`).

#### Audit log (≡, hotkey 8)
- **Qué hace:** stream de `AuditEvent` filtrable por actor, acción,
  recurso. Todo cambio externo deja huella aquí, sin importar si vino
  de panel o de Telegram (`actor="telegram:<chat_id>"`).

#### Health (♡, hotkey 9)
- **Qué hace:** salud por componente con latencia y `write_enabled`
  donde aplica. Si algo está `degraded`, te dice el comando exacto para
  arreglarlo.

### Configuración

#### Sistema (⚒) — ConfigurationView
- **Qué hace:** flags no-secretos (policy, feature toggles) e inventario
  de las 21 credenciales operador con estado, capacidad habilitada y
  *dónde obtenerlas*. **Nunca muestra valores de secretos.**

#### Conexión (⚙) — SettingsView
- **Qué hace:** apunta el panel a otra API (consumir el backend desde
  otra máquina de la LAN vía túnel), pega el JWT, alterna tema. Persiste
  en `localStorage`.

---

## 4. Pipelines internos

Tres pipelines que conviene tener en la cabeza.

### A) Pipeline `Action Plane` (acciones externas)

```
Vista (frontend) ─► POST /actions/.../request   (crea ActionRequest pending_approval)
                  └─► HumanApproval ligada (+ Job)
                       │
                       ▼  Aprobación (panel o /approve por Telegram)
                  queue_approved_action_request()  → status=queued
                       │
                       ▼  reserve_action_dispatch()  → dispatch_state=submitting
                  apply_async() en agent_longrun / mail
                       │
                       ├─► Ejecutor (mail SMTP, Calendar API, Drive API, DNS, ...)
                       ├─► AuditEvent (qué, quién, cuándo)
                       └─► JobEvents (SSE) hasta estado terminal
```

- Si Celery/Redis no acepta el dispatch: respuesta `dispatched=false`,
  `JobEvent action_request_dispatch_failed`, `dispatch_state=failed` →
  podés reintentar cuando el stack esté sano.
- Si lo acepta: `action_request_dispatch_submitted`,
  `dispatch_state=submitted` → el worker no se re-ejecuta aunque el
  broker entregue duplicado (short-circuit si el job ya está `running`).
- La reserva atómica con `SELECT ... FOR UPDATE` impide dos
  `apply_async()` simultáneos.
- **Regla:** nada toca el mundo externo sin pasar por este pipe.

### B) Pipeline `Research` (lectura intensiva)

```
Chat / Research view
   └─► LangGraph: Planner → (Researcher × N en paralelo) → Synthesizer → Scorer
        ├─ Si ENABLE_OPENHARNESS_RESEARCH=true → preludio QueryEngine antes de DeepAgents
        ├─ Tools: RAG local (Postgres+pgvector), Weaviate (híbrido + BM25 fallback), Neo4j, web fetch
        ├─ Si DeepAgent devuelve answer vacío → fallback RAG determinista
        ├─ Cada citation enlazada al documento fuente (basename, no path absoluto)
        └─ Output: respuesta + citas + score (rúbrica auditable)
```

### C) Pipeline `Code Director` (delegar a coding agents)

```
POST /code-director/run  (objective + adapter_preference + budget)
   └─► LLMPlanner.plan() → BuildPlan (subtareas reales con dependencias)
        └─ fallback: HeuristicPlanner si el LLM falla por cualquier razón
   └─► Job(code_build, waiting_approval) + HumanApproval   (cero tokens hasta aquí)
   ──── Aprobás ─────────────────────────────────────────────
   └─► Celery run_code_build en agent_longrun
        └─ topo-sort subtareas → por cada una:
             ├─ build_subtask_prompt(workspace + upstream + last_error)
             ├─ Adapter (claude_code | codex | kimi | deepagent)
             │   ├─ STDIN-only para CLIs (no fuga de prompt en `ps`)
             │   └─ SIGTERM→SIGKILL del process group al timeout
             ├─ StepResult → si falla y iterate_until_tests_pass:
             │   └─ reintento con prompt error-dirigido (no replay)
             └─ budget tracker (calls / runtime / cost) — exceder = partial
   └─► Empaqueta workspace en tar.gz + _codedirector_manifest.json
   └─► GET /code-director/{id}/download
```

---

## 5. Usarlo desde Telegram (37 comandos)

> **Nota:** el sistema integra **Telegram** (long-poll, sin webhook,
> funciona detrás de NAT). **No** integra Instagram ni otras redes.

**Setup mínimo:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ENABLED=true`,
`TELEGRAM_AUTHORIZED_USER_IDS=<tu user_id>` y opcionalmente
`TELEGRAM_ASSIST_USER_MAP` (mapea chat_id → user para tareas/notas). El
bot arranca con la pila completa.

El bot **rechaza** cualquier user_id que no esté en la allow-list y
deja claro por qué. Todo comando entra por el **mismo servicio que el
REST**, así que hereda la misma `tool policy`, los mismos
`HumanApproval` y el mismo `AuditEvent`.

### 5.1 Tabla completa de comandos (paridad con el panel)

| Comando | Hace | Vista equivalente |
|---|---|---|
| `/start`, `/help` | bienvenida + lista de comandos | — |
| `/health` | componentes ok/degraded con latencia | Health |
| `/stats` | docs/chunks/jobs/aprobaciones | Dashboard |
| `/config` | flags no-secretos + LLM/embeddings | Sistema |
| `/capabilities` | flags del Action Plane (browser/computer/maps/calendar/drive/godaddy/mail/research/sandbox/voice/webbridge) | Sistema |
| `/agents` | estado DeepAgents + jobs por tipo | DeepAgents |
| `/skills` | skills habilitadas con versión/riesgo | Skills |
| `/memory` | propuestas de memoria pendientes | Memoria |
| `/consolidate` | encola consolidación de memoria | Memoria |
| `/jobs` | últimos 10 jobs | Jobs |
| `/job <id>` | detalle + últimos eventos (acepta prefijo) | Jobs |
| `/cancel <id>` | cancela un job (idempotente) | Jobs |
| `/codebuild [max]` | últimos code-director builds | Code Director |
| `/sandbox` | estado OpenShell sandbox | Sandbox |
| `/approvals` | aprobaciones pendientes | Aprobaciones |
| `/approve <id>` | aprueba (UUID o prefijo único; four-eyes; despacha ActionRequest aprobado) | Aprobaciones |
| `/reject <id>` | rechaza con cascada a Job/ActionRequest | Aprobaciones |
| `/threads` | threads LangGraph recientes | Chat |
| `/chat <mensaje>` | habla con el orquestador (mismo grafo que la vista Chat) | Chat |
| `/ingest <ruta>` | encola ingesta de un PDF absoluto | Documentos |
| `/documents [max]` | documentos ingestados (estado/páginas/chunks) | Documentos |
| `/research [max]` | research runs recientes con estado y query | Research |
| `/runs` | últimas trazas LangSmith | LangSmith |
| `/audit [max]` | últimos audit events (actor/acción/recurso) | Audit |
| `/tasks`, `/task <texto>`, `/done <id>` | tareas personales | Asistente |
| `/notes`, `/note <título \| cuerpo>` | notas Markdown | Asistente |
| `/mail [max]` | bandeja mail multicuenta (estado/clasificación) | Mail |
| `/gmaildigest` | digest Gmail read-only (requiere `GMAIL_READ` + token) | Mail |
| `/maps <origen \| destino>` | ruta con tráfico, ETA, advice y link (read-only) | Google Ops |
| `/calendar [max]` | próximos eventos de calendar | Google Ops |
| `/freebusy [días]` | bloques ocupados de `primary` | Google Ops |
| `/drive <query>` | buscar archivos en Drive (nombre + contenido) | Google Ops |

Cada comando con capacidad asociada **respeta el gating**: si
`MAIL_ENABLED=false`, `/mail` lo dice; si Maps no tiene API key,
`/maps` devuelve el motivo exacto; si el sandbox está apagado,
`/sandbox` lo informa. Nunca explota: degrada con mensaje claro.

### 5.2 Sintaxis de argumentos

- `[max]` = entero opcional acotado (ej. `/calendar 15`,
  `/documents 5`). Fuera de rango se clampa; texto inválido usa el
  default.
- `/maps Buenos Aires | Córdoba` — origen y destino separados por `|`.
- `/task Comprar café | con detalle opcional tras la barra`.
- `/note Título de la nota | cuerpo markdown opcional`.
- `/approve ab12cd` — acepta el UUID completo **o** un prefijo único
  (mínimo 4 chars). Prefijo ambiguo/corto/inválido → mensaje claro, no
  acción.

### 5.3 Casos prácticos

- Te llega push "ApprovalPending #ab12cd…" → `/approve ab12cd` desde el
  colectivo. Si era un ActionRequest, se despacha solo a `agent_longrun`.
- "¿Qué está corriendo?" → `/jobs`, luego `/job <id>` para el detalle.
- "¿Tengo libre el jueves a la tarde?" → `/freebusy 3`.
- "¿Cómo llego a la reunión?" → `/maps Mi casa | Av. Corrientes 1234`.
- Querés meter un PDF al RAG sin abrir el laptop → `/ingest /ruta/al.pdf`,
  seguilo con `/job`.
- Auditoría rápida de qué tocó el sistema hoy → `/audit 30`.

**Simetría garantizada:** un `/approve` por Telegram deja el mismo
`AuditEvent` (`actor="telegram:<chat_id>"`) que una aprobación por
panel. Four-eyes, reaper y dispatch idempotente funcionan igual.

---

## 6. Ejemplos impresionantes

### 6.1 "Codificame una app con 2 RAGs y un frontend usando Claude Opus 4.7"

1. **Code Director** → Objetivo: "App con 2 RAGs (uno transacciones, uno
   documentos legales) + frontend Next.js + FastAPI; tests; Docker
   compose." Adapter: `default_adapter=claude_code`,
   `default_model=claude-opus-4-7`, `reviewer_adapter=codex`. Budget:
   `max_total_llm_calls=80`, `max_total_cost_usd=20.00`.
2. **Planificar** → LLMPlanner devuelve algo como
   `db-schema → rag-tx → rag-legal → api → frontend → tests → review`
   (orden por dependencia). **Cero tokens gastados todavía.**
3. **Aprobaciones** → revisás el plan, **Aprobar** (o `/approve <id>`).
4. Timeline SSE en vivo: cada subtarea a su CLI. Si `rag-legal` falla
   por `ImportError`, el reintento lleva el error literal y "no empieces
   de cero" → corrige en el segundo intento.
5. **Descargar `tar.gz`** con workspace + manifest.

### 6.2 "Negociá mis reuniones de mañana sin que toque calendar yo"

1. **Chat** → "Mirá mi calendar de mañana, contesta los pendientes de
   GoDaddy/Gmail con horarios libres de la mañana; sugerime 3 slots por
   reunión, dejame aprobar antes de mandar."
2. El grafo: Calendar free/busy → mail inbox → drafter → propone slots
   → **`HumanApproval` por cada borrador**.
3. Aprobás los que quieras desde *Aprobaciones* o `/approve <id>` → el
   worker `mail` envía → `AuditEvent` + `mail_send_logs`.

### 6.3 "Análisis legal de 6 PDFs de demanda"

1. **Documentos** → ingestá los 6 PDFs (`/ingest` o la vista).
2. **Document Analysis** → modo `evidence_matrix` → seleccionás docs →
   **Ejecutar** → XLSX con matriz + citas verificadas.
3. Modo `contradictions` → DOCX con cada contradicción referenciada
   `doc/página`. Modo `timeline` → cronología consolidada.
4. Todo descargable desde *Jobs* (JSON/MD/CSV/DOCX).

### 6.4 "Investigá X profundo, citado, en 4 minutos"

1. **Research** → query + `ENABLE_OPENHARNESS_RESEARCH=true`.
2. Plan animado: Planner expone subpreguntas, N Researchers en paralelo,
   Synthesizer arma, Scorer puntúa contra rúbrica.
3. Cada citation es clickable al fragmento exacto del documento fuente.

### 6.5 "Operador con manos atadas" (solo Telegram)

Estás fuera de casa, el laptop apagado, el server corriendo. Por el bot:
`/jobs` para ver qué hay, `/approve <id>` para desbloquear un mail
crítico, `/ingest /ruta.pdf` para meter un contrato al RAG, `/maps casa
| oficina` para la ruta, `/freebusy 2` para ver tu agenda, `/audit 20`
para revisar qué tocó el sistema. Todo deja el mismo audit que el panel.

### 6.6 "Organizá mi Drive de entregables"

1. **Google Ops** → "Validar carpeta de entregables" (preview, no toca
   nada) → "Crear solicitud de carpeta" (`drive_ensure_folder`).
2. Buscás por nombre/contenido, "Preview organización" muestra qué se
   movería, "Solicitar organización" crea `drive_organize_files`.
3. Aprobás → el worker mueve archivos a la carpeta destino. **No borra
   ni cambia permisos.**

---

## 7. Qué hace el agente y qué NO hace

### Hace

- **Investigación con citas verificadas** (RAG local + Weaviate híbrido
  + Neo4j + opcional OpenHarness preludio; fallback BM25 y RAG
  determinista).
- **Análisis legal estructurado**: matriz evidencia, contradicciones,
  timeline, full report, draft support, case summary.
- **Mail personal multicuenta** (GoDaddy IMAP/SMTP + Gmail label
  `TODOS`): leer, clasificar, redactar borradores. **Envía solo con
  aprobación humana.**
- **Google Workspace**: Maps (read-only con tráfico), Calendar (eventos,
  free/busy, write bajo `ActionRequest`), Drive (búsqueda, nube de
  entregables, upload, organización bajo `ActionRequest`).
- **Navegador**: `browser_preview` (screenshot/lectura multimodal),
  `browser_interactive` (Playwright bajo allow-list).
- **Computador local**: `computer_organize` (mover/renombrar bajo
  política y allow-list), `computer_inventory` (read-only).
- **Documentos Office**: DOCX/XLSX/PPTX con assets controlados
  (`DOCUMENT_OUTPUT_ROOT`, `DOCUMENT_MAX_SIZE_BYTES`); fórmulas XLSX
  seguras, sanitización anti-inyección.
- **Delegar codificación** (Code Director): Claude Code/Codex/Kimi CLIs
  o DeepAgents in-process; plan LLM-driven; prompts con contexto vivo;
  reintentos error-dirigidos; budget caps.
- **Skills** y **memoria persistente** con propuesta + aprobación.
- **Sandbox de código** (OpenShell, opt-in).
- **Telegram bot** simétrico al panel (mismo audit), 37 comandos.

### NO hace

- **No envía dinero ni hace pagos.** No hay integración financiera.
- **No toca tu SO sin permiso.** `computer_organize` requiere política +
  allow-list; sin eso es no-op.
- **No publica en redes sociales por su cuenta.** El subgrafo social
  *clasifica* y *propone*; el envío no está cableado a ninguna API.
- **No usa Instagram.** El único canal humano externo es Telegram.
- **No ejecuta código arbitrario fuera del sandbox.** El Code Director
  escribe en su workspace aislado.
- **No sube nada a la nube salvo lo que autorices.** Las llamadas LLM
  van a los endpoints que configuraste; el código generado vive local.
- **No gasta tokens sin tu aprobación** en flujos críticos (Code
  Director, mail send, ActionRequest Google).
- **No tiene multi-tenant.** Es para vos, en `127.0.0.1`. No expongas el
  puerto a internet.
- **No reemplaza tu juicio.** Aprobás vos.

---

## 8. Perfiles de operación: Estricto vs PC dedicado

Cognitive OS soporta dos **perfiles operativos**. Lo elegís con una
variable de `.env`; el resto del sistema se ajusta solo. El perfil
aparece reflejado en `/config/public` y en el header del panel para que
sepas dónde estás parado.

```
OPERATOR_PROFILE=strict           # ← histórico (default)
# OPERATOR_PROFILE=dedicated_local
```

### Perfil `strict` (default)

Pensado para máquinas compartidas, operación remota, o cuando el
operador no es dueño exclusivo del PC. Posturas:

| Capacidad | Comportamiento |
|---|---|
| `require_human_approval_for_external_actions` | `true` |
| `approval_require_four_eyes` | `true` (aprobador ≠ solicitante) |
| `approval_pending_max_hours` | `48 h` (reaper cierra pendientes viejas) |
| `code_director_budget_mode` | `soft` (build termina `partial`, no crash) |
| `mail_require_approval_for_send` | `true` |
| `browser_allowed_domains` / `kimi_webbridge_allowed_domains` | lista explícita |
| `computer_allowed_roots` | acotado |

### Perfil `dedicated_local` (PC dedicado al agente, tu perfil de Edge)

Pensado para el caso real: un PC dedicado al agente, con **tu perfil de
Edge real** (Google, Outlook, banca, GoDaddy, todo logueado). En este
contexto, "fricción" sin daño irreversible es ruido. El perfil afloja
silenciosamente lo que **no rompe nada en frío** y deja **visible** lo
que sí tiene cola de regret.

| Capacidad | `dedicated_local` | Razón |
|---|---|---|
| `require_human_approval_for_external_actions` | `false` | acciones rutinarias sin click extra |
| `approval_require_four_eyes` | `false` | un solo operador, no tiene sentido |
| `approval_pending_max_hours` | `168 h` (1 semana) | aprobás cuando podés, no se expiran solas en 2 días |
| `code_director_budget_mode` | `soft` | el build termina lo que está haciendo aunque cruce el cap |
| `browser_allowed_domains` | **lo decidís vos** (default `[]`) | wildcard `*` es opción explícita, no oculta |
| `kimi_webbridge_allowed_domains` | **lo decidís vos** | mismo principio |
| `mail_require_approval_for_send` | **default `true`**, opt-out visible | mail mal enviado no se desmanda; el opt-out se ve en Health |
| `computer_allowed_roots` | **lo decidís vos** (recomendación: tu `$HOME`) | |

**Importante**: una variable explícita del operador en `.env` **siempre
gana** sobre los presets del perfil. Si ponés
`APPROVAL_REQUIRE_FOUR_EYES=true` con `dedicated_local`, four-eyes sigue
activo. El perfil solo rellena valores que dejaste en su default.

### Setup recomendado: PC de Diego (PC dedicado)

`.env` para arrancar sin fricción:

```
OPERATOR_PROFILE=dedicated_local
# Browser real (Edge) con sesiones logueadas: explícito y amplio.
# (No es un wildcard oculto: aparece en /config/public y en Health.)
KIMI_WEBBRIDGE_ALLOWED_DOMAINS=*
KIMI_WEBBRIDGE_ALLOW_MUTATIONS=true
# Permitir computer_organize sobre el home (read+plan; movimientos siguen
# pasando por approval salvo que también aflojes ese gate explícitamente).
ENABLE_COMPUTER_ACTIONS=true
COMPUTER_ALLOWED_ROOTS=/home/jgonz,/home/jgonz/Escritorio,/home/jgonz/Descargas,/mnt
# Mail send siempre pide approval — irreversible.
# Code Director: los adapters CLI heredan tu entorno por default (necesario
# para que `claude`, `codex` o `kimi` usen tus credenciales ya autenticadas
# en este PC). No hay knob para "sanitizar" — si lo necesitás en otro perfil,
# corré el agente desde un usuario distinto.
CODE_DIRECTOR_BUDGET_MODE=soft
```

**Prueba end-to-end de 15 minutos (PC de Diego, dedicated_local):**

1. `~/Escritorio/Levantar\ Cognitive\ OS.sh` — health=ok (3-4 min).
2. JWT admin: `cd backend && uv run python -c "from cognitive_os.core.auth import create_access_token; print(create_access_token(user_id='operator', roles=['admin']))"`.
3. Frontend: `http://localhost:3001` → pega el JWT en TopBar → `/config/public`
   debe mostrar `operator_profile: dedicated_local`.
4. `Chat` → "¿qué es el teorema CAP?" — respuesta limpia, sin fallback RAG.
5. `Google Ops` → calcula ruta `Plaza Italia → Aeropuerto SCL` (real).
6. `Telegram` → `/health`, `/stats`, `/maps origen | destino` (cuando tengas token nuevo).
7. `Code Director` → mini-objetivo "ScriptHelloWorld" con adapter `deepagent` → aprobá → mirá el `tar.gz`.

---

## 9. Matriz de acciones (qué pide aprobación, cómo aflojarla)

Tabla rápida de **qué corre solo** y **qué pide tu OK**. La columna
"Cómo aflojar" es la variable `.env` para reducir fricción cuando el
perfil `dedicated_local` no te alcance.

| Acción | Instantánea | Pide aprobación | Cómo aflojar |
|---|---|---|---|
| Chat / Research / Document Analysis | ✅ | — | (no aplica) |
| RAG (Weaviate + Neo4j) | ✅ | — | — |
| Google Maps (rutas / geocode) | ✅ | — | — |
| Calendar list / freebusy | ✅ | — | — |
| Drive search / get | ✅ | — | — |
| Calendar event create | — | ✅ siempre | (queda con approval; el set congelado se ejecuta exacto) |
| Drive folder ensure | ✅ bajo `dedicated_local` (auto-approve reversible) | ✅ bajo `strict` | `ENABLE_GOOGLE_DRIVE_WRITE=true` |
| Drive upload (a carpeta propia) | ✅ bajo `dedicated_local` (auto-approve reversible) | ✅ bajo `strict` | `ENABLE_GOOGLE_DRIVE_WRITE=true` |
| Drive organize (mover/renombrar) | — | ✅ siempre | toca archivos existentes — **no** está en la whitelist auto-approve |
| Mail send (GoDaddy / Gmail) | — | ✅ siempre | **irreversible** — `MAIL_REQUIRE_APPROVAL_FOR_SEND=true` es el contrato; no hay carril autosend |
| Browser preview (screenshot) | — | ✅ | allow-list `BROWSER_ALLOWED_DOMAINS` |
| Browser interactivo (Playwright) | — | ✅ | allow-list + `BROWSER_ALLOW_HEADED` |
| Kimi WebBridge (tu Edge real) | ✅ con domain en allow-list | — para reads | `KIMI_WEBBRIDGE_ALLOWED_DOMAINS=*` (dedicated_local) |
| Kimi WebBridge mutations | — | ✅ por defecto | `KIMI_WEBBRIDGE_ALLOW_MUTATIONS=true` + `KIMI_WEBBRIDGE_REQUIRE_APPROVAL=false` |
| computer_inventory (read) | ✅ | — | `ENABLE_COMPUTER_ACTIONS=true` |
| computer_organize | — | ✅ | mismo + `COMPUTER_ALLOWED_ROOTS=<dirs>` |
| GoDaddy DNS preview | ✅ | — | `GODADDY_ENABLED=true` |
| GoDaddy DNS write real | — | ✅ + flags | `GODADDY_DNS_DRY_RUN_ONLY=false` + `GODADDY_ALLOW_PRODUCTION_WRITES=true` |
| Code Director plan | ✅ | — | — |
| Code Director run | — | ✅ del plan | `CODE_DIRECTOR_BUDGET_MODE=soft` (default) |
| OpenShell sandbox | — | ✅ | `ENABLE_OPENSHELL_SANDBOX=true` |
| CapSolver (captchas) | ✅ tras solver | — | `ENABLE_CAPTCHA_SOLVING=true` |

### CapSolver — qué resuelve y cómo

CapSolver está cableado (`CAPSOLVER_API_KEY` en `.env`; capability
`captcha_solver: ready` en Health). Resuelve, vía dos tools del
DeepAgent:

| Tool | Para qué |
|---|---|
| `solve_image_captcha(image_base64)` | captcha de imagen (texto distorsionado). Le pasás el PNG/JPEG en base64 y devuelve el texto reconocido. |
| `solve_token_captcha(kind, website_url, website_key, page_action?)` | reCAPTCHA v2, reCAPTCHA v3 (con `page_action`), hCaptcha, Cloudflare Turnstile. Devuelve el token para inyectar en el form. |

Docs del proveedor: <https://docs.capsolver.com/en/guide/getting-started/>.

### Reglas que NO bajan, ni en `dedicated_local`

Las pocas cosas que el sistema no afloja aunque pongas todo en
"sin fricción" (porque no son fricción real, son cosas que pueden
romper el PC del operador o filtrar credenciales):

1. **No commitees `.env`, `token.json`, `client_secret.json`,
   `storage/`** — pre-commit corre `detect-secrets` + `gitleaks`.
2. **No corras dos backends contra la misma DB.** Pisan migraciones.
3. **No subas el `tar.gz` del Code Director a un repo sin revisarlo.**
4. **No editar a mano `SETTINGS_REGISTRY_TABLE.md`** — se regenera con
   `uv run python scripts/dump_settings_registry.py`.
5. **No expongas el puerto 8000 a internet.** El backend está atado a
   `127.0.0.1`. Acceso remoto = Tailscale/WireGuard/SSH tunnel.

---

## 10. Seguridad operativa en una página

(Mantenido como referencia para producción / strict. En `dedicated_local`
muchos de estos son configurables; la matriz de §9 lo dice por capacidad.)

- **Auth:** todo endpoint sensible exige JWT HS256 firmado con
  `JWT_SECRET`. Endpoints admin (credentials-status, LangSmith opcional)
  exigen rol admin. 132 usos de dependencia de auth sobre 131 endpoints.
- **Secretos:** nunca versionados. `pre-commit` corre `gitleaks` +
  `detect-secrets` (baseline `.secrets.baseline`, 0 findings). Los
  `SecretStr` nunca salen en respuestas. `payload_executable` se cifra
  (obligatorio en producción).
- **Rate limit:** pluggable memory/redis, fail-open. Buckets en
  approval/dispatch/create.
- **Aprobación humana:** configurable por perfil y por capacidad (§9).
  Reaper cierra pendientes >TTL y jobs `running` colgados. Sweeper
  separado de `dispatch_state` (Fase 68b) destranca reservas zombi.
- **OAuth Google scopes:** el status reporta `missing_scopes` si el
  token no tiene los necesarios (Calendar `events`, Drive `drive`); no
  finge `ready`.
- **Idempotencia:** dispatch a Celery con reserva atómica
  `dispatch_state` + sweeper; worker short-circuit si AR/job ya está
  `running` (con guard de ventana de crash); índice único parcial sobre
  ActionRequest activos.
- **Red:** Postgres/Redis/Weaviate/Neo4j publicados solo en
  `127.0.0.1`. SSRF check opcional para browser. CORS estricto.
- **Producción:** los validators de `config.py` rechazan el arranque si
  hay `CHANGEME` o falta cifrado. `dedicated_local` está pensado para
  desarrollo personal local, **no** para `ENVIRONMENT=production`.

Detalle completo en `docs/SECURITY.md`.

---

## 11. Troubleshooting express

| Síntoma | Causa probable | Comando que arregla |
|---|---|---|
| Frontend dice `no-auth` | falta/venció el JWT | regenerá el token (§0.7) y pegalo en *Conexión* |
| `Health: degraded · google` | token Google caducado | `uv run python scripts/auth_google.py` (self-healing) |
| `/maps` dice "no está disponible" | falta `GOOGLE_MAPS_API_KEY` | seteala en `.env` |
| `/mail` dice `MAIL_ENABLED=false` | mail multicuenta apagado | configurá `MAIL_*` y `ENABLE` |
| Build Code Director `failed` "adapter unavailable" | CLI no instalado/logueado | `claude --version`, `codex --version`, `kimi --version` |
| `Approval pending` desaparece sola | reaper la marcó expirada (>48 h) | volvé a generarla |
| Mail nunca sale | `MAIL_REQUIRE_APPROVAL_FOR_SEND=true` y no aprobaste | *Aprobaciones* o `/approve <id>` |
| ActionRequest queda `dispatched=false` | Redis/Celery caído | levantá el stack y reintentá el dispatch |
| Drive folder/organize daba 500 en Postgres | (corregido en Fase 65: migración `202605170001`) | `uv run alembic upgrade head` |
| `detect-secrets` falso positivo en test | falta pragma | `# pragma: allowlist secret` en esa línea |
| Rate limit deja pasar todo | Redis caído (fail-open intencional) | levantá Redis; nunca bloquea legit traffic |

Cualquier otra cosa rara: `bash scripts/full-qa.sh` debería volver
verde. Si no, es una regresión real, no una rareza ambiental.

---

**Documentos relacionados:**

- `RUNBOOK.md` — operación: arrancar, detener, respaldar, restaurar
- `ACTION_PLANE.md` — detalle técnico de cada acción externa
- `ARCHITECTURE.md` — diagramas internos
- `SECURITY.md` — controles obligatorios
- `OPENHARNESS_FUSION.md` — fusión OpenHarness/LangGraph/DeepAgents
- `DOCUMENT_ANALYSIS_AGENT.md` — los 6 modos legales
- `DEEPAGENTS_SKILLS_MEMORY.md` — skills y memoria
- `COGNITIVE_OS_GUIDE.md` — guía maestra técnica desde cero
- `PROJECT_GUIDE.md` — explicación simple y técnica del producto
- `guia_credenciales.md` — **paso a paso para obtener cada credencial** (a qué web, qué botón, dónde, color)
- `OPERATOR_VARIABLE_CHECKLIST.md` — todas las ENV
- `SETTINGS_REGISTRY_TABLE.md` — tabla autogenerada desde `config.py`
- `../findings.md`, `../progress.md` — bitácora viva

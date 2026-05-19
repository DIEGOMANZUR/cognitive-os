# Cognitive OS

> **Estado actual (2026-05-19, Fase 68 — GoDaddy DNS prod operativo + doble revisión + .env.example actualizado):** monorepo en grado comercial
> operativo y **verificado funcionando con el stack real levantado** (Docker
> infra + API + worker + credenciales del operador). Backend FastAPI 0.115+
> (131 endpoints REST verificados,
> 16 tareas Celery distribuidas en 5 colas, 17 migraciones Alembic
> aplicadas en Postgres real) +
> LangGraph 1.1.10 + DeepAgents 0.6.x + Celery 5.4 + Postgres 16+pgvector +
> Redis 7 + Weaviate 1.29.0 + Neo4j 5 (servicios de datos ligados a
> `127.0.0.1`) y consola Next.js 16.2.6 con **20 vistas** en `app/views/*.tsx` (incluidas
> `AssistView` y `GoogleOpsView`). La ruta **`research`** sigue fusionada con
> [OpenHarness](https://github.com/HKUDS/OpenHarness) opcional (`extra`
> `openharness`). LLM (cadena verificada Fase 67/68): **primary+agent `gpt-5.5`**
> (gateway openai-compatible), **secondary/fallback `gemini-3.1-pro-low`**,
> **visión `glm-4.6v`** (z.ai). Kimi K2.6 solo vía el adapter CLI del Code
> Director (su endpoint HTTP da 403). El asistente personal opera **correo multicuenta** GoDaddy
> IMAP/SMTP + Gmail label `TODOS` con propuestas de respuesta por escrito,
> Google Maps read-only, Calendar free/busy + writes aprobados, Drive
> search/upload/folder/organize bajo `ActionRequest`, y envío solo tras
> aprobación humana (`MAIL_REQUIRE_APPROVAL_FOR_SEND=true`). La Fase 33 añade
> RBAC local explícito, cifrado configurable/obligatorio en producción para
> `payload_executable` y persistencia Postgres opcional para runs de research.
> Ejecutables de escritorio (`Levantar/Reiniciar/Detener/Estado Cognitive OS`)
> levantan/reinician/detienen el stack completo —incluido el worker Celery
> de la queue `mail` y Kimi WebBridge— y se verifican con
> `bash scripts/verify_desktop_launchers.sh`. Telegram bot expone **37 slash
> commands** con paridad real frente a la consola: además de approvals,
> jobs y memoria suma `/maps`, `/calendar`, `/freebusy`, `/drive`,
> `/documents`, `/audit`, `/mail`, `/research`, `/codebuild`, `/sandbox` y
> `/capabilities` — todos respetan capacidades habilitadas. Estado reproducible vía
> `bash scripts/full-qa.sh`: **685 passed, 1 skipped,
> 20 deselected**.

### Novedades Fase 68 (2026-05-19) — GoDaddy DNS prod + doble revisión profunda

- **GoDaddy DNS de producción operativo:** credenciales verificadas en
  vivo contra `api.godaddy.com` (HTTP 200, devuelve dominios reales).
  Postura segura: `GODADDY_DNS_DRY_RUN_ONLY=true` +
  `GODADDY_ALLOW_PRODUCTION_WRITES=false` → preview/dry-run con aprobación
  humana, cero escrituras DNS reales sin opt-in explícito.
- **Bug de config corregido:** el `.env` usaba `ENABLE_GODADDY` pero el
  alias real es `GODADDY_ENABLED` — el primero era no-op (GoDaddy nunca
  se habilitaba). Corregido en `.env` y `guia_credenciales.md`.
- **Doble revisión profunda:** auditoría sistemática alias `.env`↔Settings
  (sin más no-ops); `KIMI_CODING_*` documentadas como referencia (el
  adapter `kimi` usa el CLI con su propio `~/.kimi`); `.env.example`
  actualizado (documenta el carril crítico `AGENT_LLM_*`).
- **Backup completo de credenciales** en `.env` y Supermemory MCP.
- **Telegram pendiente:** el `TELEGRAM_BOT_TOKEN` del `.env` da HTTP 401
  (revocado) y falta `TELEGRAM_AUTHORIZED_USER_IDS` — requiere token
  nuevo del operador (@BotFather) + su user_id. No bloquea el resto.
- Suite **685 passed, 1 skipped, 20 deselected**, hermética por
  construcción; ruff/mypy/format/lint/build/pre-commit/git verdes.

### Novedades Fase 67 (2026-05-18) — Esquemas de tools tipados + cadena LLM

- **21 tools del DeepAgent** reescritas con `args_schema` Pydantic
  tipado/descrito/validado: antes los `lambda` sin tipos producían
  propiedades `{}` vacías que los gateways estrictos rechazaban con
  `400 "Invalid schema"`. Verificado: 0 propiedades vacías.
- **Cadena LLM del operador** (verificada en vivo httpx + LangChain):
  primary+agent `gpt-5.5`, secondary/fallback `gemini-3.1-pro-low`,
  visión `glm-4.6v`. Kimi-k2.6 HTTP da 403 (solo Code Director CLI).
- **Suite hermética por construcción:** `tests/conftest.py` con guard
  autouse que impide cualquier llamada LLM real en el suite por defecto
  (router → `deterministic_route`); determinista y rápido.

### Novedades Fase 66 (2026-05-18) — Auditoría en vivo: 4 bugs críticos corregidos

Stack real levantado con credenciales del operador. La resiliencia del
sistema **enmascaraba** fallos del carril principal. Encontrados y
corregidos, todos verificados en vivo:

- **DeepAgent nunca funcionaba:** `deepseek-v4-pro` (=reasoner) responde
  HTTP 400 a `tool_choice` forzado (structured output), así que *todo*
  DeepAgent caía silenciosamente al fallback RAG. Fix:
  `create_agent_chat_model()` + `AGENT_LLM_MODEL=deepseek-chat`. Confirmado:
  `/chat` → DeepAgent real sin fallback.
- **SECONDARY/FALLBACK LLM 403 garantizado:** el endpoint Kimi-for-Coding
  rechaza clientes HTTP. Repuntados a DeepSeek; `VISION_FALLBACK` a GLM.
  Los 6 carriles LLM → HTTP 200.
- **LangSmith dropeaba todas las trazas (403):** la `LANGSMITH_API_KEY`
  scoped no puede ingestar runs. `configure_langsmith()` ahora prefiere el
  `LANGSMITH_PERSONAL_ACCESS_TOKEN` (full scope). `/sessions` → 200.
- **Maps traffic-aware siempre 400:** `departureTime=now` llega a Google
  ya en el pasado ("Timestamp must be set to a future time"). Fix:
  default/clamp a `now + 60s`. Confirmado: ruta real `19.5 km · 25 min`.

Hardening: 7 tests pasados a herméticos (`_env_file=None`),
`SETTINGS_REGISTRY_TABLE.md` regenerado. Migración crítica `202605170001`
aplicada y verificada contra Postgres real. Suite: **685 passed, 1
skipped, 20 deselected**; full-qa verde. Único pendiente operador: OAuth
Google interactivo (`auth_google.py`) y `GODADDY_API_SECRET`.

### Novedades Fase 65 (2026-05-17) — Paridad UI↔Telegram + bugfix CHECK constraint

- **Migración `202605170001_action_requests_drive_folder_organize`**
  amplía `ck_ar_action_type` para aceptar `drive_ensure_folder` y
  `drive_organize_files`. Sin esta migración el INSERT real (Postgres)
  rompía los endpoints `/actions/drive/folders/ensure/request` y
  `/actions/drive/organize/request` con `CheckViolation`. El bug pasaba
  inadvertido porque los tests mocan `session_scope`.
- **Regresión `test_action_request_check_constraint.py`** mantiene
  alineados el ORM, la migración más reciente y `WORKFLOW_EXPORTABLE_TYPES`
  del servicio.
- **Telegram bot** sube de 25 → 37 commands: `/maps origen | destino`,
  `/calendar [max]`, `/freebusy [días]`, `/drive <query>`,
  `/documents [max]`, `/audit [max]`, `/mail [max]`, `/research [max]`,
  `/codebuild [max]`, `/sandbox`, `/capabilities`. Todos respetan los
  flags (Maps/Calendar/Drive status, `MAIL_ENABLED`,
  `ENABLE_OPENSHELL_SANDBOX`, etc.).
- Suite QA: **685 passed, 1 skipped, 20 deselected** (stress 3 corridas
  idénticas en baseline pre-fix).

### Novedades Fase 64 (2026-05-17) — Dispatch idempotente

- Reserva atómica `dispatch_state=submitting|submitted|failed` en
  `ActionRequest.metadata_json` antes de llamar a Celery.
- `submitting` bloquea dispatch concurrente, `submitted` evita re-enviar el
  mismo trabajo mientras el worker procesa y `failed` permite retry.
- REST y Telegram comparten el contrato.
- Suite QA: **674 passed, 1 skipped, 20 deselected**.

### Novedades Fases 59-63 (2026-05-17) — Dispatch durable

- REST `/actions/requests/{id}/dispatch` captura fallos del broker Celery y
  responde `dispatched=false` con reason de retry, sin 500 opaco.
- REST y Telegram registran `action_request_dispatch_submitted` y
  `action_request_dispatch_failed` como `JobEvent`.
- `run_action_request_task_async` short-circuitea si el job ya está `running`,
  evitando eventos duplicados por entregas repetidas del broker.
- Suite QA: **671 passed, 1 skipped, 20 deselected**.

### Novedades Fases 50-58 (2026-05-17) — Bloque operativo humano

- Telegram `/approve` y `/reject` aceptan UUID completo o prefijo único, rechazan
  prefijos ambiguos/cortos o con wildcard, firman como `telegram:<chat_id>` y
  mantienen four-eyes/audit.
- Aprobar un `execute_action_request:<id>` desde Telegram encola y despacha
  `run_action_request_task_async` en `agent_longrun`.
- Nuevo smoke versionado `scripts/verify_desktop_launchers.sh` para validar
  maestro, wrappers `.sh` y accesos `.desktop` sin levantar servicios.
- Suite QA: **669 passed, 1 skipped, 20 deselected**.

### Novedades Fase 42 (2026-05-17) — Legal pack DeepAgents (Apache 2.0)

- **5 skills core nuevas** adaptadas del repo
  [claude-for-legal](https://github.com/anthropics/claude-for-legal)
  (Apache 2.0) sin copiar código: `legal-hold`,
  `privilege-log-review`, `oss-license-review`, `worker-classification`,
  `matter-intake`. Atribución y obligaciones cubiertas en
  `skills/core/NOTICE.md`. **13 skills core** en total.
- Suite QA: **642 passed, 1 skipped, 20 deselected**.

### Novedades Fase 41 (2026-05-17) — Code Director F9

- **`code_director/planner.py`** — `LLMPlanner` descompone el objetivo
  vía LLM primario en subtareas reales, con `HeuristicPlanner`
  determinista como fallback ante **cualquier** fallo (sin key, JSON
  malformado, deps alucinadas, etc.). Un build nunca muere por el
  planner.
- **`code_director/prompt_builder.py`** — cada subtarea recibe un
  prompt estructurado y acotado con árbol vivo del workspace, contenido
  de archivos relevantes y resumen de upstream. En un reintento se
  inyecta el error del intento anterior con "arregla esto, no empieces
  de cero" → `iterate_until_tests_pass` converge en vez de repetir el
  mismo fallo.
- **Suite QA**: **632 passed, 1 skipped, 20 deselected**. Cero tokens
  reales gastados en tests.

### Novedades Fase 40 (2026-05-17) — Code Director

- **Vista `Code Director`** + 4 endpoints REST + Celery task
  `cognitive_os.run_code_build` + `tar.gz` descargable con manifest.
- **Adapters**: `claude_code`, `codex`, `kimi` (subprocess, STDIN-only,
  SIGTERM→SIGKILL del process group) y `deepagent` (in-process).
- **HITL completo**: `HumanApproval` antes de gastar un token; budget
  caps duros; `partial` entrega lo construido si se exceden.

### Novedades Fase 39 (2026-05-17)

- **`/system/info`** — versión runtime + commit + alembic head + policy flags.
- **`/system/credentials-status`** (admin) — inventario vivo de las 21
  credenciales operador con estado, capacidad habilitada y dónde
  obtenerlas. Nunca devuelve valores.
- **`/actions/requests/{id}/workflow`** + **`/actions/requests/from-workflow`**
  — export/import de planes como JSON `workflow.v1` portátil.
- **Vista `Research`** con plan animado vía SSE.
- **Rate limit** con backend Redis pluggable (`RATE_LIMIT_BACKEND=memory|redis`).
- **Approval reaper** (`APPROVAL_PENDING_MAX_HOURS=48`) cierra approvals stale.
- **Four-eyes** para approvals (`APPROVAL_REQUIRE_FOUR_EYES=true`).
- **Correlation IDs** propagados a logs vía `X-Request-ID`.
- **OAuth Google self-healing**: `auth_google.py` detecta token válido y
  refresca sin abrir navegador; health detail trae el comando exacto si
  falta el `token.json`.
- **Wizard CLI**: `bash scripts/init_credentials.sh` reporta checklist
  REQ/OPT/OK de las 21 credenciales con `--ci` para gate de pipeline.

Monorepo con backend **FastAPI** (agentes LangGraph, Celery, Postgres) y **Next.js** 16 como consola web.

**Investigación (`research`):** Cognitive OS **fusiona** tres capas cuando se activa el motor opcional OpenHarness: LangGraph orquesta → [OpenHarness](https://github.com/HKUDS/OpenHarness) puede generar un **preludio** con su `QueryEngine` (en el mismo workspace que DeepAgents si `OPENHARNESS_WORKSPACE_MODE=deepagent_mirror`) → [DeepAgents](https://github.com/langchain-ai/deepagents) produce el informe con citas y política del proyecto. Si OpenHarness no está instalado/habilitado o falla, el grafo continúa solo con DeepAgents y, si éste no responde, con un agente RAG determinista de fallback.

Incluye una capa de **Action Plane** para preparar acciones seguras de navegador,
computador local, Gmail, Google Maps/Calendar/Drive, GoDaddy DNS, documentos
Office y correo personal. Las
acciones sensibles requieren aprobación humana y quedan auditadas. Ver
`docs/ACTION_PLANE.md` y `docs/PERSONAL_ASSISTANT_ROADMAP.md`.

## Leer Primero

- **`docs/USER_GUIDE.md`: Guía de Usuario comercial — empieza aquí. Estado, frontend vista por vista, pipelines, Telegram, ejemplos impresionantes, qué hace / qué no hace, cómo NO usar el sistema.**
- `docs/COGNITIVE_OS_GUIDE.md`: guía maestra técnica "desde cero" — complementa la USER_GUIDE con arquitectura detallada, mail multicuenta, escritorio, credenciales, troubleshooting profundo.
- `docs/PROJECT_GUIDE.md`: explicacion simple y tecnica del producto.
- `docs/README.md`: indice completo de documentacion.
- `docs/OPENHARNESS_FUSION.md`: cómo encaja OpenHarness con LangGraph + DeepAgents (pipelines, presets, workspace).
- `docs/RUNBOOK.md`: operacion diaria.
- `docs/SECURITY.md`: reglas de seguridad.
- `docs/OPERATOR_VARIABLE_CHECKLIST.md`: checklist ENV ↔ código (`Settings`) y tabla maestra.
- `task_plan.md`, `findings.md`, `progress.md`: planificacion viva de esta
  intervencion; no son documentacion permanente de producto.

Copia de respaldo reproducible del árbol de fuentes (sin `node_modules`, `.venv`, `.next`): ejecuta desde el directorio padre:

```bash
rsync -a --exclude node_modules --exclude .next --exclude .venv --exclude '__pycache__' \
  cognitive-os/ cognitive-os-snapshot-$(date +%F)/
```

## Requisitos

- Python ≥ 3.12 y [uv](https://docs.astral.sh/uv/)
- Node.js ≥ 22 y npm
- Verificación reproducible: `bash scripts/full-qa.sh` (`uv sync --extra openharness` + `pytest` + `ruff check` + `ruff format --check` + `mypy` + `npm ci` + `npm run lint` + `npm run build`). Estrés: `bash scripts/stress-qa.sh` (3 pasadas de pytest por defecto).
- Snapshot QA vigente (2026-05-17, Fase 65 cerrada): **685 pytest passed, 1 skipped, 20 deselected**; ruff/ruff format/mypy (125 source files), frontend lint/build (20 vistas), Alembic head (`202605170001`), pre-commit (6 hooks) y `git diff --check` verdes.

## Backend

Desde la raíz del repo o `backend/`:

```bash
cd backend
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000   # API
```

`uv run cognitive-os` es un *bootstrap* mínimo (`backend/src/cognitive_os/__main__.py`) que sólo imprime un log inicial; **no** levanta la API. Para arrancar la pila completa puedes usar los ejecutables de escritorio (`/home/jgonz/Escritorio/Levantar Cognitive OS.sh`, `Reiniciar Cognitive OS.sh`, `Detener Cognitive OS.sh`, `Estado Cognitive OS.sh`) o el flujo manual de `docs/RUNBOOK.md`.

Motor opcional **OpenHarness**: `uv sync --extra openharness` + `ENABLE_OPENHARNESS_RESEARCH=true`. Variables `OPENHARNESS_*` en `docs/SETTINGS_REGISTRY_TABLE.md`; modelo de fusión (**`prelude_merge`** por defecto vs **`short_circuit`**) y presets **`minimal` / `research` / `full`** en `docs/OPENHARNESS_FUSION.md`.

Variables de entorno: copia `.env.example` en la raíz a `.env` y ajusta secretos.

- **CORS**: `CORS_ALLOW_ORIGINS` (lista CSV). Vacío ⇒ defaults `http://localhost:{3000,3001}` y `http://127.0.0.1:{3000,3001}` (frontend real corre en :3001 porque OpenChamber ocupa :3000; :3000 queda para compatibilidad). No uses `*` con credenciales habilitadas (lo rechaza la configuración).
- **Action Plane y mail personal**: las acciones externas arrancan desactivadas o con aprobación humana. Configura `ENABLE_BROWSER_AUTOMATION`, `ENABLE_COMPUTER_ACTIONS`, `GMAIL_*`, `GODADDY_*`, `MAIL_*` y sus allow-lists antes de cualquier ejecución real. `MAIL_REQUIRE_APPROVAL_FOR_SEND=true` es la política obligatoria inicial.

## Infra local (Docker)

```bash
cd infra
docker compose --env-file ../.env up -d
```

## Frontend

```bash
cd frontend
cp .env.example .env.local   # opcional: fija NEXT_PUBLIC_API_BASE_URL en build/prod
npm ci
# Dev:
PORT=3001 npm run dev        # (OpenChamber ocupa :3000)
# Prod local:
npm run serve                # build + next start -H 127.0.0.1 -p 3001
npm run lint
npm run build
```

En desarrollo el panel puede apuntar al API desde ajustes en la UI; si defines `NEXT_PUBLIC_API_BASE_URL` al hacer build, esa URL inicial tendrá prioridad.

## Ensayo local rápido

Con Postgres/Redis opcionales, la API puede arrancar con checkpointer en memoria si Postgres no está listo.

# Cognitive OS

> **Estado actual (2026-05-17, Fase 41 Code Director F9 cerrada):** monorepo en grado comercial
> operativo con backend FastAPI 0.115+ (126 endpoints REST verificados,
> 16 tareas Celery distribuidas en 5 colas, 16 migraciones Alembic) +
> LangGraph 1.1.10 + DeepAgents 0.6.x + Celery 5.4 + Postgres 16+pgvector +
> Redis 7 + Weaviate 1.29.0 + Neo4j 5 (servicios de datos ligados a
> `127.0.0.1`) y consola Next.js 16.2.6 con **20 vistas** en `app/views/*.tsx` (incluidas
> `AssistView` y `GoogleOpsView`). La ruta **`research`** sigue fusionada con
> [OpenHarness](https://github.com/HKUDS/OpenHarness) opcional (`extra`
> `openharness`). LLM por defecto: **DeepSeek V4 Pro** (`deepseek-v4-pro`),
> con Kimi K2.6-code-preview como fallback de coding y GLM-4.6v como vision
> primaria. El asistente personal opera **correo multicuenta** GoDaddy
> IMAP/SMTP + Gmail label `TODOS` con propuestas de respuesta por escrito,
> Google Maps/Calendar/Drive con writes solo bajo `ActionRequest`, y envío solo tras
> aprobación humana (`MAIL_REQUIRE_APPROVAL_FOR_SEND=true`). La Fase 33 añade
> RBAC local explícito, cifrado configurable/obligatorio en producción para
> `payload_executable` y persistencia Postgres opcional para runs de research.
> Ejecutables de escritorio (`Levantar/Reiniciar/Detener/Estado Cognitive OS`)
> levantan/reinician/detienen el stack completo —incluido el worker Celery
> de la queue `mail` y Kimi WebBridge—. Sin commits aún en `master`; estado
> reproducible vía `bash scripts/full-qa.sh`.

### Novedades Fase 42 (2026-05-17) — Legal pack DeepAgents (Apache 2.0)

- **5 skills core nuevas** adaptadas del repo
  [claude-for-legal](https://github.com/anthropics/claude-for-legal)
  (Apache 2.0) sin copiar código: `legal-hold`,
  `privilege-log-review`, `oss-license-review`, `worker-classification`,
  `matter-intake`. Atribución y obligaciones cubiertas en
  `skills/core/NOTICE.md`. **13 skills core** en total.
- Suite QA: **637 passed, 1 skipped, 20 deselected**.

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
- Snapshot QA vigente (2026-05-17, Fase 42 legal-pack cerrada): **637 pytest passed, 1 skipped, 20 deselected**; ruff/ruff format/mypy (111 source files), frontend lint/build, Compose config, Alembic head (`202605160002`) y `git diff --check` verdes. Stress 3 corridas estables.

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

- **CORS**: `CORS_ALLOW_ORIGINS` (lista CSV). Vacío ⇒ `http://localhost:3000` y `http://127.0.0.1:3000`. No uses `*` con credenciales habilitadas (lo rechaza la configuración).
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
npm run dev
npm run lint
npm run build
```

En desarrollo el panel puede apuntar al API desde ajustes en la UI; si defines `NEXT_PUBLIC_API_BASE_URL` al hacer build, esa URL inicial tendrá prioridad.

## Ensayo local rápido

Con Postgres/Redis opcionales, la API puede arrancar con checkpointer en memoria si Postgres no está listo.

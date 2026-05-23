# Cognitive OS

> **Estado canonico (2026-05-23, commit `647f103`):** Cognitive OS corre
> como **sistema cognitivo local mono-operador** para el PC dedicado de
> Diego. Prioridad de producto: **friccion operativa casi nula por sobre
> seguridad estricta** — perfil real de Edge, operacion amplia en el PC y
> approvals reducidos cuando el perfil es `dedicated_local/full`. Los
> controles principales son trazabilidad, idempotencia, logs,
> health/readiness honesto, reapers y tests. Excepcion dura: **mail** — el
> flujo normal solo lee, clasifica, resume y propone respuestas como
> texto; no crea drafts ni envia correos salvo peticion explicita + flags
> de escape hatch. Fuente de verdad corta: `docs/CURRENT_STATE.md` y
> `docs/ZERO_FRICTION_OPERATING_MODEL.md`. Doble auditoria TestSprite
> 2026-05-23 cerrada: `docs/audits/testsprite/16_FINAL_REAUDIT_REPORT.md`.

## Snapshot Tecnico

Conteos derivados del codigo por `scripts/sync_doc_counts.py` (`full-qa.sh`
falla si quedan desincronizados):

- **Backend** FastAPI 0.115+ — **147 endpoints REST**, **23 tareas Celery** en
  **5 colas** (`default`, `ingestion`, `agent_longrun`, `maintenance`, `mail`),
  hasta **13 jobs beat** segun feature flags.
- **DB** Postgres 16+pgvector — **20 migraciones Alembic**, head
  `202605200003`, `alembic check` sin drift.
- **Orquestacion** LangGraph 1.1.10 + DeepAgents 0.6.x + cliente MCP nativo +
  Action Plane. Ruta `research` fusionada con OpenHarness opcional.
- **Telegram** — **37 slash commands** (dispatch fail-closed) + modo
  conversacional sin slash en `dedicated_local`.
- **Health** — `/health/dashboard` con **18 componentes**; `POST /health/verify`
  para probe real bajo demanda; componente `operational_backlog`.
- **Frontend** Next.js 16.2.6 + React 19 + TypeScript estricto — **20 vistas**,
  PWA dark-only glassmorphism, sin Tailwind/shadcn.
- **LLM** — primary+agent `gpt-5.5` (Responses API + prompt caching 24h),
  secondary/fallback `gemini-3.1-pro-low`, vision `glm-4.6v`.
- **QA** — `full-qa.sh` **950 passed, 1 skipped, 28 deselected** +
  ruff/format/mypy/Alembic/lint/build/`sync_doc_counts`/`git diff --check`;
  `stress-qa.sh` 3 pasadas verdes de **950 passed**; Playwright **31
  passed** (sin necesidad de exportar `COGOS_JWT` — auto-mint via
  `POST /auth/local-token`); carril opt-in `tests/live/` verificado con
  **8 passed** contra proveedores reales. TestSprite MCP re-audit en dos
  batches acotados: **10/10 passed**
  (`TC001/002/003/004/006/007/008/009/010/014`).
- Infra de datos (Postgres / Redis 7 / Weaviate 1.29.0 / Neo4j 5) ligada a
  `127.0.0.1`, sin exposicion a internet.

## Cambios Recientes

**Reaudit TestSprite + zero-friction Playwright (`647f103`, 2026-05-23).**
Una segunda pasada de auditoria independiente cazo un P1 que la primera
pasada no detecto y reforzo el carril QA local:

- **P1 — `eager_defaults=True` en `db.Base`:**
  `POST /actions/browser/preview/request` (y todos los `create_*_request`
  que leen `updated_at` despues de `session.flush()` en `AsyncSession`)
  devolvia HTTP 500 con `sqlalchemy.exc.MissingGreenlet`. El attribute
  lazy-load disparaba SQL sincronico fuera del greenlet. Fix idiomatico
  SQLAlchemy 2.x: `__mapper_args__ = {"eager_defaults": True}` en `Base`,
  emite `INSERT ... RETURNING` para columnas con server-default.
  Endpoint vivo verificado HTTP 200; idempotency intacta. 3 tests de
  regresion nuevos (`backend/tests/test_action_request_eager_defaults.py`).
- **P2 — Playwright zero-friction runner:** nuevo
  `frontend/tests/e2e/_global-setup.ts` auto-mintea `COGOS_JWT` via
  `POST /auth/local-token` cuando el perfil es `dedicated_local/full`.
  `npx playwright test` ahora pasa 31/31 sin exportar nada.
- **P3 — RUNBOOK QA actualizado:** método primario `curl POST
  /auth/local-token | python3 -c "...access_token"`; el `uv run python -c
  "from cognitive_os.core.auth..."` queda como fallback para `strict`.

Gates post-fix: `full-qa.sh` **950 passed** (944 + 6 regresion), stress-qa
3 × 950, Playwright 31/31, TestSprite re-audit 10/10. Detalle completo en
`docs/audits/testsprite/16_FINAL_REAUDIT_REPORT.md`.

**Post-gate MCP/frontend (`5953b40`, 2026-05-22).** Se corrigio un falso
timeout real de `/system/mcp`: el inventario de MCP carga servidores en
paralelo y usa `MCP_INVENTORY_TIMEOUT_SECONDS=30` por defecto. Runtime
verificado: `mem`, `gh`, `fs`, `cc` y `gem` conectados (**5/5**) con **67
tools**. Tambien se estabilizo `Ctrl/Cmd+K` del command palette usando capture
phase en el hook de teclado.

**Remediacion del audit comercial (2026-05-22).** Tras
`docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md` se cerraron las 8 fallas
accionables (AUDIT-2026-A..H):

- **A (P0)** — dispatch de Telegram fail-closed: una allowlist vacia rechaza a
  todos y `main()` se niega a arrancar en ese estado.
- **B (P1)** — `/health/dashboard` distingue `verified` de `configured` y no
  pinta verde lo que nunca se probo; nuevo `POST /health/verify`.
- **C (P1)** — kill switch `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED` para la
  unica ruta de auto-deploy del plan de aprendizaje.
- **D (P2)** — matriz de tests de los 37 comandos Telegram.
- **E (P2)** — carril `tests/live/` opt-in (`LIVE_TESTS_ENABLED=1`).
- **F (P2)** — componente `operational_backlog` en health.
- **G (P3)** — `scripts/sync_doc_counts.py` mantiene los conteos canonicos.
- **H (P3)** — `scripts/dev_up.sh` valida variables antes de `docker compose`.

**Plan de aprendizaje autonomo (Fases A-E, `docs/AGENT_LEARNING_PLAN.md`):** en
produccion. Fase A recipe extractor, Fase B skill promotion (procedure → skill
YAML con rollback automatico), Fase C tool scorecard, Fase D failure
post-mortem, Fase E nightly reflection con evidencia literal obligatoria. Todo
pasa por el approval gate del operador; la unica excepcion acotada es el
auto-promote de *warnings* de Fase D, con kill switch.

**Code Director:** meta-agente que delega builds a coding agents externos
(Claude Code / Codex / Kimi CLI o DeepAgents in-process) bajo aprobacion humana
+ budget caps + audit, con planner LLM-driven y fallback heuristico.

El historial fase-a-fase detallado vive en `git log` y en el contexto del
documento de auditoria; este README mantiene solo el estado vigente.

## Que Es Cognitive OS

Monorepo con backend **FastAPI** (agentes LangGraph, Celery, Postgres) y
**Next.js 16** como consola web.

**Investigacion (`research`):** Cognitive OS **fusiona** tres capas cuando se
activa el motor opcional OpenHarness: LangGraph orquesta → [OpenHarness](https://github.com/HKUDS/OpenHarness)
puede generar un **preludio** con su `QueryEngine` (en el mismo workspace que
DeepAgents si `OPENHARNESS_WORKSPACE_MODE=deepagent_mirror`) → [DeepAgents](https://github.com/langchain-ai/deepagents)
produce el informe con citas y politica del proyecto. Si OpenHarness no esta
instalado/habilitado o falla, el grafo continua solo con DeepAgents y, si este
no responde, con un agente RAG determinista de fallback.

Incluye una capa de **Action Plane** para preparar acciones seguras de
navegador, computador local, Gmail, Google Maps/Calendar/Drive, GoDaddy DNS,
documentos Office y correo personal. Las acciones sensibles quedan auditadas
(`ActionRequest`, `JobEvent`, `AuditEvent`) y, en `strict`, pasan por aprobacion
humana. Ver `docs/ACTION_PLANE.md` y `docs/PERSONAL_ASSISTANT_ROADMAP.md`.

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
- Verificación reproducible: `bash scripts/full-qa.sh` (`uv sync --extra openharness` + `pytest` + `ruff check` + `ruff format --check` + `mypy` + `npm ci` + `npm run lint` + `npm run build` + `sync_doc_counts.py --check` + `git diff --check`). Estrés: `bash scripts/stress-qa.sh` (3 pasadas de pytest por defecto). Smokes en vivo opt-in: `bash scripts/full-qa-live.sh`.
- Snapshot QA vigente (2026-05-23, commit `647f103`): `bash scripts/full-qa.sh` **950 passed, 1 skipped, 28 deselected** (944 históricos + 6 nuevos de regresión del bug `eager_defaults`); ruff/ruff format/mypy, frontend lint/build aislado con `.next-qa`, Alembic head `202605200003` y `git diff --check` verdes. Playwright frontend: **31 passed** sin exportar `COGOS_JWT` (auto-mint via `_global-setup.ts`). Stress QA: 3 pasadas de **950 passed**. Live read-only: `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed** (último gate documentado; no re-ejecutado en re-audit por ser opt-in). TestSprite MCP re-audit: **10/10 passed** sobre dos batches.

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
- **Action Plane y mail personal**: en `strict`, las acciones externas arrancan desactivadas o con aprobación humana. En `OPERATOR_PROFILE=dedicated_local` + `LOCAL_AUTONOMY_MODE=full`, el PC dedicado elimina approvals manuales para reducir fricción en browser/computer/Google, pero conserva `ActionRequest`, `JobEvent`, `AuditEvent`, idempotencia y errores visibles. Mail queda fuera de esa relajación: por defecto solo lee, resume y propone texto; SMTP requiere una petición explícita de Diego. Configura `ENABLE_BROWSER_AUTOMATION`, `ENABLE_COMPUTER_ACTIONS`, `GMAIL_*`, `GODADDY_*`, `MAIL_*` y allow-lists/flags antes de cualquier ejecución real.

## Infra local (Docker)

Comando único correcto (valida variables y espera health checks):

```bash
bash scripts/dev_up.sh
```

Equivalente manual (no recomendado — `dev_up.sh` además valida que las
variables que el compose interpola sin default no estén vacías):

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

En desarrollo el panel puede apuntar al API desde ajustes en la UI; si defines
`NEXT_PUBLIC_API_BASE_URL` al hacer build, esa URL inicial tendrá prioridad.

**Stack y lenguaje visual:**

- Next.js 16.2.6 App Router + React 19 + TypeScript 5.8 estricto.
- **Glassmorphism dark-only** de alto contraste. Sin Tailwind, sin
  shadcn. Tokens centralizados en `app/globals.css`; `<html
  data-theme="dark">` fijo desde `layout.tsx`.
- **Tipografía:** Inter + JetBrains Mono self-hosted vía `next/font/google`
  (la PWA arranca offline sin pedir Google Fonts).
- **Iconografía:** componente `<Icon name="…" />` (`app/components/Icon.tsx`)
  con SVGs Lucide-style consistentes. **No usar emojis ni glifos
  Unicode para íconos estructurales.**
- **Charts SVG** sin dependencias en `app/components/Charts.tsx`:
  `Sparkline`, `AreaChart`, `BarList`, `Donut`.
- **PWA instalable**: `app/manifest.ts` + `public/sw.js`. Shortcuts (Chat /
  Aprobaciones / Jobs / Health), íconos PNG 192/512 + maskable + SVG fallback,
  `/offline.html` con branding propio. Handlers de `push` y
  `notificationclick` listos para notificaciones del SO.
- **Centro de notificaciones** (`NotificationCenter.tsx`) con feed unificado de
  aprobaciones, jobs y eventos de auditoría.
- **Command palette** (`CommandPalette.tsx`) con fuzzy match real, atajo
  `Ctrl/Cmd+K` estabilizado desde capture phase.
- **Defensive list guards** (`api.ts → asArray<T>(...)`): cada vista que
  consume `usePolledFetch<T[]>` usa `asArray(data)` para no caer al
  `ErrorBoundary` si el backend responde malformado.

**QA del frontend:**

- `npm run lint` → 0 warnings (`--max-warnings 0`).
- `npm run build` → Next 16.2.6 + Turbopack OK.
- `npx tsc --noEmit` → 0 errores.
- Playwright headless full-walk (1440×900 + 393×851 mobile) sobre las 20
  tabs, palette y notification center: **31 passed**, 0 errores 5xx, 0 page
  errors, 0 console errors. `playwright.config.ts` bloquea el service worker
  durante los tests y deshabilita el cache HTTP.

## Ensayo local rápido

Con Postgres/Redis opcionales, la API puede arrancar con checkpointer en memoria si Postgres no está listo.

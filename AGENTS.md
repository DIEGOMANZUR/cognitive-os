# AGENTS.md

> **Estado actual (2026-05-20, Fase 82.1 — Glass Cockpit + Robustez):**
> El frontend (Next.js 16 App Router + React 19 + TS estricto) se reescribió
> como un *command center glassmorphism dark-only de alto contraste,
> instalable como PWA*, y luego se endureció a grado comercial robusto:
> `usePolledFetch` pausa offline + tab oculta y refetcha al volver,
> primitivas `StatePrimitives` (Skeleton/EmptyState/ErrorPanel) uniformes,
> `asArray<T>` en las 13 vistas que consumen colecciones, `useFocusTrap`
> en todos los modales, skip-link al main. Doc canónica en
> `cognitive-os/docs/FRONTEND_ARCHITECTURE.md` con anti-patrones y
> checklist pre-PR. Spec Playwright nueva `glass-cockpit.spec.ts` cubre
> palette + notification center + defensive guards + skip-link. El sistema de diseño vive en
> `cognitive-os/frontend/app/globals.css` con tokens centralizados,
> tipografía self-hosted Inter + JetBrains Mono via `next/font/google`, y
> un componente `<Icon>` con un set SVG curado (~55 íconos). Componentes
> nuevos: `Charts.tsx` (Sparkline/AreaChart/BarList/Donut sin
> dependencias), `NotificationCenter.tsx` (side-panel con feed unificado
> + handshake push del SO), `CommandPalette.tsx` reescrito con fuzzy
> match real + grupos + recientes. PWA endurecida: manifest con 4
> shortcuts, íconos PNG 192/512 + maskable + SVG fallback, service
> worker `cogos-v2026-05-20-glass-2` con offline shell y handlers de push
> + notificación. **Defensive array guards** (`asArray<T>(...)` en
> `lib/api.ts`) en las 13 vistas que consumen colecciones — la SPA ya no
> cae al `ErrorBoundary` si el backend devuelve forma incorrecta.
> `playwright.config.ts` blinda el suite oficial contra service-workers
> persistentes y cache HTTP. QA: lint 0 warnings, `tsc --noEmit` limpio,
> build Next 16 + Turbopack verde, Playwright headless full-walk
> (1440×900 + 393×851 mobile) sobre las 20 tabs + palette + notification
> center = 0 errores 5xx / 0 page errors / 0 console errors.
>
> **Reglas firmes para futuras intervenciones en el frontend:**
> 1. **No reintroducir Tailwind, shadcn ni MUI.** El repo eligió CSS
>    hand-rolled con tokens; nuevas reglas se añaden a
>    `app/globals.css` y se consumen vía clases utilitarias del repo.
> 2. **No usar emojis ni glifos Unicode para íconos estructurales.**
>    Usar `<Icon name="…" />`.
> 3. **No reintroducir el toggle de tema claro.** El cockpit es
>    dark-only; `<html data-theme="dark">` queda fijo desde
>    `layout.tsx`.
> 4. **Listas:** preferir `asArray(x.data).filter|map|…` sobre
>    `(x.data ?? []).filter(...)`.
> 5. **Conservar anclajes E2E** (los tests existentes los chequean):
>    `aria-label="JWT local"`, `URL base de la API`, `Abrir menú`,
>    `Cerrar`, literales `Estado global`, `componentes ok`, los 20
>    labels declarados en `tests/e2e/_helpers.ts:TAB_LABELS`, y los
>    labels `Guardar` / `API base` / `JWT sin prefijo Bearer` en
>    `SettingsView`.
>
> **Estado anterior (Fase 78 — recipe extractor / Fase A del plan de aprendizaje):**
> Primera fase del plan documentado en `cognitive-os/docs/AGENT_LEARNING_PLAN.md`
> está cerrada. El agente ahora **distila trayectorias de jobs exitosos
> en procedimientos reutilizables** (`DeepAgentMemoryProposal(kind="procedure")`)
> que pasan por el approval gate del operador en `MemoryView →
> Recetas propuestas`. Cero auto-deploy, cero mutación del system prompt.
> Migración Alembic head: `202605200001`. Beat schedule corre cada 30
> min. Suite hermética: **735 passed**. 23 tests nuevos cubren el
> happy path, ineligibilidad por threshold/duración/tipo, LLM-failure
> sin marcar el job, skip signal, batch sweep, round-trip a memoria
> activa con `kind=procedure`. Live verificado: endpoint retorna
> proposal real con payload estructurado (recipe JSON + tool_call_count
> + duration); beat task registrada; `/health/dashboard` mantiene 17
> componentes. Frontend `MemoryView.tsx` agrega sección plegable con
> botones Aprobar / Rechazar / Extraer ahora. **Pendiente operador**:
> en futuras fases puede correr `bash scripts/full-qa.sh` para
> reverificación.
>
> **Estado anterior (Fase 68 — GoDaddy DNS producción operativo + doble revisión profunda):**
> GoDaddy DNS verificado en vivo (auth prod HTTP 200), seguro (dry-run +
> aprobación, sin prod-writes); bug de alias `ENABLE_GODADDY`→`GODADDY_ENABLED`
> corregido; `.env.example` actualizado (documenta `AGENT_LLM_*`); suite
> hermética por construcción (conftest guard) **685 passed**. Telegram
> pendiente: el `TELEGRAM_BOT_TOKEN` del `.env` da 401 (revocado) y falta
> `TELEGRAM_AUTHORIZED_USER_IDS` — requiere token nuevo del operador.
> Estado previo (Fase 67 — esquemas de tools tipados + cadena LLM operador):
> Las 21 tools del DeepAgent ahora usan `args_schema` Pydantic tipado
> (antes lambdas → `{}` vacío que gateways estrictos rechazaban). Cadena
> LLM verificada en vivo: primary+agent=gpt-5.5 @ gateway :8317,
> secondary/fallback=gemini-3.1-pro-low, visión=glm-4.6v. Kimi-k2.6 HTTP
> 403 (solo Code Director CLI). `/chat` real sin fallback, router LLM OK.
> Estado previo (Fase 66 auditoría EN VIVO con credenciales reales):
> monorepo en grado comercial operativo, verificado funcionando con stack
> real levantado. Auditoría en vivo encontró y corrigió 4 bugs críticos
> que la resiliencia enmascaraba: (1) DeepAgent muerto — el reasoner
> `deepseek-v4-pro` no soporta tool_choice forzado → carril de agente
> ahora usa `deepseek-chat` vía `AGENT_LLM_MODEL`; (2) SECONDARY/FALLBACK
> LLM con 403 garantizado (Kimi-for-Coding rechaza HTTP) → repuntados a
> DeepSeek; (3) LangSmith dropeaba trazas (key scoped 403) → usa el
> personal access token; (4) Maps traffic-aware siempre 400
> (`departureTime` pasado) → `now+60s`. Suite **685 passed**.
> Backend FastAPI 0.115+ con
> **131 endpoints REST** (104 propios + 27 de orquestación), **16 tareas
> Celery** distribuidas en 5 colas (`default`, `ingestion`,
> `agent_longrun`, `maintenance`, `mail`), **17 migraciones Alembic**
> (head `202605170001`), LangGraph 1.1.10 + DeepAgents 0.6.x + OpenHarness
> opcional, mail multicuenta GoDaddy/Gmail con aprobación humana
> obligatoria y Google Maps/Calendar/Drive operables vía Action Plane: Maps
> read-only, Calendar free/busy + create aprobado, Drive search/upload/folder/organize
> con aprobación y sin deletes. Frontend Next.js 16.2.6 + React 19 con **20 vistas**
> incluidas `AssistView`, `GoogleOpsView`, `ResearchView` (plan animado
> sobre SSE) y `CodeDirectorView`. Cockpit OpenCode con **21 MCPs**, 7
> subagentes, **15 skills** y 7 comandos slash. LLM por defecto:
> **DeepSeek V4 Pro**.
>
> Fase 39 cerró los residual risks técnicos: rate limiter pluggable
> Redis/memory, `/system/credentials-status` con inventario vivo, workflow.v1
> export/import, OAuth Google self-healing, wizard `init_credentials.sh`,
> correlation IDs, approval reaper, four-eyes, AuditEvent simétrico
> REST↔Telegram. Fase 40 añadió el **Code Director**: meta-agente que
> delega builds a coding agents externos (Claude Code / Codex / Kimi CLI
> o DeepAgents in-process) bajo aprobación humana + budget caps + audit;
> el director nunca codifica en su propio proceso ni gasta tokens hasta
> que el operador aprueba el plan. Fase 41 (F9) lo hizo capaz para apps
> complejas: planner LLM-driven (descompone el objetivo en subtareas
> reales, con fallback heurístico determinista) y prompts con contexto
> vivo del workspace + reintentos dirigidos por el error previo. Fases
> 44-49 consolidaron Google Ops (Maps con advice/ETA, Calendar
> free/busy, Drive search/upload/folder/organize aprobable). Fases
> 50-58 cerraron el bloque operativo humano: Telegram approvals acepta
> UUID completo o prefijo único, firma como `telegram:<chat_id>`,
> despacha `ActionRequest` aprobados y el repo incluye smoke reproducible
> de launchers de escritorio. Fases 59-63 endurecieron dispatch:
> broker failures visibles sin 500 opaco, JobEvents submit/fail en REST
> y Telegram, y worker short-circuit ante entrega duplicada ya `running`.
> Fase 64 añadió reserva atómica `dispatch_state=submitting|submitted|failed`
> antes de `apply_async`, impidiendo submits duplicados a Celery y dejando
> retry explícito tras fallo. Fase 65 cerró paridad Telegram↔UI (36 slash
> commands incluyendo `/maps`, `/calendar`, `/freebusy`, `/drive`,
> `/documents`, `/audit`, `/mail`, `/research`, `/codebuild`, `/sandbox`,
> `/capabilities`) y corrigió un bug crítico de CHECK constraint
> `ck_ar_action_type` que rompía silenciosamente
> `/actions/drive/folders/ensure/request` y `/actions/drive/organize/request`
> en Postgres (migración `202605170001` + test de regresión que mantiene
> alineados ORM, migración y servicio).
>
> Snapshot QA verde: **685 pytest passed, 1 skipped, 20 deselected**;
> ruff/ruff format/mypy/frontend lint/build/Alembic/`git diff --check`
> verdes vía `bash scripts/full-qa.sh`. Único pendiente operador:
> autorizar `auth_google.py` (1 click
> browser) si quiere Calendar/Drive y completar credenciales OPT que vaya
> a usar — `bash scripts/init_credentials.sh` reporta cuáles faltan.

Proyecto: **Cognitive OS** (mono-workspace).
Sub-proyecto principal: `cognitive-os/` (backend FastAPI + LangGraph + DeepAgents,
frontend Next.js 16, infra Docker con Postgres+pgvector, Redis, Weaviate 1.29.0,
Neo4j 5).

OpenCode actúa como **cockpit de desarrollo**, no como runtime productivo.

---

## Rol de OpenCode

- OpenCode diseña, inspecciona, modifica, prueba y documenta.
- LangGraph coordina workflows stateful y durables.
- Deep Agents ejecuta tareas largas con subagentes y memoria operativa.
- Neo4j guarda relaciones, entidades, eventos, GraphRAG y memoria explicable.
- Weaviate guarda recuperación vectorial / híbrida.
- LangSmith observa, evalúa y depura runs.
- OpenAPI MCP expone servicios internos como tools (cuando exista spec).
- Browser automation (Playwright / Chrome DevTools) solo se usa cuando no hay
  API confiable.

## Principio central

No mezclar responsabilidades:

- **OpenCode** = desarrollo asistido, edición, análisis, revisión, automatización local.
- **LangGraph** = orquestación runtime, checkpoints, state machines, human-in-the-loop.
- **Deep Agents** = ejecución prolongada, filesystem, subagentes, tareas complejas.
- **Neo4j** = memoria relacional, entidades, relaciones, Cypher, GraphRAG explicable.
- **Weaviate** = embeddings, vector search, hybrid search, BM25, filtros.
- **LangSmith** = trazas, datasets, evals, comparación de runs.
- **Supermemory** = memoria personal/dev cross-sesión (preferencias, decisiones,
  error-solutions, patrones). NO es memoria productiva del runtime.
- **Memory Bank MCP** = memoria local del workspace para continuidad de
  desarrollo en `memory-bank/`. Complementa Supermemory; no guarda secretos ni
  memoria productiva.
- **planning-with-files** = estado de trabajo en desarrollo, no memoria productiva.

Cuando el usuario pida recurrir a memoria, recordar contexto, continuar trabajo
previo, o cuando el asistente estime que hace falta contexto durable, usar la
skill `dual-memory-recall` y consultar **Supermemory + Memory Bank** antes de
responder o actuar.

## Layout del workspace

- `cognitive-os/` — proyecto activo.
  - `backend/` (Python ≥ 3.12, uv, FastAPI 0.115+, LangGraph 1.1.10+,
    DeepAgents 0.6.1<0.7, Celery 5.4+, SQLAlchemy 2 async, 75 archivos
    `tests/test_*.py`).
  - `frontend/` (Next.js 16.2.6, React 19, ESLint 9, TypeScript 5.8, **20
    vistas** en `app/views/*.tsx`).
  - `infra/docker-compose.yml` (PostgreSQL 16+pgvector, Redis 7, Weaviate 1.29.0
    y Neo4j 5 publicados sólo en `127.0.0.1` por defecto).
  - `mail/` (paquete bajo `backend/src/cognitive_os/`): IMAP/SMTP GoDaddy +
    Gmail label `TODOS`, queue Celery `mail`, política
    `MAIL_REQUIRE_APPROVAL_FOR_SEND=true`.
  - `assist/` (tareas/notas personales): endpoints `/assist/tasks`,
    `/assist/notes`, `/assist/notes/search` (indexación Weaviate).
  - `actions/` (Action Plane): browser, calendar, captcha, computer,
    documents, drive, gmail, godaddy, kimi_webbridge, mail, maps, voice.
  - `task_plan.md`, `findings.md`, `progress.md`, `ACCEPTANCE_CHECKLIST.md`,
    `docs/` con runbooks y registries.
- `cognitive-os-backup-*/` y `cognitive-os-snapshot-*/` — **solo lectura**, no editar.
- `docs/` (raíz) — documentación transversal (`SECURITY.md`,
  `openchamber-cognitive-os.md`, `opencode-agent-stack.md`).
- `memory-bank/cognitive-os/` — Memory Bank MCP scoped al proyecto
  (`activeContext.md`, `progress.md`).
- `~/Escritorio/{Levantar,Reiniciar,Detener,Estado} Cognitive OS.{sh,desktop}`
  — ejecutables de control del stack completo (incluye Kimi WebBridge y
  worker de mail).

## Documentación actualizada

Usa MCPs de documentación **antes** de escribir código cuando:

- haya librerías, SDKs, imports, versiones o APIs cambiantes;
- aparezcan palabras como deprecated, breaking change, latest docs, v4, v5;
- trabajes con LangGraph, LangChain, LangSmith, Weaviate, Neo4j, OpenAI SDK,
  Next.js, React, Stripe, Supabase o Cloudflare.

Preferencias:

- LangGraph / LangChain / LangSmith → `docs-langchain` MCP.
- Weaviate → `weaviate-docs` MCP.
- Librerías generales → Context7 (cuando esté habilitado).
- APIs internas → OpenAPI MCP (cuando exista spec).
- Código del repo / dependencias → subagente `repo-architect` antes de editar.

## Seguridad

- No guardar secretos en archivos versionados.
- No hacer writes en producción sin confirmación explícita.
- No habilitar writes en Neo4j, PostgreSQL o Weaviate sin confirmación.
- No modificar billing, auth, permisos, infraestructura o datos productivos
  sin confirmación.
- Preferir OAuth cuando el MCP lo soporte (GitHub MCP remoto).
- Preferir tokens de mínimo privilegio.
- Antes de comandos destructivos, pedir permiso.
- Nunca tocar `cognitive-os-backup-*/` ni `cognitive-os-snapshot-*/`.

## Flujo para tareas largas

Para tareas complejas usa la skill **planning-with-files**:

1. Crear o actualizar:
   - `task_plan.md`
   - `findings.md`
   - `progress.md`
2. Antes de decisiones importantes, releer `task_plan.md`.
3. Después de research, actualizar `findings.md`.
4. Después de cambios de implementación, actualizar `progress.md`.
5. Al final, verificar contra el plan original.
6. No tratar estos archivos como memoria productiva.

En este repo el estado vivo está en `cognitive-os/task_plan.md`,
`cognitive-os/findings.md`, `cognitive-os/progress.md`.

## Validación antes de terminar

Comandos reales detectados en este repo (úsalos según el área tocada):

Backend (`cognitive-os/backend/`):

- `uv sync` (con `--extra openharness` si vas a tocar el motor opcional).
- `uv run pytest -m 'not integration and not slow'` (snapshot vigente:
  **642 passed, 1 skipped, 20 deselected**).
- `uv run ruff check .` y `uv run ruff format --check .`.
- `uv run mypy src` (success).
- `uv run alembic check` (sin operaciones nuevas esperadas; excluye tablas
  runtime de LangGraph/PostgresSaver).

Frontend (`cognitive-os/frontend/`):

- `npm ci`
- `npm run lint` (0 warnings)
- `npm run build` (Next.js 16.2.6 OK)

Infra:

- `docker compose -f cognitive-os/infra/docker-compose.yml config`
- `docker compose -f cognitive-os/infra/docker-compose.yml --env-file ../.env up -d`

Transversal:

- `git diff --check` (clean en estado actual).
- `pre-commit run --all-files` (config en `.pre-commit-config.yaml`).
- `bash cognitive-os/scripts/full-qa.sh` — suite QA completa
  (`uv sync --extra openharness` + pytest + ruff + ruff format + mypy + npm
  ci + npm lint + npm build).
- `bash cognitive-os/scripts/stress-qa.sh` — 3 pasadas de pytest por defecto.

Stack ejecutables de escritorio (control diario sin tocar terminal):

- `~/Escritorio/Levantar Cognitive OS.sh` — arranca Docker, migraciones,
  API, Celery worker (queues `default,ingestion,agent_longrun,maintenance,mail`),
  Celery beat, frontend y Kimi WebBridge. Telegram queda omitido si
  `TELEGRAM_ENABLED=false`.
- `~/Escritorio/Reiniciar Cognitive OS.sh`, `~/Escritorio/Detener Cognitive OS.sh`,
  `~/Escritorio/Estado Cognitive OS.sh` (con sus variantes `.desktop`).

Si un comando no existe, no lo inventes. Detecta scripts reales en
`pyproject.toml`, `package.json`, `Makefile`, `docs/RUNBOOK.md` o CI antes de
ejecutar.

<!-- CODEX_CLAUDE_SUPERVISION_START -->

## Codex role in this repository

Codex is the auditor, repair architect, and supervisor.

When the user requests a complete audit or repair-supervision workflow, use:

.codex/skills/comprehensive-project-audit/SKILL.md

Codex should:
- audit the repository
- produce evidence-based findings
- generate a remediation prompt addressed directly to Claude Code
- not perform the main implementation unless explicitly asked
- review Claude Code's changes after implementation
- approve or reject based on diff, tests, and evidence

## Claude Code handoff rule

When generating instructions for Claude Code:
- speak directly to Claude Code
- include exact constraints
- include ordered implementation phases
- include files likely involved
- include tests and commands
- include acceptance criteria
- include stop conditions
- forbid unrelated changes

<!-- CODEX_CLAUDE_SUPERVISION_END -->

<!-- COMPREHENSIVE_PROJECT_AUDIT_START -->

## Comprehensive Project Audit Mode

When the user asks for a complete audit, review, validation, hardening, or inspection of this project, use the local skill:

.codex/skills/comprehensive-project-audit/SKILL.md

Rules:
- First map the repository.
- Do not rely only on README.
- Use file evidence and command output.
- Do not claim the app works unless verified.
- Mark uncertainty explicitly.
- Run safe verification commands when appropriate.
- Do not modify source files during audit mode.
- Produce a severity-ranked report.
- Use subagents when the task is broad.
- Always perform a red-team second pass.

<!-- COMPREHENSIVE_PROJECT_AUDIT_END -->

# AGENTS.md

> **Estado actual (2026-05-17, Fase 41 Code Director F9 cerrada):**
> monorepo en grado comercial operativo. Backend FastAPI 0.115+ con
> **126 endpoints REST** (100 propios + 26 de orquestación), **16 tareas
> Celery** distribuidas en 5 colas (`default`, `ingestion`,
> `agent_longrun`, `maintenance`, `mail`), **16 migraciones Alembic**
> (head `202605160002`), LangGraph 1.1.10 + DeepAgents 0.6.x + OpenHarness
> opcional, mail multicuenta GoDaddy/Gmail con aprobación humana
> obligatoria y Google Maps/Calendar/Drive operables vía Action Plane sin
> writes directos. Frontend Next.js 16.2.6 + React 19 con **20 vistas**
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
> vivo del workspace + reintentos dirigidos por el error previo.
>
> Snapshot QA verde: **609 pytest passed, 1 skipped, 20 deselected**;
> ruff/mypy/lint/build/Compose/Alembic/detect-secrets/pre-commit (6 hooks)
> verdes. Único pendiente operador: autorizar `auth_google.py` (1 click
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

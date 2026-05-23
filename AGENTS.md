# AGENTS.md

> **Estado canónico actual (2026-05-23, commit `bbaaea8`):**
> **RELEASE APPROVED** — cuatro pasadas de auditoría independiente
> cerradas, cero defectos conocidos en el alcance auditado. Cognitive OS
> corre como instalación local dedicada. La prioridad definida por Diego
> es fricción casi nula por sobre seguridad estricta: puede usar Edge
> real/Kimi WebBridge, filesystem local y auto-resolución de aprobaciones
> en `dedicated_local/full` cuando el backend lo permita. `strict` queda
> como perfil conservador, no como objetivo principal de esta máquina.
>
> **Fuente de verdad:** `cognitive-os/docs/CURRENT_STATE.md` (estado
> canónico) y `cognitive-os/docs/ZERO_FRICTION_OPERATING_MODEL.md` (modelo
> operativo). Si algo aquí discrepa, esos archivos mandan.
>
> **Cierre formal:**
> `cognitive-os/docs/audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md`.
>
> **Snapshot técnico vigente** (conteos derivados del código por
> `scripts/sync_doc_counts.py`): backend FastAPI 0.115+ con **147 endpoints
> REST**, **23 tareas Celery** en **5 colas** (`default`, `ingestion`,
> `agent_longrun`, `maintenance`, `mail`) y hasta **13 jobs beat**; **20
> migraciones Alembic** head `202605200003`; **37 slash commands Telegram**
> (dispatch fail-closed); `/health/dashboard` con **18 componentes** +
> `POST /health/verify`; frontend Next.js 16.2.6 + React 19 con **20
> vistas**; LangGraph 1.1.10 + DeepAgents 0.6.x + cliente MCP + Action
> Plane. LLM: primary+agent `gpt-5.5`, secondary/fallback
> `gemini-3.1-pro-low`, visión `glm-4.6v`.
>
> **Gates vigentes (post `647f103`):**
> `bash cognitive-os/scripts/full-qa.sh` verde con **950 passed**, 1
> skipped, 28 deselected (944 históricos + 6 nuevos de regresión del
> bug `eager_defaults`; incluye ruff/format/mypy, Alembic check, frontend
> lint/build, `sync_doc_counts --check`, `git diff --check`); Playwright
> frontend **31 passed** sin necesidad de exportar `COGOS_JWT` (auto-mint
> via `POST /auth/local-token` en `dedicated_local/full`);
> `bash cognitive-os/scripts/stress-qa.sh` con 3 pasadas de **947
> passed**. Frontend QA usa `.next-qa` para no romper un `next start`
> vivo. Carril opt-in `tests/live/` (`LIVE_TESTS_ENABLED=1`) verificado
> con **8 smokes read-only passed**. TestSprite MCP re-auditoría dos
> batches **10/10 passed** (TC001/002/003/004/006/007/008/009/010/014).
>
> **Ajuste re-audit `647f103`:** `eager_defaults=True` en `db.Base`
> resuelve `MissingGreenlet` en endpoints `POST
> /actions/*/preview/request` y análogos; Playwright runner ahora
> zero-friction (auto-mint JWT). Detalles en
> `cognitive-os/docs/audits/testsprite/16_FINAL_REAUDIT_REPORT.md`.
>
> **Ajuste previo `5953b40`:** `/system/mcp` inventaria en paralelo con
> timeout 30s; runtime verificado 5/5 MCP servers y 67 tools. `Ctrl/Cmd+K`
> del cockpit quedó estabilizado.
>
> **Regla de mail vigente:** leer Gmail `diegomanzurn@gmail.com`
> `TODOS`+`SPAM` y GoDaddy `diego@doctormanzur.com` `Spam`; el agente
> clasifica spam por sí mismo; digest 10:00/20:00 Chile; respuestas
> sugeridas como texto. No drafts y no envío automático salvo solicitud
> explícita de Diego y flags de escape hatch.
>
> **Remediación del audit comercial (2026-05-22):** se cerraron las 8
> fallas accionables (AUDIT-2026-A..H) — Telegram fail-closed, health
> honesto (`configured` vs `verified` + `/health/verify`), kill switch
> `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED`, matriz de tests Telegram,
> carril live, componente `operational_backlog`, `sync_doc_counts.py` y
> `dev_up.sh` endurecido. Detalle en
> `cognitive-os/docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md` §0.1.
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
> 5. **Conservar anclajes E2E** que los tests existentes chequean
>    (`aria-label="JWT local"`, `URL base de la API`, `Abrir menú`,
>    `Cerrar`, literales `Estado global`, `componentes ok`, los labels
>    de `tests/e2e/_helpers.ts:TAB_LABELS`).

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
    DeepAgents 0.6.1<0.7, Celery 5.4+, SQLAlchemy 2 async, 113 archivos
    `tests/test_*.py` + carril opt-in `tests/live/` con 7 archivos / 8 smokes
    `live_readonly`).
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
  - `ACCEPTANCE_CHECKLIST.md` y `docs/` con runbooks y registries (versionados).
  - `task_plan.md`, `findings.md`, `progress.md` — bitácora de sesión, archivos
    de trabajo **locales y gitignored** (no versionados, AUDIT-2026-I); la
    skill `planning-with-files` los crea/usa en disco.
- `cognitive-os-backup-*/` y `cognitive-os-snapshot-*/` — **solo lectura**,
  gitignored, no editar.
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
`cognitive-os/findings.md`, `cognitive-os/progress.md` — archivos **locales
y gitignored** (bitácora de trabajo, no se versionan).

## Validación antes de terminar

Comandos reales detectados en este repo (úsalos según el área tocada):

Backend (`cognitive-os/backend/`):

- `uv sync` (con `--extra openharness` si vas a tocar el motor opcional).
- `uv run pytest` (snapshot vigente: **950 passed, 1 skipped, 28
  deselected**; el default deselecciona `integration`, `slow` y
  `live_readonly`).
- `uv run ruff check .` y `uv run ruff format --check .`.
- `uv run mypy src` (success, 135 source files).
- `uv run alembic check` (sin operaciones nuevas esperadas; excluye tablas
  runtime de LangGraph/PostgresSaver).
- Opt-in: `LIVE_TESTS_ENABLED=1 uv run pytest -m live_readonly` para los
  smokes read-only contra proveedores reales.

Frontend (`cognitive-os/frontend/`):

- `npm ci`
- `npm run lint` (0 warnings)
- `npm run build` (Next.js 16.2.6 OK)

Infra:

- `bash cognitive-os/scripts/dev_up.sh` — comando único correcto: valida las
  variables que el compose interpola sin default, levanta la infra y espera
  health checks. No invocar `docker compose` a mano sin `--env-file ../.env`.

Transversal:

- `git diff --check` (clean en estado actual).
- `pre-commit run --all-files` (config en `.pre-commit-config.yaml`).
- `bash cognitive-os/scripts/full-qa.sh` — suite QA completa
  (`uv sync --extra openharness` + pytest + ruff + ruff format + mypy + npm
  ci + npm lint + npm build + `sync_doc_counts --check` + `git diff --check`).
- `bash cognitive-os/scripts/stress-qa.sh` — 3 pasadas de pytest por defecto.
- `bash cognitive-os/scripts/full-qa-live.sh` — opt-in: smokes read-only
  contra proveedores reales.

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

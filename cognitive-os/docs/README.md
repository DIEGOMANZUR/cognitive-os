# Documentacion De Cognitive OS

> **Estado canonico actual (2026-05-23, commit `bbaaea8`):**
> **RELEASE APPROVED**. Cuatro pasadas de auditoría independiente
> cerradas con cero defectos conocidos. Para arrancar como usuario
> nuevo: empezá por **[`USER_GUIDE.md`](USER_GUIDE.md)** (didáctica,
> paso a paso). Para entender el estado actual del producto: leé
> primero [`CURRENT_STATE.md`](CURRENT_STATE.md) y
> [`ZERO_FRICTION_OPERATING_MODEL.md`](ZERO_FRICTION_OPERATING_MODEL.md).
> Esos dos archivos mandan: si algo aca discrepa, ellos ganan. Cierre
> formal del release:
> [`audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md`](audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md).
>
> Cognitive OS es un sistema cognitivo **local mono-operador** para un PC
> dedicado. Prioridad de producto: **friccion casi nula por sobre seguridad
> estricta**, con una excepcion dura en mail (lectura + propuesta, sin envio
> ni drafts en el flujo normal).
>
> **Snapshot tecnico vigente** (conteos derivados del codigo por
> `scripts/sync_doc_counts.py`):
>
> - Backend FastAPI 0.115+ — **150 endpoints REST**, **23 tareas Celery** en
>   **5 colas** (`default`, `ingestion`, `agent_longrun`, `maintenance`,
>   `mail`), hasta **13 jobs beat** segun flags.
> - **20 migraciones Alembic**, head `202605200003`, `alembic check` sin drift.
> - **37 slash commands Telegram** (dispatch fail-closed) + modo conversacional
>   sin slash en `dedicated_local`.
> - **18 componentes** en `/health/dashboard`; `POST /health/verify` para probe
>   real bajo demanda; componente `operational_backlog` para el backlog de
>   reapers.
> - Consola Next.js 16.2.6 + React 19 — **20 vistas**, PWA dark-only.
> - Orquestacion LangGraph 1.1.10 + DeepAgents 0.6.x + cliente MCP + Action
>   Plane. Ruta `research` fusionada con **OpenHarness** opcional (extra
>   `openharness-ai>=0.1.9,<0.2`, pipeline por defecto `prelude_merge`).
> - LLM: **primary+agent `gpt-5.5`** (Responses API + prompt caching 24h),
>   **secondary/fallback `gemini-3.1-pro-low`**, **vision `glm-4.6v`**.
> - QA: `full-qa.sh` **958 passed, 1 skipped, 28 deselected** + ruff/format/
>   mypy/Alembic/lint/build/`sync_doc_counts`/`git diff --check`; `stress-qa.sh`
>   3 pasadas verdes de **958 passed**; Playwright **41 passed** sin
>   exportar `COGOS_JWT` (auto-mint via `_global-setup.ts`); carril opt-in
>   `tests/live/` verificado con **8 passed**; TestSprite completo corregido
>   en batches locales **28/28 passed**.
>
> **Re-audit `647f103` (2026-05-23):** fix `eager_defaults=True` en
> `db.Base` resuelve `MissingGreenlet` 500 en endpoints
> `POST /actions/*/preview/request` y análogos. Playwright runner ahora
> zero-friction (auto-mintea JWT via `POST /auth/local-token` en
> `dedicated_local/full`). Reporte completo:
> [`audits/testsprite/16_FINAL_REAUDIT_REPORT.md`](audits/testsprite/16_FINAL_REAUDIT_REPORT.md).
>
> **Post-gate `5953b40`:** `/system/mcp` carga inventario en paralelo con
> `MCP_INVENTORY_TIMEOUT_SECONDS=30`; runtime verificado **5/5 MCP servers**
> y **67 tools**. El frontend estabiliza `Ctrl/Cmd+K` de la command palette.
>
> **Plan de aprendizaje autonomo (Fases A-E, `AGENT_LEARNING_PLAN.md`):** en
> produccion. Fase A recipe extractor, Fase B skill promotion (procedure →
> skill YAML con rollback automatico), Fase C tool scorecard, Fase D failure
> post-mortem, Fase E nightly reflection con evidencia literal obligatoria.
> Todo pasa por el approval gate del operador; la unica excepcion acotada es
> el auto-promote de warnings de Fase D, con kill switch
> `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED`.
>
> **Code Director:** meta-agente que delega builds a coding agents externos
> (Claude Code / Codex / Kimi CLI o DeepAgents in-process) bajo aprobacion
> humana + budget caps + audit, con planner LLM-driven y fallback heuristico.
>
> **Aislamiento de DB de test:** `pytest` nunca toca produccion —
> `tests/conftest.py` redirige a `cognitive_os_test`, recreada + migrada a head
> por corrida, con red de seguridad anti-produccion.
>
> **Remediacion del audit comercial (2026-05-22):** se cerraron las 8 fallas
> accionables (AUDIT-2026-A..H) — Telegram fail-closed, health honesto
> (`configured` vs `verified` + `/health/verify`), kill switch del auto-promote,
> matriz de tests Telegram, carril live, componente `operational_backlog`,
> `sync_doc_counts.py` y `dev_up.sh` endurecido. Detalle en
> `docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md` §0.1.

Este directorio contiene la documentacion estable del proyecto. Los archivos
`task_plan.md`, `findings.md` y `progress.md` de `cognitive-os/` no son
documentacion de producto: son bitacora de trabajo de sesion, archivos locales
**gitignored** (no versionados, AUDIT-2026-I).

## Leer Primero

1. **`CURRENT_STATE.md` — fuente corta de verdad del estado actual, gates verdes, conteos y contrato de mail.**
2. **`ZERO_FRICTION_OPERATING_MODEL.md` — postura de producto: PC dedicado, friccion casi nula por sobre seguridad estricta.**
3. **`USER_GUIDE.md` — Guía de Usuario comercial: qué es Cognitive OS de principio a fin, frontend vista por vista (qué cambia cada acción), pipelines internos, uso desde Telegram, ejemplos impresionantes, "qué hace / qué no hace", "cómo NO usar el sistema".**
4. `COGNITIVE_OS_GUIDE.md` — guía maestra técnica "desde cero" con arquitectura detallada, mail multicuenta, ejecutables de escritorio y troubleshooting profundo. Complementa la `USER_GUIDE.md`.
5. `../README.md` - entrada principal, comandos basicos y mapa rapido.
6. `PROJECT_GUIDE.md` - explicacion simple y tecnica del producto completo.
7. `ARCHITECTURE.md` - arquitectura interna y flujo entre componentes.
8. **`FRONTEND_ARCHITECTURE.md` — arquitectura del cockpit Next.js (Fase 82 Glass Cockpit): stack, tokens, patterns (`asArray`, `usePolledFetch` resiliente, `StatePrimitives`, focus trap), PWA, anti-patrones, checklist pre-PR.**
9. `OPENHARNESS_FUSION.md` - fusión actual OpenHarness + LangGraph + DeepAgents en la ruta **research**.
10. `RUNBOOK.md` - como operar, levantar, apagar, respaldar y restaurar.
11. `SECURITY.md` - referencia de seguridad/safety; no es la prioridad principal en el PC dedicado.
12. `OPERATOR_VARIABLE_CHECKLIST.md` — variables de entorno ↔ `Settings` (auditoría operador).
13. `SETTINGS_REGISTRY_TABLE.md` — tabla generada 1:1 desde `config.py` (no editar a mano).
14. `guia_credenciales.md` — **paso a paso para obtener cada credencial**: a qué web entrar, qué botón apretar (nombre/ubicación/color), hasta pegar el valor en `.env`.
15. `AGENT_LEARNING_PLAN.md` — plan de aprendizaje autónomo del agente (Fases A-E, todas cerradas).

## Documentacion Por Area

| Archivo | Para que sirve |
|---|---|
| `CURRENT_STATE.md` | Estado canonico actual: conteos, gates verdes, runtime, mail, frontend, advertencias de no afirmar sin revalidar |
| `ZERO_FRICTION_OPERATING_MODEL.md` | Modelo operativo del PC dedicado: friccion casi nula primero, seguridad estricta relegada, excepcion dura de mail |
| `USER_GUIDE.md` | Guía de Usuario comercial: estado actual, principio a fin, frontend vista por vista, pipelines, Telegram, ejemplos impresionantes, qué hace / qué no, cómo NO usar |
| `COGNITIVE_OS_GUIDE.md` | Guía maestra técnica "desde cero": arquitectura detallada, mail multicuenta, escritorio, credenciales, troubleshooting profundo |
| `FRONTEND_ARCHITECTURE.md` | Arquitectura del cockpit Next.js (Fase 82 Glass Cockpit): tokens, patterns (`asArray`, `usePolledFetch` resiliente, `StatePrimitives`, focus trap), PWA, anti-patrones, checklist pre-PR |
| `ACTION_PLANE.md` | Browser, computador local, Gmail, Google Maps/Calendar/Drive, mail personal GoDaddy/Gmail, GoDaddy DNS y generación de documentos Office en modo seguro |
| `OPENHARNESS_FUSION.md` | Fusión OpenHarness (QueryEngine) con LangGraph y DeepAgents en **research** |
| `PERSONAL_ASSISTANT_ROADMAP.md` | Brechas y fases para convertir Cognitive OS en asistente personal |
| `DEEPAGENTS_INTEGRATION.md` | Como DeepAgents encaja bajo control de Cognitive OS (tools, policy, fallback) |
| `DEEPAGENTS_SKILLS_MEMORY.md` | Skills (core/user) y memoria con propuestas + aprobación humana |
| `DOCUMENT_ANALYSIS_AGENT.md` | Subagente legal: matriz, timeline, contradicciones, borradores controlados |
| `OPENSHELL_SANDBOX.md` | Ejecución de código aislada vendor-side, deshabilitada por defecto |
| `AGENT_LEARNING_PLAN.md` | Plan de aprendizaje autónomo del agente: Fases A-E (recetas, warnings, scorecard, skill promotion, reflexión nocturna) — todas en producción |

## Estado Actual

El sistema tiene una base **grado comercial operativa** con backend FastAPI
0.115+, frontend Next.js 16.2.6, **5 queues Celery** (`default`,
`ingestion`, `agent_longrun`, `maintenance`, `mail`), memoria persistida
(`DeepAgentMemoryService`), document analysis legal (6 modos), sandbox
opcional OpenShell, correo personal multicuenta read-only (Gmail
`TODOS`/`SPAM` + GoDaddy `Spam`), Google Maps/Calendar/Drive y action plane con solicitudes persistentes
(`ActionRequest`).

Hay ejecución real controlada para `computer_organize`,
`computer_inventory` (read-only), `document_generate` (DOCX/XLSX/PPTX),
`browser_preview` y `browser_interactive` (Playwright + vision multimodal),
Google Calendar create y Drive upload/folder/organize bajo `ActionRequest`,
Maps read-only con tráfico, Calendar free/busy read-only, Gmail read-only, mail
GoDaddy/Gmail con digest y propuestas escritas sin drafts ni envío normal, GoDaddy DNS bajo
dry-run, allow-lists, Celery y auditoría.

Fase 33 cerró el núcleo de Fase 29: RBAC local explícito, cifrado at-rest
de `payload_executable` y persistencia durable configurable del orquestador de research.

En la ruta **research**, el grafo puede invocar de forma opcional **OpenHarness**
(instalación extra `openharness-ai`) antes de DeepAgents: por defecto
**`OPENHARNESS_RESEARCH_PIPELINE=prelude_merge`**, los apuntes del harness van en
`metadata["openharness_prelude"]` y DeepAgents los integra en el mensaje de
usuario manteniendo su política de citas y tools. Modo **`short_circuit`**
devuelve sólo OpenHarness cuando responde bien. Ver `OPENHARNESS_FUSION.md`.

## Regla De Mantenimiento

Cuando agregues o cambies una variable en `backend/src/cognitive_os/core/config.py`:

1. Regenera `SETTINGS_REGISTRY_TABLE.md` desde `backend/`:
   `uv run python scripts/dump_settings_registry.py --out ../docs/SETTINGS_REGISTRY_TABLE.md`.

Cuando agregues una capacidad nueva:

1. Actualiza `PROJECT_GUIDE.md` si cambia la forma de explicar el sistema.
2. Actualiza el documento del area afectada.
3. Actualiza `RUNBOOK.md` si cambia la operacion.
4. Actualiza `SECURITY.md` si cambia el riesgo.
5. Agrega o actualiza pruebas antes de marcarlo como listo.

# Documentacion De Cognitive OS

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-27, Prompt 7).** Esta rama `codex/commercial-zero-friction-hardening` queda certificada como **APTA COMERCIAL LOCAL-FIRST** para PC dedicado. Branch inicial Prompt 1: HEAD `2bb4966`. Working tree del Prompt 7 consolida los cambios de Prompts 3 (F-P2-001..006), 4 (F-P4-001 fix wrapper timeout mcp_client live probe) y 6 (V2-EVAL-001 DocAnalysis API consistency). El commit final del Prompt 7 firma todo el delta V2.0 sin push. Evidencia viva en `tmp/v2_07_absolute_release_closure_20260527_175541/`.
>
> **Hallazgos cerrados V2.0 (12):** F-P2-001 wildcard_allow_all transparency · F-P2-002 stress flake eliminado (0% en 5×1232) · F-P2-003 `?limit=` honored en `/approvals` y `/actions/drive/files` · F-P2-004 `/chat` 404/400 con `missing_doc_ids`/`invalid_doc_ids` · F-P2-005 docs sync (este bloque) · F-P2-006 `_check_mcp(verify_live=True)` → overall `ok` · F-P4-001 timeout wrapper +5s sobre `mcp_inventory_timeout_seconds` · F-P4-002 fallback heurístico DocAnalysis documentado · F-P4-003 Kimi extension boot oscillation documentado · V2-EVAL-001 `GET /document-analysis/{id}` mirror artefacto · V2-EVAL-004 endpoints memoria/aprendizaje live (303 proposals, 209 recipes, 94 warnings) · V2-EVAL-005 Code Director adapter=deepagent plan+approval+reject sin exec.
>
> **Gates V2.0 medidos antes del cierre absoluto:** `bash scripts/full-qa.sh` **1232 passed, 1 skipped, 28 deselected** (ruff/format/mypy/alembic/sync_doc_counts/git-diff verdes); `bash scripts/stress-qa.sh 5` **5/5 verde × 1232 passed**, flakiness **0%**; `cd frontend && npx playwright test` **44 passed**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/openapi_readonly_smoke.py` **70 GET / 0 failures**; `bash scripts/verify_desktop_launchers.sh` OK; security-readonly-qa (bandit/semgrep/secret-scan) clean; `POST /health/verify` overall **`ok`** con `mcp_client` live `ok` 6/6 y 69 tools; checklist 400 puntos ejecutada.
>
> **Criterio de verdad:** no se declara envío de correo, draft real ni escritura DNS. Mail queda normalizado como read-only (sync/list/classify/digest + proposed replies como texto). GoDaddy preview/dry-run. Action Plane mantiene `validate→preview→request→approve→dispatch→execute→audit` con idempotencia y reapers. El runtime corre en `127.0.0.1` sin exposición LAN/internet. El frontend `cognitive.doctormanzur.com` se levanta on-demand sólo con `scripts/testsprite_web/deploy_and_verify.sh`; Prompt 7 V2.0 no lo expone permanentemente. **Cognitive OS queda certificado en este commit como APTO COMERCIAL LOCAL-FIRST para PC dedicado, con funcionamiento real activado, documentación sincronizada, dos ciclos completos verdes posteriores al último cambio, Git ordenado y sin P0/P1/P2 abiertos.**

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


> **Estado canonico actual (2026-05-26, HEAD `8a33475`):**
> **COMERCIAL LOCAL-FIRST APROBADO + frontend/TestSprite web hardening**. La base
> local-first 2026-05-25 permanece certificada; el estado vigente agrega el
> cockpit público endurecido para `https://cognitive.doctormanzur.com`: hash auth
> `#cogos_token`, API pública por host, TopBar retirado, hotkey `3 DeepAgents`,
> estados comerciales para colecciones, responsive 920px y service worker
> `cogos-v2026-05-26e-status-cards`. Para arrancar como usuario nuevo: empezá
> por **[`USER_GUIDE.md`](USER_GUIDE.md)**. Para entender el estado actual del
> producto: leé primero [`CURRENT_STATE.md`](CURRENT_STATE.md) y
> [`ZERO_FRICTION_OPERATING_MODEL.md`](ZERO_FRICTION_OPERATING_MODEL.md). Esos
> archivos mandan: si algo aca discrepa, ellos ganan. El handoff público de
> TestSprite web es `bash scripts/testsprite_web/deploy_and_verify.sh`; no se
> declara doble verde web sin reportes/PDFs del portal.
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
> - QA: `full-qa.sh` **1200 passed, 1 skipped, 28 deselected** + ruff/format/
>   mypy/Alembic/lint/build/`sync_doc_counts`/`git diff --check`; `stress-qa.sh 5`
>   **5/5 verde × 1200 passed**; Playwright **43 passed** sin exportar
>   `COGOS_JWT` (auto-mint via `_global-setup.ts`); carril opt-in `tests/live/`
>   verificado con **8 passed**; TestSprite local batched histórico **28/28
>   passed**; TestSprite web público se entrega con `deploy_and_verify.sh`.
>
> **Re-audit `647f103` (2026-05-23):** fix `eager_defaults=True` en
> `db.Base` resuelve `MissingGreenlet` 500 en endpoints
> `POST /actions/*/preview/request` y análogos. Playwright runner ahora
> zero-friction (auto-mintea JWT via `POST /auth/local-token` en
> `dedicated_local/full`). Reporte completo:
> [`audits/testsprite/16_FINAL_REAUDIT_REPORT.md`](audits/testsprite/16_FINAL_REAUDIT_REPORT.md).
>
> **Post-gate `5953b40`:** `/system/mcp` carga inventario en paralelo con
> `MCP_INVENTORY_TIMEOUT_SECONDS=30`; runtime actual verificado **6/6 MCP
> servers** y **69 tools** tras agregar el MCP local `time` (2 tools:
> `time_time_now`, `time_time_convert`). El frontend estabiliza `Ctrl/Cmd+K`
> de la command palette.
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

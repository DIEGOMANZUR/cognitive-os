# Documentacion De Cognitive OS

> **Estado actual (2026-05-20, Fases 78-81 — plan de aprendizaje autónomo
> completo; suite hermética 800 passed con DB de test aislada):**
> producto en grado comercial operativo con backend FastAPI 0.115+
> (**143 endpoints REST**, **22 tareas Celery** en **5 queues** con
> **10 jobs beat**, **20 migraciones Alembic** head `202605200003`,
> **37 slash commands Telegram**, **17 componentes `/health`**) +
> LangGraph 1.1.10 + DeepAgents 0.6.x + cliente MCP + Action Plane,
> correo personal multicuenta GoDaddy/Gmail con aprobación humana
> (`MAIL_REQUIRE_APPROVAL_FOR_SEND=true`), Google Maps/Calendar/Drive
> operables sin writes directos, infra de datos ligada a `127.0.0.1`, y
> consola Next.js 16.2.6 (**20 vistas**). La ruta `research` está
> fusionada con **OpenHarness** opcional (extra
> `openharness-ai>=0.1.9,<0.2`), pipeline por defecto `prelude_merge`,
> workspace `deepagent_mirror`. Documento canónico de la fusión:
> `OPENHARNESS_FUSION.md`. LLM: **primary+agent `gpt-5.5`** (Responses
> API + prompt caching 24h), **secondary/fallback `gemini-3.1-pro-low`**,
> **visión `glm-4.6v`**.
>
> **Plan de aprendizaje autónomo (Fases A-E, `AGENT_LEARNING_PLAN.md`):**
> cerrado en producción. F78 Fase A (recipe extractor), F79.3 Fase D
> (failure post-mortem), F79.4 Fase C (tool scorecard), F80 Fase B
> (skill promotion: procedure → skill YAML con rollback automático), F81
> Fase E (nightly reflection con evidencia literal obligatoria). 2 tablas
> nuevas (`procedure_invocation_log`, `tool_invocation_metrics`),
> endpoints `/deepagents/learning/*`, panel completo en `MemoryView`.
> Todo pasa por el approval gate del operador.
>
> **Aislamiento de DB de test:** `pytest` nunca toca producción —
> `tests/conftest.py` redirige a `cognitive_os_test`, recreada + migrada
> a head por corrida, con red de seguridad anti-producción.
>
> Fase 40 (2026-05-17) añadió el **Code Director**: meta-agente que
> delega builds a coding agents externos (Claude Code / Codex / Kimi CLI
> o DeepAgents in-process) bajo aprobación humana + budget caps + audit.
> Fase 41 lo llevó a "máximo nivel F9": **planner LLM-driven** que
> descompone objetivos en subtareas reales con fallback heurístico
> determinista, y **prompts con contexto vivo** del workspace +
> reintentos dirigidos por el error previo. Fase 39 cerró los residual
> risks técnicos: rate limiter pluggable memory/Redis,
> `/system/credentials-status` (admin) con inventario vivo de las 21
> credenciales operador, `workflow.v1` export/import, OAuth Google
> self-healing, wizard `init_credentials.sh`, correlation IDs
> `X-Request-ID`, approval reaper, four-eyes, AuditEvent simétrico
> REST↔Telegram. Fases 44-49 consolidaron Google Ops avanzado; Fases
> 50-58 cerraron Telegram approvals con dispatch real de `ActionRequest`
> y agregaron smoke reproducible de launchers de escritorio. Fases 59-63
> endurecieron dispatch con broker failure controlado y JobEvents submit/fail.
> Fase 64 agregó reserva atómica para impedir submits duplicados a Celery.
> Fase 65 cerró paridad Telegram↔UI (36 slash commands) y corrigió el
> CHECK `ck_ar_action_type` que rompía Drive folder/organize en Postgres.
> QA: **685 pytest passed, 1 skipped, 20 deselected**; ruff/format/mypy,
> frontend lint/build, Alembic head `202605170001` y `git diff --check` verdes.

Este directorio contiene la documentacion estable del proyecto. Los archivos
`task_plan.md`, `findings.md` y `progress.md` en la raiz no son documentacion de
producto: son bitacora de trabajo de la sesion actual.

## Leer Primero

1. **`USER_GUIDE.md` — Guía de Usuario comercial: qué es Cognitive OS de principio a fin, frontend vista por vista (qué cambia cada acción), pipelines internos, uso desde Telegram, ejemplos impresionantes, "qué hace / qué no hace", "cómo NO usar el sistema". Empieza aquí.**
2. `COGNITIVE_OS_GUIDE.md` — guía maestra técnica "desde cero" con arquitectura detallada, mail multicuenta, ejecutables de escritorio y troubleshooting profundo. Complementa la `USER_GUIDE.md`.
3. `../README.md` - entrada principal, comandos basicos y mapa rapido.
4. `PROJECT_GUIDE.md` - explicacion simple y tecnica del producto completo.
5. `ARCHITECTURE.md` - arquitectura interna y flujo entre componentes.
6. `OPENHARNESS_FUSION.md` - fusión actual OpenHarness + LangGraph + DeepAgents en la ruta **research**.
7. `RUNBOOK.md` - como operar, levantar, apagar, respaldar y restaurar.
8. `SECURITY.md` - reglas de seguridad y controles obligatorios.
9. `OPERATOR_VARIABLE_CHECKLIST.md` — variables de entorno ↔ `Settings` (auditoría operador).
10. `SETTINGS_REGISTRY_TABLE.md` — tabla generada 1:1 desde `config.py` (no editar a mano).
11. `guia_credenciales.md` — **paso a paso para obtener cada credencial**: a qué web entrar, qué botón apretar (nombre/ubicación/color), hasta pegar el valor en `.env`.
12. `AGENT_LEARNING_PLAN.md` — plan de aprendizaje autónomo del agente (Fases A-E, todas cerradas).

## Documentacion Por Area

| Archivo | Para que sirve |
|---|---|
| `USER_GUIDE.md` | Guía de Usuario comercial: estado actual, principio a fin, frontend vista por vista, pipelines, Telegram, ejemplos impresionantes, qué hace / qué no, cómo NO usar |
| `COGNITIVE_OS_GUIDE.md` | Guía maestra técnica "desde cero": arquitectura detallada, mail multicuenta, escritorio, credenciales, troubleshooting profundo |
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
opcional OpenShell, correo personal multicuenta GoDaddy IMAP/SMTP +
Gmail label `TODOS`, Google Maps/Calendar/Drive y action plane con solicitudes persistentes
(`ActionRequest`).

Hay ejecución real controlada para `computer_organize`,
`computer_inventory` (read-only), `document_generate` (DOCX/XLSX/PPTX),
`browser_preview` y `browser_interactive` (Playwright + vision multimodal),
Google Calendar create y Drive upload/folder/organize bajo `ActionRequest`,
Maps read-only con tráfico, Calendar free/busy read-only, Gmail read-only, mail
GoDaddy IMAP/SMTP con propuestas escritas y envío aprobado, GoDaddy DNS bajo
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

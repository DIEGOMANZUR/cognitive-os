# Documentacion De Cognitive OS

> **Estado actual (2026-05-15, Fase 33 RBAC + cifrado + research durable):** producto en grado comercial
> operativo con backend FastAPI 0.115+ (**118 endpoints REST**, **14 tareas
> Celery** en **5 queues**, **16 migraciones Alembic**) + LangGraph 1.1.10 +
> DeepAgents 0.6.x + Action Plane, correo personal multicuenta GoDaddy/Gmail
> con aprobación humana (`MAIL_REQUIRE_APPROVAL_FOR_SEND=true`), Google
> Maps/Calendar/Drive operables sin writes directos, infra de datos ligada a
> `127.0.0.1`, y consola Next.js 16.2.6 (**18 vistas**). La ruta `research` está fusionada con
> **OpenHarness** opcional (extra `openharness-ai>=0.1.9,<0.2`), pipeline
> por defecto `prelude_merge`, workspace `deepagent_mirror`. Documento
> canónico de la fusión: `OPENHARNESS_FUSION.md`. El runtime local usa
> **DeepSeek V4 Pro** (`deepseek-v4-pro`) como LLM base; secundario Kimi
> K2.6-code-preview; vision GLM-4.6v. QA: **497 pytest passed, 1 skipped,
> 20 deselected**; ruff/mypy/lint/build, Compose config, Alembic head y diff verdes.

Este directorio contiene la documentacion estable del proyecto. Los archivos
`task_plan.md`, `findings.md` y `progress.md` en la raiz no son documentacion de
producto: son bitacora de trabajo de la sesion actual.

## Leer Primero

1. **`COGNITIVE_OS_GUIDE.md` — guía maestra "desde cero" con todo: arquitectura, frontend (18 vistas, incluidas `Assist` y `Google Ops`), mail multicuenta, Google Ops, Telegram, ejecutables de escritorio, credenciales por capacidad, casos de uso y troubleshooting. Empieza aquí si nunca habías visto el proyecto.**
2. `../README.md` - entrada principal, comandos basicos y mapa rapido.
3. `PROJECT_GUIDE.md` - explicacion simple y tecnica del producto completo.
4. `ARCHITECTURE.md` - arquitectura interna y flujo entre componentes.
5. `OPENHARNESS_FUSION.md` - fusión actual OpenHarness + LangGraph + DeepAgents en la ruta **research**.
6. `RUNBOOK.md` - como operar, levantar, apagar, respaldar y restaurar.
7. `SECURITY.md` - reglas de seguridad y controles obligatorios.
8. `OPERATOR_VARIABLE_CHECKLIST.md` — variables de entorno ↔ `Settings` (auditoría operador).
9. `SETTINGS_REGISTRY_TABLE.md` — tabla generada 1:1 desde `config.py` (no editar a mano).
10. `IMPROVEMENT_EXECUTION_PLAN.md` — plan de mejoras continuas (config y docs).

## Documentacion Por Area

| Archivo | Para que sirve |
|---|---|
| `COGNITIVE_OS_GUIDE.md` | Guía maestra "desde cero": qué es, para qué sirve y para qué no, frontend, mail, Telegram, escritorio, credenciales, casos de uso, troubleshooting |
| `ACTION_PLANE.md` | Browser, computador local, Gmail, Google Maps/Calendar/Drive, mail personal GoDaddy/Gmail, GoDaddy DNS y generación de documentos Office en modo seguro |
| `OPENHARNESS_FUSION.md` | Fusión OpenHarness (QueryEngine) con LangGraph y DeepAgents en **research** |
| `PERSONAL_ASSISTANT_ROADMAP.md` | Brechas y fases para convertir Cognitive OS en asistente personal |
| `DEEPAGENTS_INTEGRATION.md` | Como DeepAgents encaja bajo control de Cognitive OS (tools, policy, fallback) |
| `DEEPAGENTS_SKILLS_MEMORY.md` | Skills (core/user) y memoria con propuestas + aprobación humana |
| `DOCUMENT_ANALYSIS_AGENT.md` | Subagente legal: matriz, timeline, contradicciones, borradores controlados |
| `OPENSHELL_SANDBOX.md` | Ejecución de código aislada vendor-side, deshabilitada por defecto |
| `IMPROVEMENT_EXECUTION_PLAN.md` | Estado de las fases A→E para hardening de configuración, docs y sala de máquinas |

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
Google Calendar/Drive writes bajo `ActionRequest`, Maps read-only con tráfico,
Gmail read-only, mail GoDaddy IMAP/SMTP con propuestas escritas y envío aprobado,
GoDaddy DNS bajo dry-run, allow-lists, Celery y auditoría.

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

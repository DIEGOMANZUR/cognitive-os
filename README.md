# Cognitive OS

> **Sistema operativo cognitivo local-first para PC dedicado.** Un agente de IA
> que vive en tu máquina, con tus credenciales reales, capaz de investigar,
> analizar documentos legales, gestionar correo, operar Google, controlar el
> navegador real y delegar tareas de programación — todo bajo un plano de
> control auditable con compuertas humanas alrededor de cada acción sensible.

**Estado:** ✅ **APTO COMERCIAL LOCAL-FIRST** (certificado V2.0, 2026-05-28).
Branch `main`. Sin P0/P1/P2 abiertos. Dos ciclos completos de QA verdes.

| Métrica | Valor |
|---|---|
| Backend | FastAPI · **150 endpoints REST** · **23 tareas Celery** en 5 colas |
| DB | PostgreSQL 16 + pgvector · **20 migraciones Alembic** (head `202605200003`) |
| Frontend | Next.js 16 + React 19 · **20 vistas** · PWA dark-only (sin Tailwind/shadcn) |
| Orquestación | LangGraph 1.1 + DeepAgents 0.6 + cliente MCP (**6/6 servers, 70 tools**) |
| Telegram | **37 slash commands** + modo conversacional |
| Health | `/health/dashboard` con **18 componentes** + `/health/verify` en vivo |
| QA | `full-qa.sh` **1269 passed** · `stress-qa.sh 5` 5/5 · Playwright **44 passed** |

---

## ¿Qué hace?

- **RAG con citas**: ingesta PDFs y responde citando `doc_id`/`page`/`chunk`.
- **Análisis de documentos legales**: 6 modos (matriz de evidencia, timeline,
  contradicciones, full report, soporte a borradores, resumen de caso), 4
  formatos descargables (JSON/MD/CSV/DOCX), con aprobación humana.
- **Correo read-only**: lee y clasifica Gmail + GoDaddy, genera digest y propone
  respuestas como texto. **No envía ni crea drafts** en el flujo normal.
- **Action Plane**: navegador (headless + Edge real), filesystem, Google
  (Maps/Calendar/Drive), GoDaddy DNS, generación de Office — todo con ciclo
  `validate → preview → request → approve → dispatch → execute → audit`.
- **Code Director**: delega builds a Claude Code / Codex / Kimi / DeepAgents bajo
  aprobación + budget + audit.
- **Aprendizaje autónomo** (Fases A–E): recetas, skills, scorecard, postmortems y
  reflexión nocturna — todo bajo la puerta de aprobación del operador.

## ¿Qué NO hace?

Por diseño: no envía correos ni crea drafts en el flujo normal · no escribe DNS
real sin opt-in explícito · no corre código sin sandbox + approval · no toca
`~/.ssh`/`~/.gnupg`/credenciales · no se expone a internet (todo en `127.0.0.1`) ·
no es multi-tenant ni SaaS.

---

## Arranque rápido

**Requisitos:** Python ≥ 3.12 + [uv](https://docs.astral.sh/uv/), Node.js ≥ 22,
Docker.

```bash
# 1. Levantar infra (Postgres + Redis + Weaviate + Neo4j) con healthchecks
bash cognitive-os/scripts/dev_up.sh

# 2. Backend
cd cognitive-os/backend && uv sync
uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000

# 3. Worker + beat (en otras terminales, desde la raíz)
bash cognitive-os/scripts/dev_worker.sh
bash cognitive-os/scripts/dev_beat.sh

# 4. Frontend
cd cognitive-os/frontend && npm ci && npm run serve   # → http://127.0.0.1:3001

# 5. Verificar
curl http://127.0.0.1:8000/health     # {"status":"ok","service":"cognitive-os"}
```

En el PC del operador todo esto está envuelto en los lanzadores de escritorio:
`Levantar / Reiniciar / Detener / Estado Cognitive OS.sh`.

**Configuración:** copiá `cognitive-os/.env.example` a `cognitive-os/.env` y
completá tus credenciales. Los secretos nunca se commitean (`.gitignore` +
`.pre-commit-config.yaml` con gitleaks/detect-secrets).

---

## Verificación / QA

```bash
cd cognitive-os
bash scripts/full-qa.sh        # pytest + ruff + mypy + alembic + build + sync  (1269 passed)
bash scripts/stress-qa.sh 5    # 5 pasadas (detección de flakiness)             (5/5 verde)
cd frontend && npx playwright test                                              # 44 passed
LIVE_TESTS_ENABLED=1 bash ../scripts/full-qa-live.sh   # smokes read-only opt-in (8 passed)
```

---

## Documentación

La guía completa vive en [`cognitive-os/docs/`](cognitive-os/docs/):

| Documento | Para qué |
|---|---|
| [`USER_GUIDE.md`](cognitive-os/docs/USER_GUIDE.md) | **Empieza aquí** — guía de usuario completa, función por función, con ejemplos. |
| [`CURRENT_STATE.md`](cognitive-os/docs/CURRENT_STATE.md) | Fuente corta de verdad del estado operativo. |
| [`ARCHITECTURE.md`](cognitive-os/docs/ARCHITECTURE.md) | Arquitectura técnica completa. |
| [`COGNITIVE_OS_GUIDE.md`](cognitive-os/docs/COGNITIVE_OS_GUIDE.md) | Guía maestra técnica desde cero. |
| [`ACTION_PLANE.md`](cognitive-os/docs/ACTION_PLANE.md) | Capa de acciones (browser, computer, Google, DNS, Office). |
| [`SECURITY.md`](cognitive-os/docs/SECURITY.md) | Modelo de seguridad y safety operativa. |
| [`RUNBOOK.md`](cognitive-os/docs/RUNBOOK.md) | Operación diaria. |
| [`ZERO_FRICTION_OPERATING_MODEL.md`](cognitive-os/docs/ZERO_FRICTION_OPERATING_MODEL.md) | Modelo operativo `dedicated_local/full`. |
| [`AGENT_LEARNING_PLAN.md`](cognitive-os/docs/AGENT_LEARNING_PLAN.md) | Aprendizaje autónomo Fases A–E. |
| [`DEEPAGENTS_INTEGRATION.md`](cognitive-os/docs/DEEPAGENTS_INTEGRATION.md) | DeepAgents, tools y políticas. |
| [`DOCUMENT_ANALYSIS_AGENT.md`](cognitive-os/docs/DOCUMENT_ANALYSIS_AGENT.md) | Pipeline de análisis legal. |
| [`docs/audits/`](cognitive-os/docs/audits/) | Certificaciones y auditorías firmadas. |

---

## Arquitectura en una imagen

```
┌──────────────┐   ┌──────────────┐   ┌────────────────────────────────────┐
│   Next.js    │   │   Telegram   │   │              FastAPI app            │
│ (cockpit web │──▶│  bot (37 cmd)│──▶│  /chat /documents /document-analysis │
│   :3001)     │   │              │   │  /actions/* /mail/* /code-director/* │
└──────────────┘   └──────────────┘   │  /deepagents/* /system/* /health/*   │
                                       └────────────────┬───────────────────┘
                  ┌────────────────────────────────────┼─────────────────────┐
                  ▼                  ▼                   ▼                     ▼
          ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    ┌──────────────┐
          │  LangGraph   │  │  DeepAgents  │  │ Action Plane │    │ Celery + Redis│
          │ orquestador  │  │ + MCP tools  │  │ (preview→    │    │ (5 colas,     │
          │ (checkpointer│  │  dinámicas   │  │  approve→    │    │  reapers,     │
          │  Postgres)   │  │              │  │  audit)      │    │  beat)        │
          └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    └──────────────┘
                 ▼                 ▼                 ▼
        Postgres+pgvector    Weaviate (RAG)    Neo4j (grafo)   — todo en 127.0.0.1
```

---

## Licencia y uso

Proyecto personal local-first de un solo operador. Corre en `127.0.0.1`, no está
endurecido para internet público ni para uso multi-usuario. Ver
[`SECURITY.md`](cognitive-os/docs/SECURITY.md) antes de cambiar de contexto.

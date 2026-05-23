# AGENT_LEARNING_PLAN — Cómo el agente aprende solo

> **Actualización vigente (2026-05-22):** el plan de aprendizaje autónomo
> está implementado y convive con el modelo operativo de baja fricción.
> La prioridad del sistema en este PC dedicado es reducir fricción por
> sobre seguridad estricta, pero las promociones de memoria/skills siguen
> pasando por proposals porque afectan el comportamiento futuro del agente.
> La **única excepción de auto-deploy** es el auto-promote de *warnings* de
> Fase D, con kill switch `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED` (default
> `true`, AUDIT-2026-C) — ver §1 y §3.4.
> QA vigente del repo (commit `647f103`): `full-qa.sh` **950 passed**,
> 1 skipped, 28 deselected; Playwright **31 passed** sin exportar
> `COGOS_JWT` (auto-mint via `_global-setup.ts`); stress QA 3 pasadas
> de **950 passed**; TestSprite re-audit 10/10 passed. Ver
> `CURRENT_STATE.md`.

> Documento de handoff. Pensado para que un chat nuevo entienda **(a)** el estado
> actual del proyecto, **(b)** la arquitectura de memoria existente, y
> **(c)** las 5 fases del plan de aprendizaje autónomo, con código, schemas,
> tests y orden de implementación.

Branch vigente de hardening: `codex/commercial-zero-friction-hardening`.

## 🟢 Status — Plan completo: las 5 fases en producción (F78-F81, 2026-05-20)

| Fase | Commit | Estado |
|---|---|---|
| **A — Recipe extractor** | F78 | ✅ Cerrada |
| **D — Failure post-mortem** | F79.3 | ✅ Cerrada |
| **C — Tool scorecard** | F79.4 | ✅ Cerrada |
| **B — Skill promotion** | F80 | ✅ Cerrada |
| **E — Nightly reflection** | F81 | ✅ Cerrada |

Notas de implementación de las dos últimas fases:

- **Fase B (F80):** nueva tabla `procedure_invocation_log` + ORM
  `ProcedureInvocationLog`. El worker DeepAgent loguea las invocaciones
  de cada `kind=procedure` activo al arrancar y marca el outcome
  (success/failure) al terminar — filtrado por agente para que el conteo
  refleje sólo procedures realmente inyectados en ese prompt. El promoter
  (`deepagents/skill_promoter.py`) emite una proposal cuando un procedure
  tiene ≥3 éxitos y <30% de fallos; al aprobarla se materializa un skill
  YAML en `storage/deepagents/skills/user/_auto/<slug>/SKILL.md`. Rollback
  automático si el `failure_rate` post-promoción supera 50% en 30 días.
  **No hay auto-promoción** — toda promoción requiere approval explícito
  del operador (§7). La ruta B.2 (code-based vía Code Director) queda como
  follow-up: la proposal registra la intención (`route="yaml"`).
- **Fase E (F81):** `deepagents/nightly_reflection.py` construye un
  transcript auditado desde Jobs/JobEvents/HumanApprovals (no toca las
  tablas internas de LangGraph) y pide al LLM primario preferences/lessons.
  El validador descarta cualquier proposal cuyas `evidence_quotes` no
  aparezcan **literalmente** en el transcript, cuyas quotes midan menos de
  12 caracteres, o cuyos `evidence_message_ids` no existan. Circuit breaker
  de auto-disable si el operador rechaza >50% de las proposals en 30 días.
- Endpoints nuevos: `GET/POST /deepagents/learning/skill-promotions[/…]`,
  `GET/POST /deepagents/learning/reflection[/run-now]`.
- UI: secciones "Promociones a skill" y "Reflexiones nocturnas" en
  `MemoryView.tsx`, con quotes literales visibles como evidencia.
- Celery beat: `skill-promoter` (04:45 UTC) y `nightly-reflection`
  (03:00 UTC), ambos detrás de feature flags.
- Tests: +21 nuevos (12 skill promoter, 9 nightly reflection). Suite total
  **797 passed**.

## 🟢 Status — Fase A implementada (F78, 2026-05-20)

La primera fase del plan está cerrada en producción. Cambios respecto a
lo descrito originalmente en §2:

- Migración Alembic real: **`202605200001_jobs_extracted_recipe_at.py`** (head).
- Pydantic `DeepAgentMemoryProposal` extendido con `kind` (default `lesson`),
  `confidence` y `metadata` para que `approve_memory_proposal` materialice
  el `kind` declarado en vez del hardcoded `lesson` previo.
- `DeepAgentMemoryService.list_memory_proposals(kind=...)` ahora filtra
  vía `metadata_json["kind"]` (no columna nueva).
- El extractor reutiliza `propose_memory_update` (redact PII + HumanApproval
  row); no escribe directo en la tabla de proposals.
- LLM secundario inyectable (`llm_invoker` parameter) para que los tests
  puedan correr sin tocar `conftest.py` ni el guard hermético.
- Beat queue real = `maintenance` (no existe `memory` queue).
- Filtros aplicados: `status IN {completed, completed_with_warnings}`,
  `tool_call_count ≥ 5` (con fallback a "eventos con metadata.tool" si
  algún agente no emite tipos canónicos), `duration ≥ 30s`,
  `job_type ∈ allowlist` (allowlist configurable, excluye infra).
- Endpoints publicados: `GET /deepagents/memory/recipes` (público a
  authenticated) + `POST /deepagents/memory/recipes/extract-now` (admin).
- UI: `MemoryView.tsx` agregó sección "Recetas propuestas" con preview
  legible + JSON colapsable + `data-testid` para Playwright.
- Tests: **23 nuevos verdes** (12 extractor + 9 prompts + 2 service
  round-trip). Suite total **735 passed**.
- Live evidence: endpoint retornó proposal real con `kind="procedure"` y
  payload completo (recipe JSON + tool_call_count + duration); beat task
  visible en Celery. En el estado actual `/health/dashboard` expone 18
  componentes (incluye `operational_backlog` y `checkpointer`).

**Siguiente paso del plan:** Fase 79 (failure post-mortem → warnings
proactivos) — ver §3.

---

## 0. Contexto rápido del chat anterior (handoff)

### 0.1 Qué se acaba de hacer

| Fase | Resumen | Estado |
|---|---|---|
| **F76** (QA) | Playwright E2E full-stack audit: `docs/qa/MAP.md`, `docs/qa/RUNBOOK.md`, `docs/qa/FINAL_AUDIT_REPORT.md`, suite `frontend/tests/e2e/` con 16 tests. **16/16 verdes**. Bug QA-1 detectado y corregido (tsconfig excluye `tests/`). | ✅ Cerrada |
| **F77** (MCP gem + cc) | Cableados `gemini-mcp-tool` y `@steipete/claude-code-mcp` como MCP stdio servers. Total **5 MCP servers conectados**: `mem` (Supermemory, 4 tools), `gh` (GitHub, 42 tools), `fs` (filesystem `/home/jgonz`, 14 tools), `cc` (Claude Code, 1 tool), `gem` (Gemini CLI, 6 tools) → **67 tools inyectables al DeepAgent**. | ✅ Cerrada |
| **Verificación live** | `/system/mcp` 5/5 connected con 67 tools (`mem`, `gh`, `fs`, `cc`, `gem`), inventario paralelo y timeout default 30s. `/health/dashboard` 18 componentes. `gem_ask-gemini` invocado en vivo respondió `PONG` en 8.4s. | ✅ |

### 0.2 Estado funcional del stack

- **Backend FastAPI:** `:8000`, 147 endpoints, suite hermética vigente
  **950 passed**, 1 skipped, 28 deselected (944 históricos + 6 nuevos
  por el fix `eager_defaults` del re-audit 2026-05-23).
- **Frontend Next.js 16 SPA:** `:3001`, 20 vistas, **31/31 Playwright
  passed** sin exportar `COGOS_JWT` (auto-mint via `_global-setup.ts`).
- **Workers Celery:** 5 queues + 3 reapers (approval, stuck_action_requests, stale_running_jobs).
- **Stores:** Postgres 16+pgvector, Redis 7, Weaviate 1.29, Neo4j 5.
- **LLM chain:** primary+agent `gpt-5.5` (openai-compatible gateway), secondary/fallback `gemini-3.1-pro-low`, vision `glm-4.6v` (z.ai), Kimi-k2.6 vía CLI.
- **OPERATOR_PROFILE:** `dedicated_local` (single-PC operator). Auto-approve para acciones reversibles (`drive_ensure_folder`, `drive_upload`, `computer_organize`).
- **Telegram bot:** `@Socio_dimn_bot`, 37 slash commands + modo conversacional sin slash, thread persistente por `chat_id`.

### 0.3 Arquitectura de memoria actual (lo que YA existe)

El agente **no** tiene una sola memoria — tiene **5 stores especializados**:

| # | Store | Backend | Qué guarda | Tabla / Recurso |
|---|---|---|---|---|
| 1 | **DeepAgent structured memory** | Postgres | Preferencias, lessons, warnings, facts, style, tool_feedback, episodios. Scoped `global/user/case/thread/agent`. Sensitivity `public/internal/sensitive/secret`. | `deepagent_memory_records` + `deepagent_memory_proposals` (schemas en `memory_schemas.py`) |
| 2 | **Vectorial RAG** | Weaviate | Chunks de documentos + embeddings (`gemini-embedding-001`). Hybrid search BM25+vector α=0.5 + rerank local. | `WeaviateStore` (`memory/weaviate_store.py`) |
| 3 | **Grafo de entidades** | Neo4j | NER de documentos (personas, orgs, dates). | `Neo4jEntityWriter` + `Neo4jGraphReader` (`ingestion/neo4j.py`) |
| 4 | **Checkpointer LangGraph** | Postgres | Estado de cada thread: mensajes, tool calls, scratchpad. | `postgres_checkpointer()` (`agents/graph.py:1010`) |
| 5 | **Memoria externa MCP** | Supermemory cloud | Lo que el agente decida persistir vía `mem_addMemory`. | MCP server `mem` |

**Importante:** las 5 stores están **desacopladas**. No hay sincronización
automática entre ellas. Cada una se llena/lee desde un punto distinto del flujo.

### 0.4 Piezas existentes que el plan reutiliza (no inventar nada nuevo)

| Pieza | Path | Para qué la usa el plan |
|---|---|---|
| `DeepAgentMemoryConsolidator` | `deepagents/memory_consolidation.py:15` | Ya consolida lessons desde `JobEvent`s. Fase A/D la extienden. |
| `DeepAgentMemoryProposal` schema | `deepagents/memory_schemas.py:42` | Approval gate ya existe. Todas las fases producen proposals que pasan por acá. |
| `DeepAgentMemoryRecord` table | `db/models.py` | Constraints ya cubren `kind ∈ {preference, procedure, lesson, warning, fact, style, tool_feedback, episodic}` — usamos las 8. |
| Skills registry | `deepagents/skills_registry.py` + `deepagents/skills/` | Fase B promueve recetas aprobadas a skills cargables. |
| Code Director | `code_director/director.py` | Fase B (code-based) lo usa para compilar Python en sandbox con tests. |
| Audit trail | `job_events` + `audit_events` + `human_approvals` | Fuente de verdad para Fase A/D/C/E. |
| Celery beat | `workers/tasks.py` + beat schedule | Donde colgamos los nuevos extractors y reflectors. |
| `/health/dashboard` | 18 componentes incl. `mcp_client`, `operational_backlog` + `checkpointer` | Cada fase agrega su propio tile de salud. |

---

## 1. Visión general del plan

**Objetivo:** que el agente acumule capacidad útil con cada interacción
**sin** modificar su "alma" (system prompt principal en `AGENT_SELF.md`) y
**sin** introducir cambios no aprobados por el operador.

**Principio rector:** todo aprendizaje pasa por **proposals** → **operator
approval** → **records activos**.

**Excepción única y acotada (Fase D):** el escáner de post-mortems
auto-promueve un *warning* (no un skill, no el system prompt, no código
ejecutable) cuando el mismo patrón `(agent_role, tool_name)` se observa
`FAILURE_POSTMORTEM_AUTOPROMOTE_THRESHOLD` veces (default 3) sin rechazos
previos del operador — el silencio del operador cuenta como aprobación
tácita para *advertencias* recurrentes. Es la única ruta de auto-deploy del
plan y está acotada a memoria `kind=warning`, que sólo agrega texto de
contexto al prompt; nunca habilita una acción nueva. Tiene **kill switch**:
`FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED=false` fuerza *toda* advertencia
aprendida por la puerta de aprobación, restaurando un literal "cero
auto-deploy". Ver §3.4. Todo lo demás (Fases A/B/C/E, skills, prompt,
código) es **siempre** proposal → approval, sin excepción.

### 1.1 Diagrama de acoplamiento

```
         ┌─────────────────────────────────────────────────────┐
         │                JobEvent (ya existe)                  │
         │   tool_invoked / tool_completed / tool_failed /      │
         │   job_completed / job_failed                         │
         └───────────────┬─────────────────┬────────────────────┘
                         │                 │
         ┌───────────────┴──┐    ┌─────────┴───────────┐    ┌─────────────────────┐
         │  Fase A          │    │  Fase D             │    │  Fase C             │
         │  recipe_extractor│    │  failure_postmortem │    │  tool_scorecard     │
         │  (jobs ≥5 tools) │    │  (fail→fix matcher) │    │  (daily aggregator) │
         └───────────────┬──┘    └─────────┬───────────┘    └──────────┬──────────┘
                         │                 │                           │
                         ▼                 ▼                           ▼
              ┌─────────────────────────────────────────┐   ┌──────────────────────┐
              │ deepagent_memory_proposals              │   │ tool_invocation_     │
              │   (kind=procedure | warning)            │   │   metrics (nueva)    │
              └────────────────┬────────────────────────┘   └──────────┬───────────┘
                               │                                       │
                               │ approval                              │ inyectada en
                               ▼                                       │ system prompt
              ┌─────────────────────────────────────────┐               │
              │ deepagent_memory_records (active)       │ ◄─────────────┘
              │   - procedural memories                 │
              │   - warnings con embeddings (Weaviate)  │
              └────────────────┬────────────────────────┘
                               │
                               │ usado ≥3 veces con éxito
                               ▼
                       ┌─────────────────┐
                       │  Fase B         │
                       │  skill_promoter │
                       │  (procedure→skill)│
                       └────────┬────────┘
                                │
                  ┌─────────────┴──────────────┐
                  ▼                            ▼
         ┌──────────────┐         ┌─────────────────────┐
         │ Prompt-based │         │ Code-based          │
         │   skill      │         │   skill (vía        │
         │ (template)   │         │   Code Director)    │
         └──────┬───────┘         └──────────┬──────────┘
                │                            │
                ▼                            ▼
           ┌─────────────────────────────────────┐
           │ skills_registry / skills/*.py       │
           │ → invocable como tool nativa        │
           └─────────────────────────────────────┘


         ┌─────────────────────────────┐
         │ LangGraph checkpoints       │
         │ (threads del día)           │
         └──────────────┬──────────────┘
                        │
                        ▼
                ┌───────────────────┐
                │ Fase E            │
                │ nightly_reflection│
                │ (03:00 cron)      │
                └─────────┬─────────┘
                          ▼
              deepagent_memory_proposals
                (kind=preference | lesson)
                          │
                          ▼
                approval gate (UI Memoria)
                          │
                          ▼
                deepagent_memory_records
                (inyectados al system prompt)
```

### 1.2 Orden de implementación (y por qué)

| # | Fase | Razón de orden |
|---|---|---|
| 1 | **A — Recetas** | Reusa consolidador existente. Cero tablas nuevas. Resultado visible en días de uso. |
| 2 | **D — Warnings de falla** | Mismo shape que A pero proactivo. Alto signal-to-noise. |
| 3 | **C — Scorecard** | Tabla nueva, pero pure read-side. No cambia comportamiento hasta que se inyecte. |
| 4 | **B — Promoción a skill** | Mayor impacto y riesgo. Espera a que A produzca muestras. Code-based pasa por Code Director. |
| 5 | **E — Reflection nocturna** | Más opinable. Mayor riesgo de fabricación. Lo último para evaluar primero los 4 anteriores. |

---

## 2. FASE A — Recipe extraction

### 2.1 Goal

Después de cada job exitoso con ≥5 tool calls, distilar la trayectoria
en una **receta reutilizable** y guardarla como
`DeepAgentMemoryProposal(kind="procedure")`. Operator la aprueba → pasa a
`DeepAgentMemoryRecord` y se inyecta como guía cuando un task similar
aparezca.

### 2.2 Trigger

Dos opciones — implementar la **#1** por simplicidad:

1. **Celery beat cada 30 min** que escanea `jobs` con `status=succeeded`
   y `extracted_recipe_at IS NULL` y `tool_call_count >= 5`. Idempotente.
2. *(alternativa)* Hook directo en `JobEvent.completed` listener.

**Filtro de relevancia:**
- `tool_call_count >= 5`
- `duration_seconds >= 30` (cortos suelen ser triviales)
- `status == "succeeded"` (los fallidos van a Fase D)
- `agent_name IN ("research", "document_analysis", "comm", "social")` (excluir
  agentes triviales tipo `route_request`)

### 2.3 Archivos a crear

```
backend/src/cognitive_os/deepagents/
├── recipe_extractor.py          # NUEVO — extractor + LLM call
└── recipe_prompts.py            # NUEVO — system + few-shots

backend/src/cognitive_os/workers/
└── tasks.py                     # MODIFICADO — agregar extract_recipe_task

backend/src/cognitive_os/db/
└── models.py                    # MODIFICADO — agregar Job.extracted_recipe_at columna

backend/src/cognitive_os/api/
└── app.py                       # MODIFICADO — endpoint GET/PATCH /memory/recipes

backend/alembic/versions/
└── XXXX_add_job_extracted_recipe_at.py   # NUEVA migración

frontend/app/views/
└── MemoryView.tsx               # MODIFICADO — sección "Recetas propuestas"

backend/tests/
├── test_recipe_extractor.py     # NUEVO
└── test_workers_tasks.py        # MODIFICADO (cobertura del nuevo Celery task)
```

### 2.4 Esquema del extractor (Python)

```python
# backend/src/cognitive_os/deepagents/recipe_extractor.py
"""Extract procedural recipes from successful long-running jobs.

Reads `job_events`, summarizes the trajectory via the secondary LLM, and
emits a DeepAgentMemoryProposal(kind="procedure", source="consolidated").
Idempotent: skips jobs already processed (Job.extracted_recipe_at IS NOT NULL).
"""

from __future__ import annotations
from uuid import UUID
from datetime import UTC, datetime
import logging

from cognitive_os.core.db import session_scope
from cognitive_os.db.models import Job, JobEvent, DeepAgentMemoryProposalRecord
from cognitive_os.deepagents.memory_schemas import (
    DeepAgentMemoryKind,
    DeepAgentMemoryProposal,
    DeepAgentMemorySource,
)
from cognitive_os.llm.factory import build_secondary_llm
from cognitive_os.deepagents.recipe_prompts import RECIPE_EXTRACT_SYSTEM, RECIPE_EXTRACT_FEWSHOTS

logger = logging.getLogger(__name__)

MIN_TOOL_CALLS = 5
MIN_DURATION_SECONDS = 30
ELIGIBLE_AGENTS = {"research", "document_analysis", "comm", "social", "legal"}

async def extract_recipe(job_id: UUID) -> DeepAgentMemoryProposal | None:
    """Return a procedure proposal for `job_id`, or None if not eligible/failed."""
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return None
        if job.extracted_recipe_at is not None:
            return None  # already processed
        if job.status != "succeeded":
            return None
        if job.agent_name not in ELIGIBLE_AGENTS:
            return None

        events = await _load_tool_events(session, job_id)
        if len(events) < MIN_TOOL_CALLS:
            return None

        duration = (job.completed_at - job.started_at).total_seconds()
        if duration < MIN_DURATION_SECONDS:
            return None

        recipe_payload = await _summarize_trajectory_with_llm(job, events)
        if recipe_payload is None:
            return None  # fail-open: LLM failure, retry on next beat cycle

        proposal = _build_proposal(job, recipe_payload, duration)

        # Persist proposal + mark job as processed atomically
        session.add(DeepAgentMemoryProposalRecord.from_pydantic(proposal))
        job.extracted_recipe_at = datetime.now(UTC)
        await session.commit()

        return proposal


async def _summarize_trajectory_with_llm(job, events) -> dict | None:
    llm = build_secondary_llm()  # gemini-3.1-pro-low
    messages = [
        {"role": "system", "content": RECIPE_EXTRACT_SYSTEM},
        *RECIPE_EXTRACT_FEWSHOTS,
        {"role": "user", "content": _serialize_trajectory(job, events)},
    ]
    try:
        resp = await llm.ainvoke(messages, response_format={"type": "json_object"})
        return _parse_and_validate(resp.content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("recipe_extract_llm_failed job_id=%s error=%s", job.id, type(exc).__name__)
        return None
```

### 2.5 Prompt del LLM (en `recipe_prompts.py`)

```python
RECIPE_EXTRACT_SYSTEM = """\
Eres un extractor procedimental. Recibes una trayectoria de tool calls
de un agente que completó una tarea exitosamente. Tu trabajo es producir
una receta reutilizable en JSON.

Reglas:
- Genera pasos abstractos, no copies inputs literales del usuario.
- Identifica precondiciones (ej. "Drive autenticado", "calendario configurado").
- Estima runtime y outputs típicos.
- Marca pasos opcionales explícitamente.
- Si la trayectoria es demasiado específica para generalizar, devuelve
  `{"skip": true, "reason": "..."}`.

Output (JSON estricto):
{
  "title": "Frase corta verbo+objeto",
  "summary": "1-2 frases.",
  "preconditions": ["..."],
  "inputs_typical": {"param1": "tipo", ...},
  "steps": [
    {"step": 1, "tool": "drive_search", "purpose": "...", "input_pattern": "..."},
    ...
  ],
  "outputs_typical": "Descripción del resultado.",
  "estimated_runtime_seconds": 90,
  "success_indicators": ["..."],
  "tags": ["drive","email"]
}
"""

RECIPE_EXTRACT_FEWSHOTS = [
    # 2-3 ejemplos curados a mano la primera vez
]
```

### 2.6 Schema DB delta

```python
# backend/src/cognitive_os/db/models.py
class Job(...):
    # ... existing fields ...
    extracted_recipe_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When Fase-A extractor processed this job. NULL = pending.",
    )
```

Migración Alembic:

```python
# backend/alembic/versions/XXXX_add_job_extracted_recipe_at.py
def upgrade():
    op.add_column("jobs", sa.Column("extracted_recipe_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_jobs_extracted_recipe_at", "jobs", ["extracted_recipe_at"])

def downgrade():
    op.drop_index("ix_jobs_extracted_recipe_at", "jobs")
    op.drop_column("jobs", "extracted_recipe_at")
```

### 2.7 Celery beat

```python
# backend/src/cognitive_os/workers/tasks.py
@celery_app.task(name="recipes.extract_pending", time_limit=300, soft_time_limit=270)
def extract_pending_recipes() -> dict:
    """Beat task: scan jobs needing recipe extraction (Fase A)."""
    import asyncio
    from cognitive_os.deepagents.recipe_extractor import extract_recipe

    async def _run():
        async with session_scope() as session:
            stmt = (
                select(Job.id)
                .where(
                    Job.status == "succeeded",
                    Job.extracted_recipe_at.is_(None),
                    Job.tool_call_count >= 5,
                    Job.completed_at > datetime.now(UTC) - timedelta(days=2),
                )
                .limit(20)  # safety cap per cycle
            )
            return [row[0] for row in (await session.execute(stmt)).all()]

    job_ids = asyncio.run(_run())
    proposals = 0
    for jid in job_ids:
        try:
            res = asyncio.run(extract_recipe(jid))
            if res is not None:
                proposals += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("recipe_task_failed job_id=%s error=%s", jid, exc)
    return {"scanned": len(job_ids), "proposed": proposals}
```

Beat schedule (`workers/celery_app.py` o donde viva el schedule):

```python
"extract-recipes": {
    "task": "recipes.extract_pending",
    "schedule": crontab(minute="*/30"),
    "options": {"queue": "memory"},
},
```

### 2.8 Endpoint REST

```python
# backend/src/cognitive_os/api/app.py

@app.get("/memory/recipes", response_model=RecipeProposalList)
async def list_recipe_proposals(
    status: Literal["pending","approved","rejected"] = "pending",
    user: AuthenticatedUser = _auth_dependency,
) -> RecipeProposalList:
    """Recipe proposals (Fase A). Subset of /memory/proposals filtered by kind=procedure."""
    ...

@app.post("/memory/recipes/{proposal_id}/approve")
async def approve_recipe(
    proposal_id: UUID,
    user: AuthenticatedUser = _auth_dependency,
) -> dict:
    """Approve → moves to deepagent_memory_records with kind=procedure."""
    ...

@app.post("/memory/recipes/{proposal_id}/reject")
async def reject_recipe(...): ...
```

### 2.9 UI

`frontend/app/views/MemoryView.tsx` ya muestra `proposals` activos. Agregar
sección plegable **"Recetas propuestas"** filtrando `kind === "procedure"`,
con preview JSON (title + steps) y botones Aprobar / Rechazar / Editar.

### 2.10 Tests

```python
# backend/tests/test_recipe_extractor.py

async def test_skips_jobs_under_threshold(...): ...
async def test_skips_failed_jobs(...): ...
async def test_skips_already_processed_jobs(...): ...
async def test_happy_path_creates_proposal(...):
    # mock LLM to return valid recipe JSON
    # assert proposal row exists with kind=procedure
async def test_llm_failure_does_not_mark_processed(...):
    # extractor should retry on next cycle
async def test_skip_signal_from_llm_marks_processed(...):
    # if LLM says {"skip": true}, mark processed but don't create proposal
async def test_concurrent_extractors_idempotent(...): ...
```

### 2.11 Acceptance criteria Fase A

| Criterio | Cómo verificar |
|---|---|
| Job con ≥5 tools, success → 1 proposal en ≤30 min | `SELECT count(*) FROM deepagent_memory_proposals WHERE kind='procedure' AND created_at > job.completed_at` |
| UI Memoria muestra proposal con preview legible | Render manual + Playwright spec opcional |
| Approve → `deepagent_memory_records` con `kind=procedure`, `source=consolidated` | Test integración E2E |
| LLM failure no marca job como procesado | Test unitario |
| Tasks que el LLM dice "skip" no generan proposal pero sí marcan procesado | Test unitario |
| `extract_pending_recipes` beat task aparece en `/system/celery` | Smoke manual |

---

## 3. FASE D — Failure post-mortem (warnings proactivos)

### 3.1 Goal

Detectar patrones `(síntoma de falla) → (acción que arregló)` en
`job_events` y guardarlos como `DeepAgentMemoryRecord(kind="warning")` con
embedding en Weaviate. En la próxima invocación similar, el agente
**recibe el warning como hint** antes de actuar.

### 3.2 Detector de patrón fail→fix

**Heurística:**

```
PARA cada job exitoso:
  events = ordenados por timestamp
  POR cada par consecutivo (e1, e2):
    si e1.type == "tool_failed" Y e2.type == "tool_succeeded":
      si tool_name match O similarity(args) > 0.7:
        candidate = {
          "symptom": {"tool": e1.tool, "args": e1.args, "error": e1.error},
          "fix": {"tool": e2.tool, "args": e2.args},
          "delta": diff(e1.args, e2.args),
        }
        candidates.append(candidate)
```

Esto detecta secuencias como:
- "Llamé `maps_directions(mode=transit)` y falló 422 → reintenté con
  `language=es` y funcionó" → warning: "agregar `language=es` cuando
  `region=AR`".

### 3.3 Archivos

```
backend/src/cognitive_os/deepagents/
└── failure_postmortem.py        # NUEVO

backend/src/cognitive_os/workers/tasks.py    # MODIFICADO — postmortem_pending task

backend/src/cognitive_os/memory/
└── warning_index.py             # NUEVO — wrapper sobre Weaviate para warnings

backend/src/cognitive_os/deepagents/
├── factory.py                   # MODIFICADO — inyectar warnings relevantes al prompt
└── policies.py                  # MODIFICADO — bias contra args que matchean warning
```

### 3.4 Política de promoción

| Disparo | Acción |
|---|---|
| 1ra detección de un patrón | Crear `DeepAgentMemoryProposal(kind="warning", confidence=0.4)` → approval requerido |
| `FAILURE_POSTMORTEM_AUTOPROMOTE_THRESHOLD`ª detección del **mismo patrón** `(agent_role, tool_name)` sin rechazos previos | Auto-promover a `DeepAgentMemoryRecord(kind="warning", source="consolidated")` sin approval (es un patrón ya validado por evidencia) |
| Si un warning produce ≥3 falsos positivos (el agente lo aplicó y igual falló) | Desactivar automáticamente (`status=archived`) |

> **Kill switch (AUDIT-2026-C).** El auto-promote de la fila 2 es la única
> ruta de auto-deploy de todo el plan de aprendizaje. Está acotado a memoria
> `kind=warning` (texto de contexto, nunca una acción nueva) y se desactiva
> con `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED=false`: con el flag en `false`
> *toda* advertencia aprendida queda como proposal a la espera de aprobación
> del operador, sin importar cuántas veces se repita el patrón. Default
> `true` (postura zero-friction del PC dedicado). El registro auto-promovido
> lleva `metadata_json.approved_by="auto_promotion"`, distinguible en la
> vista Memoria del frontend.

### 3.5 Inyección en el system prompt

`factory.py` antes de construir el prompt para un agente:

```python
relevant_warnings = await warning_index.search_relevant(
    agent_name=agent_role,
    upcoming_task_description=request.user_query,
    top_k=3,
)

if relevant_warnings:
    system_prompt += "\n\n## Warnings de invocaciones previas\n"
    for w in relevant_warnings:
        system_prompt += f"- {w.content} (confianza={w.confidence:.0%})\n"
```

### 3.6 Tests

```python
async def test_detects_fail_then_fix_pattern(): ...
async def test_no_pattern_if_tools_differ_too_much(): ...
async def test_third_detection_auto_promotes(): ...
async def test_warning_with_3_false_positives_is_archived(): ...
async def test_warning_injection_at_prompt_build_time(): ...
```

### 3.7 Acceptance criteria Fase D

- Patrón fail→fix detectado en histórico de tests → genera proposal
- 3 detecciones del mismo patrón → activo automático en `deepagent_memory_records`
- Warning relevante aparece en el system prompt construido
- 3 falsos positivos → warning archivado, no se inyecta más

---

## 4. FASE C — Tool effectiveness scorecard

### 4.1 Goal

Trackear métricas operacionales por `(agent_role, tool_name)` para sesgar
las decisiones futuras del agente hacia tools confiables.

### 4.2 Nueva tabla

```sql
CREATE TABLE tool_invocation_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_role TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    invoke_count INT NOT NULL DEFAULT 0,
    success_count INT NOT NULL DEFAULT 0,
    failure_count INT NOT NULL DEFAULT 0,
    downstream_use_count INT NOT NULL DEFAULT 0,
    user_approve_count INT NOT NULL DEFAULT 0,
    user_reject_count INT NOT NULL DEFAULT 0,
    avg_latency_ms NUMERIC(10,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(agent_role, tool_name, period_start)
);
CREATE INDEX ix_tool_metrics_role_tool ON tool_invocation_metrics(agent_role, tool_name);
CREATE INDEX ix_tool_metrics_period ON tool_invocation_metrics(period_start);
```

### 4.3 Aggregator (Celery beat diario)

```python
# backend/src/cognitive_os/workers/tasks.py

@celery_app.task(name="metrics.aggregate_tool_invocations")
def aggregate_tool_invocations() -> dict:
    """Daily aggregation of (agent_role, tool_name) metrics from JobEvent."""
    period_start = (datetime.now(UTC) - timedelta(days=1)).replace(hour=0, minute=0, second=0)
    period_end = period_start + timedelta(days=1)

    # SQL: GROUP BY (agent_role, tool_name) sobre job_events del período
    # Calcula counts + avg_latency_ms desde event.metadata
    # UPSERT en tool_invocation_metrics

    return {"period": period_start.isoformat(), "rows_upserted": ...}
```

Beat schedule: `crontab(hour=4, minute=15)` (diario 04:15 local).

### 4.4 Definiciones operacionales

- **`downstream_use_count`** = el output del tool fue referenciado por un
  tool/LLM call posterior en el mismo job (heurística: el output_ref
  aparece en los `input_args` de eventos subsiguientes).
- **`user_approve_count`** = el job final fue aprobado en `human_approvals`.
- **`user_reject_count`** = el job final fue rechazado o el usuario
  rolledback la acción.

### 4.5 Inyección al system prompt

```python
# backend/src/cognitive_os/deepagents/factory.py

scorecard = await metrics.summary_for_role(
    agent_role=role,
    days_back=30,
)

if scorecard:
    high_conf = [s for s in scorecard if s.reliability_score >= 0.85]
    low_conf = [s for s in scorecard if s.reliability_score <= 0.50 and s.invoke_count >= 5]

    if high_conf or low_conf:
        system_prompt += "\n\n## Confiabilidad de tools (últimos 30 días)\n"
        for s in high_conf:
            system_prompt += f"- ✅ `{s.tool_name}`: {s.success_rate:.0%} éxito ({s.invoke_count} llamadas) — usar con confianza\n"
        for s in low_conf:
            system_prompt += f"- ⚠️ `{s.tool_name}`: {s.success_rate:.0%} éxito — verificar inputs antes de invocar\n"
```

`reliability_score = 0.5*success_rate + 0.3*downstream_use_rate + 0.2*user_approve_rate`

### 4.6 UI

Nueva subsección en `HealthView.tsx` o un tab nuevo "Aprendizaje" con
tabla ordenable: `agent_role × tool_name × success_rate × invoke_count`.

### 4.7 Tests

```python
async def test_aggregator_groups_by_agent_and_tool(): ...
async def test_aggregator_upserts_idempotent(): ...
async def test_scorecard_injection_includes_high_confidence(): ...
async def test_scorecard_skips_tools_with_under_5_invocations(): ...
async def test_reliability_score_formula(): ...
```

### 4.8 Acceptance criteria Fase C

- Tabla `tool_invocation_metrics` poblada diariamente
- Endpoint `/metrics/tools?agent_role=research&days=30` devuelve scorecard
- System prompt incluye sección de confiabilidad cuando hay datos suficientes
- UI muestra tabla con métricas

---

## 5. FASE B — Promoción de receta → skill

### 5.1 Goal

Cuando un `DeepAgentMemoryRecord(kind=procedure)` se referencia exitosamente
≥3 veces en jobs nuevos (verificable vía `tool_invocation_metrics` o un
nuevo `procedure_invocation_log`), proponer **promoverlo a skill**.

### 5.2 Dos rutas de skill

#### B.1 Skill prompt-based (simple, sin código)

Skill = markdown template + parameter schema en YAML.

```yaml
# backend/src/cognitive_os/deepagents/skills/auto_<slug>.yaml
name: drive_organize_clients_q4
description: "Organizar Drive del Q4 por cliente"
parameters:
  - name: year
    type: int
    required: true
  - name: quarter
    type: int
    required: true
prompt_template: |
  Organizá los archivos en Drive correspondientes al Q{{quarter}} de {{year}}.
  Pasos validados:
  1. Buscar carpeta raíz "Clientes {{year}}"
  2. Para cada subcarpeta, leer archivos modificados en el trimestre
  3. Generar preview con drive_organize_files
  4. Pedir approval al usuario
  5. Ejecutar el organize
source_procedure_id: <uuid del DeepAgentMemoryRecord>
```

Registrar en `skills_registry.py` como skill cargable por nombre.

#### B.2 Skill code-based (poderoso, vía Code Director)

Skill = módulo Python con `def run(params) -> Result`.

Flujo:
1. Code Director recibe `procedure_id` + memorias asociadas
2. Genera módulo `skills/auto_<slug>/skill.py`
3. Genera tests `skills/auto_<slug>/test_skill.py`
4. Build en sandbox (ya existe — `OPENSHELL_SANDBOX`)
5. Suite debe pasar 100%
6. Approval explícito del operador
7. Registrar en `skills/__init__.py`
8. Inyectable como tool nativa de DeepAgent

### 5.3 Archivos

```
backend/src/cognitive_os/deepagents/
├── skill_promoter.py            # NUEVO — orquesta B.1 + B.2
├── skill_yaml_loader.py         # NUEVO — para B.1
└── skills/                      # YA existe — agregar auto_*.yaml + auto_*/

backend/src/cognitive_os/code_director/
└── director.py                  # MODIFICADO — agregar flujo "compile_skill_from_procedure"

backend/src/cognitive_os/api/app.py    # MODIFICADO — endpoints /memory/recipes/{id}/promote-to-skill

backend/tests/
├── test_skill_promoter.py       # NUEVO
└── test_yaml_skill_loader.py    # NUEVO
```

### 5.4 Tabla de uso de procedures (opcional, recomendado)

```sql
CREATE TABLE procedure_invocation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID NOT NULL REFERENCES deepagent_memory_records(memory_id),
    job_id UUID NOT NULL REFERENCES jobs(id),
    invoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    outcome TEXT NOT NULL CHECK (outcome IN ('success','failure','partial'))
);
```

Cada vez que el agente referencia un procedure (señal: la receta aparece
en el system prompt construido para un job), se logea la invocación y al
final del job se actualiza el `outcome`.

### 5.5 Criterio de promoción

```python
def should_propose_promotion(procedure_id: UUID) -> bool:
    success_count = count_invocations(procedure_id, outcome="success")
    failure_count = count_invocations(procedure_id, outcome="failure")
    if success_count < 3:
        return False
    if failure_count / max(success_count + failure_count, 1) > 0.3:
        return False  # too unreliable to promote
    return True
```

### 5.6 Rollback safety

Cada skill auto-promovido lleva metadatos:
- `auto_promoted_from: <procedure_id>`
- `promoted_at: <timestamp>`
- `parent_chat_id: <chat>`

Si en los **30 días posteriores a la promoción**, el `error_rate` del
skill sube >50% vs baseline → **archivar automáticamente** (`status=disabled`)
y notificar al operador. Reversible con un click.

### 5.7 Tests

```python
async def test_proposes_promotion_at_3_successes(): ...
async def test_skips_promotion_if_failure_rate_high(): ...
async def test_yaml_skill_registers_in_registry(): ...
async def test_code_skill_passes_through_code_director(): ...
async def test_code_skill_blocked_if_tests_fail(): ...
async def test_auto_rollback_on_post_promotion_failures(): ...
```

### 5.8 Acceptance criteria Fase B

- Procedure con ≥3 éxitos → proposal de promoción aparece en UI
- B.1: skill YAML registrado e invocable por nombre
- B.2: skill Python pasó por Code Director con tests verdes
- Rollback automático si post-promotion error_rate >50%

---

## 6. FASE E — Reflection nocturna

### 6.1 Goal

Cron diario a las 03:00 local que mira los threads del día y le pide al
LLM identificar **preferencias** o **lessons** implícitas. Cada proposal
debe citar evidencia (message IDs específicos).

### 6.2 Trigger

Beat task: `crontab(hour=3, minute=0)`.

### 6.3 Flujo

1. Cargar todos los threads (`langgraph_checkpoints`) del último día
2. Para cada thread, extraer:
   - Mensajes del usuario
   - Respuestas del agente
   - Aprovals/rechazos (`human_approvals`)
   - Tool calls
3. Pasar al LLM (gpt-5.5) con el prompt de reflection
4. LLM devuelve 0-3 proposals por thread con citación obligatoria de mensaje IDs
5. Insertar como `DeepAgentMemoryProposal(kind="preference"|"lesson", source="consolidated")`

### 6.4 Prompt LLM

```python
REFLECTION_SYSTEM = """\
Eres un reflexionador. Recibes una conversación entre un usuario y un agente.
Tu trabajo es identificar SOLO patrones que estén ESPECÍFICAMENTE EVIDENCIADOS
en los mensajes (no inferencias generales).

Para cada patrón, devuelve:
{
  "kind": "preference" | "lesson",
  "content": "Frase corta describing the pattern",
  "evidence_message_ids": ["msg_id_1", "msg_id_2"],
  "evidence_quotes": ["literal quote 1", "literal quote 2"],
  "confidence": 0.0-1.0,
  "sensitivity": "internal" | "public"
}

Si no hay evidencia clara, devuelve [].
NUNCA inventes preferencias. NUNCA generalices de un solo mensaje.
"""
```

### 6.5 Riesgo y mitigación

| Riesgo | Mitigación |
|---|---|
| LLM inventa preferencias | Requiere `evidence_quotes` literales (validar que aparezcan en los mensajes) |
| Sobre-aprendizaje (cambios bruscos por una conversación atípica) | Mínimo `confidence >= 0.7` y mínimo 2 menciones |
| Privacidad: contenido sensible se filtra a proposals | Honrar `sensitivity` field + filtros `SECRET_PATTERNS` de `memory_service.py` |
| Approval rate del operador muy bajo (>50% rechazo) | Auto-disable de Fase E + email al operador |

### 6.6 Tests

```python
async def test_reflection_skips_threads_without_clear_signal(): ...
async def test_reflection_requires_evidence_quotes_match_messages(): ...
async def test_reflection_respects_sensitivity_field(): ...
async def test_reflection_auto_disables_if_rejection_rate_high(): ...
```

### 6.7 Acceptance criteria Fase E

- Cron diario corre sin error
- Proposals generadas siempre incluyen `evidence_message_ids` válidos
- Validador rechaza proposals cuyas quotes no aparecen literalmente
- UI muestra evidencia al revisar cada proposal
- Auto-disable si rejection_rate >50% en 30 días

---

## 7. Anti-patterns explícitamente prohibidos

| ❌ NO hacer | Por qué |
|---|---|
| Auto-promover skills code-based sin approval | Riesgo de deploy de código buggy |
| Modificar `AGENT_SELF.md` automáticamente | Drift del "alma" del agente. Cambios al core son humanos. |
| Aprendizaje sin sensitivity filter | Memorias `secret` no deben salir al system prompt sin opt-in |
| Sincronización automática Postgres ↔ Supermemory | Supermemory es opt-in del operador. Sin auto-push. |
| Bypass del approval en `dedicated_local` profile | Approval para irreversibles **se mantiene** incluso en profile sin fricción |
| Self-improving del prompt principal con bandits | Drift impredecible. Cambios al system prompt son humanos. |
| Compartir skills aprendidos hacia marketplace externo | Fuera de scope local-first |

---

## 8. Checklist de implementación POR fase

### Para cada fase:

- [ ] **Migración Alembic** (si agrega tabla/columna)
- [ ] **Módulo nuevo** en `backend/src/cognitive_os/deepagents/` o `memory/`
- [ ] **Celery task** registrada + agregada al beat schedule
- [ ] **Endpoint REST** + schema en `api/app.py`
- [ ] **UI tile/section** en `frontend/app/views/`
- [ ] **Tests pytest** unitarios + integración (objetivo: 90% coverage del módulo nuevo)
- [ ] **Tests Playwright** smoke del UI nuevo
- [ ] **Doc update:** este archivo + `USER_GUIDE.md` + `AGENT_SELF.md` si la fase cambia capacidades
- [ ] **Verificación live:** suite + lint + restart + endpoint smoke + tile visible
- [ ] **Commit** con mensaje `feat(fase-XX): <descripción>`

### Verificación post-deploy:

- [ ] `npm run lint` 0 warnings
- [ ] `npm run build` OK
- [ ] `uv run pytest -q` todo verde
- [ ] `COGOS_JWT=$JWT npx playwright test` 31/31 (snapshot vigente)
- [ ] `curl /health/dashboard` muestra los nuevos tiles
- [ ] Smoke manual de la fase desde la UI

---

## 9. Métricas de éxito globales (los 5 fases juntas)

| Métrica | Objetivo (90 días post-deploy) |
|---|---|
| Recetas propuestas por semana (Fase A) | ≥3 con approval rate ≥60% |
| Warnings activos en producción (Fase D) | ≥5 con falsos positivos <20% |
| Tools con scorecard ≥30 días de data (Fase C) | ≥80% de las 21 native + MCP tools |
| Skills auto-promovidos (Fase B) | ≥2 prompt-based + ≥1 code-based, todos invocados ≥5 veces sin rollback |
| Preferences detectadas por Fase E | ≥10 aprobadas con evidence_quotes válidas |
| Tiempo promedio para resolver task repetida | -30% vs baseline (target stretch) |

---

## 10. Para el chat nuevo: por dónde empezar

Si estás abriendo este doc desde un chat nuevo:

1. **Lee este documento completo.**
2. **Lee también:** `docs/AGENT_SELF.md`, `docs/DEEPAGENTS_SKILLS_MEMORY.md`,
   `docs/qa/FINAL_AUDIT_REPORT.md` para contexto.
3. **Confirma estado del stack:**
   ```bash
   JWT=$(cd cognitive-os/backend && uv run python -c "from cognitive_os.core.auth import create_access_token; print(create_access_token(user_id='auditor', roles=['admin']))" | tail -1)
   curl -s -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/health/dashboard | python3 -m json.tool
   curl -s -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/system/mcp | python3 -m json.tool
   cd cognitive-os/backend && uv run pytest -q  # 944 esperado en el gate vigente
   cd cognitive-os/frontend && npm run lint && npm run build  # 0 warnings + OK
   ```
4. **Empezá por Fase A.** Es la base. Las otras 4 se construyen sobre su
   infrastructure (proposal flow + Celery beat pattern).
5. **No rompas las reglas de §7.** Especialmente: approval gate para
   skills code-based.
6. **Convención de Fases:** las anteriores van hasta F77. Las nuevas serían
   F78 (Fase A), F79 (Fase D), F80 (Fase C), F81 (Fase B), F82 (Fase E).
7. **Branch:** continúa en `main` salvo
   instrucción contraria.
8. **Operator profile:** `dedicated_local` — auto-approve para
   reversibles, approval explícito para irreversibles.
9. **Memoria persistente del operador:** `~/.claude/projects/-home-jgonz-Escritorio-PROYECTO-COGNITIVE-OS/memory/MEMORY.md` y subarchivos. **Respetar `feedback_supermemory_protected.md`** (no tocar el MCP de Supermemory).

---

**Fin del documento.** Cualquier divergencia entre este plan y la
implementación real debe documentarse acá o en un follow-up con fecha
explícita.

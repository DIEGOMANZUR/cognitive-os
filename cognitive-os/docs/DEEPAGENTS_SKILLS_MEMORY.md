# DeepAgents Skills y Memory (referencia técnica)

> **Estado (2026-05-20, Fase 74):** skills core en
> `backend/src/cognitive_os/deepagents/skills/core/` (**13 SKILL.md**: 8
> originales + **legal pack de 5** —`legal-hold`, `privilege-log-review`,
> `oss-license-review`, `worker-classification`, `matter-intake`—
> adaptadas del repo Apache 2.0
> [claude-for-legal](https://github.com/anthropics/claude-for-legal),
> con atribución en `skills/core/NOTICE.md`). User skills en
> `storage/deepagents/skills/user/`; memoria gobernada por
> `DeepAgentMemoryService` con propuestas → aprobación humana → activa.
> Tools de skills/memoria expuestas a DeepAgents:
> `list_available_skills`, `read_skill`, `get_relevant_memory`,
> `propose_memory_update`. La memoria persiste vía migración Alembic
> `202604300004_deepagents_skills_memory` y soporta `kind: episodic` desde
> `202605120005_deepagent_memory_episodic`. La consolidación corre como
> tareas Celery `cognitive_os.consolidate_deepagent_memory` (individual) y
> `cognitive_os.consolidate_all_deepagent_memory` (global).
>
> **Fase 71-72:** las propuestas de memoria propagan
> `user_id`/`case_id`/`thread_id` desde el workspace de la tarea, y
> `get_relevant_memory` los usa para filtrar el recall por scope — sin
> esto la memoria de distintos contextos se mezclaba. El mail personal no
> se convierte en memoria activa ni en tool de envío para DeepAgents — el
> carril `/mail/*` opera fuera del runtime DeepAgent.
>
> **Las 13 skills core:** `citation-discipline`, `rag-research`,
> `report-writer`, `evidence-matrix`, `contradiction-detector`,
> `timeline-builder`, `legal-draft-careful`, `sandbox-code-analysis`
> (las 8 originales) + el legal pack de 5 (`legal-hold`,
> `privilege-log-review`, `oss-license-review`, `worker-classification`,
> `matter-intake`).

## Skills vs Memory

Skills are read-only procedures stored as `SKILL.md` folders. They tell a DeepAgent how to perform
a bounded capability such as RAG research, evidence matrices, timelines, or careful drafting.

Memory is reviewed operational knowledge about preferences, procedures, warnings, lessons, style,
or tool feedback. Memory is not evidence and never replaces citations from documents.

With DeepAgents 0.6.x, approved startup memory is also written into each task
workspace as `./.cognitive_os/AGENTS.md` so native DeepAgents memory loading can
read it. Cognitive OS still injects a compact summary in the system prompt for
backward compatibility.

Para la ruta Chat **research**, el orquestador puede haber añadido un preludio OpenHarness
antes de invocar DeepAgents (`openharness_prelude` → mensaje de usuario). Eso no altera
esta guía: la memoria sigue sin ser evidencia. Ver [`OPENHARNESS_FUSION.md`](./OPENHARNESS_FUSION.md).

## Locations

- Core skills: `backend/src/cognitive_os/deepagents/skills/core`
- User skills: `storage/deepagents/skills/user`
- Memory exports: `storage/deepagents/memory`
- Persistent records: Postgres tables `deepagent_memory_records`,
  `deepagent_memory_proposals`, and `deepagent_skill_usage`

## Add A Core Skill

Create a folder with `SKILL.md`, include YAML frontmatter, and keep `risk_level: read_only` unless
the skill is explicitly approval-gated.

```markdown
---
name: evidence-matrix
description: Build a claim/evidence/citation matrix from local documents.
version: 1.0.0
risk_level: read_only
allowed_tools:
  - search_local_docs
  - read_document_pages
---
```

Core skills are versioned with the backend and must not be edited by agents.

### Legal pack (Fase 42, adapted from `claude-for-legal` — Apache 2.0)

| Skill | Risk level | Output |
|---|---|---|
| `legal-hold` | `approval_required` | Issue/refresh/release/report de litigation hold + draft `notice_text` (no envía). |
| `privilege-log-review` | `read_only` | Issues por fila (rúbrica de 4 chequeos): descripción flaca, recipient sin rol, ground débil, fecha fuera de rango. |
| `oss-license-review` | `read_only` | Reporte de cumplimiento OSS frente al modelo de distribución declarado; severidad info/warn/block. |
| `worker-classification` | `read_only` | Empleado vs contractor bajo el test correcto (ABC/economic-reality/IRS/UK), tabla de factores y deciding factors. |
| `matter-intake` | `approval_required` | Preview de `matter.md` normalizado + primera entrada de cronología; NO escribe hasta aprobar. |

Atribución Apache 2.0 en `backend/src/cognitive_os/deepagents/skills/core/NOTICE.md`. No se copió código upstream — solo se portaron las estructuras de output y las reglas duras, reescribiendo prompts a la convención Cognitive OS (`risk_level` + `allowed_tools`).

## Add A User Skill

Place user skills under `storage/deepagents/skills/user/<user_id>/<skill-name>/SKILL.md`.
The registry validates frontmatter and blocks dangerous tools such as shell, browser automation,
email, social posting, delete, or project-file edits.

## Approve Memory

Agents call `propose_memory_update`. The proposal is stored as pending and may create a
`HumanApproval`. The API exposes:

- `GET /deepagents/memory/proposals`
- `POST /deepagents/memory/proposals/{proposal_id}/approve`
- `POST /deepagents/memory/proposals/{proposal_id}/reject`

Los registros **episodicos** (`kind='episodic'`) pueden anexarse por API sin propuesta cuando
solo se necesita cronologia operativa: `POST /deepagents/memory/episodic` (JWT). Emiten auditoria
`deepagents.memory.episodic_append`. Preferencias duraderas siguen via `propose_memory_update`.

Approval creates active memory. Rejection does not create memory.

Consolidation deduplicates proposed lessons by normalized content before
creating a new proposal. This prevents the daily beat and manual consolidation
from producing the same pending lesson repeatedly.

## Export Or Archive Memory

- Export: `POST /deepagents/memory/export`
- Archive: service method `archive_memory(memory_id)`

Archives keep auditability without exposing memory to startup prompts.

## What Cannot Be Stored

- Secrets or secret-shaped strings.
- API keys, tokens, passwords, private keys, or `.env` content.
- Full sensitive case documents in global memory.
- Unredacted personal data when memory redaction is enabled.
- Legal or factual assertions as a replacement for citations.

## Debugging

- Check `AuditEvent` rows for `deepagents.memory.*`.
- Check proposal status before expecting memory in startup prompts.
- Verify core skills with `DeepAgentSkillsRegistry.discover_core_skills()`.
- If a DeepAgents version does not support `skills=` or `memory=`, Cognitive OS injects a
  compatibility summary into the system prompt and exposes `read_skill`.

## Risks

Memory can bias future answers. Cognitive OS therefore keeps critical memory read-only, requires
approval for proposals, redacts content, and preserves review/export/archive paths.

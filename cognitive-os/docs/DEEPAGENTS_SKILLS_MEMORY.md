# DeepAgents Skills y Memory (referencia técnica)

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-28, Prompt 7 V2.0 — re-ejecutado).** Esta rama `codex/commercial-zero-friction-hardening` queda certificada como **APTA COMERCIAL LOCAL-FIRST** para PC dedicado. Branch inicial Prompt 1 V2.0: HEAD `935193e`. El commit final del Prompt 7 V2.0 firma los deltas P3 (F-P2-101 restore + F-P2-103 + F-P2-104 parcial + F-P2-105) y P6 (V2-EVAL-200 path policy + V2-EVAL-202 docanalysis review). Evidencia viva en `tmp/v2_07_absolute_release_closure_20260528_133000/`.
>
> **Hallazgos cerrados V2.0 (10 verificados):** F-P2-101 working tree restored · F-P2-103 (P1) drive_get_file non-ASCII → 400 (15 tests) · F-P2-104 (P2 parcial) responses={} declarado, 89 endpoints en backlog R-001 · F-P2-105 (P3) `_inspect_workers_snapshot` con `connection_or_acquire` + connection=conn (verificado live **6/6 ciclos chaos consecutivos**) · F-P2-102 (P3) demostrado FALSO POSITIVO · V2-EVAL-200 (P1) `_is_sensitive_root` bloquea `~/.ssh`, `~/.gnupg`, `credentials/`, `tokens/` (16 tests) · V2-EVAL-201 (P3) log crudo Code Director ciclo completo · V2-EVAL-202 (P3) `apply_quality_evaluation` reconcilia top-level `human_review_required` con item severity=high / needs_human_review (4 tests). V2-EVAL-001/004/005 previos del cierre V2.0 anterior siguen sosteniéndose.
>
> **Gates V2.0 medidos antes del cierre absoluto:** `bash scripts/full-qa.sh` **1269 passed, 1 skipped, 28 deselected** (ruff/format/mypy/alembic/sync_doc_counts/git-diff verdes); `bash scripts/stress-qa.sh 5` **5/5 verde × 1269 passed × 2 ciclos posteriores al último cambio**, flakiness **0%**; `cd frontend && npx playwright test` **44 passed × 2 ciclos**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/openapi_readonly_smoke.py` **70 GET / 0 failures**; `bash scripts/verify_desktop_launchers.sh` OK; bandit severity-high 0 issues; `POST /health/verify` overall **`ok`** con `mcp_client` live `ok` 6/6 y **70 tools live**; checklist 400 puntos ejecutada (P7 V2.0). **37 tests de regresión nuevos acumulados** (15 F-P2-103 + 2 F-P2-105 + 16 V2-EVAL-200 + 4 V2-EVAL-202).
>
> **Criterio de verdad:** no se declara envío de correo, draft real ni escritura DNS. Mail queda normalizado como read-only (sync/list/classify/digest + proposed replies como texto). GoDaddy preview/dry-run. Action Plane mantiene `validate→preview→request→approve→dispatch→execute→audit` con idempotencia y reapers. Computer organize/inventory bloquean `root_path` con markers sensibles (`.ssh`, `.gnupg`, `credentials`, `secret`, `tokens`, `keychain`) además de la allow-list existente. El runtime corre en `127.0.0.1` sin exposición LAN/internet. **Cognitive OS queda certificado en este commit como APTO COMERCIAL LOCAL-FIRST para PC dedicado, con funcionamiento real activado, documentación sincronizada, dos ciclos completos verdes posteriores al último cambio, Git ordenado y sin P0/P1/P2 abiertos.**

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


> **Estado actual (2026-05-27, post cierre absoluto V2.0):** skills y memoria siguen activos
> como capa de aprendizaje operativo. Aunque el producto prioriza baja fricción en
> este PC dedicado, las promociones de memoria/skills se mantienen por proposal
> para preservar calidad y rollback: no son un mecanismo de seguridad perimetral,
> sino de control de comportamiento del agente. Mail personal no se convierte en
> tool de envío ni en memoria activa por defecto. Estado global vigente en
> `CURRENT_STATE.md`.
>
> **Histórico (2026-05-20, Fases 78-81 — plan de aprendizaje autónomo completo):**
> skills core en `backend/src/cognitive_os/deepagents/skills/core/`
> (**13 SKILL.md**: 8 originales + **legal pack de 5** —`legal-hold`,
> `privilege-log-review`, `oss-license-review`, `worker-classification`,
> `matter-intake`— adaptadas del repo Apache 2.0
> [claude-for-legal](https://github.com/anthropics/claude-for-legal),
> con atribución en `skills/core/NOTICE.md`). User skills en
> `storage/deepagents/skills/user/`; **skills auto-promovidos** (Fase B)
> en `storage/deepagents/skills/user/_auto/`. Memoria gobernada por
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

## Plan de aprendizaje autónomo (Fases A-E)

El agente acumula capacidad útil con cada interacción **sin** modificar
su "alma" (`AGENT_SELF.md`) y **sin** desplegar cambios no aprobados.
**Principio rector:** todo aprendizaje pasa por *proposals* →
*aprobación del operador* → *records activos*. La **única excepción
acotada** es el auto-promote de *warnings* de Fase D (texto de contexto,
nunca una acción ejecutable), con kill switch
`FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED`. Plan canónico completo:
[`AGENT_LEARNING_PLAN.md`](./AGENT_LEARNING_PLAN.md).

| Fase | Módulo | Qué produce | Disparo |
|---|---|---|---|
| **A** Recetas | `deepagents/recipe_extractor.py` | `DeepAgentMemoryProposal(kind=procedure)` desde jobs exitosos con ≥5 tool calls | beat `*/30 * * * *` |
| **D** Warnings | `deepagents/failure_postmortem.py` | `kind=warning` desde patrones `tool_failed → tool_succeeded`; auto-promueve tras `FAILURE_POSTMORTEM_AUTOPROMOTE_THRESHOLD` repeticiones (default 3) si `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED=true` | beat 03:35 UTC |
| **C** Scorecard | `deepagents/tool_scorecard.py` | `tool_invocation_metrics` (rollup diario) + sección de confiabilidad en el system prompt | beat 04:15 UTC |
| **B** Skill promotion | `deepagents/skill_promoter.py` | skill YAML en `skills/user/_auto/` desde un procedure usado ≥3× con <30% fallos | beat 04:45 UTC |
| **E** Reflexión nocturna | `deepagents/nightly_reflection.py` | `kind=preference\|lesson` con evidencia literal del transcript | beat 03:00 UTC |

**Tablas de soporte:**
- `tool_invocation_metrics` (migración `202605200002`) — rollup por
  `(agent_role, tool_name, period_start)` con `reliability_score`
  derivado `= 0.5·success_rate + 0.3·downstream_use_rate + 0.2·approve_rate`.
- `procedure_invocation_log` (migración `202605200003`) — una fila
  `pending` por cada procedure que pudo inyectarse en el prompt de un
  job; el worker la cierra con `success`/`failure` al terminar. El
  skill promoter la agrega para decidir cuándo proponer una promoción.

**Fase B — ciclo de vida de un skill auto-promovido:**
1. El worker DeepAgent llama `log_procedure_usage_for_job` al arrancar
   (registra los procedures activos relevantes a ese agente) y
   `mark_outcome_for_job` al terminar.
2. `evaluate_pending_promotions` (beat) emite una proposal cuando un
   procedure cruza ≥3 éxitos con `failure_rate < 30%`.
3. Al aprobar (`POST /deepagents/learning/skill-promotions/{id}/approve`,
   admin), `materialise_yaml_skill` escribe
   `skills/user/_auto/<slug>/SKILL.md` (`risk_level: approval_required`)
   y emite un `DeepAgentMemoryRecord` derivado para descubrimiento.
4. `disable_underperforming_auto_skills` (beat) archiva el skill y
   renombra su `SKILL.md` a `.md.disabled` si el `failure_rate`
   post-promoción supera 50% en la ventana de 30 días.
- **Nunca hay auto-promoción de comportamiento ejecutable**: skills y
  código siempre requieren approval explícito del operador (§7 del plan).
  La única ruta de auto-deploy del plan es Fase D, acotada a memoria
  `kind=warning` (texto de contexto, nunca una acción) y desactivable con
  `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED=false` — ver
  `AGENT_LEARNING_PLAN.md` §3.4.

**Fase E — validación de evidencia:** cada proposal de reflexión debe
citar `evidence_message_ids` que existan en el transcript y
`evidence_quotes` que aparezcan **literalmente** en él (mínimo 12
caracteres por quote). El scanner se auto-desactiva si el operador
rechaza más del 50% de sus proposals en 30 días.

Panel del operador: vista **Memoria** del frontend (secciones Recetas,
Warnings, Scorecard, Promociones a skill, Reflexiones nocturnas).
Endpoints REST bajo `/deepagents/learning/*` y `/deepagents/memory/*`.

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
- Auto-promoted skills (Fase B): `storage/deepagents/skills/user/_auto`
  (un `rm -rf` de esa carpeta revierte todas las promociones)
- Memory exports: `storage/deepagents/memory`
- Persistent records: Postgres tables `deepagent_memory_records`,
  `deepagent_memory_proposals`, `deepagent_skill_usage`,
  `tool_invocation_metrics` (Fase C) y `procedure_invocation_log` (Fase B)

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

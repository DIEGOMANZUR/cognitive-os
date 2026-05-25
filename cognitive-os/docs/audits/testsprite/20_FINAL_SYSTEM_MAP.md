# Final System Map — Cognitive OS

Fecha/hora: 2026-05-24, America/Santiago.

## 1. Resultado

PASS para mapa final. La regeneración desde código y runtime no detectó drift crítico frente al estado canónico. La diferencia entre `154` rutas runtime y `150` endpoints canónicos queda explicada: el runtime incluye rutas FastAPI auxiliares como OpenAPI/docs/redoc y fixtures, mientras `scripts/sync_doc_counts.py` cuenta decoradores REST en `backend/src/cognitive_os/api/*.py`.

## 2. Conteos regenerados

| Superficie | Conteo detectado | Fuente | Estado |
|---|---:|---|---|
| Rutas FastAPI cargadas en runtime | 154 | `uv run python` importando `cognitive_os.api.app:app` | PASS |
| Endpoints REST canónicos | 150 | `python3 scripts/sync_doc_counts.py --print` | PASS |
| Tareas Celery | 23 | `celery_app.tasks` / `workers/tasks.py` | PASS |
| Jobs beat | 10 | `celery_app.beat_schedule` | PASS |
| Migraciones Alembic | 20 | `backend/alembic/versions` | PASS |
| Head Alembic | `202605200003` | `sync_doc_counts.py --print` y `alembic current` | PASS |
| Modelos ORM | 21 | introspección `cognitive_os.db.models` | PASS |
| Vistas frontend | 20 | `frontend/app/views/*.tsx` | PASS |
| Rutas server-side frontend | 2 | `layout.tsx`, `page.tsx`; SPA en `/` | PASS |
| Comandos Telegram | 37 | decoradores `@command(...)` | PASS |
| Tests backend | 123 archivos `test_*.py` | `find backend/tests` | PASS |
| Specs Playwright | 19 archivos `.spec.ts` | `find frontend/tests/e2e` | PASS |

## 3. Namespaces API

Rutas cargadas por namespace:

| Namespace | Rutas |
|---|---:|
| `/actions` | 53 |
| `/deepagents` | 21 |
| `/assist` | 11 |
| `/mail` | 10 |
| `/document-analysis` | 7 |
| `/research` | 5 |
| `/system` | 4 |
| `/jobs` | 4 |
| `/langsmith` | 4 |
| `/approvals` | 3 |
| `/documents` | 3 |
| `/health` | 3 |
| `/test` | 3 |
| `/threads` | 3 |
| `/voice` | 3 |
| `/chat` | 2 |
| `/docs` | 2 |
| `/agents`, `/audit`, `/auth`, `/code-director`, `/config`, `/knowledge`, `/openapi.json`, `/redoc`, `/sandbox` | 1 cada uno salvo `code-director` con 4 y `sandbox` con 2 en el mapa completo |

La superficie crítica pedida por PRD está presente: health/readiness, jobs, approvals, Action Plane, mail, documents, document-analysis, research, DeepAgents/memory/skills, Code Director, MCP/system, audit, Telegram y frontend SPA.

## 4. Celery y beat

Tareas Celery detectadas:

- `cognitive_os.aggregate_tool_scorecard`
- `cognitive_os.build_personal_mail_digest`
- `cognitive_os.cleanup_old_jobs`
- `cognitive_os.consolidate_all_deepagent_memory`
- `cognitive_os.consolidate_deepagent_memory`
- `cognitive_os.debug_fast`
- `cognitive_os.deliver_personal_reminders`
- `cognitive_os.evaluate_skill_promotions`
- `cognitive_os.extract_pending_recipes`
- `cognitive_os.health_check`
- `cognitive_os.ingest_pdf`
- `cognitive_os.nightly_reflection`
- `cognitive_os.reap_stale_approvals`
- `cognitive_os.reap_stale_running_jobs`
- `cognitive_os.reap_stuck_action_requests`
- `cognitive_os.run_action_request`
- `cognitive_os.run_code_build`
- `cognitive_os.run_deepagent_task`
- `cognitive_os.run_document_analysis`
- `cognitive_os.run_openshell_task`
- `cognitive_os.scan_failure_postmortems`
- `cognitive_os.sync_personal_mail`
- `cognitive_os.telegram_gmail_digest`

Beat schedule detectado:

- `action-request-reaper`
- `approval-reaper`
- `consolidate-deepagent-memory-all`
- `failure-postmortem-scanner`
- `nightly-reflection`
- `personal-mail-digest`
- `recipe-extractor`
- `skill-promoter`
- `stale-jobs-reaper`
- `tool-scorecard-aggregator`

## 5. Modelo de datos y estados críticos

Modelos ORM detectados: `ActionRequest`, `AuditEvent`, `ConversationThread`, `DeepAgentMemoryProposalRecord`, `DeepAgentMemoryRecord`, `DeepAgentSkillUsageRecord`, `Document`, `DocumentChunk`, `DocumentPage`, `HumanApproval`, `Job`, `JobEvent`, `MailAccount`, `MailMessage`, `MailSendLog`, `PersonalNote`, `PersonalTask`, `ProcedureInvocationLog`, `ResearchRunRecord`, `ToolInvocationMetric`, `User`.

Estados protegidos por constraints o contratos de schemas:

- `HumanApproval`: `pending`, `approved`, `rejected`, `edited`, `expired`.
- `ActionRequest`: `previewed`, `pending_approval`, `approved`, `queued`, `running`, `completed`, `failed`, `cancelled`, `rejected`, `expired`.
- `ResearchRunRecord`: estados controlados por constraint.
- `MailMessage`: `new`, `reply_proposed`, `pending_send`, `sent`, `ignored`, `failed`.
- `MailSendLog`: `pending`, `sent`, `failed`.
- `DeepAgentMemoryRecord`: `active`, `pending_approval`, `rejected`, `archived`.
- `DeepAgentMemoryProposalRecord`: `pending`, `approved`, `rejected`, `applied`.
- `PersonalTask`: `pending`, `in_progress`, `done`, `cancelled`.
- Document Analysis: `ok`, `partial`, `failed`, `blocked`, `needs_human_review`.
- Code Director: schemas públicos definen adapters, subtasks, build status y eventos.

## 6. Frontend

Vistas reales:

- `AgentsView`
- `ApprovalsView`
- `AssistView`
- `AuditView`
- `ChatView`
- `CodeDirectorView`
- `ConfigurationView`
- `DashboardView`
- `DocumentAnalysisView`
- `DocumentsView`
- `GoogleOpsView`
- `HealthView`
- `JobsView`
- `LangSmithView`
- `MailInboxView`
- `MemoryView`
- `ResearchView`
- `SandboxView`
- `SettingsView`
- `SkillsView`

Tabs E2E canónicas:

`Dashboard`, `Chat`, `DeepAgents`, `Skills`, `Memoria`, `Asistente`, `Mail`, `Documentos`, `Document Analysis`, `Jobs`, `Aprobaciones`, `Google Ops`, `Research`, `Code Director`, `Sandbox`, `LangSmith`, `Audit log`, `Health`, `Sistema`, `Conexión`.

La disciplina SPA sigue vigente: sólo `/` es la superficie de navegación principal. Las vistas internas se cambian por sidebar, hotkeys y command palette.

## 7. Telegram

Comandos registrados por decorador: `start`, `help`, `health`, `stats`, `config`, `agents`, `skills`, `memory`, `consolidate`, `jobs`, `job`, `cancel`, `approvals`, `approve`, `reject`, `threads`, `chat`, `reset`, `ingest`, `tasks`, `task`, `done`, `notes`, `note`, `gmaildigest`, `runs`, `maps`, `calendar`, `freebusy`, `drive`, `documents`, `audit`, `mail`, `research`, `codebuild`, `sandbox`, `capabilities`.

El contrato operativo exige que Telegram comparta service layer y guards con HTTP, sin saltarse mail read-only ni writes externos por defecto.

## 8. MCP, DeepAgents y Code Director

Runtime previo en `19_FINAL_RUNTIME_BOOT.md` verificó 5/5 servidores MCP conectados y 67 tools expuestas. El mapa de código contiene:

- Action providers: browser, computer, documents, drive, Gmail digest/read, GoDaddy DNS, Kimi WebBridge, mail, maps, captcha, calendar.
- DeepAgents: factory, service, tools, memory service, recipes, skill promoter, nightly reflection, research, document-analysis y OpenShell adapter.
- Code Director: adapters `codex`, `claude_code`, `deepagent`, `kimi`, `fake`, planner, director y service.

## 9. Cobertura y gaps

Cobertura presente:

- Backend: 123 archivos `test_*.py`, incluyendo Action Plane, idempotencia, mail, health, readiness, Telegram, Code Director, document analysis, research, reapers, MCP, secret hardening y live read-only opt-in.
- Frontend: 19 specs Playwright, incluyendo all-views console guard, auth, zero-friction, lifecycle jobs/approvals/action, mail read-only, responsive y regression-critical.
- TestSprite: planes y ejecuciones previas en `test-results/testsprite/zero-defects-*`; la auditoría final se re-ejecutará en la fase siguiente.

Gaps a revalidar en el loop final:

- TestSprite final sobre selección crítica y segura.
- Gates oficiales completos después del relanzamiento limpio.
- Flujos críticos E2E documentados con evidencia local.
- Degradación y recuperación documentadas sin provocar writes reales.

## 10. Conclusión

El mapa actual coincide con los conteos canónicos y conserva el contrato `dedicated_local/full`: cero fricción como perfil principal, controles funcionales mínimos preservados, mail read-only, health honesto, trazabilidad, reapers y Action Plane idempotente como superficies obligatorias para el cierre.

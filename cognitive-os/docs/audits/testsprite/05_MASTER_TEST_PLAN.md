# 05 · Master Test Plan — Cognitive OS (TestSprite Audit 2026-05-23)

> **Foco:** validar `dedicated_local/full` sin sacrificar trazabilidad. Mail
> queda como excepción dura. Conservar las 14/14 capacidades del perfil
> activas sin fricciones añadidas.

## A. Frontend / GUI

| ID | Superficie | Contrato | Herramienta | Severidad |
|---|---|---|---|---|
| FE-01 | 20 tabs SPA montan | `app/page.tsx` carga `*View.tsx` sin console.error ni 5xx | Playwright `all-views-console-guard` + TestSprite TC001/002/005 | P1 |
| FE-02 | Persistencia tab + JWT | `localStorage["cogos.tab"]`, `cogos.token` sobreviven refresh | Playwright `navigation` + TestSprite TC023/025 | P2 |
| FE-03 | Health dashboard 18 componentes | `configured` warning (no danger); botón "Verificar en vivo" llama `/health/verify` | Playwright `health-verified-vs-configured` + TestSprite TC003/008 | P1 |
| FE-04 | Command palette Ctrl+K | Abre desde cualquier foco (capture phase) | Playwright `glass-cockpit` + TestSprite TC014 | P2 |
| FE-05 | Centro notificaciones | Abre/cierra ESC, `asArray` defensa | Playwright `glass-cockpit` | P2 |
| FE-06 | Skip-link a11y | Aparece al foco | Playwright `glass-cockpit` | P3 |
| FE-07 | Settings tile MCP | `/system/mcp` 5 servers visibles | Playwright `regression-critical` + TestSprite TC007 | P2 |
| FE-08 | Settings tile readiness | `/system/readiness` gaps en UI | Playwright + TestSprite TC004 | P2 |
| FE-09 | Settings tile capabilities | `/actions/capabilities` listadas | Playwright | P3 |
| FE-10 | Mobile drawer | `responsive.spec` viewport 375x667 | Playwright `mobile-pwa` + `responsive` | P2 |
| FE-11 | Sin hydration mismatch | Render server + client coinciden | Playwright `smoke` | P1 |
| FE-12 | Loading/empty/error states | StatePrimitives en cada View | Playwright `error-empty-loading-states` + TestSprite TC020/022/026/027/028 | P2 |
| FE-13 | Forms persistencia | Settings guarda API base + JWT vacío rechazado sin crash | Playwright `forms` + TestSprite TC009/012 | P2 |
| FE-14 | Theme dark-only | `<html data-theme="dark">` fijo | Inspección manual | P3 |

## B. Backend / API

| ID | Endpoint | Contrato | Herramienta | Severidad |
|---|---|---|---|---|
| BE-01 | `GET /health` | 200 `{status:ok}` público | Playwright `regression-critical` + smoke | P0 |
| BE-02 | `POST /auth/local-token` | Solo dedicated_local/full; otros 403 | pytest `test_auth.py` | P0 |
| BE-03 | `GET /system/info` | JWT required; commit/profile/alembic_head | pytest + smoke | P1 |
| BE-04 | `GET /system/mcp` | enabled, server list, tools_count, parallel timeout 30s | pytest `test_mcp_client.py` + Playwright | P1 |
| BE-05 | `GET /system/readiness` | gaps[] + summary | pytest | P2 |
| BE-06 | `GET /health/dashboard` | 18 componentes con status discreto | pytest `test_health.py` + Playwright | P1 |
| BE-07 | `POST /health/verify` | probe LLM/embed/IMAP real | pytest `test_health_verify.py` | P1 |
| BE-08 | `/jobs/*`, `/approvals/*` | CRUD + dispatch + lifecycle | pytest `test_jobs.py` + Playwright `jobs-approvals-action-lifecycle` | P1 |
| BE-09 | `/actions/requests/*` | preview/request/approve/dispatch/idempotency | pytest `test_action_request_*.py` | P0 |
| BE-10 | `/mail/*` | read-only digest/sync; send con 3 flags | pytest `test_mail.py` + Playwright `mail-readonly-contract` | P0 |
| BE-11 | `/chat`, `/threads/*` | persistencia LangGraph | pytest `test_threads.py` | P1 |
| BE-12 | `/documents/*`, `/document-analysis/*` | ingestion + analysis | pytest | P2 |
| BE-13 | `/research/*` | plan/execute/synthesize | pytest | P2 |
| BE-14 | `/code-director/*` | runs + SSE | pytest | P2 |
| BE-15 | `/deepagents/*` | recipes/warnings/scorecard/skill/reflection | pytest | P2 |

## C. Async / Pipelines

| ID | Pipeline | Contrato | Severidad |
|---|---|---|---|
| AS-01 | Worker 5 colas | Procesa default, ingestion, agent_longrun, maintenance, mail | P0 |
| AS-02 | Beat 13 jobs | 3 reapers always-on + 10 condicionales por flag | P1 |
| AS-03 | Reapers | action_request_reaper / approval_reaper / stale_jobs_reaper marcan `operational_backlog=degraded` si fallan | P1 |
| AS-04 | Dispatch idempotente | `dispatch_state submitting/submitted/failed` | P0 |
| AS-05 | Retry/cancel | Cancel respeta SIGTERM→SIGKILL | P1 |
| AS-06 | Duplicate delivery | ActionRequest no duplica side-effects | P0 |

## D. Action Plane (Validate → Preview → Request → Approve → Dispatch → Execute → Audit)

| ID | Acción | Contrato | Severidad |
|---|---|---|---|
| AP-01 | browser_preview | dominios en allow-list | P1 |
| AP-02 | browser_interactive | navigate/click/fill/scroll/wait/screenshot/analyze (vision) | P2 |
| AP-03 | computer_organize | ruta en COMPUTER_ALLOWED_ROOTS, dry-run off only with flag | P1 |
| AP-04 | document_generate DOCX/XLSX/PPTX | guardrails (path/tamaño/formulas) | P2 |
| AP-05 | gmail_digest/preview | sin draft, sin send | P0 |
| AP-06 | mail personal read-only | IMAP/Gmail REST → digest + propose text | P0 |
| AP-07 | maps geocode/route | read-only | P2 |
| AP-08 | calendar freebusy/list | read-only; create→request | P2 |
| AP-09 | drive search | read-only; upload/folder/organize→request | P2 |
| AP-10 | godaddy dns | dry-run forzado por flag | P0 |
| AP-11 | kimi webbridge | mutaciones bloqueadas por approval | P1 |
| AP-12 | workflow export/import | persistencia | P2 |
| AP-13 | action_requests cancel | cancela limpio | P2 |

## E. Mail (excepción dura)

| ID | Validación | Severidad |
|---|---|---|
| ML-01 | `/mail/sync/dispatch` solo encola | P0 |
| ML-02 | `/mail/digest/preview` `sync_first=false` por default | P1 |
| ML-03 | `/mail/digest/dispatch` encola worker mail | P1 |
| ML-04 | Clasificación spam por agente, no carpeta | P2 |
| ML-05 | Últimos 50 correos máximo | P2 |
| ML-06 | Propuestas como texto, no draft | P0 |
| ML-07 | `/mail/messages/{id}/approve-send` requiere 3 flags + frase | P0 |
| ML-08 | UI sin botón "Enviar" en flujo normal | P0 |

## F. Telegram (37 commands)

| ID | Validación | Severidad |
|---|---|---|
| TG-01 | `_dispatch` fail-closed si allowlist no contiene user_id | P0 |
| TG-02 | `main()` se niega a arrancar con allowlist vacía | P0 |
| TG-03 | Matriz 37 commands × {auth-deny, no-crash, flag-gated} | P1 |
| TG-04 | Modo conversacional sin slash en `dedicated_local` | P2 |
| TG-05 | `/reset` reinicia thread | P3 |
| TG-06 | Sin secreto en respuesta | P1 |

## G. Documents / RAG

| ID | Validación | Severidad |
|---|---|---|
| DR-01 | Ingest PDF + dedup sha256 + chunks + pages | P1 |
| DR-02 | Citations literales con page markers | P1 |
| DR-03 | Indexación Weaviate + fallback BM25 | P2 |
| DR-04 | Neo4j optional graph | P3 |

## H. Document Analysis

| ID | Validación | Severidad |
|---|---|---|
| DA-01 | evidence_matrix + timeline + contradictions | P1 |
| DA-02 | quality_score + citations literales | P1 |
| DA-03 | exports DOCX/XLSX | P2 |
| DA-04 | SSE progress | P2 |

## I. Research / OpenHarness / DeepAgents

| ID | Validación | Severidad |
|---|---|---|
| RD-01 | Planning + parallel researchers + synthesis | P2 |
| RD-02 | Scorer + citations | P1 |
| RD-03 | SSE + cancellation | P2 |
| RD-04 | Fallbacks deterministicos si OpenHarness off | P2 |

## J. Memory / Skills / Learning A-E

| ID | Validación | Severidad |
|---|---|---|
| LR-01 | Recipe extractor (Fase A) | P2 |
| LR-02 | Failure post-mortem + auto-promote bajo kill switch | P0 |
| LR-03 | Tool scorecard (Fase C) | P2 |
| LR-04 | Skill promotion proposals (Fase B) | P2 |
| LR-05 | Nightly reflection (Fase E) | P2 |
| LR-06 | Quotes literales en evidencia | P1 |
| LR-07 | UI Memory + approve/reject | P2 |

## K. Code Director

| ID | Validación | Severidad |
|---|---|---|
| CD-01 | Planner LLM + heuristic fallback | P2 |
| CD-02 | Adapters Claude Code/Codex/Kimi/DeepAgents | P2 |
| CD-03 | Budget soft sin pedir aprobación por subproceso | P1 |
| CD-04 | Subprocess timeout + SIGTERM/SIGKILL | P1 |
| CD-05 | Prompt no aparece en `ps` | P2 |
| CD-06 | Artifact manifest | P3 |

## L. MCP

| ID | Validación | Severidad |
|---|---|---|
| MC-01 | `/system/mcp` 5 servers conectados | P1 |
| MC-02 | tools_count > 0 por server | P1 |
| MC-03 | Inventory paralelo timeout 30s | P2 |
| MC-04 | Server disconnected → degraded, no crash | P1 |

## M. Scripts / Runbook

| ID | Validación | Severidad |
|---|---|---|
| SC-01 | `dev_up.sh` valida vars sin default antes de docker compose | P1 |
| SC-02 | `dev_down.sh` apaga limpio | P2 |
| SC-03 | `init_env.sh` idempotente | P2 |
| SC-04 | `full-qa.sh` aislado en `.next-qa` | P1 |
| SC-05 | `verify_desktop_launchers.sh` lock + preflight + anti-PID-recycle | P1 |
| SC-06 | `sync_doc_counts.py --check` correcto | P3 |

## N. DB / Migraciones

| ID | Validación | Severidad |
|---|---|---|
| DB-01 | `alembic upgrade head` sin drift | P0 |
| DB-02 | CHECK constraints cubren todos los action_types | P0 |
| DB-03 | Idempotency UNIQUE index parcial | P0 |
| DB-04 | Test DB `cognitive_os_test` aislada | P1 |

## O. Cero fricción específica

| ID | Validación | Severidad |
|---|---|---|
| ZF-01 | `/auth/local-token` funciona en dedicated_local/full | P0 |
| ZF-02 | `/system/readiness` 14/14 capabilities unlocked | P1 |
| ZF-03 | UI sin aprobaciones redundantes | P1 |
| ZF-04 | Telegram sin slash en dedicated_local | P2 |
| ZF-05 | Command palette desde inputs | P2 |
| ZF-06 | Code Director sin aprobación por subproceso | P2 |
| ZF-07 | Kimi WebBridge accesible | P1 |
| ZF-08 | Filesystem amplio en COMPUTER_ALLOWED_ROOTS | P2 |
| ZF-09 | Sin OPERATOR_PROFILE=strict por accidente | P0 |
| ZF-10 | Errores indican cómo resolver | P2 |

## Distribución de evidencia

- `full-qa.sh` cubre A/B parcial, AS, DB, SC, baseline general.
- Playwright (31) cubre A casi entero + C parcial + E + L + ZF.
- TestSprite (28 TC) cubre A/E/F/O reforzados con LLM-driven asserts más
  débiles que Playwright; se usa como segunda capa.
- pytest live (8) cubre proveedores reales read-only — opt-in.
- Inspección de código + smoke endpoints cubren D/G/H/I/J/K/M.

## Pruebas que se ampliarán en Fase 8 si hay huecos

- Smoke E2E concurrent dispatch (cubierto por backend; falta E2E desde UI).
- TestSprite matriz API backend extendida (parte de TC).

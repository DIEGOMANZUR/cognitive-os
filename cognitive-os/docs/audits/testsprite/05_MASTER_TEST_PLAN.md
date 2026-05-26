# 05 — Master Test Plan (TestSprite + complementario)

Fecha: **2026-05-25** | Commit: `6891d5c`

Matriz maestra — cada fila referencia herramienta primaria. IDs prefijo `MP-`.

## A. Frontend/GUI (MP-FE-*)

| ID | Superficie | Contrato | Herramienta | Severidad falla |
|---|---|---|---|---|
| MP-FE-001 | 20 vistas sidebar | Montan sin crash/hydration | Playwright navigation.spec | P1 |
| MP-FE-002 | Command palette Ctrl+K | Navega sin error | Playwright navigation-hotkeys | P2 |
| MP-FE-003 | Health dashboard | configured≠ok badges | Playwright health-configured | P1 |
| MP-FE-004 | Mail inbox | Sin botón enviar/draft | audit-commercial-mail spec | P0 |
| MP-FE-005 | Zero friction tile | dedicated_local/full visible | zero-friction-dedicated-local | P2 |
| MP-FE-006 | Mobile responsive | Hamburger OK | responsive.spec | P2 |
| MP-FE-007 | Settings MCP tile | Siempre renderiza | regression-critical | P2 |

## B. Backend/API (MP-API-*)

| ID | Superficie | Contrato | Herramienta | Sev |
|---|---|---|---|---|
| MP-API-001 | Auth local-token | 200 en dedicated_local | pytest test_api | P1 |
| MP-API-002 | Health dashboard | 18 componentes | test_health_dashboard | P1 |
| MP-API-003 | POST /health/verify | Probe real LLM/embed/mail | live opt-in | P2 |
| MP-API-004 | Action requests eager_defaults | No MissingGreenlet | test_action_request_eager_defaults | P0 |
| MP-API-005 | Auth matrix 35×9×3 | RBAC correcto | test_audit_commercial_auth_matrix | P1 |
| MP-API-006 | Mail SMTP gate | 10 filas matriz | test_audit_commercial_mail_smtp_gating | P0 |

## C. Async/pipelines (MP-ASYNC-*)

| ID | Superficie | Contrato | Herramienta |
|---|---|---|---|
| MP-ASYNC-001 | Reapers stuck AR | Idempotente | test_audit_commercial_reapers_dedicated |
| MP-ASYNC-002 | operational_backlog | Truth table reactivo | test_audit_commercial_operational_backlog |
| MP-ASYNC-003 | Celery routes | 23 tasks 5 queues | test_celery_config |

## D. Action Plane (MP-AP-*)

| ID | Flujo | Perfil | Herramienta |
|---|---|---|---|
| MP-AP-001 | browser_preview full cycle | dedicated_local/full auto | runtime curl + test_final_functional_hardening |
| MP-AP-002 | calendar dry_run=false | 409 | test_audit_commercial_calendar_drive_direct_409 |
| MP-AP-003 | godaddy DNS gate | 16 filas | test_audit_commercial_godaddy_dns_gating |
| MP-AP-004 | dispatch missing AR | fail-closed message | test_dispatch_missing_action_request |

## E. Mail (MP-MAIL-*)

| ID | Contrato | Herramienta |
|---|---|---|
| MP-MAIL-001 | No send normal | test_mail_api + SMTP gate |
| MP-MAIL-002 | PII redaction digest | test_final_functional_hardening |
| MP-MAIL-003 | UI no send button | Playwright audit-commercial-mail |

## F. Telegram (MP-TG-*)

| ID | Contrato | Herramienta |
|---|---|---|
| MP-TG-001 | 37 commands auth matrix | test_telegram_bot |
| MP-TG-002 | Fail-closed empty allowlist | test_telegram_bot |

## G–O. (Resumen)

- **Documents/RAG:** test_integration_rag_weaviate (integration)
- **Document Analysis:** test_document_analysis_* + 6 modos runtime
- **Research/DeepAgents:** test_research_openharness_priority, test_deepagents_*
- **Memory/Learning:** test_failure_postmortem, test_skill_promoter, test_nightly_reflection
- **Code Director:** test_code_director_* + STDIN audit
- **MCP:** test_audit_commercial_mcp_failopen + `/system/mcp` live
- **Scripts:** full-qa.sh, stress-qa.sh, dev_up.sh, full-testsprite.sh
- **DB:** alembic check + test_audit_commercial_db_isolation_guard
- **Cero fricción:** MP-FE-005 + readiness 14/14 + auto-mint JWT

## TestSprite MCP (plan cloud)

Usar `scripts/full-testsprite.sh` con plan canónico `qa/testsprite/frontend_commercial_plan.json` en batches serializados. Evitar invocación MCP cruda sin config de túnel — ver `BLOCKERS.md` / hallazgo TS-ZF-20260525-002.

Historial verificado: **28/28** batches locales (2026-05-24), evidencia en `qa/reports/testsprite_latest_summary.md`.

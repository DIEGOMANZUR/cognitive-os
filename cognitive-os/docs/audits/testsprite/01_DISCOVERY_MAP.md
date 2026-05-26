# 01 — Discovery Map

Fecha: **2026-05-25** | Commit: `6891d5c` | Perfil: `dedicated_local/full`

## Resumen ejecutivo

| Métrica | Valor | Fuente |
|---|---|---|
| Endpoints REST | 150 | `backend/src/cognitive_os/api/` |
| Tareas Celery | 23 | `workers/tasks.py` |
| Colas Celery | 5 | `workers/celery_app.py` |
| Beat jobs | 3 fijos + hasta 10 condicionales | `workers/celery_app.py` |
| Migraciones Alembic | 20, head `202605200003` | `alembic/versions/` |
| Vistas frontend | 20 | `frontend/app/views/*.tsx` |
| Comandos Telegram | 37 | `integrations/telegram_bot.py` |
| Action types | 11 | `actions/schemas.py` |
| Tests backend pytest | 1200 passed (default selection) | `backend/tests/` |
| Specs Playwright | 43 tests / 20 archivos | `frontend/tests/e2e/` |

## Superficie backend (grupos)

| Grupo | Endpoints | Tests clave | Hueco / riesgo |
|---|---|---|---|
| Health/system | 8 | `test_health_dashboard.py`, `test_readiness.py` | Latencia dashboard ~2s (P3) |
| Chat/threads | 5 | `test_api.py` | SSE streaming no E2E dedicado |
| Documents/RAG | 3 | `test_integration_rag_weaviate.py` | integration deselected default |
| DeepAgents | 24 | `test_deepagents_*` | OpenHarness opt-in |
| Document analysis | 7 | `test_document_analysis_*` | Fallback heurístico = contrato |
| Action Plane | ~56 | `test_actions.py`, `test_audit_commercial_*` | Cubierto por matriz comercial |
| Mail | 10 | `test_mail_api.py`, `test_audit_commercial_mail_*` | Escape hatch matriz 10 filas |
| Code Director | 4 | `test_code_director_*` | STDIN-only verificado |
| Jobs/approvals | 8 | `test_jobs_api.py`, `test_approval_reaper.py` | 309 pending operador |
| Test fixtures | 3 | `test_test_fixtures_api.py` | Solo `APP_ENV=test` o flag |

## Celery

| Cola | Tareas principales |
|---|---|
| `default` | `debug_fast` |
| `ingestion` | `ingest_pdf` |
| `agent_longrun` | deepagent, action_request, doc_analysis, code_build, openshell |
| `maintenance` | reapers, learning loop, health, cleanup |
| `mail` | sync, digest |

## Frontend

| Vista | E2E | Cero fricción |
|---|---|---|
| DashboardView | navigation.spec | readiness tile |
| HealthView | health-configured-vs-verified | POST /health/verify abort 45s |
| MailInboxView | audit-commercial-mail-no-send-button | sin botón enviar |
| SettingsView | regression-critical | tile MCP siempre visible |
| (20 total) | 43 Playwright passed | auto-mint JWT |

## NO RESTRINGIR SIN MOTIVO

Capacidades que el contrato canónico exige amplias en `dedicated_local/full`:

- Filesystem local bajo `/home/jgonz` sin aprobación por archivo
- Edge real / Kimi WebBridge cuando flags + dominios lo habilitan
- Auto-resolución de approvals reversibles (browser_preview, computer_organize, document_generate, drive_*)
- `POST /auth/local-token` sin fricción manual de JWT
- Telegram conversacional sin slash
- UI como command center (20 tabs, Ctrl+K, notifications)
- Code Director operativo con budget soft
- MCP client + inventario paralelo 30s timeout

## Controles no negociables (mantener)

- Mail read-only normal; SMTP triple gate
- Idempotencia ActionRequest + índice UNIQUE parcial
- Reapers + `operational_backlog` en health
- Telegram fail-closed allowlist
- DB test isolation (`cognitive_os_test`)
- Build QA en `.next-qa`

## Relación con tests existentes

| Superficie | Cobertura | Gap residual |
|---|---|---|
| Mail SMTP gate | `test_audit_commercial_mail_smtp_gating.py` | — |
| GoDaddy DNS | `test_audit_commercial_godaddy_dns_gating.py` | — |
| Code Director STDIN | `test_audit_commercial_code_director_stdin_only.py` | — |
| Cero fricción UI | `zero-friction-dedicated-local.spec.ts` | — |
| Final hardening | `test_final_functional_hardening.py` (8 tests) | Docs actualizados 1200 |

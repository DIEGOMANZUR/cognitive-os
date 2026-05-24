# 06 Implementation Log

## Cambios aplicados

| Fecha | ID | Cambio | Archivos | Validacion |
|---|---|---|---|---|
| 2026-05-23 | R-001 | `full-qa-live.sh` deja de exportar `LIVE_TESTS_ENABLED=1`; ahora falla rapido con diagnostico si el operador no lo setea | `scripts/full-qa-live.sh`, `backend/tests/test_frontend_static_assets.py` | `bash scripts/full-qa-live.sh` sin env -> exit 2, sin pytest/live |
| 2026-05-23 | R-002 | `full-e2e.sh` deja de mintar JWT directo; el bootstrap queda en `_global-setup.ts` via `POST /auth/local-token` | `scripts/full-e2e.sh`, `backend/tests/test_frontend_static_assets.py`, `scripts/README.md` | Playwright log: auto-minted via `/auth/local-token`; 31 passed |
| 2026-05-23 | R-003 | `USER_GUIDE.md` queda alineado con cockpit dark-only, sin prometer toggle claro | `docs/USER_GUIDE.md`, `backend/tests/test_frontend_static_assets.py` | `test_user_guide_matches_dark_only_frontend_contract` passed |
| 2026-05-23 | R-004 | Guias secundarias actualizadas a 958 passed y 14 regresiones/guards nuevas reales | `docs/COGNITIVE_OS_GUIDE.md`, `docs/AGENT_LEARNING_PLAN.md`, `scripts/README.md`, `docs/qa/*`, `docs/CURRENT_STATE.md` | `full-qa.sh` -> 958 passed |
| 2026-05-23 | R-005 | Runner TestSprite en lotes, con `API_KEY` externo, health entre batches y redaccion del config temporal | `scripts/full-testsprite.sh`, `scripts/README.md`, `backend/tests/test_frontend_static_assets.py` | TestSprite batched -> 28 passed; `test_full_testsprite_batches_and_redacts_secret_config` |
| 2026-05-23 | R-006 | Plan TestSprite generado ajustado para estados locales vivos: approvals vacio, jobs poblado/vacio y mail digest disabled son validos si son visibles y diagnosticos | `testsprite_tests/testsprite_frontend_test_plan.json` (gitignored) | rerun TC006/018/021/022 -> 4 passed; batched completo -> 28 passed |
| 2026-05-23 | R-007 | QA comercial determinista: plan TestSprite versionado, paquete TestSprite pineado, fixtures test-only, Playwright critico propio, secret scan, profile QA, summary estable y probe de saturacion | `qa/testsprite/frontend_commercial_plan.json`, `qa/QA_STACK_PROFILE.md`, `scripts/full-commercial-qa.sh`, `scripts/scan-local-artifacts-for-secrets.sh`, `scripts/probe-qa-stack-health.py`, `scripts/summarize-testsprite-report.py`, `backend/src/cognitive_os/api/test_fixtures.py`, `frontend/tests/e2e/commercial-fixtures-critical.spec.ts` | `bash scripts/full-commercial-qa.sh` -> OK; `full-qa` 958 passed; Playwright 41 passed; secret scan limpio |
| 2026-05-23 | QA-DOCS | Se reemplaza la bitacora comercial anterior por matriz, inventario, gaps, failure log, plan y reporte de esta rama | `docs/qa/commercial_zero_friction_hardening/*` | `sync_doc_counts --check` y `git diff --check` verdes |
| 2026-05-23 | SECRETS | Se redacciono token temporal ignorado regenerado por TestSprite | `testsprite_tests/tmp/config.json` (gitignored) | `API_KEY` queda `<redacted>`; no versionado |

## Validaciones ejecutadas

| Comando | Resultado |
|---|---|
| `cd backend && uv run pytest tests/test_frontend_static_assets.py -q` | 10 passed |
| `cd backend && uv run ruff check .` | All checks passed |
| `cd backend && uv run ruff format --check .` | 284 files formatted; tras format, verde |
| `cd backend && uv run alembic upgrade head` | OK |
| `bash scripts/full-qa.sh` | OK: 958 passed, 1 skipped, 28 deselected; ruff/format/mypy/Alembic/frontend lint/build/sync/diff verdes |
| `bash scripts/stress-qa.sh` | OK: 3 pasadas de 958 passed, 1 skipped, 28 deselected |
| `COGOS_SKIP_PLAYWRIGHT_INSTALL=1 bash scripts/full-e2e.sh` | OK: 41 passed; global setup auto-minted JWT via `/auth/local-token` |
| `bash scripts/verify_desktop_launchers.sh` | OK |
| `bash scripts/full-qa-live.sh` sin env | OK como guard: exit 2 antes de tocar proveedores |
| `bash scripts/full-commercial-qa.sh` | OK: full-qa 958 passed, fixtures backend 4 passed, Playwright critico 10 passed, full-e2e 41 passed, stress moderado 958 passed, health probe healthy, secret scan limpio; TestSprite saltado por falta de env `TESTSPRITE_API_KEY` y summary regenerado desde resultados 28/28 existentes |
| `python3 scripts/probe-qa-stack-health.py --url http://127.0.0.1:8000/health` | OK: classification=healthy, 16/16 successes |
| `bash scripts/scan-local-artifacts-for-secrets.sh` | OK: sin secretos criticos en artefactos locales |
| `python3 scripts/sync_doc_counts.py --check` | OK |
| `git diff --check` | OK |
| TestSprite direct full corrected batched (`scripts/full-testsprite.sh` historical batch size 4; current default serial size 1) | Historical OK: 7 batches, 28 passed, backend health 200 before/after each batch; final closure attempt blocked by provider auth |

## TestSprite

Se ejecuto TestSprite con token alternativo validado por `/api/me`, sin
persistir ni documentar la credencial, contra frontend `:3001` y backend
`:8000`.

Resultados:

- Full directo inicial: 28 ejecutados, 24 passed, 3 blocked, 1 failed.
  Los 4 no verdes eran expectativas state-dependent del plan generado:
  aprobaciones inexistentes, mail digest deshabilitado y jobs no vacios.
- Rerun focalizado tras corregir el plan: TC006/TC018/TC021/TC022 -> 4 passed.
- Full directo all-at-once tras corregir plan: invalido por sobrecarga del
  runner paralelo; saturo el backend local (`/health` timeout, backlog lleno).
  Se corto, se reinicio con el launcher oficial y se cambio a estrategia batch.
- Full corregido en lotes de 4: **28 passed**, 0 failed, 0 blocked. Agregado:
  `testsprite_tests/tmp/batched_results.json` (gitignored).

Se agrega `scripts/full-testsprite.sh` como forma reproducible: requiere
`API_KEY` o `TESTSPRITE_API_KEY`, valida health entre lotes, corre el plan
completo en batches y redacciona el config temporal al salir.

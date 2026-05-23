# 06 Implementation Log

| Fecha | Cambio | Archivos | Validacion |
|---|---|---|---|
| 2026-05-22 | Auditoria canonica y plan QA creados | `docs/qa/commercial_zero_friction_hardening/*` | Lectura completa de docs requeridos |
| 2026-05-22 | `full-qa.sh` convierte Alembic en gate duro con DB configurada y limpia `.next-qa` antes de lint/build | `scripts/full-qa.sh`, `scripts/README.md`, `backend/tests/test_frontend_static_assets.py` | `full-qa.sh` verde |
| 2026-05-22 | Gate Playwright separado con JWT local, CORS preflight y `npm ci` opt-in | `scripts/full-e2e.sh`, `backend/tests/test_frontend_static_assets.py` | `full-e2e.sh` verde |
| 2026-05-22 | CORS local fallback para QA en `:3101` sin abrir origen wildcard | `backend/src/cognitive_os/core/config.py`, `.env.example`, `backend/tests/test_config.py` | `test_config.py`, `full-e2e` con API `:8001` |
| 2026-05-22 | Health `configured` visible como warning, no danger | `frontend/app/components/Sidebar.tsx`, `frontend/tests/e2e/regression-critical.spec.ts` | `health-verified-vs-configured`, `full-e2e` |
| 2026-05-22 | Guard defensivo de listas en notificaciones | `frontend/app/components/NotificationCenter.tsx` | `error-empty-loading-states`, `full-e2e` |
| 2026-05-22 | Mocks Playwright comerciales y specs de 20 vistas, health, jobs/approvals/action, mail read-only, mobile, zero-friction y error states | `frontend/tests/e2e/_commercial_mocks.ts`, specs comerciales nuevos | 9/9 specs focales; `full-e2e` 31/31 |
| 2026-05-22 | Forms E2E respeta `COGOS_API_BASE`; hotkey spec estabilizado quitando foco de inputs | `frontend/tests/e2e/forms.spec.ts`, `navigation-hotkeys-command-palette.spec.ts` | `full-e2e` 31/31 |
| 2026-05-22 | Docs vigentes actualizados a snapshot real `943 passed` y Playwright `31 passed` | `README.md`, `docs/*`, `scripts/README.md` | `sync_doc_counts --check`, `git diff --check` dentro de full-qa |
| 2026-05-22 | Live read-only ejecutado contra proveedores reales | `scripts/full-qa-live.sh`, `backend/tests/live/*` | `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` -> 8 passed |
| 2026-05-22 | TestSprite ejecutado con alcance acotado | MCP TestSprite, CLI local, `testsprite_tests/tmp/raw_report.md` | PRD/plan generados; `TC001`, `TC002`, `TC005` -> 3/3 passed como smoke advisory |

## Gates Verdes

- `uv run pytest tests/test_config.py tests/test_frontend_static_assets.py -q` -> 24 passed.
- `bash scripts/full-qa.sh` -> 943 passed, 1 skipped, 28 deselected; ruff, format, mypy, Alembic, frontend lint/build, sync counts y diff check OK.
- `COGOS_API_BASE=http://127.0.0.1:8001 COGOS_BASE_URL=http://localhost:3101 COGOS_SKIP_PLAYWRIGHT_INSTALL=1 bash scripts/full-e2e.sh` -> 31 passed.
- `bash scripts/stress-qa.sh` -> 3 runs, cada uno 943 passed, 1 skipped, 28 deselected.
- `bash scripts/verify_desktop_launchers.sh` -> OK.
- `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` -> 8 passed, 2 warnings MCP deprecations.
- TestSprite MCP/CLI -> 3/3 passed en smoke advisory acotado.

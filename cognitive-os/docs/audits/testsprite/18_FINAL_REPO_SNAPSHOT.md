# 18 - Final Repo Snapshot

Fecha local: 2026-05-24T20:29:28-04:00

## Git

| Campo | Valor |
|---|---|
| Branch | `codex/commercial-zero-friction-hardening` |
| HEAD | `5459ec5a7382afee67a26583a9a4990ee7673951` |
| Ultimos commits | `5459ec5`, `e582f0f`, `d25af91`, `bbaaea8`, `9ab77a4`, `a1d5b9c`, `647f103`, `9b22f77`, `5953b40`, `2c3cff6` |
| `git diff --check` | PASS |

## Estado de worktree

Cambios modificados:

- `docs/audits/testsprite/cognitive-os-openapi.json`
- `frontend/app/lib/api.ts`
- `frontend/app/lib/hooks.ts`
- `frontend/app/page.tsx`
- `frontend/app/views/HealthView.tsx`
- `frontend/app/views/SettingsView.tsx`
- `qa/reports/testsprite_latest_summary.md`

Archivos nuevos recientes:

- `docs/audits/testsprite/02_TESTSPRITE_RUNTIME_STATUS.md`
- `docs/audits/testsprite/03_TESTSPRITE_AUTH_SETUP.md`
- `docs/audits/testsprite/04_TESTSPRITE_MCP_STATUS.md`
- `docs/audits/testsprite/05_TESTSPRITE_UI_PLAN.md`
- `docs/audits/testsprite/06_TESTSPRITE_API_PLAN.md`
- `docs/audits/testsprite/07_TESTSPRITE_E2E_PLAN.md`
- `docs/audits/testsprite/08_TESTSPRITE_PLAN_REVIEW.md`
- `docs/audits/testsprite/09_TESTSPRITE_INITIAL_RESULTS.md`
- `docs/audits/testsprite/10_TESTSPRITE_TRIAGE.md`
- `docs/audits/testsprite/11_TESTSPRITE_REPAIR_PLAN.md`
- `docs/audits/testsprite/12_TESTSPRITE_FIX_LOG.md`
- `docs/audits/testsprite/13_TESTSPRITE_REGRESSION_CASES.md`
- `docs/audits/testsprite/14_TESTSPRITE_TARGETED_RERUN_RESULTS.md`
- `docs/audits/testsprite/15_TESTSPRITE_POST_REPAIR_CRITICAL_REPORT.md`
- `docs/audits/testsprite/16_TESTSPRITE_REPAIR_FINAL_REPORT.md`
- `docs/audits/testsprite/17_TESTSPRITE_ZERO_DEFECTS_CONTEXT.md`
- `docs/audits/testsprite/18_TESTSPRITE_ZERO_DEFECTS_RUNTIME_CHECK.md`
- `docs/audits/testsprite/19_TESTSPRITE_TOTAL_MATRIX.md`
- `docs/audits/testsprite/20_TESTSPRITE_ZERO_DEFECTS_FIX_LOOP.md`
- `docs/audits/testsprite/21_TESTSPRITE_FALSE_POSITIVES.md`
- `docs/audits/testsprite/22_TESTSPRITE_BLOCKERS.md`
- `docs/audits/testsprite/23_TESTSPRITE_FINAL_DOUBLE_RUN.md`
- `docs/audits/testsprite/24_TESTSPRITE_ZERO_DEFECTS_CERTIFICATION.md`
- `docs/audits/testsprite/17_FINAL_CONTEXT_RECONSTRUCTION.md`
- `docs/audits/testsprite/18_FINAL_REPO_SNAPSHOT.md`

Archivos eliminados: ninguno detectado.

`git diff --stat`: 7 archivos modificados, 144 inserciones, 48 borrados antes
de los reportes finales nuevos.

## Toolchain

| Tool | Version |
|---|---|
| Python | `python3 3.12.3` (`python` no existe en PATH) |
| uv | `0.11.6` |
| Node | `v22.22.0` |
| npm | `10.9.4` |
| Docker | `29.5.2` |
| Docker Compose | `v5.1.4` |
| OS | Ubuntu/Linux `6.17.0-22-generic` |
| Playwright | `1.60.0` |
| pytest | `9.0.3` |
| Alembic current | `202605200003 (head)` |

## Puertos esperados y activos al snapshot

| Puerto | Servicio | Estado |
|---:|---|---|
| 8000 | FastAPI | activo en `127.0.0.1` |
| 3001 | Next.js frontend | activo en `127.0.0.1` |
| 5432 | Postgres | activo en `127.0.0.1` |
| 6379 | Redis | activo en `127.0.0.1` |
| 8081/50052 | Weaviate HTTP/gRPC | activo en `127.0.0.1` |
| 7475/7688 | Neo4j HTTP/Bolt | activo en `127.0.0.1` |

## Variables clave redacted

| Variable | Estado |
|---|---|
| `OPERATOR_PROFILE` | `dedicated_local` |
| `LOCAL_AUTONOMY_MODE` | `full` |
| `CODE_DIRECTOR_BUDGET_MODE` | `soft` |
| `ENABLE_EMAIL_SEND` | `false` |
| `MAIL_ALLOW_EXPLICIT_SEND` | `false` |
| `MAIL_REQUIRE_APPROVAL_FOR_SEND` | `true` |
| `MAIL_ENABLED` | `true` |
| `ENABLE_MCP_CLIENT` | `true` |
| `MCP_SERVERS` | configurado, valores/tokens redacted |
| `TELEGRAM_ENABLED` | `true` |
| `ENABLE_KIMI_WEBBRIDGE` | `true` |
| `GODADDY_DNS_DRY_RUN_ONLY` | `true` |
| `GODADDY_ALLOW_PRODUCTION_WRITES` | `false` |
| `TOOLS_READONLY_MODE` | `true` |
| `ENABLE_BROWSER_AUTOMATION` | `false` |
| `ALLOW_DANGEROUS_TOOLS` | `false` |
| `LIVE_TESTS_ENABLED` | no detectado en `.env` |

## Estado de herramientas y configuracion

- TestSprite MCP: account check OK, Diego Manzur, Starter, 323 credits.
- Config TestSprite local: `.testsprite/config.json` ausente; se usa
  `testsprite_tests/tmp/config.json`.
- Frontend package scripts: `dev`, `build`, `start`, `lint`, `serve`.
- Scripts oficiales disponibles: `dev_up.sh`, `dev_down.sh`, `full-qa.sh`,
  `stress-qa.sh`, `full-e2e.sh`, `full-qa-live.sh`,
  `verify_desktop_launchers.sh`, `full-testsprite.sh`,
  `sync_doc_counts.py`.
- Alembic migrations: 20 archivos, head `202605200003`.

## Lectura del snapshot

El repo tiene cambios no commiteados derivados de la remediacion TestSprite y
de los reportes finales. El snapshot es apto para continuar gates, pero la
evidencia final debe validar el filesystem actual y no solo el commit HEAD.

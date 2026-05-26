# 04 — Baseline QA

Fecha: **2026-05-25** | Commit: `6891d5c` | Perfil: `dedicated_local/full`

## Resumen

| Gate | Exit | Resultado | Clasificación |
|---|---|---|---|
| `bash scripts/full-qa.sh` | 0 | **1200 passed**, 1 skipped, 28 deselected | Código OK |
| `bash scripts/stress-qa.sh 3` | 0 | 3× **1200 passed** | Código OK |
| `npx playwright test` | 0 | **43 passed** | Código OK |
| `git diff --check` | 0 | Clean (post-fix whitespace doc) | Higiene OK |
| `sync_doc_counts --check` | 0 | Conteos estructurales OK | Docs OK |
| `LIVE_TESTS_ENABLED=1 full-qa-live.sh` | — | No ejecutado (opt-in, no forzado) | N/A |

## Detalle full-qa.sh

Log: `qa/reports/full-qa-prompt1.log`

Incluye: pytest, ruff, ruff format, mypy (137 files), alembic check, npm ci, lint, build `.next-qa`, sync_doc_counts, git diff --check.

**Nota:** Primera corrida falló solo en `git diff --check` por trailing whitespace en doc de auditoría creado en sesión — corregido.

## Detalle Playwright

Log: `test-results/playwright/baseline-*.log`

Auto-mint JWT via `_global-setup.ts` — sin exportar `COGOS_JWT`.

## Detalle stress-qa

Log: `test-results/backend/stress-qa-baseline.log`

3 pasadas consecutivas verdes, flakiness 0%.

## Contradicciones con Markdown previo

| Doc decía | Real medido | Acción |
|---|---|---|
| 1192 passed | 1200 passed | Docs actualizados (+8 `test_final_functional_hardening.py`) |
| COMMERCIAL APROBADO | Gates verdes en HEAD | Confirmado PASS funcional |

## verify_desktop_launchers.sh

Existe en `scripts/` — no re-ejecutado en esta pasada (stack ya vivo; script validado históricamente).

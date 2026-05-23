# 12 · Official Gates Re-Run

## Resultados (todos verdes tras corrección)

| Gate | Comando | Resultado | Log |
|---|---|---|---|
| Backend QA | `bash scripts/full-qa.sh` | **947 passed**, 1 skipped, 28 deselected · EXIT=0 | `test-results/reaudit/full-qa-after-bugfix2.log` |
| Stress QA | `bash scripts/stress-qa.sh 3` | 3 pasadas verdes de **944 passed** · EXIT=0 | `test-results/reaudit/stress-qa.log` |
| Playwright E2E | `unset COGOS_JWT && npx playwright test` | **31 passed (42.6s)** · EXIT=0 | `test-results/reaudit/playwright3.log` |
| Desktop launchers | `bash scripts/verify_desktop_launchers.sh` | Desktop launchers OK · EXIT=0 | `test-results/reaudit/verify_launchers.log` |
| `git diff --check` | dentro de `full-qa.sh` | OK | inline en `full-qa-after-bugfix2.log` |
| `alembic check` | dentro de `full-qa.sh` | OK (sin drift) | inline |
| `sync_doc_counts --check` | dentro de `full-qa.sh` | OK | inline |
| `ruff` + `ruff format` + `mypy` | dentro de `full-qa.sh` | OK | inline |
| `eslint --max-warnings 0` | dentro de `full-qa.sh` | OK | inline |
| Next.js build aislado `.next-qa` | dentro de `full-qa.sh` | 4 static pages prerendered OK | inline |

## Cambios vs baseline previo

- Backend: **944 → 947** tests pasados (los 3 nuevos en
  `tests/test_action_request_eager_defaults.py`).
- Frontend: 31 → 31 (sin cambio numérico; el bug del nuevo TS-ZF-20260523-006 fue backend).

## `full-qa-live.sh`

No ejecutado. Razón:

- `.env` no contiene `LIVE_TESTS_ENABLED=1`.
- El test live de Telegram **enviaría un mensaje real** a `getMe()` (read-only)
  y de mail haría IMAP login (read-only). No hay daño, pero el contrato dice
  opt-in. El operador puede ejecutarlo cuando quiera con
  `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh`.

## Falsa alarma resuelta durante el rerun

Primer intento de Playwright concurrente con `npm ci` de `full-qa.sh`
generó 17 fallos `Cannot find module .../playwright/lib/worker/workerProcessEntry.js`.
Causa: `npm ci` borra y rehace `node_modules/` mientras la Playwright
estaba en ejecución. Resolución: separar las ejecuciones temporalmente.
Cuando se ejecutan secuencialmente, **31/31 verde**. Esto es un riesgo de
proceso, no un bug del producto; documentado para futuras corridas.

## Bug P1 detectado y corregido en esta fase

**TS-ZF-20260523-006** — `/actions/browser/preview/request` retornaba
HTTP 500 con `sqlalchemy.exc.MissingGreenlet`. Detalle en
`14_NEW_FINDINGS.md`. Fix aplicado, 3 tests de regresión nuevos verdes,
endpoint live ahora HTTP 200 con `updated_at` poblado.

# 02 Existing Test Inventory

Estado inicial: en progreso.

## Conteos reales iniciales

| Suite | Conteo |
|---|---:|
| Backend `backend/tests/test_*.py` | 113 |
| Live read-only `backend/tests/live/test_*.py` | 7 |
| Playwright `frontend/tests/e2e/*.spec.ts` | 18 |
| Frontend views `frontend/app/views/*.tsx` | 20 |

## Backend pytest

- Config: `backend/pyproject.toml`.
- Default: `-m 'not integration and not slow and not live_readonly'`.
- DB: `backend/tests/conftest.py` redirige a DB de test; el contrato anti-produccion existe.
- Cobertura fuerte: Telegram auth matrix, mail read-only/escape hatch,
  health configured-vs-verified, ActionRequest idempotency, workflow import,
  Alembic drift, settings registry, learning kill switch.
- Debilidades:
  - algunos tests integration/live se auto-skippean por entorno;
  - live provider coverage es opt-in, correcto por contrato;
  - no todo Action Plane tiene matriz concurrente end-to-end;
  - `full-qa.sh` toleraba `alembic check` fallido con `.env` presente.

## Frontend Playwright

Specs actuales:

- `smoke.spec.ts`
- `navigation.spec.ts`
- `auth.spec.ts`
- `forms.spec.ts`
- `responsive.spec.ts`
- `regression-critical.spec.ts`
- `glass-cockpit.spec.ts`
- `recipe-proposals.spec.ts`
- `mail.spec.ts`
- `commercial-zero-friction-smoke.spec.ts`
- `all-views-console-guard.spec.ts`
- `navigation-hotkeys-command-palette.spec.ts`
- `health-verified-vs-configured.spec.ts`
- `jobs-approvals-action-lifecycle.spec.ts`
- `mail-readonly-contract.spec.ts`
- `error-empty-loading-states.spec.ts`
- `mobile-pwa.spec.ts`
- `zero-friction-dedicated-local.spec.ts`

Fortalezas:

- `watchPageHealth` captura `console.error`, `pageerror`, `requestfailed` y 5xx.
- `navigation.spec.ts` recorre las 20 tabs.
- `mail.spec.ts` prueba que UI llama `/mail/sync/dispatch`, no `/mail/sync`.
- `glass-cockpit.spec.ts` prueba guard `asArray` ante shape incorrecto.

Debilidades:

- Varias specs dependen de backend vivo y token externo `COGOS_JWT`.
- Hay gaps por nombre/alcance frente al plan comercial pedido:
  health configured-vs-ok UI, jobs/approvals/action lifecycle, mobile PWA,
  error/empty/loading con JSON malformado, zero-friction dedicated local.
- `regression-critical.spec.ts` aun espera `["ok", "degraded"]` para health,
  no incluye `configured`, por lo que puede fallar o esconder el contrato nuevo.

## Scripts QA

- `scripts/full-qa.sh`: corre backend tests, ruff, format, mypy, Alembic hard gate
  con DB configurada, frontend lint/build, sync doc counts y diff check.
- `scripts/stress-qa.sh`: repite pytest N veces, util para flakiness backend.
- `scripts/full-qa-live.sh`: opt-in live read-only, correcto.
- `scripts/verify_desktop_launchers.sh`: smoke read-only de launchers.

## TestSprite

`mcp__testsprite_agent__` esta disponible. Al inicio no existia config
TestSprite usable; el primer bootstrap quedo colgado y la CLI fallo sin plan.
Luego se genero PRD + `testsprite_frontend_test_plan.json` y se ejecuto un
subconjunto acotado (`TC001`, `TC002`, `TC005`): **3/3 passed**.

Calidad de cobertura: util como smoke externo/advisory, pero los tests
generados solo navegan/clican y verifican exito de ejecucion; no tienen los
asserts fuertes de la suite Playwright comercial sobre console/page errors,
malformed payloads, no drafts/no send, health configured-vs-verified y estados
diagnosticables. Por eso Playwright queda como gate E2E principal.

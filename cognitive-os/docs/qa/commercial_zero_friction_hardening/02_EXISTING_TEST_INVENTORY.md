# 02 Existing Test Inventory

Inventario realizado sobre la rama
`codex/commercial-zero-friction-hardening`, HEAD inicial
`d25af91a2256662df36a4e675d2ad1e771b5f936`.

## Configuracion de tests

| Suite | Config | Observacion |
|---|---|---|
| Backend pytest | `backend/pyproject.toml` | `addopts` excluye `integration`, `slow` y `live_readonly` por defecto |
| Backend live | `backend/tests/live/conftest.py` | skip global si `LIVE_TESTS_ENABLED` no es truthy |
| Frontend E2E | `frontend/playwright.config.ts` | global setup, proyectos desktop/mobile, trace screenshot/video on failure |
| Frontend lint/build | `frontend/package.json`, `next.config.mjs` | build aislable con `NEXT_DIST_DIR=.next-qa` |
| Release gate | `scripts/full-qa.sh` | backend + frontend + docs counts + whitespace |
| Stress gate | `scripts/stress-qa.sh` | 3 pasadas por defecto de pytest |
| Live gate | `scripts/full-qa-live.sh` | corregido: exige env opt-in externo |
| Desktop launchers | `scripts/verify_desktop_launchers.sh` | validacion read-only de wrappers `.sh` y `.desktop` |

## Backend pytest

Cobertura fuerte observada:

- mail read-only y escape hatch de envio con flags/frase exacta;
- Telegram fail-closed, allowlist y matriz de comandos;
- health configured-vs-verified y `operational_backlog`;
- Action Plane base: request/approval/dispatch, eager defaults e idempotency;
- settings registry, credentials status y readiness;
- learning kill switch, skill promotion y failure postmortem;
- DB test aislada mediante fixtures y guard anti-production;
- Alembic drift/head en gates.

Debilidades:

- no todas las acciones del Action Plane tienen matriz concurrente completa;
- broker/worker down se cubre mas por health/reapers que por simulacion amplia;
- RAG/document analysis/learning tienen tests utiles pero no cubren todos los
  edge cases de evidencia, cancelacion y presupuesto pedidos en el mandato;
- algunos tests usan tokens sinteticos para endpoints internos, correcto en unit
  tests, pero los gates E2E deben ejercitar `/auth/local-token`.

Riesgo de falso verde corregido:

- `full-e2e.sh` podia mintar JWT directo y ocultar una rotura del endpoint
  zero-friction local-token. Queda cubierto por test estatico.

## Frontend Playwright

Specs existentes relevantes:

- `commercial-zero-friction-smoke.spec.ts`
- `all-views-console-guard.spec.ts`
- `navigation-hotkeys-command-palette.spec.ts`
- `health-verified-vs-configured.spec.ts`
- `jobs-approvals-action-lifecycle.spec.ts`
- `mail-readonly-contract.spec.ts`
- `error-empty-loading-states.spec.ts`
- `mobile-pwa.spec.ts`
- `zero-friction-dedicated-local.spec.ts`
- specs historicas de smoke, auth, forms, responsive, regression, mail y glass cockpit.

Fortalezas:

- helpers fallan ante `console.error`, `pageerror`, `requestfailed` y 5xx no
  permitidos;
- hay cobertura desktop y mobile;
- fixtures hermeticas para vistas comerciales criticas;
- se comprueba que mail UI no exponga send/draft normal;
- se comprueban estados malformed/empty/error en rutas criticas.

Debilidades:

- TestSprite historico es advisory; sus asserts son mas suaves que Playwright;
- no todos los flows de Document Analysis, Research, DeepAgents y Learning
  estan cubiertos con asserts de negocio end-to-end;
- no se debe considerar Playwright verde sin stack local vivo y sin ejecutar el
  gate real.

## Scripts QA

| Script | Que cubre | Hallazgo |
|---|---|---|
| `scripts/full-qa.sh` | sync, pytest, ruff, format, mypy, Alembic, frontend lint/build, docs counts, diff check | gate oficial hermetico |
| `scripts/stress-qa.sh` | flakiness backend por repeticion de pytest | util, no reemplaza frontend |
| `scripts/full-e2e.sh` | Playwright contra stack local vivo | corregido para no bypassar `/auth/local-token` |
| `scripts/full-qa-live.sh` | smokes read-only contra proveedores reales | corregido para exigir opt-in externo |
| `scripts/verify_desktop_launchers.sh` | launchers de escritorio sin levantar servicios | read-only, adecuado |

## Live tests

Contrato:

- nunca dentro de `full-qa.sh`;
- solo con `LIVE_TESTS_ENABLED=1` ya definido por el operador;
- read-only;
- auto-skip si falta credencial/provider.

Falso verde/falsa seguridad detectada:

- el script live anterior seteaba `LIVE_TESTS_ENABLED=1` internamente. Aunque los
  tests son read-only, eso convertia una invocacion accidental del script en
  consentimiento implicito. Corregido.

## TestSprite

La tool TestSprite estuvo disponible tras discovery y la cuenta fue validada.
La ejecucion nueva quedo bloqueada por errores de tunel/plataforma, no por
Playwright ni por el stack local. Hay reportes historicos en
`docs/audits/testsprite/` con certificacion 10/10, pero esta pasada no declara
TestSprite verde sin resultado nuevo.

Fallback requerido:

- usar Playwright como gate E2E primario;
- mantener `07_TESTSPRITE_AND_PLAYWRIGHT_PLAN.md` con pasos exactos para
  re-ejecucion TestSprite cuando el MCP/CLI este disponible.

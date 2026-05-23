# 07 TestSprite And Playwright Plan

## Playwright Ejecutado

Se creo un gate separado:

```bash
bash scripts/full-e2e.sh
```

Propiedades del gate:

- requiere API y frontend locales alcanzables;
- no ejecuta `npm ci` por defecto para no matar un dev server vivo;
- minta `COGOS_JWT` local si falta;
- hace preflight CORS contra el origen frontend;
- ejecuta `npx playwright test`;
- usa screenshot/video/trace segun `playwright.config.ts`.

Resultado validado:

```text
COGOS_API_BASE=http://127.0.0.1:8001 \
COGOS_BASE_URL=http://localhost:3101 \
COGOS_SKIP_PLAYWRIGHT_INSTALL=1 \
bash scripts/full-e2e.sh

31 passed
OK: full-e2e
```

Cobertura nueva agregada:

- `commercial-zero-friction-smoke.spec.ts`
- `all-views-console-guard.spec.ts`
- `navigation-hotkeys-command-palette.spec.ts`
- `health-verified-vs-configured.spec.ts`
- `jobs-approvals-action-lifecycle.spec.ts`
- `mail-readonly-contract.spec.ts`
- `error-empty-loading-states.spec.ts`
- `mobile-pwa.spec.ts`
- `zero-friction-dedicated-local.spec.ts`

## TestSprite Ejecutado

Estado: disponible como MCP. Hubo bloqueo inicial de bootstrap/CLI, pero se
resolvio generando PRD + plan y ejecutando un subconjunto critico.

Ejecuciones realizadas:

1. Intento inicial:
   - `testsprite_bootstrap` contra frontend local.
   - Resultado: timeout del MCP tras 120s.
   - CLI local inicial fallo por ausencia de `testsprite_frontend_test_plan.json`.
2. Reparacion operativa:
   - PRD generado para el repo.
   - `testsprite_tests/testsprite_frontend_test_plan.json` generado.
   - API local temporal disponible durante la corrida.
3. Ejecucion acotada:
   - `TC001` - Show configured health in the cockpit sidebar.
   - `TC002` - Keep the health state from misrendering as danger after navigation.
   - `TC005` - Load the mail inbox in read-only mode.

Resultado:

```text
TestSprite TC001 -> PASSED
TestSprite TC002 -> PASSED
TestSprite TC005 -> PASSED
Total: 3/3 passed
```

Artefactos locales generados:

- `testsprite_tests/tmp/raw_report.md`
- `testsprite_tests/tmp/test_results.json`
- `testsprite_tests/testsprite-mcp-test-report.md`
- `testsprite_tests/TC001_Show_configured_health_in_the_cockpit_sidebar.py`
- `testsprite_tests/TC002_Keep_the_health_state_from_misrendering_as_danger_after_navigation.py`
- `testsprite_tests/TC005_Load_the_mail_inbox_in_read_only_mode.py`

Decision:

- Se declara TestSprite ejecutado con resultado verde para el subconjunto
  probado: 3/3 passed.
- No se declara que TestSprite cubra todo el contrato comercial.
- Los tests generados navegan/clican y verifican ejecucion exitosa, pero sus
  asserts son mas debiles que los Playwright comerciales propios. Por eso
  TestSprite queda como smoke advisory y Playwright 31/31 sigue siendo el gate
  E2E principal.
- No se versionan artefactos temporales `testsprite_tests/tmp`.

## Instrucciones Para Reintento TestSprite Completo

Para ampliar TestSprite mas alla del smoke advisory:

1. Levantar API y frontend:
   - API: `http://127.0.0.1:8000` o `:8001`
   - Frontend: `http://localhost:3001` o `:3101` con CORS permitido.
2. Generar PRD/config si no existe.
3. Generar o revisar `testsprite_frontend_test_plan.json`.
4. Ejecutar `testsprite_generate_code_and_execute` con todos los test IDs.
5. Comparar los asserts generados contra los contratos Playwright existentes;
   si son cosmeticos, tratarlos como advisory y no como release gate.

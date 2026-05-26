# TestSprite Cognitive OS — Referencia

## MCP tools reales (`user-TestSprite`)

| Tool | Cuándo |
|---|---|
| `testsprite_check_account_info` | Siempre al inicio; ver créditos |
| `testsprite_bootstrap` | Solo si prepare.sh no corrió y no hay config válido |
| `testsprite_generate_frontend_test_plan` | Plan auxiliar cloud; gate usa plan repo |
| `testsprite_generate_backend_test_plan` | API focal; requiere `type=backend` en config |
| `testsprite_generate_code_and_execute` | **Evitar crudo** — preferir full-testsprite.sh |
| `testsprite_generate_code_summary` | Tras bootstrap, si el flujo MCP lo pide |
| `testsprite_open_test_result_dashboard` | Solo lectura de resultados |

Leer schema JSON en `mcps/user-TestSprite/tools/` antes de cada call.

## Anti-patrón que rompió Prompt 1 (2026-05-25)

```
testsprite_generate_code_and_execute({
  testIds: [],                    // ← DISPARA descubrimiento API + tunnel bug
  serverMode: "development",      // ← inestable bajo audit
  additionalInstruction: "... http://127.0.0.1:8000 ..."  // ← empeora parser
})
→ node .../generateCodeAndExecute   // ← sin batches del repo
→ Target connect failed for health:80 (12+ min, abort)
```

## Patrón correcto

```bash
bash scripts/testsprite_mcp_prepare.sh
TESTSPRITE_TEST_IDS=TC001 TESTSPRITE_BATCH_SIZE=1 bash scripts/full-testsprite.sh
export TESTSPRITE_BATCH_SIZE=1
bash scripts/full-testsprite.sh
```

## Plan canónico — IDs

Fuente: `qa/testsprite/frontend_commercial_plan.json`

Casos TC001–TC038 (28 total). Reemplazos históricos verificados:

- TC037 reemplaza TC034 (auth/network)
- TC038 reemplaza TC035 (action/google guards)

Para subset focal en audit:

```bash
TESTSPRITE_TEST_IDS=TC001,TC003,TC037 bash scripts/full-testsprite.sh
```

## Config.json — shape esperado

```json
{
  "status": "init",
  "scope": "codebase",
  "type": "frontend",
  "localEndpoint": "http://localhost:3001/",
  "serverMode": "production",
  "executionArgs": {
    "projectName": "cognitive-os",
    "projectPath": "/abs/path/cognitive-os",
    "testIds": [],
    "serverMode": "production",
    "additionalInstruction": "... sin URLs http:// ...",
    "envs": { "API_KEY": "..." }
  }
}
```

`testIds: []` en config está OK **solo** cuando `full-testsprite.sh` filtra por plan/batches.
**No** OK cuando MCP execute usa `[]` directamente sin el runner.

## Plantilla additionalInstruction segura

```
Cognitive OS commercial audit on dedicated local PC (dedicated_local/full).
Frontend cockpit on port 3001. API auth via POST /auth/local-token.
Zero friction: do not add SaaS approval friction.
DO NOT send email, create drafts, or perform real DNS/provider writes.
Mail digest read-only or honest disabled UI is PASS.
Empty tables with clear empty states are PASS.
Fail on: crash, white screen, pageerror, hidden errors, unsafe writes, lying health badges.
```

## Artefactos por corrida

| Path | Contenido |
|---|---|
| `testsprite_tests/tmp/test_results.json` | Último batch (sobrescrito) |
| `testsprite_tests/tmp/batched_results.json` | Agregado full-testsprite |
| `testsprite_tests/tmp/raw_report.md` | Raw TestSprite |
| `testsprite_tests/testsprite-mcp-test-report.md` | Reporte MCP |
| `qa/reports/testsprite_latest_summary.md` | Resumen sanitizado repo |
| `test-results/testsprite/<timestamp>/` | Copia audit Prompt |

## Integración con gates locales

TestSprite es **advisory** para release; gate fuerte:

| Gate | Comando | Snapshot |
|---|---|---|
| Backend | `bash scripts/full-qa.sh` | 1200 passed |
| Stress | `bash scripts/stress-qa.sh 3` | 3× verde |
| E2E | `npx playwright test` | 43 passed |

Si TestSprite BLOCKED pero gates locales verdes → **PARTIAL**, no FAIL producto.

## Verificación rápida (agente)

```bash
cd cognitive-os
bash .cursor/skills/testsprite-cognitive-os/scripts/verify_testsprite_ready.sh
python3 .cursor/skills/testsprite-cognitive-os/scripts/validate_testsprite_config.py
bash scripts/testsprite_audit.sh
```

## Errores históricos

Ver [MISTAKES.md](MISTAKES.md) — leer antes de ejecutar.

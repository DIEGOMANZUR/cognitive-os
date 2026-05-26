# Prompt 1 — Runbook TestSprite (corregido)

> **Skill obligatoria:** `.cursor/skills/testsprite-cognitive-os/AGENT_CONTRACT.md` + `SKILL.md` + `MISTAKES.md`
> **Entrypoint único:** `bash scripts/testsprite_audit.sh` (gates: validate + assert smoke/full)
> Verificación stack: `TESTSPRITE_VERIFY_MODE=stack bash .cursor/skills/testsprite-cognitive-os/scripts/verify_testsprite_ready.sh`

Fecha fix: **2026-05-25**

## Qué falló y por qué

La corrida abortada invocó **`testsprite_generate_code_and_execute` vía MCP** con:

| Error | Efecto |
|---|---|
| `testIds: []` | TestSprite intentó descubrir/ejecutar **todo** el plan + rutas API |
| `serverMode: development` en `executionArgs` | Modo dev limitado + túnel inestable bajo carga |
| Instrucciones con `http://127.0.0.1:8000` explícito | El parser del túnel trató segmentos OpenAPI como hosts (`health:80`, `jobs:80`, `127.0.0.1:800`, `127.0.0.1:8`) |
| Sin `testsprite_bootstrap` previo | Config inconsistente vs puerto 3001 |
| Sin batches | Proceso colgado >12 min hasta abort |

**No es un bug de Cognitive OS.** Es un anti-patrón de invocación TestSprite MCP.

## Flujo correcto (Prompt 1 re-run)

### A. Preferido — runner del repo

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os"
export TESTSPRITE_API_KEY="<tu-key>"   # o API_KEY
bash scripts/testsprite_mcp_prepare.sh
export TESTSPRITE_BATCH_SIZE=1
bash scripts/full-testsprite.sh
```

Smoke rápido antes del plan completo:

```bash
TESTSPRITE_TEST_IDS=TC001 bash scripts/full-testsprite.sh
```

### B. MCP Cursor (si se usa la tool)

Orden obligatorio:

1. `testsprite_bootstrap` — `localPort: 3001`, `type: frontend`, `projectPath`, `testScope: codebase`
2. `testsprite_generate_frontend_test_plan`
3. `testsprite_generate_code_and_execute` — **`testIds` NO vacío** (ej. `["TC001"]`), `serverMode: production`

**Prohibido en Prompt 1:**

- `testIds: []` en MCP directo
- `serverMode: development` para auditoría completa
- URLs `http://127.0.0.1:8000` en `additionalInstruction` (usar texto "API local puerto 8000")

### C. Fallback si TestSprite cloud falla

Gates locales **siguen siendo el gate fuerte**:

```bash
bash scripts/full-qa.sh
bash scripts/stress-qa.sh 3
cd frontend && npx playwright test
```

## Preflight antes de Prompt 1

```bash
bash scripts/testsprite_mcp_prepare.sh
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:3001/
pgrep -af generateCodeAndExecute || echo "sin runners huérfanos"
```

Stack público opcional (portal web TestSprite): `bash scripts/testsprite_web/status_testsprite_stack.sh`

## Artefactos esperados

- `testsprite_tests/tmp/batched_results.json`
- `qa/reports/testsprite_latest_summary.md`
- `test-results/testsprite/<timestamp>/`

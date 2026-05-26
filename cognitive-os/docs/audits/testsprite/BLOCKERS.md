# TestSprite MCP — Blockers

Fecha fix: **2026-05-25**

## Blocker resuelto: TS-TUNNEL-20260525

### Síntoma

`generateCodeAndExecute` vía MCP directo abortado tras ~12 min con miles de:

```
Target connect failed for health:80
Target connect failed for 127.0.0.1:800
Target connect failed for jobs:80
```

### Causa raíz

1. **`testIds: []`** — el runner intentó cubrir todo el plan + descubrimiento API; el túnel TestSprite interpretó **rutas OpenAPI** (`/health`, `/jobs`, `/audit`, …) como **nombres de host** en puerto **80**.
2. **`serverMode` conflictivo** — `production` a nivel config pero `development` en `executionArgs`.
3. **Instrucciones con URLs completas** (`http://127.0.0.1:8000`) empeoraron el parser del túnel.
4. **Sin bootstrap** — no se llamó `testsprite_bootstrap` con `localPort: 3001` antes de ejecutar.
5. **Anti-patrón** — invocar `node ... generateCodeAndExecute` en lugar del runner **`scripts/full-testsprite.sh`** (28/28 PASS histórico).

### Fix aplicado

| Acción | Archivo |
|---|---|
| Script de preparación + reset locks/config | `scripts/testsprite_mcp_prepare.sh` |
| Runbook Prompt 1 corregido | `docs/audits/testsprite/PROMPT1_TESTSPRITE_RUNBOOK.md` |
| Runner canónico (sin cambios, ya correcto) | `scripts/full-testsprite.sh` |

### Cómo ejecutar TestSprite en Prompt 1 (re-run)

```bash
bash scripts/testsprite_mcp_prepare.sh
TESTSPRITE_BATCH_SIZE=1 bash scripts/full-testsprite.sh
```

Smoke: `TESTSPRITE_TEST_IDS=TC001 bash scripts/full-testsprite.sh`

### Estado MCP

| Check | Resultado |
|---|---|
| MCP instalado/autenticado | OK |
| Ejecución MCP cruda testIds=[] | **NO USAR** |
| Ejecución vía full-testsprite.sh | **USAR** |
| Gates locales pytest+Playwright | PASS independiente de TestSprite |

## Blockers activos

**Ninguno de producto.** TestSprite cloud requiere el flujo corregido arriba.

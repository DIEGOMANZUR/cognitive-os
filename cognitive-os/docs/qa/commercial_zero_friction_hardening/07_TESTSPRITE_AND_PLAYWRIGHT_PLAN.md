# 07 TestSprite And Playwright Plan

## Playwright

Gate ejecutado:

```bash
COGOS_SKIP_PLAYWRIGHT_INSTALL=1 bash scripts/full-e2e.sh
```

Resultado:

- **41 passed**.
- El runner no hizo `npm ci` y no invalido el frontend vivo.
- `_global-setup.ts` auto-minteo JWT via
  `http://127.0.0.1:8000/auth/local-token`.
- Las specs desktop/mobile cubrieron 20 vistas, health configured-vs-verified,
  jobs/approvals/action lifecycle, mail read-only, malformed payloads,
  command palette/hotkeys, mobile shell y zero-friction `dedicated_local/full`.

Propiedades requeridas que quedan como contrato:

- no mintar JWT directo con Python desde `scripts/full-e2e.sh`;
- preflight CORS antes de Playwright;
- trace/screenshot/video on failure desde `playwright.config.ts`;
- helpers que fallen por `console.error`, `pageerror`, request failed y HTTP
  5xx no permitidos.

## TestSprite

Estado final: **PASS**.

Ejecuciones:

- Token alternativo validado por API (`/api/me`). La credencial no queda
  versionada ni documentada y `testsprite_tests/tmp/config.json` se redacciona
  al cierre.
- Full directo inicial contra `http://localhost:3001` + backend `:8000`:
  28 ejecutados, 24 passed, 3 blocked, 1 failed.
- Causa de los 4 no verdes: plan TestSprite no era state-aware; exigia
  aprobaciones pendientes, digest activo y cola de jobs vacia en un entorno
  local vivo donde esos estados pueden ser honestamente vacios, deshabilitados
  o poblados.
- Rerun focalizado tras corregir el plan: TC006, TC018, TC021, TC022 ->
  **4 passed**.
- Full all-at-once corregido: invalidado porque el paralelismo del runner
  saturo `uvicorn` local (`/health` timeout y backlog lleno). Se recupero con
  `~/Escritorio/Reiniciar Cognitive OS.sh`.
- Full corregido en lotes de 4: **28 passed**, 0 failed, 0 blocked. Evidencia
  agregada en `testsprite_tests/tmp/batched_results.json` (gitignored).

Runner reproducible:

```bash
API_KEY=<testsprite-api-key> bash scripts/full-testsprite.sh
```

Propiedades:

- Batch size por defecto: 1 (`TESTSPRITE_BATCH_SIZE=1`), con override
  permitido solo para diagnostico. El runner mantiene idle timeout, reintentos y
  split adaptativo si se usa un lote mayor.
- Health backend antes/despues de cada lote.
- Salida sanitizada frente a `sk-user-*`.
- Redaccion automatica de `testsprite_tests/tmp/config.json`.
- Contrato duro en instrucciones: no drafts, no send, no writes externos,
  no aprobacion arbitraria de requests reales.

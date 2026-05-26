# 16 — Repair Plan

Fecha: **2026-05-26**  
Alcance: reparar hallazgos de ejecución TestSprite MCP inicial.  
Importante: no hay bug funcional de producto confirmado; los items son bloqueos de harness/plan TestSprite.

## Prioridad

1. `TS-CURSOR-004` — P0 riesgo de contrato si se ejecuta mail sync como UI normal.
2. `TS-CURSOR-001` — P1 UI smoke no valida origen público.
3. `TS-CURSOR-002` — P1 API smoke no ejecuta caso.
4. `TS-CURSOR-003` — P2 E2E/Guard no existen como IDs ejecutables.

## TS-CURSOR-004

| Campo | Valor |
|---|---|
| Suite | UI/GUARD |
| Severidad | P0 riesgo de contrato |
| Evidencia | `TC024` decía “Sync mail in read-only mode…” y podía activar sync |
| Expected PRD | Mail normal: read/classify/summarize/digest/propose text; no drafts, no sends, no sync mutante obligatorio |
| Actual | Caso TestSprite pedía “Trigger a read-only mail sync” |
| Clasificación | Bug real de plan/harness, no bug producto |
| Root cause confirmado | Plan MCP no separó read-only UI normal de guard negative |
| Archivos a modificar | `testsprite_tests/testsprite_frontend_test_plan.json` |
| Fix exacto | Reescribir `TC024` como revisión read-only sin sync/send/draft/approve-send; agregar `TCMAIL001` estable |
| Zero-friction | Preserva mail read-only sin añadir fricción SaaS |
| Mail/action/health | Evita side effects mail |
| Rerun focal | `TCMAIL001` o `TC024` después de smoke público válido |
| Criterio cierre | Código/artifact TestSprite no contiene sync/send/draft y resultado es PASS o fallo real seguro |

## TS-CURSOR-001

| Campo | Valor |
|---|---|
| Suite | UI |
| Severidad | P1 operativo |
| Evidencia | `TC001` PASS bruto usó `http://localhost:3001/` y token dummy |
| Expected PRD | `https://cognitive.doctormanzur.com/`, localStorage `cogos.token` y `cogos.api=https://cognitive-api.doctormanzur.com` |
| Actual | Localhost + `test-local-admin-jwt` |
| Clasificación | Blocker/harness; no bug producto |
| Root cause confirmado | `localEndpoint` TestSprite apuntaba a localhost y plan TC001 favorecía JWT local |
| Archivos a modificar | `testsprite_tests/tmp/config.json`, `testsprite_tests/testsprite_frontend_test_plan.json` |
| Fix exacto | Agregar `TCPUB001`, cambiar `localEndpoint` a URL pública y setear `testIds=["TCPUB001"]` |
| Zero-friction | Mantiene SPA y auth por localStorage; no crea rutas fake |
| Rerun focal | `TCPUB001` |
| Criterio cierre | Código generado navega a URL pública y no a localhost; TestSprite resultado no vacío |

## TS-CURSOR-002

| Campo | Valor |
|---|---|
| Suite | API |
| Severidad | P1 operativo |
| Evidencia | `TCAPI001` produjo `[]`/`NaN` |
| Expected PRD | TestSprite ejecuta `/health`, `/openapi.json`, `/docs`, `/redoc` públicos |
| Actual | Caso no ejecutado porque no estaba en plan activo frontend/config |
| Clasificación | Blocker/harness; no bug backend |
| Root cause confirmado | Plan API estaba separado y config activa era frontend; MCP no ejecutó ID ausente |
| Archivos a modificar | `testsprite_tests/testsprite_frontend_test_plan.json`, `testsprite_tests/tmp/config.json` |
| Fix exacto | Agregar `TCAPI001` al plan activo como smoke API público ejecutable |
| Zero-friction | No toca producto |
| Rerun focal | `TCAPI001` |
| Criterio cierre | `test_results.json` contiene resultado para `TCAPI001` o artifact con fallo real, no `[]` |

## TS-CURSOR-003

| Campo | Valor |
|---|---|
| Suite | E2E/GUARD |
| Severidad | P2 operativo |
| Evidencia | `TE2E*` y `TG*` son markdown manuales, no IDs del plan activo |
| Expected PRD | Suites ejecutables por TestSprite |
| Actual | No hay IDs nativos |
| Clasificación | Blocker/harness |
| Root cause confirmado | MCP no expone generador E2E/Guard separado |
| Archivos a modificar | `testsprite_tests/testsprite_frontend_test_plan.json` |
| Fix exacto | Añadir smoke/regression IDs seguros (`TCPUB001`, `TCAPI001`, `TCMAIL001`) y mapear Guard a API/UI seguros |
| Zero-friction | No bloquea flujos reales |
| Rerun focal | `TCPUB001`, `TCAPI001`, `TCMAIL001` |
| Criterio cierre | Focales ejecutan y generan artifacts; critical rerun puede arrancar |

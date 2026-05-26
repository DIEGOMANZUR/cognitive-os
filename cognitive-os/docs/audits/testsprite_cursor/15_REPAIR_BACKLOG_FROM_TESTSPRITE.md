# 15 — Repair Backlog From TestSprite

Fecha: **2026-05-26**  
Alcance: backlog derivado de ejecución TestSprite MCP inicial.  
Nota: no se corrigió código en este prompt.

## TS-CURSOR-001 — UI smoke no valida origen público

| Campo | Valor |
|---|---|
| Suite | UI |
| Severidad | P1 operativo de auditoría |
| Bug real producto | No confirmado |
| Evidencia | `TC001` bruto PASS, pero código generado navega a `http://localhost:3001/` y usa `test-local-admin-jwt` |
| Expected | `https://cognitive.doctormanzur.com/` + `localStorage.cogos.token=<JWT real>` + `cogos.api=https://cognitive-api.doctormanzur.com` |
| Actual | Localhost + token dummy |
| Root cause probable | TestSprite MCP usa `localEndpoint`/tunnel local pese a instrucciones públicas; plan TC001 también favorece flujo JWT local |
| Archivos probables | `testsprite_tests/tmp/config.json`, `testsprite_tests/testsprite_frontend_test_plan.json`, `docs/audits/testsprite_cursor/04_UI_PLAN.md` |
| Tipo de fix | Harness/plan TestSprite, no producto |
| Riesgo | Alto: falsos verdes UI/E2E |
| Rerun necesario | UI smoke `TC001` público + no-localhost check |
| Criterio cierre | Código generado/TestSprite artifact muestra navegación pública o configuración aceptada explícitamente como auditoría local separada |

## TS-CURSOR-002 — API smoke no ejecuta `TCAPI001`

| Campo | Valor |
|---|---|
| Suite | API |
| Severidad | P1 operativo de auditoría |
| Bug real producto | No confirmado |
| Evidencia | `test_results.json` vacío, raw report `NaN of tests passed` |
| Expected | TestSprite ejecuta `GET /health`, `/openapi.json`, `/docs`, `/redoc` |
| Actual | Sin casos ejecutados |
| Root cause probable | Config TestSprite sigue `type: frontend`; `testsprite_generate_backend_test_plan` ya falló por requerir `testType=backend` |
| Archivos probables | `testsprite_tests/tmp/config.json`, `testsprite_tests/testsprite_backend_test_plan.json` |
| Tipo de fix | Rebootstrap/config backend TestSprite o runner API separado |
| Riesgo | Alto: no hay cobertura API real |
| Rerun necesario | API smoke `TCAPI001` y luego `TCAPI001–016` |
| Criterio cierre | `test_results.json` contiene `TCAPI001` PASSED/FAILED con requests reales a API pública |

## TS-CURSOR-003 — Suites E2E/Guard no son ejecutables como IDs MCP nativos

| Campo | Valor |
|---|---|
| Suite | E2E/GUARD |
| Severidad | P2 operativo de auditoría |
| Bug real producto | No |
| Evidencia | `06_E2E_PLAN.md` y `07_GUARD_PLAN.md` son planes manuales, no IDs en plan TestSprite activo |
| Expected | TestSprite puede ejecutar TE2E/TG o casos equivalentes |
| Actual | No hay IDs ejecutables para esas suites |
| Root cause probable | MCP no expone generador E2E/Guard dedicado |
| Archivos probables | `testsprite_tests/testsprite_frontend_test_plan.json`, `testsprite_tests/testsprite_backend_test_plan.json` |
| Tipo de fix | Convertir manual plans a casos TestSprite JSON o mapear a IDs existentes seguros |
| Riesgo | Medio: cobertura incompleta |
| Rerun necesario | E2E + Guard después de smoke UI/API válido |
| Criterio cierre | Resultados TestSprite separados para E2E y Guard con artifacts |

## TS-CURSOR-004 — TC024 contiene mail sync en suite UI normal

| Campo | Valor |
|---|---|
| Suite | UI/GUARD |
| Severidad | P0 riesgo de contrato si se ejecuta sin reescritura |
| Bug real producto | No confirmado |
| Evidencia | `TC024 — Sync mail in read-only mode and review classified messages` |
| Expected | Mail normal read-only: no send, no draft, no POST mutante salvo guard controlado |
| Actual | Caso planificado puede intentar sync |
| Root cause probable | Plan MCP no distingue read-only normal vs guard negative |
| Archivos probables | `testsprite_tests/testsprite_frontend_test_plan.json`, `04_UI_PLAN.md` |
| Tipo de fix | Reescribir TC024 como GET/read-only UI o moverlo a Guard con expected block |
| Riesgo | Alto si se ejecuta |
| Rerun necesario | Mail read-only UI + Guard mail |
| Criterio cierre | TestSprite prueba mail sin drafts/send/sync mutante o confirma bloqueo 4xx/409 |

## Orden recomendado para Megaprompt 3

1. Reparar harness/config TestSprite para origen público o declarar oficialmente auditoría local separada.
2. Rebootstrap backend/API TestSprite y demostrar `TCAPI001`.
3. Convertir TE2E/TG a casos ejecutables o mapearlos a IDs seguros.
4. Reescribir TC024 antes de cualquier UI full.

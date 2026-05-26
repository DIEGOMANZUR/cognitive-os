# 11 — API Results

Fecha: **2026-05-26**  
Suite objetivo: **API Contract Full**  
Estado suite: **BLOCKED**  
Herramienta: TestSprite MCP (`testsprite_generate_code_and_execute`) + comando MCP devuelto por la tool.

## Ejecución realizada

| Item | Valor |
|---|---|
| TestSprite ID solicitado | `TCAPI001` |
| Scope | Smoke público health/docs/openapi |
| `serverMode` | `production` |
| `testIds` | `["TCAPI001"]` |
| Expected | Ejecutar `GET /health`, `GET /openapi.json`, `GET /docs`, `GET /redoc` sobre `https://cognitive-api.doctormanzur.com` |
| Resultado bruto TestSprite | `test_results.json` = `[]`; raw report con `NaN of tests passed` |
| Resultado válido para PRD público | **BLOCKED** |

## Artifacts

| Artifact | Path |
|---|---|
| Terminal API smoke | `test-results/testsprite_cursor/initial/api/terminal-smoke-tcapi001.txt` |
| Raw report | `test-results/testsprite_cursor/initial/api/raw_report.md` |
| Test results | `test-results/testsprite_cursor/initial/api/test_results.json` |

## Hallazgo API-EXEC-001

| Campo | Detalle |
|---|---|
| TestSprite ID | `TCAPI001` |
| Method/path | Public endpoints: `/health`, `/openapi.json`, `/docs`, `/redoc` |
| Masked headers | n/a — public endpoints |
| Request body | n/a |
| Expected según PRD | 200 en endpoints públicos sin auth; no secret leak |
| Actual TestSprite | No ejecutó casos; `test_results.json` vacío y reporte `NaN` |
| Status | No disponible por TestSprite |
| Response body | No disponible por TestSprite |
| Latency | No disponible por TestSprite |
| Clasificación | **BLOCKED — TestSprite/config no ejecutó el caso API** |
| Severidad | **P1 operativo de auditoría**; no es bug confirmado del backend |

## Nota de disponibilidad runtime

El pre-run confirmó disponibilidad pública con checks mínimos:

- `https://cognitive-api.doctormanzur.com/health` → HTTP 200
- `https://cognitive-api.doctormanzur.com/openapi.json` → HTTP 200
- `GET /system/info` con Bearer JWT → HTTP 200
- `GET /system/info` sin auth → HTTP 401 esperado

Esos checks son preparación de runtime, **no** sustituyen TestSprite.

## Decisión MCP inicial

**STOP para API Full vía MCP.** La herramienta no ejecutó `TCAPI001`, así que correr `TCAPI002–016` por ese camino sería inválido sin resolver primero la configuración backend/TestSprite.

## Web Portal API Run

Después del bloqueo MCP, se ejecutó una corrida API pública desde TestSprite Web Portal con configuración manual de endpoints y Bearer JWT.

| Item | Valor |
|---|---|
| TestSprite project | `backend_api` |
| Report URL | `https://www.testsprite.com/dashboard/tests/36b5b87d-b80b-4d67-90c7-50fdbb131f51/report` |
| APIs probadas | 38 |
| Test cases | 158 |
| Passed | 111 |
| Failed | 22 |
| Blocked | 25 |
| Estado triage | **PARTIAL / FAIL API CONTRACT** |

Reporte local: `docs/audits/testsprite_cursor/28_WEB_PORTAL_API_RESULTS.md`

Resumen de artifact: `test-results/testsprite_cursor/web_portal_api_report_summary.md`

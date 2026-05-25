# 09 - TestSprite Initial Results

Fecha UTC: 2026-05-24

## Estado general

**Estado TestSprite inicial: PARTIAL / FAIL**

La app publica estaba disponible, pero la auditoria no puede marcar PASS porque
TestSprite encontro fallos/bloqueos en auth zero-friction, Health y cobertura API.

## Suites ejecutadas

| Suite | Ejecutada | Tests | Resultado | Artifacts |
| --- | --- | ---: | --- | --- |
| UI full audit | si | 27 planificados, 21 completados | 20 pass, 1 fail, 6 no completados | `test-results/testsprite/initial-full-audit/ui/` |
| UI selective rerun | si | 7 planificados, 7 reportados | 2 pass, 1 fail, 4 blocked | `test-results/testsprite/initial-full-audit/ui/observed_results.md` |
| API contract | si | 1 | 0 pass, 1 fail | `test-results/testsprite/initial-full-audit/api/` |
| E2E integrated | si | 6 | 4 pass, 1 fail, 1 blocked | `test-results/testsprite/initial-full-audit/e2e/` |

## Hallazgos principales

### TS-001 - Public UI auto-token / backend fetch falla bajo TestSprite

- Suite: UI/E2E
- Severidad sugerida: **P1**
- IDs TestSprite: TC007, TC017; E2E TC007
- Area: Health, Conexión/MCP status
- Artifact: `test-results/testsprite/initial-full-audit/e2e/raw_report.md`
- Resultado observado: la UI publica muestra `No se pudo activar el JWT local automatico. Detalle: Failed to fetch`; Health queda en `Verificando...`, `Sin lecturas todavia`, 0 OK/attention/failed.
- Pasos: abrir UI publica, entrar a Health, disparar verificacion live.
- Network/console: TestSprite reporta `Failed to fetch`; no se capturo trace estructurado por tool MCP.
- Probable causa: fallo del flujo publico de auto-token o bloqueo de fetch hacia backend publico; tambien TestSprite no aplico siempre el seed de `localStorage`.
- Afecta cero friccion: si.
- Afecta health honesty: si, porque Health no logra obtener lecturas live; no se observo falso verde, pero readiness queda inutilizable.
- Afecta mail contract: no directamente.
- Afecta Action Plane idempotency: no observado.
- Bug real o esperado: **probable bug real / requiere confirmacion**, porque `POST /auth/local-token` publico tambien quedo sin respuesta en probe de preparacion.

### TS-002 - API suite no pudo autenticar dentro del sandbox TestSprite

- Suite: API
- Severidad sugerida: **P2, gap de instrumentacion TestSprite**
- ID TestSprite: TC001 `test_health_dashboard_live_verification`
- Endpoint: `/health/dashboard`, `/health/verify`
- Artifact: `test-results/testsprite/initial-full-audit/api/raw_report.md`
- Resultado: fallo antes de llamar endpoint protegido: `JWT token not found` / sandbox `/var/task` no pudo leer `/tmp/cognitive_os_testsprite_jwt.txt`.
- Pasos: ejecutar backend TestSprite plan; el codigo generado intenta leer JWT desde `/tmp`.
- Probable causa: TestSprite ejecuta backend code en sandbox remoto y no hereda el filesystem local.
- Afecta cero friccion: no como bug de producto; si afecta auditabilidad.
- Afecta health honesty: no validado por API suite.
- Bug real o esperado: **no bug de Cognitive OS**; es limitacion de configuracion/auth de TestSprite MCP.

### TS-003 - Plan backend MCP cubre solo 1 caso

- Suite: API planning
- Severidad sugerida: **P2, coverage gap**
- Artifact: `test-results/testsprite/initial-full-audit/api/testsprite_backend_test_plan.json`
- Resultado: TestSprite MCP genero solo TC001 para backend, insuficiente contra `PRD_BACKEND.md`.
- Probable causa: limitacion del generador MCP o falta de tool para cargar OpenAPI/PRD backend de forma estructurada.
- Bug real o esperado: **no bug de Cognitive OS**; limita esta auditoria inicial.

### TS-004 - Mail flows quedan bloqueados/read-only, sin send/draft expuesto

- Suite: UI/E2E
- Severidad sugerida: **P3 / expected constrained state**
- IDs: TC001, TC013, TC021
- Area: Mail
- Resultado: TestSprite no pudo inspeccionar propuestas/digest porque la UI muestra `mail desactivado`, `solo lectura por defecto`, `send bloqueado`; botones de sync/digest disabled.
- Afecta mail contract: **positivo**; no se observo send/draft normal.
- Bug real o esperado: esperado durante auditoria si el estado disabled es intencional y claro.

### TS-005 - E2E parcial: jobs/approvals/audit/navigation pasan; health falla

- Suite: E2E
- Severidad sugerida: **P1 por Health; resto pass**
- IDs: TC005 pass, TC018 pass, TC020 pass, TC027 pass, TC007 fail, TC013 blocked
- Resultado: navegacion SPA, Jobs, Approvals y Audit degradado/empty pasan; Health live no devuelve lecturas; Mail propuesta bloqueada por estado disabled.
- Bug real o esperado: Health probable bug/integracion; Mail expected blocked.

## No hallazgos P0

No se observo:

- UI principal inaccesible;
- API `/health` inaccesible;
- mail send/draft normal expuesto;
- DNS write real;
- secreto de producto expuesto en respuesta de app;
- accion destructiva ejecutada;
- falso verde critico de Health.

## Limitaciones de artifacts

- TestSprite sobrescribe `testsprite_tests/tmp/test_results.json` y `raw_report.md`
  por corrida; el raw UI completo fue reemplazado por re-runs posteriores.
- Se conservaron scripts UI exportados y resumen observado en
  `test-results/testsprite/initial-full-audit/ui/observed_results.md`.
- Los raw reports API/E2E contienen placeholders propios de TestSprite; este
  documento es el reporte consolidado canonico.
- Artifacts locales fueron sanitizados para no conservar JWT completo ni API key.

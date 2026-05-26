# 17 — Repair Fix Log

## TS-CURSOR-004

### Suite
UI/GUARD

### Severidad
P0 riesgo de contrato

### Evidencia TestSprite original
`TC024` pedía “Trigger a read-only mail sync”, incompatible con el hard mail contract del PRD para flujo normal.

### Root cause confirmado
El plan generado mezcló revisión mail read-only con una acción de sync que debe estar fuera del flujo normal o probarse solo como guard.

### Archivos modificados
- `testsprite_tests/testsprite_frontend_test_plan.json`

### Fix aplicado
`TC024` fue reescrito para abrir Mail y revisar estado existente/empty/disabled sin sync, send, draft ni approve-send. Se agregó `TCMAIL001` como caso estable de regresión mail read-only.

### Por qué respeta PRD
Preserva el contrato: leer, clasificar, resumir, digest/propuestas; no drafts ni sends.

### Por qué preserva zero-friction
No añade bloqueos nuevos al producto; solo impide que la prueba ejecute una acción fuera de scope.

### Riesgos
Debe validarse con TestSprite una vez que el smoke público UI funcione.

### TestSprite rerun requerido
`TCMAIL001` o `TC024`.

### Estado
FIXED_PENDING_RERUN — blocked by unresolved public UI TestSprite harness, not by mail plan.

## TS-CURSOR-001

### Suite
UI

### Severidad
P1

### Evidencia TestSprite original
`TC001` pasó, pero el código generado navegó a `http://localhost:3001/` y escribió `test-local-admin-jwt`.

### Root cause confirmado
Config TestSprite usaba `localEndpoint` local y plan TC001 favorecía el flujo local de Settings.

### Archivos modificados
- `testsprite_tests/tmp/config.json`
- `testsprite_tests/testsprite_frontend_test_plan.json`

### Fix aplicado
Se agregó `TCPUB001` con URL pública, seed `cogos.api` público y aserción anti-localhost. El config se orientó a `https://cognitive.doctormanzur.com/` y `testIds=["TCPUB001"]`.

### Por qué respeta PRD
Mantiene la SPA en `/` y auth por localStorage; no agrega rutas server-side falsas.

### Por qué preserva zero-friction
Usa el flujo documentado de token local y API pública sin nuevas aprobaciones.

### Riesgos
TestSprite MCP puede seguir priorizando su túnel/local server internamente.

### TestSprite rerun requerido
`TCPUB001`.

### Estado
BLOCKED — rerun `TCPUB001` still generated initial navigation to `http://localhost:3001/`.

## TS-CURSOR-002

### Suite
API

### Severidad
P1

### Evidencia TestSprite original
`TCAPI001` devolvió resultados vacíos y raw report `NaN`.

### Root cause confirmado
`TCAPI001` existía en el plan backend, pero no en el plan activo frontend usado por la config MCP.

### Archivos modificados
- `testsprite_tests/testsprite_frontend_test_plan.json`

### Fix aplicado
Se agregó `TCAPI001` al plan activo como smoke API público con endpoints public `/health`, `/openapi.json`, `/docs`, `/redoc`.

### Por qué respeta PRD
Solo usa endpoints públicos definidos por `PRD_BACKEND.md`.

### Por qué preserva zero-friction
No toca producto ni auth; es un caso de auditoría.

### Riesgos
TestSprite puede generar un test frontend en vez de requests API reales.

### TestSprite rerun requerido
`TCAPI001`.

### Estado
BLOCKED — rerun `TCAPI001` timed out / did not produce a reliable new TestSprite result.

## TS-CURSOR-003

### Suite
E2E/GUARD

### Severidad
P2

### Evidencia TestSprite original
Suites E2E/Guard estaban en markdown, sin IDs ejecutables.

### Root cause confirmado
MCP no expone generador E2E/Guard separado; hacía falta materializar casos seguros en el plan activo.

### Archivos modificados
- `testsprite_tests/testsprite_frontend_test_plan.json`

### Fix aplicado
Se agregaron IDs seguros `TCPUB001`, `TCAPI001`, `TCMAIL001` como base de regresión/critical smoke.

### Por qué respeta PRD
Los casos evitan side effects y usan endpoints públicos/read-only.

### Por qué preserva zero-friction
No cambia comportamiento de producto.

### Riesgos
Cobertura E2E/Guard total aún requiere ampliar más IDs después de focales.

### TestSprite rerun requerido
`TCPUB001`, `TCAPI001`, `TCMAIL001`.

### Estado
PARTIAL — base IDs were added, but E2E/Guard critical suites remain blocked until UI/API focal smoke closes.

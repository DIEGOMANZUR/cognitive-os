# 10 — UI Results

> **Actualización 2026-05-26:** este archivo es evidencia histórica de auditoría. El flujo vigente ya no usa TopBar: la autenticación pública es por `#cogos_token` o `localStorage.cogos.token`, la API se resuelve automáticamente por host y el shell estable se valida con `<main data-cogos-active-tab="...">`. Las menciones a TopBar debajo se conservan solo como contexto histórico.

Fecha: **2026-05-26**  
Suite objetivo: **UI SPA Full**  
Estado suite: **BLOCKED**  
Herramienta: TestSprite MCP (`testsprite_generate_code_and_execute`) + comando MCP devuelto por la tool.

## Ejecución realizada

| Item | Valor |
|---|---|
| TestSprite ID solicitado | `TC001` |
| Scope | Smoke previo a suite full |
| `serverMode` | `production` |
| `testIds` | `["TC001"]` |
| Resultado bruto TestSprite | `PASSED` |
| Resultado válido para PRD público | **BLOCKED / no válido como PASS público** |

## Artifacts

| Artifact | Path |
|---|---|
| Terminal smoke | `test-results/testsprite_cursor/initial/ui/terminal-smoke-tc001.txt` |
| Código generado | `test-results/testsprite_cursor/initial/ui/TC001_Stay_signed_in_after_saving_a_local_JWT.py` |
| TestSprite video/dashboard | En raw result de TestSprite; no se pega completo en reporte público |

## Hallazgo UI-EXEC-001

| Campo | Detalle |
|---|---|
| TestSprite ID | `TC001` |
| Tab | Global shell / Conexión |
| Journey | Persistir JWT local y validar sesión conectada |
| Expected según PRD | Abrir **`https://cognitive.doctormanzur.com/`**, seed `localStorage.cogos.token=<JWT real>` y `localStorage.cogos.api=https://cognitive-api.doctormanzur.com`, recargar `/`, validar TopBar Connected |
| Actual TestSprite | Generó Playwright contra `http://localhost:3001/` y usó token literal `test-local-admin-jwt` |
| Console errors | No extraídos; ejecución no válida para origen público |
| Network requests | Código generado navega a `http://localhost:3001/`; por lo tanto no valida “no localhost fetch” desde origen público |
| Screenshot/video/trace | TestSprite generó video, no incluido por privacidad |
| Clasificación | **BLOCKED — TestSprite/config no respetó precondición pública** |
| Severidad | **P1 operativo de auditoría**; no es bug confirmado del producto |

## Impacto

La suite UI SPA Full **no puede declararse ejecutada** porque el smoke básico no validó el contrato público del PRD. Ejecutar los 40 casos después de este smoke produciría falsos positivos/falsos verdes:

- No verifica la URL pública.
- No verifica `cogos.api` público desde origen público.
- No verifica ausencia de llamadas a localhost en producción pública.
- No verifica JWT real preparado en `/tmp/cognitive_os_testsprite_cursor_jwt.txt`.

## Decisión

**STOP.** No se ejecuta UI Full hasta corregir el harness/plan TestSprite para obligar origen público o aceptar explícitamente una auditoría local separada.

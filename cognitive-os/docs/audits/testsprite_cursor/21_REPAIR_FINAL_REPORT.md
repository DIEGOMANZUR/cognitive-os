# 21 — Repair Final Report

Fecha: **2026-05-26**  
Estado: **BLOCKED**  
QA source: TestSprite MCP only.

## Resumen ejecutivo

No se confirmaron bugs funcionales de Cognitive OS en Megaprompt 2. Los hallazgos reales eran bloqueos de ejecución/harness TestSprite. En este prompt se corrigieron los planes TestSprite donde era seguro hacerlo:

- `TC024` dejó de intentar mail sync.
- Se agregó `TCPUB001` para UI pública con seed `localStorage`.
- Se agregó `TCAPI001` al plan activo para API pública.
- Se agregó `TCMAIL001` como regresión mail read-only.

El rerun focal con TestSprite confirma que la ejecución sigue **bloqueada** por comportamiento del MCP:

- TestSprite genera una navegación inicial a `http://localhost:3001/` antes de visitar la URL pública.
- Cuando se intenta `localEndpoint=https://cognitive.doctormanzur.com/`, el runner intenta comprobar `https://localhost:443/` y queda en `ECONNREFUSED`.
- El API smoke no produjo resultado confiable tras el ajuste.

## Hallazgos iniciales

| ID | Estado inicial |
|---|---|
| `TS-CURSOR-001` | UI smoke no validaba público; localhost + dummy JWT |
| `TS-CURSOR-002` | API smoke no ejecutaba; `[]`/`NaN` |
| `TS-CURSOR-003` | E2E/Guard sin IDs TestSprite ejecutables |
| `TS-CURSOR-004` | TC024 podía activar sync mail |

## Correcciones aplicadas

| ID | Corrección | Estado |
|---|---|---|
| `TS-CURSOR-004` | `TC024` reescrito como read-only; `TCMAIL001` agregado | FIXED_PENDING_RERUN |
| `TS-CURSOR-001` | `TCPUB001` agregado; config/instrucciones públicas | BLOCKED por MCP |
| `TS-CURSOR-002` | `TCAPI001` agregado al plan activo | BLOCKED por MCP/timeout |
| `TS-CURSOR-003` | Casos base ejecutables agregados | PARTIAL |

## Falsos positivos / no bugs de producto

- `TC001` PASS bruto del Megaprompt 2 fue falso verde de harness: no prueba público.
- `TCPUB001` failure actual no prueba bug de app: falla por navegación inicial a localhost impuesta por TestSprite.
- 401 sin JWT sigue siendo esperado por PRD.
- 404 en rutas internas SPA sigue siendo esperado por PRD.

## Blockers

| Blocker | Evidencia | Impacto |
|---|---|---|
| Navegación inicial MCP a localhost | `tcpub001-regenerated-code.py` contiene `await page.goto("http://localhost:3001/")` antes de público | No se puede certificar UI pública |
| Public `localEndpoint` no soportado como esperado | Terminal `tcpub001-terminal.txt` con `checkPortListening ... 443 localhost` | Runner asume túnel/local |
| API focal sin resultado confiable | `tcapi001-terminal.txt` timeout | No se puede certificar API por TestSprite |

## Archivos modificados

- `testsprite_tests/testsprite_frontend_test_plan.json`
- `testsprite_tests/tmp/config.json` (runtime ignored/generated)
- `docs/audits/testsprite_cursor/16_REPAIR_PLAN.md`
- `docs/audits/testsprite_cursor/17_REPAIR_FIX_LOG.md`
- `docs/audits/testsprite_cursor/18_TARGETED_RERUN_RESULTS.md`
- `docs/audits/testsprite_cursor/19_REGRESSION_CASES_ADDED.md`
- `docs/audits/testsprite_cursor/20_POST_REPAIR_CRITICAL_RERUN.md`

## Casos TestSprite agregados

| ID | Propósito |
|---|---|
| `TCPUB001` | Public SPA auth seed + anti-localhost |
| `TCAPI001` | Public API `/health` + docs/OpenAPI smoke |
| `TCMAIL001` | Mail UI read-only sin sync/send/draft |

## Reruns focales

| ID | Resultado |
|---|---|
| `TCPUB001` | FAILED/BLOCKED — TestSprite navega primero a localhost |
| `TCAPI001` | BLOCKED/TIMEOUT — sin resultado confiable |

## Critical rerun

No ejecutado. Ver `20_POST_REPAIR_CRITICAL_RERUN.md`.

## Estado por suite

| Suite | Estado |
|---|---|
| UI | BLOCKED |
| API | BLOCKED |
| E2E | BLOCKED |
| GUARD | BLOCKED |

## P0/P1/P2 restantes

No hay P0/P1/P2 **de producto** confirmados. Persisten P1/P2 operativos de harness TestSprite:

- `TS-CURSOR-001` BLOCKED.
- `TS-CURSOR-002` BLOCKED.
- `TS-CURSOR-003` PARTIAL/BLOCKED para suite total.

## Riesgos residuales

- Sin soporte de TestSprite para público first-class, cualquier PASS UI puede ser falso verde local.
- Sin plan API ejecutable, guards no deben ejecutarse porque podrían no respetar side-effect constraints.

## Recomendación para Megaprompt 4

No iniciar loop total todavía. Primero decidir una ruta de ejecución:

1. **Ruta A (preferida):** conseguir configuración TestSprite MCP que permita URL pública sin preflight `localhost`.
2. **Ruta B:** aceptar auditoría TestSprite local-only y crear una suite separada mínima para verificar despliegue público con TestSprite si la herramienta lo soporta.

Después, rerun focal `TCPUB001`, `TCAPI001`, `TCMAIL001`; solo si cierran, ejecutar critical rerun y luego loop total.

# 14 — Global Triage

Fecha: **2026-05-26**  
Estado global: **BLOCKED**  
Base de clasificación: PRD principal + PRD_FRONTEND + PRD_BACKEND.

## Resumen de ejecución

| Suite | TestSprite ejecutado | Resultado bruto | Resultado de triage |
|---|---:|---|---|
| UI SPA Full | 1 smoke (`TC001`) | `PASSED` | **BLOCKED**: ejecutó local/dummy, no público/JWT real |
| API Contract Full | 1 smoke (`TCAPI001`) | `[]` / `NaN` | **BLOCKED**: no ejecutó caso API |
| E2E Integrated | 0 | n/a | **BLOCKED** por precondiciones UI/API |
| Forbidden Guards | 0 | n/a | **BLOCKED** por precondición API |

## P0

No hay P0 de producto confirmado por TestSprite en esta corrida.  
No se validaron mail send/draft, DNS write ni secret leak porque la ejecución quedó bloqueada antes de guards.

## P1

| ID | Suite | Clasificación | Descripción |
|---|---|---|---|
| `TS-CURSOR-001` | UI | BLOCKED | TestSprite ignoró objetivo público y generó smoke contra `http://localhost:3001/` con token dummy |
| `TS-CURSOR-002` | API | BLOCKED | TestSprite no ejecutó `TCAPI001`; resultados vacíos y reporte `NaN` |

## P2

| ID | Suite | Clasificación | Descripción |
|---|---|---|---|
| `TS-CURSOR-003` | E2E | BLOCKED | Suite no ejecutada por smoke UI/API inválido |
| `TS-CURSOR-004` | GUARD | BLOCKED | Suite no ejecutada por smoke API inválido y riesgo de side effects |

## P3/P4

No hay P3/P4 de producto confirmado. Los gaps de plan previos permanecen:

- Hotkeys 1–9 no explícitos.
- LangSmith/Audit/Sandbox UI no cubiertos por plan generado.
- Responsive no cubierto por plan generado.
- TC024 UI contiene “sync mail” y debe reescribirse como read-only o guard-only.

## Falsos positivos

| Caso | Clasificación |
|---|---|
| `TC001` PASS bruto | **Falso verde / no válido para PRD público** porque usa localhost y token dummy |
| 401 sin JWT | Esperado, no bug |
| 404 en rutas internas SPA | Esperado, no bug |
| Placeholder localhost en Conexión antes de seed | Esperado si requests reales usan `cogos.api` |

## Blockers

| Blocker | Impacto | Próximo paso |
|---|---|---|
| TestSprite MCP devuelve comando terminal y respeta config local `localhost` | No valida UI pública | Preparar config/plan específico o aceptar auditoría local separada |
| TestSprite API smoke no ejecuta casos | No hay cobertura API real | Rebootstrap backend/config o crear plan API ejecutable por MCP |
| Suites C/D manuales no tienen IDs MCP ejecutables | No se pueden correr como suites nativas | Convertir a casos TestSprite ejecutables o mapear a IDs seguros existentes |

## Veredicto

**BLOCKED.** No hay evidencia suficiente para declarar PASS/FAIL del producto. La falla actual es de ejecución/configuración TestSprite, no un bug funcional confirmado de Cognitive OS.

## Actualización — TestSprite Web Portal API

Se ejecutó una corrida API pública desde TestSprite Web Portal después del bloqueo MCP:

| Suite | TestSprite ejecutado | Resultado bruto | Resultado de triage |
|---|---:|---|---|
| API Contract Full parcial web | 158 endpoint tests | 111 pass / 22 fail / 25 blocked | **PARTIAL / FAIL API CONTRACT** |

Hallazgos reales probables:

- Namespaces documentados devuelven 404 en público: `/actions`, `/research`, `/config`, `/assist`, `/voice`, `/deepagents`, `/knowledge`, `/document-analysis`, `/sandbox`, `/langsmith`.
- `POST /health/verify` acepta body vacío y devuelve éxito.
- `GET /threads/{thread_id}` para UUID inexistente devuelve 200 con error payload.

No se cuentan todavía como bug real los casos de insufficient-role en `/system/credentials-status`, `/system/mcp` y `/health/dashboard`, porque la corrida usó un JWT admin global; requieren rerun focal con token no-admin/expirado real.

Detalle: `docs/audits/testsprite_cursor/28_WEB_PORTAL_API_RESULTS.md`

# 20 — Post-Repair Critical Rerun

Fecha: **2026-05-26**

## Estado

**BLOCKED / NOT RUN**

## Razón

El criterio para ejecutar critical rerun era tener P0/P1/P2 con focal rerun verde o blockers cerrados. El focal `TCPUB001` sigue fallando por harness TestSprite MCP:

- Código generado navega primero a `http://localhost:3001/`.
- La propia prueba falla por esa navegación, que contradice el contrato público del PRD.

El focal `TCAPI001` no generó resultado TestSprite nuevo confiable.

## Critical suites no ejecutadas

| Suite | Estado | Razón |
|---|---|---|
| UI Critical | BLOCKED | UI public smoke no cerrado |
| API Critical | BLOCKED | API smoke no cerrado |
| E2E Critical | BLOCKED | Depende de UI/API smoke |
| Guard Critical | BLOCKED | Depende de API/guard harness seguro |

## Próxima condición de desbloqueo

Antes del critical rerun se necesita una de estas dos rutas:

1. TestSprite MCP con soporte first-class para URL pública sin navegación inicial a `localEndpoint`.
2. Declarar oficialmente que la auditoría TestSprite será local-only y cambiar el PRD/blueprint de ejecución para aceptar `localhost` como target, manteniendo un caso separado para verificar producción pública.

No se recomienda correr critical rerun mientras `TCPUB001` falle por `localhost`.

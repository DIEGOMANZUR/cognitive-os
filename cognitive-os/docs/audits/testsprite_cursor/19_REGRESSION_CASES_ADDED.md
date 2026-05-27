# 19 — Regression Cases Added

> **Actualización 2026-05-26:** este archivo es evidencia histórica de auditoría. El flujo vigente ya no usa TopBar: la autenticación pública es por `#cogos_token` o `localStorage.cogos.token`, la API se resuelve automáticamente por host y el shell estable se valida con `<main data-cogos-active-tab="...">`. Las menciones a TopBar debajo se conservan solo como contexto histórico.

Fecha: **2026-05-26**

## Summary

Se agregaron/ajustaron casos en `testsprite_tests/testsprite_frontend_test_plan.json`. No son tests de producto; son casos TestSprite MCP para cerrar los blockers de ejecución.

## TCPUB001

| Campo | Valor |
|---|---|
| Suite | UI / E2E smoke |
| Bug cubierto | `TS-CURSOR-001` — falso verde por localhost/dummy JWT |
| Pasos | Navegar a público, obtener token por `POST /auth/local-token`, seed `localStorage`, recargar `/`, verificar Connected, rechazar localhost |
| Expected | No `localhost`/`127.0.0.1`, TopBar Connected, API pública configurada |
| Artifact | `test-results/testsprite_cursor/repair/focal/tcpub001-regenerated-results.json` |
| Estado | Ejecutable, pero BLOCKED por pre-navegación local impuesta por MCP |

## TCAPI001

| Campo | Valor |
|---|---|
| Suite | API smoke |
| Bug cubierto | `TS-CURSOR-002` — ID API ausente del plan activo |
| Pasos | GET público `/health`, `/openapi.json`, `/docs`, `/redoc` |
| Expected | 200, OpenAPI válido, sin secretos credential-shaped |
| Artifact | `test-results/testsprite_cursor/repair/focal/tcapi001-terminal.txt` |
| Estado | Agregado, pero rerun no produjo resultado confiable |

## TCMAIL001

| Campo | Valor |
|---|---|
| Suite | UI / Guard mail read-only |
| Bug cubierto | `TS-CURSOR-004` — TC024 pedía sync |
| Pasos | Abrir Mail autenticado, no activar sync/send/draft/approve-send, verificar estado read-only/empty/disabled |
| Expected | Mail normal read-only, sin side effects |
| Artifact | Pendiente de rerun tras resolver blocker UI público |
| Estado | Added, pending rerun |

## TC024 adjusted

| Campo | Valor |
|---|---|
| Suite | UI Mail |
| Cambio | Removido paso “Trigger read-only mail sync”; ahora solo revisa estado read-only |
| Expected | No sync/send/draft/approve-send |
| Estado | FIXED_PENDING_RERUN |

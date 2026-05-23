# Modelo Operativo Sin Friccion — PC Dedicado

Este documento define la postura actual del proyecto para el PC dedicado de
Diego. Es intencionalmente distinta de una postura SaaS/multiusuario.

> **Estado (2026-05-23, commit `647f103`):** la auditoria comercial
> (`docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md`) evaluo el sistema
> contra los 9 criterios de "grado comercial" definidos aqui abajo y
> cerro las 8 fallas accionables (AUDIT-2026-A..H). Los 9 criterios se
> cumplen. Una **doble re-auditoria TestSprite del 2026-05-23** valido
> los 16 hallazgos previos (15 VERIFIED_FIXED + 1 OBSOLETE_WITH_REASON)
> y cazo un P1 nuevo (`MissingGreenlet` en
> `POST /actions/*/preview/request`) que ya quedo corregido con
> `eager_defaults=True` en `db.Base` + 3 tests de regresion. Detalle
> completo en `docs/audits/testsprite/16_FINAL_REAUDIT_REPORT.md`. Para
> el snapshot vigente de conteos y gates ver
> [`CURRENT_STATE.md`](CURRENT_STATE.md).
>
> **Ajustes runtime acumulados:**
> - `647f103` (re-audit): `eager_defaults=True` en ORM Base; Playwright
>   auto-mintea JWT en `dedicated_local/full` via `_global-setup.ts`.
>   Gates: `full-qa.sh` 950 passed, Playwright 31/31 sin exportar
>   `COGOS_JWT`, TestSprite re-audit 10/10.
> - `5953b40`: MCP inventario paralelo, timeout default 30s, runtime
>   verificado 5/5 servers / 67 tools; atajo `Ctrl/Cmd+K` del cockpit
>   estabilizado.

## Decision De Producto

La prioridad actual es **eliminar friccion operativa**, incluso si eso reduce la
seguridad estricta. Cognitive OS corre en un PC dedicado, con credenciales y
sesiones reales del operador, y debe actuar como un sistema personal amplio,
trazable y recuperable.

En terminos practicos:

- El agente puede usar el perfil real de Edge mediante Kimi WebBridge.
- El agente puede operar ampliamente dentro del PC dedicado.
- El agente puede navegar, leer, organizar y preparar acciones sin pedir
  confirmaciones redundantes cuando el perfil es `dedicated_local`.
- El control principal no es "preguntar por todo"; es **dejar evidencia,
  diagnosticar rapido, evitar duplicados, poder reintentar y fallar visible**.

## Perfil Recomendado

```env
OPERATOR_PROFILE=dedicated_local
LOCAL_AUTONOMY_MODE=full
CODE_DIRECTOR_BUDGET_MODE=soft
MAIL_BACKGROUND_SYNC_ENABLED=false
MAIL_ALLOW_EXPLICIT_SEND=false
```

Este perfil asume:

- Un solo operador humano.
- Backend y servicios ligados a `127.0.0.1`.
- Sin exposicion directa a internet.
- Sesiones del navegador pertenecen a Diego.
- Los riesgos de operar en el PC son aceptados para ganar velocidad.

## Controles Que Siguen Importando

Aunque la seguridad no sea la prioridad principal, estos controles no son
negociables porque reducen fallos reales sin meter friccion innecesaria:

- `AuditEvent`, `JobEvent`, `ActionRequest` y logs utiles para saber que paso.
- Idempotencia en dispatch y requests para no duplicar trabajos.
- Reapers para jobs/approvals/action requests colgados, **con contadores
  visibles**: el componente `operational_backlog` de `/health/dashboard` se
  pone `degraded` cuando un reaper deberia haber limpiado una fila y no lo hizo.
- Timeouts y errores visibles al operador.
- Health/readiness honesto: `/health/dashboard` distingue `verified` de
  `configured` (cableado pero sin llamada real) y no pinta `ok` lo que nunca
  se probo; `POST /health/verify` fuerza el probe real bajo demanda.
- MCP diagnosticable: `/system/mcp` habla con cada server, reporta
  `connected/tools_count/error`, carga inventario en paralelo y usa
  `MCP_INVENTORY_TIMEOUT_SECONDS=30` por defecto para evitar falsos timeouts
  al arrancar varios servidores `stdio`.
- Tests hermeticos que no toquen produccion + carril opt-in `tests/live/`
  (`LIVE_TESTS_ENABLED=1`) para smokes read-only contra proveedores reales.
- Auth fail-closed donde la falla es silenciosa: el dispatch de Telegram
  rechaza por defecto si la allowlist esta vacia.
- `.env`, tokens y secretos fuera de git.
- Build frontend aislado en `.next-qa` durante QA para no romper el panel vivo.

## Excepcion Dura: Mail

Mail no sigue la regla de "hacerlo todo solo".

El contrato vigente es:

- El agente lee y clasifica correos.
- El agente genera resumen.
- El agente propone respuestas como texto.
- Diego decide si copia y envia.
- El sistema **no crea drafts**.
- El sistema **no envia correos automaticamente**.
- Solo puede enviar si Diego lo pide explicitamente y ademas se habilitan los
  flags de escape hatch.

Razon: enviar un correo no es solo una accion tecnica; es comunicacion humana
externa. El flujo normal debe asistir, no sustituir, la decision de Diego.

## Que Significa "Grado Comercial" En Este PC

Para este proyecto, en esta etapa, "grado comercial" significa los 9 criterios
siguientes (todos verificados tras la remediacion AUDIT-2026-A..H):

- Arranque reproducible.
- Stack local diagnosticable.
- Jobs no se pierden silenciosamente.
- UI no miente sobre lo que hace.
- Mail cumple el contrato de lectura/propuesta.
- Frontend no queda deshidratado despues de QA.
- Tests, build, lint, mypy, Alembic y E2E verdes.
- Fallos de credenciales/proveedores quedan visibles.
- El operador no tiene que adivinar que esta mal.

No significa:

- Aislamiento multi-tenant.
- Resistencia adversarial.
- Hardening para internet publico.
- Friccion de aprobacion maxima.
- Navegador sin perfil real.

## Si Algun Dia Cambia El Contexto

Si Cognitive OS deja de correr solo en este PC dedicado, hay que cambiar de
postura antes de operar:

1. `OPERATOR_PROFILE=strict`.
2. `LOCAL_AUTONOMY_MODE=guarded` o equivalente.
3. `KIMI_WEBBRIDGE_REQUIRE_APPROVAL=true`.
4. Allow-lists explicitas para browser/computer/MCP.
5. `REQUIRE_HUMAN_APPROVAL_FOR_EXTERNAL_ACTIONS=true`.
6. Re-auditoria de Telegram, auth, RBAC y secretos.
7. E2E + smoke live de proveedores en entorno separado.

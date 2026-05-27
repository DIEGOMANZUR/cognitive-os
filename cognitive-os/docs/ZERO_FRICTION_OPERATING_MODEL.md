# Modelo Operativo Sin Friccion — PC Dedicado

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-27, Prompt 7):** esta rama `codex/commercial-zero-friction-hardening` en base `8a33475d0502` queda sincronizada para el cierre comercial local-first. La evidencia viva se concentra en `/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/tmp/v2_07_absolute_release_closure_20260527_050231`. Estado de producto verificado durante Prompt 7: backend FastAPI local, frontend Next.js, Docker services, Postgres, Redis, Weaviate, Neo4j, Alembic head, worker, beat, health/readiness, LangGraph/chat, DeepAgents, MCP, RAG/documentos, Document Analysis, Action Plane sandbox, mail read-only, Telegram, Google read-only, GoDaddy dry-run, Kimi WebBridge y Code Director toy/guard rails.
>
> **Gates V2.0 ejecutados antes de los dos ciclos verdes finales:** `bash scripts/full-qa.sh` **1221 passed, 1 skipped, 28 deselected**; `bash scripts/stress-qa.sh 5` **5/5 verde x 1221 passed**; `cd frontend && npx playwright test` **44 passed**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/sync_doc_counts.py --check` OK; `bash scripts/verify_desktop_launchers.sh` OK; OpenAPI read-only smoke **70 GET / 0 failures**; security read-only scan sin secretos críticos; CDP/Playwright forense **10 ciclos x 20 vistas** sin console/page errors ni 5xx, con un aborto `POST /auth/local-token` adjudicado como cierre de contexto del harness y no defecto de producto; Lighthouse local: accessibility 96, best-practices 100, SEO 100.
>
> **Criterio de verdad:** no se declara envio de correo, draft real ni escritura DNS. Mail queda normalizado como read-only: sync/list/classify/digest/proposed replies como texto, sin drafts ni sends. GoDaddy queda preview/dry-run; Action Plane mantiene sandbox/approval/audit/idempotencia segun riesgo. El tunnel publico `cognitive.doctormanzur.com` se valida con `scripts/testsprite_web/deploy_and_verify.sh` cuando Diego vaya a correr TestSprite web; Prompt 7 no lo expone permanentemente porque su propia regla prohibe exponer servicios a internet.

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


Este documento define la postura actual del proyecto para el PC dedicado de
Diego. Es intencionalmente distinta de una postura SaaS/multiusuario.

> **Estado (2026-05-26, HEAD `8a33475`):** **COMERCIAL LOCAL-FIRST APROBADO +
> frontend/TestSprite web hardening**. El cierre local-first 2026-05-25 sigue
> vigente y la capa pública actual agrega hash auth `#cogos_token`, API pública
> automática, TopBar retirado, shell con `data-cogos-active-tab`, hotkey `3
> DeepAgents`, estados comerciales sin datos falsos y SW
> `cogos-v2026-05-26e-status-cards`. Handoff TestSprite web:
> `bash scripts/testsprite_web/deploy_and_verify.sh`.
>
> **Validación cero-fricción en pasada de cierre:** 30/30 PASS
> (`audits/testsprite/25_ZERO_FRICTION_RELEASE_VALIDATION.md`). El
> sistema no introdujo ninguna restricción SaaS innecesaria; ningún
> control fue debilitado en mail/Telegram/Action Plane/idempotencia.
>
> **Ajustes runtime acumulados (resumen, ver CURRENT_STATE para detalle):**
> - `8a33475`: cockpit público/TestSprite web endurecido sin fricción extra:
>   hash auth, API por host, estados comerciales y deploy/verificación en un
>   comando.
> - `bbaaea8`: cierre absoluto release audit; docs alineados a 950 tests
>   backend, 31 Playwright sin exportar JWT, 8 live read-only, TestSprite
>   acumulado 15 TC ejecutados.
> - `9ab77a4`: `HEALTH_LLM_PROBE_TIMEOUT_SECONDS=10` específico para LLM
>   probes (elimina falsos `degraded` cold-start); race guard en
>   `full-qa.sh` vs Playwright concurrente; anti-flake Ctrl+K.
> - `647f103`: `eager_defaults=True` en ORM Base; Playwright auto-mintea
>   JWT en `dedicated_local/full` via `_global-setup.ts`.
> - `5953b40`: MCP inventario paralelo, timeout default 30s, runtime
>   verificado inicialmente 5/5 servers / 67 tools; atajo `Ctrl/Cmd+K`
>   capture phase.
> - `2026-05-25`: MCP local `time` agregado como server `stdio` propio del
>   backend. Runtime actual: 6/6 servers / 69 tools; `time` no usa auth,
>   secretos, red externa ni writes.

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
  al arrancar varios servidores `stdio`. El server local `time` agrega
  conversiones horarias confiables para `America/Santiago` y otros timezones
  sin introducir credenciales ni permisos de escritura.
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

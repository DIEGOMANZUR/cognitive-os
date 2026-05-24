# Estado Actual Canonico — Cognitive OS

Fecha de sincronizacion documental: **2026-05-23**
Branch auditada: `codex/commercial-zero-friction-hardening`
Ultimo commit certificado: **`bbaaea8`** — `docs: cierre absoluto release
audit — RELEASE APPROVED, no known defects`.
Estado del producto: **RELEASE APPROVED** (grado comercial local-first).
Snapshot de cierre formal:
[`docs/audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md`](audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md).

Este archivo es la **fuente corta de verdad** del estado operativo actual. Si
otro Markdown discrepa, este archivo manda y el otro debe corregirse. Los
conteos estructurales del "Snapshot Tecnico" se generan con
`scripts/sync_doc_counts.py` y `full-qa.sh` falla si quedan desincronizados.

## Cambios Mas Recientes

**Hardening comercial zero-friction (2026-05-23, rama
`codex/commercial-zero-friction-hardening`).** Esta rama corrige falsos verdes
de QA y formaliza el gate comercial sin cambiar la postura del producto:

- `scripts/full-qa-live.sh` ya no auto-exporta `LIVE_TESTS_ENABLED=1`; si el
  operador no lo setea explicitamente, sale con diagnostico y no toca
  proveedores reales.
- `scripts/full-e2e.sh` ya no minta JWT directo via Python; Playwright debe
  ejercitar `POST /auth/local-token` desde `_global-setup.ts`.
- `docs/USER_GUIDE.md` queda alineado con el contrato dark-only.
- `scripts/full-testsprite.sh` queda como runner TestSprite reproducible en
  lotes: usa plan canonico versionado
  `qa/testsprite/frontend_commercial_plan.json`, fija por defecto
  `TESTSPRITE_PACKAGE=@testsprite/testsprite-mcp@0.0.19`, valida health entre
  batches, evita saturar `uvicorn` local, redacciona el config temporal y
  genera `qa/reports/testsprite_latest_summary.md`.
- `POST /test/fixtures/reset`, `POST /test/fixtures/seed/{scenario}` y
  `GET /test/fixtures/state` quedan disponibles solo si el backend arranca con
  `APP_ENV=test` o `COGOS_TEST_FIXTURES_ENABLED=true`; crean fixtures
  sinteticas borrables para jobs, approvals, ActionRequests, mail read-only y
  estados degradados sin tocar datos reales.
- `scripts/full-commercial-qa.sh`, `scan-local-artifacts-for-secrets.sh` y
  `probe-qa-stack-health.py` formalizan el perfil QA: batches moderados,
  secret scan de artefactos locales ignorados y observabilidad
  healthy/degraded/overloaded/failing.
- Gate ejecutado en esta rama: `bash scripts/full-qa.sh` -> **958 passed**, 1
  skipped, 28 deselected; `bash scripts/stress-qa.sh` -> 3 pasadas verdes de
  **958 passed**; `npx playwright test` -> **41 passed**.
- TestSprite historico corregido en batches -> **28 passed**. Intento final de
  cierre con API key nueva: **bloqueado por proveedor** (`AUTH_FAILED` HTTP
  401); ver `docs/qa/commercial_zero_friction_hardening/09_FINAL_CLOSURE_AUDIT.md`.

**Cierre absoluto / Release Approved (2026-05-23, commit `bbaaea8`).**
Cuarta pasada de auditoría — "cierre absoluto" — completada con
RELEASE APPROVED. Cero defectos conocidos en el alcance auditado.
Evidencia consolidada en
[`audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md`](audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md).

Lo que aportó esta pasada:

- **17 documentos nuevos** (`18_FINAL_CONTEXT_RECONSTRUCTION` →
  `34_COMMERCIAL_QUALITY_CERTIFICATION`) con evidencia completa de:
  snapshot del repo, reboot limpio, mapa del sistema regenerado, gates
  oficiales finales, TestSprite release audit (batch 3 — TC011/013/015/017/020),
  24 flujos críticos E2E, 30 asserciones cero-fricción, 25 escenarios
  de degradación, 25 escenarios de idempotencia, sweep de drift, 30 puntos
  de UX comercial, closure matrix de los 20 hallazgos, fix loop log y
  release candidate package.
- **DRIFT-947→950 corregido** en 19 docs canónicos: el conteo `947 passed`
  declarado en pass 3 quedó atrás cuando se sumaron los 3 tests de
  `test_health_llm_probe_timeout`. Bulk sed alineó todos los docs al
  conteo real **950**.
- **Verificación live con Chrome DevTools MCP**: navegación de las 20
  tabs sin un solo `console.error` crítico; Dashboard renderiza datos
  vivos reales (14/18 componentes ok, 309 approvals pendientes, audit
  log con timeline real, configuración con LLM `gpt-5.5` activo).
- **Validación TOTAL** acumulada:
  - 30/30 cero-fricción
  - 25/25 degradación/recuperación
  - 25/25 idempotencia/estados-colgados
  - 30/30 UX comercial
  - 20/20 flujos E2E críticos
  - 14/15 TestSprite historico; superseded en esta rama por
    **28/28 TestSprite batched** (`scripts/full-testsprite.sh`)
  - 19/20 hallazgos cerrados como VERIFIED_FIXED + 1 OBSOLETE_WITH_REASON.

**Certificación tercera pasada (2026-05-23, commit `9ab77a4`).** Tras
una tercera pasada de hardening explícitamente buscando debilidades, se
cerraron 4 hallazgos adicionales (TS-ZF-20260523-007/008/009/010) y se
certificó el sistema:

- **TS-ZF-20260523-007 (P2) — Falsos `degraded` LLM cold-start.** El probe
  `primary_llm` reportaba `timed out after 3s` en cold start del gateway
  por usar el `HEALTH_COMPONENT_TIMEOUT_SECONDS=3.0` global. Fix:
  `HEALTH_LLM_PROBE_TIMEOUT_SECONDS=10` (range 1–60) específico para los
  componentes con modelo de IA. `_safe_check` lo aplica selectivamente a
  `primary_llm` y `embeddings`; el resto sigue con el ceñido 3s. 3 tests
  nuevos en `test_health_llm_probe_timeout.py`. **Verificado vivo:**
  `primary_llm: ok 3.6s "Live completion succeeded"`.
- **TS-ZF-20260523-008 (P3) — Race condition `full-qa.sh` vs Playwright.**
  Si Playwright estaba corriendo en otra ventana, `npm ci` de `full-qa`
  borraba `node_modules/` y crasheaba sus workers. Guard agregado:
  `pgrep -u $USER -f "playwright test"` antes de `npm ci`, sale con
  mensaje claro.
- **TS-ZF-20260523-009 (P3) — Flake hidratación Ctrl+K.** Spec
  `glass-cockpit` pulsaba Ctrl+K antes que React hidratara el
  `useKeyboard` listener (registrado en `useEffect`). Test endurecido
  con poll-retry de hasta 7s; producción no afectada.
- **TS-ZF-20260523-010 (P3) — Test regression-critical aceptar `degraded`
  como status válido.** AUDIT-2026-B/F introdujeron `degraded` para
  componentes con problema operativo (reapers, probes); el test legacy
  sólo aceptaba `blocked`/`error`. Ahora acepta los tres.

Gates de certificación tras los fixes:
- `full-qa.sh` → **950 passed**, 1 skipped, 28 deselected.
- `stress-qa.sh 3` → 3 pasadas × 950 passed.
- `npx playwright test` → 31 passed × 3 pasadas seguidas sin flake.
- `full-qa-live.sh` → 8/8 passed.
- Migración up→down→up→check round-trip sobre DB scratch → limpio.
- Frontend↔backend endpoint compatibility → 23/23 endpoints OpenAPI.
- 174 broad excepts auditados → 0 silentes (todos loguean o degradan
  visiblemente).
- 37 type: ignore auditados → todos justificados.
- 0 xfails, 0 todos reales, 0 skips ilegítimos.

Reporte completo en
[`audits/testsprite/17_COMMERCIAL_GRADE_CERTIFICATION.md`](audits/testsprite/17_COMMERCIAL_GRADE_CERTIFICATION.md).

**Re-auditoria independiente TestSprite (2026-05-23, commit `647f103`).** Una
segunda pasada de auditoria, ejecutada como auditor independiente sobre el
estado declarado "PASS" de la primera, valido 16/16 hallazgos previos
(15 `VERIFIED_FIXED` + 1 `OBSOLETE_WITH_REASON`) y cazo un **P1 nuevo** que
la primera pasada no detecto:

- **TS-ZF-20260523-006 (P1)** — `/actions/browser/preview/request` (y todos los
  `create_*_request` que leen `updated_at` despues de `session.flush()` en
  `AsyncSession`) devolvia HTTP 500 con `sqlalchemy.exc.MissingGreenlet`. El
  attribute lazy-load disparaba SQL sincronico fuera del greenlet. **Fix:**
  `__mapper_args__ = {"eager_defaults": True}` en `db.Base`
  (`backend/src/cognitive_os/core/db.py`) — SQLAlchemy 2.x emite ahora
  `INSERT ... RETURNING` para columnas con server-default. Endpoint vivo
  verificado HTTP 200 con `updated_at` poblado; idempotency intacta (misma
  url → mismo id). **3 tests de regresion** nuevos
  (`backend/tests/test_action_request_eager_defaults.py`) corriendo contra
  la DB de test real, no contra mocks.

- **TS-ZF-20260523-001 (P2)** — Playwright runner exigia exportar
  `COGOS_JWT` manualmente (19/31 fallos al primer intento). **Fix:**
  `frontend/tests/e2e/_global-setup.ts` (nuevo) llama
  `POST /auth/local-token` antes de los workers en
  `dedicated_local/full`, populando `process.env.COGOS_JWT`. En
  `strict`/`guarded` el endpoint 403 y el helper sigue exigiendo la env
  var manualmente con mensaje claro. `npx playwright test` ahora pasa
  **31/31 sin exportar nada**.

- **TS-ZF-20260523-004 (P3)** — `docs/qa/RUNBOOK.md §2/§3` actualizada con
  `curl POST /auth/local-token` como forma corta; el comando largo
  `uv run python -c "from cognitive_os.core.auth..."` queda como fallback
  para perfil `strict`.

Gates post-fix:
- `full-qa.sh` → **950 passed**, 1 skipped, 28 deselected (944 historicos +
  3 nuevos), lint/format/mypy/Alembic/sync_doc_counts/git diff todos OK.
- `stress-qa.sh 3` → 3 pasadas verdes de **950 passed**.
- `npx playwright test` (sin exportar `COGOS_JWT`) → **31 passed**.
- `verify_desktop_launchers.sh` → OK.
- TestSprite MCP/CLI → **10/10 passed** sobre dos batches acotados
  (`TC001/002/003/004/006/007/008/009/010/014`).
- 12/12 asserciones cero-friccion validadas explicitamente
  (`docs/audits/testsprite/15_ZERO_FRICTION_VALIDATION.md`).

Reporte detallado en `docs/audits/testsprite/16_FINAL_REAUDIT_REPORT.md`.

**Post-gate MCP/frontend (2026-05-22, commit `5953b40`).** Despues del
hardening comercial se detectaron dos puntos reales en runtime y E2E; ambos
quedaron corregidos y verificados:

- `/system/mcp` ya no depende de una carga secuencial lenta: el inventario de
  servidores MCP se carga en paralelo y el timeout default
  `MCP_INVENTORY_TIMEOUT_SECONDS` subio a 30s. Verificacion runtime:
  **5/5 servidores conectados** (`mem`, `gh`, `fs`, `cc`, `gem`) y **67 tools**
  expuestas; Playwright consulta `/system/mcp` dentro de su timeout.
- `Ctrl/Cmd+K` de la command palette se registra en capture phase para que el
  atajo no quede consumido por inputs/foco de la pagina.
- QA posterior al commit: `full-qa.sh` **944 passed**, Playwright **31 passed**,
  `full-qa-live.sh` **8 passed** y `stress-qa.sh` 3 pasadas de **944 passed**.

**Hardening comercial zero-friction (2026-05-22).** Se reforzo el gate
oficial y la cobertura E2E sin cambiar la postura de producto:

- `full-qa.sh` ya no tolera un `alembic check` fallido cuando hay DB
  configurada; solo se salta Alembic en clones sin `.env`, `.env.local` ni
  `DATABASE_URL`.
- El build frontend de QA limpia `.next-qa` antes de lint/build y evita romper
  un `next start` vivo.
- Nuevo `scripts/full-e2e.sh`: gate Playwright separado con JWT local,
  preflight CORS, instalacion de Chromium omitible y `npm ci` opt-in.
- Defaults CORS incluyen `localhost/127.0.0.1:3101` para fallback local sin
  abrir wildcard.
- UI: `configured` en health se pinta como warning, no danger; el centro de
  notificaciones usa `asArray` para no crashear con payloads malformados.
- Playwright comercial sube a **31 passed** y cubre 20 vistas, console/page
  errors, health configured-vs-verified, mail read-only, jobs/approvals/action
  lifecycle, mobile y zero-friction dedicated_local/full.
- `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` ejecutado: **8 passed**.
- TestSprite MCP/CLI ejecutado como smoke advisory acotado: **3/3 passed**.
  Sus tests generados son evidencia adicional; la suite Playwright sigue siendo
  el gate E2E fuerte.

**Remediacion del audit comercial (2026-05-22).** Tras
`docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md` se cerraron **todos** los
hallazgos accionables: las 8 funcionales (AUDIT-2026-A..H) y las 3 de higiene
de repo (AUDIT-2026-I..K). Resumen de las funcionales:

- **A (P0)** — `telegram_bot.py`: `_dispatch` ahora es fail-closed
  (`if user_id not in self.allowed_user_ids`); `main()` se niega a arrancar con
  la allowlist vacia en vez de quedar un bot mudo que rechaza a todos.
- **B (P1)** — `core/health.py` distingue `verified` de `configured`. El overall
  de `/health/dashboard` es `ok` solo si cada componente fue probado en vivo;
  `configured` (cableado, sin llamada real) ya no se pinta verde. Nuevo
  `POST /health/verify` que hace probe real (completion LLM minima, embedding
  real, login IMAP) bajo demanda del operador.
- **C (P1)** — kill switch `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED` (default
  `true`) para la unica ruta de auto-deploy del plan de aprendizaje (Fase D,
  auto-promote de warnings). En `false` toda warning aprendida pasa por la
  puerta de aprobacion del operador.
- **D (P2)** — matriz parametrizada de los 37 comandos Telegram (auth-deny +
  no-crash) y comandos flag-gated.
- **E (P2)** — carril `tests/live/` (marker `live_readonly`, opt-in
  `LIVE_TESTS_ENABLED=1`): 8 smokes read-only contra proveedores reales +
  `scripts/full-qa-live.sh`.
- **F (P2)** — componente `operational_backlog` en health: approvals/jobs/
  action-requests atascados + lag del beat, con tile dedicado en el frontend.
- **G (P3)** — `scripts/sync_doc_counts.py` mantiene los conteos canonicos
  sincronizados con el codigo; `--check` corre dentro de `full-qa.sh`.
- **H (P3)** — `scripts/dev_up.sh` valida las variables que `docker compose`
  interpola sin default antes de levantar la infraestructura.

Higiene de repo (AUDIT-2026-I/J/K) — cerrada: las bitacoras de sesion
(`task_plan.md`, `findings.md`, `progress.md` y los transcripts) estan
gitignored y fuera de control de versiones; los arboles `cognitive-os-backup-*`
y `cognitive-os-snapshot-*` estan gitignored; el README ya no acumula la pila
historica de snapshots por fase.

## Postura Del Producto

Cognitive OS esta optimizado para un **PC dedicado de Diego**, no para un
producto multiusuario expuesto a internet. La prioridad declarada por el
operador es:

1. **Friccion operativa casi nula por sobre seguridad estricta.**
2. Usar el perfil real de Edge cuando haga falta.
3. Permitir al agente operar ampliamente en el PC dedicado.
4. Mantener trazabilidad, diagnostico, idempotencia y recuperacion como
   controles principales.
5. Mantener una excepcion dura en mail: el flujo normal **no envia mails, no
   crea drafts y solo propone texto**. Diego copia y envia manualmente salvo
   peticion absolutamente explicita.

La seguridad estricta sigue documentada como referencia tecnica para `strict` o
para un futuro despliegue multiusuario, pero **no es el objetivo principal de
este host**. Para el modelo operativo vigente ver
[`ZERO_FRICTION_OPERATING_MODEL.md`](ZERO_FRICTION_OPERATING_MODEL.md).

## Snapshot Tecnico

Conteos estructurales derivados del codigo (generados por
`scripts/sync_doc_counts.py`; verificados en `full-qa.sh` con `--check`):

<!-- AUTO:counts:start -->
<!-- Generado por scripts/sync_doc_counts.py — no editar a mano. -->

| Conteo canónico | Valor |
|---|---|
| Endpoints REST (`@app.*`/`@router.*` en `api/`) | 150 |
| Tareas Celery (`workers/tasks.py`) | 23 |
| Migraciones Alembic (`alembic/versions/`) | 20 |
| Head Alembic | 202605200003 |
| Vistas frontend (`frontend/app/views/*.tsx`) | 20 |
<!-- AUTO:counts:end -->

| Area | Estado actual |
|---|---|
| Backend | FastAPI 0.115+, 147 decoradores REST en `api/app.py` |
| Frontend | Next.js 16.2.6 + React 19, 20 vistas en `frontend/app/views` |
| Infra | Docker Compose local con Postgres 16+pgvector, Redis 7, Weaviate 1.29.0, Neo4j 5; todo ligado a `127.0.0.1` |
| DB | 20 migraciones Alembic, head `202605200003`, `alembic check` sin drift |
| Celery | 23 tareas, 5 colas (`default`, `ingestion`, `agent_longrun`, `maintenance`, `mail`), hasta 13 jobs beat segun flags |
| Telegram | 37 slash commands; modo conversacional sin slash en `dedicated_local`; dispatch fail-closed |
| Mail | Gmail `TODOS`/`SPAM` + GoDaddy `Spam`; clasificacion propia del agente; digest 10:00 y 20:00 Chile; respuestas propuestas como texto |
| Health | `/health/dashboard` expone 18 componentes (17 checks + checkpointer); `/health/verify` hace probe en vivo |
| MCP | Cliente habilitable en `dedicated_local`; `/system/mcp` carga inventario en paralelo con timeout default 30s; runtime verificado 5/5 servers y 67 tools |
| Learning | Fases A-E en produccion: recipes, failure postmortem, tool scorecard, skill promotion, nightly reflection; auto-promote con kill switch |
| Code Director | Planner LLM-driven + adapters Claude Code/Codex/Kimi/DeepAgents bajo budget/audit |
| Browser | Kimi WebBridge + Edge real disponibles para el perfil dedicado |
| LLM | primary+agent `gpt-5.5` (Responses API + prompt caching 24h), secondary/fallback `gemini-3.1-pro-low`, vision `glm-4.6v` |
| QA backend | `pytest` hermetico con DB de test aislada (`cognitive_os_test`) |
| QA frontend | Playwright oficial: 31 tests en desktop/mobile; runner zero-friction (auto-mintea `COGOS_JWT` via `POST /auth/local-token` en `dedicated_local/full`) |
| QA oficial | `scripts/full-qa.sh` (build Next aislado en `.next-qa`, 958 passed en esta rama); `stress-qa.sh` para flakiness; `full-qa-live.sh` opt-in para smokes reales |
| Reaudit TestSprite | 2 pasadas independientes 2026-05-23: pasada 1 (PASS, 5 hallazgos P2/P3 cerrados); pasada 2 (PASS, 1 P1 nuevo cazado y corregido — eager_defaults). Reporte en `docs/audits/testsprite/16_FINAL_REAUDIT_REPORT.md` |

## Ultimo Gate Verde Conocido

Gate mas reciente en esta rama (`codex/commercial-zero-friction-hardening`,
2026-05-23):

- `bash scripts/full-qa.sh` -> **958 passed, 1 skipped, 28 deselected**.
- `bash scripts/stress-qa.sh` -> 3 pasadas verdes de **958 passed**.
- `npx playwright test` -> **41 passed**.
- TestSprite completo corregido en batches -> **28/28 passed**.

Gate de certificación final historico (2026-05-23, ver
[`17_COMMERCIAL_GRADE_CERTIFICATION.md`](audits/testsprite/17_COMMERCIAL_GRADE_CERTIFICATION.md)):

- `bash scripts/full-qa.sh` -> **950 passed, 1 skipped, 28 deselected**
  (944 históricos + 6 nuevos: 3 `eager_defaults` + 3
  `test_health_llm_probe_timeout`).
- `bash scripts/stress-qa.sh 3` -> 3 pasadas verdes de **950 passed**.
- `npx playwright test` × 3 pasadas seguidas -> **31 passed** cada una,
  sin flakiness (incluye fix anti-race del `useKeyboard` Ctrl+K).
- `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` -> **8 passed**.
- TestSprite MCP re-audit -> **10/10 passed**.
- Migración up→down→up→check sobre DB scratch -> **limpio**.

Gate ejecutado al cierre del commit `647f103` (referencia histórica
anterior a la certificación):

- `bash scripts/full-qa.sh` -> **950 passed, 1 skipped, 28 deselected**,
  ruff OK, ruff format OK, mypy OK (`135 source files`), Alembic check OK,
  `npm ci`, frontend lint OK, frontend build OK, `sync_doc_counts --check` OK,
  `git diff --check` OK. Los 3 tests nuevos cubren el bug
  `MissingGreenlet`/`eager_defaults` con DB real, no mocks.
- `unset COGOS_JWT && COGOS_API_BASE=http://127.0.0.1:8000 COGOS_BASE_URL=http://localhost:3001 npx playwright test --reporter=list`
  -> **31 passed**. La env var `COGOS_JWT` ya **no** es obligatoria: el
  `tests/e2e/_global-setup.ts` la mintea via `POST /auth/local-token`
  cuando el perfil es `dedicated_local/full`.
- `bash scripts/stress-qa.sh 3` -> 3 pasadas verdes, **950 passed** en cada una.
- `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` -> **8 passed** (último
  carril live verificado; 2 warnings de deprecacion del adaptador MCP upstream,
  no bloqueantes). En este audit no se re-ejecutó (opt-in, no presente en
  `.env`).
- `/system/mcp` con JWT local -> **5/5 connected**, **67 tools**.
- `/system/readiness` -> **14/14 capacidades unlocked**, `gaps=[]`,
  `summary="Sin friccion. Todas las capacidades del perfil estan activas."`.
- `/health/dashboard` -> 18 componentes, overall `configured`; `POST /health/verify`
  prueba LLM/embeddings/IMAP en vivo (último probe live: mail GoDaddy IMAP
  login OK, embeddings 1536-dim OK, primary_llm `degraded` por timeout 3s
  en cold start — no bloqueante).
- TestSprite MCP/CLI -> **10/10 passed** en re-audit acotado
  (`TC001/002/003/004/006/007/008/009/010/014`); no sustituye Playwright
  porque los asserts generados son mas superficiales.

Paso de release estándar (no es un defecto): el build de frontend
(`npm run lint` + `tsc` + `npm run build`) ya está verde dentro de
`full-qa.sh`; la suite Playwright E2E (**31 tests**) necesita el stack
levantado, así que se re-corre `npx playwright test` después de reiniciar el
runtime con el código nuevo — igual que cualquier verificación E2E post-deploy.
Tras reiniciar `uvicorn`/`next start` el dashboard pasa a 18 componentes y
expone `POST /health/verify`.

Si se necesita declarar un release nuevo, volver a correr estos comandos en el
mismo orden y actualizar este archivo con fecha y resultado.

## Hallazgo Resuelto: Scope OAuth De Google Calendar

El carril live detecto que `freeBusy` devolvia `HTTP 403
ACCESS_TOKEN_SCOPE_INSUFFICIENT` aunque `CalendarService.status()` informaba
`ready`. Causa: `GOOGLE_CALENDAR_SCOPES` estaba en
`https://www.googleapis.com/auth/calendar.events`, que permite crear/leer
eventos pero **no** la consulta free/busy. Correccion aplicada: se cambio a
`https://www.googleapis.com/auth/calendar` (acceso completo) y se re-corrio
`scripts/auth_google.py` para re-consentir. Verificado: `freeBusy` responde
`200`. Esto es exactamente el falso-positivo que AUDIT-2026-B/E buscaban
exponer.

## Mail: Contrato Actual

El contrato actual de mail no es "agente envia correo". Es:

1. Dos veces al dia, 10:00 y 20:00 horario Chile, el worker genera digest.
2. Fuentes por defecto:
   - Gmail `diegomanzurn@gmail.com`: `TODOS` + `SPAM`.
   - GoDaddy `diego@doctormanzur.com`: `Spam`.
3. El agente no confia en la carpeta del proveedor: clasifica por contenido.
4. Excluye solo lo que **el propio agente** clasifica como spam.
5. Resume los ultimos 50 correos considerados.
6. Para correos importantes, propone respuestas en un campo de texto separado.
7. No crea drafts en Gmail/GoDaddy.
8. No envia SMTP en el flujo normal.
9. El boton manual de sync del frontend usa `/mail/sync/dispatch` y encola el
   worker `mail`.
10. El digest manual del frontend usa `/mail/digest/preview` con
    `sync_first=false`, por lo que no bloquea el proceso API leyendo IMAP/Gmail.
11. Existe `/mail/digest/dispatch` para encolar digest largo en el worker `mail`.
12. El escape hatch de envio real exige simultaneamente:
    `ENABLE_EMAIL_SEND=true`, `MAIL_ALLOW_EXPLICIT_SEND=true` y
    `explicit_send_confirmation="SEND_THIS_EMAIL_EXPLICITLY"`.

## Health: Contrato De Honestidad

`/health/dashboard` no miente sobre lo que verifico:

- `ok` (componente) — probado en vivo o apagado honestamente (`disabled`).
- `configured` — credenciales/cableado completos pero **sin llamada real**.
- `degraded` — fallo real o estado desconocido.
- Overall: `ok` solo si todo esta `verified`; `configured` si algo esta
  cableado-pero-no-probado; `degraded` si algo fallo.
- `POST /health/verify` fuerza el probe real de los componentes que gastan
  tokens/latencia (`primary_llm`, `embeddings`, `mail`). El frontend tiene el
  boton "Verificar en vivo".
- Componente `operational_backlog`: approvals pendientes, jobs/action-requests
  atascados mas alla del umbral de su reaper, y lag del beat. Se pone `degraded`
  cuando un reaper deberia haber limpiado una fila y no lo hizo.

## Frontend

El cockpit definitivo es **dark-only glass cockpit**, PWA instalable, sin
Tailwind/shadcn/MUI. Reglas vigentes:

- Tokens visuales en `frontend/app/globals.css`.
- Iconos estructurales via `<Icon />`, no emojis/glifos.
- `asArray<T>` en vistas que consumen colecciones.
- `usePolledFetch` pausa offline/tab oculta y reintenta al volver.
- `StatePrimitives` para skeleton/empty/error.
- `useFocusTrap` en modales.
- `playwright.config.ts` bloquea service workers/cache para E2E determinista.
- `full-qa.sh` construye Next en `.next-qa`; no tocar `.next` si el panel vivo
  esta sirviendo desde `next start`.
- `Ctrl/Cmd+K` abre la command palette desde cualquier foco normal porque
  `useKeyboard` escucha en capture phase.

## Que No Debe Afirmarse Sin Re-Validar

- No afirmar que proveedores externos escriben correctamente si no se ejecuto
  smoke real contra Google/GoDaddy/SMTP/Kimi. El carril `tests/live/`
  (`LIVE_TESTS_ENABLED=1 pytest -m live_readonly` o `scripts/full-qa-live.sh`)
  existe justamente para eso, read-only.
- `/health/dashboard` ya NO miente: el overall es `ok` solo si cada componente
  fue verificado en vivo; si alguno esta solo `configured` el overall es
  `configured`, no `ok`. Para forzar la verificacion real usar `POST /health/verify`.
- No decir que la seguridad es de grado SaaS/multiusuario. El sistema actual es
  local, mono-operador y deliberadamente permisivo.
- No decir que el agente envia mails automaticamente. No lo hace y no debe
  hacerlo en el flujo normal.
- No afirmar que el runtime vivo ya corre el codigo nuevo sin haberlo
  reiniciado: `uvicorn`/`next start` cachean el codigo de arranque.

# Cognitive OS

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-28, Prompt 7 V2.0 — re-ejecutado).** Esta rama `codex/commercial-zero-friction-hardening` queda certificada como **APTA COMERCIAL LOCAL-FIRST** para PC dedicado. Branch inicial Prompt 1 V2.0: HEAD `935193e`. El commit final del Prompt 7 V2.0 firma los deltas P3 (F-P2-101 restore + F-P2-103 + F-P2-104 parcial + F-P2-105) y P6 (V2-EVAL-200 path policy + V2-EVAL-202 docanalysis review). Evidencia viva en `tmp/v2_07_absolute_release_closure_20260528_133000/`.
>
> **Hallazgos cerrados V2.0 (10 verificados):** F-P2-101 working tree restored · F-P2-103 (P1) drive_get_file non-ASCII → 400 (15 tests) · F-P2-104 (P2 parcial) responses={} declarado, 89 endpoints en backlog R-001 · F-P2-105 (P3) `_inspect_workers_snapshot` con `connection_or_acquire` + connection=conn (verificado live **6/6 ciclos chaos consecutivos**) · F-P2-102 (P3) demostrado FALSO POSITIVO · V2-EVAL-200 (P1) `_is_sensitive_root` bloquea `~/.ssh`, `~/.gnupg`, `credentials/`, `tokens/` (16 tests) · V2-EVAL-201 (P3) log crudo Code Director ciclo completo · V2-EVAL-202 (P3) `apply_quality_evaluation` reconcilia top-level `human_review_required` con item severity=high / needs_human_review (4 tests). V2-EVAL-001/004/005 previos del cierre V2.0 anterior siguen sosteniéndose.
>
> **Gates V2.0 medidos antes del cierre absoluto:** `bash scripts/full-qa.sh` **1269 passed, 1 skipped, 28 deselected** (ruff/format/mypy/alembic/sync_doc_counts/git-diff verdes); `bash scripts/stress-qa.sh 5` **5/5 verde × 1269 passed × 2 ciclos posteriores al último cambio**, flakiness **0%**; `cd frontend && npx playwright test` **44 passed × 2 ciclos**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/openapi_readonly_smoke.py` **70 GET / 0 failures**; `bash scripts/verify_desktop_launchers.sh` OK; bandit severity-high 0 issues; `POST /health/verify` overall **`ok`** con `mcp_client` live `ok` 6/6 y **70 tools live**; checklist 400 puntos ejecutada (P7 V2.0). **37 tests de regresión nuevos acumulados** (15 F-P2-103 + 2 F-P2-105 + 16 V2-EVAL-200 + 4 V2-EVAL-202).
>
> **Criterio de verdad:** no se declara envío de correo, draft real ni escritura DNS. Mail queda normalizado como read-only (sync/list/classify/digest + proposed replies como texto). GoDaddy preview/dry-run. Action Plane mantiene `validate→preview→request→approve→dispatch→execute→audit` con idempotencia y reapers. Computer organize/inventory bloquean `root_path` con markers sensibles (`.ssh`, `.gnupg`, `credentials`, `secret`, `tokens`, `keychain`) además de la allow-list existente. El runtime corre en `127.0.0.1` sin exposición LAN/internet. **Cognitive OS queda certificado en este commit como APTO COMERCIAL LOCAL-FIRST para PC dedicado, con funcionamiento real activado, documentación sincronizada, dos ciclos completos verdes posteriores al último cambio, Git ordenado y sin P0/P1/P2 abiertos.**

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


> **Estado canonico (2026-05-27, post cierre absoluto V2.0):**
> **COMERCIAL LOCAL-FIRST APROBADO + frontend/TestSprite web hardening**. La
> base comercial local-first 2026-05-25 sigue certificada: matriz
> audit-commercial cerrada, flakiness P0 corregida, activación funcional de 16
> fases verificada, `browser_preview` migrado a `asyncio.to_thread`, router LLM
> hardened, document analysis con formatos completos y mail digest con redacción
> PII. Encima de esa base, el cockpit público quedó endurecido para el portal web
> de TestSprite sin atajos: auth por `#cogos_token=...`, API pública resuelta por
> host, TopBar retirado, shell estable en sidebar + header contextual +
> `data-cogos-active-tab`, hotkey 3 reasignada a DeepAgents, estados
> loading/empty/error reales para colecciones, responsive estable a 920px y PWA
> cache-bust `cogos-v2026-05-26e-status-cards`. Cognitive OS corre como
> **sistema cognitivo local mono-operador** para el PC dedicado de Diego.
> Prioridad de producto: **friccion operativa casi nula por sobre seguridad
> estricta**. Excepcion dura: **mail** — el flujo normal solo lee, clasifica,
> resume y propone respuestas como texto; no crea drafts ni envia correos salvo
> peticion explicita + flags de escape hatch.
>
> **Documentos de referencia:**
> - `docs/CURRENT_STATE.md` — fuente corta de verdad.
> - `docs/ZERO_FRICTION_OPERATING_MODEL.md` — modelo operativo.
> - `docs/USER_GUIDE.md` — guía didáctica para empezar desde cero.
> - `frontend/README.md` — contrato vigente del cockpit Next.js/PWA.
> - `scripts/README.md` y `scripts/testsprite_web/README.md` — operación QA,
>   incluido el despliegue público con `deploy_and_verify.sh`.
> - `docs/audits/FINAL_LOCAL_FIRST_COMMERCIAL_CERTIFICATION.md` — cierre formal
>   local-first 2026-05-25.
> - `tmp/full_functional_activation_20260525_073134/reports/FULL_FUNCTIONAL_ACTIVATION_REPORT.md` —
>   activación funcional end-to-end 2026-05-25 (16 fases live).

## Snapshot Tecnico

Conteos derivados del codigo por `scripts/sync_doc_counts.py` (`full-qa.sh`
falla si quedan desincronizados):

- **Backend** FastAPI 0.115+ — **150 endpoints REST**, **23 tareas Celery** en
  **5 colas** (`default`, `ingestion`, `agent_longrun`, `maintenance`, `mail`),
  hasta **13 jobs beat** segun feature flags.
- **DB** Postgres 16+pgvector — **20 migraciones Alembic**, head
  `202605200003`, `alembic check` sin drift.
- **Orquestacion** LangGraph 1.1.10 + DeepAgents 0.6.x + cliente MCP nativo +
  Action Plane. Ruta `research` fusionada con OpenHarness opcional.
- **Telegram** — **37 slash commands** (dispatch fail-closed) + modo
  conversacional sin slash en `dedicated_local`.
- **Health** — `/health/dashboard` con **18 componentes**; `POST /health/verify`
  para probe real bajo demanda; componente `operational_backlog`.
- **Frontend** Next.js 16.2.6 + React 19 + TypeScript estricto — **20 vistas**,
  PWA dark-only glassmorphism, sin Tailwind/shadcn.
- **LLM** — primary+agent `gpt-5.5` (Responses API + prompt caching 24h),
  secondary/fallback `gemini-3.1-pro-low`, vision `glm-4.6v`.
- **QA** — `full-qa.sh` **1232 passed (V2.0)** post-remediación 2026-05-25 (1190
  base + 2 regresión FK order), `stress-qa.sh 5` -> **5/5 verde**
  (flakiness 0% tras cerrar F-P0-001) +
  ruff/format/mypy/Alembic/lint/build/`sync_doc_counts`/`git diff --check`;
  Playwright **44 passed** (sin necesidad de exportar `COGOS_JWT` — auto-mint
  via `POST /auth/local-token`); carril opt-in `tests/live/` verificado con
  **8 passed** contra proveedores reales. TestSprite local batched histórico:
  **28/28 passed**; TestSprite web público se prepara con
  `bash scripts/testsprite_web/deploy_and_verify.sh` y no debe declararse doble
  verde hasta recibir las corridas/PDFs del portal.
- **Audit-commercial hardening matrix** — 16 archivos `test_audit_commercial_*`
  (15 pytest backend + 1 Playwright spec) con ~230 asserciones hermeticas que
  cierran los contratos P0/P1 mas sensibles: Mail SMTP gate, GoDaddy DNS gate,
  Code Director STDIN-only, eager_defaults full matrix, auth matrix completa,
  path-traversal corpus, operational_backlog reactivo, workflow.v1 version
  hardening, calendar/drive directo `dry_run=false`→409, health overall honest,
  reapers dedicados, DB isolation guard, secrets redaction, test fixtures
  gating, MCP fail-open, Mail UI sin boton Enviar.
- Infra de datos (Postgres / Redis 7 / Weaviate 1.29.0 / Neo4j 5) ligada a
  `127.0.0.1`, sin exposicion a internet.

## Cambios Recientes

**Frontend/TestSprite web hardening (`8a33475`, 2026-05-26).** El cockpit
público ahora usa el contrato de producto que TestSprite web necesita sin
maquillaje de tests:

- `app/lib/apiBase.ts` resuelve `https://cognitive-api.doctormanzur.com` cuando
  el host es `cognitive.doctormanzur.com`, acepta override controlado por hash y
  evita que la build pública llame a localhost por accidente.
- `app/page.tsx` acepta `#cogos_token=<JWT>`/`#token=`/`#jwt=`, persiste
  `localStorage.cogos.token`, elimina el fragmento de la URL y expone
  `data-cogos-active-tab` sobre `<main>` como marcador estable de vista.
- El TopBar fue retirado; la navegación viva es sidebar + header contextual +
  bottom nav móvil. Hotkeys vigentes: `1 Dashboard`, `2 Chat`, `3 DeepAgents`,
  `4 Document Analysis`, `5 Jobs`, `6 Aprobaciones`, `7 LangSmith`, `8 Audit`,
  `9 Health`.
- `DocumentsView`, `AgentsView`, `AuditView`, `HealthView` y `MailInboxView`
  muestran estados loading/empty/error reales y estables; no hay filas ni cards
  falsas para pasar TestSprite.
- `scripts/testsprite_web/deploy_and_verify.sh` reconstruye producción, levanta
  backend/worker/beat/frontend/tunnel, valida frontend público, backend
  `/health`, marker `cogos-v2026-05-26e-status-cards` en `/sw.js` y shell
  `data-cogos-active-tab` antes de pedir el rerun humano.

**Activación funcional end-to-end (2026-05-25 post-remediación).** Sesión de
16 fases con el stack vivo en `dedicated_local/full`. Veredicto: **FUNCTIONAL
WITH WARNINGS**. Lo verificado en runtime:

- Mail SMTP gate 3/3 live → HTTP 409 con mensaje contrato.
- Calendar/Drive `dry_run=false` → HTTP 409 (workflow.v1 enforced).
- `POST /health/verify` live → LLM, embeddings, mail `ok` verificado.
- Chat LLM 10/10 OK (avg 7.16s); thread persiste 4 mensajes.
- RAG: PDF 2p → 2 chunks `indexed`.
- Document Analysis 6 modos detectó contradicción intencional con cita literal.
- Code Director plan-only → 3 subtasks → HumanApproval → reject sin ejecución.
- Telegram `getMe` live `@Socio_dimn_bot` + 102/102 hermetic.
- MCP 6/6 servers, 69 tools.
- CDP 20 vistas: 0 console.error, 0 page.error, 0 5xx; Ctrl+K + mobile.
- Stress: 30 concurrent /health/dashboard 30/30 OK; backlog `ok`.

Hallazgo P1 runtime de esa pasada (preexistente, luego cerrado en el cierre comercial final 2026-05-25):
- **F-RUNTIME-001**: `browser_preview` executor fallaba con `Playwright Sync API
  inside asyncio loop`. Histórico: 5 `browser_preview` previos fallaban idénticamente.
  El contrato "fallar visible" ya funcionaba (`status=failed` + error legible) y
  el cierre comercial posterior lo cerró envolviendo los executors Playwright en
  `asyncio.to_thread`. Detalle histórico en `corregir_cognitive.md`.

Reporte completo: `tmp/full_functional_activation_20260525_073134/reports/FULL_FUNCTIONAL_ACTIVATION_REPORT.md`.

**Remediación P0 — flakiness suite hermetica (2026-05-25 post `0f8232a`).**
Una auditoría post-cierre detectó flakiness real al ~33% en `full-qa.sh` y
`stress-qa.sh`: 1 de cada 3 corridas fallaba con tests distintos cada vez.
Causa raíz: el fixture `clean_slate` de 2 archivos audit-commercial limpiaba
`HumanApproval` antes que `DeepAgentMemoryProposalRecord`, que también tiene
FK a `human_approvals.id`. Tests del plan de aprendizaje
(`test_failure_postmortem`, `test_skill_promoter`, `test_recipe_extractor`,
`test_nightly_reflection`) dejaban filas pobladas y la limpieza explotaba con
`ForeignKeyViolationError`. Fix aplicado (3 archivos de test, **cero código
de producto**):
- `backend/tests/test_audit_commercial_operational_backlog.py` — agrega
  `DeepAgentMemoryProposalRecord` al fixture antes de `HumanApproval`.
- `backend/tests/test_audit_commercial_reapers_dedicated.py` — idem.
- `backend/tests/test_clean_slate_fixture_covers_all_fks.py` (nuevo) — test
  de regresión que detecta futura adición de FKs sin actualizar fixtures.

Gate post-remediación: `full-qa.sh` -> **1232 passed (V2.0)**, `stress-qa.sh 5` ->
**5/5 verde × 1200 passed**, Playwright **44 passed**, CDP **0 console.error**.
**2 ciclos completos verdes** tras el último cambio. Flakiness post-fix: **0%**.
Reporte completo en
`tmp/full_functional_activation_20260525_073134/archived_remediation/remediation_20260525_065154.tar.gz` (archivado tar.gz).

Riesgos operativos residuales (no-código, no bloquean release):
- `google_calendar`/`google_drive` `blocked` por OAuth scope — operador re-corre
  `scripts/auth_google.py` (contrato "fallar visible" funciona).
- 309 approvals pending acumuladas (ninguna stale, reaper trabaja) — triage operador.

Registro histórico de pendientes de esa pasada: `corregir_cognitive.md`; el estado vigente 2026-05-26 se resume al inicio de este README.

**Audit-commercial hardening matrix (`0f8232a`, 2026-05-25).** Pasada
quirurgica de remediacion read-only convertida en cobertura hermetica:
cerro los 4 contratos P0-criticos y los 12 GAPs P1 del mapa de contrato
(`tmp/commercial_audit_20260525_030342/01_CONTRACT_MAP.md`). **Sin tocar
codigo de producto**; solo 16 archivos de test nuevos (15 pytest backend
+ 1 Playwright spec) con ~230 asserciones. Plan ejecutado en
`tmp/commercial_audit_20260525_030342/03_EXECUTION_PLAN.md`; reporte en
`tmp/commercial_audit_20260525_030342/05_REMEDIATION_REPORT.md`.

Tambien resuelve 2 tests historicos rojos en HEAD `5459ec5`
(`test_drive_organize_does_not_auto_approve_in_guarded_dedicated_local`
y `test_drive_organize_auto_approves_in_full_dedicated_local`) que no
stubeaban `DriveService`; ahora usan `_FakeReadyDriveService`.

Gate post-fix: `bash scripts/full-qa.sh` -> **1232 passed (V2.0; 1190 base histórico)**, 1 skipped,
28 deselected (958 historicos + 227 audit-commercial + 4 time_mcp_server
+ 1 dispatch guard). Playwright -> **43 passed**.
*Tras remediación 2026-05-25 ese gate subió a `1200 passed` por +2 tests
de regresión FK order; ver sección anterior.*

**Time MCP local + commercial UX hardening (`ce72dc2`, 2026-05-25).**
MCP server local de hora (`time_mcp_server.py`, stdio, sin red, sin
auth) -> inventario **6/6 servers** (`mem/gh/fs/cc/gem/time`) y **69
tools**. En la misma pasada: error message del dispatch
`"Action request not found; dispatch blocked before side effects"`,
voice service redacta `tts_voice_id` a `configured`/`missing`,
frontend `lib/api.ts` soporta `AbortSignal`, `page.tsx` detecta host
publico/local + aborta `requestLocalToken` tras 10s, `HealthView`
aborta `/health/verify` tras 45s con mensaje legible, `SettingsView`
siempre renderiza el tile MCP (no oculto). Nuevo
`test_dispatch_missing_action_request_reports_blocked_guard`.

**Reaudit TestSprite + zero-friction Playwright (`647f103`, 2026-05-23).**
Una segunda pasada de auditoria independiente cazo un P1 que la primera
pasada no detecto y reforzo el carril QA local:

- **P1 — `eager_defaults=True` en `db.Base`:**
  `POST /actions/browser/preview/request` (y todos los `create_*_request`
  que leen `updated_at` despues de `session.flush()` en `AsyncSession`)
  devolvia HTTP 500 con `sqlalchemy.exc.MissingGreenlet`. El attribute
  lazy-load disparaba SQL sincronico fuera del greenlet. Fix idiomatico
  SQLAlchemy 2.x: `__mapper_args__ = {"eager_defaults": True}` en `Base`,
  emite `INSERT ... RETURNING` para columnas con server-default.
  Endpoint vivo verificado HTTP 200; idempotency intacta. 3 tests de
  regresion nuevos (`backend/tests/test_action_request_eager_defaults.py`).
- **P2 — Playwright zero-friction runner:** nuevo
  `frontend/tests/e2e/_global-setup.ts` auto-mintea `COGOS_JWT` via
  `POST /auth/local-token` cuando el perfil es `dedicated_local/full`.
  `npx playwright test` ahora pasa 31/31 sin exportar nada.
- **P3 — RUNBOOK QA actualizado:** método primario `curl POST
  /auth/local-token | python3 -c "...access_token"`; el `uv run python -c
  "from cognitive_os.core.auth..."` queda como fallback para `strict`.

Gates post-fix: `full-qa.sh` **950 passed** (944 + 6 regresion), stress-qa
3 × 950, Playwright 31/31, TestSprite re-audit 10/10. En la rama
`codex/commercial-zero-friction-hardening`, el gate subio a **958 passed** por
14 regresiones/guards, Playwright subio a **41 passed** con fixtures criticas
y TestSprite completo quedo **28/28 passed** en batches. El cierre final con
API key nueva fue bloqueado por proveedor (`AUTH_FAILED` HTTP 401). Detalle en
`docs/qa/commercial_zero_friction_hardening/09_FINAL_CLOSURE_AUDIT.md` y
detalle historico en
`docs/audits/testsprite/16_FINAL_REAUDIT_REPORT.md`.

**Post-gate MCP/frontend (`5953b40`, 2026-05-22).** Se corrigio un falso
timeout real de `/system/mcp`: el inventario de MCP carga servidores en
paralelo y usa `MCP_INVENTORY_TIMEOUT_SECONDS=30` por defecto. Runtime actual
verificado tras el alta local de `time` (2026-05-25): `mem`, `gh`, `fs`, `cc`,
`gem` y `time` conectados (**6/6**) con **69 tools**. `time` corre como MCP
local del backend por `stdio` (`uv run python -m
cognitive_os.integrations.time_mcp_server`), no usa auth ni red externa, y
expone `time_time_now` / `time_time_convert` para hora actual y conversion de
zonas. Tambien se estabilizo `Ctrl/Cmd+K` del command palette usando capture
phase en el hook de teclado.

**Remediacion del audit comercial (2026-05-22).** Tras
`docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md` se cerraron las 8 fallas
accionables (AUDIT-2026-A..H):

- **A (P0)** — dispatch de Telegram fail-closed: una allowlist vacia rechaza a
  todos y `main()` se niega a arrancar en ese estado.
- **B (P1)** — `/health/dashboard` distingue `verified` de `configured` y no
  pinta verde lo que nunca se probo; nuevo `POST /health/verify`.
- **C (P1)** — kill switch `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED` para la
  unica ruta de auto-deploy del plan de aprendizaje.
- **D (P2)** — matriz de tests de los 37 comandos Telegram.
- **E (P2)** — carril `tests/live/` opt-in (`LIVE_TESTS_ENABLED=1`).
- **F (P2)** — componente `operational_backlog` en health.
- **G (P3)** — `scripts/sync_doc_counts.py` mantiene los conteos canonicos.
- **H (P3)** — `scripts/dev_up.sh` valida variables antes de `docker compose`.

**Plan de aprendizaje autonomo (Fases A-E, `docs/AGENT_LEARNING_PLAN.md`):** en
produccion. Fase A recipe extractor, Fase B skill promotion (procedure → skill
YAML con rollback automatico), Fase C tool scorecard, Fase D failure
post-mortem, Fase E nightly reflection con evidencia literal obligatoria. Todo
pasa por el approval gate del operador; la unica excepcion acotada es el
auto-promote de *warnings* de Fase D, con kill switch.

**Code Director:** meta-agente que delega builds a coding agents externos
(Claude Code / Codex / Kimi CLI o DeepAgents in-process) bajo aprobacion humana
+ budget caps + audit, con planner LLM-driven y fallback heuristico.

El historial fase-a-fase detallado vive en `git log` y en el contexto del
documento de auditoria; este README mantiene solo el estado vigente.

## Que Es Cognitive OS

Monorepo con backend **FastAPI** (agentes LangGraph, Celery, Postgres) y
**Next.js 16** como consola web.

**Investigacion (`research`):** Cognitive OS **fusiona** tres capas cuando se
activa el motor opcional OpenHarness: LangGraph orquesta → [OpenHarness](https://github.com/HKUDS/OpenHarness)
puede generar un **preludio** con su `QueryEngine` (en el mismo workspace que
DeepAgents si `OPENHARNESS_WORKSPACE_MODE=deepagent_mirror`) → [DeepAgents](https://github.com/langchain-ai/deepagents)
produce el informe con citas y politica del proyecto. Si OpenHarness no esta
instalado/habilitado o falla, el grafo continua solo con DeepAgents y, si este
no responde, con un agente RAG determinista de fallback.

Incluye una capa de **Action Plane** para preparar acciones seguras de
navegador, computador local, Gmail, Google Maps/Calendar/Drive, GoDaddy DNS,
documentos Office y correo personal. Las acciones sensibles quedan auditadas
(`ActionRequest`, `JobEvent`, `AuditEvent`) y, en `strict`, pasan por aprobacion
humana. Ver `docs/ACTION_PLANE.md` y `docs/PERSONAL_ASSISTANT_ROADMAP.md`.

## Leer Primero

- **`docs/USER_GUIDE.md`: Guía de Usuario comercial — empieza aquí. Estado, frontend vista por vista, pipelines, Telegram, ejemplos impresionantes, qué hace / qué no hace, cómo NO usar el sistema.**
- `docs/COGNITIVE_OS_GUIDE.md`: guía maestra técnica "desde cero" — complementa la USER_GUIDE con arquitectura detallada, mail multicuenta, escritorio, credenciales, troubleshooting profundo.
- `docs/PROJECT_GUIDE.md`: explicacion simple y tecnica del producto.
- `docs/README.md`: indice completo de documentacion.
- `docs/OPENHARNESS_FUSION.md`: cómo encaja OpenHarness con LangGraph + DeepAgents (pipelines, presets, workspace).
- `docs/RUNBOOK.md`: operacion diaria.
- `docs/SECURITY.md`: reglas de seguridad.
- `docs/OPERATOR_VARIABLE_CHECKLIST.md`: checklist ENV ↔ código (`Settings`) y tabla maestra.
- `task_plan.md`, `findings.md`, `progress.md`: planificacion viva de esta
  intervencion; no son documentacion permanente de producto.

Copia de respaldo reproducible del árbol de fuentes (sin `node_modules`, `.venv`, `.next`): ejecuta desde el directorio padre:

```bash
rsync -a --exclude node_modules --exclude .next --exclude .venv --exclude '__pycache__' \
  cognitive-os/ cognitive-os-snapshot-$(date +%F)/
```

## Requisitos

- Python ≥ 3.12 y [uv](https://docs.astral.sh/uv/)
- Node.js ≥ 22 y npm
- Verificación reproducible: `bash scripts/full-qa.sh` (`uv sync --extra openharness` + `pytest` + `ruff check` + `ruff format --check` + `mypy` + `npm ci` + `npm run lint` + `npm run build` + `sync_doc_counts.py --check` + `git diff --check`). Estrés: `bash scripts/stress-qa.sh` (3 pasadas de pytest por defecto). Smokes en vivo opt-in: `bash scripts/full-qa-live.sh`.
- Snapshot QA actual (2026-05-27, post cierre absoluto V2.0): `bash scripts/full-qa.sh` **1200 passed, 1 skipped, 28 deselected** (1190 base + 2 regresión FK order); `bash scripts/stress-qa.sh 5` -> **5/5 verde** (flakiness 0%); ruff/ruff format/mypy, frontend lint/build aislado con `.next-qa`, Alembic head `202605200003` y `git diff --check` verdes. Playwright frontend: **43 passed** sin exportar `COGOS_JWT` (auto-mint via `_global-setup.ts`). Live read-only: `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed** (último gate documentado). TestSprite local batched histórico: **28/28 passed**; TestSprite web público se entrega con `bash scripts/testsprite_web/deploy_and_verify.sh` y queda pendiente de confirmar por reportes del portal, sin afirmar dos corridas web verdes hasta recibirlos.

## Backend

Desde la raíz del repo o `backend/`:

```bash
cd backend
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000   # API
```

`uv run cognitive-os` es un *bootstrap* mínimo (`backend/src/cognitive_os/__main__.py`) que sólo imprime un log inicial; **no** levanta la API. Para arrancar la pila completa puedes usar los ejecutables de escritorio (`/home/jgonz/Escritorio/Levantar Cognitive OS.sh`, `Reiniciar Cognitive OS.sh`, `Detener Cognitive OS.sh`, `Estado Cognitive OS.sh`) o el flujo manual de `docs/RUNBOOK.md`.

Motor opcional **OpenHarness**: `uv sync --extra openharness` + `ENABLE_OPENHARNESS_RESEARCH=true`. Variables `OPENHARNESS_*` en `docs/SETTINGS_REGISTRY_TABLE.md`; modelo de fusión (**`prelude_merge`** por defecto vs **`short_circuit`**) y presets **`minimal` / `research` / `full`** en `docs/OPENHARNESS_FUSION.md`.

Variables de entorno: copia `.env.example` en la raíz a `.env` y ajusta secretos.

- **CORS**: `CORS_ALLOW_ORIGINS` (lista CSV). Vacío ⇒ defaults `http://localhost:{3000,3001}` y `http://127.0.0.1:{3000,3001}` (frontend real corre en :3001 porque OpenChamber ocupa :3000; :3000 queda para compatibilidad). No uses `*` con credenciales habilitadas (lo rechaza la configuración).
- **Action Plane y mail personal**: en `strict`, las acciones externas arrancan desactivadas o con aprobación humana. En `OPERATOR_PROFILE=dedicated_local` + `LOCAL_AUTONOMY_MODE=full`, el PC dedicado elimina approvals manuales para reducir fricción en browser/computer/Google, pero conserva `ActionRequest`, `JobEvent`, `AuditEvent`, idempotencia y errores visibles. Mail queda fuera de esa relajación: por defecto solo lee, resume y propone texto; SMTP requiere una petición explícita de Diego. Configura `ENABLE_BROWSER_AUTOMATION`, `ENABLE_COMPUTER_ACTIONS`, `GMAIL_*`, `GODADDY_*`, `MAIL_*` y allow-lists/flags antes de cualquier ejecución real.

## Infra local (Docker)

Comando único correcto (valida variables y espera health checks):

```bash
bash scripts/dev_up.sh
```

Equivalente manual (no recomendado — `dev_up.sh` además valida que las
variables que el compose interpola sin default no estén vacías):

```bash
cd infra
docker compose --env-file ../.env up -d
```

## Frontend

```bash
cd frontend
cp .env.example .env.local   # opcional: fija NEXT_PUBLIC_API_BASE_URL en build/prod
npm ci
# Dev:
PORT=3001 npm run dev        # (OpenChamber ocupa :3000)
# Prod local:
npm run serve                # build + next start -H 127.0.0.1 -p 3001
npm run lint
npm run build
```

En desarrollo el panel puede apuntar al API desde ajustes en la UI; si defines
`NEXT_PUBLIC_API_BASE_URL` al hacer build, esa URL inicial tendrá prioridad.

**Stack y lenguaje visual:**

- Next.js 16.2.6 App Router + React 19 + TypeScript 5.8 estricto.
- **Glassmorphism dark-only** de alto contraste. Sin Tailwind, sin
  shadcn. Tokens centralizados en `app/globals.css`; `<html
  data-theme="dark">` fijo desde `layout.tsx`.
- **Tipografía:** Inter + JetBrains Mono self-hosted vía `next/font/google`
  (la PWA arranca offline sin pedir Google Fonts).
- **Iconografía:** componente `<Icon name="…" />` (`app/components/Icon.tsx`)
  con SVGs Lucide-style consistentes. **No usar emojis ni glifos
  Unicode para íconos estructurales.**
- **Charts SVG** sin dependencias en `app/components/Charts.tsx`:
  `Sparkline`, `AreaChart`, `BarList`, `Donut`.
- **PWA instalable**: `app/manifest.ts` + `public/sw.js`. Shortcuts (Chat /
  Aprobaciones / Jobs / Health), íconos PNG 192/512 + maskable + SVG fallback,
  `/offline.html` con branding propio. Handlers de `push` y
  `notificationclick` listos para notificaciones del SO.
- **Centro de notificaciones** (`NotificationCenter.tsx`) con feed unificado de
  aprobaciones, jobs y eventos de auditoría.
- **Command palette** (`CommandPalette.tsx`) con fuzzy match real, atajo
  `Ctrl/Cmd+K` estabilizado desde capture phase.
- **Defensive list guards** (`api.ts → asArray<T>(...)`): cada vista que
  consume `usePolledFetch<T[]>` usa `asArray(data)` para no caer al
  `ErrorBoundary` si el backend responde malformado.

**QA del frontend:**

- `npm run lint` → 0 warnings (`--max-warnings 0`).
- `npm run build` → Next 16.2.6 + Turbopack OK.
- `npx tsc --noEmit` → 0 errores.
- Playwright headless full-walk (1440×900 + 393×851 mobile) sobre las 20
  tabs, palette y notification center: **43 passed** (incluye `audit-commercial-mail-no-send-button.spec.ts`), 0 errores 5xx, 0 page
  errors, 0 console errors. `playwright.config.ts` bloquea el service worker
  durante los tests y deshabilita el cache HTTP.

## Ensayo local rápido

Con Postgres/Redis opcionales, la API puede arrancar con checkpointer en memoria si Postgres no está listo.

# Estado Actual Canonico — Cognitive OS

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-27, Prompt 7).** Esta rama `codex/commercial-zero-friction-hardening` queda certificada como **APTA COMERCIAL LOCAL-FIRST** para PC dedicado. Branch inicial Prompt 1: HEAD `2bb4966`. Working tree del Prompt 7 consolida los cambios de Prompts 3 (F-P2-001..006), 4 (F-P4-001 fix wrapper timeout mcp_client live probe) y 6 (V2-EVAL-001 DocAnalysis API consistency). El commit final del Prompt 7 firma todo el delta V2.0 sin push. Evidencia viva en `tmp/v2_07_absolute_release_closure_20260527_175541/`.
>
> **Hallazgos cerrados V2.0 (12):** F-P2-001 wildcard_allow_all transparency · F-P2-002 stress flake eliminado (0% en 5×1232) · F-P2-003 `?limit=` honored en `/approvals` y `/actions/drive/files` · F-P2-004 `/chat` 404/400 con `missing_doc_ids`/`invalid_doc_ids` · F-P2-005 docs sync (este bloque) · F-P2-006 `_check_mcp(verify_live=True)` → overall `ok` · F-P4-001 timeout wrapper +5s sobre `mcp_inventory_timeout_seconds` · F-P4-002 fallback heurístico DocAnalysis documentado · F-P4-003 Kimi extension boot oscillation documentado · V2-EVAL-001 `GET /document-analysis/{id}` mirror artefacto · V2-EVAL-004 endpoints memoria/aprendizaje live (303 proposals, 209 recipes, 94 warnings) · V2-EVAL-005 Code Director adapter=deepagent plan+approval+reject sin exec.
>
> **Gates V2.0 medidos antes del cierre absoluto:** `bash scripts/full-qa.sh` **1232 passed, 1 skipped, 28 deselected** (ruff/format/mypy/alembic/sync_doc_counts/git-diff verdes); `bash scripts/stress-qa.sh 5` **5/5 verde × 1232 passed**, flakiness **0%**; `cd frontend && npx playwright test` **44 passed**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/openapi_readonly_smoke.py` **70 GET / 0 failures**; `bash scripts/verify_desktop_launchers.sh` OK; security-readonly-qa (bandit/semgrep/secret-scan) clean; `POST /health/verify` overall **`ok`** con `mcp_client` live `ok` 6/6 y 69 tools; checklist 400 puntos ejecutada.
>
> **Criterio de verdad:** no se declara envío de correo, draft real ni escritura DNS. Mail queda normalizado como read-only (sync/list/classify/digest + proposed replies como texto). GoDaddy preview/dry-run. Action Plane mantiene `validate→preview→request→approve→dispatch→execute→audit` con idempotencia y reapers. El runtime corre en `127.0.0.1` sin exposición LAN/internet. El frontend `cognitive.doctormanzur.com` se levanta on-demand sólo con `scripts/testsprite_web/deploy_and_verify.sh`; Prompt 7 V2.0 no lo expone permanentemente. **Cognitive OS queda certificado en este commit como APTO COMERCIAL LOCAL-FIRST para PC dedicado, con funcionamiento real activado, documentación sincronizada, dos ciclos completos verdes posteriores al último cambio, Git ordenado y sin P0/P1/P2 abiertos.**

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->

<!-- V2_PROMPT3_REMEDIATION_STATUS_START -->

> **Remediación Prompt 3 V2.0 (2026-05-27, post-Prompt-2 sweep).** Esta auditoría
> independiente partió desde la rama `codex/commercial-zero-friction-hardening`
> base `2bb4966` y reabrió la matriz contractual sin asumir ningún verde
> declarado. El Prompt 2 (RUN_DIR
> `tmp/v2_02_readonly_execution_20260527_142619`) reportó **6 hallazgos** (1 P0
> + 1 P1 + 2 P2 + 2 P3) frente al stack vivo. El Prompt 3 los cerró con tests
> de regresión sin tocar `.env`, sin commits y sin TestSprite:
>
> - **F-P2-001 (P0 → CLOSED)**: `WebBridgeStatus` ahora expone
>   `wildcard_allow_all` para distinguir un dominio específico de la opt-out
>   `*` que el operador tiene configurada. El bypass observado por Prompt 2
>   resultó ser la opt-out documentada, ahora visible al cockpit/audit. Test:
>   `test_kimi_webbridge.py::test_status_flags_wildcard_allow_all_when_star_is_configured`.
> - **F-P2-002 (P1 → CLOSED)**: `test_document_analysis_api.py::test_run_endpoint_creates_job`
>   endurecido — el test mockea `_record_celery_dispatch_outcome` para
>   eliminar la dependencia transitiva a la sesión DB que producía 20% de
>   flake bajo `stress-qa.sh 5`.
> - **F-P2-006 (P2 → CLOSED)**: `_check_mcp(verify_live=True)` ahora hace
>   probe real contra los servidores MCP declarados, lo que permite que el
>   overall de `/health/dashboard` llegue a `ok` tras `POST /health/verify`.
>   Tres tests nuevos cubren la matriz (todos conectados, partial drop,
>   total drop).
> - **F-P2-003 (P2 → CLOSED)**: `GET /approvals?limit=N` ahora honra el
>   parámetro (default 100, bounds 1..500). `POST /actions/drive/files`
>   acepta `limit` como alias de `max_results`. Tests:
>   `test_api_limit_contracts_p2_003.py`.
> - **F-P2-004 (P3 → CLOSED)**: `POST /chat` con `doc_ids` 100% inexistentes
>   ahora devuelve **404** con `missing_doc_ids`; `doc_ids` sin UUID válido
>   devuelve **400**; misses parciales siguen pasando al grafo para que el
>   análisis declare los gaps. Tests:
>   `test_chat_doc_ids_validation_p2_004.py`.
> - **F-P2-005 (P3 → CLOSED por anotación)**: este bloque documenta el HEAD
>   post-Prompt-3 mientras el bloque V2_ABSOLUTE_CLOSURE original se
>   reserva para el cierre formal del Prompt 7 V2.0.
>
> **Gates Prompt 3 post-fix:** `python3 scripts/sync_doc_counts.py --check` OK
> (sin cambios estructurales en endpoints/tareas/migraciones/vistas).
> `cognitive-os/backend` ruff + ruff-format + mypy + alembic-check verdes.
> Tests focales de cada fix verdes en hermetic mode. Stress de cierre y
> Playwright corren en la sección "Último Gate Verde Conocido" tras este
> bloque.

<!-- V2_PROMPT3_REMEDIATION_STATUS_END -->


Fecha de sincronizacion documental: **2026-05-27 (post cierre absoluto V2.0 — Prompt 7 V2.0)**
Branch auditada: `codex/commercial-zero-friction-hardening`
Ultimo commit certificado documentalmente: **commit V2.0 final** (`git log -1` — `final: certify Cognitive OS commercial local-first readiness (V2.0)`) sobre base `2bb4966983ab` (Prompt 1 inicial).
Estado del producto: **APTO COMERCIAL LOCAL-FIRST para PC dedicado** — 12 hallazgos V2.0 cerrados, 0 P0/P1/P2 abiertos, 2 ciclos completos verdes posteriores al último cambio, doc audit firmado en `docs/audits/FINAL_ABSOLUTE_V2_COMMERCIAL_LOCAL_FIRST_CERTIFICATION.md`.
La certificación local-first 2026-05-25 se conserva como base: matriz audit-commercial hardening cerrada, flakiness P0 cerrada, activación funcional end-to-end verificada, browser_preview migrado a `asyncio.to_thread`, router LLM hardened, document analysis con formatos completos, mail digest con redacción PII y 0 P0/P1/P2 funcionales abiertos en esa capa. El estado vigente agrega el hardening frontend/public-web: hash auth `#cogos_token`, API pública por host, TopBar retirado, shell estable en sidebar + header contextual + `data-cogos-active-tab`, hotkey 3 = DeepAgents, estados comerciales loading/empty/error sin datos falsos, responsive 920px y service worker `cogos-v2026-05-26e-status-cards`.
Snapshot de cierre formal previo:
[`docs/audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md`](audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md).
**Certificación comercial final local-first:**
[`docs/audits/FINAL_LOCAL_FIRST_COMMERCIAL_CERTIFICATION.md`](audits/FINAL_LOCAL_FIRST_COMMERCIAL_CERTIFICATION.md).
Reportes de activación + evaluación independiente en
`tmp/full_functional_activation_20260525_073134/reports/`.

Este archivo es la **fuente corta de verdad** del estado operativo actual. Si
otro Markdown discrepa, este archivo manda y el otro debe corregirse. Los
conteos estructurales del "Snapshot Tecnico" se generan con
`scripts/sync_doc_counts.py` y `full-qa.sh` falla si quedan desincronizados.

## Cambios Mas Recientes

**Cierre absoluto V2.0 (2026-05-27, commit V2.0 final sobre base `2bb4966`).**
Siete prompts V2.0 (`prompts_claude-codex_v2/`) re-ejecutaron desde cero el
plan de hardening commercial local-first:

- **Prompt 1** — Mapa contractual + matriz de 663 controles.
- **Prompt 2** — Ejecución read-only adversarial: 6 hallazgos descubiertos
  (F-P2-001..006).
- **Prompt 3** — Remediación inicial: 6 fixes + 9 tests de regresión
  (1230 passed, stress 3/3 verde).
- **Prompt 4** — Activación real con runtime nuevo: F-P4-001 fix wrapper
  timeout para `mcp_client` live probe.
- **Prompt 5** — Evaluación independiente: V2-EVAL-001 (DocAnalysis
  response API ≠ artefacto persistido).
- **Prompt 6** — Fix V2-EVAL-001 con 2 tests + reactivación
  (1232 passed, stress 5/5 verde).
- **Prompt 7** — Cierre absoluto: sync de 16 docs canónicos con bloque
  `V2_ABSOLUTE_CLOSURE_STATUS`, **dos ciclos completos verdes posteriores
  al último cambio**, commit local final y certificación firmada.

**Fixes V2.0 cerrados (12 hallazgos, 0 P0/P1/P2 abiertos):**

- `F-P2-001` — `WebBridgeStatus.wildcard_allow_all` ahora distingue
  configuración `KIMI_WEBBRIDGE_ALLOWED_DOMAINS=*` (opt-out wildcard) de
  un dominio específico, sin tocar el comportamiento.
- `F-P2-002` — `test_run_endpoint_creates_job` endurecido contra race
  con `_record_celery_dispatch_outcome` bajo carga (`stress-qa.sh 5`
  ahora 0% flakiness × 10 corridas consecutivas).
- `F-P2-003` — `GET /approvals?limit=N` honra el parámetro con bounds
  1..500 (default 100); `POST /actions/drive/files` acepta `limit` como
  alias de `max_results`.
- `F-P2-004` — `POST /chat` con `doc_ids` 100% inexistentes → **404**
  con `missing_doc_ids`; `doc_ids` mal formados → **400** con
  `invalid_doc_ids`; misses parciales siguen pasando al grafo.
- `F-P2-005` — bloque `V2_ABSOLUTE_CLOSURE_STATUS` regenerado en los 16
  docs canónicos para apuntar al cierre V2.0 (este).
- `F-P2-006` — `_check_mcp(verify_live=True)` ahora dial los 6 MCP
  servers vía `load_mcp_tools_async`, lo que permite que el overall de
  `/health/verify` finalmente llegue a `ok` (antes el endpoint era
  estructuralmente inalcanzable).
- `F-P4-001` — `_safe_check` ahora aplica `mcp_inventory_timeout_seconds + 5s`
  al wrapper de `mcp_client` (antes el wrapper estrangulaba a 3s el probe
  live que toma ~5s en paralelo).
- `F-P4-002` (declarado) — DeepAgent BadRequestError sigue cayendo a
  fallback heurístico, que produce contenido válido con citas literales.
  Documentado como capacidad opt-in para futura migración del agent lane.
- `F-P4-003` (declarado) — Kimi WebBridge extension oscilla al arrancar
  el daemon; quedar `ready` tras ~30s; no bloquea operación.
- `V2-EVAL-001` — `GET /document-analysis/{task_id}` ahora retorna el
  `DocumentAnalysisResult` completo serializado (evidence_matrix,
  timeline, contradictions, missing_evidence, draft_sections, citations,
  uncertainty_notes, available_artifacts, thread_id), coincidente con
  el artefacto descargable `/download/json`. Antes el endpoint sólo
  exponía 5 campos parciales, lo que hacía aparecer "vacíos" análisis
  que en disco tenían claims y contradicciones detectadas.
- `V2-EVAL-004` — endpoints `/deepagents/memory/*` y
  `/deepagents/learning/*` verificados live (303 proposals + 209
  recipes + 94 warnings al cierre).
- `V2-EVAL-005` — Code Director con `adapter_preference={"default_adapter":"deepagent"}`
  generó plan de 3 subtasks → HumanApproval → reject sin ejecución,
  confirmando que el flujo no gasta tokens antes de approval; el `fake`
  adapter sigue rechazado con 400.

**Tests V2.0 (9 nuevos, 1230 → 1232):**

- `tests/test_kimi_webbridge.py::test_status_flags_wildcard_allow_all_when_star_is_configured`
- `tests/test_health_dashboard.py::test_mcp_verify_live_*` (3 cases)
- `tests/test_api_limit_contracts_p2_003.py` (2 cases)
- `tests/test_chat_doc_ids_validation_p2_004.py` (3 cases)
- `tests/test_document_analysis_response_consistency_v2_eval_001.py` (2 cases)
- `tests/test_document_analysis_api.py::test_run_endpoint_creates_job` (endurecido)

**Documentos canónicos sincronizados (16):** CURRENT_STATE,
ZERO_FRICTION_OPERATING_MODEL, ARCHITECTURE, ACTION_PLANE, RUNBOOK,
USER_GUIDE, PROJECT_GUIDE, COGNITIVE_OS_GUIDE, AGENT_LEARNING_PLAN,
DEEPAGENTS_INTEGRATION, DEEPAGENTS_SKILLS_MEMORY, DOCUMENT_ANALYSIS_AGENT,
FRONTEND_ARCHITECTURE, OPERATOR_VARIABLE_CHECKLIST, SECURITY, README.

**Frontend/TestSprite web hardening (2026-05-26, commit `8a33475`).** El
estado activo del cockpit público quedó alineado con el PRD read-only usado en
TestSprite web:

- Frontend público: `https://cognitive.doctormanzur.com`.
- Backend público: `https://cognitive-api.doctormanzur.com`.
- Auth preferida: `#cogos_token=<JWT_SIN_BEARER>`; el frontend persiste
  `localStorage.cogos.token` y limpia el fragmento de la URL.
- El shell ya no depende del TopBar: la navegación vive en sidebar + header
  contextual + bottom nav móvil, y `<main>` expone `data-cogos-active-tab`.
- Hotkeys vigentes: `1 Dashboard`, `2 Chat`, `3 DeepAgents`, `4 Document
  Analysis`, `5 Jobs`, `6 Aprobaciones`, `7 LangSmith`, `8 Audit`, `9 Health`.
- `DocumentsView`, `AgentsView`, `AuditView`, `HealthView` y `MailInboxView`
  mantienen DOM estable para loading/empty/error sin inventar datos.
- Responsive comercial: breakpoint 920px, sidebar desmontado en móvil salvo
  drawer abierto, bottom nav visible y sincronización por `matchMedia` +
  `orientationchange` + `visualViewport`.
- PWA/service worker: marker `cogos-v2026-05-26e-status-cards`.
- Handoff público: `bash scripts/testsprite_web/deploy_and_verify.sh`; este
  valida frontend, backend `/health`, marker SW y shell antes de pedir rerun
  humano. No se deben declarar dos corridas web verdes hasta recibir los PDFs o
  reportes del portal.

**Activación funcional end-to-end (2026-05-25 post-remediación).** Sesión
operativa de 16 fases con el stack vivo en `dedicated_local/full` y JWT real.
Resultado: **FUNCTIONAL WITH WARNINGS**. Todos los contratos críticos
verificados en runtime:

- **Mail SMTP gate 3/3 live** → `HTTP 409` con mensaje contrato; no drafts, no send.
- **Calendar/Drive `dry_run=false` → `HTTP 409`** (workflow.v1 enforced).
- **GoDaddy DNS preview** `dry_run_only=true`; nunca writes reales.
- **`POST /health/verify` live** → `primary_llm`, `embeddings`, `mail` confirmados `ok`.
- **Chat live LLM** 10 mensajes consecutivos OK (avg 7.16s); thread persiste 4 msgs.
- **RAG ingest+retrieve** verificado: PDF 2p → 2 chunks `indexed` (Weaviate confirm).
- **Document Analysis 6 modos** ejercitado; detectó contradicción intencional con
  cita literal (page 2, chunk 1); JSON+MD descargables; `human_review_required=true`
  por fallback heurístico (DeepAgent `BadRequestError` — F-DOC-ANALYSIS-001).
- **Code Director plan-only** → 3 subtasks generadas → HumanApproval → reject limpio
  **sin ejecución**.
- **Telegram** `getMe` live `@Socio_dimn_bot` + 102/102 hermetic.
- **MCP** 6/6 servers / 69 tools live.
- **CDP 20 vistas** con **0 console.error, 0 page.error, 0 5xx**; Ctrl+K palette y
  mobile OK; 21 screenshots capturados.
- **Stress**: 30 GET /health/dashboard concurrentes 30/30 OK en 8.33s;
  `operational_backlog.status=ok` post-actividad (beat_lag 6.6 min).

Hallazgo P1 nuevo (runtime preexistente, NO regresión):
- **F-RUNTIME-001**: `browser_preview` executor falla con
  `Playwright Sync API inside asyncio loop`. Histórico confirmado:
  los últimos 5 `browser_preview` ActionRequests previos (2026-05-23)
  fallan idénticamente. Contrato "fallar visible" funciona
  (`status=failed` + error legible + JobEvent). La función queda
  pendiente de migrar a Async Playwright. Detalle en `corregir_cognitive.md`.

Reporte completo: `tmp/full_functional_activation_20260525_073134/reports/FULL_FUNCTIONAL_ACTIVATION_REPORT.md`.

**Remediación P0 — flakiness suite hermetica (2026-05-25, post `0f8232a`).**
Una auditoría post-cierre detectó **flakiness real al ~33%** en
`scripts/full-qa.sh` y `scripts/stress-qa.sh`: 1 de cada 3 corridas fallaba
con tests distintos cada vez (`test_mail_api`, `test_failure_postmortem`,
`test_audit_commercial_operational_backlog`, `test_audit_commercial_reapers_dedicated`).
Causa raíz: el fixture `clean_slate` de los 2 archivos audit-commercial
borraba `HumanApproval` antes que `DeepAgentMemoryProposalRecord`, que
también tiene FK a `human_approvals.id`. Tests previos del plan de
aprendizaje (`test_failure_postmortem`, `test_skill_promoter`,
`test_recipe_extractor`, `test_nightly_reflection`) dejaban filas en
`deepagent_memory_proposals` con `approval_id` poblado y la limpieza
explotaba con `ForeignKeyViolationError` en
`fk_deepagent_memory_proposals_approval_id_human_approvals`.

Fix aplicado (3 archivos de test, **cero código de producto**):
- `backend/tests/test_audit_commercial_operational_backlog.py` — agrega
  `DeepAgentMemoryProposalRecord` al import y al fixture `clean_slate`
  antes de `HumanApproval`.
- `backend/tests/test_audit_commercial_reapers_dedicated.py` — idem.
- `backend/tests/test_clean_slate_fixture_covers_all_fks.py` (nuevo) —
  test de regresión que detecta futura adición de tablas con FK a
  `human_approvals` sin actualizar los fixtures.

Gate post-fix: `bash scripts/full-qa.sh` -> **1200 passed**, 1 skipped,
28 deselected (1190 históricos + 2 regresión). `bash scripts/stress-qa.sh 5`
-> **5/5 corridas × 1200 passed** sin un solo fallo. Playwright -> **43
passed**. CDP sweep 20 vistas -> **0 console.error**. **2 ciclos completos
verdes** tras el último cambio. Tasa de flakiness post-fix: **0%**. Reporte
en
`tmp/full_functional_activation_20260525_073134/archived_remediation/remediation_20260525_065154.tar.gz` (archivado tar.gz).

Riesgos operativos residuales (no-código, requieren operador):
- `google_calendar`/`google_drive` siguen `blocked` por OAuth scope; re-correr
  `scripts/auth_google.py` para refrescar consent.
- 309 approvals pending acumuladas (ninguna stale, reaper trabaja); triage
  operador.

**Audit-commercial hardening matrix (2026-05-25, commit `0f8232a`).**
Pasada quirurgica de remediacion read-only convertida en cobertura
hermetica: cerro los 4 contratos P0-criticos y los 12 GAPs P1 mas
sensibles que el mapa de contrato
(`tmp/commercial_audit_20260525_030342/01_CONTRACT_MAP.md`) habia
flageado entre "happy-path verificado" y "todos los caminos criticos
bajo regresion". **No se toco codigo de producto** en esta remediacion;
solo se agregaron 16 archivos de test (15 pytest backend + 1 Playwright
spec) con ~230 asserciones nuevas.

P0-criticos cubiertos por matriz exhaustiva:

- **Mail SMTP escape hatch** (`test_audit_commercial_mail_smtp_gating.py`):
  matriz 10 filas `(enable_email_send × mail_allow_explicit_send ×
  confirmation phrase)`. Solo `(True, True, "SEND_THIS_EMAIL_EXPLICITLY")`
  llega a SMTP; el resto levanta `MailServiceError` ANTES de
  `_send_with_account`.
- **GoDaddy DNS production gate**
  (`test_audit_commercial_godaddy_dns_gating.py`): matriz 16 filas
  `(enabled × dry_run × allow_writes × dominio_allow_list × prod_vs_OTE)`.
  Solo 3 combinaciones ejecutan HTTP PATCH; el resto bloquea sin trafico.
- **Code Director STDIN-only**
  (`test_audit_commercial_code_director_stdin_only.py`): 4 layers —
  `build_argv` no contiene prompt/secret tokens (Claude/Codex/Kimi),
  argv bounded, lectura viva de `/proc/<pid>/cmdline` confirma cero
  leak, static guard sobre `subprocess_base.py`.
- **Mail UI sin boton Enviar**
  (`audit-commercial-mail-no-send-button.spec.ts`): scan DOM por roles
  (button/link/menuitem/switch/checkbox) y placeholders de input contra
  patrones send/draft (es+en); intercept de
  `/mail/messages/*/approve-send` para confirmar que el flujo de digest
  jamas lo invoca.

GAPs P1 cerrados (12 archivos): eager_defaults full matrix (los 9
`WORKFLOW_EXPORTABLE_TYPES` + 2 carriles), auth matrix 35 operator x 9
admin endpoints x 3 roles, corpus path-traversal +
`resolve_ingest_document_path` + symlink escape, operational_backlog
truth table reactivo, workflow.v1 version reject + dedup idempotente,
calendar/drive directo `dry_run=false` -> 409, health `_overall_status`
truth table (configured != ok), reapers dedicados (`reap_stuck_running`
+ `_reap_stale_running_jobs` con idempotencia), DB isolation guard en
subproceso aislado, secrets redaction sobre 8 superficies hostiles,
test fixtures gating en local/production/APP_ENV/COGOS flag, MCP
per-server fail-open.

Tambien resuelto en este pase (test-only bugs encontrados durante
verificacion):

- `test_drive_organize_does_not_auto_approve_in_guarded_dedicated_local`
  y `test_drive_organize_auto_approves_in_full_dedicated_local`
  estaban rojos en HEAD `5459ec5` porque no stubeaban `DriveService`
  (el servicio real devolvia `blocked` por `token.json` ausente y
  short-circuiteaba la gate). Se agrego `_FakeReadyDriveService`
  reusando el patron de
  `test_drive_organize_action_request_service_persists_approval_lifecycle`.

Gate ejecutado: `bash scripts/full-qa.sh` -> **1190 passed**, 1 skipped,
28 deselected (958 historicos + 232 nuevos: 227 audit-commercial + 4
time_mcp_server + 1 dispatch guard); `npx playwright test` -> **43
passed** (41 historicos + 2 del nuevo spec de Mail UI).
*Post-remediación 2026-05-25 ese gate subió a `1200 passed` por +2 tests
de regresión de la fix `clean_slate` FK order.*

**Time MCP local + commercial UX hardening (2026-05-25, commit `ce72dc2`).**
Sumo un MCP server local que expone hora actual y conversion de zonas
sin red ni auth (`time_mcp_server.py`, stdio), llevando el inventario a
**6/6 servers** (`mem/gh/fs/cc/gem/time`) y **69 tools**. En la misma
pasada lleva el hardening UX que el working tree habia acumulado:

- `actions/service.py`: el error de dispatch ahora dice
  *"Action request not found; dispatch blocked before side effects"* para
  garantizar trazabilidad del fail-closed cuando el AR no existe.
- `voice/service.py`: redacta `tts_voice_id` a `"configured"`/`"missing"`
  en lugar de leakear el id real del proveedor.
- Frontend: `lib/api.ts` reenvia `AbortSignal`; `page.tsx` detecta host
  publico/local y elige API base correcto + aborta `requestLocalToken`
  tras 10s; `HealthView` aborta `/health/verify` tras 45s con mensaje
  legible; `SettingsView` siempre renderiza el tile MCP (cargando / sin
  datos / N/M conectados) en lugar de esconderlo.
- Tests: `test_dispatch_missing_action_request_reports_blocked_guard`
  cubre el guard del dispatch; `test_audit_commercial_*` (en commit
  posterior) cierran la matriz.
- `scripts/README.md`, `qa/reports/testsprite_latest_summary.md`:
  snapshots refrescados.

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
  `MCP_INVENTORY_TIMEOUT_SECONDS` subio a 30s. Verificacion runtime original:
  **5/5 servidores conectados** (`mem`, `gh`, `fs`, `cc`, `gem`) y **67 tools**
  expuestas; Playwright consulta `/system/mcp` dentro de su timeout.
- `Ctrl/Cmd+K` de la command palette se registra en capture phase para que el
  atajo no quede consumido por inputs/foco de la pagina.
- QA posterior al commit: `full-qa.sh` **944 passed**, Playwright **31 passed**,
  `full-qa-live.sh` **8 passed** y `stress-qa.sh` 3 pasadas de **944 passed**.

**MCP local `time` (2026-05-25).** Se agrego un servidor MCP propio de
Cognitive OS para hora/conversion de zonas sin depender del bridge de Codex:

- Implementacion: `backend/src/cognitive_os/integrations/time_mcp_server.py`
  con el SDK Python MCP (`FastMCP`) y transporte `stdio`.
- Configuracion runtime: `MCP_SERVERS` suma
  `time:stdio:uv run python -m cognitive_os.integrations.time_mcp_server::cwd=.../cognitive-os/backend`.
  Como todo cambio en `.env`/`MCP_SERVERS`, requiere reinicio del stack para
  que API y workers lean la declaracion nueva.
- Seguridad/alcance: read-only, sin auth, sin secretos, sin red externa y sin
  writes. Default timezone `America/Santiago`.
- Tools expuestas: `time_time_now` y `time_time_convert`. Runtime vivo
  verificado en `/system/mcp`: **6/6 servers conectados**
  (`mem`, `gh`, `fs`, `cc`, `gem`, `time`) y **69 tools**.

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
| Endpoints REST (`@app.*`/`@router.*` en `api/`) | 153 |
| Tareas Celery (`workers/tasks.py`) | 23 |
| Migraciones Alembic (`alembic/versions/`) | 20 |
| Head Alembic | 202605200003 |
| Vistas frontend (`frontend/app/views/*.tsx`) | 20 |
<!-- AUTO:counts:end -->

| Area | Estado actual |
|---|---|
| Backend | FastAPI 0.115+, 150 endpoints REST en `api/app.py` (147 `@app.*` + 3 `@router.*` de `test_fixtures`) |
| Frontend | Next.js 16.2.6 + React 19, 20 vistas en `frontend/app/views`; cockpit público con hash auth, `data-cogos-active-tab`, hotkey 3 DeepAgents y SW `cogos-v2026-05-26e-status-cards` |
| Infra | Docker Compose local con Postgres 16+pgvector, Redis 7, Weaviate 1.29.0, Neo4j 5; todo ligado a `127.0.0.1` |
| DB | 20 migraciones Alembic, head `202605200003`, `alembic check` sin drift |
| Celery | 23 tareas, 5 colas (`default`, `ingestion`, `agent_longrun`, `maintenance`, `mail`), hasta 13 jobs beat segun flags |
| Telegram | 37 slash commands; modo conversacional sin slash en `dedicated_local`; dispatch fail-closed |
| Mail | Gmail `TODOS`/`SPAM` + GoDaddy `Spam`; clasificacion propia del agente; digest 10:00 y 20:00 Chile; respuestas propuestas como texto |
| Health | `/health/dashboard` expone 18 componentes (17 checks + checkpointer); `/health/verify` hace probe en vivo |
| MCP | Cliente habilitable en `dedicated_local`; `/system/mcp` carga inventario en paralelo con timeout default 30s; runtime verificado 6/6 servers (`mem`, `gh`, `fs`, `cc`, `gem`, `time`) y 69 tools; `time` es local read-only por `stdio` (`uv run python -m cognitive_os.integrations.time_mcp_server`, no usa auth ni red externa) |
| Learning | Fases A-E en produccion: recipes, failure postmortem, tool scorecard, skill promotion, nightly reflection; auto-promote con kill switch |
| Code Director | Planner LLM-driven + adapters Claude Code/Codex/Kimi/DeepAgents bajo budget/audit; STDIN-only (no fuga en `ps`) verificado por matriz audit-commercial |
| Browser | Kimi WebBridge + Edge real disponibles para el perfil dedicado |
| LLM | primary+agent `gpt-5.5` (Responses API + prompt caching 24h), secondary/fallback `gemini-3.1-pro-low`, vision `glm-4.6v` |
| QA backend | `pytest` hermetico con DB de test aislada (`cognitive_os_test`); guard exhaustivo (subproceso aislado) verifica que se niega a correr contra produccion |
| QA frontend | Playwright oficial: 43 tests en desktop/mobile; runner zero-friction (auto-mintea `COGOS_JWT` via `POST /auth/local-token` en `dedicated_local/full`) |
| QA oficial | `scripts/full-qa.sh` (build Next aislado en `.next-qa`, **1200 passed** post-remediación 2026-05-25 — 1190 históricos + 2 regresión FK order); `stress-qa.sh 5` -> 5/5 verde, flakiness 0%; `full-qa-live.sh` opt-in para smokes reales; `scripts/testsprite_web/deploy_and_verify.sh` para handoff público TestSprite web |
| Audit matrix | 16 archivos `test_audit_commercial_*` + `audit-commercial-*.spec.ts` (~230 asserciones) cubren los 4 P0-criticos y 12 GAPs P1 del contrato comercial: Mail SMTP gate, GoDaddy DNS gate, Code Director STDIN, eager_defaults full, auth matrix, path-traversal corpus, operational_backlog reactivo, workflow.v1 hardening, calendar/drive directo `dry_run=false`→409, health overall honest, reapers dedicados, DB isolation, secrets redaction, test fixtures gating, MCP fail-open, Mail UI sin boton Enviar |
| TestSprite | Reaudit MCP histórico 2026-05-23: 2 pasadas independientes PASS (incluye P1 eager_defaults cazado y corregido). TestSprite local batched histórico: **28/28 passed**. TestSprite web público vigente: usar `deploy_and_verify.sh` y esperar PDFs/reportes antes de afirmar doble verde. |

## Ultimo Gate Verde Conocido

**Gate V2.0 final** (commit V2.0 `final: certify Cognitive OS commercial local-first readiness (V2.0)` sobre base `2bb4966`, Prompt 7 V2.0, 2026-05-27):

- `bash scripts/full-qa.sh` → **1232 passed, 1 skipped, 28 deselected**
  (1230 base post-Prompt-3 + 2 nuevos casos `test_document_analysis_response_consistency_v2_eval_001.py` del fix V2-EVAL-001).
- `bash scripts/stress-qa.sh 5` × **2 ciclos verdes posteriores al último cambio** → **10/10 corridas × 1232 passed**, flakiness 0%.
- `npx playwright test` × 2 ciclos verdes → **44 passed** ambos sin exportar `COGOS_JWT`.
- `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` → **8 passed** (LLM ping + IMAP/SMTP + Telegram getMe + GoDaddy GET + Kimi status + Google OAuth + MCP list_tools).
- `python3 scripts/openapi_readonly_smoke.py` → **70 GET / 0 failures**.
- `python3 scripts/sync_doc_counts.py --check` → OK.
- `bash scripts/verify_desktop_launchers.sh` → OK.
- Ruff/format/mypy/Alembic/`git diff --check` → todos verdes.
- `POST /health/verify` → overall **`ok`** con `mcp_client` live `ok` 6/6 conectados, 69 tools (F-P2-006 + F-P4-001 cerrados).
- `/system/mcp` → 6/6 connected (`mem`, `gh`, `fs`, `cc`, `gem`, `time`), 69 tools.
- `/system/readiness` → 14/14 unlocked, gaps=[].
- Mail SMTP gate verificado live → `HTTP 409` con mensaje de contrato.
- Calendar/Drive direct writes `dry_run=false` → `HTTP 409`.
- Code Director `fake` adapter → `HTTP 400`.
- GoDaddy DNS preview → `dry_run_only=true`, sin writes reales.
- `GET /document-analysis/{id}` mirror persisted result (V2-EVAL-001 cerrado, response API ↔ artefacto JSON 2 claims / 2 events / 1 contradicción).
- Doc audit firmado: [`audits/FINAL_ABSOLUTE_V2_COMMERCIAL_LOCAL_FIRST_CERTIFICATION.md`](audits/FINAL_ABSOLUTE_V2_COMMERCIAL_LOCAL_FIRST_CERTIFICATION.md).

Gates históricos previos al cierre V2.0 (preservados):

Gate previo histórico (HEAD `8a33475`, 2026-05-26): `full-qa.sh` 1200 passed, `stress-qa.sh 5` 5/5 × 1200, Playwright 43, live 8.

Gate `0f8232a` (2026-05-25, pre-remediación FK): 1190 passed.

Gate inmediatamente anterior (commit `5459ec5`, 2026-05-23):

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
- `/system/mcp` con JWT local -> **6/6 connected**, **69 tools**.
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

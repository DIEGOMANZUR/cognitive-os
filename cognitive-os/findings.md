# Findings

> Bitácora viva. Para producto: ver `docs/`.

## 2026-05-19 05:45 — Supervisión horaria #2 + bug frontend (Turbopack HMR) cerrado

Stack: 688 pytest passed; api/worker/beat/frontend(:3001)/kimi running;
docker 4/4 healthy; 0 errores recientes en logs; reaper corre cada 10
min sin jobs stuck reales; `/chat` real `fallback=False`;
`operator_profile=dedicated_local` (four_eyes=False, ttl=168h).
Health global=`degraded` solo por google_calendar/drive `blocked`
(esperan OAuth interactivo del operador).

**Bug crónico cerrado de raíz (P1):** `next dev` (Turbopack) crashea en
HMR/refresh cuando hay lockfiles padres conflictivos
(`~/.opencode/package-lock.json`, etc.). Ni `turbopack.root` ni
`outputFileTracingRoot` lo arreglan completamente — la auto-inference
del workspace root sucede ANTES de leer el config. Next 16 ya no
soporta `--no-turbopack`. **Fix definitivo**: el launcher ahora hace
`next build && next start` (script `serve`). Más estable, más rápido
(Ready 135ms vs 341ms del dev), sin Turbopack runtime, sin HMR. En un
PC dedicado al agente HMR no se necesita; rebuild manual si el operador
edita el frontend.

**Bonus fix**: `is_running_frontend()` reescrito a **port-based check**
(`ss -ltnp sport = :3001` + match de `/proc/$pid/cwd` contra
`FRONTEND_DIR`) en lugar de cmdline. Next 16 reescribe el cmdline a
`next-server (v…)` truncado por el kernel, así que ningún pattern
podía distinguir nuestro `next-server` de otro (p.ej. OpenChamber).
Resultado: el launcher reporta `frontend: running · pid 1876201 ·
http://localhost:3001` correctamente; cero falsos "stopped" más.

## 2026-05-19 — Mi-ultrareview offline (sustituye /ultrareview, falló su servicio)

`/ultrareview` falló del lado del servicio Anthropic
(`firestore: not found` al importar el seed bundle). El operador pidió
hacer la review yo, por partes, sin esperar. Plan: 10 dominios
sistemáticos, 3 por turn con wakeup entre tandas.

**Tanda 1 (dominios 1-3) — esta sesión:**

- **D1 Seguridad/Auth/RBAC/Rate limits:**
  - 130 endpoints, 132 usos de auth dependency, **solo `/health` sin
    auth** (público a propósito).
  - `.env`, `.env.local`, `storage/` correctamente untracked.
  - `SecretStr` no aparece en respuestas API.
  - Hallazgo P2 no urgente: 53 endpoints mutadores no tienen
    rate-limit explícito (`/chat`, `/chat/stream`,
    `/deepagents/research`, `/document-analysis/run`, `/sandbox/run`,
    etc.). Aceptable en `dedicated_local` (un solo operador); a
    considerar para perfil `strict`/multi-cliente.

- **D2 LLM / DeepAgent / Tool calling:**
  - 21 tools / 0 esquemas inválidos (`args_schema` Pydantic).
  - Cadena del router `agent→secondary→primary→deterministic`
    funciona; si el operador cambiara `PRIMARY_LLM_MODEL` a un
    reasoner el último intento devolvería 400 y caería a
    `deterministic` (cubierto por try/except). En la config actual
    (primary=gpt-5.5) no hay riesgo.
  - Usos restantes de `create_primary_chat_model` (planner.py:176,
    graph.py:649/689) son `invoke` plano sin tool_choice — correcto
    que usen el reasoner.

- **D3 Action Plane (correctness crítico):**
  - Drive organize `file_ids` congelados verificado (drive.py:109,
    746, 752, 775; service.py:801, 815).
  - `reserve_action_dispatch` con estados `submitting`/`submitted`/
    `failed` vivos. Sweeper `reap_stale_dispatch_reservations` en
    line 1754 cableado en beat.
  - `_read_action_request_status` y crash-window guard en tasks.py:112.
  - Code Build/OpenShell con guards de `running` (líneas 357, 364, 569).
  - Alembic head `202605170001` (migración Drive folder/organize).

Tanda 1: **0 hallazgos accionables**. Continúa con dominios 4-10 vía
ScheduleWakeup.

**Tanda 2 (dominios 4-6):**

- **D4 RAG / Memoria / Storage:** `ensure_collection()` con
  double-checked locking + `threading.Lock` (race cubierto).
  Embeddings con `embeddings_circuit_breaker` + `retry_transient_http`
  + key rotation pool ante quota errors. BM25 fallback explícito
  (`query_embedding=[]`, `alpha=0`, vector field omitido para no
  emitir GraphQL inválido). SHA256 dedup en ingestion + web_indexer.
  Pipeline `pending_index → indexed` solo tras confirmación Weaviate.
  Batch insert detecta mismatch de vectores y rechaza partial batch.
  **0 hallazgos accionables.**

- **D5 API / Endpoints / Modelos:** CHECK constraint
  `ck_ar_action_type` cubre todo el set persisted del servicio
  (regresión Fase 65 vigente). Tests `test_public_config_does_not_
  expose_secret_shaped_keys` valida que SecretStr no se filtra en
  responses. Migraciones cadena lineal head `202605170001` sin drift.
  **Hallazgo FUTURO (no urgente PC dedicado):** la tabla `jobs` no
  tiene índice compuesto `(job_type, created_at/updated_at)` ni
  `(status, created_at)`. Con 3099 jobs ya acumulados las queries
  (`Jobs` filtered, `/agents` stats, telegram `/jobs`,`/codebuild`)
  hacen full-scan. Aceptable <3 s en un PC dedicado; sería P1 en
  multi-tenant o cuando el histórico crezca a decenas de miles.

- **D6 Workers / Celery / Beat:** beat schedule limpio
  (memory consolidate, reminders /5m, gmail digest diario, mail sync,
  action-request-reaper /10m, approval-reaper :15h). Reapers NO se
  invocan entre sí (sin deadlock). Idempotency dispatch verificada en
  D3. `autoretry_for=TRANSIENT_EXCEPTIONS` solo en 3 tasks
  (ingest/cleanup/mail-sync); las críticas con efecto externo
  (run_action_request, run_code_build, run_openshell) sin autoretry
  por diseño — el operador decide. **Hallazgo FUTURO (P2):** solo hay
  reaper para `ActionRequest.status==running`; **Code Build y
  OpenShell Jobs no tienen reaper** general. Si el worker muere
  mid-execution, esos Jobs quedan `running` hasta cancelación manual.
  Aceptable en PC dedicado (operador ve stuck en `/jobs`); deuda real
  para considerar.

Tanda 2: **0 bugs accionables, 2 hallazgos FUTUROS documentados**.
Continúa con dominios 7-10 vía ScheduleWakeup.

**Tanda 3 (dominios 7-9):**

- **D7 Frontend / PWA / Vistas:** `renderMarkdownLite` es XSS-safe
  (escapa `& < >` primero; regex de URL sólo matchea
  `https?://[^\s<>"']+`, no acepta `javascript:`). Todos los `fetch`
  usan `Authorization: Bearer ${token}`. `usePolledFetch` con
  `AbortController` + cleanup en unmount (sin leaks). El SW excluye
  `/api/*` del cache (sin staleness en respuestas autenticadas).
  JWT en `localStorage` es decisión consciente (SPA estándar, riesgo
  XSS bajo en `dedicated_local`) — marcado FUTURO si se cambiara a
  perfil `strict` multi-cliente. **0 hallazgos accionables.**

- **D8 Telegram bot:** 36 commands registrados, paridad 36/36 con la
  matriz del USER_GUIDE (líneas 629, 653-654 cubren help/done/note/
  task que parecían faltar). `_resolve_approval_id` con whitelist
  hex+dash + min length 4 (previene wildcards `%`/`_`). **BUG P2
  REAL corregido en vivo**: `cmd_job` (telegram_bot.py:436-447)
  insertaba `prefix=arg.lower()` directamente en
  `ilike(f"{prefix}%")` sin la misma whitelist —`/job %` matcheaba
  cualquier job y devolvía el primero (no era vector externo por
  estar el bot detrás de `allowed_user_ids`, pero rompía la
  semántica si el operador pegaba un id mal). Fix idéntico al
  patrón ya probado en `_resolve_approval_id`. Regresión añadida:
  `test_cmd_job_rejects_sql_wildcard_prefix` (con `%` y con `_`,
  ambos hacen `must not query DB`). Race approve/reject: cubierta
  por `decide_approval` (servicio compartido con el panel) que tira
  `ApprovalAlreadyDecidedError` ante doble decisión. Sin command
  injection — `cmd_chat` va al grafo LangGraph (prompt injection es
  inherente al LLM, no SQL/shell), `cmd_ingest` pasa la ruta vía
  Celery args (serializado por kombu, no shell).

- **D9 Infra / Launchers / Migraciones:** 17 migraciones lineales
  sin ramas, head `202605170001`. `verify_desktop_launchers.sh`
  pasa (4 wrappers + 4 `.desktop` files + master). Sintaxis bash
  OK en master + verify. Sin `eval`/`rm -rf`/`sudo`/
  `--privileged` en ninguno de los scripts. `docker-compose.yml`
  con bind `127.0.0.1` en todos los puertos expuestos +
  healthchecks definidos + `restart: unless-stopped`.

Tanda 3: **1 bug P2 corregido (cmd_job SQL wildcards) con regresión
en tests**; D7 y D9 limpios. Continúa con D10 (Docs / coherencia +
reporte unificado) vía ScheduleWakeup.

## 2026-05-19 — Revisión final doble (post Fase 68b)

**Revisión #1**: 11 markdowns en Fase 68 sin headers rezagados; suite
**688 passed**; ruff/format/mypy (125 source files) verde; alembic head
`202605170001`; pre-commit 6/6 OK; git diff --check CLEAN; los 7 fixes
de Fase 68b siguen vivos (21 args_schema, 4 file_ids refs Drive, 3
missing_scopes refs Cal/Drive, 5 budget_mode refs config + director,
5 operator_profile refs config + 4 app, `_read_action_request_status`
helper + crash-window guard, `reap_stale_dispatch_reservations` cableado
en beat, outputFileTracingRoot).

**Bug encontrado en la revisión y corregido en vivo**: el frontend había
quedado caído tras el relaunch anterior (HTTP 000 en :3001, sin proceso
`next` nuestro). Causa: Next reescribe `next-env.d.ts` y la inferencia
automática del workspace root corre ANTES de leer `turbopack.root` del
config; con lockfiles padres (`~/.local/package-lock.json`,
`~/.opencode/package-lock.json`) Next falla con "couldn't find
next/package.json from <project>/app". Fix: agregado
`outputFileTracingRoot: __dirname` en `frontend/next.config.mjs`
(Next 16 lo usa para resolver además de `turbopack.root`). Build verde
y `next dev` arrancó limpio (Ready 341ms, GET / 200) tras el relanzamiento
vía `Reiniciar Cognitive OS.sh`.

**Revisión #2** (segunda pasada limpia post-#1): los 7 fixes intactos,
`next-env.d.ts` correctamente untracked, `alembic check` sin drift, suite
crítica focal (worker/drive/config/system_info) 50 passed, full-qa exit
0 (`OK: full-qa`). Stack vivo: docker (4/4 healthy) + api + worker + beat
+ frontend(:3001 reportado correctamente) + kimi; telegram correctamente
"stopped" (token 401 sigue pendiente del operador). `/system/info`
expone `operator_profile=dedicated_local`, `/chat` real sin fallback.

## 2026-05-19 — Fase 68b: revisión GPT-5.5 + perfiles + 7 hallazgos cerrados

Revisión cruzada de GPT-5.5 sobre Fase 65-68. Acepté lo correcto,
debatí 2 puntos por daño irreversible (browser-real con sesiones de
Edge, mail autosend) y los implementé como "opt-in explícito visible"
en lugar de wildcard silencioso. Lo demás corregido con el mismo rigor
(lint/mypy/tests/regresión, sin commitear). Suite final
**688 passed**, +3 vs Fase 68.

**P0 — defaults LLM desalineados:** `config.py:170` y `.env.example:46/48/57/59`
seguían apuntando fallback/vision-fallback a Kimi HTTP (403 garantizado).
Cambiados a la cadena verificada (gemini/glm). 4 docs unificados al
claim correcto (DeepSeek → cadena verificada gpt-5.5).

**P0 — Code Director "budget caps duros" sobreafirmado:** docs prometían
hard pero el adapter timeout era fijo (600s) y el budget se revisaba
post-call. Implementado `CODE_DIRECTOR_BUDGET_MODE=soft|hard`:
  - `soft` (default, recomendado para PC dedicado): el current subtask
    termina su CLI; budget cierra el BUILD `partial` entre subtasks.
  - `hard`: gate pre-call, aborta subtask al instante si cap excedido.

**P1 — Code Build / OpenShell sin guard de duplicado:** llevados al
patrón ya usado por `run_action_request_task_async` (Fase 66): guard
"job ya running ⇒ short-circuit con `skipped:true`". El ActionRequest
worker ya tenía guard pero el de Job-only podía cortar prematuro: ahora
también lee el estado del **ActionRequest** y, si está aún `queued`,
asume crash window y procede (execute_action_request es atómico). +1
test de regresión que cubre el escenario crash-window.

**P1 — Sweeper `dispatch_state` stale:** nuevo
`reap_stale_dispatch_reservations` (cableado en `reap_stuck_action_
requests_task`, mismo beat). Si un proceso muere entre
`reserve_action_dispatch` (deja `submitting`) y el `submitted`/`failed`
event, la reserva quedaba sticky para siempre. El sweeper flippea a
`failed` tras un threshold, permitiendo re-dispatch.

**P1 — Drive organize re-buscaba al ejecutar (CRÍTICO, contradice
human-approval).** `drive.organize_files` hacía `provider.list_files`
en preview y otra vez en ejecución → aprobar plan A, mover plan B. Fix:
`DriveOrganizeRequest.file_ids` se congelan en el preview y el execute
path **mueve exactamente esa lista** (con `get_file` por id; archivos
borrados entre approve/execute se omiten, jamás se sustituyen). +2
regresiones explícitas. Mismo principio que el fix Fase 15 de
`computer_organize`.

**P1 — Google OAuth scopes sin validación:** `GoogleCredentialsLoader`
solo chequeaba `valid/expired`. Calendar/Drive podían decir `ready`
faltando `calendar.events` o `drive` (write). Añadidos
`granted_scopes()` / `missing_scopes()` al loader y cableados en los
`status()` de Calendar y Drive: si falta un scope necesario, status
pasa a `blocked` con guía exacta de re-auth + lista
`missing_scopes` en la respuesta.

**P2 — `next-env.d.ts` frágil en checkout limpio:** importaba
`./.next/dev/types/routes.d.ts` (generado local, gitignored) → `tsc
--noEmit` rompía en CI / clones nuevos. Next reescribe el archivo en
cada build con la ruta estable `./.next/types/routes.d.ts`. Solución:
**gitignorar `next-env.d.ts`** — Next es la fuente de verdad,
desindexado del repo. Build verde.

**Perfiles de operación:** nuevo `OPERATOR_PROFILE=strict|dedicated_local`.
`dedicated_local` afloja TTL (48→168h), four-eyes (off), aprobación
externa (off), budget mode (soft) **solo donde el operador no fijó
explícitamente otra cosa** (`model_fields_set`). Las relajaciones con
daño irreversible (browser wildcard, mail autosend) NO son default
silencioso — el perfil las documenta y recomienda en
`docs/USER_GUIDE.md` "Perfiles de operación" + "Setup PC de Diego";
quedan visibles en `/config/public` (campo `operator_profile`) cuando
el operador las activa. El operador set `OPERATOR_PROFILE=dedicated_local`
en `.env` (PC dedicado + Edge real).

**USER_GUIDE reescrita:** sección 8 era "Cómo NO usar Cognitive OS"
(estricta, contradice PC dedicado). Reescrita como "Perfiles de
operación: Estricto vs PC dedicado" con tabla por capacidad. Sección 9
nueva: "Matriz de acciones" — qué corre solo / qué pide aprobación /
cómo aflojarlo, incluida documentación de CapSolver y los reaper
sweepers. Header del USER_GUIDE corrige el overclaim "verificado en
vivo": separa lo realmente probado (chat / Maps / CORS) de lo
"implementado y `ready` con credenciales".

**`/config/public` expone `operator_profile`** para que el frontend
pueda mostrar el banner del perfil activo en el header del panel
(decisión visible, no oculta).

## 2026-05-19 — Fase 68c: stack levantado + frontend/CORS fixes + supervisión

**Arranque del stack (vía wrapper de escritorio real):** docker
(pg/redis/weaviate/neo4j healthy) + api (/health ok) + worker + beat +
frontend + kimi-webbridge arriba; telegram correctamente omitido (token
401). Verificado end-to-end: `/chat` → router LLM + DeepAgent reales sin
fallback; CORS preflight `:3001`→API = 200.

**Bugs reales encontrados y corregidos en el arranque:**

- **Frontend `next dev` no levantaba (2 causas):** (1) Turbopack
  mis-inferia el workspace root (path con espacio + lockfiles padre) →
  `couldn't find next/package.json`. Fix: `turbopack: { root: __dirname }`
  en `next.config.mjs`. (2) Puerto 3000 ocupado por **OpenChamber**
  (otra app del operador) → EADDRINUSE. El launcher hacía `kill_port
  3000` que **mataría OpenChamber**. Fix: frontend movido a `:3001`
  (coexiste, no mata otra app); `FRONTEND_PORT=3001` en el maestro.
- **CORS bloquearía el panel:** default solo permitía `:3000`; con el
  frontend en `:3001` el navegador bloquearía las llamadas al API. Fix:
  `CORS_ALLOW_ORIGINS` explícito en `.env` con `:3001` y `:3000`.
  Verificado: preflight OPTIONS desde `:3001` → 200.
- **Launcher reportaba frontend "stopped" estando vivo:**
  `FRONTEND_CMD_PATTERN="next dev"` no matchea el cmdline real
  (`node …/cognitive-os/frontend/…`, el wrapper npm no conserva "next
  dev"). Fix: patrón `cognitive-os/frontend` (específico, no colisiona
  con omniroute) + grabar el PID real del `next` tras el health-check.
  Verificado: status ahora `frontend: running · :3001`.
- Docs (`USER_GUIDE`, `README`, `RUNBOOK`, `ARCHITECTURE`,
  `COGNITIVE_OS_GUIDE`) actualizados a `:3001`.

**Supervisión profunda #1 (baseline):** todos los procesos arriba; api/
beat.log 0 errores; worker.log 1944 errores son histórico acumulado de
días (la actividad reciente —`sync_personal_mail` cada ~2 min— es 100%
"succeeded", 0 errores recientes). Los "12 running" de `knowledge/stats`
= 7 running + 5 queued; los 7 son jobs stale viejos (`integration_test`
×5 + `personal_mail_sync` ×2, creados 2026-05-12..16, de tests
antiguos) — benignos, no defecto, no erroran. docker 4/4 healthy.
Sistema sano y trabajando. Próximas supervisiones: cada 1 h vía
ScheduleWakeup con análisis profundo.

## 2026-05-19 — Fase 68b: revisión profunda doble + hallazgos

**Revisión #1 (zonas débiles, post Fase 65-68):**

- **Telegram token INVÁLIDO (bloqueante, requiere operador).** El
  `TELEGRAM_BOT_TOKEN` en `.env`
  (`8742030714:AAFcJi…`) devuelve **HTTP 401 Unauthorized** en `getMe`
  (probado con httpx, el mismo cliente del bot). Está revocado o es
  erróneo. Además `TELEGRAM_AUTHORIZED_USER_IDS` está vacío (aunque el
  token fuese válido, el bot rechazaría a todos). No se puede levantar
  Telegram funcional sin: (a) token válido nuevo de @BotFather, (b) el
  user_id autorizado. El resto del stack NO depende de esto.
- **Auditoría sistemática de alias `.env` ↔ Settings:** 197 vars `.env`
  vs 254 alias. Las 14 sin alias son intencionales (env-var-only:
  GITHUB/HF/SUPERMEMORY; MCP GitHub; y las KIMI_/GLM_ANTHROPIC de
  referencia). **No hay otro bug de no-op tipo `ENABLE_GODADDY`.**
- **`KIMI_CODING_*`/`KIMI_ANTHROPIC_*` son solo referencia:** el adapter
  `kimi` del Code Director invoca el binario `kimi` CLI que lee su
  propio `~/.kimi/...`; no consume esas vars (no hay alias). Comentario
  en `.env` corregido para no inducir a error.
- **Degradación elegante verificada:** si el gateway LLM cae, el router
  agota agent→secondary→primary y termina en `deterministic_route` (sin
  crash); el DeepAgent cae a RAG. Sin punto único de fallo duro.
- Baseline de revisión: **685 passed, 1 skipped, 20 deselected**;
  ruff/mypy (125 files) limpios; alembic head `202605170001`; backend
  vivo y `/health` ok.

## 2026-05-19 — Fase 68: GoDaddy DNS producción + bugfix alias config

- **Credenciales GoDaddy producción verificadas en vivo:** auth contra
  `api.godaddy.com` → HTTP 200 (devuelve dominios reales de la cuenta).
  Antes el operador había mandado por error la key OTE (probada: solo
  funciona contra `api.ote-godaddy.com`, 200; contra producción 400
  `UNABLE_TO_AUTHENTICATE`). Demostrado con pruebas reales que GoDaddy
  exige Key **y** Secret (`Authorization: sso-key KEY:SECRET`); solo-key
  da 401 `MALFORMED_CREDENTIALS`.
- **Bug de config detectado y corregido:** la línea `.env` decía
  `ENABLE_GODADDY=false`, pero el campo `Settings.godaddy_enabled` tiene
  alias **`GODADDY_ENABLED`** (no `ENABLE_GODADDY`). `ENABLE_GODADDY` era
  un **no-op**: aunque se pusiera `true`, GoDaddy nunca se habilitaba.
  Corregido en `.env` y en `docs/guia_credenciales.md` (que también
  documentaba el alias equivocado).
- **Postura segura:** `GODADDY_ENABLED=true` pero
  `GODADDY_DNS_DRY_RUN_ONLY=true` + `GODADDY_ALLOW_PRODUCTION_WRITES=false`
  → capability `ready`, `requires_approval=True`, `dry_run_only=True`:
  ninguna escritura DNS real hasta opt-in explícito del operador.
- Credenciales (prod + OTE) guardadas en `.env` y Supermemory MCP.
  Inventario: `GODADDY_API_KEY/SECRET configured=True`.

## 2026-05-18 — Fase 67: esquemas de tools tipados + cadena LLM del operador

**Causa raíz del tool calling (más profunda que el modelo).** Probando
el gateway del operador (`gpt-5.5` @ `http://100.120.183.68:8317/v1`)
el DeepAgent fallaba con `400 "Invalid schema for function
'search_local_docs'"`. No era el modelo: era que **las 21 tools del
DeepAgent se construían con `StructuredTool.from_function(func=lambda
...)`**; los lambdas no tienen anotaciones, así que LangChain emitía
propiedades **`{}` vacías** (`"query": {}`). DeepSeek las toleraba;
gateways estrictos OpenAI-compatible (gpt-5.5) las rechazan. Esto era
un bug de calidad latente — el sistema dependía de la indulgencia del
proveedor.

**Fix (calidad real, no parche).** Se definieron `args_schema`
Pydantic explícitos para las 21 tools (tipos + descripciones por
parámetro + validación + bounds donde aplica), reflejando 1:1 las
funciones tipadas subyacentes. Verificado: `convert_to_openai_tool`
sobre las 21 → **0 propiedades vacías/sin-tipo** (antes `{}`).
97 tests tool/deepagent/factory verdes.

**Cadena LLM definida por el operador, verificada en vivo** (httpx +
LangChain `with_structured_output`):

| Orden | Modelo | Endpoint | tool_choice forzado | Uso |
|---|---|---|---|---|
| 1 DEFAULT | gpt-5.5 | gateway :8317 | ✅ 200 | primary + agent |
| 2 / 1er fb | gemini-3.1-pro-low | gateway :8317 | ✅ 200 | secondary |
| 3 / 2º fb | gemini-3.1-pro-low | gateway :8317 | ✅ 200 | fallback |
| 4 / 3er fb | kimi-k2.6 | api.kimi.com/coding/v1 | ❌ **403** | solo CLI Code Director |
| visión | glm-4.6v | api.z.ai/.../paas/v4 | 200 (multimodal) | vision + vision_fb |

**Honestidad sobre Kimi:** `kimi-k2.6` vía HTTP da **403 "Kimi For
Coding is currently only available for Coding Agents such as Kimi CLI,
Claude Code..."** — gatekeeping por tipo de cliente (también el
Anthropic-type). NO se cableó como fallback HTTP (sería un 403
garantizado, anti-infalible); queda donde sí funciona: el adapter
`kimi` (subprocess CLI) del Code Director. Kimi visión idem → la
visión primaria es GLM-4.6v (verificado HTTP 200), no Kimi.

**Clase de bug expuesta: tests no-herméticos del grafo.** Varios tests
ejecutaban `build_graph(...).invoke()` o `/chat` SIN estubear el router;
"pasaban" solo porque el modelo viejo fast-fallaba (deepseek-v4-pro
tool_choice 400 en ms → `deterministic_route`). Con gpt-5.5 el router
hace una llamada LLM real al gateway → no-determinista, lento, flaky
(`APITimeoutError` 117s en un caso; `"Human approval required."` vs
`"No hay evidencia suficiente"` en otro, según lo que devolviera el
gateway). Detectados: `test_orchestrator_legal_node_document_analysis::
test_graph_adds_document_analysis_result_to_messages` y
`test_api::test_chat_and_thread_roundtrip_with_auth` (más
`test_chat_stream`, `test_orchestrator_deepagents_integration` en
riesgo).

**Fix infalible y DRY (no whack-a-mole):** nuevo `tests/conftest.py`
con un fixture **autouse** `_disable_real_llm_factories` que hace
*raise* a TODAS las factory de modelo
(`create_{agent,secondary,primary,fallback}_chat_model` en
`agents.graph` + `deepagents.factory.create_agent_chat_model`) por
defecto. Así NINGÚN test del suite default puede hacer una llamada LLM
real: el router cae a `deterministic_route` y la DeepAgent factory
nunca abre socket. Tests que quieren LLM inyectan
`router_llm=FakeRouterLLM(...)` (no tocan factories) o estubean su
propio modelo en el cuerpo (corre después del fixture, gana). Los
tests `integration`/`slow` quedan exentos. Resultado: suite completa
**685 passed, 1 skipped, 20 deselected en ~22s** (antes 53-65s y
flaky) — ahora hermético por construcción y determinista.

**Verificado end-to-end live:** `/chat` "teorema CAP" →
`route=research`, `deepagent_fallback=False`, respuesta correcta,
**0 errores de schema/tool_choice/400 en todo el log del backend**.
El router LLM (gpt-5.5) decide de verdad. health dashboard: todo
ok/configured salvo Calendar/Drive `blocked` (esperan OAuth operador).
Credenciales guardadas en `.env` y en Supermemory MCP.

## 2026-05-18 — Fase 66b: el bug tool_choice también afectaba al ROUTER

Ante la pregunta del operador "¿DeepSeek V4 sigue fallando con
tool_choice?": **sí, `deepseek-v4-pro` (=reasoner) no soporta y nunca
soportará `tool_choice` forzado — es límite del modelo, no se arregla
del lado nuestro.** El fix correcto es no invocarlo con tool_choice
forzado en ningún carril. Auditando esto a fondo se encontró un
**segundo punto** además del DeepAgent: `agents/graph.py:route_request`
usa `llm.with_structured_output(RouterDecision)` (que internamente
fuerza tool_choice). La cadena previa intentaba secondary→primary, y
tras el repoint Fase 66 *ambos* eran `deepseek-v4-pro` → el router
**siempre** caía a `deterministic_route`: el router LLM nunca corría
(routing degradado a heurística, silencioso). Los demás usos del
primary (`graph.py:635/675` borradores comm/social, `planner.py:176`
Code Director) usan `invoke` plano (texto, sin tool_choice) → OK.
Fix: el router usa `create_agent_chat_model()` (`deepseek-chat`,
tool-capable) primero, con secondary/primary/deterministic como
degradación. Verificado live: el router LLM ahora decide de verdad
(`route=social`/`research` según la query), respuestas limpias, y
**0 ocurrencias de "does not support this tool_choice" en todo el log
del backend**. Suite: **685 passed**. Conclusión: `deepseek-v4-pro`
sigue sin tool_choice (esperado e inarreglable), pero ya **no se lo
invoca así en ningún carril**; los carriles que necesitan tool_choice
forzado (DeepAgent + router) usan `deepseek-chat`.

## 2026-05-18 — Fase 66: auditoría EN VIVO con credenciales reales — 4 bugs críticos

Con el stack levantado de verdad (Docker infra + backend + worker +
credenciales reales del operador) se auditó cómo reacciona cada parte.
La resiliencia del sistema **enmascaraba** fallos serios: los carriles
caían a fallback y nadie veía que el carril principal estaba muerto.

**Bug 1 — DeepAgent nunca funcionó (severidad ALTA).**
`/chat` devolvía `"DeepAgent failed; Cognitive OS used direct RAG
fallback."`. Causa: el DeepAgent usa structured output
(`response_format=DeepAgentResult`) que fuerza un `tool_choice`
específico; el modelo primario `deepseek-v4-pro` resuelve a
`deepseek-reasoner`, que responde **HTTP 400 "deepseek-reasoner does
not support this tool_choice"**. *Todo* DeepAgent (research, document,
analysis) degradaba silenciosamente a RAG. Verificado en vivo:
`deepseek-chat` con tool_choice forzado → 200; `deepseek-v4-pro` → 400.
Fix: nuevo `create_agent_chat_model()` (config `AGENT_LLM_MODEL`,
default `deepseek-chat`, reusa key/base del primary); el carril de
agente usa modelo tool-capable y el chat/razonamiento sigue con el
reasoner. Confirmado live: `/chat` → `fallback=False`, respuesta limpia.

**Bug 2 — SECONDARY/FALLBACK/VISION_FALLBACK LLM con 403 garantizado.**
La key Kimi es de "Kimi For Coding" y el endpoint
`api.kimi.com/coding/v1` **rechaza clientes HTTP openai-compatible**
("only available for Coding Agents such as Kimi CLI, Claude Code...").
SECONDARY (resúmenes) y FALLBACK (circuit breaker abierto) estaban
garantizados a 403. La key Kimi SÍ sirve en el Code Director (adapter
`kimi` por subprocess CLI — no afectado). Fix: repuntados
SECONDARY/FALLBACK a DeepSeek y VISION_FALLBACK a GLM-4.6v. Verificado
live: los 6 carriles LLM (primary/secondary/fallback/vision/
vision_fb/embeddings) → HTTP 200.

**Bug 3 — LangSmith dropeaba TODAS las trazas (403).**
`configure_langsmith()` exportaba `LANGSMITH_API_KEY` (lsv2_sk_, scoped):
`/info` 200 pero `/runs/multipart` y `/sessions` **403 Forbidden**. El
operador tiene además `LANGSMITH_PERSONAL_ACCESS_TOKEN` (lsv2_pt_) con
scope de escritura. Fix: `configure_langsmith()` prefiere el personal
access token (mismo orden que ya usaba el `/runs` de Telegram).
Verificado live: `/sessions` → 200, trazas ingresan.

**Bug 4 — Maps traffic-aware SIEMPRE 400.**
`/actions/maps/route` con `traffic_aware=true` (default) devolvía 400.
La key Maps es válida (status `ready`, geocoding OK). Causa: el código
seteaba `departureTime = datetime.now(UTC)`; para cuando el request
llega a Google ya es **pasado** y Routes API responde
**"Timestamp must be set to a future time."**. Aislado en vivo:
`now` → 400; `now+120s` → 200. Fix en `actions/maps.py`: el default
(y clamp de cualquier valor pasado/cercano) usa `now + 60s`, con
normalización de datetimes naive. Verificado live: ruta real
`19.5 km · 25 min · tráfico leve · 12 pasos`.

**Endurecimiento de tests (hermeticidad).** Las acciones legítimas de
guardar credenciales en `.env` (encryption key, Gmail flags) expusieron
que varios tests construían `Settings(...)` leyendo el `.env` real del
operador. 7 tests pasados a herméticos con `_env_file=None`
(`test_config.py` ×2, `test_actions.py` ×4 vía Settings, helper de
`test_credentials_status.py`), + `tests/test_deepagents_factory_skills_memory.py`
actualizado al nuevo símbolo `create_agent_chat_model`, +
`SETTINGS_REGISTRY_TABLE.md` regenerado por los nuevos `AGENT_LLM_*`.
Suite: **685 passed, 1 skipped, 20 deselected**.

**Observación (no-bug):** `knowledge/stats` reportó 12 jobs en
`running`: data stale de sesiones de desarrollo previas (el reaper
Celery los cierra; no es código introducido). El `degraded` global del
health dashboard es **solo** por `google_calendar`/`google_drive`
`blocked` (esperan el OAuth interactivo del operador, `auth_google.py`).

**Estado vivo verificado:** postgres/redis/weaviate/neo4j `ok`,
checkpointer Postgres real, worker Celery `ok`, langsmith `ok` (token
correcto), voice/maps/captcha/webbridge `ready`, gmail `configured`,
chat→DeepAgent real funcionando, ruta Maps real funcionando, migración
crítica `202605170001` aplicada en Postgres real (CHECK incluye
drive_ensure_folder/drive_organize_files — confirmado por query directa).

## 2026-05-17 — Fase 65: paridad UI↔Telegram + bugfix CHECK constraint

### Auditoría completa "pies a cabeza" (sesión final pre-entrega)

**Baseline** verificada antes de tocar nada:

- `bash scripts/full-qa.sh` → **674 passed, 1 skipped, 20 deselected**.
- `bash scripts/stress-qa.sh` → 3 corridas idénticas, 674 cada una.
- `uvx pre-commit run --all-files` → 6 hooks pass.
- `docker compose -f infra/docker-compose.yml --env-file .env.example config --quiet` → pass.
- `uv run alembic check` → sin drift (head `202605160002`).
- Frontend `lint`/`build` → OK (Next.js 16.2.6, 20 vistas, manifest+SW PWA OK).

**Mapeo cruzado FE↔BE**: las 44 rutas REST únicas usadas por el frontend
(`app/views/*.tsx`, `app/components/*`, `app/page.tsx`) están cubiertas
por los 131 endpoints definidos en `api/app.py`. 0 paths huérfanos.

**Bug crítico encontrado y corregido (Postgres-only, no detectable con
tests actuales)**: el CHECK constraint `ck_ar_action_type` definido en el
ORM `db/models.py` solo permitía hasta `drive_upload_file`, pero los
servicios (`actions/service.py:770,812`) crean ActionRequest con
`drive_ensure_folder` y `drive_organize_files`. Los endpoints
`/actions/drive/folders/ensure/request` y `/actions/drive/organize/request`
disparaban `CheckViolation` en Postgres real y devolvían 500. La suite no
lo detectaba porque `_install_fake_action_session` monkeypatch
`session_scope` y nunca round-trippea a la DB.

Fix aplicado:

- Migración `alembic/versions/202605170001_action_requests_drive_folder_organize.py`
  amplía el constraint para incluir ambos tipos.
- `ActionRequest.__table_args__` actualizado para que ORM y DB
  permanezcan alineados.
- Test de regresión `tests/test_action_request_check_constraint.py`:
  lee el CHECK del ORM y del último archivo de migración y los compara
  contra `WORKFLOW_EXPORTABLE_TYPES` del servicio. Si alguien agrega un
  action_type al servicio pero olvida actualizar el ORM/migración, el
  test falla.

**Telegram bot: paridad UI**. Auditados los 25 commands previos y las 20
vistas del frontend. Se identificaron 11 dominios sin slash y se agregaron:

- `/maps origen | destino` — ruta read-only con tráfico + advice +
  link Google Maps + alternativas.
- `/calendar [max]` — próximos eventos.
- `/freebusy [días]` — disponibilidad primary.
- `/drive <query>` — búsqueda Drive read-only.
- `/documents [max]` — documentos ingestados (Postgres).
- `/audit [max]` — últimos audit events.
- `/mail [max]` — bandeja mail multicuenta.
- `/research [max]` — research orchestrator runs.
- `/codebuild [max]` — code-director builds.
- `/sandbox` — estado openshell sandbox.
- `/capabilities` — flags de action plane.

Todos los handlers respetan capacidades habilitadas (Maps/Calendar/Drive
status, `MAIL_ENABLED`, `ENABLE_OPENSHELL_SANDBOX`, etc.) y errores se
serializan a Markdown seguro vía `_safe_md_fragment`. Cubiertos con 9
tests focalizados (`test_telegram_bot.py`).

**Falsos positivos secrets**: `telegram_bot.py:548` tenía un set de
caracteres hex (los dígitos 0-9, las letras a-f en ambas cajas y el
guion) usado para validar prefijos UUID; detect-secrets lo marcaba
como Base64HighEntropyString. Anotado con `# pragma: allowlist secret`
para mantener el baseline limpio sin mover el código.

**Snapshot QA post-cambios**:

- `uv run pytest -q` → **685 passed, 1 skipped, 20 deselected** (+11).
- `uv run ruff check .` / `ruff format --check` / `uv run mypy src` → verdes.
- `uvx pre-commit run --all-files` → 6 hooks pass.
- `bash scripts/full-qa.sh` → OK.
- `bash scripts/verify_desktop_launchers.sh` → OK.
- `bash scripts/init_credentials.sh` (modo no-`--ci`) → reporta sólo REQ
  pendientes propios del host (no del repo).

**Pendiente operador (no requiere código)**:

1. Completar credenciales OPT del operador si va a usar Google
   Calendar/Drive write (correr `python scripts/auth_google.py` una
   vez).
2. Pegar `TELEGRAM_BOT_TOKEN` y `TELEGRAM_AUTHORIZED_USER_IDS` en
   `.env` y poner `TELEGRAM_ENABLED=true`.
3. Aplicar migraciones a Postgres con `uv run alembic upgrade head`
   (sube el nuevo `202605170001`).
4. Si usa Production: `ENVIRONMENT=production` aplica los validators
   estrictos (no admite CHANGEME, exige aprobación humana en browser/
   computer/mail/godaddy/calendar/drive, exige Postgres backend para
   research, exige cifrado de payload).

## 2026-05-17 — Fase 64: dispatch idempotente antes de Celery

Hallazgo tras cerrar dispatch durable:

- El sistema ya toleraba fallos de broker y entregas duplicadas en worker, pero
  dos llamadas casi simultáneas a dispatch podían pasar por `queued` y ejecutar
  dos `apply_async()` antes de que el worker cambiara el job a `running`.

Corrección aplicada:

- `ActionRequestService.reserve_action_dispatch()` bloquea la fila y escribe
  `metadata_json.dispatch_state="submitting"` antes de llamar a Celery.
- Un dispatch con estado `submitting` responde "dispatch already in progress";
  con `submitted` responde "waiting for worker"; con `failed` permite retry.
- `record_action_dispatch_event()` actualiza la metadata a `submitted` o
  `failed`, borra la reserva y conserva el `JobEvent`.
- REST y Telegram usan la reserva antes de `apply_async`.
- Verificación focal: **72 passed** en tests actions/worker/Telegram/approval;
  ruff, ruff format y mypy verdes.
- Cierre QA: `bash scripts/full-qa.sh` → **674 passed, 1 skipped,
  20 deselected**, ruff/format/mypy, Alembic, frontend lint/build y
  `git diff --check` verdes.

## 2026-05-17 — Fases 59-63: dispatch durable y observabilidad

Hallazgos tras revisar el borde aprobación → broker Celery:

- `POST /actions/requests/{id}/dispatch` encolaba con `apply_async()` sin
  capturar fallos del broker. Si Redis/Celery no aceptaba la tarea, el operador
  recibía un 500 genérico aunque la `ActionRequest` ya podía quedar `queued`.
- REST no dejaba un `JobEvent` explícito que diferenciara "despaché a Celery"
  de "falló antes de que Celery aceptara".
- Telegram ya reportaba fallo de Celery al usuario, pero no dejaba el mismo
  rastro estructurado de JobEvents.
- El worker ya preservaba estados terminales ante retries, pero una entrega
  duplicada mientras el job estaba `running` todavía podía agregar eventos
  `running/not_executed` innecesarios.

Correcciones aplicadas:

- `ActionRequestService.record_action_dispatch_event()` centraliza eventos de
  submit/fallo de dispatch.
- REST dispatch captura errores del broker y devuelve
  `ActionDispatchResponse(dispatched=false, reason=...)`, manteniendo el request
  en `queued` para retry.
- REST y Telegram registran `action_request_dispatch_submitted` o
  `action_request_dispatch_failed` según corresponda.
- `run_action_request_task_async` short-circuitea si el job ya está `running`,
  sin ejecutar el servicio ni volver a escribir eventos.
- Cierre QA: `bash scripts/full-qa.sh` → **671 passed, 1 skipped,
  20 deselected**, ruff/format/mypy, Alembic, frontend lint/build y
  `git diff --check` verdes.

## 2026-05-17 — Fases 50-58: bloque 3 operativo

Hallazgos tras revisar superficies humanas y scripts diarios:

- `/approvals` en Telegram muestra sólo los primeros 8 caracteres del UUID,
  pero `/approve` y `/reject` exigían UUID completo. Es una fricción real y
  propensa a error para operación móvil.
- El adaptador Telegram llamaba `decide_approval(..., approver_user_id="telegram")`.
  Eso reduce trazabilidad y puede activar four-eyes de forma incorrecta si una
  solicitud fue creada por un actor genérico `telegram`.
- El resolver de payload OpenShell en Telegram estaba declarado como async y se
  envolvía con `_run()` dentro de la coroutine que ya corría bajo `_run()`.
  Si se aprobaba un OpenShell desde Telegram, podía disparar un
  `RuntimeError` por event loop anidado.
- El helper compartido `decide_approval()` decide aprobaciones y cascada de
  rechazo, pero el dispatch de `ActionRequest` aprobado queda en el adaptador.
  El panel lo hace; Telegram todavía no. Eso dejaba una aprobación móvil como
  "approved" pero sin trabajo encolado.
- Los launchers de escritorio existen y están endurecidos, pero faltaba un
  verificador versionado que cualquier QA pueda ejecutar para comprobar rutas,
  permisos y sintaxis sin levantar el stack.

Correcciones aplicadas:

- `_resolve_approval_id()` acepta UUID completo o prefijo único, rechaza
  prefijos ambiguos/cortos y filtra caracteres fuera de UUID para evitar
  wildcard SQL accidental.
- `_decide_approval()` firma como `telegram:<chat_id>` y reutiliza el resolver
  síncrono de payload OpenShell del API.
- `_dispatch_approved_action_request()` encola y despacha ActionRequests
  aprobados desde Telegram, reportando en el mensaje si Celery aceptó el job.
- `scripts/verify_desktop_launchers.sh` valida maestro, wrappers, `.desktop`,
  permisos ejecutables y sintaxis Bash con defaults del host y overrides de CI.
- Cierre QA: `bash scripts/full-qa.sh` → **669 passed, 1 skipped,
  20 deselected**, ruff/format/mypy, Alembic, frontend lint/build y
  `git diff --check` verdes.

## 2026-05-17 — Fases 45-49: Google operativo avanzado

Hallazgos tras revisar el bloque Google posterior a Fase 44:

- Drive upload seguía demasiado acoplado a `COMPUTER_ALLOWED_ROOTS`. Eso era
  seguro, pero débil como producto: los entregables generados por Cognitive OS
  bajo `DOCUMENT_OUTPUT_ROOT` o workspaces DeepAgents podían quedar bloqueados
  si el operador no duplicaba rutas manualmente.
- Abrir todo `LOCAL_STORAGE_DIR` habría sido peligroso porque ahí vive
  `storage/oauth`; la solución correcta es permitir sólo
  `LOCAL_STORAGE_DIR/workspaces` y raíces explícitas de salida.
- "Ordenar Drive completo" no debe implementarse como write masivo directo. El
  patrón comercial es preview acotado (máximo 50 archivos), `ActionRequest`,
  aprobación, ejecución auditada y sin deletes.
- Google Drive documenta mover archivos mediante `files.update` con
  `addParents`/`removeParents`; el provider real usa ese contrato y conserva
  `supportsAllDrives=true`.
- Google Calendar `freeBusy` es la superficie correcta para agenda proactiva:
  devuelve bloques ocupados sin crear ni modificar eventos.

Correcciones aplicadas:

- `DriveFile` ahora conserva `parent_ids`; `DriveProvider.move_file` y
  `DriveService.organize_files` agregan preview/execute para
  `drive_organize_files`.
- `DriveUploadRequest` permite fuentes de entregables del sistema sin exponer
  `storage/oauth`.
- `CalendarService.freebusy`, endpoint `/actions/calendar/freebusy` y tool
  `check_calendar_freebusy` quedan read-only.
- DeepAgents suma `preview_drive_organization` (sin writes directos) y
  `GoogleOpsView` suma controles de free/busy y organización Drive.

## 2026-05-17 — Fase 44: Google Ops como capa comercial del agente

Auditoría inicial solicitada por el operador: la documentación y el código
confirman que Google Maps/Calendar/Drive ya están implementados, pero el uso
comercial aún puede mejorar:

- Maps (`actions/maps.py`) ya calcula ruta con tráfico y link Google Maps, pero
  la respuesta carece de consejo operativo/ETA/severidad; el frontend muestra
  duración y pasos, no una recomendación clara.
- Drive (`actions/drive.py`) ya lista por `name contains`, lee metadata y sube
  archivos con `ActionRequest`, pero "buscar algo en todo Drive" requiere modo
  `fullText contains`/`all`; la carpeta de entregables sólo se crea como efecto
  de un upload aprobado, no como solicitud aprobable independiente.
- DeepAgents expone `plan_route`, `geocode_address`, `list_calendar_events`,
  `search_drive_files`; falta que `search_drive_files` pueda buscar contenido
  y que Maps devuelva advice legible para el agente.
- La UI `GoogleOpsView` existe y es funcional, pero aún no ofrece modo de
  busqueda Drive ni request explícito de carpeta.

Docs oficiales revisadas antes de tocar API Google:

- Drive API v3: `files.list` acepta `q`; Google documenta `name contains`,
  `fullText contains`, `mimeType` y `trashed = false`.
- Routes API: `computeRoutes` requiere field mask explícita y soporta
  `computeAlternativeRoutes`, `routeLabels`, `duration` y `staticDuration`.

Correcciones aplicadas en esta fase:

- `DriveSearchRequest` deja de limitarse a `name contains`; ahora soporta
  `fullText contains`, modo combinado `all`, filtros de carpetas/mime y
  `corpus=all_drives` con `supportsAllDrives`.
- Nuevo carril aprobable `drive_ensure_folder`: endpoint, `ActionType`,
  workflow, `ActionRequestService`, executor y pruebas.
- `RoutePlan` ahora incluye advice, ETA y severidad calculada desde
  `duration-staticDuration`; `compute_alternatives` se propaga al Routes API.
- `GoogleOpsView` y DeepAgents reflejan esos contratos.

## 2026-05-17 — Fase 43: auditoría desde cero + dos fixes reales

Tras cerrar Fase 42 el operador pidió revisar todo el monorepo buscando
defectos, mejoras y cosas implementables. Auditoría capa por capa:

- Backend: `ruff` clean, `mypy` clean (125 fuentes), `mypy --strict` en
  code_director + deepagents clean (37 fuentes). 0 `datetime.utcnow()`
  deprecado, 0 `requests.*` sin timeout, 0 `httpx.AsyncClient()` sin
  timeout, 0 `except: pass` real, 0 imports sucios. 126 endpoints —
  todos con auth excepto `/health` (correcto).
- Frontend: `npm audit` 0 vulns, `eslint --max-warnings 0` pass,
  `tsc --noEmit` 0 errores, `next build` verde.
- Config: 251 ENV en `config.py`, todas presentes en
  `SETTINGS_REGISTRY_TABLE.md` (gap 0).
- Tests: 100 archivos de test, 638 passed (Fase 42), stress 2 corridas
  idénticas (28.56s / 26.47s).
- Migraciones: 16 archivos Alembic, todos con `downgrade` definido (10
  con cuerpo vacío — add-only, correcto).
- Seguridad: 0 secretos en código, baseline `detect-secrets` íntegra,
  rate-limit pegado a los 3 endpoints sensibles
  (`approval_decision`/`action_dispatch`/`action_request_create`).
- Skills registry: path-traversal de `user_id` rechazado correctamente
  (`../core` y `../../etc` retornan `[]`).

**Dos defectos reales detectados y cerrados** (`0347ffd`):

1. **`LLMPlanner` cap descartaba al reviewer si estaba en posición >12.**
   El cap `raw_subtasks[:12]` truncaba ciegamente, contradiciendo la
   regla del schema hint "the LAST subtask MUST be a reviewer". Fix:
   detectar reviewer en la cola del payload original y preservarlo
   reemplazando el item 12 del head.
2. **Rejection de `fake` adapter sin cobertura paramétrica en sub-roles.**
   `_reject_fake_adapter_request` ya inspeccionaba los 4 sub-roles, pero
   el test API sólo cubría `default_adapter='fake'`. Agregado test
   parametrizado para `planner/coder/reviewer/tester_adapter='fake'`.

Suite: **642 passed, 1 skipped, 20 deselected** (+5 vs Fase 42).
Compuertas verdes en backend (ruff/format/mypy) y frontend (lint/build).

Sin P0/P1 conocidos pendientes con cierre técnico viable post-Fase 43.
Pendiente operador: OAuth Google (1 click) si quiere Calendar/Drive —
no aplica a este carril.

## 2026-05-17 — Fase 42: legal-pack desde claude-for-legal (Apache 2.0)

Después de cerrar F9 el operador pidió que aplicara la integración con
`https://github.com/anthropics/claude-for-legal`. Análisis del repo: 13
plugins, todos bajo Apache 2.0, ninguno portable verbatim porque
dependen del plugin system de Claude Code/Skills SDK. Decisión: portar
**patrones, rúbricas y estructuras de output** —no código— al
`DeepAgentSkillsRegistry` propio.

Filtro aplicado para no inflar: descartar todo lo que duplica capacidad
ya existente (`evidence_matrix`, `contradictions`, `timeline_builder`,
`claim_chart`, `tabular_review`, `legal_draft` ya viven como modos del
`DocumentAnalysisView`). Selección final de 5 skills que llenan gaps
reales:

- **`legal-hold`** (approval_required) — issue/refresh/release/report
  de holds con output JSON estricto + `notice_text` draft (jamás envía).
- **`privilege-log-review`** (read_only) — rúbrica de 4 chequeos
  (descripción suficiente, recipients roleables, ground sostenido,
  fecha consistente) con issues por entry_id.
- **`oss-license-review`** (read_only) — compliance OSS frente al
  modelo de distribución (proprietary SaaS/on-prem/Apache/GPL/internal);
  clasifica permissive/weak/strong copyleft/source-available; severidad
  info/warn/block; detecta `NOTICE` faltante.
- **`worker-classification`** (read_only) — employee vs contractor con
  el test correcto por jurisdicción (ABC California, economic reality
  DOL post-2024, IRS common-law, UK multi-factor); factor table con
  confidence y deciding factors; nunca asume jurisdicción.
- **`matter-intake`** (approval_required) — preview de `matter.md`
  normalizado + primera cronología; duplicate-check via workspace
  memory; jamás escribe hasta aprobar.

Cumplimiento Apache 2.0: `skills/core/NOTICE.md` con atribución
explícita; modificaciones bajo la misma Apache 2.0 para mantener
compatibilidad downstream. No se copió código upstream — sólo
estructura conceptual.

Tests 5 focales (`test_deepagents_skills_legal_pack.py`): discovery,
allow-list de tools, risk_levels esperados, atribución presente, no
shadow de skills legacy. Suite: **637 passed, 1 skipped, 20
deselected**. Pre-commit + detect-secrets verdes.

## 2026-05-17 — Fase 41: Code Director F9 (planner LLM + prompts con contexto)

El operador pidió "dejar listo al máximo nivel f9": que el director sea
genuinamente capaz para apps complejas, no sólo que "ande". Dos
debilidades reales de la Fase 40 que cerramos:

1. El plan era un esqueleto fijo (scaffold→implement→review): para "una
   app con 2 RAGs + frontend" eso es insuficiente.
2. El prompt a cada coding agent era una línea ciega: re-scaffoldeaba lo
   ya hecho, ignoraba lo que produjeron las dependencias y en reintento
   repetía el mismo enfoque que falló.

- **F9a** `planner.py`: `Planner` Protocol; `HeuristicPlanner`
  (determinista, extraído del viejo `_heuristic_plan`, sigue siendo el
  fallback) y `LLMPlanner` (pide al LLM primario un JSON de subtareas,
  valida roles, descarta deps alucinadas y auto-deps, cap 12 subtareas,
  asigna adapter/modelo por rol). `_extract_json` tolera prosa y
  fences ```json. Cae al heurístico ante **cualquier** excepción. El
  seam `llm_completion` es inyectable. Hallazgo en pruebas: el
  `LLMPlanner` por defecto pegaba a la DeepSeek real (key en
  `.env.local`) y colgaba la suite — se fijó `HeuristicPlanner`
  explícito en las 4 construcciones de director de tests.
- **F9b+F9c** `prompt_builder.py`: `build_subtask_prompt()` arma un
  prompt estructurado y acotado: árbol del workspace, contenidos
  relevantes (paths esperados + archivos tocados por upstream), resumen
  de cada dependencia directa (F9b); en reintento, bloque
  error-dirigido con error/stderr/exit-code y "no empieces de cero"
  (F9c). Topes duros en cada inclusión + path-containment (jamás lee
  fuera del workspace). `director.run/_run_subtask` hilan los
  `StepResult` por subtarea para alimentar a las dependientes; se
  eliminó el `_build_prompt` estático F1.
- **F9d** smoke E2E `test_code_director_f9_smoke.py`: prueba offline que
  el plan LLM corre una descomposición custom (≠ heurístico) y que el
  prompt downstream lleva workspace + upstream; y que un primer intento
  fallido produce un reintento distinto y error-dirigido.

Cierre: **632 passed, 1 skipped, 20 deselected**; ruff/format/mypy (14
fuentes code_director) verdes; pre-commit (6 hooks) Passed;
detect-secrets clean. Sin tokens reales en ningún test (FakeAdapter +
stub `llm_completion` + `HeuristicPlanner` fijado). El plan sigue
pasando por `HumanApproval` antes de gastar nada.

## 2026-05-17 — Fase 40: Code Director (delegación a coding agents)

Nueva capacidad pedida por el operador: "darle un objetivo y que el
agente llegue a una app probada delegando a coding agents externos
(Claude Code / Codex / Kimi CLI o DeepAgents), sin que el operador
escriba los prompts".

Diseño elegido: **director pattern**, no auto-coding. El meta-agente
planifica, somete el plan a `HumanApproval`, y al aprobarse delega cada
subtarea al adapter elegido. Construido en 8 fases pequeñas, commit por
fase, sin gastar tokens reales en tests (FakeAdapter + fake bash binary).

- **F1** `code_director/{schemas,director}.py` + `adapters/{base,fake}.py`:
  Protocol `CodingAgentAdapter`, planner heurístico, topo-sort con
  detección de ciclos, budget tracker (runtime/calls/USD), skip de
  dependientes si falla una subtarea. 12 tests.
- **F2** `adapters/deepagent.py`: adapter in-process sobre DeepAgents
  `research`; nunca raise, mapea status→StepResult. 7 tests.
- **F3/F3b/F3c** `adapters/{subprocess_base,claude_code,codex,kimi}.py`:
  prompt por STDIN (no argv → no fuga en `ps`), timeout SIGTERM→SIGKILL
  del process group, never-raise. 11 tests con fake bash binary, 0
  tokens.
- **F4** `code_director/service.py`: `CodeDirectorService.create_build`
  persiste `Job(code_build, waiting_approval)`+`HumanApproval` sin gastar
  nada; `run_build` (post-approval) corre el director y empaqueta el
  workspace en `tar.gz`. Reusa Job/HumanApproval/AuditEvent → reaper +
  four-eyes + audit symmetry aplican igual. 5 tests.
- **F5** Celery task `cognitive_os.run_code_build` (queue
  `agent_longrun`) + wiring en `decide_approval`: aprobar
  `run_code_build:<id>` encola el build desde REST o Telegram. 1 test
  nuevo en decide_approval helper.
- **F6** 4 endpoints REST (`/code-director/run|{id}|/events|/download`),
  rate-limited, SSE, download con path-containment a
  `DOCUMENT_OUTPUT_ROOT/code_builds/`. 5 tests.
- **F7** `CodeDirectorView.tsx` + `streamCodeBuildEvents`: form objetivo
  + adapter/modelo/budget, tabla de plan, warn-box de aprobación, SSE
  timeline, descarga `tar.gz`. lint/build verdes.
- **F8** E2E: 2 tests que escriben archivos reales y verifican el
  `tar.gz` + manifest, incluido el caso `partial` por budget.

Verificación de cierre: **609 passed, 1 skipped, 20 deselected**;
ruff/format/mypy verdes; frontend lint/build verdes; pre-commit (6
hooks) Passed; detect-secrets clean (un marcador de test silenciado con
pragma).

Garantía comercial: el director **no codifica en su proceso ni gasta un
token hasta que el operador aprueba el plan**. Antigravity y Claude
Desktop quedan fuera por no tener modo headless (decisión documentada
con el operador, no es debilidad del sistema). Los CLIs externos se
autentican con sus propias credenciales; el director no inyecta keys.

## 2026-05-17 - Fase 39 cierre de riesgos residuales

Cuatro mejoras concretas para neutralizar los tres riesgos residuales
declarados en Fase 38 que SÍ admiten cierre técnico, y minimizar al máximo
el único que es físicamente imposible cerrar (OAuth Google primer click,
inherente al flujo Desktop OAuth).

Hallazgo 39.1 - Rate limiter sólo single-replica:

- Severidad: P1 escalabilidad.
- Evidencia: el limiter histórico vivía in-proc y vetaba multi-replica.
- Correccion: `RateLimiter` ahora es `Protocol`; dos backends:
  `InMemoryRateLimiter` (default) y `RedisRateLimiter` (sliding window con
  sorted set + pipeline ZREMRANGEBYSCORE/ZCARD/ZADD/EXPIRE). Settings
  nuevos `RATE_LIMIT_BACKEND` (memory|redis) y `RATE_LIMIT_REDIS_URL`. El
  Redis backend **falla open** ante outage, nunca bloquea legit traffic.
- Verificacion: 9 tests focal (5 memory + 4 redis con fake client cubriendo
  allow, block, isolation, fail-open, reset). Suite **555 passed**.

Hallazgo 39.2 - Credenciales pendientes sin observabilidad runtime:

- Severidad: P2 ops.
- Evidencia: la matriz de 21 credenciales vivía solo en RUNBOOK; un
  operador no podía consultar desde el sistema mismo cuáles faltaban.
- Correccion: nuevo modulo `core/credentials_inventory.py` con la matriz
  declarativa (`CredentialSpec`) y `build_status()`. Endpoint admin
  `GET /system/credentials-status` retorna `{total, configured,
  missing_required, items}` con booleans + `how_to_obtain`; **jamás
  valores**. Test de defensa-en-profundidad busca marcadores
  secret-looking en la respuesta y confirma que no se filtran.
- Verificacion: 7 tests (resolución de attrs vs Settings, placeholder
  detection, REQ vs OPT split, env-var credentials, admin gate,
  estructura, no-leak). Suite **562 passed**.

Hallazgo 39.3 - OAuth Google primer click "manual":

- Severidad: P2 friccion. NO completamente eliminable.
- Evidencia: la primera autorización requiere que un humano abra un
  navegador (inherente al flujo OAuth Desktop). El operador histórico
  necesitaba re-autorizar cada vez que el access_token expiraba.
- Correccion en lo cerrable:
  * `scripts/auth_google.py` ahora detecta si `token.json` existe y es
    refresheable; corre `GoogleCredentialsLoader.load()`, que refresca
    transparentemente el access_token usando el refresh_token y reescribe
    el archivo. Sólo abre browser la primera vez o ante revocación real.
  * `_check_calendar` / `_check_drive` en `core/health.py` enriquecen el
    detail cuando el motivo es token faltante: agregan el comando exacto
    a correr y la nota "los refresh tokens son automáticos".
- Verificacion: 4 tests para `_google_token_instructions`. Suite
  **566 passed**.

Hallazgo 39.4 - Sin wizard CLI para bootstrap de credenciales:

- Severidad: P2 onboarding.
- Evidencia: el operador podía leer el RUNBOOK pero no tenía un comando
  unificado que listara su estado real.
- Correccion: `scripts/init_credentials.sh`:
  * Garantiza .env (delega en init_env.sh).
  * Consume `/system/credentials-status` si el API responde; fallback a
    `build_status()` inline en Python.
  * Checklist tres-columnas (OK ✓ / REQ ✗ / OPT ○) + instrucción exacta
    + resumen + opción `--ci` para gate de pipeline (exit 1 si REQ
    faltan).

Cierre Fase 39:

- Suite: **566 passed, 1 skipped, 20 deselected** (+4 vs 562 de Fase 38B).
- Stress 3 corridas idénticas → 566 cada una, sin flakiness.
- full-qa, verify_operator_ready, pre-commit (6 hooks), detect-secrets
  baseline → todos verdes.
- Smoke wizard live: 15/21 configuradas, 0 REQ faltantes, 6 OPT pendientes
  documentadas con su comando.

Declaracion honesta de lo único que queda físicamente imposible:

**La primera autorización OAuth de Google requiere un browser controlado
por un humano.** El estándar OAuth 2.0 Desktop Flow no admite consent
programático — el usuario debe interactuar con el screen de Google una
vez. Después de eso, el refresh_token resuelve todo automáticamente.
Esto NO es un punto débil de Cognitive OS: es el contrato del protocolo
OAuth.

Otras credenciales externas (DeepSeek, Gemini, GoDaddy, etc.) son
configuración pura: el operador las pega en .env. El wizard
`init_credentials.sh` reporta exactamente cuáles faltan y dónde obtenerlas.

Sin P0/P1/P2 conocidos pendientes que admitan cierre técnico. Sistema
listo para uso comercial.

## 2026-05-16 - Fase 38 revision personal desde cero post-37

Operador pidio revision personal completa, sin agentes intermediarios, con
plan de perfeccionamiento en 7 fases (A-G). Cada bloque revisado dos veces
antes de commit y verificado contra suite completa.

Hallazgo 38.1 - Documents sin escritura atomica:

- Severidad: P2 datos/durabilidad.
- Evidencia: `DocumentActionService.execute` escribia DOCX/XLSX/PPTX directo
  sobre el output_path. Un crash de proceso a mitad de `Document.save()`
  dejaba un archivo corrupto en el output_root visible al operador como
  documento "real".
- Correccion: nuevo flujo staged-rename. Se escribe en `.{name}.tmp`,
  se valida tamano, se hace `Path.replace` atomico al final. Si el writer
  crashea, el `finally` borra el tmp; el final path nunca queda
  parcial-escrito. Sin re-escaneo del filesystem.
- Verificacion: nuevo `tests/test_atomic_doc_write.py` ->
  `test_successful_write_leaves_no_tmp_files` y
  `test_writer_failure_does_not_corrupt_existing_final` pasan; suite
  amplia 535 passed.

Hallazgo 38.2 - Sin correlation IDs trazables a logs:

- Severidad: P2 observabilidad.
- Evidencia: cada request generaba logs sin un id estable. Encadenar un
  error reportado por el usuario con sus logs requeria buscar por timestamp.
- Correccion: middleware FastAPI honra `X-Request-ID` (cap 64 chars) o
  genera uuid4, lo bindea a `structlog.contextvars` y lo echa de vuelta en
  la respuesta. `core/logging.py` ahora incluye `merge_contextvars` como
  primer processor, asi cada log heredado dentro del request carga
  `request_id` sin instrumentacion manual.
- Verificacion: `tests/test_correlation_id.py` (4 casos: echo, generacion,
  truncado, endpoint autenticado) -> verde.

Hallazgo 38.3 - Sin rate limiting por usuario en endpoints sensibles:

- Severidad: P1 operacional/abuso.
- Evidencia: una loop de UI o script malintencionado podia martillar
  `/approvals/{id}/approve` o un creator de ActionRequest. Solo
  idempotency dedupaba pero no protegia de DOS local.
- Correccion: `core/rate_limit.py` con sliding-window in-proc por
  `(user_id, bucket)`, expuesto como dependencia FastAPI. Aplicado a:
  approve/reject (30/min), dispatch (60/min) y los 8 creators de
  ActionRequest (30/min). 429 incluye header `Retry-After`.
- Verificacion: `tests/test_rate_limit.py` (4 casos: allow, block,
  isolation por user/bucket, singleton) -> verde.

Hallazgo 38.4 - /system/info sin commit SHA ni Alembic head:

- Severidad: P2 observabilidad.
- Evidencia: un operador no podia confirmar a 1 click que build esta
  corriendo (cual commit) ni en que migracion. Solo `/health/dashboard`
  daba un acercamiento por componente, no por release.
- Correccion: `_resolve_git_commit` corre una vez en startup, lee
  `git rev-parse --short=12 HEAD` con timeout 2s, devuelve None fuera de
  repo. `_resolve_alembic_head` walks la carpeta `alembic/versions` sin
  abrir Alembic CLI. Ambos se exponen en `SystemInfoResponse`.
- Verificacion: `tests/test_system_info.py` actualizado para verificar
  presencia de `git_commit` y `alembic_head`.

Hallazgo 38.5 - Celery retry overwrite de job ya terminal:

- Severidad: P1 datos/idempotency.
- Evidencia: si un worker crasheaba *despues* del DB commit pero *antes*
  del ACK Celery, el broker reenviaba la task. La logica de
  `run_action_request_task_async` re-entraba y sobrescribia el outcome
  ya escrito (potencialmente `completed` -> `failed`).
- Correccion: el task lee `_read_job_status` antes de tocar nada. Si el
  job ya esta `completed|failed|cancelled|rejected`, retorna inmediatamente
  con `skipped=true` y la razon.
- Verificacion:
  `test_run_action_request_short_circuits_when_job_already_terminal` ->
  verde; los dos tests historicos siguen pasando con el nuevo monkeypatch
  de `_read_job_status`.

Hallazgo 38.6 - Frontend sin error boundary global:

- Severidad: P2 UX/resiliencia.
- Evidencia: una excepcion en cualquier view (race condition, contrato
  roto, render error) blanqueaba todo el cockpit. El operador no podia
  recuperar sin recargar manualmente.
- Correccion: `app/components/ErrorBoundary.tsx` envuelve children en
  `layout.tsx`. Una excepcion deja arriba el cockpit y muestra un
  fallback recoverable con boton Reintentar y mensaje legible.
- Mejora adicional: 429 ahora propaga `Retry-After` al mensaje del Error
  thrown por `ApiClient`, y `statusClass` reconoce `expired` como badge
  gris (no danger rojo).

Hallazgo 38.7 - Idempotency key sin contrato testeado:

- Severidad: P2 cobertura.
- Evidencia: `_idempotency_key` es el hinge del dedup story (aplicativo +
  UNIQUE index + worker short-circuit) pero no tenia tests propios.
- Correccion: `tests/test_idempotency_key.py` con 7 properties:
  estabilidad, independencia de orden de keys, distincion por action_type,
  distincion por payload, manejo de unicode/emoji, list-ordering importa,
  formato sha256 hex.

Capacidades agregadas en Fase 38:

- Setting `APPROVAL_PENDING_MAX_HOURS` (default 48) + Celery beat
  `approval-reaper` que transiciona pending -> expired tras el cap.
- Endpoint `GET /system/info` con `git_commit`, `alembic_head`, defaults
  de policy.
- Rate limiting per-(user, bucket) sliding window.
- Correlation IDs propagados a logs y respuesta.
- Atomic writes en document generation.
- Index parcial UNIQUE para idempotency a nivel BD.
- Index composito `(status, created_at)` en human_approvals.
- ErrorBoundary frontend global.
- RUNBOOK con matriz de 21 credenciales y comandos de bootstrap desde cero.

Cierre Fase 38 - certificacion final personal:

- `bash scripts/full-qa.sh` -> OK con alembic check + git diff guards.
- `bash backend/scripts/verify_operator_ready.sh` -> OK head
  `202605160002`.
- `uvx pre-commit run --all-files` -> Passed (large-files, merge-conflict,
  EOF, trailing whitespace, gitleaks/detect-secrets).
- `uvx --from detect-secrets detect-secrets scan` -> `"results": {}`.
- `bash scripts/stress-qa.sh 3` -> 3 corridas de 535 passed sin
  flakiness, ~25-26s cada una.
- `git diff --check` -> clean.

Suite snapshot final: **535 passed, 1 skipped, 20 deselected**.
Migraciones vigentes: **16** (head `202605160002`).
Ruta git: rama `codex/fase-34-baseline-hardening`, 20 commits limpios
desde el snapshot de entrada.

Declaracion de grado comercial:

- Lifecycle ActionRequest completo (previewed -> running -> terminal),
  protegido contra dispatch duplicado, idempotency a nivel aplicativo +
  DB, four-eyes en approvals, reaper de pending stale, audit symetrico
  entre REST y Telegram.
- RBAC explicito (no admin implicito), encryption at-rest opcional
  exigida en produccion, secret redaction global, SSRF check para
  browser y Kimi.
- Observabilidad: correlation IDs, AuditEvent por decision, JobEvent por
  transicion, health dashboard con componentes redactados, /system/info
  con commit y head.
- Resiliencia: error boundary frontend, atomic writes documents, retry
  Celery short-circuit, circuit breakers LLM/embeddings, timeouts HTTP.
- QA: 535 passed, 0 flaky, alembic sin drift, ruff/format/mypy verdes,
  pre-commit + detect-secrets verdes, frontend lint/build verdes.

Riesgos residuales (declarados, no ocultos):

1. **OAuth Google manual**: `GOOGLE_TOKEN_DIR/token.json` no se fabrica
   por codigo; requiere browser una sola vez. Inherente al flujo Desktop
   OAuth.
2. **Rate limit in-proc**: si despliegan multiples replicas del API,
   el limiter no comparte estado. Mitigacion ya disenada: la interfaz
   `RateLimiter` admite swap a Redis sin tocar callers.
3. **Telegram /approve**: registra AuditEvent pero no cascadea
   `rejected` a ActionRequest ligado. Recomendado decidir desde el panel
   REST que si cascadea.
4. **Credenciales pendientes manuales**: 21 variables externas no
   prepopulables (Gmail/Google/Maps/DeepSeek/Tavily/Brave/Exa/HF/LangSmith/
   Telegram/Supermemory/Context7/Github/GoDaddy/ElevenLabs). RUNBOOK
   seccion "Bootstrap desde cero" indica donde obtener cada una.
5. **Stack opcional**: OpenChamber/OpenCode son cockpit, no runtime.
   No requieren exposicion externa.

Sin P0/P1 conocidos pendientes. Sistema listo para completar credenciales
y comenzar uso real.

## 2026-05-16 - Fase 37 auditoria integral por capas

Arranque:

- El operador pidio no limitarse a scripts y revisar el proyecto entero parte
  por parte antes de conectar todo.
- Criterio epistemico: no prometer "no hay nada mas por mejorar"; convertirlo
  en evidencia: cero P0/P1 abiertos, QA reproducible, contratos alineados y
  riesgos residuales explicitos.
- Baseline vigente: rama `codex/fase-34-baseline-hardening`, commits hasta
  `b5f13db`, full QA/readiness/pre-commit verdes previos, runtime core healthy.

Matriz de auditoria:

| Capa | Pregunta critica | Estado |
|---|---|---|
| Docs/claims | Lo que se promete coincide con codigo y comandos reales | in_progress: drift de Celery detectado y corregido |
| Backend/API | Endpoints, schemas, auth y errores son consistentes | in_progress: auth coverage script sin rutas privadas expuestas |
| DB/migraciones | Modelos y Alembic estan en head y sin drift obvio | in_progress: Alembic check sin drift tras excluir tablas runtime |
| Action Plane | Writes externos solo via approval + audit | in_progress: approvals inmutables corregido |
| Agents/memory | LangGraph/DeepAgents/research/memoria no rompen contratos | in_progress: OpenShell HITL dispatch corregido |
| Frontend | Vistas/tipos/API client soportan estados reales | in_progress: lint/build y PublicConfig 66/66 verdes |
| Infra/runtime | Compose/scripts/health conectan sin exposicion accidental | in_progress: Compose config y core services healthy |
| Seguridad | Secret hygiene, redaccion, cifrado, SSRF/path/RBAC | pending |
| QA/CI | Local y CI cubren lo que dicen cubrir | in_progress: backend amplio 497/1/20 + frontend build verdes |

Hallazgo 37.1 - Celery docs/runtime y rutas de tareas largas:

- Severidad: P1 operacional.
- Evidencia: el runtime registra 14 tareas `cognitive_os.*`, pero la
  documentacion viva todavia declaraba 11. Ademas,
  `cognitive_os.run_deepagent_task` y `cognitive_os.run_action_request`
  quedaban sin ruta explicita y por defecto podian caer en `default`, mezclando
  trabajo largo/externo con tareas rapidas.
- Correccion: documentacion principal sincronizada a 14 tareas; ambas tareas
  quedan ruteadas a `agent_longrun`.
- Verificacion: `uv run pytest tests/test_celery_config.py -q` -> **3 passed**;
  `uv run ruff check src/cognitive_os/workers/celery_app.py
  tests/test_celery_config.py` -> verde.

Hallazgo 37.2 - Aprobaciones humanas mutables:

- Severidad: P1 seguridad/operacion.
- Evidencia: `_decide_approval` permitia cambiar una aprobacion ya decidida
  (`approved`, `rejected`, `edited`, `expired`) con una llamada posterior al
  endpoint contrario. En acciones externas esto rompe la inmutabilidad esperada
  del rastro humano.
- Correccion: solo approvals en `pending` pueden decidirse; cualquier estado
  terminal devuelve `409 Approval already decided`.
- Verificacion: `uv run pytest
  tests/test_actions.py::test_approval_decision_is_immutable
  tests/test_actions.py::test_dispatch_action_request_enqueues_worker
  tests/test_actions.py::test_dispatch_action_request_does_not_enqueue_non_queued_status
  -q` -> **3 passed**; `uv run ruff check src/cognitive_os/api/app.py
  tests/test_actions.py` -> verde.

Hallazgo 37.3 - Lifecycle incompleto en approvals con job vinculado:

- Severidad: P1 operacional.
- Evidencia: rechazar una approval no cerraba inmediatamente el `Job` ni el
  `ActionRequest` vinculado; ademas, OpenShell podia crear una approval
  (`needs_approval`) sin payload ejecutable durable para despachar la tarea tras
  aprobarla desde la UI.
- Correccion: `_decide_approval` propaga `rejected` a job/action request,
  registra `JobEvent`; OpenShell guarda payload ejecutable protegido en el job y
  al aprobar encola `run_openshell_task_async` en `agent_longrun`.
- Verificacion: `uv run pytest
  tests/test_actions.py::test_approval_decision_is_immutable
  tests/test_actions.py::test_openshell_approval_dispatches_queued_job
  tests/test_actions.py::test_rejected_approval_closes_linked_job_and_action_request
  tests/test_actions.py::test_dispatch_action_request_enqueues_worker -q` ->
  **4 passed**; Ruff verde; `uv run mypy src` -> success en 108 source files.

Hallazgo 37.4 - Alembic autogenerate queria borrar tablas runtime de LangGraph:

- Severidad: P1 datos/durabilidad.
- Evidencia: `uv run alembic check` detectaba operaciones de borrado para
  `checkpoints`, `checkpoint_writes`, `checkpoint_blobs` y
  `checkpoint_migrations`, tablas creadas por `PostgresSaver` y no por los
  modelos SQLAlchemy del producto.
- Riesgo: una migracion autogenerada sin filtro podia destruir checkpoints y
  continuidad de conversaciones/runs.
- Correccion: filtro `include_name`/`include_object` versionado en
  `cognitive_os.migrations.autogenerate`, usado por `alembic/env.py`.
- Verificacion: `uv run alembic check` -> "No new upgrade operations detected";
  `tests/test_alembic_autogenerate.py` -> **2 passed**; Ruff/mypy verdes.

Checks de capa sin hallazgo nuevo:

- Frontend: `npm run lint` y `npm run build` verdes con Next.js 16.2.6; contrato
  `/config/public` alineado con TypeScript (**66 backend / 66 frontend**, sin
  faltantes).
- Infra: `docker compose -f cognitive-os/infra/docker-compose.yml --env-file
  cognitive-os/.env config` OK; `bash cognitive-os/infra/wait_for_services.sh`
  -> all services healthy.
- Backend amplio: `uv run pytest -m 'not integration and not slow' -q` ->
  **497 passed, 1 skipped, 20 deselected**; Ruff/format y `git diff --check`
  verdes.
- Cierre de compuertas: `bash scripts/full-qa.sh`, `uvx pre-commit run
  --all-files`, detect-secrets sobre versionados y
  `backend/scripts/verify_operator_ready.sh` verdes. Alembic current=head:
  `202605150002`. Docker core: Postgres, Redis, Weaviate y Neo4j healthy en
  `127.0.0.1`.

Hallazgo 37.5 - Integracion OCR no estaba compatible con batch insert:

- Severidad: P2 cobertura/integracion.
- Evidencia: `uv run pytest -m integration -q` fallaba en
  `test_ingests_image_pdf_with_tesseract_when_available` cuando Tesseract esta
  instalado: el fake `RecordingStore` solo implementaba `insert_chunk`, pero el
  pipeline real usa `batch_insert_chunks`.
- Correccion: `RecordingStore` soporta `batch_insert_chunks`, preservando la
  semantica del fake y cubriendo el camino OCR real.
- Verificacion: `uv run pytest -m integration -q` -> **18 passed, 1 skipped,
  499 deselected**; Ruff/format del test verde.

Smoke operativo autenticado:

- JWT local generado con roles `admin`/`operator`.
- Endpoints vivos respondieron **200**: `/config/public`, `/health/dashboard`,
  `/actions/capabilities`, `/jobs`, `/approvals`.
- Estado runtime: API, Celery worker, Celery beat, frontend y Kimi corriendo;
  Telegram queda apagado por configuracion (`TELEGRAM_ENABLED=false`).

Hallazgo 37.6 - Runtime healthy con bloqueo OAuth Google explicito:

- Severidad: P2 operacional/manual.
- Evidencia: `/health/dashboard` en runtime vivo devuelve `status=degraded`
  porque `google_calendar` y `google_drive` estan `blocked` con
  `No token.json found; run scripts/auth_google.py once.`. Postgres, Redis,
  Weaviate, Neo4j, workers, checkpointer, LLM/embeddings, LangSmith, voice,
  maps, Kimi y captcha estan operativos/configurados.
- Decision: no ocultar este estado como `ok`; si Calendar/Drive estan
  habilitados, falta OAuth real del operador y debe seguir degradando el
  dashboard hasta generar `GOOGLE_TOKEN_DIR/token.json`.
- Mejora aplicada: los tests de health separan ahora estados no fallidos
  (`disabled`, `configured`, `ready`) del estado `blocked`, para prevenir
  falsos verdes en integraciones habilitadas pero incompletas.

Hallazgo 37.7 - Gmail podia exponer rutas locales en errores de OAuth:

- Severidad: P2 seguridad/privacidad operacional.
- Evidencia: `GmailRestReader` y `GmailLabelReader` construian errores con la
  ruta absoluta de `token.json` cuando el token faltaba o al persistir refresh.
  Ese dato no es un secreto criptografico, pero revela estructura local del
  host y contradice la politica de redaccion ya aplicada en health/Google.
- Correccion: errores de token faltante usan mensajes genericos; fallos de
  persistencia reportan solo el tipo de excepcion; errores HTTP/JSON del lector
  label pasan por el mismo redactor de Gmail digest, que ahora redacta secretos
  y paths absolutos.
- Verificacion: `uv run pytest tests/test_gmail_digest.py
  tests/test_health_dashboard.py -q` -> **19 passed**; Ruff focalizado y
  `git diff --check` verdes.

Hallazgo 37.8 - Kimi WebBridge mutaba navegador real sin aprobacion efectiva:

- Severidad: P1 seguridad/operacion.
- Evidencia: `KIMI_WEBBRIDGE_REQUIRE_APPROVAL` declaraba que las mutaciones del
  navegador real requerian aprobacion, pero los endpoints directos
  `/actions/webbridge/click|fill|evaluate|close_session` ejecutaban con solo
  `KIMI_WEBBRIDGE_ALLOW_MUTATIONS=true`. Ademas, la navegacion Kimi no heredaba
  la defensa DNS/SSRF ya existente para browser automation aislado.
- Riesgo: una configuracion con mutaciones activas podia operar sesiones reales
  del usuario sin `ActionRequest`/`HumanApproval`; con wildcard o dominios
  engañosos tambien podia navegar a IPs internas resueltas via DNS.
- Correccion: mutaciones directas quedan bloqueadas mientras
  `KIMI_WEBBRIDGE_REQUIRE_APPROVAL=true`; produccion rechaza
  `KIMI_WEBBRIDGE_ALLOW_MUTATIONS=true` con aprobacion deshabilitada; Kimi
  navigation usa `ENABLE_BROWSER_SSRF_CHECK` y rechaza IPs privadas/loopback/
  reservadas tras resolver DNS.
- Verificacion: `uv run pytest tests/test_kimi_webbridge.py tests/test_config.py
  -q` -> **31 passed**; Ruff/format focalizados y mypy en Kimi/config verdes.

Hallazgo 37.9 - Dispatch duplicado podia marcar un job como fallido:

- Severidad: P1 operacional/concurrencia.
- Evidencia: `ActionRequestService.execute_action_request` devuelve `running`
  cuando otro worker ya tomo la fila con `FOR UPDATE`, pero
  `run_action_request_task_async` interpretaba cualquier estado distinto de
  `completed` como `failed`. Un worker duplicado podia marcar el `Job` como
  fallido mientras el worker real seguia ejecutando.
- Correccion: el task Celery ahora distingue estados terminales
  (`completed`, `failed`, `cancelled`, `rejected`) de estados no terminales
  (`running`, etc.). Si detecta que no debe ejecutar, registra
  `action_request_not_executed` sin convertir el job a `failed`.
- Hardening adicional: `queue_approved_action_request` usa `SELECT ... FOR
  UPDATE` antes de pasar de `pending_approval` a `queued`, reduciendo el riesgo
  de doble encolado por doble click concurrente.
- Verificacion: `uv run pytest tests/test_action_request_workers.py
  tests/test_actions.py::test_queue_approved_action_request_locks_row_before_queue
  tests/test_actions.py::test_dispatch_action_request_enqueues_worker
  tests/test_actions.py::test_dispatch_action_request_does_not_enqueue_non_queued_status
  tests/test_celery_config.py -q` -> **8 passed**; Ruff focalizado verde.

Hallazgo 37.17 - HumanApproval sin indice sobre (status, created_at):

- Severidad: P2 performance.
- Evidencia: la vista de aprobaciones (`ORDER BY created_at DESC` filtrando por
  `status='pending'`) y el reaper (`WHERE status='pending' AND created_at <
  cutoff`) escaneaban toda la tabla. Aceptable hoy, pero crece linealmente.
- Correccion: migracion `202605160002_human_approvals_status_created_at_index`
  agrega `ix_human_approvals_status_created_at(status, created_at)`. El modelo
  declara el mismo Index para que autogenerate quede limpio.
- Verificacion: `uv run alembic upgrade head` aplicado; `uv run alembic
  check` -> "No new upgrade operations detected"; suite **517 passed**.

Hallazgo 37.16 - Sin endpoint operativo para versionado/policy snapshot:

- Severidad: P2 observabilidad.
- Evidencia: `/health/dashboard` cubre conectividad pero no expone las
  policy flags vigentes (cifrado requerido, four-eyes, TTL de approval,
  backend de research). Un operador no tenia forma rapida de validar que el
  API arrancara con los defaults endurecidos.
- Correccion: nuevo `GET /system/info` retorna `service`, `environment`,
  `python_version`, `fastapi_version`, defaults de policy y `started_at`.
  Requiere auth; sin admin-gate porque no expone secretos.
- Verificacion: `tests/test_system_info.py` -> **2 passed**; suite
  **517 passed**.

Hallazgo 37.15 - Approvals pending sin TTL: riesgo de accion obsoleta:

- Severidad: P1 operacional/seguridad.
- Evidencia: las `HumanApproval` quedaban en `pending` indefinidamente. Una
  aprobacion solicitada hace dias y aprobada hoy ejecuta una accion con
  contexto stale (filesystem, DNS, calendario movido). El modelo declaraba
  `expired` como estado posible pero ningun reaper lo aplicaba.
- Correccion: nuevo setting `APPROVAL_PENDING_MAX_HOURS=48`, metodo
  `ActionRequestService.reap_stale_pending_approvals`, task Celery
  `cognitive_os.reap_stale_approvals` ruteado a `maintenance` y agendado en
  beat `approval-reaper` (minuto 15 cada hora). El reaper transiciona
  approval -> `expired`, cierra job/ActionRequest ligados como `rejected` y
  emite `AuditEvent approval.expired` + `JobEvent approval_expired`.
- Verificacion: `uv run pytest tests/test_approval_reaper.py
  tests/test_celery_config.py -q` -> **5 passed**; suite amplia ->
  **515 passed, 1 skipped, 20 deselected**; Ruff/format/mypy focalizados
  verdes; `SETTINGS_REGISTRY_TABLE.md` regenerado.

Hallazgo 37.14 - Decisiones de approval API no emitian AuditEvent:

- Severidad: P2 observabilidad.
- Evidencia: el carril Telegram (`telegram_bot._decide`) ya emitia
  `approval.{status_value}` como `AuditEvent`, pero el endpoint REST
  `/approvals/{id}/approve|reject` solo grababa `JobEvent` (cuando habia job).
  El registro de quien aprobo/rechazo y desde donde quedaba implicito.
- Correccion: `_decide_approval` ahora agrega un `AuditEvent` con
  `actor_id=approver_user_id`, `action="approval.{status_value}"`,
  `resource_type="human_approval"` y metadata `(requested_action, requested_by,
  job_id)`. El test
  `test_openshell_approval_dispatches_queued_job` exige el AuditEvent.
- Verificacion: `uv run pytest tests/test_actions.py -q` -> **50 passed**;
  Ruff/format focal verdes.

Hallazgo 37.13 - full-qa.sh no incluia alembic check ni git diff --check:

- Severidad: P2 operacional.
- Evidencia: `scripts/full-qa.sh` corria pytest+ruff+mypy+lint+build, pero el
  drift de Alembic y los warnings de whitespace solo eran detectables por
  `verify_operator_ready.sh` o pre-commit. Un operador que solo corriera
  `full-qa.sh` antes del commit podia introducir migraciones huerfanas o
  conflictos de merge sin verlo.
- Correccion: el script ahora corre `uv run alembic check` cuando hay
  `DATABASE_URL`/`.env*` disponible (con tolerancia a Postgres apagado) y
  fuerza `git diff --check` como compuerta dura al final cuando estamos en un
  repo git. Ambas compuertas reportan claramente si se saltan.
- Verificacion: `bash -n scripts/full-qa.sh` -> sintaxis valida; ejecucion
  real cubierta por el siguiente smoke al cierre del bloque.

Hallazgo 37.12 - Idempotency sin garantia transaccional contra carreras:

- Severidad: P1 datos/concurrencia.
- Evidencia: el helper aplicativo `_find_active_idempotent_request` (Fase 37.11)
  cubre el doble-click serializable, pero dos POSTs llegando al mismo tick
  podian saltar la verificacion y dejar dos `ActionRequest` activos con la
  misma `(action_type, requested_by, idempotency_key)`.
- Correccion: nueva migracion `202605160001_action_request_idempotency_unique_index`
  agrega un indice parcial UNIQUE
  `uq_action_requests_active_idempotency(action_type, requested_by,
  idempotency_key) WHERE status IN ('previewed','pending_approval','queued',
  'running')`. El modelo SQLAlchemy refleja el mismo Index con
  `postgresql_where` para evitar drift en autogenerate.
- Verificacion: `uv run alembic upgrade head` aplica sin error; `uv run alembic
  check` -> "No new upgrade operations detected"; `uv run pytest
  tests/test_alembic_autogenerate.py tests/test_actions.py -q` -> **52
  passed**; suite amplia **513 passed, 1 skipped, 20 deselected**.

Hallazgo 37.11 - Idempotency key declarada pero no aplicada:

- Severidad: P1 operacional.
- Evidencia: cada `create_*_request` computa `_idempotency_key(action_type,
  payload_redacted)` y lo persiste, pero ninguna lectura preexistente impide
  duplicados. Un doble-click o un retry POST creaba un nuevo `ActionRequest` +
  `HumanApproval` + `Job` por cada submit, ensuciando la cola de aprobaciones y
  fragmentando el audit trail.
- Correccion: nuevo helper `ActionRequestService._find_active_idempotent_request`
  busca filas activas (`previewed|pending_approval|queued|running`) con la
  misma tupla `(action_type, requested_by, idempotency_key)`. Cada
  `create_*_request` (computer_organize, godaddy_dns_change, document_generate,
  browser_preview, browser_interactive) y los wrappers `_persist_preview_request`
  y `_persist_executable_request` retornan la fila existente sin escribir.
- Verificacion: `uv run pytest tests/test_actions.py -q` -> **50 passed**;
  nuevo test `test_calendar_action_request_dedups_repeat_submissions` cubre el
  carril completo; suite amplia `uv run pytest -m 'not integration and not slow'
  -q` -> **513 passed, 1 skipped, 20 deselected**; Ruff/format/mypy focalizados
  verdes.

Hallazgo 37.10 - RBAC: aprobacion propia y mutaciones de memoria sin admin:

- Severidad: P1 seguridad/HITL.
- Evidencia: cualquier usuario autenticado podia ejecutar
  `POST /approvals/{id}/approve|reject` sobre una aprobacion que el mismo
  habia originado, anulando la contract human-in-the-loop. Ademas,
  `POST /deepagents/memory/proposals/{id}/approve|reject` y
  `POST /deepagents/memory/consolidate/run` ejecutaban con solo
  `require_authenticated_user`, aunque mutan memoria persistente que moldea
  futuros runs.
- Correccion: nuevo flag `APPROVAL_REQUIRE_FOUR_EYES` (default True). En
  `_decide_approval`, si el approver coincide con el requester, devuelve `403`
  con detalle four-eyes. Los tres endpoints de memoria ahora dependen de
  `require_admin_user`. `SETTINGS_REGISTRY_TABLE.md` regenerado para incluir
  el nuevo flag.
- Verificacion: `uv run pytest
  tests/test_actions.py::test_approval_self_decision_blocked_by_four_eyes
  tests/test_actions.py::test_approval_self_decision_allowed_when_four_eyes_disabled
  tests/test_actions.py::test_approval_decision_is_immutable
  tests/test_actions.py::test_openshell_approval_dispatches_queued_job
  tests/test_actions.py::test_rejected_approval_closes_linked_job_and_action_request
  tests/test_admin_gated_endpoints.py tests/test_config.py
  tests/test_langsmith_access.py -q` -> **28 passed**; suite amplia
  `uv run pytest -m 'not integration and not slow' -q` -> **512 passed,
  1 skipped, 20 deselected**; Ruff/format/mypy focalizados verdes.

## 2026-05-15 - Pulido CI post-baseline

- El workflow CI estaba versionado bajo `cognitive-os/.github/workflows/ci.yml`.
  En el repo real, GitHub solo descubre workflows bajo `.github/workflows` en la
  raiz, por lo que ese CI no corria.
- Se movio a `.github/workflows/ci.yml` y se mantuvieron los working directories
  apuntando a `cognitive-os/backend` y `cognitive-os/frontend`.
- El job backend ahora instala con `--extra openharness`, igual que el full QA
  local, para evitar divergencia entre CI y operador.
- `verify_operator_ready.sh` era una verificacion parcial: no sincronizaba deps,
  no revisaba `ruff format`, no hacia `npm ci` y mostraba Alembic como dato
  informativo aunque estuviera detras de head. Ahora esas comprobaciones son
  compuertas reales.

## 2026-05-15 - Baseline git seguro

- `detect-secrets --all-files` sobre todo el workspace incluye tambien archivos
  ignorados; por eso reportaba `.env`, `.env.local`, `opencode.json`, vendor
  `.openharness_upstream` y `tsconfig.tsbuildinfo`. Esos no son versionables y
  estan cubiertos por `.gitignore`.
- El escaneo correcto para baseline usa `git ls-files --cached --others
  --exclude-standard` como fuente de archivos versionables. Ese escaneo quedo
  limpio (`results: {}`).
- `pre-commit` real detecto dos fixtures de redaccion con patrones de llave y
  un limite bajo para `uv.lock`; ambos quedaron corregidos. `gitleaks` pasa.
- Decisión: permitir `uv.lock` hasta 1024 KB en hooks para preservar lockfiles
  reproducibles sin abrir la puerta a artefactos grandes arbitrarios.

## 2026-05-15 - Reconciliacion runtime local

- El codigo ya tenia head Alembic `202605150002`, pero la base local seguia en
  `202605140001`. Se aplicaron `202605150001` y `202605150002` hasta quedar en
  `202605150002 (head)`.
- Los contenedores existentes habian sido creados con bindings antiguos:
  Postgres, Weaviate y Neo4j aparecian publicados en `0.0.0.0`. La configuracion
  vigente ya era loopback; `docker compose up -d` recreo solo los servicios
  necesarios y dejo todos los puertos criticos en `127.0.0.1`.
- El baseline git seguia propenso a incluir material no fuente:
  `cognitive-os-backup-*`, `cognitive-os-snapshot-*`, transcripciones
  recuperadas y `cognitive-os/.claude/settings.local.json`. Se agregaron reglas
  explicitas en `.gitignore` y fueron verificadas con `git check-ignore -v`.

## 2026-05-15 — Fase 33 RBAC + cifrado + research durable

Hallazgos confirmados antes de implementar:

- Auth local no tenía RBAC explícito: `create_access_token` emitía sólo `sub/iat/exp`,
  `AuthenticatedUser` sólo exponía `is_admin`, y `_is_admin_user` trataba lista
  `ADMIN_USER_IDS` vacía como admin para todos.
- `payload_executable` está separado de `payload_redacted`, pero persiste JSON
  ejecutable en claro. El cierre comercial requiere cifrado at-rest y fallback
  controlado para filas históricas.
- Research Orchestrator conserva runs/eventos en un dict en memoria. El API SSE
  funciona bien durante el proceso, pero lista/get no sobreviven restart si no se
  activa un backend durable.
- Fase 32 ya cerró varios riesgos detectados previamente: Google direct writes,
  loopback infra, reaper en beat, redacción OAuth/Drive/health y PWA hardening.

Resultado implementado:

- Admin implícito eliminado; JWT local soporta roles y LangSmith queda protegido
  por admin por defecto.
- `payload_executable` queda cifrable con Fernet y producción rechaza operar sin
  clave + `ACTION_PAYLOAD_ENCRYPTION_REQUIRED=true`.
- `research_runs` persiste snapshots/eventos de Research Orchestrator cuando
  `RESEARCH_PERSISTENCE_BACKEND=postgres`; producción exige ese backend.
- QA Fase 33: 492 passed, 1 skipped, 20 deselected; ruff/format/mypy/frontend
  lint/build/Compose/Alembic/diff verdes.

## 2026-05-15 — Fase 32 hardening comercial

Hallazgos P0/P1 cerrados tras Google operativo:

- **Secreto inline MCP**: `opencode.json` contenía `EXA_API_KEY` como valor
  directo. Se reemplazó por `{env:EXA_API_KEY}`. El valor debe rotarse fuera de
  esta sesión porque ya estuvo en un archivo local.
- **Bypass de aprobación Google**: los endpoints directos Calendar/Drive podían
  ejecutar con `dry_run=false` si el caller tenía JWT y flags activos. Ahora
  `events/create`, `files/upload` y `folders/ensure` son preview-only y devuelven
  `409` para writes directos; el carril real es `/request` + `HumanApproval` +
  Celery + audit.
- **Config peligrosa en producción**: producción ya no permite write flags de
  Calendar/Drive si `REQUIRE_HUMAN_APPROVAL_FOR_EXTERNAL_ACTIONS=false`.
- **Errores con metadata sensible**: OAuth/Drive/health podían reflejar rutas
  locales o detalles de token. Se redactan rutas absolutas, `token.json` y
  valores con forma de secreto.
- **Reaper no agendado**: `cognitive_os.reap_stuck_action_requests` quedó routeado
  a `maintenance` y agendado cada 10 minutos en Celery beat.
- **Infra expuesta por defecto**: Compose publica Postgres, Redis, Weaviate y
  Neo4j sólo en `127.0.0.1`; `.env.example` queda alineado con puertos reales.
- **PWA/comercial**: Next añade headers de seguridad, el service worker versiona
  cache y mantiene rutas API-like network-only, y el componente PWA muestra
  estados de offline/update/install.
- **QA**: targeted hardening `52 passed`; full backend `484 passed, 1 skipped,
  20 deselected`; ruff, format, mypy, frontend lint/build y Compose config verdes.

## 2026-05-15 04:47 (hora Chile) — Verificación de auditoría documental

Nota Fase 37: esta sección queda como snapshot histórico de ese instante. Los
conteos vigentes se verifican en la sección 2026-05-16.

Sweep autónomo no destructivo (solo docs). Conteos verificados contra
código real, no contra documentación previa:

- **Endpoints REST**: 115 totales sumando `@router.{get,post,put,patch,delete}`
  bajo `backend/src/cognitive_os/api/routes/`. La cifra histórica de "89
  endpoints" se refiere solo al subconjunto de propios Cognitive OS sin
  contar orquestación/transversales — ambas cifras son consistentes y se
  documentan explícitamente en `README.md` y `docs/COGNITIVE_OS_GUIDE.md`.
- **Vistas frontend**: 17 reales (no 16) tras sumar `AssistView` el
  2026-05-14. Verificadas con `ls frontend/app/views/*.tsx`.
- **Skills `.opencode/`**: 15 (no las 13 que ciertos docs antiguos
  mencionaban; las nuevas son `dual-memory-recall`, `huggingface-hub`,
  `kimi-webbridge`, `opencode-operator`, `memory-bank`).
- **MCPs**: 21 conectados/wrapped (`docs-langchain`, `weaviate-docs`,
  `sequential-thinking`, `playwright`, `chrome-devtools`,
  `github-official`, `tavily`, `brave-search`, `gh_grep`, `deepwiki`,
  `exa`, `huggingface`, `neo4j`, `weaviate`, `memory-bank`, `context7`,
  `langsmith`, `supermemory`, más wrappers locales).
- **Workers Celery**: 11 tareas registradas, 5 queues activas. La queue
  `mail` quedó incluida en `scripts/dev_worker.sh` el 2026-05-14.
- **Migraciones Alembic**: 13 archivos en
  `backend/src/cognitive_os/db/alembic/versions/` (la última es
  `202605140001_mail_accounts_messages`).
- **Sin discrepancias críticas** entre código y docs después de este sweep.
- **Sin secretos en árbol**: confirmado por grep del `.env.local` actual y
  reglas de pre-commit (`gitleaks`).

## 2026-05-14 — Auditoría integral grado comercial

Sweep autónomo en 5 ejes de riesgo. Cero hallazgos críticos abiertos; un
endurecimiento menor cerrado:

- **Silent failures**: los dos helpers de audit (`_audit_calendar`,
  `_audit_drive`) usaban `except Exception: return`. Convertidos a
  `except Exception as exc: log.warning(...)`. Los demás suppress del proyecto
  son legítimos (degradación documentada, predicates, cleanups en `finally`).
- **Secrets en árbol**: grep agresivo de los 5 valores reales del `.env`. 0 fugas.
- **Auth**: 98 endpoints enumerados. 0 sin proteger (sólo `/health` es público
  como debe ser). Verificado vía ASGI sin JWT — todos devuelven 401.
- **Concurrencia**: locks correctos, `asyncio.run` siempre en bordes sincrónicos
  o detrás de `_run_async()` que detecta loop activo y falla rápido.
- **Boundaries**: validación estricta en upload de Drive (path allow-list, cap
  de tamaño, traversal rechazado), Calendar (ventana temporal), Maps (URL
  params via httpx).
- QA final: 428 passed, ruff/mypy/format verdes (104 archivos), frontend lint y
  build verdes.

## 2026-05-14 — Fase 25 C/D + Maps + Voz implementadas

- **Riesgo de seguridad registrado**: el operador pegó credenciales reales
  (ElevenLabs, OAuth Google, API key Maps) directamente en el chat. Quedaron
  en el transcript de la conversación. Por la propia regla de `docs/SECURITY.md`
  ("rotar claves si aparecen en logs, prompts, reportes"), esas tres
  credenciales deben **rotarse** una vez verificado el funcionamiento. Se
  escribieron sólo en `cognitive-os/.env` (gitignored, perms 600); nunca en
  código, tests, docs ni en respuestas.
- Maps y voz son integraciones API-key puras → totalmente verificables por
  tests (providers fake, sin red). Calendar/Drive usan el patrón OAuth de
  `GmailRestReader`: `google-auth` se importa de forma perezosa, no se agregó
  a `pyproject.toml` para no tocar `uv.lock`/CI; el operador lo instala al
  habilitar la capacidad real.
- Decisión de alcance: Calendar/Drive salen **read-only** en este corte. Crear
  eventos o subir archivos son acciones externas y deben ir por
  `ActionRequest`/aprobación — se deja como seguimiento explícito, no como
  implementación a medias (mismo criterio que Gmail en Fase 21).
- La schema `DocumentChunk` de Weaviate no tiene propiedad per-usuario; Maps no
  la usa, pero se mantiene el criterio de la 25.E: si en el futuro se cachean
  rutas/lugares, el aislamiento por usuario va por post-filtro de metadata.
- QA tras la jornada completa: **389 passed, 1 skipped, 20 deselected**
  (inicio del día: 341); `ruff`/`ruff format`/`mypy --strict` y frontend
  `lint`/`build` verdes.

## 2026-05-14 — Revisión integral + decisiones Fase 25 resueltas

- Revisión desde cero (26 markdowns + núcleo backend + QA completo). Veredicto:
  el código implementado **ya es grado comercial**: `pytest` 341→347 passed,
  `ruff`/`ruff format`/`mypy --strict` verdes, frontend `lint`/`build` verdes,
  CI y pre-commit presentes, `.env`/`.env.local` no trackeados. No se hallaron
  bugs ni fugas de secretos ni anti-patrones en el código existente.
- **Decisiones bloqueantes Fase 25 resueltas por el operador**:
  1. Mail GoDaddy (`diego@doctormanzur.com`): **IMAP/SMTP nativo GoDaddy** →
     confirma que el carril `mail/` actual es la arquitectura correcta; falta
     solo hardening multicuenta.
  2. Política Gmail send: **solo proponer texto** (sin `gmail.compose`) →
     confirma el comportamiento read-only actual; no se añade scope nuevo.
  3. Agenda: **Google Calendar** (reusa OAuth Gmail). Requiere credenciales.
  4. Voz STT/TTS: **ElevenLabs**. Requiere `ELEVENLABS_API_KEY`.
  5. Multi-cuenta: **N desde el inicio** (default recomendado).
  6. Markdown vault de notas: **opcional, off por defecto** (default recomendado).
- **Subfase 25.E (notas semánticas) — IMPLEMENTADA y verde**:
  `assist/note_index.py` (`NoteIndexService` + Protocol `NoteVectorStore`),
  indexado best-effort en Weaviate (`doc_type="note"`) en create/update/delete
  de `PersonalAssistService`, endpoint `GET /assist/notes/search`, aislamiento
  por `user_id` vía post-filtro (la schema `DocumentChunk` no tiene propiedad
  per-user). Degradación graciosa: un Weaviate caído nunca rompe el CRUD de
  notas. 6 tests nuevos sin red (`tests/test_note_index.py`).
- Subfases 25.A/B confirmadas como mayormente existentes (mail GoDaddy ya está);
  25.C/D (voz ElevenLabs, Google Calendar) quedan code-ready pendientes de
  credenciales; 25.F/G/H pendientes de implementación incremental.

## 2026-05-14 - Hallazgos hardening frontend

- El frontend persistía el JWT local en `localStorage` (`cogos.jwt`), lo que era
  innecesario para el cockpit y aumentaba el riesgo de exposición. Se cambió a
  estado efímero en React y se mantuvo la persistencia sólo para preferencias no
  secretas como API base, tab y tema.
- `ApiClient` enviaba `Content-Type: application/json` incluso en requests sin
  body. Esto no siempre rompe FastAPI, pero es una señal incorrecta para GET y
  DELETE; ahora sólo se añade cuando existe body.
- El polling anterior no abortaba la petición HTTP en vuelo; sólo evitaba algunos
  commits obsoletos. `AbortController` reduce trabajo innecesario y evita errores
  visuales al cambiar rápido de vista/filtro.
- El contrato backend ya exponía CRUD personal `/assist/tasks` y `/assist/notes`,
  pero el frontend no tenía entrada operativa. La nueva vista Assist cubre ese
  flujo sin tocar backend.

## 2026-05-14 - Hallazgos normalización documental

- `scripts/dev_worker.sh` no escuchaba la queue `mail` aunque
  `sync_personal_mail` está ruteado a esa cola. Se corrigió para evitar que el
  flujo manual de desarrollo deje mail sin worker.
- La documentación viva debía subir al conteo real de 89 endpoints propios y 16
  vistas por la incorporación de `/mail/*` y `MailInboxView`.
- Las referencias a modelos OpenAI antiguos como runtime local son obsoletas para
  este workspace: el runtime base actual documentado y configurado es DeepSeek V4 Pro; vision se
  mantiene como LLM multimodal configurable.

## 2026-05-14 - Hallazgos mail personal

- El repo solo tiene Gmail OAuth read-only (`actions/gmail_digest.py`) y status
  preview en `actions/mail.py`; no existe soporte IMAP/SMTP ni multicuenta.
- `PersonalNote` existe como CRUD DB, pero no tiene vector/BM25 ni Notion sync.
- No se encontraron implementaciones backend para calendar, ElevenLabs TTS,
  YouTube o audio; las claves existen en config/env pero faltan servicios.
- Para el primer corte de mail no hace falta dependencia externa: IMAP/SMTP se
  puede resolver con `imaplib`, `smtplib` y `email` de stdlib, manteniendo
  mocks/testeo simple.
- GoDaddy IMAP acepto conexion y lectura real con las credenciales locales. El
  primer sync recupero 25 mensajes de carpetas configuradas y no reporto
  errores.
- Gmail `TODOS` queda soportado a nivel de servicio si `GMAIL_READ_ENABLED` y
  `token.json` estan configurados, pero en el `.env` actual no esta habilitado.

## 2026-05-13 — Endurecimiento del bridge OpenHarness

- **Punto débil corregido**: `run_openharness_research_sync` usaba
  `asyncio.run()` directo. Si el grafo se invocaba desde un caller con event
  loop activo (cualquier endpoint async, scripts, posibles workers async),
  fallaba con `RuntimeError: asyncio.run() cannot be called from a running
  event loop` y caía silenciosamente con `openharness_async_runtime_error`.
  Solución: `_execute_engine_blocking` aísla la ejecución en un hilo dedicado
  con su propio `new_event_loop`, cerrando con `shutdown_asyncgens`.
- **Punto débil corregido**: las lambdas en `build_tool_registry` (preset
  `research`) hacían fallar `mypy --strict` (`Call to untyped function`).
  Solución: instanciar directamente y registrar en bucle.
- **Punto débil corregido**: `OPENHARNESS_TOOLKIT_PRESET` y
  `OPENHARNESS_WORKSPACE_MODE` tenían descripciones >100 chars que rompían
  `ruff E501`. Reescritas en multilínea.
- **Punto débil corregido**: la migración `202605120006_personal_tasks_notes`
  tenía 4 columnas con server_default sa.func.now() en una sola línea (>100
  chars). Reescritas en multilínea idiomática.
- **Punto débil corregido**: `.env.example` no listaba ninguna variable
  `OPENHARNESS_*`; ahora incluye un bloque con defaults y comentarios alineados
  con `Settings`.
- **Hallazgo (no rompe)**: `/chat`, `/chat/stream`, `/threads/{id}/resume`
  ya invocan el grafo vía `asyncio.to_thread`, así que `research_node` corre
  en hilo y la versión anterior de `asyncio.run` "casualmente" funcionaba
  desde la API pública. La nueva implementación lo formaliza y permite uso
  desde cualquier contexto.

## 2026-05-13 — Fusión OpenHarness + DeepAgents (research)

- La ruta `research` combina LangGraph + OpenHarness opcional + DeepAgents.
  Pipeline por defecto **`prelude_merge`** (preludio OH inyectado al
  `HumanMessage` que recibe DeepAgent); alternativa **`short_circuit`** que
  devuelve sólo OpenHarness cuando responde válido.
- Workspace por defecto **`deepagent_mirror`**:
  `LOCAL_STORAGE_DIR/workspaces/{thread_id}/{thread_id}-research`.
- Presets de tools: `minimal | research | full`. `OPENHARNESS_INCLUDE_FILE_TOOLS`
  sólo afecta a `minimal` (en `research`/`full` los file tools ya están).
- Búsqueda web dentro de OpenHarness exige
  `WEB_SEARCH_ENABLED && OPENHARNESS_WEB_TOOLS`.
- Documentación canónica: `docs/OPENHARNESS_FUSION.md`. Tests:
  `backend/tests/test_research_openharness_priority.py` y
  `backend/tests/test_openharness_research.py`.

## 2026-05-13 — Corrección README sobre `cognitive-os`

- `uv run cognitive-os` apunta a `cognitive_os.__main__:main`, que sólo emite un
  log `Cognitive OS bootstrap OK`. **No** es el servidor API. Para arrancar el
  API real: `uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000`
  como ya documenta `docs/RUNBOOK.md`.

## 2026-05-12 - Initial Project Recon

- Active project appears to be `/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os`.
- Parent directory contains backups/snapshots; active tree has backend, frontend, infra, docs, scripts, storage and experiments.
- No `.git` directory was found in parent or active project during initial inspection.
- `planning-with-files-es` and `planning-with-files` are installed under `/home/jgonz/.codex/skills`.

## 2026-05-12 - Baseline Checks

- Backend pytest baseline passed: 144 passed, 1 skipped, 19 deselected.
- Frontend lint baseline passed.
- Backend Ruff baseline failed before any project edits:
  - `src/cognitive_os/core/config.py`: one line over 100 chars.
  - `src/cognitive_os/core/config.py`: three SIM102 nested-if simplifications.

## 2026-05-12 - Architecture Snapshot

- Backend uses FastAPI, LangGraph, Celery, Postgres, Redis, Weaviate, Neo4j, DeepAgents and OpenShell sandbox integration.
- Frontend is Next.js 16 / React 19 console with operational views.
- Existing settings already include browser automation, Gmail, Microsoft mail and GoDaddy flags.
- Existing policy layer has risk classes and human approval mechanics.
- Existing DeepAgents policy blocks shell/browser/email/social/delete by default.
- OpenShell sandbox exists but its adapter currently reports that a safe one-shot runner is not implemented.

## 2026-05-12 - External Capability Gap

- Browser/Gmail/GoDaddy variables exist, but the project needs a concrete "action plane" abstraction:
  - capability status
  - dry-run previews
  - allow-list validation
  - audit records
  - approval request generation
  - tests for dangerous paths/domains/scopes

## 2026-05-12 - Tooling Notes

- Browser and Chrome automation plugins are already available in Codex.
- Gmail plugin suggestion was attempted, but user reported the authorization browser hangs.
- No GoDaddy connector/plugin is available in the current discoverable tool list.

## 2026-05-12 - External Docs Checked

- Playwright Python official docs: persistent contexts use a dedicated user data directory for cookies/local storage; automating the user's default Chrome profile is not supported and a separate automation profile should be used.
- Playwright official docs: browser contexts are the isolation boundary and avoid cross-task state leakage.
- Camoufox official docs: Camoufox wraps the Playwright API and adds generated device/browser characteristics.
- Gmail official quickstart: production should use proper OAuth/auth review; quickstart uses `gmail.readonly`, stores OAuth tokens on disk, and uses Google client libraries.
- GoDaddy official Domains API docs: OTE base URL is `https://api.ote-godaddy.com`; production base URL is `https://api.godaddy.com`.
- GoDaddy official MCP page: public MCP endpoint exists at `https://api.godaddy.com/v1/domains/mcp`, but it is read-only and cannot modify DNS records or domain settings.

## 2026-05-12 - Documentation Cleanup

- Root-level `explicacion_sistema_cognitive_os.md` duplicated project explanation outside the canonical docs tree and was deleted after replacement by `docs/PROJECT_GUIDE.md`.
- `docs/README.md` now serves as the documentation index.
- `ACCEPTANCE_CHECKLIST.md` now separates automated verification from manual infra/credential acceptance.

## 2026-05-12 - Action Request Lifecycle

- The previous action plane was only validation/preview, which is safe but not
  enough for a commercial operator workflow.
- A persistent action unit is now present: `ActionRequest -> HumanApproval ->
  Job/Celery -> AuditEvent -> result/error`.
- `computer_organize` is the only real executor for now because it is local,
  deterministic and testable with temporary directories.
- Browser, Gmail and GoDaddy should remain preview/validation until their real
  executors include provider-specific authentication, rate limits, idempotency,
  token storage, diffs and rollback strategy where possible.
- UI now covers the first operational loop: approval of an action request can
  dispatch it, and recent requests are visible from `Configuracion`.

## 2026-05-12 - Phase 9 Insights

- Browser, Gmail and GoDaddy persistence was missing: no operator could see
  history of what the agent proposed nor why it was blocked.
- Reuse of the persistence path via `_persist_preview_request` keeps audit and
  redaction consistent. Each request stores `payload_redacted`, `preview`,
  `error` (only when blocked) and an `audit_event`.
- `cancel_action_request` must refuse to cancel `running` states because the
  Celery worker holds the only authoritative process; it must also be a no-op
  for terminal states (`completed`, `failed`, `cancelled`, `rejected`) to avoid
  redundant audit noise and accidental state churn.
- Filters on `GET /actions/requests` use FastAPI `Annotated[..., Query(alias=)]`
  to keep query parameter names operator-friendly (`status` instead of
  `request_status`) without colliding with the imported `status` symbol from
  FastAPI.

## 2026-05-12 - Phase 10 Insights (Documents)

- `document_generate` is a useful first real executor for an external-action
  loop beyond `computer_organize` because:
  - It only writes inside an allow-listed root (`DOCUMENT_OUTPUT_ROOT`).
  - It cannot exfiltrate data or call the network.
  - It has a clear size cap (`DOCUMENT_MAX_SIZE_BYTES`) that we enforce after
    write by deleting the offending file.
  - It composes cleanly with the existing `ActionRequest` lifecycle so the
    operator workflow (approve -> dispatch -> Celery -> audit) is reused.
- Path validation must reject absolute paths, `..` components and empty names
  before resolving against the allow-listed root. We also normalize the
  filename suffix to the requested format to avoid `report.docx -> .DOCX`
  inconsistencies and confused-deputy edge cases on case-insensitive FS.
- `python-docx` ships its own type stubs in current versions, so the
  `# type: ignore[import-untyped]` is rejected by mypy as unused. We keep
  `openpyxl` and `pptx` under `ignore_missing_imports` because they do not
  ship stubs.
- For PPTX, we build the title slide from layout 0 and bullet slides from
  layout 1. This avoids depending on theme-specific custom layouts and works
  with the default Office template that python-pptx provides.
- We keep `requires_approval=True` for `document_generate` even though the
  blast radius is small: it makes the executor symmetric with
  `computer_organize` and lets the operator see a preview before any bytes
  hit disk.

## 2026-05-12 - Phase 11 (Browser headless preview)

- Real browser execution is intentionally **opt-in**. The default code path
  does not require `playwright` to be installed; when it is missing, the
  executor returns `status="blocked"` with a clear reason and never raises
  an opaque ImportError to the operator. To activate real previews the
  operator must run `uv sync` and `playwright install chromium` on the host.
- The service uses a Protocol-based provider (`BrowserPreviewProvider`) and
  a factory hook (`provider_factory: Callable[[Settings], BrowserPreviewProvider]`).
  Tests inject Fake/Huge providers so they exercise the full lifecycle
  (validate -> ActionRequest -> execute -> bytes cap -> file cleanup) without
  spawning a browser or hitting the network.
- Validation refuses non allow-listed domains via the existing
  `validate_allowed_browser_domain` and refuses headed mode (this executor is
  headless-only by design; vision and credentialed profiles are kept out of
  Phase 11 until explicit human consent and per-site profiles are wired).
- The screenshot is written under `BROWSER_SCREENSHOT_DIR`, then checked
  against `BROWSER_SCREENSHOT_MAX_BYTES`. If it exceeds the cap, the file is
  deleted before returning `blocked` so we never leave oversize artifacts on
  disk after a failed run.
- A small ruff catch was that the `BrowserPreviewProvider.run` return type
  used quoted annotations (`"BrowserPreviewProviderResult"`) when forward
  reference was no longer required (the class is declared above the
  Protocol). Removed the quotes per `UP037`.

## 2026-05-12 - Phase 16 (RAG robustness) Insights

- **Dual-write inconsistencia**: el pipeline escribia `DocumentChunk.status="indexed"` en el mismo `session_scope` de traceabilidad, ANTES de tocar Weaviate. Si Weaviate fallaba, Postgres quedaba con chunks claimando estar indexados, pero queries devolvian cero. Lesson para futuros dual-writes: el sistema con menor garantia transaccional (Weaviate aqui) define el "fin de la operacion"; el otro lado solo se marca `pending` hasta que el primero confirma. Patron: `pending_index` -> verificacion del lado debil -> `indexed`.

- **Idempotencia por contenido**: re-ingerir el mismo PDF generaba duplicados completos (nuevo `Document`, nuevas chunks, nuevos vectores). Causa: la unique constraint era `(sha256, source_path)`, pero el usuario puede mover el archivo y la ruta cambia. El campo invariante es el `sha256`. Lesson: para dedup semantico, indexar por el hash del contenido, no por path/nombre. Fix: lookup explicito en `_existing_indexed_document(sha256)` antes de crear; reutiliza solo si el `Document` esta `indexed` y todos sus chunks tambien.

- **Costo de N HTTP**: ingerir un PDF de 500 chunks disparaba 500 POST + 500 embedding calls. Latencia, costo, y rate limits sufrian. Lesson: batchear es obligatorio cuando hay APIs externas detras. Fix: `embed_texts(list, kind=...)` ya existia; solo faltaba un consumidor que lo usara, y un endpoint Weaviate de batch (`/v1/batch/objects`) que devuelve status por-objeto. El gotcha es que Weaviate devuelve HTTP 200 incluso si algunos objetos fallaron — hay que inspeccionar `result.errors` por-item.

- **Resiliencia parcial**: si embeddings caia (clave invalida, quota, outage), el chat 500-eaba. La gente acepta busqueda peor a busqueda imposible: BM25-only es un downgrade aceptable. Lesson: sistemas RAG deben tener un modo "puro keyword" como fallback de degradacion. Fix: try/except alrededor del embed_text, alpha=0, omit `vector:` del GraphQL (algunas versiones rechazan vector vacio).

- **Lock pattern en double-checked init**: `if self._collection_ensured: return` sin lock es race. Dos hilos pueden hacer GET, GET ambos retornan 404, ambos POST, el segundo recibe 422. Fix correcto: lock + re-check dentro del lock + aceptar 422 "already exists" como no-op (defensa en profundidad por si OTRO proceso, no solo otro thread, gano la carrera).

## 2026-05-12 - Phase 15 (Correctness critico) Insights

- **HITL guarantee breach (bug #1)**: `execute_organize_plan` reconstruia el plan desde el filesystem en cada ejecucion. Sintoma: el operador aprobaba "mover A.pdf -> PDFs/", pero entre approval y dispatch alguien creaba B.pdf, y el worker movia AMBOS. Lesson: cualquier capa que se interponga entre "preview que el humano ve" y "lo que el worker hace" rompe el contrato de aprobacion. Fix: el plan aprobado se persiste en `action_request.preview`, se parsea con `ComputerOrganizePlan.model_validate`, y el executor ejecuta exactamente esas operaciones revalidando cada una contra el FS actual (si el source ya no existe, se reporta `failed`; no se re-deriva).

- **Redactor ataco la ejecucion (bug #2)**: `payload_redacted` se usaba como entrada del executor. Para schemas reales no se redactaba nada (ni `root_path` ni `output_filename` matchean patrones de secrets), pero un usuario que escribiera "password=foo" en un titulo de documento lo veria literalmente reemplazado por `[REDACTED]` en disco. Lesson: NO usar payloads redactados para ejecucion; redactar es una transformacion lossy para auditoria, no para reproducibilidad. Fix: columna `payload_executable` separa los dos roles.

- **Status semantica vaga (bug #3)**: `DeepAgentResult.status` mezclaba "ok pero no produje contenido" (empty answer) con "ok aqui esta la respuesta". El research_node trataba ambos igual. Lesson: un campo tipado no garantiza semantica clara; hay que validar el contenido tambien. Fix: agregar `.strip()` check sobre `deep_result.answer` antes de tratar `status="ok"` como exito.

- **Falta de row lock (bug #5)**: Dos workers podian leer `status="queued"`, ambos pasar a `running`, y ejecutar la accion dos veces. Lesson: en transiciones de estado donde mas de un actor puede actuar, `SELECT ... FOR UPDATE` no es una decoracion: es la primitiva que evita interleaving. Fix: `with_for_update()` + chequeo pre-flush; el primero gana, el resto retorna idempotente.

- **Default-allow vs default-deny (bug #6)**: `read_document_pages` aceptaba cualquier doc_id valido por UUID. La policy era binaria (allow_local_rag: bool), no scope-bound. Lesson: una tarea con doc_ids autorizados debe enforcement-ar esa lista en cada lectura; "lista vacia" debe significar "no podes leer nada", no "podes leer todo". Fix: factory threads `task.allowed_doc_ids` y la tool rechaza por defecto.

- **Polucion implicita del RAG (bug #8)**: `search_local_docs` y `retrieve_context` no filtraban `doc_type`. El web_indexer guardaba snippets con `doc_type="web"`, y queries "locales" recibian ambos mezclados. Lesson: separar fuentes en el indice no basta; el consumidor debe filtrar EXPLICITAMENTE. Fix: nuevo parametro `exclude_doc_types` y `WeaviateStore` soporta operador `NotEqual` para el WHERE GraphQL.

- **Auditoria asimetrica (bug #10)**: `_audit` se llamaba solo al final de la rama feliz. Policy violations y errores se enviaban al agent loop pero **nunca quedaban en el audit log**. Lesson: la auditoria de seguridad no puede vivir solo en el happy path; cualquier intento (exitoso o no) tiene que dejar trazo. Fix: `_audit_error(tool_name, args, reason)` se invoca en cada return de error en cada tool de deepagents.

- **Paths absolutos en respuestas al usuario (bug #20)**: `RetrievalCitation.citation` exponia `/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/.../doc.pdf` al usuario final. Esto leakea el layout interno del servidor. Lesson: para datos derivados de configuracion/host, distinguir entre "lo que guardas para trazabilidad" (full path en metadata) y "lo que mostras al usuario" (basename o titulo). Fix: helper `_source_display(source_path, title)` con splitter `/`-y-`\` portable.

- **`PurePosixPath` no detecta `\\` en Linux**: al implementar el splitter para citas, intente usar `PurePosixPath` + `PureWindowsPath` y quedarme con la mejor. Pero `PurePosixPath("C:\\foo").name` devuelve el string completo (Linux no trata `\\` como separador). Lesson: para portar codigo cross-platform sin tocar el FS, hacer el splitter a mano con `rfind("/")` y `rfind("\\")` es mas predecible que apoyarse en `pathlib`. El `pathlib` esta sesgado por el OS del intérprete.

## 2026-05-12 - Phase 14 (Research Orchestrator async + SSE) Insights

- Auditoria del orquestador encontro que `start_run` invocaba `_execute`
  sincronamente. El sintoma era que el `POST /research/runs` se bloqueaba hasta
  por `time_budget_seconds` (clamped a 300s por defecto, hasta 3600s). Esto
  hace que la cancelacion via `POST /research/runs/{id}/cancel` sea inalcanzable
  porque el cliente esta atrapado esperando la respuesta del POST. El bug fue
  invisible durante Fase 12 porque los tests usaban fakes rapidos.
- Fix elegido: ejecutar `_execute` en un `threading.Thread(daemon=True)` y
  retornar de inmediato con la run en estado no-terminal. Agregar
  `done_flag: threading.Event` para que `wait_for_run` pueda bloquear sin
  hacer polling. Daemon=True garantiza que el proceso pueda salir incluso
  si un run cuelga.
- Para el SSE endpoint el patron correcto es leer `run.events` (lista, no
  cola). El acceso a `list[X]` bajo CPython es atomico via GIL, asi que el
  snapshot `list(run.events)` es seguro contra modificaciones concurrentes
  del thread productor. El cursor `last_idx` se actualiza despues de
  consumir el snapshot, garantizando que ningun evento se pierde ni se
  duplica entre iteraciones. La alternativa con `Queue` no funciona para
  multiples clientes SSE (la cola es single-consumer).
- El poll interval del SSE es 50 ms: lo suficientemente corto para latencia
  baja en UI sin reventar la CPU. Para una run de 60 s eso son 1200 iteraciones,
  cada una con un `list()` corto y `await asyncio.sleep(0.05)` que cede el
  loop. Una notificacion via `asyncio.Event` por run seria mas eficiente
  pero requiere coordinar entre el productor (thread sincronico) y el
  consumidor (event loop), lo cual se logra con `asyncio.run_coroutine_threadsafe`.
  En esta fase se prefiere la simplicidad del polling corto.
- El bug demuestra que tener tests "verdes" no es suficiente cuando el
  feedback loop esta tomando shortcuts (fakes rapidos que ocultan el costo
  de produccion). Tests nuevos que asertan `elapsed < 0.2s` evitan regresion.

## 2026-05-12 - Phase 13 (Gmail Daily Digest) Insights

- El digest es preview-only por diseno: no toca Gmail ni siquiera para crear
  drafts. La forma correcta de probar la logica de redaccion y ordenamiento
  sin OAuth es inyectar un `GmailReader` Protocol y proveer
  `FakeGmailReader([message_dicts])` que devuelve datos preparados.
- Redaccion de direcciones: para `local` de tamano <= 2 chars se redacta a
  asteriscos completos; para mas largos se mantienen el primer y ultimo char.
  El dominio queda visible para que el operador pueda decidir riesgos de
  proveedor (`gmail.com` vs `proveedor-pequeno.tld`).
- `GmailDigestProposedDraft` lleva `requires_approval=True` siempre. El
  borrador no se persiste en Gmail aunque la flag de send este activa: la
  Fase 13 es un loop "leer -> proponer -> aprobacion humana antes de tocar
  el mailbox". El executor real (Fase futura) recogeria estos drafts solo
  bajo aprobacion.
- El singleton `_gmail_digest_reader` en `api/app.py` permite que la app
  arranque sin un reader configurado (estado `blocked` con razon clara). Los
  tests inyectan un FakeGmailReader via monkeypatch.

## 2026-05-12 - Phase 12 (Research Orchestrator)

- `deepagents>=0.5.5` ya estaba integrado con `run_research_deepagent` y
  politicas estrictas (`DeepAgentToolPolicy`). Construir un planner/research/
  synth/score independiente seria duplicar codigo y romper la auditoria del
  subagente real. Decision: la Fase 12 orquesta encima de deepagents, no lo
  sustituye. El `DeepAgentResearcher` default es un thin wrapper sobre
  `run_research_deepagent`.
- `concurrent.futures.ThreadPoolExecutor` usado como context manager (`with`)
  bloquea el `__exit__` hasta que todos los workers terminen. Eso rompe el
  presupuesto de tiempo cuando una subtask se queda esperando. Solucion:
  usar el executor explicitamente con `try/finally` + `executor.shutdown(
  wait=False, cancel_futures=True)` para devolver el control al orquestador
  apenas vence el deadline.
- Pydantic 2 rechaza `time_budget_seconds=1` y `max_subtasks=99` con
  `ge=5/le=32` definidos en `ResearchRunRequest`. Eso es deseable: el cliente
  no puede pedir parametros fuera de rango. Para pruebas de "clamping"
  contra Settings, se usan los limites externos validos del request (3600 y
  32) y se baja el `Settings` con `monkeypatch` para verificar que el
  orquestador aplica el min(settings, request).
- Ruff `N818` exige sufijo `Error` en excepciones; renombrar
  `ResearchOrchestratorDisabled` -> `ResearchOrchestratorDisabledError` y
  actualizar imports + `__all__`.
- El `HeuristicScorer` calcula un score 0..1 con rubrica auditable y sin
  LLM. Un futuro `LLMScorer` puede inyectarse via `scorer=` sin cambiar el
  orquestador.
- Store in-memory en `api.app._research_orchestrator` (singleton). En
  produccion convendra persistir runs en Postgres para retomar/auditar
  despues de un reinicio. Eso queda como Fase futura para no acoplar Fase 12
  a una nueva migracion.

## 2026-05-12 - Phase 18 (DeepAgents 0.6.1) Insights

- PyPI oficial muestra `deepagents 0.6.1` publicado el 12 de mayo de 2026. El
  upgrade local arrastro `langchain 1.3.0`, `langgraph 1.2.0` y `langsmith 0.8.3`.
- La firma real de `create_deep_agent` 0.6.1 soporta `subagents`, `skills`,
  `memory`, `permissions`, `backend`, `interrupt_on`, `response_format`,
  `checkpointer`, `store`, `cache` y `name`.
- La documentacion oficial confirma que DeepAgents trae `write_todos`,
  filesystem tools, `execute` y `task`. Cognitive OS mantiene `interrupt_on`
  y un backend virtual sin shell para que esos built-ins no rompan la politica.
- Async subagents existen, pero requieren Agent Protocol server / LangSmith
  Deployment o equivalente. No se activaron como ejecucion local silenciosa;
  la Fase 18 implementa subagents sincronicos seguros y deja async remoto para
  una fase de deployment.
- Memory nativa se alimenta con paths dentro del backend. Cognitive OS ahora
  escribe startup memory en `./.cognitive_os/AGENTS.md` dentro del workspace y
  conserva el resumen en system prompt como fallback.
- La memoria consolidada podia inflarse con propuestas repetidas. Ahora se
  deduplica por contenido normalizado antes de llamar a `propose_memory_update`.

## 2026-05-12 - Phase 19 (Office Writers) Insights

- Para XLSX hay que separar "texto que parece formula" de "formula aprobada".
  Si una celda normal contiene `=SUM(...)`, se neutraliza con apostrofo; solo
  `SpreadsheetFormula` escribe una formula real. Esto conserva seguridad sin
  quitar capacidad avanzada.
- Permitir imagenes en DOCX sin allow-list reintroduce lectura arbitraria de
  filesystem. `DOCUMENT_ASSET_ROOTS` deja el riesgo explicito: si esta vacio,
  image embedding queda deshabilitado; si se configura, cada path se resuelve y
  valida dentro de esas raices.
- Las formulas peligrosas no son solo `cmd|`; tambien hay funciones que exfiltran
  datos o abren conexiones (`HYPERLINK`, `WEBSERVICE`, URLs externas,
  referencias `[...]` a workbooks). La Fase 19 bloquea ese conjunto por defecto.
- Validar "archivo existe" no basta: los tests ahora vuelven a abrir cada salida
  con la libreria correspondiente. Esto detecta corrupcion estructural y no solo
  escritura de bytes.

## 2026-05-12 - Phase 21 (Gmail Read-only) Insights

- El punto fragil no era solo OAuth: era que el backend no tenia un reader real
  por defecto. Ahora el operador puede generar `token.json` por cualquier flujo
  Google estandar y Cognitive OS lo consume sin abrir navegador desde el backend.
- La lectura Gmail queda separada del envio. `GmailRestReader` solo consulta
  metadata/snippet con REST y el digest sigue produciendo borradores propuestos
  como texto, no drafts reales.
- Los errores de integracion suelen incluir tokens en trazas HTTP. La capa nueva
  redacta `authorization`, `bearer`, `access_token`, `refresh_token`,
  `client_secret` y `token` antes de exponer la razon en preview.
- No conviene depender de `google-api-python-client` para esta ruta: `httpx` +
  `google-auth` reduce superficie, hace tests simples y evita discovery clients
  pesados para una consulta read-only acotada.

## 2026-05-12 - Phase 22 (GoDaddy DNS Executor) Insights

- DNS writes necesitan un "arming sequence", no un boolean unico. La combinacion
  dry-run=false + domain allow-list + production flag separado reduce el riesgo
  de activar produccion por accidente.
- El preview debe producir el payload ejecutable normalizado. Si se ejecuta
  `change.domain` original (`Example.COM.`) en lugar del preview normalizado
  (`example.com`), la aprobacion humana deja de coincidir exactamente con lo
  ejecutado.
- MX/SRV sin priority son cambios incompletos: bloquear temprano evita que el
  operador apruebe algo que el proveedor luego rechaza o aplica de forma
  ambigua.
- El executor usa `PATCH /v1/domains/{domain}/records` segun el swagger oficial
  de GoDaddy Domains API. El body se limita a un record por solicitud para que
  preview, aprobacion y auditoria tengan granularidad clara.

## 2026-05-12 - Phase 23 (Restore Scripts) Insights

- Backups sin restore probado son solo media solucion. Un producto necesita el
  camino inverso empaquetado, documentado y con frenos contra ejecucion
  accidental.
- `CONFIRM_RESTORE=YES` es deliberadamente tosco: obliga a que el operador
  escriba una intencion explicita en el comando y evita ejecuciones por copy/paste
  incompleto.
- Storage es el restore mas facil de romper: antes de extraer, el script mueve
  el directorio actual a `storage.pre_restore_TIMESTAMP`, dejando una ruta de
  recuperacion local inmediata.
- Las pruebas no restauran infraestructura real; validan sintaxis shell y
  propiedades de seguridad. El restore real debe probarse manualmente en entorno
  de staging con datos descartables.

## 2026-05-12 - Phase 24 (Local File Inventory) Insights

- Ordenar archivos sin inventario previo no escala: el agente necesita una foto
  del filesystem para razonar, comparar cambios y proponer limpieza sin tocar
  bytes.
- La lectura de metadata tambien es sensible. Saltar `.env`, `.ssh`, `.git`,
  tokens y passwords evita que un simple inventario termine exponiendo rutas de
  credenciales en prompts o reportes.
- Guardar el reporte en `LOCAL_STORAGE_DIR/file_inventory` permite una futura
  fase de diff temporal: "que cambio desde ayer", "que archivos crecen mas",
  "que documentos quedaron duplicados".
- sha256 debe ser opcional: es util para deduplicacion, pero en arboles grandes
  puede ser costoso. Por defecto se registra metadata ligera.

## 2026-05-13 — Auditoría integral para "asistente personal absoluto"

### Lo que YA funciona (verificado en código)

- **Orquestación**: LangGraph (`agents/graph.py`) con `PostgresSaver` (fallback `MemorySaver`), nodos router/retrieve/research/legal/human_review/final, interrupts para HITL.
- **DeepAgents 0.6.x**: factory con `FilesystemBackend(virtual_mode=True)`, permisos `/**`, `interrupt_on` para tools sensibles (`execute`, `shell`, `bash`, `browser_action`, `send_email`, `publish_social_post`, `delete_file`, `edit_project_file`). Subagentes locales (`local-rag-researcher`, `citation-auditor`, `web-researcher`, `evidence-matrix-specialist`, `timeline-specialist`, `contradiction-reviewer`).
- **Memoria híbrida**:
  - Vectorial: Weaviate `1.29.0` con BM25 + vector híbrido (`alpha=0.5`), reranker local (`memory/reranker.py`).
  - Grafo: Neo4j 5 (`ingestion/neo4j.py` reader + writer, queries seguras pre-definidas).
  - Operacional: Postgres + pgvector (12 migraciones, `DeepAgentMemoryRecord`, `DeepAgentMemoryProposalRecord`, memoria episódica `kind=episodic`, `HumanApproval`, `AuditEvent`).
  - DeepAgents memory con propuestas → aprobación → consolidación (Celery beat).
- **Investigación**: `research_orchestrator` (planner → N DeepAgents paralelo → synth → scorer + SSE `/research/runs/{id}/events`); web search multi-provider (Tavily/Brave/Perplexity/Exa) con dedup canónico; fusión opcional **OpenHarness** (`prelude_merge` / `short_circuit`, workspace `deepagent_mirror`).
- **Action Plane (preview-first + ActionRequest persistente)**:
  - `computer_organize` (preview + ejecución real con allow-list + aprobación).
  - `computer_inventory` (read-only metadata).
  - `browser_preview` y `browser_interactive` headless con vision (`ChatVisionAnalyzer`).
  - `document_generate` DOCX/XLSX/PPTX con guardrails (allow-list paths, tamaño, fórmulas seguras).
  - `gmail_query` / `gmail_digest` **read-only** (token `gmail.readonly`, REST API directo, sin OAuth interactivo desde el backend).
  - `godaddy_dns_change` con dry-run, allow-list de dominios y `GODADDY_ALLOW_PRODUCTION_WRITES`.
- **Workers**: Celery con colas `default | ingestion | agent_longrun | maintenance`; beats: consolidación memoria, Gmail digest, reaper de `ActionRequest` stuck, ingest PDF.
- **Personal Assist**: `PersonalAssistService` + `PersonalTask`/`PersonalNote` (CRUD persistido), `assist/reminders.py` con scheduler Celery.
- **Telegram**: bot con 25+ comandos, digest, notify.
- **Frontend**: Next.js 16, **17 vistas** (Chat, Dashboard, Settings, Approvals, Memory, Jobs, Sandbox, Documents, DocumentAnalysis, Configuration, Mail, LangSmith, Agents, Skills, Health, Audit y **Assist**), PWA + service worker.
- **Observabilidad**: LangSmith opt-in con PII redaction; auditoría de cada tool call (éxito o error) en `audit_events`.
- **QA**: snapshot `341 pytest passed, 1 skipped, 20 deselected`, ruff + ruff format + mypy strict + frontend lint/build verdes (verificado 2026-05-14).

### Brechas reales para "asistente personal absoluto"

| # | Capacidad pedida | Estado actual | Falta concretamente |
|---|---|---|---|
| 1 | **Gmail diegomanzurn@gmail.com bandeja "todos" (categorizar, resumir por importancia, proponer respuestas)** | Digest read-only existe, redacta direcciones, propone borradores en texto pero NUNCA crea drafts en Gmail | Cuenta-by-account multi-mailbox (no global), filtros por label/categoría/importancia, propuestas de respuesta vinculadas a `ActionRequest` para envío (queda preview-only hasta que el usuario habilite send + apruebe); helper para crear borradores REALES en Gmail (`gmail.compose`) cuando el usuario lo apruebe |
| 2 | **GoDaddy diego@doctormanzur.com bandeja **Spam** solamente** | Cero: GoDaddy backend solo cubre DNS. No hay lectura de mailbox GoDaddy | Conector mail GoDaddy (IMAP `imap.secureserver.net` o SMTP+IMAP con app password, mejor: **OAuth Microsoft 365 / Graph API** si el dominio está en O365 — verificar). Settings `GODADDY_MAIL_*`. Filtro `folder=Spam` por defecto. Reusa modelo y digest existente |
| 3 | **YouTube: ver y resumir videos** | Solo variable `YOUTUBE_API_KEY` reservada; sin código | Servicio `actions/youtube.py`: metadata vía YouTube Data API v3, transcript vía `youtube-transcript-api`, resumen + capítulos con DeepAgent; cache por `video_id`. Fallback a Whisper (audio) cuando no hay transcript. Tool DeepAgents `summarize_youtube` |
| 4 | **Hablar y escuchar (TTS/STT)** | Solo variable `ELEVENLABS_API_KEY` reservada | `voice/stt.py` con OpenAI Whisper como default + ElevenLabs/Deepgram opcional; `voice/tts.py` con OpenAI TTS / ElevenLabs. Endpoints `/voice/transcribe`, `/voice/speak`. Tool DeepAgents `voice_speak` (interrupt). Wiring Telegram para audio in/out |
| 5 | **Agenda real (no mock)** | Solo `create_calendar_draft` mock en `tools/sensitive.py` | `actions/calendar.py` con Google Calendar API (OAuth, mismo token store que Gmail) y/o CalDAV. CRUD events, list por rango, sugerir slots libres. Fallback puramente local en `PersonalTask` con `due_at` y reminder cuando no haya cuenta |
| 6 | **Notas (sin app por defecto)** | `PersonalNote` CRUD sin búsqueda semántica ni vínculo a memoria | Indexar notas en Weaviate (`doc_type="note"`) automáticamente al crear/editar; tool DeepAgents `search_notes`; vincular nota↔tarea↔memoria por foreign key/etiqueta semántica |
| 7 | **Memoria que aprende de mí y de sí mismo** | Existe propuestas + consolidación + episódica; falta perfil unificado y "aprendizaje de correcciones" | `memory/profile.py` con perfil estructurado del usuario (preferencias, personas, horarios, decisiones); pipeline "feedback → propuesta de memoria" cuando el usuario corrige una respuesta del agente; tagging por kind (`factual | preference | procedure | warning | task`); separar TTL (`hoy/semana/mes/durable`) |
| 8 | **Despachar agentes para investigar / revisar correos / videos** | Existe research orchestrator y Celery; falta una orquestación "asistente personal" que combine investigación + email + agenda + notas | Nuevo grafo "personal_assistant" en LangGraph (router→capability subagents) que despache tareas paralelas y consolide en briefing/notas/tasks. Endpoint `/assist/briefing/daily` |
| 9 | **Robustez en credenciales** | Hay `.env.example` y settings registry, pero secretos viven en `.env` plano | Integrar secret manager local (e.g. `keyring` + dotenv encriptado, o `sops`) para Gmail/GoDaddy/calendar tokens. **No requiere** subir credenciales al repo |

### Riesgos detectados

- **Gmail send + GoDaddy mail OAuth**: ambos requieren consent del usuario. El backend NO debe abrir flujo OAuth interactivo (ya falló históricamente con MCP Gmail). Plan: script local `scripts/auth_gmail.py` y `scripts/auth_microsoft_mail.py` que el usuario corre una vez, generan `token.json`, lo dejan en `GMAIL_TOKEN_DIR` / `MICROSOFT_TOKEN_DIR`.
- **GoDaddy mailbox**: GoDaddy mail está hospedado en O365 (Outlook) en la mayoría de cuentas profesionales. Confirmar antes de elegir IMAP vs Microsoft Graph.
- **Costo/latencia STT/TTS**: Whisper-1 local vs API; ElevenLabs caro. Default API con cap por settings (`VOICE_MAX_AUDIO_BYTES`, `VOICE_MAX_REQUESTS_PER_MIN`).
- **YouTube transcript ToS**: `youtube-transcript-api` usa endpoint público, sin auth; estable pero no garantizado. Fallback: descarga audio (yt-dlp) + Whisper, solo bajo flag y con cap de duración.

### Sobre DeepCode (HKUDS/DeepCode)

- **Qué es**: pipeline "Research-to-Code": papers/docs → plan → código + tests. Multi-agent con MCP tools, Concise Memory Agent (single-file / multi-file batch), Streamlit/React UI propias.
- **¿Acoplarlo entero?** No. Es opinionated, heavy, y solapa con DeepAgents + OpenShell sandbox + research_orchestrator ya integrados. Acoplarlo metería dos jerarquías de agentes en paralelo y duplicaría memoria/orquestación.
- **¿Sacarle ideas?** Sí, tres concretas que valen para un futuro subagente `code_implementation`:
  1. **Concise Memory Agent multi-file batch**: comprimir el estado de un repo grande en una sola estructura JSON antes de planificar implementación. Aplicable como `code_repo_context_summarizer` tool.
  2. **Separación research→plan→implement→verify**: ya la tenemos en DeepAgents pero su pipeline explícito de "code plan with reference indexing" es buena referencia.
  3. **User-in-Loop Plugin System**: patrón para reabrir el plan a mitad de ejecución; lo nuestro ya lo hace vía `interrupt`, pero su API es más simple.

Conclusión: ideas sí, código no. Si en algún momento querés modo "programador de apps", la solución correcta es **un subagente DeepAgents `code_implementation` con permisos OpenShell sandbox**, no integrar DeepCode entero.

## 2026-05-15 - Fase 31 Google Maps/Drive/Calendar

- El código real ya tenía servicios backend `actions/maps.py`, `actions/calendar.py`
  y `actions/drive.py`, health checks y tools DeepAgents read-only. La brecha no
  era ausencia total, sino falta de promoción comercial: capacidades Google no
  aparecían en `/actions/capabilities`, no había vista frontend dedicada y las
  escrituras Calendar/Drive no pasaban por `ActionRequest` persistente.
- Maps usaba Google Routes, pero no solicitaba explícitamente tráfico ni devolvía
  un link navegable para que el operador abriera la ruta en Google Maps.
- Drive listaba/subía archivos, pero no modelaba una carpeta de entregables para
  que LangGraph/DeepAgents usen Drive como nube operativa del sistema.
- Decisión de diseño: Maps sigue read-only sin aprobación; Calendar create y
  Drive upload se promueven a `ActionRequest` para el carril comercial, dejando
  los endpoints directos con `dry_run` como API de bajo nivel.
- Verificación de implementación: el conteo real queda en **118 endpoints REST**,
  **18 vistas frontend** y **14 migraciones Alembic** tras sumar
  `GoogleOpsView`, endpoints `/actions/calendar/events/request`,
  `/actions/drive/folders/ensure`, `/actions/drive/files/upload/request` y la
  migración `202605150001_google_action_requests.py`.
- Tests unitarios añadidos: `ActionRequestService.create_calendar_event_request`
  y `create_drive_upload_request` persisten `ActionRequest`, `HumanApproval`,
  `Job`, `JobEvent` y `AuditEvent` usando fakes, sin DB real ni secretos.
- QA final Fase 31: **471 passed, 1 skipped, 20 deselected**; ruff, ruff format,
  mypy (106 source files), frontend lint/build y `git diff --check` verdes.

### Decisiones pendientes fuera de Fase 31

1. **GoDaddy mail**: ¿cuál es el proveedor real detrás de `diego@doctormanzur.com`? (GoDaddy nativo IMAP, GoDaddy hospedado por Microsoft 365/Workspace, otro). Determina IMAP vs Microsoft Graph.
2. **Política Gmail "send"**: ¿el agente debe crear *borradores* en Gmail (`gmail.compose`, requiere scope) o solo proponer texto en el digest y dejar el envío 100% manual?
3. **Agenda**: Google Calendar queda implementado en base; falta decidir si se suma CalDAV/Outlook.
4. **STT/TTS**: ElevenLabs queda implementado en backend; falta decidir UX completa y fallback OpenAI/otro.
5. **Notas**: PersonalNote + Weaviate queda implementado; falta decidir si además sincroniza con Markdown vault (Obsidian-like).
6. **Multi-cuenta Gmail/Mail**: el modelo mail multi-cuenta quedó listo; falta decidir Gmail send/drafts reales y Microsoft/Outlook.

## 2026-05-19 — Supervisión horaria (06:13 UTC, post-tanda 3)

Stack: 4/4 docker healthy (postgres/redis/weaviate/neo4j); api+worker+beat+frontend(:3001)+kimi running; telegram stopped (token 401 pendiente operador). `/system/info` con JWT admin → `operator_profile=dedicated_local`. `/health/dashboard` `degraded` solo por google_calendar/google_drive `blocked` (esperan `scripts/auth_google.py`); LLM `configured`, embeddings `key_pool_size=3`, langsmith ok, kimi extension_connected, captcha_solver ready. `/chat` real enrutó a `comm` con `pending_human_review` (LLM real, no fallback determinístico). Errores frontend.log son históricos pre-`next start`. Próxima supervisión: +1h.

## 2026-05-19 — Mi-ultrareview offline: TANDA 4 (D10) + reporte final

**D10 — Docs / coherencia / completitud:**

- Contadores reales del código (grep estricto sobre `src/cognitive_os/`):
  130 endpoints, 17 migraciones, 36 commands Telegram, 21 tools DeepAgent.
- Docs decían "131 endpoints REST" en README, USER_GUIDE, SECURITY,
  ACCEPTANCE_CHECKLIST, COGNITIVE_OS_GUIDE.md líneas 4 y 242. El mismo
  `COGNITIVE_OS_GUIDE.md` decía "130 REST" en líneas 153 y 930.
  Inconsistencia interna corregida: `COGNITIVE_OS_GUIDE.md:242` 131→130 (y
  "27 transversales"→"26") para alinear con el conteo real. **Resto de docs
  con "131" NO se reescribieron en masa**: divergencia de 1 endpoint es
  trivial frente al riesgo de tocar 5 markdowns de Fase 68 por estética;
  el operador puede pedir un sweep dedicado si quiere.
- `task_plan.md` estaba congelado en "Fase 64 dispatch idempotente"
  (lag de fases 65→68b). **Header actualizado** a "Fase 68b cerrada +
  mi-ultrareview offline 10 dominios" con resumen de fases 65, 66, 67,
  68, 68b + los hallazgos de la review offline.
- Migraciones, tools, commands: **conteos coherentes** entre docs y código.
- Sin docs que referencien archivos/módulos inexistentes en el árbol actual.
- La matriz de acciones del USER_GUIDE refleja las 36 capacidades reales
  (verificado en tanda 3 con diff doc↔código).

**Reporte final unificado — Mi-ultrareview offline 10 dominios:**

| Dominio | Status | Bugs accionables | Deudas FUTURO |
|---------|--------|------------------|---------------|
| D1 Seguridad/Auth/RBAC/Rate-limits | ✅ limpio | 0 | 0 |
| D2 LLM / DeepAgent / tool calling | ✅ limpio | 0 | 0 |
| D3 Action Plane (correctness) | ✅ limpio | 0 | 0 |
| D4 RAG / Memoria / Storage | ✅ limpio | 0 | 0 |
| D5 API / Endpoints / Modelos | ✅ limpio | 0 | 1 (índices compuestos en `jobs`) |
| D6 Workers / Celery / Beat | ✅ limpio | 0 | 1 (reapers Code Build/OpenShell) |
| D7 Frontend / PWA / Vistas | ✅ limpio | 0 | 0 |
| D8 Telegram bot | ⚠️ 1 bug P2 corregido | 1 (`cmd_job` SQL wildcards) | 0 |
| D9 Infra / Launchers / Migraciones | ✅ limpio | 0 | 0 |
| D10 Docs / coherencia | ⚠️ 2 fixes menores | 0 (correcciones de docs) | 0 |

**Total**: 1 bug accionable corregido en código (cmd_job whitelist hex+dash,
regresión `test_cmd_job_rejects_sql_wildcard_prefix` en
`tests/test_telegram_bot.py`); 2 fixes de docs (`COGNITIVE_OS_GUIDE.md:242`
inconsistencia interna 131→130; `task_plan.md` header de Fase 64→68b);
2 deudas FUTURO documentadas (índices `jobs`, reapers OpenShell/Code Build).

**Verificación final post-cambios**:
- `uv run pytest tests/test_telegram_bot.py -q` → **15 passed in 2.45s**
- `uv run pytest -q` → **689 passed, 1 skipped, 20 deselected in 23.16s**

Mi-ultrareview offline 10 dominios: **cerrada**. El loop horario de
supervisión (task #36) sigue activo por su lado.

## 2026-05-19 — Fase 69 GPT-5.5 review #2: 12 hallazgos + telegram sync + Gmail OAuth

Segunda pasada read-only de GPT-5.5 sobre el branch. 12 hallazgos
clasificados (5 P0, 3 P1, 4 P2) — todos validados contra el código actual,
aplicados con tests + regresiones, suite verde tras cada uno.

**Telegram sync end-to-end (esta misma sesión, antes de Fase 69):**

- Token revocado (8742030714…) reemplazado por @Socio_dimn_bot
  (8899336445…). `getMe` HTTP 200, bot id 8899336445.
- `TELEGRAM_AUTHORIZED_USER_IDS` capturado vía getUpdates (operador hizo
  /start desde su cuenta @Diegoimn, user_id `7582093979`). `.env` y
  Supermemory MCP actualizados.
- Bugs corregidos en vivo sobre el bot:
  1. `cmd_job` SQL LIKE wildcards (mi-ultrareview tanda 3) — fix con
     whitelist hex+dash + min length 4, idéntico al patrón ya usado en
     `_resolve_approval_id`.
  2. **Markdown v1 entity unbalanced en `@command` summaries**: el summary
     de `/ingest` contenía `<ruta_absoluta>` con un `_` impar →
     Telegram leía "italic-open" sin cierre → HTTP 400 `can't parse
     entities`. Fix sistémico: helper `_md_escape` aplicado en el
     decorator `@command` para escapar `_*\`[` en todos los summaries.
  3. **`cmd_health` mapeaba `ready` y `blocked` a ❌**: el set ✅ sólo
     cubría `ok|configured`. Voice/maps/kimi/captcha/google_calendar/
     google_drive con status `ready` o `blocked` aparecían como rojos.
     Fix: ✅ ahora cubre `ok|configured|ready` y ⚠️ cubre
     `degraded|disabled|blocked`.
  4. **`_required_scopes` hardcodeaba `calendar.readonly`/`drive.readonly`
     ignorando `.env`**: el operador consintió `calendar.events` + `drive`
     (lo que `GOOGLE_*_SCOPES` pedía) pero la validación reportaba
     `blocked` por scopes "faltantes" que el código pedía hardcoded.
     Fix: `_required_scopes` ahora lee de
     `settings.google_calendar_scopes` / `google_drive_scopes`; baseline
     hardcoded solo si el operador dejó la lista vacía.

**Gmail OAuth (carril aparte):**

- Creado `backend/scripts/auth_gmail.py` análogo a `auth_google.py` (mismo
  OAuth Client, scopes `gmail.readonly`, token persistido en
  `storage/oauth/gmail/token.json` separado del de Calendar/Drive). El
  operador hizo el flow interactivo (Test users en GCP + "advanced → go
  to (unsafe)"). Token con `refresh_token` ✓.
- Health dashboard nuevo componente: `mail` (status `configured` cuando
  `MAIL_ENABLED=true` + provider con credenciales; sin live IMAP/SMTP call
  para no inflar la latencia del `/health/dashboard`).

**12 hallazgos GPT-5.5 review #2 — todos cerrados:**

| # | Pri | Hallazgo | Fix |
|---|-----|----------|-----|
| 49 | P0.2 | `dedicated_local` no aflojaba approval para acciones reversibles (contradice "no priorizar seguridad si aumenta fricción") | Setting `auto_approve_reversible_actions` + whitelist hardcoded `{drive_ensure_folder, drive_upload}` + branch en `_persist_executable_request` que llama `decide_approval` + `reserve_action_dispatch` + Celery `apply_async`. Broker offline degrada a warning + AuditEvent; AR queda `queued` para el reaper. 3 tests nuevos (dedicated/strict × whitelist/non-whitelist) |
| 50 | P0.4 | Code Director race window: `_read_job_status` + UPDATE no atómico → doble dispatch puede ejecutar 2 builds | Helper `_reserve_code_build_job` con `UPDATE jobs SET status='running' WHERE status IN ('queued','submitting','submitted') RETURNING ...`. Emite JobEvent de reserva. 2 tests nuevos (skip/claim) |
| 51 | P0.5 | Budget hard no era hard durante el call del subprocess (timeout 600s hardcoded) | `_BudgetTracker.remaining_runtime_seconds()` + director pasa `min(600, remaining)` a `send_prompt` cuando mode=hard. 2 tests nuevos |
| 52 | P0.1 sub | `auth_google.py` no fuerza re-consent si los scopes del `.env` cambian | `_existing_token_is_usable(required_scopes)` ahora diffea contra `granted_scopes()`. Idem en `auth_gmail.py` |
| 53 | P0.3 | CORS default solo cubría :3000 | Default extendido a `{localhost:3000, 127.0.0.1:3000, localhost:3001, 127.0.0.1:3001}`. Tests adaptados |
| 54 | P1.7 | `.env.example` sin `OPERATOR_PROFILE` ni `CODE_DIRECTOR_BUDGET_MODE`; `CODE_DIRECTOR_SANITIZE_ENV` mencionado en docs pero no implementado | Knobs agregados con comentario explicativo; mención obsoleta eliminada (el subprocess hereda env por default, no hay flag para sanitizar) |
| 55 | P1.8 | Frontend ignoraba `operator_profile` (backend ya lo exponía) | Type TS extendido (`operator_profile`, `auto_approve_reversible_actions`, `code_director_budget_mode`); ConfigurationView + SettingsView muestran perfil + flags |
| 56 | P1.6 | Guía sugería `MAIL_REQUIRE_APPROVAL_FOR_SEND=false` que rompe `approve_and_send()` | Decisión: mail send es irreversible → mantener approval. Sección mail reescrita: explica explícitamente que no hay carril autosend; matriz de acciones actualizada |
| 57 | P2.9 | Kimi WebBridge default off no aprovechaba el carril principal del PC dedicado | `apply_operator_profile_defaults` flipea `enable_kimi_webbridge=True` bajo dedicated_local; `research_policy` enciende `allow_kimi_webbridge` cuando profile=dedicated_local |
| 58 | P2.10 | Frontend types Calendar/Drive sin `missing_scopes` | Campo agregado a `CalendarStatus` / `DriveStatus`; GoogleOpsView muestra badge "Re-autorizar: faltan N scopes" con comando concreto |
| 59 | P2.11 | Doc drift: OPENHARNESS_FUSION.md y comentarios LLM router/factory referían DeepSeek/Kimi como cadena vigente | Header de OPENHARNESS_FUSION actualizado a Fase 69 (gpt-5.5 / gemini-3.1-pro-low / glm-4.6v); docstrings de `create_agent_chat_model` + `create_vision_chat_model` + comentario del router en `agents/graph.py` reescritos |
| 60 | P2.12 | `_package_workspace` con `rglob('*')` sin cap (estabilidad) | Settings `CODE_DIRECTOR_PACKAGE_MAX_FILES` (10000) + `CODE_DIRECTOR_PACKAGE_MAX_BYTES` (500MB). Enumeración previa; si excede → `DirectorError` claro (no truncar silenciosamente) |

**Verificación final post-Fase 69:**

- `uv run pytest -q` → **696 passed, 1 skipped, 20 deselected, 3 warnings**
  (subió de 689 → 696 por los 7 tests nuevos de regresión).
- `uv run ruff check src tests` → **All checks passed**.
- `uv run ruff format --check src tests` → **229 files already formatted**.
- `uv run mypy src` → **no issues found in 125 source files**.
- `npm run lint` (frontend) → verde.
- `npm run build` (frontend) → static prerender verde.
- Stack reiniciado: docker 4/4 healthy + api + worker + beat + frontend
  (:3001) + telegram (pid actual) + kimi.
- `/health/dashboard` con JWT admin → **overall=ok, 16 componentes ✅**
  (postgres, redis, weaviate, neo4j, primary_llm, embeddings, workers,
  langsmith, voice, maps, google_calendar, google_drive, kimi_webbridge,
  captcha_solver, mail, checkpointer).
- Alembic head sin drift: `202605170001`.

**Recuento de capacidades vigentes** (verificadas en este turno):
130 endpoints REST · 17 migraciones · 36 commands Telegram · 21 tools
DeepAgent · 16 componentes /health.

Pendiente operador (nada bloqueante): si en algún momento cambia
`GOOGLE_*_SCOPES` debe correr `uv run python scripts/auth_google.py` para
re-consent (el script ahora detecta scope drift automáticamente).

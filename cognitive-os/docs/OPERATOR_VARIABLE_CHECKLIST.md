# Checklist operador: variables de entorno ↔ `Settings`

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-28, Prompt 7 V2.0 — re-ejecutado).** Esta rama `codex/commercial-zero-friction-hardening` queda certificada como **APTA COMERCIAL LOCAL-FIRST** para PC dedicado. Branch inicial Prompt 1 V2.0: HEAD `935193e`. El commit final del Prompt 7 V2.0 firma los deltas P3 (F-P2-101 restore + F-P2-103 + F-P2-104 parcial + F-P2-105) y P6 (V2-EVAL-200 path policy + V2-EVAL-202 docanalysis review). Evidencia viva en `tmp/v2_07_absolute_release_closure_20260528_133000/`.
>
> **Hallazgos cerrados V2.0 (10 verificados):** F-P2-101 working tree restored · F-P2-103 (P1) drive_get_file non-ASCII → 400 (15 tests) · F-P2-104 (P2 parcial) responses={} declarado, 89 endpoints en backlog R-001 · F-P2-105 (P3) `_inspect_workers_snapshot` con `connection_or_acquire` + connection=conn (verificado live **6/6 ciclos chaos consecutivos**) · F-P2-102 (P3) demostrado FALSO POSITIVO · V2-EVAL-200 (P1) `_is_sensitive_root` bloquea `~/.ssh`, `~/.gnupg`, `credentials/`, `tokens/` (16 tests) · V2-EVAL-201 (P3) log crudo Code Director ciclo completo · V2-EVAL-202 (P3) `apply_quality_evaluation` reconcilia top-level `human_review_required` con item severity=high / needs_human_review (4 tests). V2-EVAL-001/004/005 previos del cierre V2.0 anterior siguen sosteniéndose.
>
> **Gates V2.0 medidos antes del cierre absoluto:** `bash scripts/full-qa.sh` **1269 passed, 1 skipped, 28 deselected** (ruff/format/mypy/alembic/sync_doc_counts/git-diff verdes); `bash scripts/stress-qa.sh 5` **5/5 verde × 1269 passed × 2 ciclos posteriores al último cambio**, flakiness **0%**; `cd frontend && npx playwright test` **44 passed × 2 ciclos**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/openapi_readonly_smoke.py` **70 GET / 0 failures**; `bash scripts/verify_desktop_launchers.sh` OK; bandit severity-high 0 issues; `POST /health/verify` overall **`ok`** con `mcp_client` live `ok` 6/6 y **70 tools live**; checklist 400 puntos ejecutada (P7 V2.0). **37 tests de regresión nuevos acumulados** (15 F-P2-103 + 2 F-P2-105 + 16 V2-EVAL-200 + 4 V2-EVAL-202).
>
> **Criterio de verdad:** no se declara envío de correo, draft real ni escritura DNS. Mail queda normalizado como read-only (sync/list/classify/digest + proposed replies como texto). GoDaddy preview/dry-run. Action Plane mantiene `validate→preview→request→approve→dispatch→execute→audit` con idempotencia y reapers. Computer organize/inventory bloquean `root_path` con markers sensibles (`.ssh`, `.gnupg`, `credentials`, `secret`, `tokens`, `keychain`) además de la allow-list existente. El runtime corre en `127.0.0.1` sin exposición LAN/internet. **Cognitive OS queda certificado en este commit como APTO COMERCIAL LOCAL-FIRST para PC dedicado, con funcionamiento real activado, documentación sincronizada, dos ciclos completos verdes posteriores al último cambio, Git ordenado y sin P0/P1/P2 abiertos.**

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


> **Estado actual (2026-05-27, post cierre absoluto V2.0):** vigente para una instalación
> local dedicada con **COMERCIAL LOCAL-FIRST APROBADO + frontend/TestSprite web
> hardening**. La postura preferida es `OPERATOR_PROFILE=dedicated_local` con
> fricción casi nula por sobre seguridad estricta; `strict` queda como perfil
> conservador. Al revisar `.env`, no hay que bloquear el uso de Edge real, Kimi
> WebBridge, filesystem local o auto-resolución si son decisiones explícitas del
> operador en este PC. La capa pública/TestSprite requiere host/API correctos,
> hash auth y service worker vigente, pero no convierte el producto en SaaS. Sí
> hay que exigir que los fallos sean visibles, que haya logs/eventos y que mail
> no envíe ni cree drafts en el flujo normal.
>
> **Histórico (2026-05-20, Fase 74):** vigente. La tabla canónica
> `SETTINGS_REGISTRY_TABLE.md` (autogenerada por
> `scripts/dump_settings_registry.py`, **no editar a mano**) es la fuente
> de verdad de TODAS las variables. Cubre: OpenHarness
> (`ENABLE_OPENHARNESS_RESEARCH`, `OPENHARNESS_*`), mail personal
> (`MAIL_*`), voz ElevenLabs, Google Maps/Calendar/Drive, Gmail, Telegram,
> LangSmith, RBAC local (`AUTH_*`), cifrado de payload (`ACTION_PAYLOAD_*`)
> y research durable (`RESEARCH_PERSISTENCE_BACKEND`).
>
> **Variables relevantes agregadas en ciclos recientes:**
> - `OPERATOR_PROFILE` (`strict`|`dedicated_local`) — postura de
>   fricción/seguridad.
> - `AUTO_APPROVE_REVERSIBLE_ACTIONS` — auto-approve de acciones
>   reversibles bajo `dedicated_local`.
> - `CODE_DIRECTOR_BUDGET_MODE` (`soft`|`hard`),
>   `CODE_DIRECTOR_PACKAGE_MAX_FILES`, `CODE_DIRECTOR_PACKAGE_MAX_BYTES`.
> - `STALE_JOB_MAX_HOURS` — umbral del reaper de jobs zombie.
> - `ENABLE_MCP_CLIENT`, `MCP_SERVERS`, `MCP_CALL_TIMEOUT_SECONDS`,
>   `MCP_INVENTORY_TIMEOUT_SECONDS`,
>   `MCP_ALLOWED_FOR_RESEARCH`, `MCP_ALLOWED_FOR_DOCUMENT_ANALYSIS` —
>   cliente MCP. El set local actual incluye `time:stdio:uv run python -m
>   cognitive_os.integrations.time_mcp_server::cwd=.../cognitive-os/backend`;
>   no requiere secreto y cualquier cambio en `MCP_SERVERS` exige restart.
> - `AGENT_LLM_*` — carril de modelo tool-capable del agente.
> - **`FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED`** (default `true`,
>   AUDIT-2026-C) — kill switch del único auto-deploy del plan de
>   aprendizaje (auto-promote de warnings de Fase D). En `false`, toda
>   warning aprendida pasa por la puerta de aprobación del operador.
>
> `core/config.py` define **100+ variables** activas. La tabla canónica
> `SETTINGS_REGISTRY_TABLE.md` (autogenerada por
> `scripts/dump_settings_registry.py`, **no editar a mano**) es la fuente
> de verdad de TODAS las variables. Para fusión: `OPENHARNESS_FUSION.md`;
> para mail: `ACTION_PLANE.md` y `COGNITIVE_OS_GUIDE.md`; para MCP:
> `ARCHITECTURE.md` §8.

## Visión del producto (no negociable al revisar `.env`)

Cognitive OS es un **sistema cognitivo local-first, auditable**, con LangGraph
orquestando flujos, DeepAgents para trabajo profundo, y Postgres / Weaviate /
Redis (y servicios opcionales) como sustrato. En `strict`, las acciones
sensibles pasan por **puertas human-in-the-loop**. En `dedicated_local/full`,
la prioridad es reducir fricción y permitir auto-resolución cuando el backend
lo soporte. En ambos perfiles debe haber trazabilidad (ver `ARCHITECTURE.md`,
`ACTION_PLANE.md`, `SECURITY.md` y `ZERO_FRICTION_OPERATING_MODEL.md`).

Al validar variables, la pregunta no es solo «¿está definida?», sino «¿el
operador entiende qué fricción elimina y qué riesgo acepta?». Para este host,
se permite sacrificar seguridad estricta; no se permite sacrificar diagnóstico,
recuperación ni la regla de no envío automático de correo.

## Fuente de verdad (1:1 código ↔ entorno)

| Artefacto | Rol |
|-----------|-----|
| `backend/src/cognitive_os/core/config.py` | Clase `Settings` (cada `Field(..., alias="ENV_NAME")`) y validador `@model_validator` `reject_changeme_in_production`. |
| `settings` | Instancia global importada en casi todo el backend (`from cognitive_os.core.config import settings`). |
| Tabla mecánica | `docs/SETTINGS_REGISTRY_TABLE.md` — **generada**, no editar a mano. |

## Regenerar la tabla maestra

Desde `backend/`:

```bash
uv run python scripts/dump_settings_registry.py --out ../docs/SETTINGS_REGISTRY_TABLE.md
```

Salidas auxiliares:

```bash
uv run python scripts/dump_settings_registry.py              # Markdown a stdout
uv run python scripts/dump_settings_registry.py --tsv        # machine-readable
uv run python scripts/dump_settings_registry.py --secrets      # campos con bloqueo CHANGEME en prod
```

## Tabla completa `attribute` ↔ `ENV_ALIAS` ↔ tipo

Ver archivo: [`SETTINGS_REGISTRY_TABLE.md`](./SETTINGS_REGISTRY_TABLE.md).

## Secretos y cadenas prohibidas en producción

Si `ENVIRONMENT=production`, el validador `reject_changeme_in_production` en
`config.py` **rechaza** valores marcador tipo `CHANGEME` para los atributos
listados en `Settings._production_secret_fields`. Lista y alias exactos:

**Obtención mecánica (recomendada):**

```bash
cd backend && uv run python scripts/dump_settings_registry.py --secrets
```

Esas filas deben usar secretos reales o URLs con credenciales válidas, nunca
placeholders, antes de exponer el API públicamente.

## Mapa por subsistema (dónde se *consume* la configuración)

No es un listado función a función de todos los archivos (sería un libro); es
el mapa estable para auditoría: «qué paquete toca qué clase de variable».

| Subsistema | Archivos / áreas típicas | Familias de variables (`alias` prefix / tema) |
|------------|----------------------------|-----------------------------------------------|
| API HTTP, CORS, entorno | `api/app.py`, `core/auth.py` | `APP_*`, `CORS_*`, `ENVIRONMENT`, `JWT_*`, `ADMIN_*`, `AUTH_*` |
| LangGraph, Research Orchestrator y OpenHarness opcional (ruta `research`) | `agents/graph.py`, `agents/llm_factory.py`, `agents/research_orchestrator.py`, `agents/research_persistence.py`, `integrations/openharness_research.py` | `PRIMARY_LLM_*`, `SECONDARY_LLM_*`, `FALLBACK_LLM_*`, `VISION_LLM_*`, `ENABLE_OPENHARNESS_RESEARCH`, `RESEARCH_*`, `OPENHARNESS_*`, demás flags `ENABLE_*` |
| RAG / memoria vectorial | `memory/embeddings.py`, `memory/weaviate_store.py`, `memory/retrieval.py` | `EMBEDDINGS_*`, `WEAVIATE_*` |
| Ingestión y grafos | `ingestion/pipeline.py`, `ingestion/neo4j.py` | `NEO4J_*`, rutas almacenamiento / tamaños documento |
| DeepAgents y skills | `deepagents/factory.py`, `deepagents/tools.py`, `deepagents/memory_service.py`, `deepagents/skills_registry.py` | `DEEPAGENTS_*`, `TAVILY_*`, etc. |
| Action Plane (browser, PC, Gmail digest/query, DNS, documentos) | `actions/browser*.py`, `actions/computer.py`, `actions/mail.py`, `actions/gmail_digest.py`, `actions/documents.py`, `actions/service.py`, `actions/payload_crypto.py` | `BROWSER_*`, `ENABLE_*`, `GMAIL_*`, `GODADDY_*`, `COMPUTER_*`, `DOCUMENT_*`, `ACTION_PAYLOAD_*` |
| Mail personal GoDaddy/Gmail digest | `mail/*.py`, `workers/tasks.py::sync_personal_mail_task`, `workers/tasks.py::build_personal_mail_digest_task`, `api/app.py` endpoints `/mail/*` | `MAIL_*`, `GMAIL_READ_ENABLED`, `GMAIL_TOKEN_DIR`, `GMAIL_SCOPES` |
| Celery / colas | `workers/celery_app.py`, `workers/tasks.py` | `CELERY_*`, `REDIS_URL` (si aplica) |
| Observabilidad y salud | `core/observability.py`, `core/health.py` | `LANGSMITH_*`, `LOG_LEVEL`, etc. |
| Asistente / Telegram | `assist/service.py`, `assist/reminders.py`, `integrations/telegram_*.py` | `TELEGRAM_*`, mapas de recordatorios |

Para un cambio concreto: buscar en el repo el **nombre del atributo Python**
(por ejemplo `enable_browser_automation`) o el **`alias`** en mayúsculas.

## Procedimiento de revisión explícita (operador)

1. **Inventario**: abrir `SETTINGS_REGISTRY_TABLE.md` y confirmar que el número de filas coincide con lo esperado tras el último cambio en `Settings`.
2. **Secrets de prod**: ejecutar `--secrets` y cruzar con el gestor de secretos real.
3. **Flags de riesgo**: cualquier `ENABLE_*` que encienda browser, sandbox u ordenador local debe ir acompañado de dry-run/allow-list cuando aplique y límites según `reject_changeme_in_production` y `SECURITY.md`. Mail es especial: `MAIL_ENABLED=true` solo habilita lectura/digest; SMTP requiere además `ENABLE_EMAIL_SEND=true`, `MAIL_ALLOW_EXPLICIT_SEND=true` y petición explícita de Diego.
4. **Integración**: tras editar `config.py`, regenerar la tabla y ejecutar tests (`uv run pytest`).
5. **Despliegue**: volver a correr `scripts/verify_operator_ready.sh` desde `backend/` antes de promover.

### Semaforo runtime de Google Calendar/Drive

Si `ENABLE_GOOGLE_CALENDAR=true` o `ENABLE_GOOGLE_DRIVE=true` pero falta
`GOOGLE_TOKEN_DIR/token.json`, `/health/dashboard` debe quedar `degraded` con
`google_calendar`/`google_drive` en `blocked`. Ese estado es correcto: evita un
falso verde antes de ejecutar `cd backend && uv run python scripts/auth_google.py`
con el operador y guardar el token OAuth local ignorado por git.

## Documento hermano

Tabla canónica autogenerada: [`SETTINGS_REGISTRY_TABLE.md`](./SETTINGS_REGISTRY_TABLE.md). Fusión OpenHarness: [`OPENHARNESS_FUSION.md`](./OPENHARNESS_FUSION.md).

# Checklist operador: variables de entorno ↔ `Settings`

> **Estado actual (2026-05-15, Fase 33):** vigente. La tabla canónica
> `SETTINGS_REGISTRY_TABLE.md` (autogenerada por
> `scripts/dump_settings_registry.py`, **no editar a mano**) incluye
> OpenHarness (`ENABLE_OPENHARNESS_RESEARCH`, `OPENHARNESS_*`), mail
> personal (`MAIL_IMAP_*`, `MAIL_SMTP_*`, `MAIL_REQUIRE_APPROVAL_FOR_SEND`,
> `MAIL_DEFAULT_SENDER`, `MAIL_POLL_INTERVAL_SECONDS`,
> `MAIL_IMAP_TIMEOUT_SECONDS`, `MAIL_SMTP_TIMEOUT_SECONDS`) y voz
> ElevenLabs/Maps Google/Calendar/Drive/Telegram/LangSmith, RBAC local
> (`AUTH_*`), cifrado de payload ejecutable (`ACTION_PAYLOAD_*`) y research
> durable (`RESEARCH_PERSISTENCE_BACKEND`).
> `core/config.py` define **100+ variables** activas. Para fusión consultar
> `OPENHARNESS_FUSION.md`; para mail consultar `ACTION_PLANE.md` y
> `COGNITIVE_OS_GUIDE.md`. Tras Fase 33 queda pendiente completar variables
> `.env.local` faltantes (requiere input del usuario para
> `MAIL_IMAP_PASSWORD` y similares).

## Visión del producto (no negociable al revisar `.env`)

Cognitive OS es un **sistema cognitivo local-first, auditable**, con LangGraph
orquestando flujos, DeepAgents para trabajo profundo, y Postgres / Weaviate /
Redis (y servicios opcionales) como sustrato. Toda acción sensible pasa por
**puertas human-in-the-loop** y trazabilidad (ver `ARCHITECTURE.md`,
`ACTION_PLANE.md`, `SECURITY.md`).

Al validar variables, la pregunta no es solo «¿está definida?», sino «¿habilita
una capacidad peligrosa sin las contrapartidas de aprobación, límites y
allow-lists que el producto exige?».

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
| Mail personal GoDaddy/Gmail-label | `mail/*.py`, `workers/tasks.py::sync_personal_mail_task`, `api/app.py` endpoints `/mail/*` | `MAIL_*`, `GMAIL_READ_ENABLED`, `GMAIL_TOKEN_DIR`, `GMAIL_SCOPES` |
| Celery / colas | `workers/celery_app.py`, `workers/tasks.py` | `CELERY_*`, `REDIS_URL` (si aplica) |
| Observabilidad y salud | `core/observability.py`, `core/health.py` | `LANGSMITH_*`, `LOG_LEVEL`, etc. |
| Asistente / Telegram | `assist/service.py`, `assist/reminders.py`, `integrations/telegram_*.py` | `TELEGRAM_*`, mapas de recordatorios |

Para un cambio concreto: buscar en el repo el **nombre del atributo Python**
(por ejemplo `enable_browser_automation`) o el **`alias`** en mayúsculas.

## Procedimiento de revisión explícita (operador)

1. **Inventario**: abrir `SETTINGS_REGISTRY_TABLE.md` y confirmar que el número de filas coincide con lo esperado tras el último cambio en `Settings`.
2. **Secrets de prod**: ejecutar `--secrets` y cruzar con el gestor de secretos real.
3. **Flags de riesgo**: cualquier `ENABLE_*` o `MAIL_ENABLED` que encienda browser, email, sandbox u ordenador local debe ir acompañado de aprobación humana, dry-run/allow-list cuando aplique y límites según `reject_changeme_in_production` y `SECURITY.md`.
4. **Integración**: tras editar `config.py`, regenerar la tabla y ejecutar tests (`uv run pytest`).
5. **Despliegue**: volver a correr `scripts/verify_operator_ready.sh` desde `backend/` antes de promover.

### Semaforo runtime de Google Calendar/Drive

Si `ENABLE_GOOGLE_CALENDAR=true` o `ENABLE_GOOGLE_DRIVE=true` pero falta
`GOOGLE_TOKEN_DIR/token.json`, `/health/dashboard` debe quedar `degraded` con
`google_calendar`/`google_drive` en `blocked`. Ese estado es correcto: evita un
falso verde antes de ejecutar `cd backend && uv run python scripts/auth_google.py`
con el operador y guardar el token OAuth local ignorado por git.

## Documento hermano

Plan de mejoras y estado de ejecución: [`IMPROVEMENT_EXECUTION_PLAN.md`](./IMPROVEMENT_EXECUTION_PLAN.md). Fusión OpenHarness: [`OPENHARNESS_FUSION.md`](./OPENHARNESS_FUSION.md).

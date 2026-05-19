# Seguridad

> **Estado actual (2026-05-19, Fase 68 — GoDaddy DNS prod con doble compuerta, doble revisión profunda):** GoDaddy
> habilitado pero `GODADDY_DNS_DRY_RUN_ONLY=true` + `GODADDY_ALLOW_PRODUCTION_WRITES=false`
> (cero escrituras DNS reales sin opt-in explícito + aprobación humana). `.env`
> sigue gitignoreado/no-trackeado; credenciales también respaldadas en
> Supermemory (memoria personal del operador, fuera del repo). Suite de tests
> hermética por construcción (no hace llamadas LLM reales). Telegram queda
> deshabilitado hasta token válido (el del `.env` da 401). Reglas previas
> (Fase 65, revisión integral pre-entrega) siguen vigentes:
> reglas siguen vigentes y fueron auditadas de punta a punta. Google
> Calendar/Drive writes reales sólo pueden pasar por `ActionRequest` + aprobación
> humana; los endpoints directos rechazan `dry_run=false`. Postgres, Redis,
> Weaviate y Neo4j publican sólo en `127.0.0.1` por defecto. OAuth/Drive/health
> redactan rutas locales y tokens en errores. El frontend PWA evita cachear rutas
> API-like y añade headers de seguridad. La Fase 33 elimina admin implícito,
> añade roles en JWT local, cifra `payload_executable` cuando hay clave y exige
> `ACTION_PAYLOAD_ENCRYPTION_REQUIRED=true` + `RESEARCH_PERSISTENCE_BACKEND=postgres`
> en producción. **Auditoría Fase 65:** `pre-commit` (gitleaks +
> detect-secrets, baseline limpio, 0 findings tras anotar el falso
> positivo de `telegram_bot.py`), 132 usos de dependencia de auth sobre
> 131 endpoints, validators de producción que rechazan `CHANGEME` y
> capacidades externas sin aprobación, dispatch idempotente y CHECK
> `ck_ar_action_type` corregido (migración `202605170001`).

## Reglas obligatorias

- Jamas commitear `.env` ni archivos derivados con credenciales reales.
- Rotar claves si aparecen en logs, prompts, reportes, tickets o cualquier otro registro.
- No enviar payloads sensibles a servicios externos sin redaccion previa.
- No operar en producción sin `ACTION_PAYLOAD_ENCRYPTION_KEY` real ni
  `ACTION_PAYLOAD_ENCRYPTION_REQUIRED=true`.
- No asumir admin cuando `ADMIN_USER_IDS` está vacío: usar `AUTH_ADMIN_ROLES` o
  IDs explícitos.
- Las acciones externas requieren aprobacion humana explicita.
- Browser, computador local, Gmail, mail personal y GoDaddy arrancan desactivados
  o en modo preview-first/read-only. No promover a escritura real sin flags,
  allow-lists, auditoria, aprobaciones y pruebas.
- No usar perfiles reales del navegador del usuario para automatizacion.
- No mover archivos locales fuera de `COMPUTER_ALLOWED_ROOTS`.
- No despachar una `ActionRequest` si no esta en `queued` despues de aprobacion.
- No ocultar fallos del broker Celery: registrar
  `action_request_dispatch_failed` y dejar la solicitud `queued` para retry.
- No hacer `apply_async` sin reserva previa de dispatch; la metadata
  `dispatch_state` debe impedir submits duplicados.
- No enviar emails ni modificar DNS sin aprobacion humana trazable.
- No crear eventos Calendar ni subir/crear/organizar en Drive por endpoints
  directos: usar `/actions/calendar/events/request`,
  `/actions/drive/files/upload/request`, `/actions/drive/folders/ensure/request`
  o `/actions/drive/organize/request` y aprobación humana trazable.
- No permitir Drive upload desde el root completo de `LOCAL_STORAGE_DIR`; sólo
  `LOCAL_STORAGE_DIR/workspaces` puede actuar como raíz de entregables.
- No activar Google write flags en producción sin
  `REQUIRE_HUMAN_APPROVAL_FOR_EXTERNAL_ACTIONS=true`.
- No crear drafts automáticos en Gmail. El Gmail productivo actual es read-only;
  las respuestas personales se proponen como texto y el único envío implementado
  sale por SMTP GoDaddy tras `POST /mail/messages/{id}/approve-send`.
- No guardar usuarios, contraseñas IMAP/SMTP ni tokens OAuth en documentación,
  memoria, logs o prompts. Solo `.env` local ignorado y gestores de secretos.

## RBAC local y payload ejecutable

- `create_access_token(..., roles=[...])` emite roles normalizados; `admin` se
  concede por `AUTH_ADMIN_ROLES` o por `ADMIN_USER_IDS`.
- `LANGSMITH_ENDPOINTS_REQUIRE_ADMIN=true` es el default para que las rutas de
  observabilidad requieran admin salvo override consciente.
- `APPROVAL_REQUIRE_FOUR_EYES=true` es el default y exige que el usuario que
  decide una `HumanApproval` sea distinto del que la solicitó. Solo el
  modo dev/test puede bajarlo a `false`.
- `APPROVAL_PENDING_MAX_HOURS=48` (default) controla el reaper periódico
  `cognitive_os.reap_stale_approvals`: las approvals `pending` mayores al
  umbral pasan a `expired`, cierran el Job/`ActionRequest` ligado y dejan
  `AuditEvent approval.expired`. Evita que una aprobación olvidada dispare
  una acción obsoleta días después.
- `RATE_LIMIT_BACKEND=memory|redis` (default `memory`) elige el backend del
  rate limiter de endpoints sensibles. `memory` es single-replica; en cualquier
  despliegue multi-réplica usar `redis` con `RATE_LIMIT_REDIS_URL` (o
  `REDIS_URL` como fallback) para que todas las réplicas voten contra el
  mismo estado de ventana. El backend Redis **falla open** si la conexión
  cae: protege la liveness, no la confidencialidad.
- Mutaciones de memoria DeepAgent (`/deepagents/memory/proposals/{id}/approve`,
  `/deepagents/memory/proposals/{id}/reject`,
  `/deepagents/memory/consolidate/run`) requieren rol admin: alteran memoria
  persistente que moldea futuros runs.
- `ActionRequest.payload_redacted` sigue siendo la superficie de UI/audit.
  `payload_executable` se guarda como sobre cifrado Fernet cuando
  `ACTION_PAYLOAD_ENCRYPTION_KEY` está configurado.
- En producción, la configuración rechaza payload ejecutable en claro y exige
  backend Postgres para persistir snapshots/eventos de Research Orchestrator.

## Infra local-only

La configuración Docker por defecto no debe abrir servicios de datos en todas las
interfaces de red:

- PostgreSQL: `127.0.0.1:${POSTGRES_PORT:-5432}:5432`.
- Redis: `127.0.0.1:${REDIS_PORT:-6379}:6379`.
- Weaviate HTTP/gRPC: `127.0.0.1:${WEAVIATE_HTTP_PORT:-8081}:8080` y
  `127.0.0.1:${WEAVIATE_GRPC_PORT:-50052}:50051`.
- Neo4j HTTP/Bolt: `127.0.0.1:${NEO4J_HTTP_PORT:-7475}:7474` y
  `127.0.0.1:${NEO4J_BOLT_PORT:-7688}:7687`.

Validación recomendada: `docker compose --env-file .env.example -f infra/docker-compose.yml config --quiet`.

## Pre-commit

Este repositorio queda preparado para usar `detect-secrets` mediante pre-commit.

Instalacion local:

```bash
python -m pip install pre-commit detect-secrets
pre-commit install
pre-commit run --all-files
```

## OpenHarness (investigación, opcional)

Si activas `ENABLE_OPENHARNESS_RESEARCH` con el extra `openharness-ai`, el
backend puede ejecutar el bucle de herramientas de **OpenHarness** antes o en
lugar de DeepAgents según `OPENHARNESS_RESEARCH_PIPELINE`.

Hechos relevantes para seguridad (verificados contra
`backend/src/cognitive_os/integrations/openharness_research.py` y
`backend/src/cognitive_os/agents/graph.py::research_node`):

- Los presets **`research`** y **`full`** registran **`BashTool`**, edición y
  escritura de archivos, ejecución de notebooks, LSP y otras herramientas que
  operan dentro del `cwd` resuelto por `resolve_openharness_cwd`. El `cwd`
  está acotado, pero las acciones ocurren con los permisos del proceso del
  backend.
- En modo **`deepagent_mirror`** (default), OpenHarness y DeepAgent comparten
  el mismo workspace de la tarea; los archivos generados quedan visibles para
  el flujo posterior y para el operador.
- El permiso interno se eleva a `PermissionMode.FULL_AUTO` en `research`/`full`
  y se mantiene en `PermissionMode.PLAN` sólo en `minimal`.
- Búsqueda web dentro de OpenHarness exige **dos** flags: `WEB_SEARCH_ENABLED`
  (a nivel proyecto) y `OPENHARNESS_WEB_TOOLS` (a nivel motor). Si el operador
  los activa, el harness puede hacer HTTP GET a la red pública.
- El proceso OpenHarness usa `PRIMARY_LLM_*` igual que DeepAgent. No se pasa
  `Settings` de Cognitive OS al motor (`settings=None` al instanciar
  `QueryEngine`) para evitar fugar configuración interna.

Trátalo como capacidad de **operador consciente**: actívalo solo donde
entiendas preset, modo de workspace y límites de red.
Detalle completo: **`docs/OPENHARNESS_FUSION.md`**.

## Mail personal GoDaddy/Gmail-label

El paquete `backend/src/cognitive_os/mail/` puede leer correo y enviar respuestas
aprobadas. Reglas de operación:

- `MAIL_ENABLED=false` por defecto en entornos limpios.
- `MAIL_REQUIRE_APPROVAL_FOR_SEND=true` debe mantenerse para operación real.
- GoDaddy IMAP/SMTP usa `MAIL_GODADDY_*`; las credenciales son secretas y no se
  imprimen ni se documentan con valores reales.
- Gmail label (`MAIL_GMAIL_LABEL`, default `TODOS`) solo se lee si el OAuth
  read-only (`GMAIL_READ_ENABLED` + `GMAIL_TOKEN_DIR/token.json`) está listo.
- El sistema guarda mensajes/propuestas en Postgres (`mail_accounts`,
  `mail_messages`) y cada envío en `mail_send_logs`.
- No existe auto-send ni draft remoto. El operador edita texto, aprueba y recién
  entonces se llama SMTP.

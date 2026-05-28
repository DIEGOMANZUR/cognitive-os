# Seguridad Y Safety Operativa (referencia técnica)

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-28, Prompt 7 V2.0 — re-ejecutado).** Esta rama `codex/commercial-zero-friction-hardening` queda certificada como **APTA COMERCIAL LOCAL-FIRST** para PC dedicado. Branch inicial Prompt 1 V2.0: HEAD `935193e`. El commit final del Prompt 7 V2.0 firma los deltas P3 (F-P2-101 restore + F-P2-103 + F-P2-104 parcial + F-P2-105) y P6 (V2-EVAL-200 path policy + V2-EVAL-202 docanalysis review). Evidencia viva en `tmp/v2_07_absolute_release_closure_20260528_133000/`.
>
> **Hallazgos cerrados V2.0 (10 verificados):** F-P2-101 working tree restored · F-P2-103 (P1) drive_get_file non-ASCII → 400 (15 tests) · F-P2-104 (P2 parcial) responses={} declarado, 89 endpoints en backlog R-001 · F-P2-105 (P3) `_inspect_workers_snapshot` con `connection_or_acquire` + connection=conn (verificado live **6/6 ciclos chaos consecutivos**) · F-P2-102 (P3) demostrado FALSO POSITIVO · V2-EVAL-200 (P1) `_is_sensitive_root` bloquea `~/.ssh`, `~/.gnupg`, `credentials/`, `tokens/` (16 tests) · V2-EVAL-201 (P3) log crudo Code Director ciclo completo · V2-EVAL-202 (P3) `apply_quality_evaluation` reconcilia top-level `human_review_required` con item severity=high / needs_human_review (4 tests). V2-EVAL-001/004/005 previos del cierre V2.0 anterior siguen sosteniéndose.
>
> **Gates V2.0 medidos antes del cierre absoluto:** `bash scripts/full-qa.sh` **1269 passed, 1 skipped, 28 deselected** (ruff/format/mypy/alembic/sync_doc_counts/git-diff verdes); `bash scripts/stress-qa.sh 5` **5/5 verde × 1269 passed × 2 ciclos posteriores al último cambio**, flakiness **0%**; `cd frontend && npx playwright test` **44 passed × 2 ciclos**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/openapi_readonly_smoke.py` **70 GET / 0 failures**; `bash scripts/verify_desktop_launchers.sh` OK; bandit severity-high 0 issues; `POST /health/verify` overall **`ok`** con `mcp_client` live `ok` 6/6 y **70 tools live**; checklist 400 puntos ejecutada (P7 V2.0). **37 tests de regresión nuevos acumulados** (15 F-P2-103 + 2 F-P2-105 + 16 V2-EVAL-200 + 4 V2-EVAL-202).
>
> **Criterio de verdad:** no se declara envío de correo, draft real ni escritura DNS. Mail queda normalizado como read-only (sync/list/classify/digest + proposed replies como texto). GoDaddy preview/dry-run. Action Plane mantiene `validate→preview→request→approve→dispatch→execute→audit` con idempotencia y reapers. Computer organize/inventory bloquean `root_path` con markers sensibles (`.ssh`, `.gnupg`, `credentials`, `secret`, `tokens`, `keychain`) además de la allow-list existente. El runtime corre en `127.0.0.1` sin exposición LAN/internet. **Cognitive OS queda certificado en este commit como APTO COMERCIAL LOCAL-FIRST para PC dedicado, con funcionamiento real activado, documentación sincronizada, dos ciclos completos verdes posteriores al último cambio, Git ordenado y sin P0/P1/P2 abiertos.**

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


> **Estado canonico actual (2026-05-27, post cierre absoluto V2.0):** **COMERCIAL LOCAL-FIRST APROBADO + frontend/TestSprite web hardening**. Este documento no debe leerse como
> promesa de hardening SaaS. En el PC dedicado de Diego la decision de producto
> sigue siendo **friccion casi nula por sobre seguridad estricta**. `strict`
> queda documentado para auditorias, maquinas compartidas o un futuro despliegue
> multiusuario; el modo real recomendado para este host es
> `OPERATOR_PROFILE=dedicated_local` + `LOCAL_AUTONOMY_MODE=full`.
>
> En ese modo se acepta usar el perfil real de Edge, credenciales locales,
> Kimi WebBridge, MCP filesystem y acceso amplio al PC. La capa pública actual
> para TestSprite agrega hash auth `#cogos_token`, API pública automática y shell
> estable, pero no convierte el producto en SaaS ni relaja los controles de
> acciones externas. Los controles que importan son trazabilidad, idempotencia,
> timeouts, reapers, health/readiness, tests y diagnostico visible. La excepcion
> explicita es mail: el flujo normal **no envia mails, no crea drafts y solo
> propone texto**. Ver `CURRENT_STATE.md` y `ZERO_FRICTION_OPERATING_MODEL.md`.
>
> **Estado historico (2026-05-20, Fases 78-81 — plan de aprendizaje completo, cliente MCP, perfil dedicated_local):**
> GoDaddy habilitado pero `GODADDY_DNS_DRY_RUN_ONLY=true` +
> `GODADDY_ALLOW_PRODUCTION_WRITES=false` (cero escrituras DNS reales sin
> opt-in explícito + aprobación humana). `.env` gitignoreado/no-trackeado;
> credenciales también respaldadas en Supermemory (fuera del repo). Suite
> hermética por construcción (no hace llamadas LLM reales). **Telegram
> operativo** con bot autorizado. Reglas auditadas de punta a punta:
> Google Calendar/Drive writes reales sólo vía `ActionRequest` +
> aprobación humana. Postgres, Redis, Weaviate y Neo4j publican sólo en
> `127.0.0.1`. OAuth/Drive/health redactan rutas locales y tokens en
> errores. El frontend PWA evita cachear rutas API-like y añade headers de
> seguridad. RBAC local explícito, `payload_executable` cifrado cuando hay
> clave, `ACTION_PAYLOAD_ENCRYPTION_REQUIRED=true` +
> `RESEARCH_PERSISTENCE_BACKEND=postgres` obligatorios en producción.
> `pre-commit` (gitleaks + detect-secrets, baseline limpio, 0 findings).
> Auth dependency sobre los endpoints sensibles (sólo `/health` público).
> La suite `pytest` corre contra una DB de test aislada
> (`cognitive_os_test`); nunca lee ni escribe la base de producción.
>
> **Modelo por perfil (`OPERATOR_PROFILE`):** `strict` mantiene compuertas,
> four-eyes y allow-lists angostas. `dedicated_local/full` sacrifica seguridad
> para bajar friccion: puede auto-aprobar acciones que antes exigian OK y puede
> operar con Edge real y acceso local amplio. No describir `dedicated_local/full`
> como seguro para internet, multiusuario o multi-cliente.
>
> **Remediacion del audit (AUDIT-2026-A..H, 2026-05-22):** la unica falla de
> seguridad real del audit fue el dispatch de Telegram fail-open con allowlist
> vacia — corregida (ahora fail-closed). El resto de hallazgos accionables son
> de honestidad operativa (health `configured` vs `verified`, kill switch del
> auto-promote, visibilidad de backlog) y no de hardening de perimetro.

## Reglas obligatorias

- Jamas commitear `.env` ni archivos derivados con credenciales reales.
- Rotar claves si aparecen en logs, prompts, reportes, tickets o cualquier otro registro.
- No enviar payloads sensibles a servicios externos sin redaccion previa.
- No operar en producción sin `ACTION_PAYLOAD_ENCRYPTION_KEY` real ni
  `ACTION_PAYLOAD_ENCRYPTION_REQUIRED=true`.
- No asumir admin cuando `ADMIN_USER_IDS` está vacío: usar `AUTH_ADMIN_ROLES` o
  IDs explícitos.
- En `strict`, las acciones externas requieren aprobacion humana explicita. En
  `dedicated_local/full`, la aprobacion puede auto-resolverse para reducir
  friccion; la proteccion pasa a logs, audit, idempotencia y reapers.
- Browser, computador local, Gmail, mail personal y GoDaddy arrancan desactivados
  o en modo preview-first/read-only. No promover a escritura real sin flags,
  allow-lists, auditoria, aprobaciones y pruebas.
- En `strict`, no usar perfiles reales del navegador del usuario para
  automatizacion. En este host `dedicated_local`, **si se permite** Edge real via
  Kimi WebBridge porque es parte del objetivo de friccion casi nula.
- No mover archivos locales fuera de `COMPUTER_ALLOWED_ROOTS`.
- No despachar una `ActionRequest` si no esta en `queued` despues de aprobacion.
- No ocultar fallos del broker Celery: registrar
  `action_request_dispatch_failed` y dejar la solicitud `queued` para retry.
- No hacer `apply_async` sin reserva previa de dispatch; la metadata
  `dispatch_state` debe impedir submits duplicados.
- No enviar emails desde el flujo normal. Mail solo propone texto. El envio real
  requiere peticion explicita de Diego y los flags de escape hatch. DNS real
  debe conservar flags de dry-run/production-writes y allow-list; si se aflojan,
  documentarlo como decision consciente de operador.
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
- El dispatch del bot de Telegram es **fail-closed**: una allowlist
  `TELEGRAM_AUTHORIZED_USER_IDS` vacía rechaza a todos (no acepta a nadie) y
  `main()` se niega a arrancar el bot en ese estado. No revertir a la guardia
  `if self.allowed_user_ids and ...` (un set vacío evaluaba a `False` y
  saltaba el rechazo).

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

Validación recomendada: `bash scripts/dev_up.sh` valida — antes de invocar
`docker compose` — que las variables que el compose interpola **sin default**
(`POSTGRES_USER/PASSWORD/DB`, `WEAVIATE_API_KEY`, `NEO4J_USER/PASSWORD`) no
estén vacías ni en `CHANGEME`; `docker compose` por sí solo las trataría como
string vacío sin fallar (AUDIT-2026-H). Para una verificación pura del compose:
`docker compose --env-file .env -f infra/docker-compose.yml config --quiet`.

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

## Cliente MCP (Fase 73)

El DeepAgent puede cargar tools de servidores MCP externos
(`ENABLE_MCP_CLIENT=true` + `MCP_SERVERS`). Reglas de seguridad:

- El cliente MCP es **opt-in** y sólo se activa bajo
  `OPERATOR_PROFILE=dedicated_local` — las tools MCP usan credenciales
  personales del operador (tokens en los headers de `MCP_SERVERS`), que no
  deben filtrarse a deployments multi-tenant.
- Cada servidor MCP se conecta **aislado**: un server caído o malicioso se
  skipea con warning, no compromete a los demás.
- `time` es la excepcion de bajo riesgo dentro del set actual: corre local por
  `stdio` desde `backend/src/cognitive_os/integrations/time_mcp_server.py`,
  no requiere auth, no usa secretos, no accede a red externa y no escribe
  datos. Solo calcula hora actual y conversiones de zona horaria.
- Las tools MCP de **write** tienen efectos reales (p.ej. crear un issue
  en GitHub, escribir un archivo). El operador es responsable de qué
  servidores declara — el sistema no puede auditar qué hace una tool
  remota arbitraria. Declarar sólo servidores de confianza.
- Los headers de auth (`header_Authorization=Bearer ...`) viven en `.env`
  gitignoreado. Nunca documentar valores reales.
- `MCP_ALLOWED_FOR_RESEARCH` / `MCP_ALLOWED_FOR_DOCUMENT_ANALYSIS`
  permiten restringir qué servers ve qué subgrafo — usar para mantener
  servidores sensibles fuera de la ruta legal.

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

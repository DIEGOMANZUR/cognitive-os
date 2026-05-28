# Action Plane

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-27, Prompt 7).** Esta rama `codex/commercial-zero-friction-hardening` queda certificada como **APTA COMERCIAL LOCAL-FIRST** para PC dedicado. Branch inicial Prompt 1: HEAD `2bb4966`. Working tree del Prompt 7 consolida los cambios de Prompts 3 (F-P2-001..006), 4 (F-P4-001 fix wrapper timeout mcp_client live probe) y 6 (V2-EVAL-001 DocAnalysis API consistency). El commit final del Prompt 7 firma todo el delta V2.0 sin push. Evidencia viva en `tmp/v2_07_absolute_release_closure_20260527_175541/`.
>
> **Hallazgos cerrados V2.0 (12):** F-P2-001 wildcard_allow_all transparency · F-P2-002 stress flake eliminado (0% en 5×1232) · F-P2-003 `?limit=` honored en `/approvals` y `/actions/drive/files` · F-P2-004 `/chat` 404/400 con `missing_doc_ids`/`invalid_doc_ids` · F-P2-005 docs sync (este bloque) · F-P2-006 `_check_mcp(verify_live=True)` → overall `ok` · F-P4-001 timeout wrapper +5s sobre `mcp_inventory_timeout_seconds` · F-P4-002 fallback heurístico DocAnalysis documentado · F-P4-003 Kimi extension boot oscillation documentado · V2-EVAL-001 `GET /document-analysis/{id}` mirror artefacto · V2-EVAL-004 endpoints memoria/aprendizaje live (303 proposals, 209 recipes, 94 warnings) · V2-EVAL-005 Code Director adapter=deepagent plan+approval+reject sin exec.
>
> **Gates V2.0 medidos antes del cierre absoluto:** `bash scripts/full-qa.sh` **1232 passed, 1 skipped, 28 deselected** (ruff/format/mypy/alembic/sync_doc_counts/git-diff verdes); `bash scripts/stress-qa.sh 5` **5/5 verde × 1232 passed**, flakiness **0%**; `cd frontend && npx playwright test` **44 passed**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/openapi_readonly_smoke.py` **70 GET / 0 failures**; `bash scripts/verify_desktop_launchers.sh` OK; security-readonly-qa (bandit/semgrep/secret-scan) clean; `POST /health/verify` overall **`ok`** con `mcp_client` live `ok` 6/6 y 69 tools; checklist 400 puntos ejecutada.
>
> **Criterio de verdad:** no se declara envío de correo, draft real ni escritura DNS. Mail queda normalizado como read-only (sync/list/classify/digest + proposed replies como texto). GoDaddy preview/dry-run. Action Plane mantiene `validate→preview→request→approve→dispatch→execute→audit` con idempotencia y reapers. El runtime corre en `127.0.0.1` sin exposición LAN/internet. El frontend `cognitive.doctormanzur.com` se levanta on-demand sólo con `scripts/testsprite_web/deploy_and_verify.sh`; Prompt 7 V2.0 no lo expone permanentemente. **Cognitive OS queda certificado en este commit como APTO COMERCIAL LOCAL-FIRST para PC dedicado, con funcionamiento real activado, documentación sincronizada, dos ciclos completos verdes posteriores al último cambio, Git ordenado y sin P0/P1/P2 abiertos.**

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


> **Estado canonico actual (2026-05-27, post cierre absoluto V2.0):**
> **COMERCIAL LOCAL-FIRST APROBADO**. En el PC dedicado el Action Plane se
> interpreta bajo `dedicated_local/full`: friccion casi nula primero, seguridad
> estricta despues. En `strict`, preview/request/approval sigue siendo la postura
> conservadora. En `dedicated_local/full`, las approvals reversibles auto-resuelven
> y la defensa pasa a audit, idempotencia, reapers y observabilidad. Mail se
> mantiene fuera del auto-send: solo lectura, digest y propuestas de texto. La
> capa frontend pública vigente usa `#cogos_token`, API pública por host y estados
> comerciales sin datos falsos; ver `CURRENT_STATE.md`, `USER_GUIDE.md` y
> `ZERO_FRICTION_OPERATING_MODEL.md`.
>
> **Fix `647f103` que afecta directamente el Action Plane:**
> `eager_defaults=True` en `db.Base` corrige el bug P1
> `MissingGreenlet` en todos los `POST /actions/*/preview/request` y
> `POST /actions/*/request`. Endpoints verificados HTTP 200 vivo con
> `updated_at` populado e idempotencia preservada (misma url → mismo
> id). 3 tests de regresión en
> `backend/tests/test_action_request_eager_defaults.py`.
>
> **Estado historico (2026-05-21, Fase 85 — contrato mail read-only):** capa **preview-first con
> `ActionRequest` persistente** y carril activo de **mail personal read-only por defecto**.
> GoDaddy DNS verificado en vivo (auth producción HTTP 200) y habilitado en
> postura segura: `GODADDY_DNS_DRY_RUN_ONLY=true` +
> `GODADDY_ALLOW_PRODUCTION_WRITES=false` → solo preview/dry-run con
> aprobación humana; ninguna escritura DNS real sin opt-in explícito del
> operador. Bug de alias `ENABLE_GODADDY`→`GODADDY_ENABLED` corregido
> (el primero era no-op). Estado previo (Fase 65 paridad UI/Telegram + bugfix CHECK):
> **Fase 65 corrigió un bug crítico:** el CHECK `ck_ar_action_type` no
> incluía `drive_ensure_folder` ni `drive_organize_files`, así que esos
> dos `/request` daban `CheckViolation` (500) contra Postgres real
> aunque los tests pasaran (mocan `session_scope`). Migración
> `202605170001` amplía el constraint; un test de regresión
> (`tests/test_action_request_check_constraint.py`) mantiene ORM,
> última migración y `WORKFLOW_EXPORTABLE_TYPES` alineados para que no
> vuelva a pasar.
> Hay ejecución real para `computer_organize`, `document_generate`,
> `browser_preview`, `browser_interactive`, GoDaddy DNS (solo con dry-run
> desactivado y dominio allow-listed), Google Calendar create,
> Google Drive upload/folder/organize vía `/request`. Mail queda separado por
> política de operador: el flujo normal lee Gmail `TODOS`/`SPAM` y GoDaddy
> `Spam`, clasifica con el agente, genera digest 10:00/20:00 Chile y propone
> respuestas como texto; **no crea drafts ni envía SMTP**. El endpoint
> `/mail/messages/{id}/approve-send` solo funciona si se habilita
> `MAIL_ALLOW_EXPLICIT_SEND=true`, `ENABLE_EMAIL_SEND=true` y la llamada trae
> la frase de confirmación explícita.
> Google Maps es read-only con rutas de tráfico y link navegable. Las migraciones
> Alembic relevantes ya activas: `action_requests` (v1 + browser_preview +
> browser_interactive + document_generate + `payload_executable` separado),
> `mail_*` (cuentas/mensajes/send_logs), `personal_tasks/notes` y nuevos action
> types Google (`calendar_create_event`, `drive_upload_file`,
> `drive_ensure_folder`, `drive_organize_files`). Fase 33 añade
> cifrado at-rest configurable de `payload_executable` y admin/RBAC explícito.
> Fase 38/39 agregan: idempotency aplicativa + DB (índice parcial UNIQUE),
> four-eyes en approvals (`APPROVAL_REQUIRE_FOUR_EYES=true`), reaper de
> approvals stale (`APPROVAL_PENDING_MAX_HOURS=48`), AuditEvent simétrico
> entre REST y Telegram, `workflow.v1` export/import (ver sección abajo),
> rate limiter por usuario (memory/Redis) y correlation IDs propagados.

El action plane es la capa que prepara a Cognitive OS para actuar en el computador,
en navegador y en servicios externos sin saltarse trazabilidad, auditoria,
idempotencia ni el perfil operativo elegido.

Hechos verificables (1:1 con `backend/src/cognitive_os/actions/` y `api/app.py`):

- `computer_organize`: previewable por `POST /actions/computer/organize/preview`,
  ejecutable por `POST /actions/computer/organize/request` + `dispatch`. Solo
  corre con `ENABLE_COMPUTER_ACTIONS=true`, ruta dentro de
  `COMPUTER_ALLOWED_ROOTS` y `COMPUTER_ORGANIZE_DRY_RUN_ONLY=false`.
- `browser_preview` / `browser_interactive`: headless Chromium, dominios en
  allow-list, screenshots en `BROWSER_SCREENSHOT_DIR`. `interactive` añade
  pasos `navigate/click/fill/scroll/wait/screenshot/analyze`; `analyze` usa
  `VisionAnalyzer` (default `ChatVisionAnalyzer.from_settings`).
- `document_generate`: DOCX/XLSX/PPTX con guardrails (paths, tamaño, assets
  allow-listed, fórmulas XLSX no inyectables) y `pending_approval` por defecto.
- Gmail: `digest/preview` redacta direcciones y propone texto; **nunca** crea
  drafts en el mailbox del usuario.
- Google Maps: `geocode` y `route` son read-only; `route` incluye tráfico,
  duración estática, retraso y link Google Maps sin exponer API keys.
- Google Calendar: `events/create` es preview-only; si llega `dry_run=false`
  responde `409`. `freebusy` es read-only. El carril comercial usa
  `events/request` -> `ActionRequest` -> aprobación -> Celery.
- Google Drive: `folders/ensure` gestiona la carpeta de entregables;
  `files/upload/request` sube archivos permitidos por raices de entregables o
  `COMPUTER_ALLOWED_ROOTS` y cap de tamaño; `organize/request` mueve archivos
  a carpeta destino sin borrar nada. Los endpoints directos rechazan writes.
- Mail personal: `cognitive_os.mail` lee GoDaddy IMAP y Gmail REST en modo
  read-only, persiste mensajes, clasifica sin confiar en carpetas del proveedor,
  genera un digest y propone respuestas como texto. No envía en el flujo normal.
- GoDaddy: `dns/preview` y `dns/request` aplican rate limit local; ejecución
  real solo si `GODADDY_DNS_DRY_RUN_ONLY=false` + dominio allow-listed +
  aprobación; producción exige `GODADDY_ALLOW_PRODUCTION_WRITES=true`.
- Kimi WebBridge: opera el navegador real del usuario mediante daemon local.
  Navegación exige `KIMI_WEBBRIDGE_ALLOWED_DOMAINS` y hereda
  `ENABLE_BROWSER_SSRF_CHECK`; mutaciones directas (`click/fill/evaluate/close`)
  se rechazan mientras `KIMI_WEBBRIDGE_REQUIRE_APPROVAL=true`. En producción no
  se permite activar mutaciones con esa aprobación deshabilitada.

## Principio central

Toda accion se modela en un ciclo controlado:

1. **Validate**: la solicitud pasa por allow-lists y flags de entorno.
2. **Preview**: el sistema devuelve que haria, que endpoint/ruta usaria y si
   requiere aprobacion.
3. **Request**: si la accion puede ejecutar, se guarda como `ActionRequest`
   con payload redactado, preview, estado, idempotency key y metadata.
4. **Approve**: acciones reales requieren `HumanApproval`.
5. **Dispatch**: una aprobacion aceptada se encola como job Celery.
6. **Execute/Audit**: el worker toma el `ActionRequest` con transicion atomica
   a `running`, ejecuta el executor permitido, guarda resultado o error, y
   registra `AuditEvent`. Si llega un worker duplicado y la fila ya esta
   `running`, sale sin marcar el job como fallido.

El dispatch deja `JobEvent` explícito: `action_request_dispatch_submitted` cuando
Celery acepta el job, o `action_request_dispatch_failed` si el broker falla antes
de aceptarlo. En ese último caso la respuesta indica `dispatched=false` y la
solicitud queda `queued` para reintentar cuando el broker esté sano.

Antes de llamar a Celery, el API y Telegram reservan el dispatch bajo lock de la
`ActionRequest`. La metadata usa `dispatch_state=submitting|submitted|failed`:
`submitting` bloquea una llamada concurrente, `submitted` evita re-enviar el
mismo trabajo mientras el worker procesa, y `failed` permite retry.

## Endpoints

Todos requieren JWT.

| Endpoint | Proposito | Ejecuta accion real |
|---|---|---|
| `GET /actions/capabilities` | Estado de browser, computer, Gmail, GoDaddy, Maps, Google Calendar y Google Drive | No |
| `POST /actions/browser/validate` | Valida URL, modo headed/vision y perfil | No |
| `POST /actions/browser/request` | Crea `ActionRequest` persistente para navegacion (preview-only) | No |
| `POST /actions/computer/organize/preview` | Propone movimientos para ordenar carpetas | No |
| `POST /actions/computer/organize/request` | Crea `ActionRequest` persistente para ordenar carpetas | No directamente |
| `POST /actions/computer/inventory` | Crea inventario read-only de archivos dentro de allow-list | No |
| `GET /actions/requests` | Lista solicitudes de accion recientes (filtros `action_type`, `status`) | No |
| `GET /actions/requests/{id}` | Obtiene una solicitud de accion | No |
| `POST /actions/requests/{id}/dispatch` | Encola una solicitud ya aprobada | Si queda en `queued` |
| `POST /actions/requests/{id}/cancel` | Cancela una solicitud no-corriente/no-final | No |
| `GET /actions/gmail/status` | Estado de Gmail/OAuth/scopes | No |
| `POST /actions/gmail/query/preview` | Valida una busqueda Gmail | No |
| `POST /actions/gmail/query/request` | Crea `ActionRequest` persistente para query Gmail (preview-only) | No |
| `POST /actions/gmail/digest/preview` | Resumen diario read-only con respuestas propuestas como texto (no crea drafts en Gmail) | No |
| `GET /actions/maps/status` | Estado Maps/Routes/Geocoding | No |
| `POST /actions/maps/geocode` | Geocodifica una dirección | No |
| `POST /actions/maps/route` | Calcula ruta con tráfico/link Google Maps | No |
| `GET /actions/calendar/status` | Estado Calendar/OAuth/write flag | No |
| `POST /actions/calendar/events` | Lista eventos por rango | No |
| `POST /actions/calendar/freebusy` | Lista bloques ocupados por calendario/rango | No |
| `POST /actions/calendar/events/create` | Preview directo; rechaza `dry_run=false` con `409` | No |
| `POST /actions/calendar/events/request` | Crea `ActionRequest` aprobable para evento Calendar | No directamente |
| `GET /actions/drive/status` | Estado Drive/OAuth/upload cap/carpeta | No |
| `POST /actions/drive/files` | Busca archivos Drive | No |
| `GET /actions/drive/files/{file_id}` | Lee metadata de archivo Drive | No |
| `POST /actions/drive/folders/ensure` | Preview de carpeta de entregables; rechaza `dry_run=false` con `409` | No |
| `POST /actions/drive/folders/ensure/request` | Crea `ActionRequest` aprobable para crear/asegurar carpeta de entregables | No directamente |
| `POST /actions/drive/organize/preview` | Previsualiza archivos Drive que se moverian a una carpeta destino | No |
| `POST /actions/drive/organize/request` | Crea `ActionRequest` aprobable para mover archivos Drive a una carpeta | No directamente |
| `POST /actions/drive/files/upload` | Preview/upload directo; rechaza `dry_run=false` con `409` | No |
| `POST /actions/drive/files/upload/request` | Crea `ActionRequest` aprobable para upload Drive | No directamente |
| `GET /mail/status` | Estado del carril mail personal y cuentas configuradas | No |
| `POST /mail/sync` | Endpoint directo legacy para sync IMAP/Gmail; evitar desde UI porque puede bloquear el API | No |
| `POST /mail/sync/dispatch` | Encola sync de mail en Celery queue `mail`; es el camino de la UI | No |
| `POST /mail/digest/preview` | Genera resumen de mensajes locales y respuestas propuestas separadas, sin drafts/sends; la UI usa `sync_first=false` | No |
| `POST /mail/digest/dispatch` | Encola digest persistente en Celery queue `mail` | No |
| `GET /mail/messages` | Lista mensajes persistidos y propuestas | No |
| `PATCH /mail/messages/{id}/reply` | Edita la propuesta escrita | No |
| `POST /mail/messages/{id}/ignore` | Marca mensaje como ignorado | No |
| `POST /mail/messages/{id}/approve-send` | Escape hatch SMTP; requiere flags de envío y `explicit_send_confirmation` | Sí, solo si Diego lo pide explícitamente |
| `GET /actions/godaddy/status` | Estado de GoDaddy/API/MCP publico | No |
| `POST /actions/godaddy/dns/preview` | Previsualiza cambio DNS | No |
| `POST /actions/godaddy/dns/request` | Crea `ActionRequest` persistente para cambio DNS (preview-only) | No |
| `GET /actions/documents/status` | Estado del generador de documentos (DOCX/XLSX/PPTX) | No |
| `POST /actions/documents/preview` | Previsualiza ruta de salida, formato y bloques estimados | No |
| `POST /actions/documents/request` | Crea `ActionRequest` persistente para generar un documento | No directamente |
| `POST /actions/browser/preview/request` | Crea `ActionRequest` persistente para `browser_preview` headless (titulo + screenshot, sin login) | No directamente |
| `POST /actions/browser/interactive/request` | Plan interactivo (click/fill/scroll/screenshot/analyze) con vision LLM opcional | No directamente |
| `GET /actions/webbridge/status` | Estado de Kimi WebBridge local | No |
| `POST /actions/webbridge/navigate` | Navega el navegador real a dominio allow-listed y con SSRF check | No, pero cambia estado del navegador |
| `POST /actions/webbridge/snapshot` / `screenshot` / `list_tabs` | Lee estado visual/tabs del navegador real | No |
| `POST /actions/webbridge/click` / `fill` / `evaluate` / `close_session` | Mutaciones directas en navegador real; bloqueadas por defecto si requieren aprobación | Sí solo si `KIMI_WEBBRIDGE_ALLOW_MUTATIONS=true` y `KIMI_WEBBRIDGE_REQUIRE_APPROVAL=false` |
| `GET /actions/requests/{id}/workflow` | Exporta una `ActionRequest` como `workflow.v1` JSON (payload redactado + preview + procedencia) | No |
| `POST /actions/requests/from-workflow` | Crea una nueva `ActionRequest` a partir de un `workflow.v1` JSON | Sí (a través del carril normal con aprobación) |

## Workflow.v1 (export / import)

Cada `ActionRequest` cuyo `action_type` está entre las siguientes 9 puede
serializarse a un documento JSON portátil y volver a someterse:

- `computer_organize`
- `godaddy_dns_change`
- `document_generate`
- `browser_preview`
- `browser_interactive`
- `calendar_create_event`
- `drive_upload_file`
- `drive_ensure_folder`
- `drive_organize_files`

El import siempre pasa por el mismo `create_*_request` que el endpoint
estándar, así que **todos los guardrails se aplican intactos**: allow-lists,
SSRF check, idempotency dedup, aprobación humana, cifrado at-rest del payload
ejecutable y rate limiting per-`(user, bucket)`. Lo único que viaja en el JSON
es el payload **redactado**; los valores con forma de secreto quedan como
`[REDACTED]` y deben re-suministrarse al re-someter el plan si la acción los
requería realmente.

Ejemplo de documento exportado por `GET /actions/requests/{id}/workflow`:

```json
{
  "workflow_version": "1.0",
  "action_type": "browser_preview",
  "payload": {
    "url": "https://example.com/landing",
    "wait_until": "load",
    "capture_screenshot": true
  },
  "preview": {
    "status": "ok",
    "url": "https://example.com/landing",
    "wait_until": "load",
    "capture_screenshot": true,
    "timeout_ms": 20000
  },
  "source": {
    "exported_at": "2026-05-17T01:23:45+00:00",
    "exported_by": "1",
    "source_action_request_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
  },
  "notes": null,
  "metadata": {}
}
```

Para re-someter el mismo plan (idéntico o editado):

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     --data @workflow-aaaa.json \
     http://127.0.0.1:8000/actions/requests/from-workflow
```

La respuesta es `WorkflowImportResult` con la nueva `ActionRequest` ya creada,
en estado `pending_approval` o `blocked` según la política vigente. Si el
operador re-somete un payload idéntico mientras la `ActionRequest` original
sigue activa, el helper `_find_active_idempotent_request` retorna la fila
existente sin duplicar.

`workflow_version` está versionado: cambios aditivos suben el minor, cambios
breaking suben el major. El importador rechaza versiones distintas a `1.0`
con `422 Unprocessable Entity` (Pydantic Literal).

En el panel: la pestaña **Aprobaciones** trae `Importar workflow` (file
picker) en la cabecera y un botón `Exportar` por fila ligada a una
`ActionRequest`.

## Estados de `ActionRequest`

| Estado | Significado |
|---|---|
| `previewed` | Solo hay preview; no puede ejecutar con la configuracion actual |
| `blocked` | La politica rechazo la solicitud |
| `pending_approval` | Lista para aprobacion humana |
| `queued` | Aprobada y encolada para Celery |
| `running` | Worker ejecutando |
| `completed` | Ejecucion terminada correctamente |
| `failed` | Ejecucion fallo o el executor devolvio fallo |
| `rejected` | Aprobacion humana rechazada |
| `cancelled` | Cancelada antes de ejecutar |

## Browser: Playwright y Camoufox

Variables:

- `ENABLE_BROWSER_AUTOMATION=false`
- `BROWSER_AUTOMATION_PROVIDER=playwright`
- `BROWSER_ALLOWED_DOMAINS=`
- `BROWSER_HEADLESS_DEFAULT=true`
- `BROWSER_ALLOW_HEADED=false`
- `BROWSER_ALLOW_VISION=false`
- `BROWSER_PROFILE_DIR=./storage/browser/profiles`
- `BROWSER_DOWNLOAD_DIR=./storage/browser/downloads`

Diseno:

- Headless por defecto.
- Headed solo con `BROWSER_ALLOW_HEADED=true`.
- Vision solo con `BROWSER_ALLOW_VISION=true`.
- Dominios siempre en allow-list.
- Perfiles persistentes separados por tarea/sesion; nunca usar el perfil real
  del usuario.
- TTL de sesiones y limite de paginas por tarea.
- Capturas, trazas y descargas van a storage controlado.

Fuentes oficiales revisadas:

- Playwright persistent contexts: https://playwright.dev/python/docs/api/class-browsertype
- Playwright isolation: https://playwright.dev/python/docs/browser-contexts
- Camoufox Python: https://camoufox.com/python/

## Computer / ordenar carpetas

Variables:

- `ENABLE_COMPUTER_ACTIONS=false`
- `COMPUTER_ALLOWED_ROOTS=`
- `COMPUTER_ORGANIZE_DRY_RUN_ONLY=true`
- `COMPUTER_MAX_FILES_PER_PLAN=500`

Diseno:

- Apagado por defecto.
- Sin raices permitidas no puede actuar.
- La primera capacidad es `organize/preview`: clasifica archivos por tipo y
  propone movimientos.
- Ignora symlinks.
- No toca archivos ocultos salvo `include_hidden=true`.
- La ejecucion real existe solo para `computer_organize` y requiere:
  `ENABLE_COMPUTER_ACTIONS=true`, raiz permitida, `COMPUTER_ORGANIZE_DRY_RUN_ONLY=false`,
  aprobación y despacho por `/actions/requests/{id}/dispatch`.
- **Fase 73b — auto-approve bajo `dedicated_local`:** `computer_organize`
  está en el whitelist `AUTO_APPROVE_REVERSIBLE_ACTIONS`. Cuando
  `OPERATOR_PROFILE=dedicated_local` (y el flag no fue puesto en `false`
  manualmente), el plan de organización se auto-aprueba y se despacha sin
  pedir click — mover/renombrar un archivo no es irreversible (sigue en
  el disco). El preview completo igual queda persistido en el
  `ActionRequest` para auditar después. En `strict` sigue pidiendo
  aprobación humana.
- En la PC dedicada del operador, `COMPUTER_ALLOWED_ROOTS` cubre todo
  `/home/jgonz` (más `/tmp`, `/mnt`); el agente puede ordenar el
  filesystem completo del usuario, no sólo una carpeta.
- La ejecucion vuelve a validar el plan antes de mover archivos; no confia en
  previews viejos.
- `computer_inventory` crea un mapa read-only de metadata dentro de
  `COMPUTER_ALLOWED_ROOTS`: path relativo, categoria, extension, tamano,
  `modified_at` y sha256 opcional. Guarda JSON en
  `LOCAL_STORAGE_DIR/file_inventory`.
- El inventario no lee contenido, no sigue symlinks, omite hidden files por
  defecto y salta rutas sensibles como `.env`, `.ssh`, `.git`, `secret`,
  `token`, `password` y `credentials`.

## Gmail

Variables:

- `GMAIL_READ_ENABLED=false`
- `GMAIL_SEND_ENABLED=false`
- `GMAIL_CLIENT_ID=CHANGEME`
- `GMAIL_CLIENT_SECRET=CHANGEME`
- `GMAIL_TOKEN_DIR=./storage/oauth/gmail`
- `GMAIL_SCOPES=https://www.googleapis.com/auth/gmail.readonly`

Diseno:

- Lectura separada de envio.
- Scope read-only por defecto.
- Envio requiere flag propio, aprobacion humana y auditoria.
- Tokens OAuth en directorio controlado, nunca en repo.
- Las busquedas se previsualizan antes de llamar al API.
- El digest diario puede leer Gmail real en modo read-only cuando existe
  `GMAIL_TOKEN_DIR/token.json`. Usa Gmail REST + `google-auth`, refresca token
  si puede y nunca envia correos.
- El conector Gmail MCP de Codex queda como opcion operativa externa. Para el
  backend del producto, la ruta robusta es `token.json` propio bajo
  `GMAIL_TOKEN_DIR`; si la autorizacion del navegador se cuelga, no bloquea el
  producto.

Fuente oficial revisada:

- Gmail API Python quickstart/OAuth: https://developers.google.com/workspace/gmail/api/quickstart/python

## Mail personal GoDaddy/Gmail-label

Variables:

- `MAIL_ENABLED=false`
- `MAIL_DEFAULT_SENDER=diego@doctormanzur.com`
- `MAIL_REQUIRE_APPROVAL_FOR_SEND=true`
- `MAIL_ALLOW_EXPLICIT_SEND=false`
- `MAIL_BACKGROUND_SYNC_ENABLED=false`
- `MAIL_POLL_INTERVAL_SECONDS=120`
- `MAIL_IMAP_TIMEOUT_SECONDS=30`
- `MAIL_SMTP_TIMEOUT_SECONDS=30`
- `MAIL_FETCH_MAX_PER_FOLDER=50`
- `MAIL_GMAIL_LABEL=TODOS`
- `MAIL_GMAIL_MONITOR_LABELS=TODOS,SPAM`
- `MAIL_DIGEST_ENABLED=true`
- `MAIL_DIGEST_HOURS_LOCAL=10,20`
- `MAIL_DIGEST_TIMEZONE=America/Santiago`
- `MAIL_DIGEST_MAX_MESSAGES=50`
- `MAIL_DIGEST_OUTPUT_DIR=mail_digests`
- `MAIL_GODADDY_ENABLED=false`
- `MAIL_GODADDY_IMAP_HOST=imap.secureserver.net`
- `MAIL_GODADDY_IMAP_PORT=993`
- `MAIL_GODADDY_SMTP_HOST=smtpout.secureserver.net`
- `MAIL_GODADDY_SMTP_PORT=465`
- `MAIL_GODADDY_USERNAME=diego@doctormanzur.com`
- `MAIL_GODADDY_PASSWORD=CHANGEME`
- `MAIL_GODADDY_MONITOR_FOLDERS=Spam`

Diseño:

- Fuentes por defecto: Gmail `TODOS` + `SPAM` para
  `diegomanzurn@gmail.com`; GoDaddy `Spam` para `diego@doctormanzur.com`.
- El agente no confía en la carpeta ni en la clasificación del proveedor:
  solo excluye lo que su propio clasificador marca como `spam`.
- El digest programado corre dos veces al día, 10:00 y 20:00
  `America/Santiago`, toma los últimos 50 mensajes persistidos tras sync y
  produce dos campos: resumen general y respuestas propuestas para importantes.
- El sistema genera propuestas de respuesta **como texto**; no crea drafts en el
  buzón y no escribe en Gmail/GoDaddy durante el flujo normal.
- El envío SMTP GoDaddy queda como escape hatch: exige `ENABLE_EMAIL_SEND=true`,
  `MAIL_ALLOW_EXPLICIT_SEND=true` y `explicit_send_confirmation` con el valor
  `SEND_THIS_EMAIL_EXPLICITLY`. No hay envío automático por beat, UI ni digest.
- Los mensajes se guardan en `mail_messages`; los envíos en `mail_send_logs`.

## Google Maps / Calendar / Drive

Variables:

- `GOOGLE_MAPS_API_KEY=CHANGEME`
- `ENABLE_MAPS_ROUTING=false`
- `GOOGLE_CLIENT_ID=CHANGEME`
- `GOOGLE_CLIENT_SECRET=CHANGEME`
- `GOOGLE_TOKEN_DIR=./storage/oauth/google`
- `ENABLE_GOOGLE_CALENDAR=false`
- `ENABLE_GOOGLE_CALENDAR_WRITE=false`
- `ENABLE_GOOGLE_DRIVE=false`
- `ENABLE_GOOGLE_DRIVE_WRITE=false`
- `GOOGLE_DRIVE_UPLOAD_MAX_BYTES=52428800`
- `GOOGLE_DRIVE_DELIVERABLES_FOLDER_NAME=Cognitive OS Deliverables`

Diseño:

- Maps es read-only: no requiere aprobación porque no modifica servicios externos.
- `RoutePlan` devuelve duración con tráfico, duración base, retraso estimado y
  `google_maps_url` para abrir la ruta manualmente. Desde Fase 44 tambien
  devuelve `traffic_severity`, ETA, labels de ruta, conteo de alternativas y
  `route_advice` legible para el agente/operador.
- Calendar list es read-only. Crear eventos reales exige
  `ENABLE_GOOGLE_CALENDAR_WRITE=true` y una `ActionRequest` aprobada
  (`calendar_create_event`). El endpoint directo `events/create` no ejecuta
  writes reales. `freebusy` lee disponibilidad por rango y calendario sin
  modificar Google.
- Drive list/get es read-only. La busqueda soporta `name`, `full_text` y `all`
  (`name OR fullText`) sobre `Mi unidad` o `allDrives`, siempre con
  `trashed = false` y filtros seguros de carpetas/mime.
- Upload real exige `ENABLE_GOOGLE_DRIVE_WRITE=true`, tamaño bajo
  `GOOGLE_DRIVE_UPLOAD_MAX_BYTES`, aprobación vía `/request` y path dentro de
  `DOCUMENT_OUTPUT_ROOT`, `LOCAL_STORAGE_DIR/workspaces`,
  `OPENSHELL_ALLOWED_OUTPUT_DIR` o `COMPUTER_ALLOWED_ROOTS`. No se permite el
  root completo de `LOCAL_STORAGE_DIR`, así `storage/oauth` queda fuera.
- Organización real de Drive usa `drive_organize_files`: preview lista hasta 50
  candidatos (`name`/`fullText`/`all`, `Mi unidad` o `allDrives`) y la ejecución
  aprobada usa `files.update` con `addParents/removeParents` para mover archivos
  a una carpeta destino. No borra, no mueve carpetas, no cambia permisos.
- Drive usa por defecto la carpeta `GOOGLE_DRIVE_DELIVERABLES_FOLDER_NAME` para
  entregables del sistema. `folders/ensure` previsualiza esa carpeta;
  `folders/ensure/request` crea la `ActionRequest` aprobable
  `drive_ensure_folder`, y los uploads aprobados siguen asegurando la carpeta
  durante la ejecución.
- `/config/public` solo expone flags no sensibles de Google; nunca paths de token,
  client secrets ni API keys.
- En producción, `ENABLE_GOOGLE_CALENDAR_WRITE=true` o
  `ENABLE_GOOGLE_DRIVE_WRITE=true` requiere
  `REQUIRE_HUMAN_APPROVAL_FOR_EXTERNAL_ACTIONS=true`.

## GoDaddy

Variables:

- `GODADDY_ENABLED=false`
- `GODADDY_BASE_URL=https://api.godaddy.com`
- `GODADDY_API_KEY=CHANGEME`
- `GODADDY_API_SECRET=CHANGEME`
- `GODADDY_ALLOWED_DOMAINS=example.com`
- `GODADDY_DNS_DRY_RUN_ONLY=true`
- `GODADDY_ALLOW_PRODUCTION_WRITES=false`
- `GODADDY_MAX_REQUESTS_PER_MINUTE=60`

Diseno:

- OTE primero para pruebas (`https://api.ote-godaddy.com`).
- Dry-run por defecto. Con dry-run activo, el cambio queda solo en preview.
- Para ejecutar DNS real se requiere `GODADDY_DNS_DRY_RUN_ONLY=false`, dominio
  incluido en `GODADDY_ALLOWED_DOMAINS`, aprobacion humana via `ActionRequest`
  y, si la base URL es produccion, `GODADDY_ALLOW_PRODUCTION_WRITES=true`.
- Cambios DNS se devuelven como preview con endpoint, payload y metodo. El
  executor real aplica `PATCH /v1/domains/{domain}/records` solo despues de
  aprobacion.
- Fase futura: comparar estado actual vs propuesto antes de pedir confirmacion.
- Rate limit local antes de llamar.
- El MCP publico oficial de GoDaddy existe, pero es solo lectura y no modifica DNS.

Fuentes oficiales revisadas:

- Domains API: https://developer.godaddy.com/doc/endpoint/domains
- GoDaddy MCP: https://developer.godaddy.com/mcp

## Camino a ejecucion real

Ya implementado:

1. Persistir `ActionRequest` en Postgres con payload redactado.
2. Crear `HumanApproval` para `computer_organize` ejecutable.
3. Encolar ejecucion aprobada en worker Celery.
4. Registrar `AuditEvent` al crear y al ejecutar.
5. Guardar resultado o error en la solicitud.
6. Crear/ejecutar `ActionRequest` para `calendar_create_event`,
   `drive_upload_file`, `drive_ensure_folder` y `drive_organize_files` bajo
   doble compuerta.
7. Cifrar `payload_executable` con Fernet cuando `ACTION_PAYLOAD_ENCRYPTION_KEY`
   está configurado; producción exige cifrado requerido.

Pendiente para capacidades futuras:

1. Gmail send/drafts reales si el operador decide ampliar scopes.
2. Rate limits por proveedor para Calendar/Drive/Gmail send.
3. Diff/rollback cuando el proveedor lo soporte.
4. UI completa para todos los `ActionRequest`, ver preview/resultado expandido y
   reintentar fallos desde el panel. Hoy `GoogleOpsView` cubre Google y el panel
   ya lista solicitudes recientes y despacha automaticamente al aprobar una
   `ActionRequest`.

## Guardrails no negociables

- No usar perfiles reales de Chrome/Firefox.
- No abrir dominios fuera de allow-list.
- No enviar emails sin aprobacion.
- No modificar DNS sin preview y aprobacion.
- No mover archivos locales fuera de `COMPUTER_ALLOWED_ROOTS`.
- No leer secretos ni archivos `.env` desde acciones de computador.
- No escribir documentos fuera de `DOCUMENT_OUTPUT_ROOT` ni mayores que
  `DOCUMENT_MAX_SIZE_BYTES`.
- No usar `browser_preview` con cookies persistidas, login, ni modo headed.
  Sus screenshots quedan acotadas a `BROWSER_SCREENSHOT_MAX_BYTES` dentro de
  `BROWSER_SCREENSHOT_DIR`.
- El Code Director no codifica en su propio proceso ni gasta tokens hasta
  que el operador aprueba el plan; el código generado vive aislado en
  `LOCAL_STORAGE_DIR/workspaces/code_builds/` y el `tar.gz` entregable
  jamás escapa `DOCUMENT_OUTPUT_ROOT/code_builds/`. El `fake` adapter es
  sólo de tests (rechazado con 400 en la API).

## Code Director (delegación a coding agents)

Meta-agente que descompone un objetivo de alto nivel en subtareas y
delega cada una a un coding agent externo
(`claude_code` | `codex` | `kimi` | `deepagent`) seleccionable por rol.
Mismo ciclo controlado que el resto del Action Plane: **plan →
HumanApproval → dispatch Celery (`agent_longrun`) → ejecución →
JobEvents + AuditEvent → entrega `tar.gz`**. Budget caps duros
(`max_runtime_minutes`, `max_total_llm_calls`, `max_calls_per_subtask`,
`max_total_cost_usd`); al excederse el build queda `partial` y entrega
lo construido. El plan lo genera un **planner LLM-driven** que
descompone el objetivo en subtareas reales (con fallback heurístico
determinista ante cualquier fallo, así un build nunca muere por el LLM
planificador); cada subtarea se promptea con el estado vivo del
workspace + lo que produjeron sus dependencias, y los reintentos son
dirigidos por el error del intento anterior. Detalle operativo completo
en `docs/RUNBOOK.md` § "Code Director".

| Endpoint | Proposito | Ejecuta accion real |
|---|---|---|
| `POST /code-director/run` | Planifica un build y crea `Job`+`HumanApproval` | No (sin tokens hasta aprobar) |
| `GET /code-director/{id}` | Estado + plan + result | No |
| `GET /code-director/{id}/events` | SSE del timeline de JobEvents | No |
| `GET /code-director/{id}/download` | `tar.gz` del workspace generado | No |

## Documentos: DOCX/XLSX/PPTX

Variables:

- `ENABLE_DOCUMENT_GENERATION=true`
- `DOCUMENT_OUTPUT_ROOT=./storage/documents`
- `DOCUMENT_ASSET_ROOTS=./storage/documents/assets`
- `DOCUMENT_MAX_SIZE_BYTES=10485760`

Diseno:

- `DocumentActionService` valida formato (`docx|xlsx|pptx`), rechaza rutas con
  `..` o absolutas y obliga a que el output este dentro de
  `DOCUMENT_OUTPUT_ROOT`.
- Las imagenes de documentos solo se leen desde `DOCUMENT_ASSET_ROOTS`. Si esa
  lista esta vacia, el embedding de imagenes queda bloqueado.
- `build_preview` devuelve la ruta final, formato, `estimated_blocks` y
  motivo de bloqueo si aplica.
- `execute` escribe con `python-docx`, `openpyxl` o `python-pptx`. Si el
  archivo final supera `DOCUMENT_MAX_SIZE_BYTES` se borra y se devuelve
  `blocked`.
- DOCX soporta parrafos, tablas con encabezado, imagenes allow-listed y captions.
- XLSX distingue entre strings y formulas: strings que empiezan con `=/+/-/@`
  se neutralizan; formulas reales deben venir como `SpreadsheetFormula` y se
  bloquean si intentan comandos, URLs externas, `HYPERLINK`, `WEBSERVICE` o
  referencias a workbooks externos.
- PPTX soporta layouts `title`, `bullets`, `two_column` y `quote`.
- `ActionRequest` con `action_type='document_generate'` queda en
  `pending_approval` por defecto: requiere aprobacion humana antes de
  ejecutar via Celery, igual que `computer_organize`.

## Gmail Daily Digest read-only

Variables:

- `GMAIL_READ_ENABLED=true`
- `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`
- `GMAIL_TOKEN_DIR=./storage/oauth/gmail`
- `GMAIL_SCOPES=https://www.googleapis.com/auth/gmail.readonly`

Diseno:

- `GmailDigestService.build_preview` redacta direcciones (`l***l@dominio`),
  agrupa por remitente, ordena por fecha y propone respuestas como texto.
- **Nunca crea drafts en Gmail**, ni siquiera con flags de send activas. El
  loop es: leer -> proponer texto -> Diego decide fuera del mailbox.
- El servicio consume un `GmailReader` Protocol. En tests se puede inyectar un
  fake; en runtime, si `GMAIL_READ_ENABLED=true`, el default es
  `GmailRestReader` leyendo `GMAIL_TOKEN_DIR/token.json`.
- Endpoint nuevo: `POST /actions/gmail/digest/preview`. Tests usan
  `FakeGmailReader([dicts])` y monkeypatch del singleton.

## Browser interactivo + vision (opt-in)

Variables (mismas que browser_preview):

- `ENABLE_BROWSER_AUTOMATION=true`
- `BROWSER_HEADLESS_DEFAULT=true` (obligatorio)
- `BROWSER_ALLOWED_DOMAINS=example.com,...`
- `BROWSER_SCREENSHOT_DIR`, `BROWSER_SCREENSHOT_MAX_BYTES`, `BROWSER_NAVIGATION_TIMEOUT_MS`

Diseno:

- `BrowserInteractiveService.execute(BrowserInteractiveRequest)` ejecuta un plan
  de pasos (`navigate`, `click`, `fill`, `scroll`, `wait`, `screenshot`, `analyze`).
- **Validacion pre-launch**: enable flag, headless flag, allow-list de dominios
  (incluyendo cada `navigate`), CSS selector regex (rechaza `;`, `'`, etc fuera de
  patrones validos), tope de 10s en `wait`, prompt requerido en `analyze`.
- **`analyze`**: captura un screenshot y lo envia al `VisionAnalyzer` Protocol.
  El default (`ChatVisionAnalyzer.from_settings`) usa el primary chat model en
  modo multimodal (`HumanMessage` con bloques `text` e `image_url` data-URI).
  Tests inyectan FakeAnalyzer; produccion usa el LLM multimodal configurado en
  `VISION_LLM_*`/`PRIMARY_LLM_*` (OpenAI-compatible, actualmente DeepSeek V4 Pro
  como base local y proveedor vision configurable).
- `BrowserInteractiveProvider` Protocol; default `PlaywrightBrowserInteractive
  Provider` (Chromium headless). Si Playwright no esta instalado, el executor
  devuelve `blocked` con razon clara.
- Cada screenshot excedente del cap se borra antes de retornar; ningun PNG queda
  huerfano en disco.
- Endpoint: `POST /actions/browser/interactive/request` bajo JWT, crea
  `ActionRequest` con `pending_approval` o `blocked`, ligando `HumanApproval` y
  `Job` para que Celery ejecute solo tras aprobacion.

## Browser headless preview (opt-in)

Variables:

- `ENABLE_BROWSER_AUTOMATION=true`
- `BROWSER_AUTOMATION_PROVIDER=playwright` (Chromium)
- `BROWSER_ALLOWED_DOMAINS=example.com,docs.python.org,...`
- `BROWSER_HEADLESS_DEFAULT=true` (obligatorio para `browser_preview`)
- `BROWSER_SCREENSHOT_DIR=./storage/browser/screenshots`
- `BROWSER_NAVIGATION_TIMEOUT_MS=20000`
- `BROWSER_SCREENSHOT_MAX_BYTES=5242880`

Diseno:

- `BrowserPreviewService.validate` exige `ENABLE_BROWSER_AUTOMATION=true`,
  `BROWSER_HEADLESS_DEFAULT=true` y dominio dentro de
  `BROWSER_ALLOWED_DOMAINS`. Rechaza modo headed y vision.
- El provider se inyecta. El default es `PlaywrightBrowserPreviewProvider`
  (Chromium headless via `sync_playwright`). Si `playwright` no esta
  instalado, el executor responde `blocked` con razon clara: el operador
  debe correr `uv sync && playwright install chromium`.
- `execute` resuelve la ruta de screenshot dentro de
  `BROWSER_SCREENSHOT_DIR` con `validate_path_inside_roots`, lanza el
  navegador, obtiene `final_url`, `title` y captura PNG. Si la captura
  excede `BROWSER_SCREENSHOT_MAX_BYTES` se borra el archivo y se devuelve
  `blocked`.
- `ActionRequest` con `action_type='browser_preview'` queda en
  `pending_approval` por defecto: requiere aprobacion humana antes de
  ejecutar via Celery. Cookies no se persisten entre ejecuciones.

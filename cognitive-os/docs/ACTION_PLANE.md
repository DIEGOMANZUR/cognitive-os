# Action Plane

> **Estado actual (2026-05-15, Fase 33 RBAC + cifrado):** capa **preview-first con
> `ActionRequest` persistente** y carril activo de **mail personal aprobado**.
> Hay ejecución real para `computer_organize`, `document_generate`,
> `browser_preview`, `browser_interactive`, GoDaddy DNS (solo con dry-run
> desactivado, dominio allow-listed y aprobación), Google Calendar create y
> Google Drive upload **solo vía `/request` + aprobación**, y mail GoDaddy SMTP
> (solo `/mail/messages/{id}/approve-send`, con `MAIL_REQUIRE_APPROVAL_FOR_SEND=true`).
> Gmail sigue read-only para digest/label `TODOS`.
> Google Maps es read-only con rutas de tráfico y link navegable. Las migraciones
> Alembic relevantes ya activas: `action_requests` (v1 + browser_preview +
> browser_interactive + document_generate + `payload_executable` separado),
> `mail_*` (cuentas/mensajes/send_logs), `personal_tasks/notes` y nuevos action
> types Google (`calendar_create_event`, `drive_upload_file`). Fase 33 añade
> cifrado at-rest configurable de `payload_executable` y admin/RBAC explícito.

El action plane es la capa que prepara a Cognitive OS para actuar en el computador,
en navegador y en servicios externos sin saltarse seguridad, auditoria ni aprobacion
humana.

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
- Gmail: `digest/preview` redacta direcciones y propone borradores; **nunca**
  crea drafts en el mailbox del usuario.
- Google Maps: `geocode` y `route` son read-only; `route` incluye tráfico,
  duración estática, retraso y link Google Maps sin exponer API keys.
- Google Calendar: `events/create` es preview-only; si llega `dry_run=false`
  responde `409`. El carril comercial usa `events/request` -> `ActionRequest` ->
  aprobación -> Celery.
- Google Drive: `folders/ensure` gestiona la carpeta de entregables; `files/upload/request`
  sube archivos permitidos por `COMPUTER_ALLOWED_ROOTS` y cap de tamaño. Los
  endpoints directos `folders/ensure` y `files/upload` rechazan `dry_run=false`.
- Mail personal: `cognitive_os.mail` lee GoDaddy IMAP y Gmail label `TODOS`
  cuando está habilitado, persiste mensajes, propone respuestas como texto y
  envía desde GoDaddy SMTP solo tras aprobación humana.
- GoDaddy: `dns/preview` y `dns/request` aplican rate limit local; ejecución
  real solo si `GODADDY_DNS_DRY_RUN_ONLY=false` + dominio allow-listed +
  aprobación; producción exige `GODADDY_ALLOW_PRODUCTION_WRITES=true`.

## Principio central

Toda accion se modela en un ciclo controlado:

1. **Validate**: la solicitud pasa por allow-lists y flags de entorno.
2. **Preview**: el sistema devuelve que haria, que endpoint/ruta usaria y si
   requiere aprobacion.
3. **Request**: si la accion puede ejecutar, se guarda como `ActionRequest`
   con payload redactado, preview, estado, idempotency key y metadata.
4. **Approve**: acciones reales requieren `HumanApproval`.
5. **Dispatch**: una aprobacion aceptada se encola como job Celery.
6. **Execute/Audit**: el worker ejecuta el executor permitido, guarda resultado
   o error, y registra `AuditEvent`.

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
| `POST /actions/gmail/digest/preview` | Resumen diario read-only con borradores propuestos (no crea drafts en Gmail) | No |
| `GET /actions/maps/status` | Estado Maps/Routes/Geocoding | No |
| `POST /actions/maps/geocode` | Geocodifica una dirección | No |
| `POST /actions/maps/route` | Calcula ruta con tráfico/link Google Maps | No |
| `GET /actions/calendar/status` | Estado Calendar/OAuth/write flag | No |
| `POST /actions/calendar/events` | Lista eventos por rango | No |
| `POST /actions/calendar/events/create` | Preview directo; rechaza `dry_run=false` con `409` | No |
| `POST /actions/calendar/events/request` | Crea `ActionRequest` aprobable para evento Calendar | No directamente |
| `GET /actions/drive/status` | Estado Drive/OAuth/upload cap/carpeta | No |
| `POST /actions/drive/files` | Busca archivos Drive | No |
| `GET /actions/drive/files/{file_id}` | Lee metadata de archivo Drive | No |
| `POST /actions/drive/folders/ensure` | Preview de carpeta de entregables; rechaza `dry_run=false` con `409` | No |
| `POST /actions/drive/files/upload` | Preview/upload directo; rechaza `dry_run=false` con `409` | No |
| `POST /actions/drive/files/upload/request` | Crea `ActionRequest` aprobable para upload Drive | No directamente |
| `GET /mail/status` | Estado del carril mail personal y cuentas configuradas | No |
| `POST /mail/sync` | Sincroniza GoDaddy IMAP/Gmail-label de forma manual | No |
| `POST /mail/sync/dispatch` | Encola sync de mail en Celery queue `mail` | No |
| `GET /mail/messages` | Lista mensajes persistidos y propuestas | No |
| `PATCH /mail/messages/{id}/reply` | Edita la propuesta escrita | No |
| `POST /mail/messages/{id}/ignore` | Marca mensaje como ignorado | No |
| `POST /mail/messages/{id}/approve-send` | Envía la respuesta aprobada por SMTP GoDaddy | Sí, solo aprobación explícita |
| `GET /actions/godaddy/status` | Estado de GoDaddy/API/MCP publico | No |
| `POST /actions/godaddy/dns/preview` | Previsualiza cambio DNS | No |
| `POST /actions/godaddy/dns/request` | Crea `ActionRequest` persistente para cambio DNS (preview-only) | No |
| `GET /actions/documents/status` | Estado del generador de documentos (DOCX/XLSX/PPTX) | No |
| `POST /actions/documents/preview` | Previsualiza ruta de salida, formato y bloques estimados | No |
| `POST /actions/documents/request` | Crea `ActionRequest` persistente para generar un documento | No directamente |
| `POST /actions/browser/preview/request` | Crea `ActionRequest` persistente para `browser_preview` headless (titulo + screenshot, sin login) | No directamente |
| `POST /actions/browser/interactive/request` | Plan interactivo (click/fill/scroll/screenshot/analyze) con vision LLM opcional | No directamente |

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
  `HumanApproval` aprobada y despacho por `/actions/requests/{id}/dispatch`.
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
- `MAIL_POLL_INTERVAL_SECONDS=120`
- `MAIL_IMAP_TIMEOUT_SECONDS=30`
- `MAIL_SMTP_TIMEOUT_SECONDS=30`
- `MAIL_FETCH_MAX_PER_FOLDER=25`
- `MAIL_GMAIL_LABEL=TODOS`
- `MAIL_GODADDY_ENABLED=false`
- `MAIL_GODADDY_IMAP_HOST=imap.secureserver.net`
- `MAIL_GODADDY_IMAP_PORT=993`
- `MAIL_GODADDY_SMTP_HOST=smtpout.secureserver.net`
- `MAIL_GODADDY_SMTP_PORT=465`
- `MAIL_GODADDY_USERNAME=diego@doctormanzur.com`
- `MAIL_GODADDY_PASSWORD=CHANGEME`
- `MAIL_GODADDY_MONITOR_FOLDERS=INBOX,Bulk Mail,Junk Email,Spam`

Diseño:

- GoDaddy IMAP es la fuente principal de correo propio.
- Gmail solo se lee por label (`MAIL_GMAIL_LABEL`, por defecto `TODOS`) si
  `GMAIL_READ_ENABLED=true` y existe OAuth token.
- El sistema genera propuestas de respuesta **como texto**; no crea drafts en el
  buzón.
- El envío real sale por SMTP GoDaddy y requiere `approve-send` autenticado.
- `MAIL_REQUIRE_APPROVAL_FOR_SEND=true` debe mantenerse en producción.
- Los mensajes se guardan en `mail_messages`; los envíos en `mail_send_logs`.

## Google Maps / Calendar / Drive

Variables:

- `GOOGLE_MAPS_API_KEY=CHANGEME`
- `ENABLE_MAPS_GEOCODING=false`
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
  `google_maps_url` para abrir la ruta manualmente.
- Calendar list es read-only. Crear eventos reales exige
  `ENABLE_GOOGLE_CALENDAR_WRITE=true` y una `ActionRequest` aprobada
  (`calendar_create_event`). El endpoint directo `events/create` no ejecuta
  writes reales.
- Drive list/get es read-only. Upload real exige `ENABLE_GOOGLE_DRIVE_WRITE=true`,
  path dentro de `COMPUTER_ALLOWED_ROOTS`, tamaño bajo
  `GOOGLE_DRIVE_UPLOAD_MAX_BYTES` y aprobación vía `/request`. Los endpoints
  directos de Drive no ejecutan writes reales.
- Drive usa por defecto la carpeta `GOOGLE_DRIVE_DELIVERABLES_FOLDER_NAME` para
  entregables del sistema. `folders/ensure` previsualiza esa carpeta; la creación
  real queda bajo el ciclo aprobable.
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
6. Crear/ejecutar `ActionRequest` para `calendar_create_event` y
   `drive_upload_file` bajo doble compuerta.
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
- No mover archivos fuera de `COMPUTER_ALLOWED_ROOTS`.
- No leer secretos ni archivos `.env` desde acciones de computador.
- No escribir documentos fuera de `DOCUMENT_OUTPUT_ROOT` ni mayores que
  `DOCUMENT_MAX_SIZE_BYTES`.
- No usar `browser_preview` con cookies persistidas, login, ni modo headed.
  Sus screenshots quedan acotadas a `BROWSER_SCREENSHOT_MAX_BYTES` dentro de
  `BROWSER_SCREENSHOT_DIR`.

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
  agrupa por remitente, ordena por fecha y propone borradores con
  `requires_approval=True`.
- **Nunca crea drafts en Gmail**, ni siquiera con flags de send activas. El
  loop es: leer -> proponer -> aprobacion humana antes de tocar el mailbox.
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

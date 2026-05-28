# Guía de Usuario — Cognitive OS

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-28, Prompt 7 V2.0 — re-ejecutado).** Esta rama `codex/commercial-zero-friction-hardening` queda certificada como **APTA COMERCIAL LOCAL-FIRST** para PC dedicado. Branch inicial Prompt 1 V2.0: HEAD `935193e`. El commit final del Prompt 7 V2.0 firma los deltas P3 (F-P2-101 restore + F-P2-103 + F-P2-104 parcial + F-P2-105) y P6 (V2-EVAL-200 path policy + V2-EVAL-202 docanalysis review). Evidencia viva en `tmp/v2_07_absolute_release_closure_20260528_133000/`.
>
> **Hallazgos cerrados V2.0 (10 verificados):** F-P2-101 working tree restored · F-P2-103 (P1) drive_get_file non-ASCII → 400 (15 tests) · F-P2-104 (P2 parcial) responses={} declarado, 89 endpoints en backlog R-001 · F-P2-105 (P3) `_inspect_workers_snapshot` con `connection_or_acquire` + connection=conn (verificado live **6/6 ciclos chaos consecutivos**) · F-P2-102 (P3) demostrado FALSO POSITIVO · V2-EVAL-200 (P1) `_is_sensitive_root` bloquea `~/.ssh`, `~/.gnupg`, `credentials/`, `tokens/` (16 tests) · V2-EVAL-201 (P3) log crudo Code Director ciclo completo · V2-EVAL-202 (P3) `apply_quality_evaluation` reconcilia top-level `human_review_required` con item severity=high / needs_human_review (4 tests). V2-EVAL-001/004/005 previos del cierre V2.0 anterior siguen sosteniéndose.
>
> **Gates V2.0 medidos antes del cierre absoluto:** `bash scripts/full-qa.sh` **1269 passed, 1 skipped, 28 deselected** (ruff/format/mypy/alembic/sync_doc_counts/git-diff verdes); `bash scripts/stress-qa.sh 5` **5/5 verde × 1269 passed × 2 ciclos posteriores al último cambio**, flakiness **0%**; `cd frontend && npx playwright test` **44 passed × 2 ciclos**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/openapi_readonly_smoke.py` **70 GET / 0 failures**; `bash scripts/verify_desktop_launchers.sh` OK; bandit severity-high 0 issues; `POST /health/verify` overall **`ok`** con `mcp_client` live `ok` 6/6 y **70 tools live**; checklist 400 puntos ejecutada (P7 V2.0). **37 tests de regresión nuevos acumulados** (15 F-P2-103 + 2 F-P2-105 + 16 V2-EVAL-200 + 4 V2-EVAL-202).
>
> **Criterio de verdad:** no se declara envío de correo, draft real ni escritura DNS. Mail queda normalizado como read-only (sync/list/classify/digest + proposed replies como texto). GoDaddy preview/dry-run. Action Plane mantiene `validate→preview→request→approve→dispatch→execute→audit` con idempotencia y reapers. Computer organize/inventory bloquean `root_path` con markers sensibles (`.ssh`, `.gnupg`, `credentials`, `secret`, `tokens`, `keychain`) además de la allow-list existente. El runtime corre en `127.0.0.1` sin exposición LAN/internet. **Cognitive OS queda certificado en este commit como APTO COMERCIAL LOCAL-FIRST para PC dedicado, con funcionamiento real activado, documentación sincronizada, dos ciclos completos verdes posteriores al último cambio, Git ordenado y sin P0/P1/P2 abiertos.**

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->

> **Esta guía es la referencia operativa completa de Cognitive OS.** Explica
> qué es, cómo levantarlo, y **cada una de sus funciones** con ejemplos reales,
> indicando en qué canal usarlas (cockpit web, bot de Telegram o API REST).
> Para la guía técnica profunda ver `COGNITIVE_OS_GUIDE.md`; para arquitectura
> ver `ARCHITECTURE.md`; para operación diaria ver `RUNBOOK.md`.

---

## Índice

1. [Qué es Cognitive OS](#1-qué-es-cognitive-os)
2. [Los tres canales de uso](#2-los-tres-canales-de-uso)
3. [Arrancar, reiniciar y detener](#3-arrancar-reiniciar-y-detener)
4. [Primer login y autenticación](#4-primer-login-y-autenticación)
5. [El cockpit web vista por vista](#5-el-cockpit-web-vista-por-vista) (las 20 vistas)
6. [Chat y orquestador (LangGraph)](#6-chat-y-orquestador-langgraph)
7. [Conocimiento y RAG (documentos)](#7-conocimiento-y-rag-documentos)
8. [Análisis de documentos legales](#8-análisis-de-documentos-legales)
9. [DeepAgents, skills y memoria](#9-deepagents-skills-y-memoria)
10. [Action Plane (acciones sobre el mundo real)](#10-action-plane-acciones-sobre-el-mundo-real)
11. [Correo (read-only)](#11-correo-read-only)
12. [Google: Calendar, Drive, Maps](#12-google-calendar-drive-maps)
13. [GoDaddy DNS](#13-godaddy-dns)
14. [Navegador real (Kimi WebBridge)](#14-navegador-real-kimi-webbridge)
15. [Code Director (delegar programación)](#15-code-director-delegar-programación)
16. [MCP (herramientas externas dinámicas)](#16-mcp-herramientas-externas-dinámicas)
17. [Aprendizaje autónomo (Fases A–E)](#17-aprendizaje-autónomo-fases-a-e)
18. [Asistente personal: tareas y notas](#18-asistente-personal-tareas-y-notas)
19. [Salud, readiness y observabilidad](#19-salud-readiness-y-observabilidad)
20. [Telegram: los 37 comandos](#20-telegram-los-37-comandos)
21. [API REST: ejemplos con curl](#21-api-rest-ejemplos-con-curl)
22. [Qué hace y qué NO hace](#22-qué-hace-y-qué-no-hace)
23. [Modelo de seguridad para el usuario](#23-modelo-de-seguridad-para-el-usuario)
24. [Troubleshooting](#24-troubleshooting)
25. [Glosario](#25-glosario)

---

## 1. Qué es Cognitive OS

Cognitive OS es tu **sistema operativo cognitivo personal, local-first**: un
agente de IA que vive en tu PC, con tus credenciales reales, capaz de:

- **Investigar y responder** con citas a tus documentos (RAG).
- **Analizar documentos legales** (matriz de evidencia, línea de tiempo,
  contradicciones, borradores) con citas verificables.
- **Leer y clasificar tu correo** (Gmail + GoDaddy) y proponer respuestas — sin
  enviar ni crear borradores por su cuenta.
- **Operar Google**: rutas con tráfico (Maps), disponibilidad y eventos
  (Calendar), búsqueda y organización (Drive).
- **Controlar tu navegador Edge real** con tus sesiones (Kimi WebBridge).
- **Organizar archivos** de tu PC con plan previo y auditoría.
- **Gestionar DNS de GoDaddy** en modo preview/dry-run.
- **Delegar tareas de programación** a CLIs de coding agents (Code Director).
- **Aprender** de su propio uso (recetas, skills, lecciones) bajo tu aprobación.

**Filosofía del producto** (perfil `dedicated_local/full`):

1. **Vos sos el dueño.** Corre en tu máquina, con tus credenciales, ligado a
   `127.0.0.1` (sin exposición a internet).
2. **Fricción operativa casi nula** por sobre seguridad estricta — porque este
   PC está dedicado a Cognitive OS.
3. **Mail es la excepción dura**: el flujo normal **solo lee, clasifica, resume
   y propone texto**. Nunca envía ni crea drafts salvo orden explícita tuya con
   flags de escape activos.
4. **Si algo falla, falla visible**: trazabilidad (`AuditEvent`/`JobEvent`),
   idempotencia, reapers de trabajos colgados, health honesto.

---

## 2. Los tres canales de uso

Todo lo que hace Cognitive OS está disponible por **tres vías equivalentes** que
comparten el mismo servicio de negocio (mismas políticas, mismas aprobaciones,
mismo audit):

| Canal | URL / acceso | Cuándo conviene |
|---|---|---|
| **Cockpit web** | `http://127.0.0.1:3001` | Uso diario, ver estado, aprobar acciones, analizar documentos. |
| **Telegram** | `@Socio_dimn_bot` | En movilidad; consultas rápidas; chat conversacional. |
| **API REST** | `http://127.0.0.1:8000` | Integraciones, scripts, automatización. |

> Mismo cerebro detrás de los tres: si aprobás una acción desde el cockpit o
> desde Telegram, el resultado y el audit son idénticos.

---

## 3. Arrancar, reiniciar y detener

La forma más simple son los **lanzadores de escritorio** (en `~/Escritorio/`):

| Necesito… | Lanzador | Qué hace |
|---|---|---|
| Arrancar todo | `Levantar Cognitive OS.sh` | Docker (Postgres/Redis/Weaviate/Neo4j) + backend + worker + beat + frontend |
| Reiniciar | `Reiniciar Cognitive OS.sh` | Reinicia limpio (útil tras cambios de `.env`) |
| Detener | `Detener Cognitive OS.sh` | Baja todo ordenadamente |
| Ver estado | `Estado Cognitive OS.sh` | Reporta qué componentes están vivos |

**Equivalente manual** (desde la raíz del repo):

```bash
bash cognitive-os/scripts/dev_up.sh          # infra Docker + healthchecks
cd cognitive-os/backend
uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000   # API
bash ../scripts/dev_worker.sh                # Celery worker
bash ../scripts/dev_beat.sh                  # Celery beat (cron)
cd ../frontend && npm run serve              # frontend en :3001
```

Verificá que arrancó:

```bash
curl http://127.0.0.1:8000/health   # → {"status":"ok","service":"cognitive-os"}
```

---

## 4. Primer login y autenticación

El cockpit y la API usan un **JWT local**. En el perfil `dedicated_local/full`
el sistema lo **auto-provisiona** — al abrir `http://127.0.0.1:3001` ya quedás
autenticado.

Para obtener un JWT manualmente (scripts/API):

```bash
JWT=$(curl -s -X POST http://127.0.0.1:8000/auth/local-token | jq -r .access_token)
echo "$JWT"   # token bearer válido ~60 min
```

En el cockpit público (`cognitive.doctormanzur.com`, on-demand) el login es por
hash: `https://cognitive.doctormanzur.com/#cogos_token=<JWT_SIN_BEARER>`. El
frontend lo persiste en `localStorage` y limpia el fragmento de la URL.

---

## 5. El cockpit web vista por vista

El cockpit es un **glass cockpit dark-only, PWA instalable**. Navegación por
sidebar + header contextual + bottom-nav en móvil. **Hotkeys** `1`–`9`:

`1` Dashboard · `2` Chat · `3` DeepAgents · `4` Document Analysis ·
`5` Jobs · `6` Aprobaciones · `7` LangSmith · `8` Audit · `9` Health.
`Ctrl/Cmd+K` abre la **command palette** (búsqueda fuzzy de cualquier vista o acción).

Las **20 vistas** (`frontend/app/views/*.tsx`):

| Vista | Para qué | Cómo se usa |
|---|---|---|
| **Dashboard** | Pulso del sistema: métricas vivas (docs, chunks, jobs, approvals), salud resumida, actividad reciente. | Es la portada. Refresca solo (polling pausado si la pestaña está oculta). |
| **Chat** | Hablar con el orquestador. | Escribís en lenguaje natural; podés adjuntar `doc_ids` para forzar análisis legal. |
| **DeepAgents (Agents)** | Ver los subagentes activos y sus stats. | Inspección; muestra research / document-analysis / personal. |
| **Skills** | Skills DeepAgents habilitadas (pack legal + core). | Lectura; cada skill tiene su `SKILL.md`. |
| **Memory** | Propuestas de memoria, recetas y warnings aprendidos. | Aprobás/rechazás propuestas; botón "Extraer ahora". |
| **Assist** | Tareas y notas personales. | CRUD de tareas y notas con búsqueda. |
| **Google Ops** | Maps / Calendar / Drive. | Pedís ruta, ves freebusy, buscás en Drive. |
| **Mail** | Bandeja multicuenta read-only + digest. | Ves correos clasificados; generás digest; ves respuestas propuestas (no envía). |
| **Documents** | Documentos ingestados y sus chunks. | Ves estado `indexed`, abrís chunks con cita page/chunk. |
| **Document Analysis** | Análisis legal de uno o más documentos. | Elegís modos; descargás JSON/MD/CSV/DOCX. |
| **Jobs** | Trabajos async (ingesta, análisis, builds, reapers). | Ves estado/progreso, eventos, cancelás. |
| **Approvals** | Compuertas humanas (HITL). | Aprobás o rechazás acciones sensibles. |
| **Sandbox** | Estado de OpenShell (sandbox de código). | Lectura; off por defecto. |
| **Research** | Runs de investigación persistentes. | Lanzás/seguís investigaciones con citas. |
| **Code Director** | Builds delegados a coding agents. | Ves plan, aprobás, seguís eventos, descargás `tar.gz`. |
| **LangSmith** | Trazas de runtime de LangGraph (si tracing on). | Inspección de runs y proyectos. |
| **Audit** | Trail de auditoría de toda acción importante. | Timeline real con `action`, `user`, `created_at`. |
| **Health** | 18 componentes con estado honesto. | Botón **"Verificar en vivo"** (`/health/verify`). |
| **Configuration** | Flags y proveedores activos (sin secretos). | Lectura del estado de configuración. |
| **Settings** | API base + JWT + tile MCP. | Persistís API base/JWT en `localStorage`. |

**Estados comerciales reales**: cada vista que consume listas muestra estados
`loading` / `empty` / `error` **honestos** — nunca inventa filas ni datos falsos.

---

## 6. Chat y orquestador (LangGraph)

El chat enruta tu pedido por un grafo de estados (router → research / legal /
comm / social) con checkpointer en Postgres (los hilos sobreviven reinicios).

**Cockpit**: vista **Chat** (hotkey `2`).
**Telegram**: cualquier mensaje **sin** `/` (modo conversacional) o `/chat <texto>`.
**API**:

```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"message":"¿Qué contratos tengo del año pasado?"}' | jq
# → { "thread_id": "...", "message": "...", "route": "research", "pending_human_review": null }
```

**Forzar análisis legal** adjuntando documentos (fuerza la ruta `legal`):

```bash
curl -s -X POST http://127.0.0.1:8000/chat -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message":"Analiza este contrato","doc_ids":["<DOC_ID>"]}' | jq .route
# → "legal"
```

- Hilo persistente: pasá el mismo `thread_id` en mensajes sucesivos.
- `/threads/{id}` devuelve el historial completo (system + human + ai).
- `/threads/{id}/resume` continúa desde el checkpoint.
- Degradación elegante: si los LLM no responden, cae a ruteo determinístico por
  keywords; si Weaviate cae, responde "sin evidencia" en vez de fallar.

---

## 7. Conocimiento y RAG (documentos)

Cognitive OS ingesta PDFs → páginas → chunks → Weaviate (búsqueda híbrida
BM25+vector) + Neo4j (grafo de entidades, read-only). Las respuestas citan
`doc_id` / `page` / `chunk_id`.

**Ingestar un PDF** (CLI):

```bash
bash cognitive-os/scripts/ingest_now.sh /ruta/absoluta/contrato.pdf
# → document_id=... pages=2 chunks=2 warnings=0
```

**Telegram**: `/ingest /ruta/absoluta.pdf`

**Ver documentos y chunks** (API):

```bash
curl -s -H "Authorization: Bearer $JWT" "http://127.0.0.1:8000/documents?limit=5" | jq
curl -s -H "Authorization: Bearer $JWT" \
  "http://127.0.0.1:8000/documents/<DOC_ID>/chunks?limit=2" | jq '.[].text'
```

**Stats de conocimiento**:

```bash
curl -s -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/knowledge/stats | jq
# → { "documents": 40, "pages": 41, "chunks": 256, ... }
```

Cada chunk trae `page_start`, `page_end`, `sha256` y el `text` literal — la base
de las citas verificables.

---

## 8. Análisis de documentos legales

Pipeline dedicado (`Document Analysis`) que produce **6 modos** y **4 formatos**
descargables, con citas literales y aprobación humana cuando corresponde.

**Modos** (`modes`):

| Modo | Qué produce |
|---|---|
| `evidence_matrix` | Matriz de afirmaciones ↔ citas que las soportan. |
| `timeline` | Línea de tiempo de eventos con fechas y fuentes. |
| `contradictions` | Contradicciones detectadas (con severidad y ambas citas). |
| `full_report` | Integra matriz + timeline + contradicciones. |
| `legal_draft_support` | Apoyo a borradores (nunca envía nada). |
| `case_summary` | Resumen del caso con citas verificables. |

**Formatos** generados por defecto: `json`, `markdown`, `csv` (×3:
evidence_matrix, timeline, contradictions) y `docx`.

**Cockpit**: vista **Document Analysis** (hotkey `4`) → elegís documentos +
modos → ves resultados → descargás artefactos.

**API**:

```bash
# Lanzar análisis (vía chat con doc_ids fuerza la ruta legal)
curl -s -X POST http://127.0.0.1:8000/chat -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message":"Detectá contradicciones","doc_ids":["<DOC_ID>"]}' | jq

# Consultar el resultado (mirror exacto del artefacto en disco)
curl -s -H "Authorization: Bearer $JWT" \
  "http://127.0.0.1:8000/document-analysis/<TASK_ID>" | jq \
  '{status, evidence_matrix:(.evidence_matrix|length), contradictions:(.contradictions|length)}'

# Descargar artefactos
curl -s -H "Authorization: Bearer $JWT" \
  "http://127.0.0.1:8000/document-analysis/<TASK_ID>/download/docx" -o reporte.docx
curl -s -H "Authorization: Bearer $JWT" \
  "http://127.0.0.1:8000/document-analysis/<TASK_ID>/download/csv/contradictions" -o contradicciones.csv
```

**Ejemplo real**: un contrato con cláusula 1 "reportes mensuales" y cláusula 2
"reportes trimestrales" produce una contradicción `severity:high` con ambas
citas literales (page+chunk) y marca `human_review_required: true`.

> Si el agente principal devuelve `BadRequest`, cae a un **fallback heurístico**
> que igual produce contenido válido con citas; el resultado queda `status:partial`
> y exige revisión humana.

---

## 9. DeepAgents, skills y memoria

DeepAgents es la capa que hace el trabajo profundo: subagentes con herramientas
tipadas, políticas por rol y memoria persistente.

- **Tools built-in** (entre otras): `search_local_docs`, `read_document_pages`,
  `graph_query_readonly`, `search_web` (gated), `plan_route`, `geocode_address`,
  `list_calendar_events`, `check_calendar_freebusy`, `search_drive_files`,
  `preview_drive_organization`, `browse_real_navigate/snapshot/screenshot`,
  `solve_image_captcha`, `get_relevant_memory`, `propose_memory_update`.
- **Tools dinámicas MCP**: cuando `ENABLE_MCP_CLIENT=true`, se suman las tools de
  los servidores MCP (hoy 70 tools vivas — ver §16).
- **Niveles de riesgo**: `READ_ONLY`, `REVERSIBLE_WRITE`, `EXTERNAL_ACTION`,
  `DANGEROUS`, `SANDBOX_EXECUTE`. Las externas y peligrosas **siempre** pasan por
  aprobación humana, salvo la whitelist reversible en `dedicated_local/full`
  (`drive_ensure_folder`, `drive_upload`, `computer_organize`).
- **Skills**: pack legal (12 skills core: `evidence-matrix`,
  `contradiction-detector`, `timeline-builder`, `citation-discipline`,
  `legal-hold`, `privilege-log-review`, etc.) + skills de usuario.
- **Memoria**: las propuestas pasan por approval (`/deepagents/memory/proposals`)
  antes de quedar activas. Hay memoria semántica, episódica y consolidación
  diaria.

**Cockpit**: vistas **DeepAgents**, **Skills**, **Memory**.
**API**:

```bash
curl -s -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/deepagents | jq
curl -s -H "Authorization: Bearer $JWT" \
  "http://127.0.0.1:8000/deepagents/memory/proposals?limit=5" | jq
```

---

## 10. Action Plane (acciones sobre el mundo real)

El Action Plane prepara y ejecuta acciones sin saltarse trazabilidad, auditoría,
idempotencia ni el perfil operativo. **Ciclo de vida**:

```
validate → preview → request → approve/reject → dispatch → execute → audit
```

**8 capacidades** (`GET /actions/capabilities`):

| Capacidad | Estado típico | Notas |
|---|---|---|
| `browser` | ready | Chromium headless + Edge real (Kimi). |
| `computer` | ready | Organizar/inventariar archivos (con guardas). |
| `documents` | ready | Generar DOCX/XLSX/PPTX con guardrails. |
| `gmail` | ready | Query/digest read-only (nunca drafts). |
| `godaddy` | ready, **dry_run_only** | DNS preview; no escribe sin opt-in. |
| `maps` | ready, dry_run | Geocode + rutas read-only. |
| `google_calendar` | ready, **requires_approval** | Create vía ActionRequest. |
| `google_drive` | ready, **requires_approval** | Upload/organize vía ActionRequest. |

**Action types** (11): `computer_organize`, `browser_navigation`, `gmail_query`,
`godaddy_dns_change`, `document_generate`, `browser_preview`,
`browser_interactive`, `calendar_create_event`, `drive_upload_file`,
`drive_ensure_folder`, `drive_organize_files`.

**Ejemplos**:

```bash
# Organizar una carpeta (preview, no mueve nada todavía)
curl -s -X POST http://127.0.0.1:8000/actions/computer/organize/preview \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"root_path":"/home/jgonz/Descargas","strategy":"by_type"}' | jq '{status, operations:(.operations|length)}'

# Generar un DOCX (queda pending_approval)
curl -s -X POST http://127.0.0.1:8000/actions/documents/preview \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" -d '{...}'

# Listar ActionRequests y su workflow
curl -s -H "Authorization: Bearer $JWT" "http://127.0.0.1:8000/actions/requests?limit=5" | jq
```

**Guardas duras verificadas** (no se pueden saltar):

- `computer_organize` rechaza rutas fuera de `COMPUTER_ALLOWED_ROOTS` y
  **bloquea raíces sensibles** (`~/.ssh`, `~/.gnupg`, `credentials/`, `secret/`,
  `tokens/`, `keychain/`).
- Calendar/Drive con `dry_run=false` directo → **HTTP 409** (hay que pasar por
  `request` + approval).
- Idempotencia: mismo `idempotency_key` no duplica trabajos.

---

## 11. Correo (read-only)

**Contrato de mail** (la excepción dura del producto):

1. Lee Gmail (`TODOS` + `SPAM`) y GoDaddy (`Spam`).
2. Clasifica con criterio propio (no confía en la carpeta del proveedor).
3. Genera **digest** dos veces al día (10:00 y 20:00 hora Chile).
4. Para correos importantes, **propone respuesta como texto**.
5. **No crea drafts. No envía SMTP** en el flujo normal.

**Cockpit**: vista **Mail** (sin botón Enviar — verificado por test).
**Telegram**: `/mail [max]`, `/gmaildigest`.
**API**:

```bash
curl -s -H "Authorization: Bearer $JWT" "http://127.0.0.1:8000/mail/messages?limit=5" | jq
curl -s -X POST http://127.0.0.1:8000/mail/digest/preview \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"sync_first":false}' | jq '.summary_text'
```

**Escape hatch de envío real** (triple gate, deliberadamente incómodo): requiere
**simultáneamente** `ENABLE_EMAIL_SEND=true` + `MAIL_ALLOW_EXPLICIT_SEND=true` +
`explicit_send_confirmation="SEND_THIS_EMAIL_EXPLICITLY"`. Sin las tres,
`/mail/messages/{id}/approve-send` responde **409**.

---

## 12. Google: Calendar, Drive, Maps

**Cockpit**: vista **Google Ops**. **Telegram**: `/maps`, `/calendar`,
`/freebusy`, `/drive`. **API**:

```bash
# Maps: ruta con tráfico (read-only)
curl -s -X POST http://127.0.0.1:8000/actions/maps/route \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"origin":"Santiago, Chile","destination":"Valparaíso, Chile"}' \
  | jq '{distance_meters, duration_seconds}'

# Calendar: disponibilidad (read-only)
curl -s -X POST http://127.0.0.1:8000/actions/calendar/freebusy \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"time_min":"2026-06-01T00:00:00Z","time_max":"2026-06-02T00:00:00Z"}' | jq

# Drive: buscar (read-only)
curl -s -X POST http://127.0.0.1:8000/actions/drive/files \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"query":"name contains \"contrato\"","limit":5}' | jq
```

- **Calendar create** y **Drive upload/organize** son **writes**: pasan por
  `events/request` / `files/upload/request` → ActionRequest → approval. En
  `dedicated_local/full`, los reversibles (`drive_ensure_folder`, `drive_upload`)
  pueden auto-aprobarse.
- Llamar a los endpoints directos con `dry_run=false` → **409** por diseño.

---

## 13. GoDaddy DNS

Read-only / preview por defecto: `GODADDY_DNS_DRY_RUN_ONLY=true` +
`GODADDY_ALLOW_PRODUCTION_WRITES=false`. **Ninguna escritura DNS real** sin
opt-in explícito + dominio en allow-list + aprobación.

**Telegram**: el estado se ve con `/capabilities`. **API**:

```bash
curl -s -X POST http://127.0.0.1:8000/actions/godaddy/dns/preview \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"domain":"doctormanzur.com","record_type":"TXT","name":"_probe","data":"v=test"}' \
  | jq '{dry_run_only, method}'
# → { "dry_run_only": true, "method": "PATCH" }   (no hace tráfico real)
```

---

## 14. Navegador real (Kimi WebBridge)

Permite que el agente controle tu **Edge real** con tus sesiones activas
(navegar, leer, screenshot; mutaciones solo si `KIMI_WEBBRIDGE_ALLOW_MUTATIONS=true`).

```bash
curl -s -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/actions/webbridge/status | jq
```

- Acciones read (`navigate`, `snapshot`, `screenshot`) habilitadas por defecto en
  `dedicated_local`.
- El estado expone `wildcard_allow_all` para que sea transparente cuando la
  allow-list de dominios está en `*`.

---

## 15. Code Director (delegar programación)

Meta-agente que **planifica builds** y los delega a CLIs (Claude Code / Codex /
Kimi / DeepAgents) bajo **aprobación humana + budget caps + audit**.

**Cockpit**: vista **Code Director**. **Telegram**: `/codebuild [max]`. **API**:

```bash
# Planificar (NO ejecuta hasta aprobar)
curl -s -X POST http://127.0.0.1:8000/code-director/run \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"objective":"Crear un script que liste contratos por cliente","adapter_preference":{"default_adapter":"deepagent"}}' \
  | jq '{job_id, approval_id, n_subtasks:(.plan.subtasks|length), detail}'
```

- Devuelve un **plan** (scaffold → implement → review) + un `HumanApproval`
  pendiente. **Ningún coding agent corre hasta que apruebes.**
- Si rechazás, el job queda `rejected` y **el workspace ni se crea**.
- El adapter `fake` se rechaza con **400** (es solo para tests internos).
- Aprobás desde **Approvals** (cockpit) o `POST /approvals/{id}/approve`.

---

## 16. MCP (herramientas externas dinámicas)

Bajo `ENABLE_MCP_CLIENT=true`, el agente carga tools de servidores MCP externos.
Runtime actual: **6/6 servidores**, **70 tools**:

| Servidor | Tools | Qué aporta |
|---|---|---|
| `mem` | 4 | Memoria personal (Supermemory). |
| `gh` | 43 | GitHub (issues/PRs/code search). |
| `fs` | 14 | Filesystem (`/home/jgonz`). |
| `cc` | 1 | Claude Code. |
| `gem` | 6 | Gemini CLI. |
| `time` | 2 | Hora/conversión de zonas (local, read-only, sin red). |

```bash
curl -s -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/system/mcp | jq \
  '{servers:[.servers[]|{name,connected,tools_count}]}'
```

Fail-open por servidor: si uno cae, se skipea con warning y los demás siguen.

---

## 17. Aprendizaje autónomo (Fases A–E)

Cognitive OS aprende de su propio uso. Todo pasa por la puerta de aprobación
(excepción acotada: auto-promote de *warnings* de Fase D, con kill switch).

| Fase | Job | Qué hace |
|---|---|---|
| **A** | `extract_pending_recipes` (`*/30` min) | Distila jobs exitosos en recetas `kind=procedure`. |
| **B** | `evaluate_skill_promotions` (`04:45`) | Promueve procedures → skills YAML, con rollback. |
| **C** | `aggregate_tool_scorecard` (`04:15`) | Rollup de confiabilidad por (agente, tool). |
| **D** | `scan_failure_postmortems` (`03:35`) | Warnings desde patrones fallo→recuperación. |
| **E** | `nightly_reflection` (`03:00`) | El LLM propone preferences/lessons con evidencia literal. |

**Cockpit**: vista **Memory** (recetas, warnings, propuestas). **API**:

```bash
curl -s -H "Authorization: Bearer $JWT" "http://127.0.0.1:8000/deepagents/memory/recipes?limit=5" | jq
curl -s -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/deepagents/learning/tool-scorecard | jq
```

---

## 18. Asistente personal: tareas y notas

**Cockpit**: vista **Assist**. **Telegram**: `/tasks`, `/task titulo | desc`,
`/done <id>`, `/notes`, `/note titulo | cuerpo`. **API**:

```bash
curl -s -X POST http://127.0.0.1:8000/assist/tasks -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" -d '{"title":"Llamar al cliente ACME"}' | jq
curl -s -H "Authorization: Bearer $JWT" "http://127.0.0.1:8000/assist/notes/search?q=contrato" | jq
```

Las notas se indexan en Weaviate para búsqueda semántica.

---

## 19. Salud, readiness y observabilidad

**Health honesto** (`/health/dashboard`, 18 componentes): distingue
`ok`/`ready` (probado o apagado), `configured` (cableado pero sin llamada real),
`degraded` (falla). El overall es `ok` **solo si todo está verificado**.

```bash
# Estado pasivo (no gasta tokens)
curl -s -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/health/dashboard | jq '.status'

# Probe en vivo bajo demanda (LLM, embeddings, IMAP, MCP)
curl -s -X POST -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/health/verify | jq '.status'
# → "ok"
```

**Cockpit**: vista **Health** con botón "Verificar en vivo".

- `/system/readiness`: capacidades del perfil (14/14 unlocked, `gaps=[]`).
- `operational_backlog`: vigila approvals/jobs/action-requests atascados + lag
  del beat; se pone `degraded` cuando un reaper debió limpiar algo y no lo hizo.
- **Audit**: `GET /audit/events` y vista **Audit** muestran el trail real.
- Secrets redactados en logs y trazas (`TRACE_REDACT_PII=true` por defecto).

---

## 20. Telegram: los 37 comandos

Bot `@Socio_dimn_bot`, **fail-closed** (solo tu user_id autorizado; con allowlist
vacía el bot no arranca). Mensaje **sin** `/` = chat conversacional.

| Grupo | Comandos |
|---|---|
| Sistema | `/start` `/help` `/health` `/stats` `/config` `/capabilities` |
| Agentes | `/agents` `/skills` `/memory` `/consolidate` |
| Jobs | `/jobs` `/job <id>` `/cancel <id>` |
| Aprobaciones | `/approvals` `/approve <id>` `/reject <id>` |
| Conversación | `/threads` `/chat <msg>` `/reset` |
| Conocimiento | `/ingest <ruta>` `/documents [max]` `/research [max]` |
| Asistente | `/tasks` `/task <t>` `/done <id>` `/notes` `/note <t>` |
| Correo | `/mail [max]` `/gmaildigest` |
| Google | `/maps origen \| destino` `/calendar [max]` `/freebusy [días]` `/drive <query>` |
| Observabilidad | `/audit [max]` `/runs` |
| Code | `/codebuild [max]` `/sandbox` |

**Ejemplos**:
- `/maps Providencia | Aeropuerto SCL` → ruta con tráfico y link.
- `/freebusy 3` → tu disponibilidad de los próximos 3 días.
- "¿qué correos importantes tengo hoy?" (sin slash) → resumen clasificado.

---

## 21. API REST: ejemplos con curl

Inventario: **150 endpoints** (`@app.*`) + 3 de test (gated). Documentación
viva en `http://127.0.0.1:8000/openapi.json`. Endpoints clave:

```bash
JWT=$(curl -s -X POST http://127.0.0.1:8000/auth/local-token | jq -r .access_token)

curl -s http://127.0.0.1:8000/health                                   # público
curl -s -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/system/info | jq
curl -s -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/system/readiness | jq
curl -s -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/system/credentials-status | jq '{configured, missing_required}'
curl -s -H "Authorization: Bearer $JWT" "http://127.0.0.1:8000/jobs?limit=5" | jq
curl -s -H "Authorization: Bearer $JWT" "http://127.0.0.1:8000/approvals?limit=5" | jq
```

Todo endpoint mutador exige JWT; `/health` es el único público.

---

## 22. Qué hace y qué NO hace

**SÍ hace**:
- Investiga con citas, analiza documentos legales, lee/clasifica correo, opera
  Google read-only, prepara writes con approval, organiza archivos con plan,
  controla Edge real, delega builds con approval, aprende bajo aprobación.

**NO hace** (por diseño):
- ❌ No envía correos ni crea drafts en el flujo normal.
- ❌ No escribe DNS real sin opt-in explícito + approval.
- ❌ No ejecuta código en tu PC sin OpenShell sandbox + approval.
- ❌ No toca `~/.ssh`, `~/.gnupg`, credenciales (bloqueado).
- ❌ No corre coding agents sin que apruebes el plan.
- ❌ No se expone a internet (todo en `127.0.0.1`).
- ❌ No es multi-usuario ni multi-tenant.

---

## 23. Modelo de seguridad para el usuario

- **Local-first**: Postgres/Redis/Weaviate/Neo4j y la API solo en `127.0.0.1`.
- **Secretos fuera de git**: `.env` gitignored; logs y trazas redactan PII/tokens.
- **Aprobaciones humanas** en toda acción externa o peligrosa.
- **Idempotencia + reapers**: nada se duplica; lo colgado se recupera y queda
  visible en `operational_backlog`.
- **Tests aislados**: la suite usa una DB de test (`cognitive_os_test`) y se
  niega a correr contra producción.
- Si algún día este PC deja de ser dedicado, ver `SECURITY.md` §"Si cambia el
  contexto" para endurecer (perfil `strict`).

---

## 24. Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| El cockpit no carga | frontend caído | `Reiniciar Cognitive OS.sh` o `npm run serve` en `frontend/` |
| `/health/verify` da `degraded` | un proveedor real falla | leé el `detail` del componente afectado |
| `google_calendar`/`drive` `blocked` | OAuth scope vencido | `python scripts/auth_google.py` y re-consentir |
| Workers `degraded` tras reiniciar Postgres | conexión stale (resuelto) | el fix F-P2-105 los recupera en ~5s; si persiste, reiniciá uvicorn |
| Approvals acumuladas | falta triage | revisalas en vista **Approvals**; el reaper limpia las stale |
| Chat tarda ~10–15s | latencia del LLM | normal en la primera llamada (cold start) |
| `/actions/drive/files/<id>` da 400 | file_id inválido | usá un id real `[A-Za-z0-9_.-]{1,200}` |

Logs: `bash cognitive-os/scripts/dev_logs.sh`. Verificación completa:
`bash cognitive-os/scripts/full-qa.sh` (suite hermética, 1269 passed).

---

## 25. Glosario

- **Action Plane**: capa que prepara/ejecuta acciones con preview + approval + audit.
- **ActionRequest**: registro persistente de una acción (preview, payload cifrado, estado).
- **HumanApproval**: compuerta humana antes de una acción sensible.
- **DeepAgents**: subagentes con tools tipadas, políticas y memoria.
- **LangGraph**: grafo de estados que orquesta el chat (router → subgrafos).
- **RAG**: retrieval-augmented generation; respuestas con citas a tus documentos.
- **MCP**: Model Context Protocol; servidores externos que aportan tools dinámicas.
- **Reaper**: job que recupera trabajos/aprobaciones colgados.
- **dedicated_local/full**: perfil operativo de fricción casi nula para PC dedicado.
- **Checkpointer**: persiste el estado de cada hilo de chat en Postgres.

---

*Guía de usuario — Cognitive OS. Documento canónico, sincronizado con el código
en el cierre V2.0. Para profundizar: `COGNITIVE_OS_GUIDE.md`, `ARCHITECTURE.md`,
`ACTION_PLANE.md`, `RUNBOOK.md`, `SECURITY.md`.*

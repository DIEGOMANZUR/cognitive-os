# Cognitive OS Hardening And Action Plane Plan

> **Estado actual (2026-05-15, Fase 33 RBAC + cifrado + research durable):** las fases 1–28,
> 30, 31, 32 y 33 tienen sus bloques P0/P1 cerrados. La Fase 33 aplica el núcleo
> de Fase 29: admin explícito/RBAC local, cifrado at-rest de `payload_executable`
> y backend Postgres configurable para snapshots/eventos del Research Orchestrator.
> Queda fuera del código completar variables `.env.local` reales y operar
> credenciales que requieren input manual del operador. Las tablas de "Resultado De
> Verificacion" más abajo son **snapshots históricos** por fase: para
> conocer el verdadero estado de QA hoy ejecuta `bash scripts/full-qa.sh` y
> revisa la salida. Snapshot QA persistente: **492 pytest passed, 1
> skipped, 20 deselected**, ruff/ruff format/mypy/lint/build, Compose config,
> Alembic head y `git diff --check` verdes. Documentación de producto autoritativa:
> `docs/COGNITIVE_OS_GUIDE.md`, `docs/PROJECT_GUIDE.md`,
> `docs/ARCHITECTURE.md`, `docs/OPENHARNESS_FUSION.md`, `docs/RUNBOOK.md`,
> `docs/SECURITY.md`.

## Objetivo

Revisar Cognitive OS de punta a punta y elevarlo hacia una base comercializable:
mas robusta, observable, segura por defecto y preparada para agentes capaces de actuar
con aprobacion humana, auditoria y limites claros.

No se promete software infalible. La meta operativa es eliminar fallas obvias,
reducir superficies fragiles, hacer explicitas las politicas de riesgo y dejar
pruebas/documentacion que sostengan evolucion futura.

## Estado De Fases

| Fase | Estado | Resultado esperado |
|---|---|---|
| 1. Recuperacion y baseline | complete | Entender estructura, checks actuales, deuda inmediata |
| 2. Plan de accion segura | complete | Disenar browser/computer/email/domain actions con deny-by-default |
| 3. Implementacion backend | complete | Modulos, politicas, schemas, endpoints y pruebas |
| 4. Consola y documentacion | complete | UI/README/runbook/security actualizados |
| 5. Verificacion integral | complete | pytest, ruff, mypy, lint/build frontend |
| 6. Normalizacion documental | complete | Markdown claro: guia humana, indice tecnico, estado y roadmap |
| 7. Informe final y roadmap | complete | Resumen claro, limites restantes, pasos para Gmail/GoDaddy/Camoufox |
| 8. Action Requests persistentes | complete | Registrar, aprobar, ejecutar y auditar acciones controladas |
| 9. Unificacion de ciclo Action Request | complete | Browser/Gmail/GoDaddy persistentes preview-only + filtros + cancel |
| 10. Generacion de documentos (DOCX/XLSX/PPTX) | complete | Nuevo executor real `document_generate` con allow-list y aprobacion humana |
| 11. Browser headless preview (Playwright opt-in) | complete | Nuevo executor real `browser_preview` con provider inyectable, sin login |
| 12. Research Orchestrator sobre deepagents | complete | Planner -> N deepagents en paralelo -> synth -> scorer con providers inyectables |
| 13. Gmail Daily Digest read-only | complete | Resumen diario redactado con propuestas de respuesta (nunca crea drafts) |
| 14. Research Orchestrator async + SSE streaming | complete | `start_run` no-bloqueante (daemon thread), `wait_for_run`, endpoint SSE `/research/runs/{id}/events` |
| 15. Correctness critico (8 bugs) | complete | Plan aprobado en computer_organize, payload_executable separado, fallback con respuesta vacia, row lock atomico, allowed_doc_ids, filtro web, auditoria de errores, citas con basename |
| 16. Robustez del pipeline RAG | complete | Postgres-Weaviate consistent order (pending_index -> indexed), sha256 dedup, Weaviate batch insert, BM25-only fallback, ensure_collection thread-safe |
| 17. Browser interactivo + vision multimodal | complete | `browser_interactive` ActionType con click/fill/scroll/wait/screenshot/analyze; VisionAnalyzer Protocol con default ChatVisionAnalyzer sobre LLM multimodal configurado; provider Playwright real + inyectable; persistencia ActionRequest + endpoint POST /actions/browser/interactive/request |
| 18. DeepAgents 0.6.x + subagents/memory | complete | Upgrade a `deepagents>=0.6.1,<0.7.0`, subagents configurables, `write_todos`/task tools preservadas, memory paths seguros, dedup de propuestas |
| 19. Office writers extendidos | complete | DOCX tablas/imagenes, XLSX formulas seguras, PPTX layouts mas ricos |
| 20. Ops hardening | complete | XLSX cell sanitization (formula injection); SSRF protection (DNS resolve + private/loopback/link-local refuse); reaper de action_requests stuck en running; structlog warnings en lugar de silent excepts (web_indexer/reranker); tokenizer reranker con diacriticos y stopwords español |
| 21. Fusión OpenHarness + DeepAgents (research) | complete | Extra `openharness`; `prelude_merge` por defecto (`openharness_prelude` → DeepAgent); `short_circuit`; workspace `deepagent_mirror`; presets toolkit; tests y `docs/OPENHARNESS_FUSION.md` |
| 22. GoDaddy DNS executor seguro | complete | DNS writes reales solo con dry-run desactivado, dominio allow-listed, aprobación y flag prod explícito |
| 23. Restore scripts operativos | complete | Restore Postgres/Neo4j/storage con `CONFIRM_RESTORE=YES`, checksum y copia previa |
| 24. Inventario local de archivos | complete | `computer_inventory` read-only bajo allow-list, sin symlinks ni lectura de secretos |
| 25. Roadmap asistente personal completo | complete | Matriz de capacidades y brechas documentada en `PERSONAL_ASSISTANT_ROADMAP.md` |
| 26. Mail multicuenta personal con aprobación humana | complete | GoDaddy IMAP/SMTP, Gmail label `TODOS`, Postgres `mail_*`, UI Mail, queue `mail`, envío solo aprobado |
| 27. Normalización documental 2026-05-14 | complete | Todos los Markdown activos reflejan DeepSeek V4 Pro, Weaviate 1.29.0, 89 endpoints propios, **17 vistas (incluida `Assist`)**, mail personal y ejecutables escritorio |
| 28. Revisión integral y optimización comercial | in_progress (P0/P1 done) | Auditoría desde cero ejecutada (arquitectura/backend/frontend/seguridad/tests); P0/P1 aplicados: secret hygiene, mail timeouts/redacción, `/config/public` ampliado, contratos frontend, AssistView, tests mail/config/no-secret. **Pendientes P2 → mover a Fase 29**: auth/RBAC, cifrado payload, persistencia research, bind DB privado |
| 29. Endurecimiento comercial multi-usuario | in_progress (code closed, env manual) | Auth/RBAC con roles, cifrado at-rest de `payload_executable` en `action_requests`, persistencia durable configurable del orquestador de research en Postgres; queda completar variables `.env.local` faltantes con input del operador |
| 30. Barrido documental 2026-05-15 | complete | Auditoría con subagente `Explore` + sincronización de 25 markdowns principales con conteos verificados (115 endpoints, 17 vistas, 11 workers, 5 queues, 13 migraciones, 21 MCPs, 15 skills, 7 agentes, 7 comandos), fecha unificada 2026-05-15 04:47 hora Chile |
| 31. Google Maps/Drive/Calendar operables | complete | Maps con tráfico/link, Drive carpeta de entregables, Calendar/Drive writes vía `ActionRequest`, `/actions/capabilities` y `/config/public` con flags Google, `GoogleOpsView`, tests focalizados y QA amplio verde |
| 32. Hardening comercial seguridad/PWA/QA | complete | Google direct writes preview-only, producción exige aprobación humana, errores sensibles redactados, reaper en beat, infra loopback, PWA con headers/update/offline, tests high-value y QA amplio verde |
| 33. Fase 29 aplicada: RBAC + cifrado + research durable | complete | Admin explícito sin fallback implícito, roles en JWT local, cifrado Fernet de payload ejecutable, backend Postgres opcional para runs de research, tests y docs |

## Fase 33 - Plan de implementacion activo

Alcance aprobado por el operador ("dale aplicate con todo"):

- Cerrar el riesgo de admin implícito: roles en JWT local, `AuthenticatedUser.roles`,
  helpers RBAC y validadores de producción.
- Cifrar `ActionRequest.payload_executable` cuando exista clave configurada, exigir
  clave en producción y mantener fallback compatible para filas históricas.
- Añadir persistencia Postgres configurable para snapshots/eventos del Research
  Orchestrator, con modo `memory` sólo para desarrollo/tests.
- Actualizar `.env.example`, documentación viva y tests focalizados.
- Validar con pytest focalizado, ruff, mypy y checks razonables del área tocada.

Resultado:

- RBAC local: `roles` en JWT, `AuthenticatedUser.roles`, admin por
  `AUTH_ADMIN_ROLES` o `ADMIN_USER_IDS`; no hay admin implícito por lista vacía.
- Payload ejecutable: `actions/payload_crypto.py` cifra con Fernet cuando hay
  `ACTION_PAYLOAD_ENCRYPTION_KEY`; producción exige cifrado requerido.
- Research durable: nueva migración `202605150002_research_run_records.py`, modelo
  `research_runs` y `RESEARCH_PERSISTENCE_BACKEND=postgres` obligatorio en producción.
- Validación Fase 33: **492 passed, 1 skipped, 20 deselected**, ruff/format/mypy,
  frontend lint/build, Compose config, Alembic head y `git diff --check` verdes.

## Principios De Diseno

- Deny-by-default para toda accion externa.
- Separar lectura, escritura reversible, accion externa y accion peligrosa.
- Human-in-the-loop obligatorio para email send, dominios, browser con login, red y filesystem real.
- Auditoria redactada para cada intento de accion.
- Allow-lists explicitas de dominios, rutas y scopes.
- Modo simulacion primero; ejecucion real solo cuando configuracion y aprobacion coinciden.
- Ningun secreto en logs, respuestas, reportes o archivos de plan.

## Alcance Inicial

- Backend FastAPI, LangGraph, DeepAgents, tools policy, config, workers y tests.
- Frontend Next.js como consola operativa.
- Documentacion de arquitectura, seguridad, sandbox y runbook.
- Integraciones planeadas: browser automation, computer/filesystem actions, Gmail/OAuth, GoDaddy API.

## Riesgos A Controlar

| Riesgo | Mitigacion prevista |
|---|---|
| Acciones externas sin aprobacion | Guarded tools, approvals, audit events |
| Lectura/escritura fuera de rutas permitidas | Path validation, no symlinks, workspace roots |
| Browser automation contra sitios sensibles | Domain allow-list, session TTL, headed/vision flags, approval |
| Gmail con scopes excesivos | Read-only por defecto, send separado, OAuth token dir protegido |
| GoDaddy DNS/domain changes irreversibles | Preview/diff, rate limit, approval, dry-run |
| Deuda de calidad oculta | Ruff/mypy/pytest/frontend build como puerta final |

## Errores Encontrados

| Error | Intentos | Resolucion |
|---|---:|---|
| Gmail MCP authorization browser hung | 1 | Marcado como no bloqueante; no repetir ahora. Continuar con API/OAuth propio del proyecto |
| Ruff baseline failed in config.py | 1 | Pendiente corregir linea larga y SIM102 |
| Root folder is not a git repository | 1 | Trabajar con trazabilidad en archivos de plan; no usar operaciones Git destructivas |

## Resultado De Verificacion

| Check | Resultado |
|---|---|
| Backend pytest completo | 154 passed, 1 skipped, 19 deselected |
| Backend Ruff check | pass |
| Backend Ruff format check | pass |
| Backend mypy | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 25 - Roadmap asistente personal completo

Creado `docs/PERSONAL_ASSISTANT_ROADMAP.md` con matriz de estado y brechas:

- memoria personal temporal/semantica;
- correo multi-cuenta;
- grounding multi-provider;
- navegacion completa;
- agenda/tareas/recordatorios;
- notas personales;
- audio/voz;
- YouTube/video;
- MCP/tools/skills externos;
- IDE/repo agent workflow.

El documento tambien fija el criterio de aceptacion global: flags de config,
providers fake, tests, redaccion, auditoria, docs y degradacion `blocked` cuando
faltan credenciales.

## Fase 26 - Mail multicuenta personal con aprobacion humana

### Objetivo

Implementar el primer corte operativo del asistente personal de correo:

- leer GoDaddy IMAP para `INBOX` y spam/junk;
- leer Gmail label `TODOS` cuando el OAuth existente este habilitado;
- consolidar mensajes en Postgres;
- clasificar importancia de forma conservadora;
- generar propuestas de respuesta como texto, nunca como borrador;
- enviar exclusivamente desde la cuenta GoDaddy configurada y solo tras aprobacion humana.

### Criterios De Aceptacion

- Nuevas tablas `mail_accounts`, `mail_messages`, `mail_send_logs` con deduplicacion por cuenta/carpeta/uid.
- Settings `MAIL_*` y GoDaddy IMAP/SMTP en `.env` local sin documentar secretos.
- API autenticada para status, sync manual, listar mensajes, ver detalle, editar propuesta, ignorar y aprobar envio.
- Worker Celery periodico opcional para sync.
- Politica inicial: `MAIL_REQUIRE_APPROVAL_FOR_SEND=true`; no auto-send.
- Tests/ruff/mypy backend pasan o quedan fallas diagnosticadas.

### Fuera Del Primer Corte

- Calendar, ElevenLabs, Notion vector sync y frontend avanzado quedan para el siguiente bloque.
- Gmail send no se implementa: todo envio sale por GoDaddy SMTP.

### Resultado

- Modelos/migracion `mail_*`, paquete `cognitive_os.mail`, endpoints `/mail/*`,
  worker `cognitive_os.sync_personal_mail` en queue `mail`, vista `Mail` y smoke
  real GoDaddy IMAP con 25 mensajes insertados.
- Envio por SMTP GoDaddy solo via `/mail/messages/{id}/approve-send`.

## Fase 27 - Normalización documental 2026-05-14

### Objetivo

Actualizar todos los Markdown activos para que una persona nueva entienda el
estado real del proyecto: funcionamiento, arquitectura, guías de uso, variables,
mail personal, runtime DeepSeek V4 Pro, Weaviate 1.29.0, Kimi WebBridge,
ejecutables de escritorio, 89 endpoints propios y 17 vistas frontend (Chat, Dashboard, Settings, Approvals, Memory, Jobs, Sandbox, Documents, DocumentAnalysis, Configuration, Mail, LangSmith, Agents, Skills, Health, Audit, Assist).

### Criterios De Aceptacion

- No quedan afirmaciones vivas en docs de producto con conteos antiguos de
  endpoints/vistas, modelos OpenAI antiguos como runtime local, versiones
  antiguas de Weaviate ni mail Gmail-only.
- `COGNITIVE_OS_GUIDE.md` explica `/mail/*`, queue `mail`, `MAIL_*`, flujo de
  aprobación y brechas actuales.
- `frontend/README.md`, `scripts/README.md`, `ACCEPTANCE_CHECKLIST.md`,
  `SECURITY.md`, `OPERATOR_VARIABLE_CHECKLIST.md` y docs DeepAgents/OpenHarness
  reflejan estado 2026-05-14.

## Fase 28 - Revisión integral y optimización comercial

### Objetivo

Releer el proyecto completo desde cero, detectar errores, fragilidades,
incoherencias UX/backend, zonas propensas a fallar y mejoras necesarias para
elevarlo a producto comercial operable como sala de máquinas real.

### Criterios De Aceptacion Iniciales

- Inventario actualizado de arquitectura, endpoints, vistas, settings, workers y
  datos persistidos.
- Plan de mejora priorizado por severidad, riesgo y retorno comercial.
- Ejecución autónoma de cambios seguros sin tocar secretos ni datos productivos.
- Cualquier variable faltante queda listada como pendiente accionable, no como
  bloqueo.
- QA final documentado con comandos reales.

### Resultado parcial 2026-05-14

Auditoría desde cero ejecutada con subagentes de arquitectura, backend, frontend,
seguridad y tests. P0/P1 aplicados:

- **Secret hygiene**: `opencode.json` y wrappers `.opencode/bin/*.sh` usan
  `{env:VAR}` sin fallbacks secretos; contraseña OpenChamber retirada del Markdown;
  `.gitignore` reforzado; reglas bash `cat/find/rg/grep *` pasan a `ask` y se
  añaden denies adicionales.
- **Backend mail**: nuevos `MAIL_IMAP_TIMEOUT_SECONDS` / `MAIL_SMTP_TIMEOUT_SECONDS`,
  errores SMTP/IMAP redactados por tipo, estado `pending_send` antes de enviar.
- **Backend `/config/public`**: ampliado con flags no sensibles de Action Plane,
  mail, GoDaddy, OpenHarness, LangSmith, Telegram, browser y documentos.
- **Backend Gmail status**: ya no expone `token_path` / `token_dir`.
- **Frontend**: contratos alineados (`pending_send`, `ActionType`, `MailSendResult`);
  JWT en sesión React (no `localStorage`); polling con `AbortController`;
  `ConfigurationView` con grupos sala-de-máquinas; nueva `AssistView` cubre
  `/assist/tasks` y `/assist/notes`.
- **Tests**: nuevos `test_mail_api.py` (7 casos), `test_mail_clients.py` (timeouts),
  contract `/config/public` no-secret y Gmail status sin paths locales.
- **Scripts**: `verify_operator_ready.sh` ahora incluye `mypy src` y
  frontend `npm run lint && npm run build`; `scripts/dev_worker.sh` corregido para
  escuchar la queue `mail`.

QA final: `uv run pytest -m 'not integration and not slow'` → **341 passed,
1 skipped, 20 deselected**; `ruff check`, `ruff format --check`, `mypy src`,
`npm run lint`, `npm run build`, `git diff --check` todo verde.

### Pendiente comercial sin bloquear (variables/condiciones)

- Auth/RBAC comercial real (OIDC/OAuth, refresh tokens, sesiones, MFA).
- Cifrado de `payload_executable` en `ActionRequest`.
- Persistencia durable del Research Orchestrator (DB + Celery) en vez de in-memory.
- Bind privado de Postgres/Weaviate/Neo4j en `infra/docker-compose.yml`
  (requiere confirmación del operador).
- Variables/credenciales por completar en `.env.local` cuando el operador vuelva:
  `EXA_API_KEY`, `TAVILY_API_KEY`, `BRAVE_API_KEY`, `BRAVE_ANSWER_API_KEY`,
  `BRAVE_SEARCH_API_KEY`, `BRAVE_FREE_API_KEY`, `HF_TOKEN`, `CONTEXT7_API_KEY`,
  `LANGSMITH_API_KEY`, `LANGSMITH_ENDPOINT`, `SUPERMEMORY_API_KEY`,
  `SUPERMEMORY_PROJECT`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `NEO4J_DATABASE`.
- Rotar cualquier token previamente inline en `opencode.json` y wrappers.

## Fase 24 - Inventario local de archivos Windows/Linux

### Piensa 2 Veces (Fase 24)

`computer_organize` ya podia mover archivos aprobados, pero el agente aun no
tenia un mapa seguro del filesystem. Para ser asistente personal no basta con
ordenar: necesita registrar que existe, cuanto pesa, cuando cambio y como se
clasifica cada archivo, sin leer secretos ni recorrer todo el computador sin
permiso.

### Accion Elegida

- Nuevo `ComputerInventoryRequest` y `ComputerInventoryResult`.
- Nuevo endpoint `POST /actions/computer/inventory`.
- `ComputerActionService.build_inventory`:
  - exige `ENABLE_COMPUTER_ACTIONS=true`;
  - valida `root_path` dentro de `COMPUTER_ALLOWED_ROOTS`;
  - no sigue symlinks;
  - omite hidden files por defecto;
  - salta rutas sensibles (`.env`, `.ssh`, `.git`, `secret`, `token`,
    `password`, etc.);
  - respeta `max_files`;
  - opcionalmente calcula sha256;
  - escribe un reporte JSON en `LOCAL_STORAGE_DIR/file_inventory/`.

### Evaluacion Real Fase 24

| Check | Resultado |
|---|---|
| Backend pytest completo | 298 passed, 1 skipped, 19 deselected |
| Backend pytest enfocado inventory/actions | 43 passed |
| Backend Ruff check | pass |
| Backend Ruff format check | pass |
| Backend mypy | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 23 - Restore scripts operativos

### Piensa 2 Veces (Fase 23)

El proyecto ya podia crear backups con `sha256`, pero el restore real estaba
solo documentado como comandos manuales. Para operacion comercial eso es fragil:
un operador puede equivocarse de comando, olvidar checksum o sobreescribir
storage sin copia previa.

### Accion Elegida

- Agregar scripts idempotentes/conservadores:
  - `scripts/restore_postgres.sh`
  - `scripts/restore_neo4j.sh`
  - `scripts/restore_storage.sh`
- Todos exigen `CONFIRM_RESTORE=YES`.
- Todos verifican `.sha256` cuando existe.
- `restore_storage.sh` mueve el storage actual a
  `storage.pre_restore_TIMESTAMP` antes de extraer.
- Tests verifican sintaxis shell, confirmacion obligatoria, checksum y copia de
  seguridad.

### Evaluacion Real Fase 23

| Check | Resultado |
|---|---|
| Backend pytest completo | 292 passed, 1 skipped, 19 deselected |
| Backend pytest enfocado restore scripts | 4 passed |
| Backend Ruff check | pass |
| Backend Ruff format check | pass |
| Backend mypy | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 22 - GoDaddy DNS executor seguro

### Piensa 2 Veces (Fase 22)

GoDaddy tenia preview y `ActionRequest`, pero `_execute` no podia aplicar el
cambio. Eso dejaba el sistema en una zona intermedia: parecia accionable, pero
terminaba en `No executor is enabled`. La solucion no podia ser "ejecutar DNS"
sin mas, porque DNS es una accion externa de alto impacto.

La accion correcta es un executor con cuatro frenos:

- `GODADDY_ENABLED=true`;
- `GODADDY_DNS_DRY_RUN_ONLY=false`;
- dominio incluido en `GODADDY_ALLOWED_DOMAINS`;
- si la base URL es produccion (`https://api.godaddy.com`), exigir tambien
  `GODADDY_ALLOW_PRODUCTION_WRITES=true`.

### Accion Elegida

- `GoDaddyActionService.preview_dns_change` ahora distingue dry-run vs
  executable y valida:
  - dominio;
  - nombre de record;
  - prioridad requerida para MX/SRV;
  - allow-list de dominios para writes reales;
  - bloqueo extra de produccion.
- Nuevo `GoDaddyDnsExecutionResult`.
- Nuevo `GoDaddyActionService.execute_dns_change` que llama
  `PATCH /v1/domains/{domain}/records` con payload de un record aprobado.
- `ActionRequestService.create_godaddy_dns_change_request` ahora persiste
  `payload_executable`, crea aprobacion/job cuando el cambio es ejecutable y
  deja dry-run como `previewed`.
- `_execute` ya despacha `godaddy_dns_change` al executor real.

### Evaluacion Real Fase 22

| Check | Resultado |
|---|---|
| Backend pytest completo | 288 passed, 1 skipped, 19 deselected |
| Backend pytest enfocado actions | 37 passed |
| Backend Ruff check | pass |
| Backend Ruff format check | pass |
| Backend mypy | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 21 - Gmail read-only real reader

### Piensa 2 Veces (Fase 21)

El digest Gmail estaba bien modelado en seguridad, pero dependia de un reader
inyectado en tests. En produccion devolvia `No Gmail reader configured`, justo
en una zona que el usuario pidio: que el agente pueda revisar correos sin que
el flujo OAuth en navegador deje la sesion colgada.

No conviene implementar envio ni drafts reales todavia. La accion correcta es
activar lectura real read-only usando el `token.json` estandar de Google,
manteniendo:

- scope minimo `gmail.readonly`;
- sin envio;
- sin drafts reales;
- errores redactados;
- propuesta de respuestas solo como preview con aprobacion.

### Accion Elegida

- Nuevo `GmailRestReader` en `actions/gmail_digest.py`:
  - lee `GMAIL_TOKEN_DIR/token.json`;
  - refresca token si expiro y hay `refresh_token`;
  - consulta Gmail REST (`users/me/messages`) con `httpx`;
  - normaliza headers `From`, `Subject`, `Date`, labels, snippet y thread.
- `get_gmail_digest_reader()` ahora usa el reader real cuando Gmail read esta
  habilitado y no hay fake inyectado por tests.
- `GmailActionService.status()` reporta `token_path`, `token_present` y
  disponibilidad de `google-auth`.
- `GmailDigestService` convierte fallos del reader en `blocked`, no en 500, y
  redacta tokens en razones de error.
- Tests nuevos con cliente HTTP y credenciales fake, sin red ni OAuth real.

### Evaluacion Real Fase 21

| Check | Resultado |
|---|---|
| Backend pytest completo | 284 passed, 1 skipped, 19 deselected |
| Backend pytest enfocado Gmail/actions | 15 passed |
| Backend Ruff check | pass |
| Backend Ruff format check | pass |
| Backend mypy | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 19 - Office writers extendidos

### Piensa 2 Veces (Fase 19)

El generador de documentos ya era seguro para rutas y tamano, pero producia
artefactos muy basicos: DOCX solo con parrafos, XLSX sin formulas explicitas
y PPTX solo con bullets. Para acercarlo a un producto comercial, habia que
subir expresividad sin abrir de nuevo riesgos como formula injection o lectura
de archivos arbitrarios.

La decision fue mantener retrocompatibilidad total y agregar capacidades por
campos explicitos:

- DOCX: tablas e imagenes, pero las imagenes solo pueden venir desde
  `DOCUMENT_ASSET_ROOTS`.
- XLSX: formulas reales solo por `SpreadsheetFormula`; cualquier string que
  empiece con `=/+/-/@` sigue neutralizado como texto.
- PPTX: layouts `title`, `bullets`, `two_column` y `quote`.

### Accion Elegida

- Ampliar `DocumentGenerateRequest` con `DocumentTable`, `DocumentImage`,
  `SpreadsheetFormula` y layouts extendidos de `SlideContent`.
- Agregar `DOCUMENT_ASSET_ROOTS` para permitir imagenes solo desde raices
  declaradas.
- Mejorar escritores:
  - DOCX escribe tablas con header bold e imagenes con caption.
  - XLSX crea tablas de Excel, congela headers, ajusta anchos y permite formulas
    explicitamente validadas.
  - PPTX crea layouts de dos columnas y cita/quote sin depender de templates
    externos.
- Tests que reabren los archivos generados con `python-docx`, `openpyxl` y
  `python-pptx`.

### Evaluacion Real Fase 19

| Check | Resultado |
|---|---|
| Backend pytest completo | 280 passed, 1 skipped, 19 deselected |
| Backend pytest enfocado Office/action | 39 passed |
| Backend Ruff check | pass |
| Backend Ruff format check | pass |
| Backend mypy | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Optimizacion 2026-05-12 (Composer)

### Accion ejecutada

- **Exa** integrado como cuarto proveedor del router web existente (`web_search.py`,
  `/config/public`).
- Memoria episodica persistida (**kind=`episodic`**) + endpoint autenticado y
  migracion Postgres.
- Docs de roadmap y checklist alineadas con estado real del grounding multi-provider.

### Evaluacion

| Check | Resultado |
|---|---|
| Backend pytest completo | 306 passed, 1 skipped, 19 deselected |
| Backend Ruff check | pass |
| Backend Ruff format check | pass |
| Backend mypy | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Resultado De Verificacion Final De Esta Fase

| Check | Resultado |
|---|---|
| Backend pytest completo | 154 passed, 1 skipped, 19 deselected |
| Backend Ruff check | pass |
| Backend Ruff format check | pass |
| Backend mypy | pass |
| Frontend lint | pass |
| Frontend build | pass |
| Busqueda de referencias obsoletas criticas | sin referencias activas fuera de bitacora |

## Decisiones Abiertas

- Si se versionara el proyecto, crear repo Git limpio desde `cognitive-os` excluyendo backups, storage, node_modules, .next y .venv.
- Gmail MCP de Codex queda pendiente por bloqueo de autorizacion; no es requisito para implementar Gmail en Cognitive OS.
- GoDaddy no tiene plugin disponible en esta sesion; se implementara via API propia y politicas.

## Markdown Canonicos

### Planificacion viva

- `task_plan.md`: fases, riesgos, decisiones y checks de esta intervencion.
- `findings.md`: hallazgos tecnicos y fuentes revisadas.
- `progress.md`: bitacora cronologica de cambios y verificaciones.

### Documentacion estable del proyecto

- `README.md`: entrada principal, arranque rapido y mapa de lectura.
- `docs/PROJECT_GUIDE.md`: explicacion simple y tecnica para entender el producto.
- `docs/README.md`: indice de documentacion.
- `docs/ACTION_PLANE.md`: modelo de browser, computador, Gmail y GoDaddy.
- `docs/ARCHITECTURE.md`: arquitectura tecnica.
- `docs/RUNBOOK.md`: operacion diaria.
- `docs/SECURITY.md`: controles de seguridad.

## Fase 8 - Diseno Antes De Actuar

### Pensamiento 1

El action plane actual valida y previsualiza bien, pero todavia no tiene una
unidad persistente de trabajo. Eso impide operar comercialmente porque no hay
historial formal de "solicitud de accion", resultado, error, aprobacion y job.

### Pensamiento 2

No conviene saltar directo a Gmail/GoDaddy/browser real. Primero se debe crear
el flujo comun: ActionRequest -> HumanApproval -> Job/Celery -> AuditEvent. El
executor real inicial debe ser local y testeable: `computer_organize`.

### Accion Elegida

Implementar tabla/modelo/migracion `action_requests`, servicio de action plane,
endpoints de crear/listar/ejecutar, worker Celery y pruebas. Mantener acciones
externas no-locales como `blocked` hasta tener ejecutores completos.

### Evaluacion Minima Posterior

- Tests unitarios de creacion y ejecucion con directorio temporal.
- Tests de API para crear request.
- Ruff, mypy y pytest enfocado.

### Resultado Fase 8

- Agregada tabla/modelo/migracion `action_requests` con estados, preview,
  resultado, payload redactado, approval/job links e indices operativos.
- Agregado `ActionRequestService` para crear, listar, obtener, encolar y ejecutar
  solicitudes.
- Agregado executor real inicial para `computer_organize`, apagado por defecto y
  limitado por `COMPUTER_ALLOWED_ROOTS`, dry-run, aprobacion y Celery.
- Agregados endpoints:
  - `POST /actions/computer/organize/request`
  - `GET /actions/requests`
  - `GET /actions/requests/{id}`
  - `POST /actions/requests/{id}/dispatch`
- El panel ahora intenta despachar automaticamente una `ActionRequest` aprobada
  y muestra solicitudes recientes en `Configuracion`.

### Evaluacion Real Fase 8

| Check | Resultado |
|---|---|
| Backend pytest completo | 159 passed, 1 skipped, 19 deselected |
| Backend pytest enfocado actions | 14 passed |
| Backend Ruff check | pass |
| Backend Ruff format check | pass |
| Backend mypy | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 9 - Unificacion del ciclo Action Request

### Pensamiento 1

Solo `computer_organize` tenia persistencia en `action_requests`. Browser, Gmail
y GoDaddy quedaban como previews efimeros: no eran auditables, no se podian
listar, ni se podia documentar historicamente que la operacion fue propuesta y
por que se bloqueo. Eso impide cualquier flujo operativo comercial donde el
equipo necesita ver "que solicito el agente y por que se rechazo o aprobo".

### Pensamiento 2

No es seguro habilitar executors reales hoy para esos tres (browser/Gmail/
GoDaddy) por falta de tokens, rate limits y rollback. La forma correcta es
persistir cada solicitud como `previewed` (si la politica la permite) o
`blocked` (si la politica la rechaza), guardar payload redactado, preview y
auditoria, y diferir la ejecucion hasta tener executor seguro por proveedor.

### Accion Elegida

- Refactor de `ActionRequestService` con un helper compartido
  `_persist_preview_request`.
- Tres nuevas creaciones: `create_browser_navigation_request`,
  `create_gmail_query_request`, `create_godaddy_dns_change_request`.
- Nueva operacion `cancel_action_request` con transicion segura: bloquea
  cancelar mientras `running`, ignora estados finales, marca job asociado y
  registra `AuditEvent`.
- `list_action_requests` ahora acepta filtros `action_type` y `status`.
- Tres nuevos endpoints `POST /actions/{browser|gmail|godaddy}/.../request`,
  un `POST /actions/requests/{id}/cancel` y filtros sobre `GET /actions/requests`.

### Evaluacion Real Fase 9

| Check | Resultado |
|---|---|
| Backend pytest completo | 165 passed, 1 skipped, 19 deselected |
| Backend pytest enfocado actions | 20 passed |
| Backend Ruff check | pass |
| Backend Ruff format check | pass |
| Backend mypy | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 10 - Generacion de documentos (DOCX/XLSX/PPTX)

### Piensa 2 Veces (Fase 10)

El usuario pide redactar Word, Excel y PowerPoint sin abrir la puerta a
acciones de mayor riesgo (browser real con perfil, envio de email, DNS real).
Generar documentos es un punto util y de bajo radio porque solo escribe en
una carpeta allow-listed, no llama a la red, no usa credenciales y se puede
auditar facil.

Hay dos riesgos reales: (a) escribir fuera de la allow-list por una ruta
maliciosa (`..`, absoluta, suffix incorrecto); (b) generar archivos enormes
que llenen el disco. Ambos se cubren con validacion previa y tope post-write
(`DOCUMENT_MAX_SIZE_BYTES`).

### Accion Elegida

- Nuevo `DocumentActionService` con `status`/`build_preview`/`execute` para
  DOCX/XLSX/PPTX.
- Nuevo `action_type='document_generate'` integrado al ciclo persistente
  existente: preview -> ActionRequest pending_approval -> HumanApproval ->
  Celery -> AuditEvent.
- Tres endpoints publicos bajo JWT: `status`, `preview`, `request`.
- Settings: `ENABLE_DOCUMENT_GENERATION`, `DOCUMENT_OUTPUT_ROOT`,
  `DOCUMENT_MAX_SIZE_BYTES`. Migracion Alembic extendiendo el check
  constraint del `action_type`.

### Evaluacion Real Fase 10

| Check | Resultado |
|---|---|
| Backend pytest completo | 172 passed, 1 skipped, 19 deselected |
| Backend pytest enfocado actions | 27 passed |
| Backend Ruff check (src tests) | pass |
| Backend Ruff format check | pass |
| Backend mypy --strict | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 11 - Browser headless preview (Playwright opt-in)

### Piensa 2 Veces (Fase 11)

El usuario pide navegacion real (headless + vision + perfil con credenciales).
Saltar directo a vision o login persistente es riesgoso: requiere binarios de
Playwright instalados, perfiles con cookies reales y consentimiento humano por
sitio. El paso seguro y util ahora es ofrecer un `browser_preview` headless,
sin cookies persistidas, contra dominios allow-listed, que devuelve titulo y
captura limitada de tamano.

Hay dos riesgos: (a) instalar Playwright requiere descarga de Chromium y red,
no procede ejecutar `playwright install` automaticamente; (b) las pruebas no
deben depender de un navegador real. Ambos se cubren con un **provider
inyectable** (`BrowserPreviewProvider` Protocol) y un default que verifica
`find_spec("playwright")` y bloquea con razon clara cuando falta.

### Accion Elegida

- Nuevo `BrowserPreviewService` con `validate`/`execute` y provider factory.
- Default `PlaywrightBrowserPreviewProvider` (sync_playwright, headless,
  domcontentloaded/networkidle, `page.title`, `page.screenshot`).
- Nuevo `action_type='browser_preview'` integrado al ciclo persistente
  existente: preview -> ActionRequest pending_approval -> HumanApproval ->
  Celery -> AuditEvent.
- Tests inyectan FakeProvider/HugeProvider: 6 casos cubren disabled,
  fuera de allow-list, provider missing, ejecucion ok con archivo, tope de
  bytes (file se borra), y endpoint POST.
- Settings: `BROWSER_SCREENSHOT_DIR`, `BROWSER_NAVIGATION_TIMEOUT_MS`,
  `BROWSER_SCREENSHOT_MAX_BYTES`. Migracion Alembic
  `202605120002_action_requests_browser_preview.py` extiende el check
  constraint del `action_type`.
- Nuevo endpoint `POST /actions/browser/preview/request`.

### Evaluacion Real Fase 11

| Check | Resultado |
|---|---|
| Backend pytest completo | 178 passed, 1 skipped, 19 deselected |
| Backend pytest enfocado actions | 33 passed |
| Backend Ruff check (src tests) | pass |
| Backend Ruff format check | pass |
| Backend mypy --strict | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 12 - Research Orchestrator sobre deepagents

### Piensa 2 Veces (Fase 12)

El usuario pidio "investigar durante el tiempo que yo le asigne generando
tareas a varios agentes, respondiendo de manera incremental, al final
analizando la respuesta, recibiendo una calificacion por un nodo dedicado".
El repo ya integra `deepagents` con `run_research_deepagent` (politicas
estrictas, skills, memoria, workspace, citas). Construir un orquestador
propio que reescriba ese trabajo duplicaria logica y romperia la auditoria.

Decision: la Fase 12 NO sustituye deepagents. Es una **capa orquestadora**
encima: planner -> N deepagents en paralelo -> synthesizer -> scorer, con
presupuesto de tiempo, eventos incrementales por nodo y cancelacion segura.

### Accion Elegida

- Nuevo modulo `agents/research_orchestrator.py` con `ResearchOrchestrator`,
  Protocols `PlannerProvider`/`ResearcherProvider`/`SynthesizerProvider`/
  `ScorerProvider`, defaults heuristicos auditables (`HeuristicPlanner`,
  `DeepAgentResearcher` que delega a `run_research_deepagent`,
  `HeuristicSynthesizer`, `HeuristicScorer` con rubrica explicita).
- Cancelacion via `threading.Event`, deadline global con
  `concurrent.futures.wait(timeout=...)` y `executor.shutdown(wait=False,
  cancel_futures=True)` para no bloquear el thread principal.
- Streaming incremental: cada nodo emite `ResearchEvent` a una cola
  por run (consumible por SSE en una fase posterior).
- Settings: `ENABLE_RESEARCH_ORCHESTRATOR`, `RESEARCH_MAX_PARALLEL_WORKERS`,
  `RESEARCH_MAX_TIME_BUDGET_SECONDS`, `RESEARCH_MAX_SUBTASKS`.
- Endpoints nuevos:
  - `POST /research/runs` arranca el run.
  - `GET /research/runs` lista.
  - `GET /research/runs/{id}` detalle.
  - `POST /research/runs/{id}/cancel` cancelacion segura.
- Store in-memory (v1). Persistencia DB queda para una fase futura.
- 11 tests con providers fake (Planner/Researcher/Synth/Scorer/SlowResearcher
  para timeout y cancel), sin LLMs ni red.

### Evaluacion Real Fase 12

| Check | Resultado |
|---|---|
| Backend pytest completo | 189 passed, 1 skipped, 19 deselected |
| Backend pytest enfocado research orchestrator | 11 passed |
| Backend Ruff check (src tests) | pass |
| Backend Ruff format --check | pass |
| Backend mypy --strict | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 13 - Gmail Daily Digest read-only

### Piensa 2 Veces (Fase 13)

El usuario quiere un resumen diario de su Gmail sin riesgo de envio accidental.
La regla central es: leer redactado, agrupar por remitente, proponer borradores
de respuesta pero **nunca crearlos** en Gmail. El executor real queda fuera de
Fase 13: el digest es preview-only y se inyecta un `GmailReader` Protocol para
que las pruebas no necesiten OAuth.

### Accion Elegida

- Nuevo modulo `actions/gmail_digest.py` con `GmailDigestService`,
  `GmailReader` Protocol y `FakeGmailReader` para tests.
- Redaccion de direcciones (`local` -> `l*l@dominio`), agrupacion por remitente,
  ordenamiento por fecha, propuestas de respuesta `requires_approval=True`
  sin tocar Gmail.
- Schemas: `GmailDigestRequest`, `GmailDigestPreview`, `GmailDigestMessage`,
  `GmailDigestSender`, `GmailDigestProposedDraft`.
- Endpoint nuevo `POST /actions/gmail/digest/preview` bajo JWT, con singleton
  `_gmail_digest_reader` inyectable via monkeypatch para tests.
- 10 tests nuevos cubriendo: read disabled, sin reader, redaccion, filtrado por
  ventana, dedup por remitente, propuestas con `requires_approval=True`,
  warnings cuando la ventana esta vacia, parametros pasados al reader,
  endpoint blocked/ok y autenticacion obligatoria.

### Evaluacion Real Fase 13

| Check | Resultado |
|---|---|
| Backend pytest completo | 199 passed, 1 skipped, 19 deselected |
| Backend pytest enfocado gmail digest | 10 passed |
| Backend Ruff check (src tests) | pass |
| Backend Ruff format --check | pass |
| Backend mypy --strict | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 14 - Research Orchestrator async + SSE streaming

### Piensa 2 Veces (Fase 14)

Bug encontrado durante la auditoria: `ResearchOrchestrator.start_run` invocaba
`_execute` de forma sincrona. Esto bloqueaba `POST /research/runs` hasta por
`time_budget_seconds` (clamped a 300s por defecto, hasta 3600s posible) y dejaba
inutil al endpoint de cancelacion (`POST /research/runs/{id}/cancel`) porque
el cliente no podia llamarlo mientras esperaba el POST. La cola de eventos
existia pero nadie podia consumirla en tiempo real.

### Accion Elegida

- `start_run` ahora lanza `_execute` en un daemon thread y retorna de inmediato
  con `status` no-terminal. `ResearchRun` gana `done_flag: threading.Event` y
  `executor_thread: threading.Thread | None`.
- Nuevo metodo `wait_for_run(run_id, *, timeout=60.0)` para tests y callers
  sincronicos.
- Nuevo endpoint SSE `GET /research/runs/{run_id}/events` que emite todos los
  `ResearchEvent` historicos + nuevos hasta estado terminal, mas un evento
  `snapshot` final con el `ResearchRunView` completo y un `done`.
- Tests existentes actualizados a `start_run` + `wait_for_run`.
- 5 tests nuevos:
  - `wait_for_run` retorna `None` para id desconocido.
  - `start_run` retorna < 200 ms (no-bloqueante) y deja la run en estado no-terminal.
  - SSE streaming emite eventos en orden con `snapshot` + `done` al final.
  - SSE 404 para run inexistente.
  - SSE requiere JWT.

### Evaluacion Real Fase 14

| Check | Resultado |
|---|---|
| Backend pytest completo | 204 passed, 1 skipped, 19 deselected |
| Backend pytest enfocado research orchestrator | 16 passed |
| Backend Ruff check (src tests) | pass |
| Backend Ruff format --check | pass |
| Backend mypy --strict | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 18 - DeepAgents 0.6.x + subagents/memory

### Piensa 2 Veces (Fase 18)

El avance de Claude dejo Fases 15, 16, 17 y 20 completas, pero no habia
ejecutado la Fase 18: `backend/pyproject.toml` seguia fijado a
`deepagents>=0.5.5,<0.6.0`. PyPI oficial muestra `deepagents 0.6.1` publicado
el 12 de mayo de 2026, y la documentacion oficial confirma subagents,
`write_todos`, task tool, backends, memory y async subagents.

No conviene activar async subagents remotos a ciegas porque requieren Agent
Protocol/LangSmith Deployment o un servidor compatible. La accion correcta es:
upgrade seguro de dependencia, adaptar la factory local con introspeccion para
pasar `subagents`/`memory` solo si el SDK lo soporta, preservar permisos y
aprobaciones, y deduplicar memoria consolidada para evitar inflacion.

### Accion Elegida

- Cambiar dependencia a `deepagents>=0.6.1,<0.7.0` y regenerar `uv.lock`.
- Inspeccionar la firma real instalada de `create_deep_agent`.
- Agregar builders de subagents locales declarativos para research/document
  analysis sin habilitar herramientas peligrosas.
- Mantener `interrupt_on` para `execute`, shell, browser, email, social, delete
  y edicion de proyecto.
- Mejorar memoria: paths seguros + dedup de propuestas por contenido normalizado.
- Tests de compatibilidad con fake `create_deep_agent`, sin LLM ni red.

### Evaluacion Minima Posterior

- Tests enfocados de factory, memory consolidation y deepagents service.
- Suite backend completa.
- Ruff check + format, mypy, frontend lint/build.

### Resultado Fase 18

- Dependencia actualizada a `deepagents>=0.6.1,<0.7.0`; `uv.lock` resuelto con
  `deepagents 0.6.1`, `langchain 1.3.0`, `langgraph 1.2.0`, `langsmith 0.8.3`.
- `create_controlled_deep_agent` ahora detecta la firma real de
  `create_deep_agent` 0.6.1 y pasa `subagents`/`memory` solo si estan soportados.
- Nuevo flag `DEEPAGENTS_ENABLE_SUBAGENTS=true`.
- Subagents locales seguros:
  - Research: `local-rag-researcher`, `citation-auditor`, `web-researcher`
    solo cuando `web_allowed` + policy web.
  - Document analysis: `evidence-matrix-specialist`, `timeline-specialist`,
    `contradiction-reviewer`.
- Startup memory se escribe dentro del workspace como
  `./.cognitive_os/AGENTS.md` y tambien queda resumida en el system prompt por
  compatibilidad.
- `DeepAgentMemoryConsolidator` deduplica propuestas por contenido normalizado,
  tanto dentro de una corrida como contra propuestas/memorias existentes.

### Evaluacion Real Fase 18

| Check | Resultado |
|---|---|
| Backend pytest completo | 274 passed, 1 skipped, 19 deselected |
| Backend focused deepagents | 34 passed |
| Backend Ruff check | pass |
| Backend Ruff format check | pass |
| Backend mypy | pass |
| Frontend lint | pass |
| Frontend build | pass |

## Fase 25 — Asistente personal completo (memoria, correos, agenda, notas, voz, video)

### Objetivo

Cerrar las brechas para que Cognitive OS sea un asistente personal real,
controlable y auditable, sin acoplar runtime productivo dentro de OpenCode.
Cada capacidad nueva debe traer: flag de configuración, provider fake para
tests, redacción de secretos, auditoría, degradación `blocked` cuando faltan
credenciales, doc en `docs/`, y tests sin red.

### Subfases

#### 25.A — Mail unificado multi-cuenta (Gmail principal + GoDaddy/M365 Spam)

- Nuevo módulo `cognitive_os.actions.mail_unified`:
  - `MailAccountSpec(account_id, provider, mailbox, folders, scopes, redact_level)`.
  - Providers: `GmailRestReader` (ya existe, refactor a interfaz común) y
    `MicrosoftMailGraphReader` (nuevo) y/o `ImapReader` (nuevo, opt-in).
- Settings: `MAIL_ACCOUNTS_JSON` (lista declarativa) reemplazando el modelo
  monolítico de un solo `GMAIL_*`; mantener `GMAIL_*` como compat layer.
- `actions/mail_unified.py::run_account_digest(account_id, folders, lookback)`.
- Endpoints:
  - `GET /actions/mail/accounts` (status por cuenta).
  - `POST /actions/mail/digest/run` (por `account_id` y `folders`).
- Categorización + priorización (LLM con prompt determinístico):
  - Categoría: `personal | trabajo | newsletter | financiero | spam | otro`.
  - Importancia: `urgente | importante | informativo | ignorar`.
  - Output: lista de `MailItem(category, importance, summary, suggested_reply_text?)`.
- Propuestas de respuesta:
  - Siempre como texto en la salida del digest.
  - Si `GMAIL_SEND_ENABLED=true` y `MAIL_DRAFTS_ENABLED=true`, además crear
    `ActionRequest` con `action_type="mail_draft_create"`; el envío real queda
    detrás de aprobación humana posterior y `MAIL_SEND_ENABLED=true`.
- Scripts: `scripts/auth_gmail.py`, `scripts/auth_microsoft_mail.py` para
  generar `token.json` localmente, sin OAuth interactivo en el backend.
- Tests: providers fake, redacción de direcciones/secrets, categorización
  con LLM mock.

#### 25.B — YouTube watcher

- Nuevo `cognitive_os.actions.youtube`:
  - `YouTubeMetadataClient` (YouTube Data API v3 con `YOUTUBE_API_KEY`).
  - `YouTubeTranscriptClient` (`youtube-transcript-api`; fallback opcional
    `yt-dlp` + Whisper bajo `YOUTUBE_AUDIO_FALLBACK=true` y cap de duración).
  - `YouTubeSummaryService.summarize(video_id, lang?)`: devuelve título,
    capítulos detectados, resumen ejecutivo, key takeaways y citas
    `mm:ss` cuando hay transcript.
- Tool DeepAgents `summarize_youtube(url|video_id)` para que el agente la
  llame durante chats o desde Telegram.
- Cache en Postgres tabla `youtube_summaries` por `video_id + lang`.
- Endpoints: `GET /actions/youtube/status`, `POST /actions/youtube/summarize`.
- Tests: client fake, transcript fake, validación de URLs/IDs.

#### 25.C — Voz (STT/TTS)

- Nuevo `cognitive_os.voice`:
  - `stt.py`: provider `OpenAIWhisperSTT` (default) + `ElevenLabsSTT` opcional.
  - `tts.py`: provider `OpenAITTS` (default) + `ElevenLabsTTS` opcional.
- Settings: `VOICE_ENABLED`, `VOICE_STT_PROVIDER`, `VOICE_TTS_PROVIDER`,
  `VOICE_MAX_AUDIO_BYTES`, `VOICE_MAX_DURATION_SECONDS`,
  `VOICE_DEFAULT_LANGUAGE`.
- Endpoints: `POST /voice/transcribe` (multipart audio), `POST /voice/speak`.
- Tool DeepAgents `voice_speak(text)` con `interrupt_on=True` (acción
  externa con costo).
- Telegram: handler de audio mensajes → STT → procesamiento normal;
  comando `/voz` para responder con TTS.
- Tests: providers fake, cap de tamaño, redacción de texto transcrito.

#### 25.D — Agenda real (Google Calendar y CalDAV)

- Nuevo `cognitive_os.actions.calendar`:
  - `GoogleCalendarClient` (reusa OAuth Gmail si las cuentas coinciden).
  - `CalDAVClient` (alternativa para iCloud / Fastmail / etc.).
- Settings: `CALENDAR_PROVIDER=none|google|caldav`, allow-list de calendarios.
- Operaciones: list events por rango, sugerir slots libres, crear evento
  (preview + `ActionRequest` `calendar_event_create`).
- Integración con `PersonalTask`: cuando una tarea tiene `due_at`, ofrecer
  crear evento; cuando un evento se crea, indexar resumen en notas.
- Endpoints: `GET /actions/calendar/status`, `GET /calendar/events`,
  `POST /actions/calendar/events/preview`, `POST /actions/calendar/events/request`.
- Tests con provider fake.

#### 25.E — Notas semánticas

- Indexar `PersonalNote` automáticamente en Weaviate (`doc_type="note"`)
  al crear/actualizar; reindexar en background con Celery.
- Tool DeepAgents `search_notes(query, limit)` + `create_note(title, content, tags)`.
- Vínculo bidireccional `nota ↔ tarea ↔ memoria episódica` por columna
  `linked_ids` (uuid array).
- Opcional: sync a Markdown vault local en `LOCAL_STORAGE_DIR/notes_vault/`
  cuando `NOTES_MARKDOWN_VAULT_ENABLED=true`.
- Endpoints existentes ampliados con búsqueda semántica.

#### 25.F — Perfil de usuario + aprendizaje por feedback

- Nuevo `cognitive_os.memory.profile`:
  - `UserProfile(preferences, important_people, schedules, decisions,
    communication_style, tags)` persistido en Postgres.
  - Helpers `update_profile_from_correction(thread_id, correction_text)`
    que generan `DeepAgentMemoryProposal` con `kind="preference"`.
- Pipeline "feedback loop":
  - Cuando el usuario corrige una respuesta (botón "Eso está mal" o
    mensaje "no, en realidad…"), abrir proposal con la corrección.
  - `consolidate_all_deepagent_memory` ahora considera correcciones como
    señal positiva fuerte.
- Tagging por kind: `factual | preference | procedure | warning | task |
  episodic`. TTLs configurables (`MEMORY_TTL_DAILY_DAYS`,
  `MEMORY_TTL_WEEKLY_DAYS`, etc.).
- Tool DeepAgents `update_user_profile(field, value)` y `get_user_profile()`.

#### 25.G — Grafo "personal_assistant" en LangGraph

- Nuevo nodo/graph `personal_assistant` en `agents/graph.py`:
  - Router decide `mail | calendar | notes | research | voice | task_mgmt`.
  - Subagentes paralelos por capacidad.
  - Consolidador genera `DailyBriefing` (mail digest + agenda + tareas pendientes
    + alerts) que se publica en frontend + Telegram.
- Endpoint `POST /assist/briefing/run` (manual) + cron diario.

#### 25.H — Hardening de credenciales

- Reemplazar lectura plana de `.env` con `core.secrets.SecretStore`:
  - Por defecto: `.env` (compat).
  - Opt-in: `keyring` del SO o `sops`-encrypted dotenv.
- Auditar todos los `SecretStr` para que NUNCA aparezcan en logs/responses
  (ya cubierto en su mayoría, agregar tests de regresión).
- Operator scripts: `scripts/auth_gmail.py`, `scripts/auth_microsoft_mail.py`,
  `scripts/auth_google_calendar.py`, `scripts/check_credentials.sh`.

### Criterio de aceptación Fase 25

- Backend pytest verde con suite ampliada (objetivo: +50 tests sin red).
- Ruff + ruff format + mypy strict pasan.
- Frontend lint + build pasan.
- Operator checklist en `docs/OPERATOR_VARIABLE_CHECKLIST.md` actualizado.
- Documentación nueva: `docs/MAIL_UNIFIED.md`, `docs/YOUTUBE_SUMMARY.md`,
  `docs/VOICE_IO.md`, `docs/CALENDAR.md`, `docs/USER_PROFILE.md`.
- Demo manual: con credenciales reales, `POST /assist/briefing/run` produce
  un briefing diario completo (mail + agenda + tareas + resumen ejecutivo)
  sin errores y con citas/acciones aprobables.

### Decisiones que bloquean implementación

- **GD-mail provider** (IMAP vs M365 Graph).
- **Gmail send scope** (compose vs solo texto).
- **Agenda provider** (Google vs CalDAV).
- **STT/TTS provider** (OpenAI vs ElevenLabs).
- **Notas markdown vault** sí/no.
- **Multi-cuenta**: 1 sola por ahora o N desde el inicio.

Ver `findings.md` "Decisiones pendientes" para detalle.

## Fase 31 - Google Maps y Drive operables como capa comercial

### Objetivo

Cerrar la brecha entre las integraciones Google ya presentes y una experiencia
operable de grado comercial: rutas con tráfico/link de Google Maps, Google Drive
como carpeta de entregables, visibilidad en sala de máquinas, y escrituras
Calendar/Drive bajo el ciclo persistente `ActionRequest` + aprobación humana.

### Criterios De Aceptacion

- Maps devuelve ruta con preferencia de tráfico para conducción, retraso estimado
  y link navegable a Google Maps sin exponer API keys.
- Drive puede asegurar una carpeta de entregables `Cognitive OS Deliverables` y
  subir archivos permitidos a esa carpeta bajo doble compuerta (`ENABLE_*_WRITE`
  + aprobación humana para el carril comercial).
- `/actions/capabilities` incluye `maps`, `google_calendar` y `google_drive`.
- `/config/public` expone sólo postura no sensible de Google.
- Calendar create y Drive upload pueden crear `ActionRequest` aprobables y
  ejecutables por Celery; las rutas directas existentes permanecen preview-only
  y rechazan `dry_run=false` para no rodear aprobación humana.
- Frontend tiene una vista operativa para Maps/Calendar/Drive y los tipos quedan
  alineados con el backend.
- Tests focalizados cubren providers fake, endpoints auth, contratos public config
  y ActionRequest de Calendar/Drive, sin red ni secretos.

### Resultado 2026-05-15

- Backend: Maps devuelve tráfico/link; Drive asegura carpeta de entregables;
  Calendar/Drive writes quedan promovidos a `ActionRequest` ejecutables tras
  aprobación humana.
- API: `/actions/capabilities` incluye `maps`, `google_calendar` y
  `google_drive`; `/config/public` expone solo postura no sensible.
- Frontend: `GoogleOpsView` añadida y conectada al dashboard/sidebar.
- Tests: `tests/test_actions.py` incluye lifecycle unitario de
  `calendar_create_event` y `drive_upload_file`; `uv run pytest tests/test_actions.py -q`
  pasa con 42 tests.
- QA amplio final: `uv run pytest -m 'not integration and not slow'` → **471 passed,
  1 skipped, 20 deselected**; `uv run ruff check .`; `uv run ruff format --check .`;
  `uv run mypy src`; `npm run lint`; `npm run build`; `git diff --check`, todo verde.

## Fase 32 - Hardening comercial seguridad/PWA/QA

### Objetivo

Cerrar hallazgos P0/P1 detectados tras Google operativo y elevar el cockpit a una
postura comercial segura por defecto: sin bypass de aprobación en Google writes,
infra local-only por defecto, errores sin secretos/rutas locales, reaper operativo,
PWA robusta y tests que fijen los contratos críticos.

### Criterios De Aceptacion

- `opencode.json` no contiene valores secretos inline para MCPs; usa `{env:VAR}`.
- `POST /actions/calendar/events/create`, `POST /actions/drive/files/upload` y
  `POST /actions/drive/folders/ensure` rechazan `dry_run=false` con `409`; el
  camino real queda en `/request` + `HumanApproval` + Celery + audit.
- Producción no arranca con `ENABLE_GOOGLE_CALENDAR_WRITE=true` o
  `ENABLE_GOOGLE_DRIVE_WRITE=true` si
  `REQUIRE_HUMAN_APPROVAL_FOR_EXTERNAL_ACTIONS=false`.
- OAuth/Drive/health no exponen rutas locales, `token.json` ni valores con forma
  de token en errores.
- `cognitive_os.reap_stuck_action_requests` está routeado a `maintenance` y
  agendado por Celery beat.
- Postgres, Redis, Weaviate HTTP/gRPC y Neo4j HTTP/Bolt publican sólo en
  `127.0.0.1` en Compose.
- PWA/Next incluye headers de seguridad, service worker versionado, APIs
  network-only, flujo de update y banner offline/install.
- Tests high-value cubren direct-write reject, producción Google, redacción,
  health degraded, Celery beat y assets frontend.

### Resultado 2026-05-15

- Seguridad: `EXA_API_KEY` en `opencode.json` quedó como `{env:EXA_API_KEY}`;
  el valor expuesto debe rotarse fuera de esta sesión.
- Backend: endpoints directos Google write quedaron preview-only; validación de
  producción exige aprobación humana; errores Google OAuth, Drive y health son
  redactados; health dashboard degrada componentes rotos sin abortar todo el
  dashboard.
- Workers: reaper de `ActionRequest` stuck queda en queue `maintenance` y beat
  `action-request-reaper` cada 10 minutos.
- Infra: `docker compose --env-file .env.example -f infra/docker-compose.yml config --quiet`
  pasa y muestra Postgres/Redis/Weaviate/Neo4j ligados a `127.0.0.1`.
- Frontend/PWA: `next.config.mjs` añade headers de seguridad y desactiva
  `X-Powered-By`; `sw.js` usa cache versionado, network-only para rutas API-like
  y `COGOS_SKIP_WAITING`; `PWA.tsx` muestra offline/update/install; `TopBar` suma
  atributos anti-autofill/accesibilidad.
- Tests nuevos/modificados: `test_frontend_static_assets.py`,
  `test_health_dashboard.py`, `test_celery_config.py`, `test_config.py`,
  `test_google_calendar.py`, `test_google_drive.py`, `test_google_oauth.py`.
- QA amplio: `uv run pytest -m 'not integration and not slow'` → **484 passed,
  1 skipped, 20 deselected**; `uv run ruff check .`; `uv run ruff format --check .`;
  `uv run mypy src`; `npm run lint`; `npm run build`, todo verde.

## Fase 34 - Reconciliacion operativa local

### Objetivo

Cerrar la brecha entre el codigo validado y el runtime local: aplicar migraciones
pendientes, asegurar que Docker corre con la postura loopback vigente y blindar
el baseline contra inclusion accidental de backups/snapshots o archivos locales.

### Resultado 2026-05-15

- Alembic local quedo en `202605150002 (head)`.
- Docker Compose fue reconciliado con la configuracion actual mediante `up -d`;
  Postgres, Redis, Weaviate y Neo4j quedaron healthy y publicados en `127.0.0.1`.
- `.gitignore` raiz ignora `cognitive-os-backup-*`, `cognitive-os-snapshot-*`,
  transcripciones recuperadas y `**/.claude/settings.local.json`.
- Verificacion final enfocada: `git diff --check` limpio, ignores criticos
  confirmados y tests de config/research/action payload encryption en verde
  (**32 passed**).

## Fase 35 - Baseline git seguro

### Objetivo

Crear el primer baseline versionado sin arrastrar secretos, backups, snapshots,
archivos locales o ruido de hooks.

### Resultado 2026-05-15

- Rama de trabajo: `codex/fase-34-baseline-hardening`.
- Todos los archivos versionables fueron staged con `.gitignore` activo.
- `detect-secrets` sobre archivos versionables quedo limpio (`results: {}`).
- `uvx pre-commit run --all-files` quedo verde, incluyendo `gitleaks`.
- Se corrigieron falsos positivos de fixtures de tests y se ajusto el umbral de
  lockfiles a 1024 KB para permitir `uv.lock`.

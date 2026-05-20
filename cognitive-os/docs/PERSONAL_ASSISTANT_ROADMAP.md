# Roadmap: Cognitive OS como asistente personal

> **Estado actual (2026-05-20, Fases 78-81 — plan de aprendizaje autónomo completo):** roadmap vivo, mayormente
> ejecutado. El correo multicuenta está implementado y verificado contra
> GoDaddy IMAP/SMTP real + Gmail label `TODOS`. La vista frontend
> `AssistView` cubre tareas/notas personales (`PersonalTask`/
> `PersonalNote`) con CRUD; `GoogleOpsView` opera Maps/Calendar/Drive.
> Telegram operativo (slash + conversacional). El asistente tiene acceso
> total al `/home` del operador (Fase 73b) + cliente MCP (Fase 73). La
> queue Celery `mail` está integrada en los launchers de escritorio.
> Calendar/Drive writes reales bajo `ActionRequest` + aprobación (o
> auto-approve reversible en `dedicated_local`). El **plan de aprendizaje
> autónomo** (Fases A-E) está cerrado: el agente aprende de cada
> interacción bajo el approval gate del operador. QA: **800 passed, 1
> skipped, 20 deselected** contra DB de test aislada;
> ruff/format/mypy/frontend verdes. La ruta
> `research` sigue fusionada con OpenHarness opcional y puede persistir runs
> en Postgres. Pendiente para
> "asistente personal absoluto": OAuth real Gmail/Calendar/Drive operados
> por el usuario en runtime, voice STT/TTS productiva en frontend, y los ítems Fase
> 29 operativos de credenciales/UX.

Este documento separa lo que ya funciona, lo que esta parcialmente listo y lo
que falta para que Cognitive OS sea un asistente personal operativo.

## Estado actual

| Area | Estado | Que ya existe |
|---|---|---|
| Memoria | Parcial fuerte | DeepAgents memory (propuestas, aprobacion, startup memory, dedup) + registros episodicos `kind=episodic` persistidos (`POST /deepagents/memory/episodic`) |
| Investigacion | Parcial fuerte | RAG local; web multi-provider; research orchestrator async + SSE; DeepAgents + subagents; **fusión opcional OpenHarness** (`prelude_merge` / `short_circuit`, ver `OPENHARNESS_FUSION.md`) |
| Navegador | Parcial fuerte | `browser_preview` y `browser_interactive` headless con screenshots + vision |
| Archivos locales | Parcial fuerte | Organizar carpetas aprobado + inventario read-only allow-listed |
| Mail multicuenta | Parcial fuerte | GoDaddy IMAP/SMTP, Gmail label `TODOS` soportado si OAuth activo, Postgres `mail_*`, propuestas escritas, envío aprobado desde GoDaddy |
| Google Ops | Parcial fuerte | Maps route/geocode read-only con tráfico/link; Calendar list/create bajo OAuth y `ActionRequest`; Drive list/get/folder/upload bajo OAuth, allow-list y aprobación |
| GoDaddy | Parcial | Preview + executor DNS seguro con dry-run/allow-list/aprobacion |
| Documentos Office | Parcial fuerte | DOCX/XLSX/PPTX con guardrails, tablas, imagenes, formulas y layouts |
| Telegram | Parcial | Bot existente; falta completar flujos proactivos/notificaciones personales |
| Backups/restore | Parcial fuerte | Backup scripts + restore scripts con confirmacion y checksum |
| Audio | Parcial | VoiceService ElevenLabs STT/TTS + endpoints; falta UX completa y Telegram audio in/out |
| YouTube/video | Pendiente | `YOUTUBE_API_KEY`; falta transcript/resumen/video vision |
| Agenda/tareas | Parcial fuerte | `PersonalTask` CRUD + reminders básicos; Google Calendar list/create operativo bajo OAuth y aprobación; falta scheduling/push proactivo completo |
| Notas personales | Parcial fuerte | `PersonalNote` CRUD + búsqueda semántica Weaviate; falta Notion sync/export/import |
| MCP/skills externos | Parcial | Skills DeepAgents core/user; falta import/adaptador de MCP/tools externos |
| IDE/programacion | Parcial | OpenShell sandbox + code-analysis skill; falta flujo IDE/repo agent end-to-end |

## Gaps principales

### 1. Memoria personal temporal y semantica

Necesario:

- Perfil del usuario: preferencias, tono, prioridades, personas importantes,
  cuentas, horarios, formas de decidir.
- Memoria episodica: que hizo el agente, cuando, con que resultado y que aprendio
  (**base**: API `POST /deepagents/memory/episodic`, kind `episodic` visible en prompts).
- Memoria temporal: hoy, esta semana, este mes; expiracion y relevancia.
- Correcciones del usuario como aprendizaje aprobado.
- Separar memoria factual, preferencia, procedimiento, advertencia y tarea.

Regla: memoria sensible requiere aprobacion o redaccion; no guardar secretos.

### 2. Correo personal multi-cuenta

Implementado primer corte:

- GoDaddy IMAP para carpetas configuradas (`INBOX`, spam/junk/bulk).
- Gmail label `TODOS` soportado por `GmailLabelReader` cuando OAuth está activo.
- Tablas `mail_accounts`, `mail_messages`, `mail_send_logs`.
- Endpoint `/mail/sync` + worker `cognitive_os.sync_personal_mail` en queue `mail`.
- Propuestas de respuesta como texto, no drafts.
- Envío por SMTP GoDaddy solo vía `/mail/messages/{id}/approve-send`.

Falta:

- Mejor clasificación LLM sobre DeepSeek V4 Pro en vez de heurística inicial.
- Telegram inline buttons para aprobar/editar/ignorar.
- Acciones de archivar, etiquetar, marcar spam/no-spam.

### 3. Grounding web multi-provider

Implementado como `MultiProviderWebSearchClient`: Tavily, Brave Search,
Perplexity y Exa configurables por variables de entorno, dedup por URL canonica
y ranking favoreciendo URLs devueltas por varios proveedores. Opcionalmente el
pipeline reindexa resultados como `doc_type=web` cuando hay Weaviate y
embeddings.

Falta (roadmap avanzado):

- Paneles y telemetricas por proveedor (coste, errores, latencias).
- Cross-check sintetico automatizado cuando varios providers devuelven extractos discrepantes sobre el mismo tema.
- Presupuestos/runbooks de grounding largos (jobs dedicados más allá del research orchestrator).

### 4. Navegacion completa

Ya hay base headless/vision. Falta:

- Camoufox real como provider alternativo.
- Revalidacion post-redirect en cada navigation.
- Estado de pagina observable por DOM + screenshot.
- Recorder de acciones para replay.
- Descargas allow-listed.
- Formularios complejos y login solo con aprobacion/secret manager.

### 5. Agenda, tareas y recordatorios

Necesario:

- Modelo propio de tareas: titulo, estado, prioridad, fecha, recordatorio,
  origen, tags, notas.
- Notificador: Telegram primero, luego email/calendario.
- Scheduler/automation: digest diario, revision semanal, follow-ups.
- Integración opcional Google Calendar ya existe para listar/crear eventos bajo
  OAuth y aprobación; falta Outlook/CalDAV y recordatorios proactivos completos.

### 6. Notas personales

Necesario:

- Servicio de notas simple con Markdown.
- Tags y busqueda semantica.
- Relacion nota <-> memoria <-> tarea.
- Export/import.

### 7. Audio y voz

Necesario:

- STT para escuchar audios/notas de voz.
- TTS para responder por Telegram/app.
- ElevenLabs/OpenAI audio u otro proveedor.
- Politica de privacidad: no enviar audio a terceros sin flag y aviso.

### 8. YouTube/video

Necesario:

- Extraer metadata y transcript cuando exista.
- Resumir transcript con citas temporales.
- Si no hay transcript, descargar/analizar audio o frames con vision, bajo
  limites de tamano y proveedor.
- Cache de resumen por video_id.

### 9. MCP/tools/skills externos

Necesario:

- Registry de tool providers.
- Adaptador MCP a tools DeepAgents bajo policy.
- Importador de skills externas a `storage/deepagents/skills/user`.
- Sandbox/validacion de SKILL.md antes de habilitar.

### 10. Programar apps en IDE/repos

Necesario:

- Modo proyecto: abrir repo, diagnosticar, editar, testear, construir.
- Politica de escritura por workspace.
- PR/patch summary.
- Soporte a agentes externos opcionales (Claude Code, OpenCode, etc.) como
  ejecutores sandboxeados, no como dependencias obligatorias.

## Orden recomendado

1. ~~Fase 25: memoria personal + preferencias + eventos episodicos~~ (base fuerte: DeepAgents memory + episodic API).
2. ~~Fase 26A: correo multicuenta primer corte~~ (GoDaddy IMAP/SMTP + propuestas + UI Mail).
3. Fase 26B: tareas/notas/recordatorios con Telegram como notificador (+ cablear escritura episódica desde jobs/Telegram).
3. ~~Fase 27 web grounding multi-provider~~ (nucleo listo): cross-check sintetico, telemetrias y agendas de refresco mas avanzadas.
4. Fase 28: mejorar mail con LLM classifier, Telegram approvals, acciones mailbox.
5. ~~Fase 29: Google Calendar + reminders proactivos~~ (Calendar base lista; falta push/scheduler avanzado).
6. ~~Fase 30: Notas DB + Weaviate hybrid/BM25~~; falta Notion sync/export/import.
7. ~~Fase 31: Google Ops comercial~~ (Maps/Calendar/Drive UI + ActionRequests). Siguiente: YouTube/audio summaries y UX voz.
8. Fase 32: MCP/skills external adapter + IDE/repo agent workflow.

## Criterio de aceptacion global

Cada capacidad nueva debe tener:

- flag de configuracion;
- provider fake para tests;
- tests unitarios + endpoint si aplica;
- redaccion de secretos;
- auditoria;
- documentacion en `ACTION_PLANE.md` o guia especifica;
- degradacion clara (`blocked`, no excepcion 500) cuando faltan credenciales.

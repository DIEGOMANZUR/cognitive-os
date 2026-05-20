# Cognitive OS - Guia Simple Y Tecnica

> **Estado actual (2026-05-20, Fase 74 — auditoría completa + cliente MCP; LLM primary/agent gpt-5.5, fallbacks gemini-3.1-pro-low, visión glm-4.6v; suite hermética 712 passed):**
> producto en grado comercial operativo. Backend FastAPI 0.115+ con **130
> endpoints REST**, **17 tareas Celery** distribuidas en **5 queues**
> (`default`, `ingestion`, `agent_longrun`, `maintenance`, `mail`), **17
> migraciones Alembic** (head `202605170001`). Frontend Next.js 16.2.6
> con **20 vistas** (incluidas `AssistView`, `GoogleOpsView`,
> `ResearchView` con plan animado sobre SSE, y `CodeDirectorView`). La
> ruta `research` está fusionada con **OpenHarness** opcional (extra
> `openharness-ai>=0.1.9,<0.2`, `prelude_merge` por defecto). Runtime
> local (cadena verificada Fase 67/68): primary+agent **gpt-5.5**, secondary/fallback **gemini-3.1-pro-low**, visión **glm-4.6v**; Kimi solo Code Director CLI.
>
> Fase 41 (F9) llevó al **Code Director** a "máximo nivel": planner
> LLM-driven que descompone objetivos en subtareas reales con fallback
> heurístico determinista, y prompts con contexto vivo del workspace +
> reintentos dirigidos por el error previo. Fase 40 introdujo el Code
> Director (delegación a Claude Code / Codex / Kimi CLI o DeepAgents
> bajo HumanApproval + budget caps). Fase 39 cerró los residual risks
> técnicos: rate limiter pluggable memory/Redis,
> `/system/credentials-status` con inventario vivo, `workflow.v1`
> export/import, OAuth Google self-healing, `init_credentials.sh`
> wizard, correlation IDs, approval reaper, four-eyes, AuditEvent
> simétrico REST↔Telegram. Fases 50-58 cerraron approvals Telegram con
> dispatch real de `ActionRequest` y smoke de launchers. Fases 59-63
> agregaron dispatch durable con fallo de broker controlado y JobEvents
> submit/fail. Fase 64 añadió reserva atómica anti-submit duplicado.
> Fase 65 cerró paridad Telegram↔UI (36 slash commands) y corrigió el
> CHECK `ck_ar_action_type` que rompía Drive folder/organize en Postgres.
> QA snapshot: **712 pytest passed, 1 skipped, 20 deselected**; ruff/format/mypy,
> frontend lint/build, Alembic head `202605170001` y `git diff --check` verdes.
>
> **Guía de usuario completa:** `docs/USER_GUIDE.md`.

## En Una Frase

Cognitive OS es una central local de inteligencia artificial para investigar,
analizar documentos, producir evidencia trazable y preparar acciones externas
seguras con aprobacion humana.

## En Palabras Simples

No es solo un chatbot. Es una mesa de trabajo con varias piezas coordinadas:

- Un panel web para operar el sistema.
- Un backend que recibe solicitudes y decide que ruta seguir.
- Una memoria de documentos con citas.
- Un grafo para entender relaciones entre personas, fechas, documentos y hechos.
- Trabajadores de fondo para tareas largas.
- Agentes especializados que investigan o analizan documentos.
- Un sistema de aprobaciones para impedir acciones sensibles sin supervision.
- Una capa de accion para navegador, carpetas, Gmail, Google Maps/Calendar/Drive,
  mail personal, GoDaddy y documentos,
  con solicitudes persistentes o aprobaciones explícitas para acciones sensibles.

La idea es que puedas pedir algo como:

```text
Analiza estos documentos, detecta contradicciones, crea una linea de tiempo
y prepara una matriz hecho/evidencia/cita.
```

El sistema debe recuperar evidencia, citar paginas, separar hechos de inferencias
y guardar los resultados. Si algo puede afectar el mundo real, por ejemplo enviar
un email o cambiar DNS, debe pedir aprobacion.

## Mapa Mental

```text
Usuario
  -> Frontend Next.js
  -> FastAPI
  -> LangGraph decide ruta
  -> RAG / (opcional OpenHarness en research) / DeepAgents / Document Analysis / Action Plane / OpenShell
  -> Postgres guarda estado, jobs, aprobaciones y auditoria
  -> Weaviate guarda chunks para busqueda semantica
  -> Neo4j guarda relaciones
  -> Celery procesa tareas largas
```

## Componentes Principales

### Frontend

Ubicacion: `frontend/`

Es la consola del operador. Permite chatear, revisar jobs, aprobar acciones,
ver salud del sistema, gestionar documentos, inspeccionar memoria y revisar el
estado del action plane. Cuando una aprobacion corresponde a una `ActionRequest`,
el panel intenta despacharla automaticamente despues de aprobarla.

### API Backend

Ubicacion: `backend/src/cognitive_os/api/app.py`

Expone endpoints para chat, documentos, document analysis, jobs, aprobaciones,
memoria, salud, skills, sandbox y action plane.

### Orquestador LangGraph

Ubicacion: `backend/src/cognitive_os/agents/graph.py`

Es el coordinador. Decide si una solicitud va a investigacion, analisis legal,
comunicaciones, social, revision humana o respuesta final. Mantiene estado por
thread y puede persistirlo con Postgres.

### RAG Y Busqueda

Ubicaciones:

- `backend/src/cognitive_os/memory/`
- `backend/src/cognitive_os/ingestion/`

Los documentos se ingieren, se dividen en paginas/chunks, se indexan en Weaviate
y se citan con `doc_id`, `chunk_id` y paginas.

### Neo4j

Ubicacion: `backend/src/cognitive_os/ingestion/neo4j.py`

Guarda relaciones entre entidades. No reemplaza a RAG; lo complementa cuando la
pregunta es relacional.

### DeepAgents

Ubicacion: `backend/src/cognitive_os/deepagents/`

Son trabajadores cognitivos especializados. No mandan sobre el sistema: reciben
tareas acotadas, herramientas permitidas y politicas estrictas. Si quieren hacer
algo externo, deben pedirlo como accion revisable.

La integracion usa `deepagents>=0.6.1,<0.7.0`. Cognitive OS habilita subagents
locales seguros para investigacion, citas, evidencia, timeline y contradicciones,
pero todos heredan las mismas tools controladas y no reciben shell/email/browser
sin politica y aprobacion.

### OpenHarness (fusión en research, opcional)

Ubicacion principal: `backend/src/cognitive_os/integrations/openharness_research.py`
y el nodo `research_node` en `backend/src/cognitive_os/agents/graph.py`.

**OpenHarness** es un paquete opcional (`openharness-ai`) que expone un bucle
de herramientas (`QueryEngine`) probado en upstream. Cognitive OS no lo trata
como orquestador: LangGraph lo invoca en la ruta **research** cuando
`ENABLE_OPENHARNESS_RESEARCH=true` y el extra está instalado.

- Por defecto (**`prelude_merge`**), el texto que devuelve OpenHarness se guarda
  en `openharness_prelude` y DeepAgents lo recibe al inicio del mensaje de
  usuario para **integrarlo** con citas RAG y política propia.
- Con **`short_circuit`**, si OpenHarness responde bien, no se ejecuta DeepAgent
  en ese turno.

Modo de workspace (**`deepagent_mirror`**) y presets de herramientas
(`minimal`, `research`, `full`) están descritos en **`docs/OPENHARNESS_FUSION.md`**.

### Document Analysis Agent

Ubicacion: `backend/src/cognitive_os/deepagents/document_analysis/`

Produce matriz hecho/evidencia/cita, timeline, contradicciones, vacios
probatorios, reportes Markdown/JSON/CSV/DOCX y quality score. No reemplaza una
revision profesional; entrega soporte trazable.

### Action Plane

Ubicacion: `backend/src/cognitive_os/actions/`

Prepara acciones sobre navegador, computador local, Gmail, mail personal,
GoDaddy y generacion de documentos Office. Hoy combina preview-first,
`ActionRequest` persistente y aprobacion humana:

- valida dominios;
- valida rutas;
- valida scopes;
- previsualiza movimientos de archivos;
- previsualiza cambios DNS;
- sincroniza correo personal GoDaddy/Gmail-label y propone respuestas escritas;
- envía respuestas de mail solo después de aprobación humana explícita;
- genera DOCX/XLSX/PPTX con guardrails de ruta, tamano, assets allow-listed y
  formulas XLSX explicitas;
- muestra si cada capacidad esta disabled, blocked, configured o ready.
- registra solicitudes de accion con preview, estado, job, aprobacion y resultado.

No ejecuta acciones reales por accidente. Las ejecuciones reales implementadas
incluyen `computer_organize`, `document_generate`, `browser_preview`,
`browser_interactive`, Calendar create, Drive upload/folder/organize, GoDaddy DNS
bajo flags estrictos y mail GoDaddy SMTP bajo aprobación humana. Cada una queda
limitada por configuración, auditoría y estado.

### OpenShell Sandbox

Ubicacion: `experiments/openshell-deepagent/`

Sirve para ejecucion de codigo aislada. Esta apagado por defecto, no recibe
secretos, no monta home y requiere aprobacion para tareas riesgosas.

## Flujo De Una Tarea Normal

1. El usuario escribe en el panel.
2. FastAPI valida JWT.
3. LangGraph decide la ruta.
4. Si necesita evidencia, consulta documentos.
5. Si la ruta es research y OpenHarness está habilitado, puede ejecutarse antes
   el preludio QueryEngine (según `OPENHARNESS_RESEARCH_PIPELINE`).
6. Si necesita trabajo largo, encola un job Celery.
7. El worker ejecuta la tarea y guarda eventos.
8. El usuario ve progreso en `Jobs`.
9. El resultado queda disponible con citas y artefactos.
10. Si hay riesgo, se crea `HumanApproval`.

## Como El Agente Podra Actuar

### Navegar Internet

Usara Playwright o Camoufox con perfiles aislados, nunca el navegador personal
del usuario. Solo podra abrir dominios en `BROWSER_ALLOWED_DOMAINS`. Headed y
vision requieren flags separados.

### Ordenar Carpetas

Primero genera un plan de movimientos dentro de `COMPUTER_ALLOWED_ROOTS`. Si el
operador desactiva dry-run y aprueba la solicitud, se ejecuta como job Celery,
revalida rutas antes de mover y deja resultado/auditoria. El modo por defecto
es dry-run, por seguridad.

### Revisar correo

Hay dos rutas complementarias:

- Gmail OAuth read-only (`gmail.readonly`) para digest y label `TODOS` cuando
  existe `GMAIL_TOKEN_DIR/token.json`.
- Mail personal multicuenta (`cognitive_os.mail`) para GoDaddy IMAP/SMTP:
  sincroniza carpetas configuradas, guarda mensajes en Postgres, clasifica
  importancia, genera propuestas escritas y envía desde `MAIL_DEFAULT_SENDER`
  solo tras aprobación humana.

### Gestionar GoDaddy

Primero usa OTE/sandbox de GoDaddy. DNS real esta en dry-run por defecto; para
ejecutar se exige dominio allow-listed, aprobacion humana y un flag extra si se
usa produccion. Cada solicitud aplica un solo record para que preview,
aprobacion y auditoria coincidan.

## Reglas De Seguridad

- Nada externo se ejecuta sin flag de entorno.
- Nada sensible se ejecuta sin aprobacion humana.
- Nada se registra con secretos sin redaccion.
- Nada toca rutas fuera de allow-lists.
- Nada usa perfiles reales del navegador.
- Nada de DNS/email se ejecuta sin preview o aprobación explícita.

## Donde Mirar Si Algo Falla

- Salud general: `GET /health/dashboard`
- Jobs: `/jobs` y `/jobs/{job_id}/events`
- Aprobaciones: `/approvals`
- Auditoria: `/audit`
- Action plane: `/actions/capabilities`
- Logs de Docker: `scripts/dev_logs.sh SERVICE_NAME`

## Comandos De Calidad

Backend:

```bash
cd backend
uv sync --extra openharness   # opcional, requerido si vas a probar la ruta research con OpenHarness
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000
```

> `uv run cognitive-os` solo ejecuta el bootstrap (`cognitive_os.__main__:main`); el servidor real es `uvicorn cognitive_os.api.app:app`.

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

QA reproducible (recomendado antes de promocionar):

```bash
bash scripts/full-qa.sh    # incluye uv sync --extra openharness y pytest completo
bash scripts/stress-qa.sh  # repite pytest N veces para detectar flakiness
```

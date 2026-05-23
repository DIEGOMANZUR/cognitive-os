# Cognitive OS - Guia Simple Y Tecnica

> **Estado actual (2026-05-23, commit `647f103`):** producto local-first
> para un PC dedicado del operador. La prioridad explícita es fricción
> casi nula por sobre seguridad estricta: usar Edge real, Kimi WebBridge,
> filesystem local y auto-resolución de aprobaciones en
> `dedicated_local/full` es una decisión de producto, no una excepción
> accidental. `strict` queda disponible como perfil conservador. Doble
> auditoría TestSprite cerrada en `docs/audits/testsprite/16_FINAL_REAUDIT_REPORT.md`.
>
> **Snapshot vivo:** backend FastAPI con **147 decoradores REST**, **23
> tareas Celery** en **5 queues**, **20 migraciones Alembic** (head
> `202605200003`), frontend Next.js 16.2.6 con **20 vistas**, Telegram con
> **37 slash commands**, health dashboard con **18 componentes** y
> `POST /health/verify` para probe en vivo. Mail personal: Gmail `TODOS` +
> `SPAM` de `diegomanzurn@gmail.com`, GoDaddy `Spam` de
> `diego@doctormanzur.com`, clasificación de spam por agente, digest
> 10:00/20:00 Chile, máximo 50 correos, propuestas de respuesta como texto
> separado; no drafts y no envío automático.
>
> **QA más reciente (commit `647f103`):** `bash scripts/full-qa.sh` verde
> con **947 passed, 1 skipped, 28 deselected** (944 históricos + 3 nuevos
> que cubren el fix `eager_defaults`); ruff/format/mypy/Alembic/lint/
> build/`sync_doc_counts --check`/`git diff --check` OK; Playwright
> **31 passed** sin exportar `COGOS_JWT` (auto-mint via
> `_global-setup.ts`); `bash scripts/stress-qa.sh` verde con 3 pasadas
> de **947 passed**. El build de QA usa `NEXT_DIST_DIR=.next-qa` para no
> invalidar un frontend vivo servido desde `.next`. Live read-only:
> **8 passed**. TestSprite MCP re-audit: **10/10 passed** sobre dos
> batches acotados.
>
> **Ultimo ajuste post-gate (`647f103`):** fix `eager_defaults=True` en
> `db.Base` corrige `MissingGreenlet` en `/actions/*/preview/request` y
> análogos. Playwright runner zero-friction (auto-mint JWT).
>
> **Ajuste previo (`5953b40`):** `/system/mcp` ahora inventaria los
> servidores en paralelo con timeout default 30s; runtime verificado
> **5/5 MCP servers** y **67 tools**. El command palette del frontend
> abre con `Ctrl/Cmd+K` de forma estable incluso con foco en inputs.
>
> **Guía de usuario completa:** `docs/USER_GUIDE.md`. Estado canónico:
> `docs/CURRENT_STATE.md`. Modelo operativo: `docs/ZERO_FRICTION_OPERATING_MODEL.md`.

## En Una Frase

Cognitive OS es una central local de inteligencia artificial para investigar,
analizar documentos, producir evidencia trazable y ejecutar o preparar acciones
externas con trazabilidad. En este PC dedicado se privilegia la mínima fricción
operativa; la aprobación humana queda como política configurable por perfil y
como excepción obligatoria para envíos de correo no solicitados explícitamente.

## En Palabras Simples

No es solo un chatbot. Es una mesa de trabajo con varias piezas coordinadas:

- Un panel web para operar el sistema.
- Un backend que recibe solicitudes y decide que ruta seguir.
- Una memoria de documentos con citas.
- Un grafo para entender relaciones entre personas, fechas, documentos y hechos.
- Trabajadores de fondo para tareas largas.
- Agentes especializados que investigan o analizan documentos.
- Un sistema de aprobaciones configurable: estricto cuando se necesita control,
  y de mínima fricción en el perfil local dedicado.
- Una capa de accion para navegador, carpetas, Gmail, Google Maps/Calendar/Drive,
  mail personal, GoDaddy y documentos,
  con solicitudes persistentes o aprobaciones explícitas para acciones sensibles.

La idea es que puedas pedir algo como:

```text
Analiza estos documentos, detecta contradicciones, crea una linea de tiempo
y prepara una matriz hecho/evidencia/cita.
```

El sistema debe recuperar evidencia, citar paginas, separar hechos de inferencias
y guardar los resultados. Si algo puede afectar el mundo real, la política exacta
depende del perfil operativo; el correo es la excepción dura y nunca se envía en
el flujo normal.

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

Hay dos carriles:

- **`browser_preview` / `browser_interactive`** (Playwright headless con
  visión multimodal): perfiles aislados, dominios limitados por
  `BROWSER_ALLOWED_DOMAINS`. Headed y visión requieren flags separados.
- **Kimi WebBridge / Edge real:** en el perfil `dedicated_local`, y como
  decisión de producto explícita de este PC, el agente puede operar el
  navegador Edge real del operador vía el daemon Kimi WebBridge
  (`ENABLE_KIMI_WEBBRIDGE` / `ENABLE_EDGE_DEVTOOLS_WEBBRIDGE`). Ver
  `docs/ACTION_PLANE.md` y `docs/ZERO_FRICTION_OPERATING_MODEL.md`.

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

En este PC dedicado la postura es fricción casi nula (ver
`docs/ZERO_FRICTION_OPERATING_MODEL.md`); las reglas vigentes son:

- Nada externo se ejecuta sin su flag de entorno.
- En `strict`, las acciones sensibles pasan por aprobación humana; en
  `dedicated_local/full` se auto-resuelven las reversibles, pero siempre
  quedan `ActionRequest`, `JobEvent` y `AuditEvent`.
- Nada se registra con secretos sin redacción.
- Nada toca rutas fuera de las allow-lists configuradas.
- El navegador Edge real del operador **sí** se usa, vía Kimi WebBridge,
  como decisión de producto del perfil `dedicated_local`; los carriles
  `browser_preview`/`browser_interactive` siguen usando perfiles aislados.
- Mail es la excepción dura: nada de DNS/email se ejecuta sin preview o
  aprobación explícita, y el flujo normal de correo no envía ni crea drafts.

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

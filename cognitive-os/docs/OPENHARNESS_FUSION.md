# Fusión OpenHarness ↔ Cognitive OS (LangGraph + DeepAgents)

> **Estado actual (2026-05-22):** integración estable, **opcional**,
> dentro del modelo local de baja fricción. OpenHarness solo participa en
> la ruta `research`; no cambia el contrato de mail, no envía correos, no
> crea drafts y no sustituye al Action Plane. En `dedicated_local/full`,
> puede compartir workspace con DeepAgents para acelerar investigación,
> pero los fallos deben quedar como fallback explícito y no como éxito
> falso.
>
> **Histórico (2026-05-20, Fase 74):** integración estable, **opcional**,
> gobernada por `ENABLE_OPENHARNESS_RESEARCH`. Pipeline por defecto
> **`prelude_merge`**, workspace por defecto **`deepagent_mirror`**, preset
> por defecto **`research`**. Cadena LLM verificada (gateway openai-compatible
> del operador): primary+agent **`gpt-5.5`**, secondary/fallback
> **`gemini-3.1-pro-low`**, visión **`glm-4.6v`**. Kimi-k2.6 sólo a través del
> adapter CLI del Code Director (su endpoint HTTP devuelve 403). El extra
> opcional se instala con `uv sync --extra openharness` (declara
> `openharness-ai>=0.1.9,<0.2`). Mail personal (GoDaddy IMAP/SMTP + Gmail
> label `TODOS`) y Kimi WebBridge no cambian este contrato. La fusión NO
> participa en `document_analysis` (ruta legal) ni en el carril `/mail/*`.

Esta guía describe cómo integramos [OpenHarness](https://github.com/HKUDS/OpenHarness) en la **ruta `research`** de Cognitive OS **sin** sustituir al orquestador LangGraph ni al subagente [DeepAgents](https://github.com/langchain-ai/deepagents). El producto resultante combina las tres piezas: orquestación + políticas + persistencia aquí; bucle de herramientas probado en OpenHarness cuando aporta; informe estructurado y skills con DeepAgents.

## 1. Roles de cada pieza

| Pieza | Rol concreto en `research_node` |
| --- | --- |
| **LangGraph** (`agents/graph.py::research_node`) | Decide si invoca OpenHarness (extra instalado y `enable_openharness_research`), resuelve `cwd`, llama al puente, construye `DeepAgentTask` y maneja resultado/fallback. |
| **OpenHarness** (`integrations/openharness_research.py`) | Crea `OpenAICompatibleClient` con `PRIMARY_LLM_*`, monta `ToolRegistry` según preset, instancia `QueryEngine`, recolecta el último mensaje `assistant`. |
| **DeepAgents** (`deepagents/research_deepagent.py`) | Sigue siendo el motor del informe: skills, RAG citado, política `DeepAgentToolPolicy` (sin shell/browser/email/social/delete) y workspace bajo `storage/workspaces/{thread_id}/{task_id}/`. |
| **Fallback RAG determinista** | Si DeepAgents devuelve respuesta vacía, `research_node` invoca `ResearchAgent` con `ReadOnlyResearchTools`. |

OpenHarness **no** es un segundo orquestador. Es **un paso opcional en la ruta `research`** controlado por `OPENHARNESS_RESEARCH_PIPELINE`.

## 2. Configuración (1:1 con `Settings`)

Variables expuestas en `backend/src/cognitive_os/core/config.py` (todas con prefijo `OPENHARNESS_*` o el flag global) y reflejadas en la tabla generada `docs/SETTINGS_REGISTRY_TABLE.md`:

| Env / Atributo | Default | Significado |
| --- | --- | --- |
| `ENABLE_OPENHARNESS_RESEARCH` | `false` | Encender el puente. Sin esto, `research_node` ignora OpenHarness aunque el extra esté instalado. |
| `OPENHARNESS_RESEARCH_PIPELINE` | `prelude_merge` | `prelude_merge` (siempre llama DeepAgent y antepone preludio) o `short_circuit` (devuelve sólo OH si responde bien). |
| `OPENHARNESS_TOOLKIT_PRESET` | `research` | `minimal`, `research` o `full`. Detalle abajo. |
| `OPENHARNESS_WORKSPACE_MODE` | `deepagent_mirror` | `deepagent_mirror` (mismo cwd que DeepAgent) o `sandbox` (usa `OPENHARNESS_WORKSPACE`). |
| `OPENHARNESS_WORKSPACE` | `./storage/openharness_workspace` | Raíz cuando el modo es `sandbox`. |
| `OPENHARNESS_INCLUDE_FILE_TOOLS` | `false` | Sólo afecta al preset `minimal`: añade `FileReadTool`. En `research`/`full` los file tools ya están incluidos por defecto. |
| `OPENHARNESS_WEB_TOOLS` | `true` | Permite registrar `web_search` / `web_fetch`. La ejecución real exige además `WEB_SEARCH_ENABLED=true` (gate del proyecto). |
| `OPENHARNESS_QUERY_TIMEOUT_SECONDS` | `180` | Hard timeout (wall clock) por ejecución; al expirar, `OpenHarnessResearchResult.error="OpenHarness exceeded timeout (...)"`. |
| `OPENHARNESS_MAX_TURNS` | `16` | Pasado a `QueryEngine(max_turns=...)`. |

Instalación: en `backend/`, `uv sync --extra openharness` (paquete `openharness-ai>=0.1.9,<0.2`, declarado en `pyproject.toml`).

## 3. Pipeline (`OPENHARNESS_RESEARCH_PIPELINE`)

Implementado en `agents/graph.py::research_node` (líneas con `oh_result`, `oh_prelude`, `task_metadata`).

### `prelude_merge` (default)
1. Si OpenHarness está disponible y habilitado, se llama `run_openharness_research_sync(...)`.
2. Si `oh_result.ok` y `oh_result.answer.strip()`, el texto se guarda en `task.metadata["openharness_prelude"]`.
3. Se ejecuta `run_deepagent_task` siempre. `build_research_user_message_content(task)` (en `deepagents/research_deepagent.py`) antepone:
   ```
   Preludio de OpenHarness (QueryEngine dentro de Cognitive OS).
   Integra y contrasta estos apuntes con tu propia evidencia y citas.

   <texto OH>

   ---

   Pregunta: <task.query>
   Devuelve DeepAgentResult estructurado. No ejecutes acciones externas.
   ```
4. Si OpenHarness falla (`error`), `research_node` loggea `openharness_research_fallback` y continúa sin preludio.

### `short_circuit`
1. Si OpenHarness responde con texto válido, `research_node` retorna inmediatamente:
   ```python
   AgentResult(route="research", content=oh_result.answer,
               citations=[], uncertainty="OpenHarness QueryEngine (restricted tools).")
   ```
   No se llama a DeepAgent ni al fallback.
2. Si OpenHarness no responde válidamente, el flujo continúa con DeepAgent + fallback como en `prelude_merge`.

### Casos sin OpenHarness
- `enable_openharness_research=false` → se omite todo el bloque OH.
- Extra no instalado → `is_openharness_available()` retorna `False` y se loguea `openharness_enabled_but_package_missing`.
- `skipped_reason` posibles del puente: `openharness_not_installed`, `disabled`, `empty_query`.

## 4. Workspace (`OPENHARNESS_WORKSPACE_MODE`)

`integrations/openharness_research.py::resolve_openharness_cwd`:

- **`deepagent_mirror` (default)** y `thread_id`+`task_id` definidos →
  `Path(LOCAL_STORAGE_DIR) / "workspaces" / {thread_id} / {task_id}`.
  Coincide exactamente con `DeepAgentWorkspace` creado por `research_deepagent.create_workspace(task)` para `task_id={thread_id}-research`. OpenHarness y DeepAgents leen/escriben **el mismo directorio** dentro del turno.
- **`sandbox`** → `Path(OPENHARNESS_WORKSPACE)` resuelto.

El directorio se crea con `mkdir(parents=True, exist_ok=True)` antes de instanciar `QueryEngine`.

## 5. Presets de herramientas (`OPENHARNESS_TOOLKIT_PRESET`)

`build_tool_registry(app_settings, *, web_allowed)` decide qué tools registrar (`integrations/openharness_research.py`):

### `minimal`
- Siempre: `GrepTool`, `GlobTool`.
- Si `OPENHARNESS_INCLUDE_FILE_TOOLS=true`: + `FileReadTool`.
- Si `web_on` (`web_allowed and OPENHARNESS_WEB_TOOLS`): + `WebSearchTool`, `WebFetchTool`.
- `PermissionMode.PLAN` (más restrictivo en OpenHarness).

### `research` (default)
- Conjunto amplio inspirado en upstream (sin MCP remoto):
  bash, ask_user_question, file_read/write/edit, notebook_edit, glob, grep,
  image_to_text, **lsp**, skill, tool_search, config, brief, sleep,
  enter/exit_worktree, todo_write, enter/exit_plan_mode,
  cron_create/list/delete/toggle, remote_trigger,
  task_create/get/list/stop/output/update, agent, send_message,
  team_create/delete, mcp_auth.
- Si `web_on`: + `WebSearchTool`, `WebFetchTool`.
- `PermissionMode.FULL_AUTO`.

### `full`
- Llama `openharness.tools.create_default_tool_registry(None)` upstream.
- Si web está deshabilitada (`not web_on`), se construye un `ToolRegistry` filtrado **omitendo** las tools cuyo `name in {"web_search", "web_fetch"}` (sin tocar internals privados de upstream).
- `PermissionMode.FULL_AUTO`.

> **Nota web**: el flag efectivo es `web_allowed and OPENHARNESS_WEB_TOOLS`. `research_node` pasa `web_allowed=settings.web_search_enabled` al puente, así que la búsqueda web sólo aparece dentro de OpenHarness cuando ambos flags están en `true`.

## 6. Modelo y prompt

- LLM: `OpenAICompatibleClient(api_key=PRIMARY_LLM_API_KEY, base_url=PRIMARY_LLM_BASE_URL)` y `model=PRIMARY_LLM_MODEL`.
- System prompt OpenHarness (corto y citacionista):
  ```
  You are OpenHarness tooling inside Cognitive OS (LangGraph + DeepAgents downstream).
  Prefer accurate, cited short notes the orchestrator will merge into a structured report.
  Use Spanish when user content is Spanish. Never fabricate accesses outside cwd.
  ```
- `max_tokens=4096`, `max_turns=OPENHARNESS_MAX_TURNS`, `settings=None` (no pasamos `Settings` upstream para que use defaults internos sin fugar config interna).

## 7. Resultado

`OpenHarnessResearchResult` (dataclass frozen, `slots=True`) tiene:
- `ok: bool`
- `answer: str` (último mensaje `assistant.text`)
- `error: str | None` (timeout, runtime, excepción genérica, errores acumulados con texto vacío)
- `skipped_reason: str | None` (`openharness_not_installed` | `disabled` | `empty_query`)

## 8. Puntos de código relevantes

| Archivo | Símbolo | Para qué |
| --- | --- | --- |
| `backend/src/cognitive_os/core/config.py` | Campos `enable_openharness_research`, `openharness_*` | Fuente de verdad de configuración |
| `backend/src/cognitive_os/integrations/openharness_research.py` | `is_openharness_available`, `resolve_openharness_cwd`, `build_tool_registry`, `_permission_context`, `_run_engine_inner`, `_run_engine`, `_execute_engine_blocking`, `run_openharness_research_sync`, `OpenHarnessResearchResult` | Puente con OpenHarness |
| `backend/src/cognitive_os/agents/graph.py` | `research_node` | Orden y modo de fusión |
| `backend/src/cognitive_os/deepagents/research_deepagent.py` | `build_research_user_message_content`, `run_research_deepagent`, `create_workspace`, `research_policy` | Aplicación del preludio y workspace DeepAgent |
| `backend/tests/test_research_openharness_priority.py` | `test_research_node_uses_openharness_before_deepagent`, `test_research_node_prelude_merge_stashes_openharness_in_task_metadata`, `test_build_research_user_message_includes_openharness_prelude` | Regresión de los dos modos y del preludio |
| `backend/tests/test_openharness_research.py` | `test_is_openharness_available_matches_spec`, `test_run_openharness_skips_when_disabled`, `test_run_openharness_skips_when_disabled_even_if_extra_missing`, `test_run_openharness_skips_empty_query_when_enabled`, `test_run_openharness_safe_inside_running_loop` | Disponibilidad, skip-precedence y aislamiento de event loop |

### Aislamiento de event loop

`run_openharness_research_sync` usa `_execute_engine_blocking`, que crea un
`ThreadPoolExecutor(max_workers=1)` exclusivo y un **event loop nuevo** por
ejecución. Eso garantiza:

- No se rompe si alguien invoca el bridge desde un contexto async (FastAPI
  endpoints async, Celery con eventlet, scripts con `asyncio.run`).
- El loop se cierra tras `shutdown_asyncgens()` para evitar warnings de
  `Unclosed transport` / `Task was destroyed`.
- El timeout `OPENHARNESS_QUERY_TIMEOUT_SECONDS` opera dentro de ese loop
  aislado: cancela la coroutine sin afectar al loop del caller.

### Precedencia de skips

`run_openharness_research_sync` evalúa los skips en este orden estricto:

1. `disabled` — `ENABLE_OPENHARNESS_RESEARCH=false`.
2. `openharness_not_installed` — `importlib.util.find_spec("openharness")` es
   `None` (el extra no se sincronizó).
3. `empty_query` — el mensaje del usuario está vacío tras `strip()`.

Esto refleja intención del operador antes que estado del entorno: si el
operador apagó el motor, no importa si el extra está instalado.

## 9. Operación local

```bash
cd backend
uv sync --extra openharness
ENABLE_OPENHARNESS_RESEARCH=true \
PRIMARY_LLM_API_KEY=... \
PRIMARY_LLM_BASE_URL=https://... \
PRIMARY_LLM_MODEL=... \
uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000
```

QA reproducible (asegura que la fusión sigue verde):

```bash
bash scripts/full-qa.sh        # uv sync --extra openharness + pytest + ruff + mypy + frontend lint/build
bash scripts/stress-qa.sh 5    # repite pytest 5 veces para detectar flakiness
```

## 10. Seguridad y operadores

- Los presets `research` y `full` exponen **muchas más capacidades** dentro del proceso OpenHarness que las del DeepAgent controlado (incluye `BashTool` operando dentro del cwd resuelto). El cwd está acotado pero el proceso del backend ejecuta esas tools.
- Trátalo como **capacidad de operador consciente**: despliega sólo donde el operador entienda preset, modo de workspace y límites de red/web (`docs/SECURITY.md` apartado *OpenHarness*).
- El extra `openharness` **no se carga** si `ENABLE_OPENHARNESS_RESEARCH=false`. La importación de tools de upstream ocurre dentro de funciones para evitar coste cuando el motor no se usa.

## 11. Por qué la fusión supera a OpenHarness o DeepAgents por separado

- **Política unificada y human-in-the-loop**: graph + Action Plane + aprobaciones siguen vivos aunque el research use el bucle OpenHarness.
- **Mismo workspace** entre OH y DeepAgent (modo mirror) → evidencia y artefactos compartidos en una sola tarea.
- **Preludio explícito** hacia DeepAgent (no caja negra): el operador puede leer en `metadata["openharness_prelude"]` qué entró al informe.
- **Fallback determinista** si cualquiera de los dos motores falla → la ruta `research` no se queda muda.
- **Trazabilidad**: structlog (`openharness_research_fallback`, `openharness_skipped`, `openharness_query_timeout`, `openharness_async_runtime_error`, `openharness_research_failed`) + auditoría DeepAgent (`deepagents.research`).

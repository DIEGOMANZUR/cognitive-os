# DeepAgents Integration

> **Estado actual (2026-05-15, 04:47 hora Chile):** DeepAgents
> (`deepagents>=0.6.1,<0.7.0`) sigue siendo el subagente productivo de las
> rutas `research` y `document_analysis`. En `research` puede recibir un
> **preludio OpenHarness** vía `task.metadata["openharness_prelude"]` (ver
> `docs/OPENHARNESS_FUSION.md`). El carril `/mail/*` (GoDaddy IMAP/SMTP +
> Gmail label `TODOS`) no habilita `send_email` dentro del DeepAgent: las
> políticas locales (`DeepAgentToolPolicy`) no se relajan por la fusión ni
> por mail personal. Tools efectivamente expuestas por
> `build_deepagent_tools` (verificable en
> `backend/src/cognitive_os/deepagents/tools.py`): operaciones de
> archivo/URL (`read_file`, `write_file`, `list_files`, `glob_files`,
> `delete_file`, `read_url`), búsqueda web (`search_web`), visión
> (`analyze_image`), skills/memoria (`list_available_skills`, `read_skill`,
> `get_relevant_memory`, `propose_memory_update`) y herramientas
> personales aisladas por `user_id` (`plan_route`, `geocode_address`,
> `list_calendar_events`, `check_calendar_freebusy`, `search_drive_files`,
> `preview_drive_organization`, `search_notes`).

## Rol En Cognitive OS

DeepAgents Python se integra como worker cognitivo/subgrafo especializado. No reemplaza al
orquestador LangGraph principal: Cognitive OS sigue siendo la torre de control que enruta,
aplica política, decide interrupciones humanas, persiste jobs y hace fallback.

En la ruta **`research`**, LangGraph puede ejecutar antes (opcional) **OpenHarness**
(`QueryEngine`) y fusionar el resultado con DeepAgents mediante
`openharness_prelude` cuando `OPENHARNESS_RESEARCH_PIPELINE=prelude_merge` (por defecto).
Orden técnico, presets y workspaces: **`docs/OPENHARNESS_FUSION.md`**.

Version actual integrada: `deepagents>=0.6.1,<0.7.0`. Cognitive OS usa las
capacidades nativas de DeepAgents 0.6.x (`write_todos`, filesystem, `task`,
subagents y memory) sin entregar permisos peligrosos por defecto.

## Tools Permitidas

Definidas en `backend/src/cognitive_os/deepagents/tools.py` y compuestas por `build_deepagent_tools` según la `DeepAgentToolPolicy`:

- `search_local_docs`: consulta RAG local con citas (filtra por `allowed_doc_ids`).
- `read_document_pages`: lee páginas ingeridas desde Postgres, máximo 20 por llamada.
- `graph_query_readonly`: consultas de grafo predefinidas; no acepta Cypher libre.
- `search_web`: solo si `WEB_SEARCH_ENABLED=true` y la tarea permite web.
- `write_workspace_file`: escribe solo dentro de `storage/workspaces/{thread_id}/{task_id}/`.
- `list_available_skills` / `read_skill`: introspección de skills habilitadas (core + user) para que el subagente decida qué procedimiento aplicar.
- `get_relevant_memory`: trae memoria revisada de `deepagent_memory_records` filtrada por scope.
- `propose_memory_update`: propone (no aprueba) nuevas entradas en `deepagent_memory_proposals`. La promoción a memoria activa requiere aprobación humana vía API.

## Tools Prohibidas

- `execute`, `shell`, `bash`, `python_exec`.
- `browser_action`.
- `send_email`.
- `publish_social_post`.
- `delete_file`.
- `edit_project_file`.
- Acceso al filesystem del proyecto.

DeepAgents usa un workspace temporal controlado y backend filesystem en `virtual_mode=True`.
No se habilita ejecución de shell dentro de DeepAgents. La ejecución de codigo
se canaliza por OpenShell, que es un sandbox separado, deshabilitado por defecto
y sujeto a aprobacion humana.

## Subagents

`DEEPAGENTS_ENABLE_SUBAGENTS=true` habilita subagents sincronicos locales dentro
del mismo harness DeepAgents. No son procesos separados ni reciben mas permisos:
usan las mismas tools policy-bound, el mismo backend virtual y el mismo
`interrupt_on` para herramientas sensibles.

Subagents actuales:

- Research: `local-rag-researcher`, `citation-auditor`, `web-researcher` solo
  si web esta permitido por tarea y policy.
- Document analysis: `evidence-matrix-specialist`, `timeline-specialist`,
  `contradiction-reviewer`.

Async subagents oficiales requieren Agent Protocol server / LangSmith Deployment
o una implementacion compatible. No se activan automaticamente en local.

## Memory Nativa

La memoria aprobada se inyecta de dos formas:

- Resumen de compatibilidad dentro del system prompt.
- Archivo `./.cognitive_os/AGENTS.md` creado dentro del workspace de la tarea,
  para que `MemoryMiddleware` de DeepAgents 0.6.x pueda leerlo como memory path.

La consolidacion evita duplicar propuestas por contenido normalizado.

## Test Manual

```bash
cd backend
uv run python ../scripts/test_deepagent_research.py "investiga la diferencia entre LangGraph y DeepAgents usando mis documentos locales"
```

El resultado se guarda en `storage/workspaces/manual-test/{task_id}/result.json`.

## Activar Web Search

1. Configura `WEB_SEARCH_ENABLED=true`.
2. Define al menos una clave (`TAVILY_API_KEY`, `BRAVE_API_KEY`, `PERPLEXITY_API_KEY`
   u `EXA_API_KEY`). Los proveedores disponibles se combinan automáticamente.
3. Lanza la tarea con `web_allowed=true`.

Si web no está habilitada, `search_web` devuelve `web_search_disabled`.

## Revisar Workspace

Cada tarea crea:

```text
storage/workspaces/{thread_id}/{task_id}/
  report.md
  result.json
```

Los endpoints y jobs nunca exponen rutas absolutas del workspace.

## Depuración

- Revisa `JobEvent` para `started`, `workspace_created`, `agent_started`, `agent_finished` o `failed`.
- Revisa `result.json`.
- Revisa `AuditEvent` para herramientas DeepAgents.
- Si DeepAgents falla, `research_node` usa fallback RAG directo.
- Si usas OpenHarness en `short_circuit`, una respuesta válida de OH evita DeepAgent;
  en `prelude_merge` (por defecto), el preludio llega en metadata y el fallo de OH
  sólo implica continuar sin preludio (`docs/OPENHARNESS_FUSION.md`).

## Riesgos Conocidos

- DeepAgents sigue un modelo "trust the LLM"; Cognitive OS impone allowlists, permisos y wrappers.
- El filesystem de DeepAgents se limita al workspace temporal, pero no sustituye aislamiento de proceso.
- Las herramientas web reales se mantienen deshabilitadas salvo configuración explícita.
- OpenShell es el camino separado para ejecucion de codigo. DeepAgents no recibe
  shell directo.
- OpenHarness (opcional) sí puede ejecutar bash y otras herramientas dentro del
  cwd del harness según preset; ver `OPENHARNESS_FUSION.md`.

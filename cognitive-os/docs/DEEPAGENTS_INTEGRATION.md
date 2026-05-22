# Integración de DeepAgents (referencia técnica)

> **Estado actual (2026-05-22):** DeepAgents sigue siendo el worker
> cognitivo productivo para `research` y `document_analysis`. En el perfil
> local dedicado se prioriza baja fricción: las tools permitidas por la
> policy pueden usar contexto real del operador, Kimi WebBridge y workspace
> local cuando están habilitadas. Eso no elimina la obligación de citas,
> logs, JobEvents y fallos explícitos; tampoco habilita envío automático de
> correo.
>
> **Histórico (2026-05-20, Fase 74):** DeepAgents (`deepagents>=0.6.1,<0.7.0`)
> es el subagente productivo de las rutas `research` y `document_analysis`
> del orquestador LangGraph. Expone **21 tools built-in** con `args_schema`
> Pydantic tipado (Fase 67 — antes los `lambda` sin tipos producían
> esquemas `{}` vacíos que los gateways estrictos rechazaban con `400
> Invalid schema`). Bajo `ENABLE_MCP_CLIENT=true` (Fase 73) se suman
> **tools dinámicas** de servidores MCP externos. El modelo del carril de
> agente es `gpt-5.5` vía `create_agent_chat_model()` — un modelo
> *tool-capable* (soporta `tool_choice` forzado para structured output);
> los modelos *reasoner* rompen este carril en silencio.

---

## 1. Rol dentro de Cognitive OS

DeepAgents NO reemplaza al orquestador LangGraph. LangGraph es la torre de
control: enruta, aplica políticas, decide interrupciones humanas, persiste
jobs y hace fallback. DeepAgents es el **worker cognitivo** que hace el
trabajo profundo dentro de un subgrafo especializado.

- En **`research`**: LangGraph puede ejecutar antes (opcional) un prelude
  de **OpenHarness** (`QueryEngine`) y fusionarlo vía
  `task.metadata["openharness_prelude"]` cuando
  `OPENHARNESS_RESEARCH_PIPELINE=prelude_merge` (default). Ver
  `docs/OPENHARNESS_FUSION.md`.
- En **`document_analysis`**: el subagente arma matrices hecho/evidencia/
  cita, detecta contradicciones, construye líneas de tiempo y propone
  borradores legales con citas. Ver `docs/DOCUMENT_ANALYSIS_AGENT.md`.

Cognitive OS usa las capacidades nativas de DeepAgents 0.6.x (`write_todos`,
filesystem virtual, `task`, subagents y memory) **sin entregar permisos
peligrosos por defecto**.

---

## 2. Las 21 tools built-in

Definidas en `backend/src/cognitive_os/deepagents/tools.py`, compuestas por
`build_deepagent_tools()` según la `DeepAgentToolPolicy` de la tarea. Cada
una tiene una clase `args_schema` Pydantic tipada y descrita.

**Conocimiento / RAG:**
- `search_local_docs` — RAG local con citas, filtra por `allowed_doc_ids`.
- `read_document_pages` — lee páginas ingestadas desde Postgres, máx. 20
  por llamada, respeta `allowed_page_ranges`.
- `graph_query_readonly` — consultas de grafo Neo4j predefinidas; NO
  acepta Cypher libre.
- `search_web` — sólo si `WEB_SEARCH_ENABLED=true` y la tarea permite web.

**Skills y memoria:**
- `list_available_skills` — introspección de skills habilitadas (core +
  user).
- `read_skill` — lee una skill por nombre, sin aceptar rutas arbitrarias.
- `get_relevant_memory` — trae memoria revisada, filtrada por scope
  (Fase 71-72: propaga `user_id`/`thread_id`).
- `propose_memory_update` — propone (no aplica) memoria nueva; la
  promoción a memoria activa requiere aprobación humana.

**Workspace:**
- `write_workspace_file` — escribe sólo dentro de
  `storage/workspaces/{thread_id}/{task_id}/`.

**Asistente personal (read-only, aislado por `user_id`):**
- `plan_route` / `geocode_address` — Google Maps.
- `list_calendar_events` / `check_calendar_freebusy` — Google Calendar.
- `search_drive_files` / `preview_drive_organization` — Google Drive.
- `search_notes` — notas personales indexadas en Weaviate.

**Navegador real (Kimi WebBridge, sólo si la policy lo habilita):**
- `browse_real_navigate` / `browse_real_snapshot` /
  `browse_real_screenshot` — controlan el Edge real del operador.

**Captcha (CapSolver):**
- `solve_image_captcha` / `solve_token_captcha` — resuelven captchas;
  gastan créditos CapSolver.

---

## 3. Tools MCP dinámicas (Fase 73)

Cuando `ENABLE_MCP_CLIENT=true`, `build_deepagent_tools()` recibe un
parámetro `mcp_tools` con las herramientas de los servidores MCP externos
declarados en `MCP_SERVERS`. Llegan prefijadas `<server>_<toolname>`
(p.ej. `mem_search_memories`, `gh_list_issues`, `fs_read_file`) para no
colisionar con las 21 built-in. La carga es:

- `research_deepagent.py` y `document_deepagent.py` llaman
  `load_mcp_tools_for_role_sync(role)` antes de crear el agente.
- La allow-list `MCP_ALLOWED_FOR_RESEARCH` /
  `MCP_ALLOWED_FOR_DOCUMENT_ANALYSIS` restringe qué servers ve qué carril.
- Sólo se activa bajo `OPERATOR_PROFILE=dedicated_local`.

Detalle: `docs/ARCHITECTURE.md` §8 + `docs/COGNITIVE_OS_GUIDE.md`.

---

## 4. Tools prohibidas dentro del DeepAgent

El DeepAgent NUNCA recibe directamente:

- `execute`, `shell`, `bash`, `python_exec` — la ejecución de código va
  por OpenShell (sandbox separado, off por default, con approval).
- `send_email` — el envío de mail pasa por `HumanApproval`, fuera del
  DeepAgent.
- `publish_social_post` — idem.
- `delete_file` / `edit_project_file` — el filesystem del DeepAgent es un
  workspace temporal en `virtual_mode=True`.
- Acceso al filesystem del proyecto.

El acceso amplio al filesystem del operador (Fase 73b: todo `/home/jgonz`)
NO es vía el DeepAgent crudo — es vía el servidor MCP `fs` (gobernado por
su propia policy) o vía `computer_organize` del Action Plane (con
preview + auto-approve reversible).

---

## 5. Subagents

`DEEPAGENTS_ENABLE_SUBAGENTS=true` habilita subagents síncronos locales
dentro del mismo harness. NO son procesos separados ni reciben más
permisos: usan las mismas tools policy-bound, el mismo backend virtual y
el mismo `interrupt_on` para herramientas sensibles.

- **Research:** `local-rag-researcher`, `citation-auditor`,
  `web-researcher` (sólo si web está permitido).
- **Document analysis:** `evidence-matrix-specialist`,
  `timeline-specialist`, `contradiction-reviewer`.

Los async subagents oficiales requieren Agent Protocol server / LangSmith
Deployment; no se activan automáticamente en local.

---

## 6. Memoria nativa

La memoria aprobada se inyecta de dos formas:

- Resumen de compatibilidad dentro del system prompt.
- Archivo `./.cognitive_os/AGENTS.md` dentro del workspace de la tarea,
  para que el `MemoryMiddleware` de DeepAgents 0.6.x lo lea como memory
  path.

El ciclo de memoria: `propose_memory_update` crea una propuesta →
`approve_memory_proposal` (API/operador) la promueve a memoria activa. La
consolidación (Celery beat diario) evita duplicar propuestas por contenido
normalizado. Fase 71-72: las propuestas propagan
`user_id`/`case_id`/`thread_id` para recall correcto por scope.

---

## 7. Test manual

```bash
cd backend
uv run python ../scripts/test_deepagent_research.py \
  "investiga la diferencia entre LangGraph y DeepAgents usando mis documentos locales"
```

El resultado se guarda en
`storage/workspaces/manual-test/{task_id}/result.json`.

---

## 8. Activar web search

1. `WEB_SEARCH_ENABLED=true`.
2. Al menos una clave: `TAVILY_API_KEY`, `BRAVE_API_KEY`,
   `PERPLEXITY_API_KEY` o `EXA_API_KEY`. Los proveedores se combinan
   automáticamente.
3. Lanzar la tarea con `web_allowed=true`.

Si web no está habilitada, `search_web` devuelve `web_search_disabled`.

---

## 9. Workspace y depuración

Cada tarea crea `storage/workspaces/{thread_id}/{task_id}/` con
`report.md` + `result.json`. Los endpoints y jobs nunca exponen rutas
absolutas.

Para depurar:
- `JobEvent`: `started`, `workspace_created`, `agent_started`,
  `agent_finished`, `failed`.
- `result.json`: salida estructurada del agente.
- `AuditEvent`: cada tool call del DeepAgent.
- Si DeepAgents falla, `research_node` usa fallback RAG directo citado.
- Con OpenHarness en `short_circuit`, una respuesta válida de OH evita el
  DeepAgent; en `prelude_merge` el fallo de OH sólo implica continuar sin
  preludio.

---

## 10. Riesgos conocidos

- DeepAgents sigue un modelo "trust the LLM"; Cognitive OS impone
  allowlists, permisos y wrappers en cada borde.
- El filesystem del DeepAgent se limita al workspace temporal — no
  sustituye aislamiento de proceso.
- Las tools web reales quedan deshabilitadas salvo configuración
  explícita.
- OpenShell es el único camino para ejecución de código; el DeepAgent no
  recibe shell directo.
- OpenHarness (opcional) sí puede ejecutar bash dentro de su cwd según
  preset; ver `OPENHARNESS_FUSION.md`.
- Las tools MCP corren contra servidores externos: una tool MCP de write
  puede tener efectos reales — por eso el cliente MCP es opt-in y sólo
  bajo `dedicated_local`.

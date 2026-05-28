# OpenCode Agent Stack — Cognitive OS

> **Estado V2.0 (2026-05-27, post cierre absoluto Prompt 7 V2.0).**
> Cognitive OS quedó certificado como **APTO COMERCIAL LOCAL-FIRST** para
> PC dedicado. Working tree limpio sobre commit V2.0 (`git log -1`). Gates V2.0:
> `full-qa.sh` **1232 passed**, `stress-qa.sh 5` **5/5 verde × 1232 × 2 ciclos**
> (flakiness 0%), `npx playwright test` **44 passed × 2 ciclos**,
> `full-qa-live.sh` **8 passed**, `openapi_readonly_smoke.py` **70/70**.
> Doc audit firmado: [`cognitive-os/docs/audits/FINAL_ABSOLUTE_V2_COMMERCIAL_LOCAL_FIRST_CERTIFICATION.md`](../audits/FINAL_ABSOLUTE_V2_COMMERCIAL_LOCAL_FIRST_CERTIFICATION.md).


> **Estado actual (2026-05-22):** OpenCode sigue siendo cockpit de
> desarrollo, no runtime productivo. El runtime Cognitive OS se documenta
> en `cognitive-os/docs/CURRENT_STATE.md` y prioriza fricción casi nula en
> PC dedicado por sobre seguridad estricta. Para trabajo de desarrollo,
> siguen vigentes las reglas de no filtrar secretos, no tocar backups/
> snapshots y no ejecutar acciones destructivas sin instrucción explícita.
>
> **Histórico (2026-05-15, 04:47 hora Chile):** OpenCode actúa como cockpit
> de desarrollo. `opencode.json` usa `{env:VAR}` para secretos MCP; las
> credenciales reales viven en `.env.local` ignorado por git con permisos
> `600`. Stack vigente: **21 MCPs** (17 conectados directos + 4 wrappers
> locales hacia MCPs remotos), **15 skills**, **7 subagentes** y **7
> comandos slash**. Memory Bank y Supermemory operan como dual-recall según
> la skill `dual-memory-recall`. Sin secretos inline en wrappers; los hooks
> de pre-commit cubren `gitleaks`. Verificado 2026-05-15.

Documento operativo del stack OpenCode instalado en este workspace.
OpenCode es **cockpit de desarrollo**; el runtime productivo lo manejan
LangGraph, DeepAgents, Neo4j, Weaviate y LangSmith.

## 1. Qué se configuró

- `AGENTS.md` (raíz): reglas principales del proyecto.
- `opencode.json` (raíz): configuración OpenCode con permisos conservadores,
  MCPs y referencias `{env:VAR}` para secretos.
- `.gitignore`: ampliado con `opencode.local.json`, `.opencode/local/`,
  `.opencode/node_modules/`, `.opencode/package-lock.json`, `memory-bank/`,
  `task_plan.local.md`, `findings.local.md`, `progress.local.md`,
  `*.bak-*`. Backup en `.gitignore.bak-20260513-021119`.
- `.env.local` (ignorado): credenciales reales de Neo4j y Weaviate
  importadas desde `cognitive-os/.env`. Permisos `600`.
- `.env.local.example`: plantilla pública.
- `.opencode/skills/` (15 skills nativas/proyecto, incluido `kimi-webbridge` y
  `opencode-operator`).
- `.opencode/agents/` (7 subagentes).
- `.opencode/commands/` (7 comandos slash).
- `.opencode/bin/weaviate-mcp.sh`: wrapper que carga `.env.local` y arranca
  `mcp-weaviate` con flags resueltos en runtime, evitando inline de
  secretos.
- `.opencode/bin/patch-mcp-weaviate.sh`: parche local para el bug de auth del
  paquete community `mcp-weaviate` v0.2.0.
- `~/.local/bin/opencode`: wrapper de usuario delante de `/usr/local/bin/opencode`
  en el `PATH`; carga el `.env.local` del workspace antes de abrir OpenCode.
- `~/.kimi-webbridge/bin/kimi-webbridge`: daemon local en `127.0.0.1:10086`
  usado por la skill `kimi-webbridge` cuando se necesita operar Kimi en navegador.
- `.opencode/plugins/` (vacío; los permisos cubren la política).

## 2. MCPs habilitados (conectados)

| MCP | Tipo | Auth | Notas |
|---|---|---|---|
| `docs-langchain` | remote | ninguna | LangGraph / LangChain / LangSmith docs. |
| `weaviate-docs` | remote | OAuth/login interactivo si lo pide kapa.ai | Docs actualizados de Weaviate. Ya autenticado en esta sesión. |
| `sequential-thinking` | local (npx) | ninguna | Razonamiento ramificado. |
| `playwright` | local (npx) | ninguna | Automatización de navegador. |
| `chrome-devtools` | local (npx) | ninguna | Debug de páginas vía DevTools. |
| `github-official` | local Docker (`ghcr.io/github/github-mcp-server`) | env `GITHUB_PERSONAL_ACCESS_TOKEN` | GitHub MCP oficial en modo read-only con `GITHUB_READ_ONLY=true`. |
| `tavily` | local wrapper hacia MCP remoto | env `TAVILY_API_KEY` | `.opencode/bin/tavily-mcp.sh` usa `mcp-remote` contra `https://mcp.tavily.com/mcp/`. |
| `brave-search` | local (npx) | env `BRAVE_SEARCH_API_KEY` | MCP oficial Brave Search (`@modelcontextprotocol/server-brave-search`). |
| `gh_grep` | remote | ninguna | `https://mcp.grep.app` para busqueda en GitHub/repos publicos. |
| `deepwiki` | remote | ninguna | `https://mcp.deepwiki.com/mcp` para contexto y explicaciones de repos GitHub. |
| `exa` | local wrapper hacia MCP remoto | env `EXA_API_KEY` | `.opencode/bin/exa-mcp.sh` habilita `web_search_exa`, `web_search_advanced_exa`, `web_fetch_exa`. |
| `huggingface` | remote | header `Authorization: Bearer {env:HF_TOKEN}` | MCP oficial de Hugging Face en `https://huggingface.co/mcp`. |
| `neo4j` | local (`uvx mcp-neo4j-cypher`) | env (`.env.local`) | Servidor oficial `neo4j-contrib/mcp-neo4j-cypher` v0.6.0. Forzado **read-only** con `--read-only`. Apunta a `bolt://localhost:7688` (compose). |
| `weaviate` | local (`mcp-weaviate` via wrapper) | APIKey en `.env.local` | Paquete community `mcp-weaviate` v0.2.0 con parche local de auth; usa `WEAVIATE_URL`, `WEAVIATE_API_KEY` y `WEAVIATE_GRPC_PORT=50052` desde env. Conexión verificada contra Weaviate 1.29.0. Writes no se deben pedir salvo confirmación explícita. |
| `memory-bank` | local (`npx @allpepper/memory-bank-mcp`) | env `MEMORY_BANK_ROOT` | Memory Bank MCP de `alioshr/memory-bank-mcp`, aislado en `memory-bank/` dentro del workspace. |
| `context7` | remote | header `CONTEXT7_API_KEY` desde env | Docs actualizados de cualquier librería. Server v2.2.5. |
| `langsmith` | local (`uvx langsmith-mcp-server`) | env `LANGSMITH_API_KEY` | Server oficial `langchain-ai/langsmith-mcp-server` v0.1.1. Tools de **lectura**: `fetch_runs`, `list_projects`, `list_datasets`, `list_examples`, `list_experiments`, `get_thread_history`, `get_billing_usage`. |
| `supermemory` | remote (`https://mcp.supermemory.ai/mcp`) | `Authorization: Bearer` + `x-sm-project` desde env | Memoria persistente cross-sesión v4.0.0. Scopeada al proyecto `cognitive-os`. Para uso correcto: ver skill `supermemory-context`. |

## 3. MCPs deshabilitados

Ya no quedan MCPs sensibles deshabilitados.

## 4. MCPs no instalados (decisión explícita)

- **Filesystem MCP**: el repo ya es accesible por OpenCode; instalar solo si
  hace falta acceso fuera del workspace.
- **OpenAPI MCP**: no hay `openapi.{yaml,json}` ni `swagger.json` en el repo.
- **Browserbase**: no se requiere browser cloud; Playwright local cubre.
- **Supabase, PostgreSQL, Notion, Linear, Atlassian, Sentry, Stripe,
  Firecrawl, Neon, LaunchDarkly, Cloudflare, Vercel, Figma, Slack**: no
  detectados en el stack actual.

## 5. Skills creadas (`.opencode/skills/`)

- `planning-with-files`
- `project-onboarding`
- `systematic-debugging`
- `code-review`
- `rag-architecture-review`
- `langgraph-agent-workflow`
- `neo4j-graphrag`
- `weaviate-rag`
- `supermemory-context`
- `web-research-mcps`
- `memory-bank`
- `dual-memory-recall`
- `huggingface-hub`
- `kimi-webbridge`
- `opencode-operator`

## 6. Subagentes creados (`.opencode/agents/`)

- `repo-architect` (read-only)
- `rag-engineer`
- `graph-memory-engineer` (Neo4j read-only por defecto)
- `vector-search-engineer` (Weaviate writes off)
- `test-engineer`
- `security-reviewer` (read-only)
- `devops-engineer`

## 7. Comandos slash (`.opencode/commands/`)

| Comando | Para qué |
|---|---|
| `/plan <tarea>` | Genera/actualiza `task_plan.md`, `findings.md`, `progress.md` sin editar código. |
| `/continue-plan <foco>` | Continúa el siguiente paso pendiente del plan. |
| `/review <ruta o diff>` | Revisión de código sin editar. |
| `/debug <síntoma>` | Workflow de depuración sistemática. |
| `/rag-review <área>` | Revisa la arquitectura RAG/agentes. |
| `/mcp-check <ámbito>` | Audita MCPs, secretos y permisos. |
| `/verify <área>` | Ejecuta validaciones reales del proyecto. |

## 8. Variables

### Ya configuradas en `.env.local` (ignorado por git)

| Integración | Variable | Origen |
|---|---|---|
| Neo4j | `NEO4J_URI` | importado de `cognitive-os/.env` |
| Neo4j | `NEO4J_USERNAME` | mapeado desde `NEO4J_USER` |
| Neo4j | `NEO4J_PASSWORD` | importado |
| Neo4j | `NEO4J_DATABASE` | `neo4j` (default) |
| Weaviate | `WEAVIATE_URL` | importado (`http://localhost:8081`) |
| Weaviate | `WEAVIATE_API_KEY` | importado |
| Context7 | `CONTEXT7_API_KEY` | dado por el usuario |
| LangSmith | `LANGSMITH_API_KEY` | personal access token |
| LangSmith | `LANGSMITH_ENDPOINT` | `https://api.smith.langchain.com` |
| Supermemory | `SUPERMEMORY_API_KEY` | dado por el usuario (cuenta Supermemory) |
| Supermemory | `SUPERMEMORY_PROJECT` | `cognitive-os` (scoping) |
| Web search | `WEB_SEARCH_ENABLED` | `true` para habilitar `search_web` runtime |
| Perplexity | `PERPLEXITY_API_KEY` | dado por el usuario para Search/Grounding |
| Perplexity | `PERPLEXITY_BASE_URL` | `https://api.perplexity.ai` |
| Tavily | `TAVILY_API_KEY` | dado por el usuario para MCP y runtime web search |
| Brave | `BRAVE_API_KEY` | dado por el usuario para runtime web search |
| Brave | `BRAVE_SEARCH_API_KEY` | dado por el usuario para Brave MCP/Search |
| Brave | `BRAVE_ANSWER_API_KEY` | dado por el usuario para Answer API |
| Brave | `BRAVE_FREE_API_KEY` | dado por el usuario para Free API |
| Exa | `EXA_API_KEY` | dado por el usuario para MCP y runtime web search |
| Hugging Face | `HF_TOKEN` | dado por el usuario para Hugging Face MCP |
| Hugging Face | `HUGGING_FACE_HUB_TOKEN` | mismo token para SDKs/CLI si aplica |
| GitHub | `GITHUB_PERSONAL_ACCESS_TOKEN` | dado por el usuario para GitHub MCP |
| GitHub | `GITHUB_READ_ONLY` | `true` |
| GitHub | `GITHUB_TOOLSETS` | `repos,issues,pull_requests,actions,code_security,users` |
| Memory Bank | `MEMORY_BANK_ROOT` | `/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/memory-bank` |
| Kimi WebBridge | daemon local | `127.0.0.1:10086`, no guardar cookies/tokens en docs |

> Cuando agregues nuevas variables, hazlo en `.env.local`. Nunca inline en
> `opencode.json` ni en archivos versionados.

## 9. OAuth pendiente

- `github` MCP remoto oficial. Tras revisar `opencode.json`, ejecuta:

  ```bash
  opencode mcp auth github
  ```

  Si tu org exige PAT, dime y migramos a la variante con
  `Authorization: Bearer {env:GITHUB_PERSONAL_ACCESS_TOKEN}`.

## 10. Riesgos de seguridad

- `cognitive-os/.env` y `cognitive-os-backup-*/.env` contienen secretos
  reales (`DATABASE_URL` con password en backup). Ya están cubiertos por
  `.gitignore`, pero no los subas y considera rotarlos.
- `opencode.json` fue saneado para usar `{env:VAR}`. Si alguna vez tuvo tokens
  inline, rotarlos desde el proveedor correspondiente aunque ya no estén en el
  archivo.
- Habilitar `neo4j`/`weaviate` MCPs aumenta superficie. Mantén Neo4j
  `READ_ONLY=true` y Weaviate `WRITE_ACCESS=false` salvo confirmación
  explícita.
- `playwright` y `chrome-devtools` permiten automatización local: úsalos
  solo cuando no exista API.
- `bash` por defecto está en `ask`; las reglas `deny` cubren `rm`,
  `git reset --hard`, `git push --force`, `docker system prune`,
  `terraform destroy`, `kubectl delete`. Revisa antes de ampliar `allow`.

## 11. Cómo revertir cambios

- `.gitignore`: restaurar desde `.gitignore.bak-20260513-021119`.
- `AGENTS.md` y `opencode.json`: no existían antes; eliminarlos basta.
- `.opencode/`: directorio nuevo; eliminarlo lo deshabilita todo.
- Git: usar `git status` y `git diff` para revertir selectivamente; no usar
  `git reset --hard` salvo orden explícita.

## 12. Próximos pasos recomendados

1. Ejecuta `opencode mcp auth github` para completar OAuth de GitHub.
2. (Opcional) Exporta `CONTEXT7_API_KEY` / `LANGSMITH_API_KEY` y pon
   `enabled: true` en sus bloques de `opencode.json`.
3. Lanza `/mcp-check` para auditar la config en vivo.
4. Si quieres permisos más estrictos en `edit`, cambia `"edit": "ask"` a
   `"edit": "deny"` y añade overrides por agente.
5. Limpia el MCP `git` roto de tu config global de OpenCode
   (`~/.config/opencode/...`) si no lo usas.
6. Abre OpenCode desde terminal con `opencode`. El wrapper
   `~/.local/bin/opencode` carga `.env.local` automáticamente antes de abrir
   la UI.

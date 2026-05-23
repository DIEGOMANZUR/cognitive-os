# QA · MAP — inventario funcional de la app

> **Actualización vigente (2026-05-23, commit `647f103`):** mapa QA para
> el cockpit actual. La suite oficial Playwright está verde con **31
> passed** y se ejecuta contra la SPA Next.js de 20 tabs sin necesidad
> de exportar `COGOS_JWT` (auto-mint via `_global-setup.ts`). Backend
> verificado por `full-qa.sh`: **950 passed**, 1 skipped, 28 deselected
> (944 históricos + 6 nuevos para regresión del bug `eager_defaults`).
> El producto corre en un PC dedicado con prioridad de fricción casi
> nula; los tests deben validar que esa fricción baja no esconda
> errores, pantallas muertas ni operaciones silenciosas. Mail sigue
> siendo read-only/digest por defecto. MCP actual: `/system/mcp` runtime
> 5/5 servers y 67 tools.
>
> Doble re-auditoría TestSprite 2026-05-23 cerrada: **10/10** passed,
> 1 P1 nuevo cazado y corregido (eager_defaults), 16/16 hallazgos
> previos verificados. Reporte:
> [`../audits/testsprite/16_FINAL_REAUDIT_REPORT.md`](../audits/testsprite/16_FINAL_REAUDIT_REPORT.md).
>
> La auditoría Fase 76 (2026-05-20) queda como base histórica. Datos
> extraídos del código real, no del README.

## Framework y arquitectura

- **Frontend:** Next.js 16.2.6 (App Router) · React 19 · TypeScript 5.8.
  SPA con UN SOLO route segment (`app/page.tsx`); las "páginas" del panel
  son **20 tabs** intercambiables sin cambio de URL, controladas por el
  state local `tab: Tab` con persistencia en `localStorage`
  (`cogos.tab`).
- **Backend:** FastAPI 0.115+ en `http://127.0.0.1:8000` — 147
  decoradores REST con JWT bearer. CORS abierto a `:3000` y `:3001`.
- **Datos:** Postgres 16+pgvector + Redis 7 + Weaviate 1.29 + Neo4j 5.
  Los 4 ligados a `127.0.0.1`.
- **Bot:** Telegram long-poll (no afecta E2E web).

## Rutas web

| URL | Componente | Notas |
|---|---|---|
| `http://localhost:3001/` | `app/page.tsx` (SPA) | Única ruta real. La vista activa la decide el state `tab`. |
| `/manifest.webmanifest` | `app/manifest.ts` | PWA manifest. |
| `/sw.js` | `public/sw.js` | Service worker que excluye `/api/*` del cache. |

## Tabs (20 vistas)

```
dashboard · chat · agents · skills · memory · assist · googleOps · mail ·
documents · documentAnalysis · jobs · approvals · sandbox · research ·
codeDirector · langsmith · audit · health · configuration · settings
```

Cada tab vive como `app/views/<Name>View.tsx`. La navegación es
`Sidebar.tsx`: una lista de `<button>` con texto del tab; en mobile el
sidebar abre/cierra con un `aria-label="Abrir menú"`/"Cerrar".

## Flujos críticos a auditar

1. **Carga inicial sin JWT.** `app/page.tsx` muestra TopBar con campo JWT
   + un placeholder con instrucciones; las views deberían renderizar
   estado "no auth" sin romper.
2. **Pegado de JWT** (Settings o TopBar) → polling de `/health/dashboard`,
   `/config/public`, `/knowledge/stats` debe empezar y producir datos
   reales (overall `ok` o `configured`, 18 componentes).
3. **Navegación entre tabs** — cambiar a cada una de las 20 sin
   pantalla blanca ni `console.error`.
4. **Refresh de página** — el JWT debe persistir (`useLocalState("cogos.token")`).
5. **Health dashboard** — 18 componentes con badges ok/configured/ready;
   botón "Verificar en vivo" (`POST /health/verify`) y tile "Backlog
   operacional".
6. **Settings tiles nuevos** — "Capacidades bloqueadas"
   (`/system/readiness`) y "MCP servers" (`/system/mcp`).
7. **ConfigurationView** — tabla de flags, marca danger por perfil
   (`strict` invierte vs `dedicated_local`).
8. **Mobile (375x667)** — Sidebar colapsa, TopBar usable, vistas no
   overflow.
9. **Chat con JWT (smoke)** — submit envía y recibe respuesta o muestra
   estado de loading consistente.

## Endpoints clave consumidos por la UI

| Endpoint | Vista que lo usa |
|---|---|
| `GET /health` | DashboardView (public) |
| `GET /health/dashboard` | HealthView, DashboardView |
| `GET /config/public` | SettingsView, ConfigurationView, CodeDirectorView |
| `GET /system/info` | DashboardView |
| `GET /system/readiness` | SettingsView (tile gaps) — Fase 72 |
| `GET /system/mcp` | SettingsView (tile MCP) — Fase 73 |
| `GET /knowledge/stats` | DashboardView |
| `GET /actions/capabilities` | SettingsView |
| `GET /actions/requests?limit=N` | SettingsView, ApprovalsView |
| `GET /actions/maps/status` + `POST /actions/maps/route` | GoogleOpsView |
| `GET /actions/calendar/status` + `/list` | GoogleOpsView |
| `GET /actions/drive/status` + `/search` | GoogleOpsView |
| `GET /jobs`, `/jobs/{id}`, `/jobs/{id}/events` | JobsView |
| `GET /approvals`, `POST /approvals/{id}/approve` | ApprovalsView |
| `POST /chat`, `GET /threads`, `GET /threads/{id}/messages` | ChatView |
| `GET /code-director/{id}` + SSE `/events` | CodeDirectorView |
| `GET /research/runs/{id}` + SSE `/events` | ResearchView |
| `GET /mail/messages`, `POST /mail/sync/dispatch`, `POST /mail/digest/preview`, `POST /mail/digest/dispatch` | MailInboxView |
| `GET /assist/tasks`, `/assist/notes` | AssistView |
| `GET /sandbox/openshell/status`, `POST /sandbox/openshell/run` | SandboxView |
| `GET /deepagents/memory/proposals` | MemoryView · propuestas |
| `GET /deepagents/memory/recipes` | MemoryView · Recetas (Fase A) |
| `GET /deepagents/memory/warnings` | MemoryView · Warnings (Fase D) |
| `GET /deepagents/learning/tool-scorecard` | MemoryView · Scorecard (Fase C) |
| `GET /deepagents/learning/skill-promotions` | MemoryView · Promociones a skill (Fase B) |
| `GET /deepagents/learning/reflection` | MemoryView · Reflexiones nocturnas (Fase E) |
| `GET /skills` | SkillsView |
| `GET /audit/events` | AuditView |
| `GET /langsmith/runs` (admin) | LangSmithView |

## Formularios principales

- **TopBar:** API base + JWT (`useLocalState("cogos.token")`).
- **Settings:** misma idea + tile readiness + tile MCP.
- **ChatView:** textarea + submit → `/chat`.
- **GoogleOpsView:** origen/destino (Maps), datetime-local (Calendar
  event), query (Drive), upload path/name. Botones de write disabled
  cuando `write_enabled=false`.
- **CodeDirectorView:** objetivo + adapter + modelo + max runtime/calls +
  checkbox sandbox (disabled si OpenShell off).
- **AssistView:** task title + description, note title + body.
- **DocumentAnalysisView:** doc_ids, modes (checkboxes).
- **SandboxView:** purpose (required) + comando.

## Roles de usuario

- **operator** (default): puede leer todo, pegar JWT, navegar todas las
  vistas. Los endpoints REST validan rol antes de aceptar mutaciones.
- **admin** (`ADMIN_USER_IDS` o `roles=['admin']` en JWT): habilita
  `/system/credentials-status`, mutaciones de memoria DeepAgent y
  endpoints LangSmith.
- Sin JWT: la mayoría de tabs muestran "no autenticado" o tabla vacía;
  no rompen.

## Dependencias externas (live calls)

| Dependencia | Quién la usa | Si cae |
|---|---|---|
| Postgres | TODO el backend | API levanta con `MemorySaver`, jobs/auth fallan |
| Redis | Celery + rate limiter | API responde; jobs no encolan |
| Weaviate | RAG (DeepAgent) | retorna `[]`; chat sin evidencia |
| Neo4j | Grafo entidades | ingesta avisa, chat no afectado |
| LLM gateway (gpt-5.5) | Chat, DeepAgent, router | router cae a deterministic |
| Google APIs | Maps/Calendar/Drive/Gmail | componentes `blocked` |
| Kimi WebBridge daemon | KimiWebBridgeService | componente `degraded` |
| GoDaddy API | DNS preview | endpoint reporta `blocked` |
| MCP servers (mem/gh/fs/cc/gem) | DeepAgent dynamic tools | cada server falla aislado; inventario paralelo con timeout 30s |

## Riesgos funcionales identificados

1. **SPA monolítica:** una excepción en una vista podría tumbar todo si
   el `ErrorBoundary` no la atrapa. Verificar.
2. **Polling agresivo:** algunas vistas usan `usePolledFetch` con
   intervalos cortos (10-30s). Con JWT inválido se podría inundar la
   consola con 401s.
3. **JWT en localStorage:** correcto post-Fase 71-H, pero si está
   corrupto se rompería el `JSON.parse` del hook.
4. **Tabs sin URL:** no se puede deep-linkear ni copiar URL. Refresh
   vuelve a la última tab guardada (`cogos.tab`).
5. **Service worker:** puede servir HTML cacheado obsoleto tras un
   deploy. El SW excluye API pero no HTML.
6. **CORS:** default cubre :3000/:3001; deploy en otro origen necesitaría
   `CORS_ALLOW_ORIGINS`.
7. **Console.error en producción:** logs no estructurados; un error
   ruidoso en una vista pasaría inadvertido. La suite E2E debe fallar
   ante `console.error` inesperado.

## Resultado esperado de la suite

- `npm run build` verde.
- `npm run lint` 0 warnings.
- Playwright E2E pasa completo en chromium.
- 0 `console.error` no esperados.
- 0 respuestas 5xx en flujos críticos.
- Cobertura de las 20 tabs en `navigation.spec.ts`.

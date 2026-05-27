# QA · MAP — inventario funcional de la app

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-27, Prompt 7):** esta rama `codex/commercial-zero-friction-hardening` en base `8a33475d0502` queda sincronizada para el cierre comercial local-first. La evidencia viva se concentra en `/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/tmp/v2_07_absolute_release_closure_20260527_050231`. Estado de producto verificado durante Prompt 7: backend FastAPI local, frontend Next.js, Docker services, Postgres, Redis, Weaviate, Neo4j, Alembic head, worker, beat, health/readiness, LangGraph/chat, DeepAgents, MCP, RAG/documentos, Document Analysis, Action Plane sandbox, mail read-only, Telegram, Google read-only, GoDaddy dry-run, Kimi WebBridge y Code Director toy/guard rails.
>
> **Gates V2.0 ejecutados antes de los dos ciclos verdes finales:** `bash scripts/full-qa.sh` **1221 passed, 1 skipped, 28 deselected**; `bash scripts/stress-qa.sh 5` **5/5 verde x 1221 passed**; `cd frontend && npx playwright test` **44 passed**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/sync_doc_counts.py --check` OK; `bash scripts/verify_desktop_launchers.sh` OK; OpenAPI read-only smoke **70 GET / 0 failures**; security read-only scan sin secretos críticos; CDP/Playwright forense **10 ciclos x 20 vistas** sin console/page errors ni 5xx, con un aborto `POST /auth/local-token` adjudicado como cierre de contexto del harness y no defecto de producto; Lighthouse local: accessibility 96, best-practices 100, SEO 100.
>
> **Criterio de verdad:** no se declara envio de correo, draft real ni escritura DNS. Mail queda normalizado como read-only: sync/list/classify/digest/proposed replies como texto, sin drafts ni sends. GoDaddy queda preview/dry-run; Action Plane mantiene sandbox/approval/audit/idempotencia segun riesgo. El tunnel publico `cognitive.doctormanzur.com` se valida con `scripts/testsprite_web/deploy_and_verify.sh` cuando Diego vaya a correr TestSprite web; Prompt 7 no lo expone permanentemente porque su propia regla prohibe exponer servicios a internet.

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


> **Actualización vigente (2026-05-26, HEAD `8a33475`):** cockpit público
> endurecido para TestSprite web sobre la base local-first 2026-05-25. El mapa QA
> debe considerar el frontend real en `https://cognitive.doctormanzur.com`, auth
> por `#cogos_token`, API pública automática, shell sin TopBar con
> `data-cogos-active-tab`, hotkey `3 DeepAgents`, estados comerciales
> loading/empty/error sin datos falsos, responsive 920px y service worker
> `cogos-v2026-05-26e-status-cards`. Suite local: Playwright **43 passed**,
> `full-qa.sh` **1200 passed**, `stress-qa.sh 5` **5/5 verde × 1200 passed**.
> TestSprite local batched histórico: **28/28 passed**. TestSprite web público se
> prepara con `scripts/testsprite_web/deploy_and_verify.sh`; no afirmar dos
> corridas web verdes hasta recibir reportes del portal.
>
> **Audit-commercial hardening matrix** — 16 archivos de test (~230
> asserciones) introducidos en commit `0f8232a` cubren los 4
> P0-críticos y 12 GAPs P1 que el mapa de contrato había marcado
> entre "happy-path verificado" y "todos los caminos bajo regresión":
> Mail SMTP gate, GoDaddy DNS gate, Code Director STDIN-only,
> eager_defaults full matrix, auth matrix completa, path-traversal
> corpus, operational_backlog reactivo, workflow.v1 hardening,
> calendar/drive directo `dry_run=false`→409, health overall honest,
> reapers dedicados, DB isolation, secrets redaction, fixtures
> gating, MCP fail-open, Mail UI sin botón Enviar.
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
| `/sw.js` | `public/sw.js` | Service worker `cogos-v2026-05-26e-status-cards`; los prefijos REST son network-only. |

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

1. **Carga inicial sin JWT.** `app/page.tsx` debe renderizar la shell estable sin romper, mostrar estados no-auth/empty/error honestos y aceptar bootstrap posterior por `#cogos_token` o localStorage.
2. **Activación de JWT** (fragmento `#cogos_token`, localStorage o Settings) → polling de `/health/dashboard`,
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
8. **Mobile (375x667)** — Sidebar se desmonta fuera del drawer, bottom nav usable, vistas no
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

- **Shell/auth:** hash `#cogos_token`, `localStorage.cogos.token`, API base por host y Settings (`useLocalState("cogos.token")`).
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
| MCP servers (mem/gh/fs/cc/gem/time) | DeepAgent dynamic tools | cada server falla aislado; inventario paralelo con timeout 30s; `time` es local read-only para hora/conversion de zonas |

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

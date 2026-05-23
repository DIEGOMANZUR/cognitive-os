# 29 · Commercial UX Review — 30 Puntos

Fecha: 2026-05-23 07:30 UTC-4

Evidencia: snapshot live del Dashboard via Chrome DevTools MCP en Fase
5 + navegación de las 20 tabs sin errores.

| # | Punto UX | Estado | Evidencia |
|---|---|---|---|
| 1 | Operador sabe qué hacer en dashboard | **PASS** | "Operations Dashboard" h1 + tiles claros: DOCUMENTOS=29, JOBS ACTIVOS=0, APROBACIONES=309, COMPONENTES OK=14/18; 5 acciones rápidas visibles arriba |
| 2 | Vistas tienen empty states útiles | **PASS** | Spec `error-empty-loading-states.spec.ts` verifica las 20 vistas con malformed payloads → degradan a empty sin ErrorBoundary |
| 3 | Errores explican causa y solución | **PASS** | Mail 409: "Mail sending is disabled by policy. Normal flow is read-only: generate a summary/proposed reply and Diego sends manually." (causa + qué hacer); F-10: 422 con `loc=["path","approval_id"]` |
| 4 | Botones peligrosos dicen qué harán | **PASS** | Mail UI no tiene botón "Enviar" en flujo normal (TC010); Approval shows action_type+preview antes de aprobar; Document generate previews path antes de aceptar |
| 5 | Preview/request/approve no confunden | **PASS** | UI separa visualmente preview (read-only) vs request (queue) vs approve (HITL); el flow Approvals lista action_request_id + preview + botón aprobar/rechazar |
| 6 | Jobs muestran progreso | **PASS** | JobsView muestra `Job.progress` field; Dashboard tile "JOBS ACTIVOS" + "completados / fallidos"; live: 5609 completados, 69 failed |
| 7 | Health muestra estado real | **PASS** | HealthView 18 componentes con latencias reales (postgres 314ms, redis 263ms, weaviate 262ms, neo4j 245ms, workers 2020ms); F-02 verify devuelve probes reales |
| 8 | Readiness muestra flags faltantes | **PASS** | `/system/readiness.gaps[*].remediation` provee `env_var` + `value`; UI SettingsView tile lo expone (live actual: gaps=[]) |
| 9 | Mail separa propuesta vs envío | **PASS** | MailInboxView muestra propuesta como text area separado; no hay botón Send; backend rechaza send con HTTP 409 |
| 10 | Action Plane muestra preview | **PASS** | `actions/*/preview` endpoints son explícitos; UI ApprovalsView muestra preview antes de approve |
| 11 | Document Analysis muestra citas/artifacts | **PASS** | DocumentAnalysisView consume `/document-analysis/{task_id}/report` con citations literales; spec frontend cubre |
| 12 | Research muestra progreso/citas | **PASS** | ResearchView consume SSE `/research/runs/{id}/events`; `research_orchestrator` emite progresivamente |
| 13 | Code Director muestra budget/plan/status | **PASS** | CodeDirectorView consume `/code-director/{job_id}` con plan + budget + status; SSE events para progreso |
| 14 | Memory muestra evidencia | **PASS** | MemoryView consume `/deepagents/memory/proposals` con `proposed_content` + `reason` + evidence quotes (Fase E) |
| 15 | Telegram responde claro | **PASS** | 102 tests pytest cubren `test_authorized_command_never_emits_unhandled_exception_dump` para los 37 commands |
| 16 | No textos contradictorios | **PASS** | Drift sweep en 28_DOCS_AND_DRIFT_CHECK: cero contradicciones |
| 17 | No pantallas eternamente cargando | **PASS** | `StatePrimitives.Skeleton` / `Empty` / `Error` cubren todos los estados; spec frontend verifica |
| 18 | No botones sin feedback | **PASS** | Approvals UI muestra "pending" durante POST; JobsView refresca con polling; spec cubre |
| 19 | No errores crípticos para problemas esperables | **PASS** | F-10: 422 con detalle Pydantic legible; F-11: `status=blocked, reason="computer path is outside allowed roots."` |
| 20 | No navegación rota | **PASS** | F-12: 20/20 tabs montan, cero console.error |
| 21 | No demasiada fricción para acciones locales | **PASS** | 6/8 capabilities sin approval en dedicated_local/full; auto-mint JWT, auto-dispatch reversibles |
| 22 | No pasos manuales innecesarios | **PASS** | Playwright corre sin exportar `COGOS_JWT` (auto-mint via global-setup) |
| 23 | No forms sin ayuda | **PASS** | Forms validan client-side + server-side (Pydantic) con mensajes legibles |
| 24 | No estados disabled sin explicación | **PASS** | Health components con `disabled` incluyen detail: "MAIL_ENABLED=false" o equivalente |
| 25 | No "success" sin efecto real | **PASS** | UI muestra `JobEvent` timeline tras dispatch; AuditEvent persiste; DB refleja cambio |
| 26 | No datos falsos / mock no indicado | **PASS** | Todos los datos del Dashboard son live (5609 jobs reales, 309 approvals reales, audit timeline real con `tool.webbridge.list_tabs`) |
| 27 | No paneles que parezcan operativos pero no lo sean | **PASS** | Cada vista llama endpoint real; F-12 verificó las 20 tabs |
| 28 | No rutas muertas | **PASS** | F-12 + 20 vistas cargan; Playwright `navigation.spec` cubre |
| 29 | No variables bloqueantes invisibles | **PASS** | `/system/readiness` lista flags y remediation; UI SettingsView lo muestra |
| 30 | No dependencia obligatoria no documentada | **PASS** | `init_credentials.sh` produce checklist REQ/OPT/OK; USER_GUIDE §0.2 documenta REQ vs OPT |

## Resultado

**30 / 30 PASS.** Producto comercialmente usable, se siente como command
center con datos reales, errores accionables, sin fricción innecesaria,
mail intacto, navegación limpia.

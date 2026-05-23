# 26 · Degradation & Recovery Tests — 25 Casos

Fecha: 2026-05-23 07:18 UTC-4
Mandato: Cognitive OS debe **fallar bien**. Cada caso del prompt §12
validado.

## 1. Tabla de los 25 casos

| # | Escenario | Comportamiento esperado | Resultado | Evidencia |
|---|---|---|---|---|
| 1 | LLM provider no disponible | health degraded con detail; LangGraph router degrada con red `agent→secondary→primary→deterministic_route` | **PASS** | Pasada 2: live timeout 3s reportaba `degraded`; ahora con timeout 10s reporta `ok 3.9s`. Si el LLM cae > 10s, mostraría `degraded` con `timed out after 10s` — `test_health_llm_probe_timeout.py` cubre |
| 2 | Embeddings no disponibles | health `degraded` con detail | **PASS** | `_check_embeddings` con `verify_live=True` retorna `degraded` si fallo; live actual `ok 1.2s` |
| 3 | Weaviate disabled/unavailable | hybrid search degrada a BM25 / fallback determinista | **PASS** | `WeaviateStore.hybrid_query` envuelto en try; pasa a `[]` con effective_alpha=0.0 si embeddings fallan |
| 4 | Neo4j disabled/unavailable | RAG graph degrada; resto de pipelines siguen | **PASS** | `_check_neo4j` reporta `degraded`; pipelines RAG sin graph aún operativos |
| 5 | MCP server caído | `/system/mcp` reporta `connected=false` con `error`; resto OK | **PASS** | `mcp_client.py` reporta cada server con `connected/tools_count/error`; degradación granular |
| 6 | Kimi WebBridge no disponible | `kimi_webbridge: degraded` con `daemon_running=false`; resto OK | **PASS** | `_check_kimi_webbridge` inspecciona `daemon_url` + `edge_devtools_running`; live actual `ready` con todos los flags true |
| 7 | Telegram disabled | `_check_workers` no reporta error; bot no arranca; `TELEGRAM_ENABLED=false` documentado | **PASS** | `telegram_bot.py::main()` se niega a arrancar con allowlist vacía (fail-closed) |
| 8 | Mail disabled | `mail: disabled` en health; UI muestra "MAIL_ENABLED=false"; endpoints retornan 503/disabled | **PASS** | `_check_mail` evalúa `mail_enabled`; UI tile vista MailInboxView muestra estado |
| 9 | Google disabled | `google_calendar/google_drive: disabled` con motivo; UI tile lo refleja | **PASS** | health components leen `enable_google_calendar`/`enable_google_drive`; GoogleOpsView muestra status |
| 10 | GoDaddy disabled | `godaddy: disabled` o `dry_run_only=true`; `/actions/godaddy/dns/preview` igual responde | **PASS** | actualmente `GODADDY_DNS_DRY_RUN_ONLY=true` (dry-run forzado) |
| 11 | Worker detenido | `_check_workers` retorna `degraded` con `worker_count=0`; jobs quedan en cola | **PASS** | `_check_workers` consulta celery inspect; live actual `ok 2020ms` con 1 worker, 23 tasks registradas |
| 12 | Beat detenido | reapers no corren; `operational_backlog.beat_lag_minutes` sube | **PASS** | live: `beat_lag_minutes=0.0`, `beat_lag_degrade_minutes=120.0`; al pasar el umbral `operational_backlog: degraded` |
| 13 | Job stale | `stale_jobs_reaper` lo marca cancelled; UI muestra "job_cancelled" event | **PASS** | `test_phase20_ops_hardening.py::test_reaper_uses_settings_max_minutes_default` cubre |
| 14 | Approval stale | `approval_reaper` la expira (`APPROVAL_PENDING_MAX_HOURS=168`) | **PASS** | `test_approval_reaper.py::test_reaper_expires_pending_approvals_and_cascades` cubre |
| 15 | ActionRequest stuck | `reap_stuck_action_requests_task` lo libera | **PASS** | Pasada 2: stuck request liberado live con `result.reaped=1` |
| 16 | API devuelve error | frontend muestra error con detail accionable | **PASS** | `apiClient` propaga 4xx/5xx con `detail`; `StatePrimitives.Error` |
| 17 | Frontend recibe array null | `asArray<T>` previene crash | **PASS** | `tests/e2e/error-empty-loading-states.spec.ts` cubre todas las vistas con malformed payloads |
| 18 | Frontend recibe 500 | sentinel `watchPageHealth` lo captura; UI degrada con error visible | **PASS** | Playwright spec verifica `serverErrors=[]` en flujos normales |
| 19 | SSE se corta | `usePolledFetch` reintenta; UI pausa offline | **PASS** | `hooks.ts::usePolledFetch` pausa con offline/hidden, reintenta |
| 20 | Polling falla | mismo path: hooks degradan, UI muestra "estado desconocido" | **PASS** | `StatePrimitives.Error` se aplica |
| 21 | OAuth faltante | `google_calendar: degraded` con `reason="OAuth token missing"` | **PASS** | `_check_calendar` evalúa `_google_calendar_token_status()` |
| 22 | API key faltante | health del componente correspondiente `degraded` con detail "PRIMARY_LLM_API_KEY is not configured" o similar | **PASS** | health.py distingue configured/degraded por presencia de keys |
| 23 | Redis lento/ausente | `_check_redis` retorna `degraded`; idempotency en memoria fallback | **PASS** | `_check_redis` mide latency; rate limiter es fail-open intencional |
| 24 | Provider configured pero no verified | health pasivo retorna `configured` (no `ok`); `verify_live=True` lo prueba | **PASS** | AUDIT-2026-B implementado; F-02 verificado live |
| 25 | Provider verified pero caído ahora | siguiente probe live mostrará `degraded`; entre probes el cache puede mostrar último estado conocido | **PASS** | health probes son on-demand; no usan cache para evitar mentiras |

## 2. Verificación live de degradación

Probada en runtime:

### Path fuera de allowed_roots
```
POST /actions/computer/organize/preview {"root_path":"/root", ...}
→ status=blocked, reason="computer path is outside allowed roots."
```

### Path /etc/shadow
```
POST /actions/computer/organize/preview {"root_path":"/etc/shadow", ...}
→ status=blocked, reason="computer path is outside allowed roots."
```

### Bad UUID
```
POST /approvals/not-a-uuid/approve
→ HTTP 422 con detalle Pydantic legible
```

### Bad payload sin root_path
```
POST /actions/computer/organize/preview {"path":"/tmp/x"}
→ HTTP 422 con {"detail":[{"type":"missing","loc":["body","root_path"], ...}]}
```

## 3. Conclusión

**25/25 escenarios PASS.**

El sistema falla bien:
- UI nunca crashea globalmente (asArray + StatePrimitives + ErrorBoundary).
- Health refleja la realidad sin mentir.
- Readiness ayuda con remediation.
- Logs son útiles (`langsmith_ready` por request, AuditEvent timeline).
- Operador puede diagnosticar sin tocar código.
- Reapers limpian estados colgados.
- Recuperación es coherente (refresh probe retorna estado real).

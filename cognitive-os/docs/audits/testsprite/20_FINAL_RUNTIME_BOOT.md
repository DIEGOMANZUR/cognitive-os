# 20 · Final Runtime Boot — Reboot Limpio Desde Cero

Fecha: 2026-05-23 07:03 UTC-4
Mandato: el cierre absoluto NO usa procesos viejos como evidencia. Stop
+ start controlados desde cero antes de validar.

## 1. Secuencia ejecutada

```
[07:02:50] ~/Escritorio/cognitive-os.sh stop
[07:02:55] verificado puertos 8000/3001/10086 vacíos
[07:03:00] docker compose (cognitive_os_*) sigue corriendo (no se tocó
            infra de datos — el contrato es no-destruir Postgres/Redis/
            Weaviate/Neo4j sin razón)
[07:03:05] ~/Escritorio/cognitive-os.sh start
[07:03:32] todos los servicios listos
```

## 2. Procesos arrancados

| Componente | PID | Endpoint |
|---|---|---|
| API uvicorn | 2031184 | http://127.0.0.1:8000/health |
| Celery worker | 2031279 | queues: default,ingestion,agent_longrun,maintenance,mail |
| Celery beat | 2031294 | tiered schedule (10 condicionales + 3 reapers) |
| Next.js frontend | 2031316 | http://localhost:3001 |
| Telegram bot | 2031428 | long-poll allowlist-gated |
| Kimi WebBridge | 2031xxx | http://127.0.0.1:10086 (Edge DevTools 9222) |

## 3. Verificación HTTP inmediata (sondeos sin live probe)

```bash
JWT=$(curl -sX POST http://127.0.0.1:8000/auth/local-token | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
```

### `/system/info`

```
git_commit: 9ab77a44946e   ← matchea HEAD 9ab77a4 ✓
profile:    dedicated_local
alembic:    202605200003
```

### `/system/readiness`

```
target_capabilities_unlocked: 14 / 14
gaps: []
summary: "Sin fricción. Todas las capacidades del perfil están activas."
```

### `/system/mcp`

```
5/5 servers connected: mem, gh, fs, cc, gem
67 tools totales
```

### `/health/dashboard`

```
overall = configured       (honesto — sin probe live)
ok        = 8   (postgres, redis, weaviate, neo4j, workers, langsmith,
                 operational_backlog, checkpointer)
configured = 4 (primary_llm, embeddings, mail, mcp_client)
ready     = 6   (voice, maps, google_calendar, google_drive,
                 kimi_webbridge, captcha_solver)
degraded  = 0
disabled  = 0
```

### Frontend `http://localhost:3001/`

```
HTTP/1.1 200 OK
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Cross-Origin-Opener-Policy: same-origin
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
```

## 4. Cero errores en boot

- API levantó sin warnings en log (`langsmith_ready` en cada request).
- Worker conectó las 5 colas, registró 23 tareas (`expected_task_count=23`).
- Beat agendó los 13 jobs sin conflictos.
- Frontend respondió a primer GET / con headers de seguridad correctos.
- Telegram allowlist no vacía → bot arrancó sin abort.
- Kimi WebBridge daemon listo + Edge DevTools listo + extensión
  conectada.

## 5. Perfil operativo validado tras reboot

`dedicated_local/full` activo, **14/14 capacidades**, gaps=[], "Sin
fricción", `require_human_approval=false`, `four_eyes=false`. El reboot
no degradó nada.

## 6. Sin reparación aplicada

El reboot fue limpio en una sola ejecución del launcher. No se requirió
ningún fix manual durante el boot.

## 7. Próximo paso

Fase 4 — regenerar mapa real del sistema (doc 21) y comparar con docs
canónicos.

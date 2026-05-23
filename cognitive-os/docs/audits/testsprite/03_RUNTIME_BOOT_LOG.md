# 03 · Runtime Boot Log

Fecha: 2026-05-23 04:00-07:00 UTC
Stack: ya levantado por la sesión anterior; no se relanzó nada al inicio
del audit para evitar interrumpir el trabajo del operador.

## 1. Capturas de entorno

```
git status: clean
git branch: codex/commercial-zero-friction-hardening
git rev-parse HEAD: 9b22f77
git diff 2c3cff6..HEAD: 34 files (docs+counts mostly; ver §11 del DISCOVERY MAP)
python: 3.12.3
uv: presente (backend/.venv activo)
docker: instalado, cognitive_os_{postgres,redis,weaviate,neo4j} healthy
node: usado por next-server v16.2.6
```

## 2. Procesos vivos (a 04:00 UTC)

| PID | Componente | Comando |
|---|---|---|
| 106597/106603 | API | `uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000` |
| 106744+ | Celery worker | `worker -Q default,ingestion,agent_longrun,maintenance,mail --loglevel=info` |
| 106760/106772 | Celery beat | `beat --loglevel=info` |
| 106787 | Frontend | `next-server (v16.2.6)` en `127.0.0.1:3001` (`next start` desde `.next/BUILD_ID=vBH-vqxLOrOv8e5lHn1Rf` del 2026-05-22 22:26) |
| 106944/106970 | Telegram bot | `python -m cognitive_os.integrations.telegram_bot` |

## 3. Docker containers (cognitive-os)

| Container | Status | Ports |
|---|---|---|
| cognitive_os_postgres | Up (healthy) | 127.0.0.1:5432 |
| cognitive_os_redis | Up (healthy) | 127.0.0.1:6379 |
| cognitive_os_weaviate | Up (healthy) | 127.0.0.1:8081, 127.0.0.1:50052 (gRPC) |
| cognitive_os_neo4j | Up (healthy) | 127.0.0.1:7475, 127.0.0.1:7688 |

## 4. Verificaciones HTTP

```
$ curl http://127.0.0.1:8000/health
{"status":"ok","service":"cognitive-os"}

$ curl -X POST http://127.0.0.1:8000/auth/local-token
{ "access_token": "<JWT>", "user_id": "local-operator",
  "roles": ["admin", "operator"], "expires_at": "2036-05-20T..." }

$ curl http://127.0.0.1:8000/system/info -H "Authorization: Bearer <JWT>"
{ "operator_profile": "dedicated_local",
  "git_commit": "2c3cff6dfccf", "alembic_head": "202605200003" }

$ curl http://127.0.0.1:8000/system/mcp -H "Authorization: Bearer <JWT>"
{ enabled: true, 5 servers all connected, 67 tools }

$ curl http://127.0.0.1:8000/health/dashboard -H "Authorization: Bearer <JWT>"
{ status: "configured", 18 components,
  ok: postgres, redis, weaviate, neo4j, workers, langsmith, operational_backlog, checkpointer
  ready: voice, maps, google_calendar, google_drive, kimi_webbridge, captcha_solver
  configured: primary_llm, embeddings, mail, mcp_client (cableados, sin probe live) }

$ curl http://127.0.0.1:8000/system/readiness -H "Authorization: Bearer <JWT>"
{ operator_profile: "dedicated_local", local_autonomy_mode: "full",
  target_capabilities_unlocked: 14, target_capabilities_total: 14, gaps: [] }

$ curl -I http://127.0.0.1:3001/
HTTP/1.1 200 OK (Next.js production server, security headers presentes)
```

## 5. JWT capturado

Guardado en `/tmp/cogos_jwt.txt` para reuso en pytest/Playwright/TestSprite.
Roles: `admin`, `operator`. TTL: ~10 años (decisión `dedicated_local/full`).

## 6. Sin reparación necesaria

El stack estaba sano y reproducible al momento del audit. No se requirió
levantar nada nuevo. Una eventual reinicialización al cierre se aplicará
sólo si hace falta cargar binarios de HEAD (ver `02_ZERO_FRICTION_RUNTIME_PROFILE.md` §4).

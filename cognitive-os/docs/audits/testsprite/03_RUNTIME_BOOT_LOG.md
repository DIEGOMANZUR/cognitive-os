# 03 — Runtime Boot Log

Fecha: **2026-05-25** | Auditoría Prompt 1

## Snapshot entorno

| Item | Valor |
|---|---|
| Branch | `codex/commercial-zero-friction-hardening` |
| HEAD | `6891d5c3dc573bcfadbe6438ea062334e4e86a05` |
| Python | 3.12.3 |
| uv | 0.11.6 |
| Node | v22.22.0 |
| npm | 10.9.4 |
| Docker | 29.5.2 |
| Compose | v5.1.4 |

## Estado al inicio

Stack **ya levantado** (no se reinició para no interrumpir operador):

| Servicio | URL/Puerto | Estado |
|---|---|---|
| API FastAPI | 127.0.0.1:8000 | UP |
| Frontend Next | 127.0.0.1:3001 | UP (HTTP 200) |
| `/system/info` | — | `operator_profile=dedicated_local`, git `6891d5c` |
| `/system/readiness` | — | 14/14 unlocked |

## Verificaciones ejecutadas

```bash
curl -sX POST http://127.0.0.1:8000/auth/local-token
curl -s http://127.0.0.1:8000/system/info -H "Authorization: Bearer $JWT"
curl -s http://127.0.0.1:8000/system/readiness -H "Authorization: Bearer $JWT"
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3001  # → 200
```

## Reparaciones aplicadas en boot

Ninguna de infraestructura requerida — stack operativo.

## PIDs / logs

No se capturaron PIDs (stack preexistente vía launchers de escritorio). Logs en rutas estándar del RUNBOOK (`~/Escritorio/cognitive-os.sh logs`).

## Carpetas de artefactos creadas

- `docs/audits/testsprite/`
- `test-results/testsprite/`
- `test-results/manual/`, `playwright/`, `backend/`, `runtime/`

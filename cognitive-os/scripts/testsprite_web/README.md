# scripts/testsprite_web — Public TestSprite tunnel runner

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-27, Prompt 7):** esta rama `codex/commercial-zero-friction-hardening` en base `8a33475d0502` queda sincronizada para el cierre comercial local-first. La evidencia viva se concentra en `/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/tmp/v2_07_absolute_release_closure_20260527_050231`. Estado de producto verificado durante Prompt 7: backend FastAPI local, frontend Next.js, Docker services, Postgres, Redis, Weaviate, Neo4j, Alembic head, worker, beat, health/readiness, LangGraph/chat, DeepAgents, MCP, RAG/documentos, Document Analysis, Action Plane sandbox, mail read-only, Telegram, Google read-only, GoDaddy dry-run, Kimi WebBridge y Code Director toy/guard rails.
>
> **Gates V2.0 ejecutados antes de los dos ciclos verdes finales:** `bash scripts/full-qa.sh` **1221 passed, 1 skipped, 28 deselected**; `bash scripts/stress-qa.sh 5` **5/5 verde x 1221 passed**; `cd frontend && npx playwright test` **44 passed**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/sync_doc_counts.py --check` OK; `bash scripts/verify_desktop_launchers.sh` OK; OpenAPI read-only smoke **70 GET / 0 failures**; security read-only scan sin secretos críticos; CDP/Playwright forense **10 ciclos x 20 vistas** sin console/page errors ni 5xx, con un aborto `POST /auth/local-token` adjudicado como cierre de contexto del harness y no defecto de producto; Lighthouse local: accessibility 96, best-practices 100, SEO 100.
>
> **Criterio de verdad:** no se declara envio de correo, draft real ni escritura DNS. Mail queda normalizado como read-only: sync/list/classify/digest/proposed replies como texto, sin drafts ni sends. GoDaddy queda preview/dry-run; Action Plane mantiene sandbox/approval/audit/idempotencia segun riesgo. El tunnel publico `cognitive.doctormanzur.com` se valida con `scripts/testsprite_web/deploy_and_verify.sh` cuando Diego vaya a correr TestSprite web; Prompt 7 no lo expone permanentemente porque su propia regla prohibe exponer servicios a internet.

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


These scripts bring up the **full local Cognitive OS stack** (Docker infra +
FastAPI backend + Celery worker + Celery beat + Next.js production frontend)
**and** publish it on the public internet via a Cloudflare Tunnel so the
**TestSprite Web Portal** (a cloud SaaS) can drive the UI and call the API.

They are intentionally separate from `scripts/dev_up.sh` so the developer
workflow is unchanged; this stack is only for QA windows.

## Public endpoints

| Hostname                            | Backed by                |
|-------------------------------------|--------------------------|
| `https://cognitive.doctormanzur.com`     | `http://localhost:3001` (Next.js) |
| `https://cognitive-api.doctormanzur.com` | `http://localhost:8000` (FastAPI) |

Both are routed by a single Cloudflare Tunnel named **`cognitive-os-testsprite`**
with config at `~/.cloudflared/cognitive-os-testsprite.yml`.

## One-time setup (already done on this PC)

If you ever need to recreate the tunnel from scratch:

```bash
# Requires: cloudflared installed AND `cloudflared tunnel login` already run.
cloudflared tunnel create cognitive-os-testsprite

# Write the ingress config (see ~/.cloudflared/cognitive-os-testsprite.yml in
# this repo's setup notes).

# Point DNS at the new tunnel (force-overwrite if CNAMEs already exist):
cloudflared tunnel route dns -f cognitive-os-testsprite cognitive.doctormanzur.com
cloudflared tunnel route dns -f cognitive-os-testsprite cognitive-api.doctormanzur.com
```

## Daily usage

Flujo primario para re-runs del portal web:

```bash
bash scripts/testsprite_web/deploy_and_verify.sh
```

Ese comando hace todo en una sola pasada: detiene restos del stack anterior,
reconstruye el frontend de producción con los commits actuales, levanta backend,
worker, beat, `next start` y Cloudflare Tunnel, espera que el frontend público
responda `200`, chequea `/health` del backend público, valida que `/sw.js`
contenga `cogos-v2026-05-26e-status-cards` y confirma que `/` sirve la cockpit
shell (`data-cogos-active-tab`). Si pasa, imprime el checklist exacto para
apretar **Rerun** en TestSprite sin tocar PRD ni instructions.

Comandos manuales de soporte, solo si necesitás observar o cortar servicios:

```bash
bash scripts/testsprite_web/status_testsprite_stack.sh
bash scripts/testsprite_web/stop_testsprite_stack.sh
bash scripts/testsprite_web/start_testsprite_stack.sh
```

## Logs

- `logs/testsprite_web/backend.log`
- `logs/testsprite_web/worker.log`
- `logs/testsprite_web/beat.log`
- `logs/testsprite_web/frontend.log` (`next start`)
- `logs/testsprite_web/frontend_build.log` (turbopack build)
- `logs/testsprite_web/cloudflared.log`

PID files for each service live in the same directory as `<svc>.pid`.

## Notes

- The frontend is **rebuilt** every time `start_testsprite_stack.sh` runs so
  the bundle bakes in `NEXT_PUBLIC_API_BASE_URL=https://cognitive-api.doctormanzur.com`.
  `deploy_and_verify.sh` wraps that start script and is the preferred public
  TestSprite handoff because it also validates cache-bust + shell markers.
  Override at start time with `FRONTEND_PUBLIC_API=https://... bash …/start_testsprite_stack.sh`.
- The `.env` of this repo has `https://cognitive.doctormanzur.com` appended to
  `CORS_ALLOW_ORIGINS` so the public frontend can call the public backend.
- The dangerous-action safety flags (`ENABLE_EMAIL_SEND`, `GODADDY_*`) remain
  `false` / dry-run-only. Do **not** flip them during a TestSprite window.
- For the admin JWT, see `docs/audits/testsprite/WEB_PORTAL_TUNNEL_SETUP.md`.

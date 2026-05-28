# scripts/testsprite_web — Public TestSprite tunnel runner

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-27, Prompt 7).** Esta rama `codex/commercial-zero-friction-hardening` queda certificada como **APTA COMERCIAL LOCAL-FIRST** para PC dedicado. Branch inicial Prompt 1: HEAD `2bb4966`. Working tree del Prompt 7 consolida los cambios de Prompts 3 (F-P2-001..006), 4 (F-P4-001 fix wrapper timeout mcp_client live probe) y 6 (V2-EVAL-001 DocAnalysis API consistency). El commit final del Prompt 7 firma todo el delta V2.0 sin push. Evidencia viva en `tmp/v2_07_absolute_release_closure_20260527_175541/`.
>
> **Hallazgos cerrados V2.0 (12):** F-P2-001 wildcard_allow_all transparency · F-P2-002 stress flake eliminado (0% en 5×1232) · F-P2-003 `?limit=` honored en `/approvals` y `/actions/drive/files` · F-P2-004 `/chat` 404/400 con `missing_doc_ids`/`invalid_doc_ids` · F-P2-005 docs sync (este bloque) · F-P2-006 `_check_mcp(verify_live=True)` → overall `ok` · F-P4-001 timeout wrapper +5s sobre `mcp_inventory_timeout_seconds` · F-P4-002 fallback heurístico DocAnalysis documentado · F-P4-003 Kimi extension boot oscillation documentado · V2-EVAL-001 `GET /document-analysis/{id}` mirror artefacto · V2-EVAL-004 endpoints memoria/aprendizaje live (303 proposals, 209 recipes, 94 warnings) · V2-EVAL-005 Code Director adapter=deepagent plan+approval+reject sin exec.
>
> **Gates V2.0 medidos antes del cierre absoluto:** `bash scripts/full-qa.sh` **1232 passed, 1 skipped, 28 deselected** (ruff/format/mypy/alembic/sync_doc_counts/git-diff verdes); `bash scripts/stress-qa.sh 5` **5/5 verde × 1232 passed**, flakiness **0%**; `cd frontend && npx playwright test` **44 passed**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/openapi_readonly_smoke.py` **70 GET / 0 failures**; `bash scripts/verify_desktop_launchers.sh` OK; security-readonly-qa (bandit/semgrep/secret-scan) clean; `POST /health/verify` overall **`ok`** con `mcp_client` live `ok` 6/6 y 69 tools; checklist 400 puntos ejecutada.
>
> **Criterio de verdad:** no se declara envío de correo, draft real ni escritura DNS. Mail queda normalizado como read-only (sync/list/classify/digest + proposed replies como texto). GoDaddy preview/dry-run. Action Plane mantiene `validate→preview→request→approve→dispatch→execute→audit` con idempotencia y reapers. El runtime corre en `127.0.0.1` sin exposición LAN/internet. El frontend `cognitive.doctormanzur.com` se levanta on-demand sólo con `scripts/testsprite_web/deploy_and_verify.sh`; Prompt 7 V2.0 no lo expone permanentemente. **Cognitive OS queda certificado en este commit como APTO COMERCIAL LOCAL-FIRST para PC dedicado, con funcionamiento real activado, documentación sincronizada, dos ciclos completos verdes posteriores al último cambio, Git ordenado y sin P0/P1/P2 abiertos.**

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

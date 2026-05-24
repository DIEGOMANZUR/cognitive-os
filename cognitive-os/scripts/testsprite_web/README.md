# scripts/testsprite_web — Public TestSprite tunnel runner

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

```bash
# Start everything (idempotent — kills orphan PIDs from prior runs first):
bash scripts/testsprite_web/start_testsprite_stack.sh

# Check status:
bash scripts/testsprite_web/status_testsprite_stack.sh

# Stop everything (leaves Docker infra running):
bash scripts/testsprite_web/stop_testsprite_stack.sh
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
  Override at start time with `FRONTEND_PUBLIC_API=https://... bash …/start_testsprite_stack.sh`.
- The `.env` of this repo has `https://cognitive.doctormanzur.com` appended to
  `CORS_ALLOW_ORIGINS` so the public frontend can call the public backend.
- The dangerous-action safety flags (`ENABLE_EMAIL_SEND`, `GODADDY_*`) remain
  `false` / dry-run-only. Do **not** flip them during a TestSprite window.
- For the admin JWT, see `docs/audits/testsprite/WEB_PORTAL_TUNNEL_SETUP.md`.

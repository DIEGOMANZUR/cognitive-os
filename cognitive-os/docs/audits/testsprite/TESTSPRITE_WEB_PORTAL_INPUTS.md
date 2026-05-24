# TestSprite Web Portal — Inputs

What you (Diego) paste/upload in the TestSprite cloud portal for this run.

## 1. Frontend URL (UI project)

```
https://cognitive.doctormanzur.com
```

## 2. Backend URL (API project)

```
https://cognitive-api.doctormanzur.com
```

## 3. OpenAPI

Upload the file:

```
docs/audits/testsprite/cognitive-os-openapi.json
```

(140 paths, ~183 KB. Snapshot taken from the public tunnel during setup.)

## 4. JWT (admin)

Open the local file (do NOT paste it into anything else):

```
/tmp/cognitive_os_testsprite_jwt.txt
```

It contains a single line — the bearer token. Copy that line.

Use it in two places:

- **UI project:** when the app loads, paste the token into the TopBar
  "Token" field (the value is stored in localStorage as `cogos.token`).
- **API project:** add a global header

  ```
  Authorization: Bearer <paste>
  ```

Roles: `["admin"]`. Sub: `1`. Expires: 8 h from emission.

If it expires mid-run, regenerate:

```bash
cd backend
uv run python -c "
from datetime import timedelta
from cognitive_os.core.auth import create_access_token
print(create_access_token(user_id='1', roles=['admin'], expires_delta=timedelta(hours=8)))
" > /tmp/cognitive_os_testsprite_jwt.txt
chmod 600 /tmp/cognitive_os_testsprite_jwt.txt
```

## 5. Authentication instructions for TestSprite

- Send the JWT in **every** API call as `Authorization: Bearer <JWT>`.
- The UI persists the JWT in `localStorage` (`cogos.token`). After paste,
  refreshes preserve auth.
- The frontend uses `NEXT_PUBLIC_API_BASE_URL=https://cognitive-api.doctormanzur.com`,
  so its own fetch calls go through the public tunnel — no localhost.

## 6. Rules TestSprite must respect

Do **not** attempt any of:

- Sending real emails (`ENABLE_EMAIL_SEND=false`, `MAIL_ALLOW_EXPLICIT_SEND=false`).
- Creating Gmail drafts that would result in actual SMTP delivery.
- DNS writes against GoDaddy (`GODADDY_DNS_DRY_RUN_ONLY=true`,
  `GODADDY_ALLOW_PRODUCTION_WRITES=false`).
- Destructive filesystem actions (`ALLOW_DANGEROUS_TOOLS=false`).
- Headful browser automation that drives external sites
  (`ENABLE_BROWSER_AUTOMATION=false`).

Allowed:

- All health checks.
- All read-only API calls.
- Preview / dry-run flows.
- Request flows that produce text proposals without execution.
- UI exercises (clicking, navigation, screenshotting, accessibility audits).

## 7. PRD

```
docs/audits/testsprite/COGNITIVE_OS_TESTSPRITE_PRD.md
```

## 8. Checklist for Diego

- [ ] Stack is up (`bash scripts/testsprite_web/status_testsprite_stack.sh` shows green for backend, worker, frontend, cloudflared).
- [ ] JWT in `/tmp/cognitive_os_testsprite_jwt.txt` is fresh (≤ 8 h old).
- [ ] OpenAPI uploaded to the API project.
- [ ] PRD uploaded to both projects.
- [ ] Bearer header configured globally in the API project.
- [ ] UI project URL set to `https://cognitive.doctormanzur.com`.
- [ ] Confirmed safety flags listed in section 6 are still off (`grep -E '^(ENABLE_EMAIL_SEND|GODADDY_)' .env`).

After the window:

- [ ] `bash scripts/testsprite_web/stop_testsprite_stack.sh`
- [ ] Optionally revoke the JWT by rotating `JWT_SECRET` in `.env`.

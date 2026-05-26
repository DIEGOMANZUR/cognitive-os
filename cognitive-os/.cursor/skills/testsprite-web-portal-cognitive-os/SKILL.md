---
name: testsprite-web-portal-cognitive-os
description: Runs Cognitive OS audits through the TestSprite Web Portal instead of TestSprite MCP. Use when the user mentions TestSprite frontend, TestSprite web portal, uploaded PRD, browser session, Edge/TestSprite website, or asks to fill TestSprite portal fields, run UI/API suites from the website, avoid MCP localhost/tunnel problems, or continue a TestSprite web run.
---

# TestSprite Web Portal — Cognitive OS

Use this skill when TestSprite MCP is blocked by localhost/tunnel behavior and the user has TestSprite open in the browser. This skill is for **TestSprite Web Portal execution**, not local Playwright, pytest, lint, or TestSprite MCP.

## Non-Negotiables

- Do **not** store real TestSprite API keys, JWTs, refresh tokens, passwords, or portal session data in this skill, reports, or git.
- Use the user's logged-in TestSprite browser session. Do not paste `TESTSPRITE_API_KEY` into the web portal.
- Cognitive OS frontend entry URL is only `https://cognitive.doctormanzur.com/`.
- Cognitive OS backend base URL is `https://cognitive-api.doctormanzur.com`.
- For UI auth from the Web Portal, prefer a URL fragment bootstrap: `https://cognitive.doctormanzur.com/#cogos_token=<JWT_WITHOUT_BEARER>`. This only transports the real JWT into `localStorage.cogos.token`; it must not enable demo, fixture, or provisional UI data. If unavailable, put a fresh Cognitive OS JWT in the Test Account password field and instruct TestSprite to use it only as `localStorage.cogos.token`.
- Do not instruct external portal agents to call `POST /auth/local-token`; Cloudflare may block external/browser-agent signatures. That endpoint is still valid for dedicated local/bootstrap contexts.
- There is no email/password login. Test Account password, when used, is a JWT transport only.
- Never run destructive or real-world side-effect cases: mail send/draft/approve-send, DNS write, destructive sandbox, safety flag mutation, JWT secret rotation, admin mutation.
- Stop before generating/executing if the plan includes real mutating actions; rewrite/delete those cases as read-only or guard-only.
- Never declare PASS unless the portal report is clean and local artifacts are saved.

## Required Reading

Before portal work, read:

1. `PRD.md`
2. `PRD_FRONTEND.md`
3. `PRD_BACKEND.md`
4. `cognitive-os-launchers-README.md` when runtime/launchers are involved
5. `PORTAL_FIELD_VALUES.md`
6. `CREDENTIALS.md`
7. `TRIAGE_TEMPLATE.md`

If a portal-generated assumption conflicts with PRDs, the PRDs win.

## Workflow

1. Confirm the portal is logged in and the browser session is usable.
2. Upload PRD/Product Description only when requested by the portal. Use the combined execution pack if present:
   - `/home/jgonz/Escritorio/testsprite/COGNITIVE_OS_TESTSPRITE_FULL_UPLOAD.md`
   - `TESTSPRITE_WEB_PORTAL_EXECUTION_PACK.md`
3. Choose suite type:
   - API suite: `Backend (APIs)`
   - UI suite: `Frontend (URLs)`
4. Fill fields from `PORTAL_FIELD_VALUES.md`.
5. If API credential is needed, follow `CREDENTIALS.md`: use a fresh Cognitive OS JWT without `Bearer ` prefix. Prefer a token minted for the current run; never write it into markdown.
6. Review extracted features/use cases before execution. Delete or rewrite unsafe cases.
7. Generate/execute only after the plan is read-only or guard-only.
8. Save a local report under `docs/audits/testsprite_cursor/` and a summary artifact under `test-results/testsprite_cursor/`.
9. Triage every finding:
   - real bug;
   - expected behavior;
   - false positive grounded in PRD;
   - blocked;
   - flaky/TestSprite limitation.

## Portal Guardrails

### UI Suite

Allowed:

- Load `/`.
- Seed `localStorage`.
- Sidebar navigation.
- Hotkeys `1` through `9`.
- `Ctrl+K` command palette.
- Read-only view validation.
- Responsive checks.

Forbidden:

- Direct navigation to SPA internal server paths.
- Email send/draft/sync/approve-send.
- Destructive action dispatch.
- Sandbox destructive code.

### API Suite

Allowed:

- Public GETs: `/health`, `/openapi.json`, `/docs`, `/redoc`.
- Authenticated safe GET/status/list endpoints.
- Guard tests only when expected result is controlled 4xx/409/no side effect.

Forbidden:

- Real mail sending or draft creation.
- Real DNS writes.
- Destructive sandbox/tool execution.
- Admin/user/security mutation.
- Treating 401 missing/invalid token as a bug.

## Evidence Rules

Record:

- TestSprite project name and portal report URL.
- Total cases, pass, fail, blocked.
- Exact failed endpoint/view names.
- Triage classification.
- Local artifact paths.

Do not record:

- JWT values.
- TestSprite API key.
- Portal cookies/session data.
- Raw secret-shaped backend responses.

## Utilities

Use the helper only to print safe field values:

```bash
python3 .cursor/skills/testsprite-web-portal-cognitive-os/scripts/portal_fields.py ui
python3 .cursor/skills/testsprite-web-portal-cognitive-os/scripts/portal_fields.py api
```

The helper intentionally does not print secrets.

For real token acquisition rules, read `CREDENTIALS.md`. It explains TestSprite portal session, TestSprite API key scope, Cognitive OS JWT minting, UI localStorage seed, and negative auth credentials without embedding secrets.

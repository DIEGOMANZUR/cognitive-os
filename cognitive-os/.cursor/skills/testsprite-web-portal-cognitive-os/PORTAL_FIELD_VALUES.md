# TestSprite Web Portal Field Values

Use these values when filling the TestSprite Web Portal for Cognitive OS.

## Shared Upload

Upload under **PRD / Product Description**:

- Preferred: `/home/jgonz/Escritorio/testsprite/COGNITIVE_OS_TESTSPRITE_FULL_UPLOAD.md`
- Alternate: `TESTSPRITE_WEB_PORTAL_EXECUTION_PACK.md`

Do not upload this as API Docs. API Docs should be OpenAPI/endpoint docs only.

## API Suite

Test type:

- `Backend (APIs)`

API docs:

- Prefer public OpenAPI URL if the portal accepts it: `https://cognitive-api.doctormanzur.com/openapi.json`
- If manual entry is required, add safe/read endpoints first and avoid dangerous mutating endpoints.

API name examples:

- `Cognitive OS Health public`
- `Cognitive OS protected system info`
- `System Readiness API`
- `Jobs API`
- `Mail status API`
- `OpenAPI Docs`

API endpoint URL examples:

- `https://cognitive-api.doctormanzur.com/health`
- `https://cognitive-api.doctormanzur.com/openapi.json`
- `https://cognitive-api.doctormanzur.com/docs`
- `https://cognitive-api.doctormanzur.com/redoc`
- `https://cognitive-api.doctormanzur.com/system/info`
- `https://cognitive-api.doctormanzur.com/system/readiness`
- `https://cognitive-api.doctormanzur.com/system/credentials-status`

Authentication type:

- Public endpoints: `None`
- Protected endpoints: `Bearer`

Credential / Key:

- Paste a fresh Cognitive OS JWT only, without `Bearer ` prefix.
- Do not paste `TESTSPRITE_API_KEY`.
- Click `Apply to all APIs` only after confirming all protected endpoints should receive the same auth token.
- Do not record the token in reports.
- To obtain the JWT, follow `CREDENTIALS.md`.

Extra testing instructions:

```text
Cognitive OS API Contract Full. Use https://cognitive-api.doctormanzur.com as the backend base. Public endpoints are GET /health, GET /openapi.json, GET /docs, GET /redoc. All other endpoints require Authorization: Bearer <JWT>. Expected auth guards: missing token 401, invalid token 401, expired token 401 JWT has expired, insufficient role 403 forbidden_role. Do not mark expected guards as bugs. Do not execute real-world destructive actions: no mail send, no mail draft, no approve-send, no DNS write, no destructive sandbox execution, no dangerous tool execution, no safety flag mutation, no JWT secret rotation, no admin user mutation. Guard tests are allowed only when expected result is controlled 400/403/409/feature_disabled/dry_run_only/forbidden with no side effect. Mail is read-only in normal flow. Treat provider disabled/degraded as acceptable only if response is explicit and non-5xx.
```

## UI Suite

Test type:

- `Frontend (URLs)`

Website URL:

```text
https://cognitive.doctormanzur.com/#cogos_token=<JWT_WITHOUT_BEARER>
```

Test Account:

- Prefer `https://cognitive.doctormanzur.com/#cogos_token=<JWT_WITHOUT_BEARER>` when the deployed frontend supports hash bootstrap. This authenticates the real SPA only; it must not enable demo, fixture, or provisional UI data.
- If using credentials instead, set username/email to `local-operator-jwt`.
- Set password to the stable Cognitive OS JWT from `/home/jgonz/Escritorio/testsprite/cognitive_os_testsprite_stable_jwt.txt`, without `Bearer `.
- There is no email/password login; the password is used only as the JWT source for `localStorage`.

Extra context/instructions:

```text
Cognitive OS UI SPA Full. Use only https://cognitive.doctormanzur.com/ as the entry URL, preferably with #cogos_token=<JWT_WITHOUT_BEARER> when available. This is a single-page app: do NOT directly navigate to /dashboard, /health, /mail, /chat, /documents, /settings, /jobs, /approvals, /research, or /code-director because direct server paths are expected 404. Do NOT click "Usar JWT local automatico" and do NOT call POST /auth/local-token from the external TestSprite portal; Cloudflare may block external agent signatures. If a Test Account password is provided, treat it as a JWT, not as a login password: set localStorage.cogos.token to that credential value, set localStorage.cogos.api to https://cognitive-api.doctormanzur.com, set localStorage.cogos.token.source to manual, then reload /. If direct localStorage scripting is unavailable, open Conexión, paste the Test Account password into "JWT sin prefijo Bearer", confirm API base is https://cognitive-api.doctormanzur.com, click Guardar, then return to Dashboard. Navigate views only through sidebar, hotkeys 1-9, and Ctrl+K command palette. Cover Dashboard, Chat, DeepAgents, Skills, Memoria, Asistente, Mail read-only, Documentos, Document Analysis, Jobs, Aprobaciones, Google Ops, Research, Code Director, Sandbox, LangSmith, Audit log, Health, Sistema, Conexion, Notifications, Command Palette, and responsive behavior. Do not accept demo, fixture, or provisional UI fallbacks as success. Assert connected or controlled degraded state after seed. Fail on critical console errors, hydration/chunk errors, CORS, mixed content, infinite loading, false green health, dead critical buttons, or real network requests to localhost/127.0.0.1. Mail must remain read-only: do not create drafts, sync mail, approve send, or send email. Do not execute destructive actions.
```

## Feature Review Before Execution

Delete or rewrite UI cases that say:

- send mail;
- create draft;
- approve send;
- sync mail;
- dispatch action with real side effect;
- execute sandbox code destructively;
- cancel jobs unless the UI clearly exposes a dry-run/safe guard;
- approve real external operations;
- upload/import documents unless explicitly approved as safe project data.

Rewrite them as:

- verify blocked/disabled state;
- verify read-only status;
- verify explicit warning/confirmation;
- verify no false success.

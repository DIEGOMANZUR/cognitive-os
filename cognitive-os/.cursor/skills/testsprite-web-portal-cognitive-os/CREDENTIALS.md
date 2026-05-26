# Credentials And Tokens

This file explains where to get real credentials for TestSprite Web Portal runs. It must not contain real secrets.

## TestSprite Web Portal Session

Use the user's already logged-in browser session at:

```text
https://www.testsprite.com/dashboard/testing
```

If the portal shows login, stop and ask the user to log in manually. Do not ask for the user's TestSprite password.

## TestSprite API Key

The TestSprite API key is for MCP/CLI flows, not for the portal's API credential field.

Allowed sources:

1. Current shell environment:

```bash
printf '%s\n' "${TESTSPRITE_API_KEY:+TESTSPRITE_API_KEY is set}"
```

2. Repo loader, if MCP/local flow is being used:

```bash
bash scripts/load_testsprite_env.sh
```

Never paste `TESTSPRITE_API_KEY` into:

- API `Credential / Key`;
- Bearer token fields for Cognitive OS endpoints;
- markdown reports;
- skill files.

## Cognitive OS JWT For Protected API Tests

Use the stable TestSprite JWT without the `Bearer ` prefix.

Preferred source during portal work:

```text
/home/jgonz/Escritorio/testsprite/cognitive_os_testsprite_stable_jwt.txt
```

This token is intentionally long-lived for zero-friction TestSprite Web Portal work. It must remain outside git and must not be pasted into reports or chat.

The compatibility copy for current scripts/portal helpers is:

```text
/tmp/cognitive_os_testsprite_web_jwt.txt
```

Check either file without echoing the value to chat:

```bash
test -s /home/jgonz/Escritorio/testsprite/cognitive_os_testsprite_stable_jwt.txt && echo "Stable JWT file exists"
```

Paste this JWT into TestSprite's `Credential / Key` field for protected Cognitive OS API endpoints. Paste it **without** `Bearer `.

## UI Web Portal Seed

For UI Web Portal tests, do not use email/password. Prefer the URL fragment bootstrap when the deployed frontend supports it:

```text
https://cognitive.doctormanzur.com/#cogos_token=<JWT_WITHOUT_BEARER>
```

Use the contents of:

```text
/home/jgonz/Escritorio/testsprite/cognitive_os_testsprite_stable_jwt.txt
```

The fragment is handled by the SPA, persisted to `localStorage.cogos.token`, and removed from the address bar. The fragment is not sent to the server. It must not enable demo, fixture, or provisional UI data.

If a URL fragment cannot be used, put a fresh JWT in the Test Account password field and instruct TestSprite to seed it in browser context:

```js
localStorage.setItem("cogos.token", TEST_ACCOUNT_PASSWORD_VALUE);
localStorage.setItem("cogos.api", "https://cognitive-api.doctormanzur.com");
localStorage.setItem("cogos.token.source", "manual");
location.href = "/";
```

Do not instruct external TestSprite Web Portal agents to call `POST /auth/local-token`. Cloudflare may block external/browser-agent signatures before the request reaches the backend.

## Negative Auth Credentials

Use these only for guard tests:

- Missing token: omit the Authorization header.
- Invalid token: use a clearly fake JWT-shaped value such as `invalid.invalid.invalid`.
- Expired token: only use a real expired token if the backend/test fixture provides one. Do not invent a signed expired token unless the signing secret is intentionally available for tests.
- Insufficient role: only use a real non-admin/limited-role token if the backend/test fixture provides one. Do not classify an admin-token 200 as an insufficient-role bug.

## Reporting

Allowed in reports:

- `JWT present`;
- `Bearer token applied`;
- `admin JWT was used`;
- `invalid.invalid.invalid` for fake-token tests.

Forbidden in reports:

- Actual JWT values;
- `TESTSPRITE_API_KEY`;
- browser cookies;
- OAuth tokens;
- unredacted secret-shaped backend values.

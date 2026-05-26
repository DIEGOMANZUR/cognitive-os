# TestSprite Web Portal UI Auth Blocker

Status: `BLOCKED / FIX_PREPARED_NOT_YET_DEPLOYED`

Date: 2026-05-26

## Context

TestSprite Web Portal was configured for a strict read-only UI suite against:

```text
https://cognitive.doctormanzur.com/
```

The generated feature map was safe and read-only:

- Application Bootstrap and Session Seeding
- Global Navigation and View Switching
- Responsive Shell Layout
- Health Status Visibility
- Dashboard Read-Only Overview
- Mail Read-Only Review
- Documents Read-Only Browsing
- Audit Event Review

## Observed Blocker

TestSprite repeatedly failed the connected-shell bootstrap. The portal trace reported:

```text
No se pudo activar el JWT local automático.
Detalle: Timeout al pedir JWT local despues de 10s.
```

A retry later reported:

```text
Cloudflare 502 error and request timeouts on
https://cognitive-api.doctormanzur.com/auth/local-token
prevented session seeding.
```

Runtime checks from the agent machine confirmed that the public endpoint can be blocked before reaching the backend:

```text
POST /auth/local-token -> Cloudflare 403 Error 1010: Access denied
POST /auth/local-token with public Origin -> timeout
```

## Classification

This is not a read-only UI case design failure. It is an external TestSprite/public-edge authentication blocker:

- The local/backend contract for `/auth/local-token` remains valid in `dedicated_local/full`.
- The public Cloudflare edge can block external browser-agent signatures before the request reaches FastAPI.
- TestSprite ignored the credential override and continued to call `/auth/local-token`.

Verdict: `BLOCKED`, with a real deployment/infrastructure compatibility issue for external portal testing.

## Fix Prepared

Prepared a frontend bootstrap fallback:

```text
https://cognitive.doctormanzur.com/#cogos_token=<JWT_WITHOUT_BEARER>
```

The SPA now reads `cogos_token`, `token`, or `jwt` from the URL fragment, stores it as `localStorage.cogos.token`, marks token source as manual, and removes the fragment from the address bar. URL fragments are not sent to the server, avoiding Cloudflare and server logs.

Updated portal guidance files to prefer the fragment bootstrap and avoid external `/auth/local-token` calls.

## Next Required Step

Deploy the frontend change before re-running the Web Portal UI suite. Then configure TestSprite with:

```text
Website URL: https://cognitive.doctormanzur.com/#cogos_token=<fresh JWT without Bearer>
```

Do not upload additional files unless starting a clean project; if a file is requested, use:

```text
/home/jgonz/Escritorio/testsprite/COGNITIVE_OS_TESTSPRITE_UI_READONLY_UPLOAD.md
```

Do not claim UI PASS until the post-deploy portal rerun reaches connected state and produces a clean read-only report.

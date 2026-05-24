# Cognitive OS — Backend (API) PRD for TestSprite

## 1. Identity

- **Service:** Cognitive OS backend (FastAPI + SQLAlchemy 2.x async + Celery)
- **Public base URL:** `https://cognitive-api.doctormanzur.com`
- **OpenAPI:** uploaded as `cognitive-os-openapi.json` (140 paths)
- **Auth:** JWT HS256 bearer, header `Authorization: Bearer <token>`
- **Admin role required for non-public endpoints.** A pre-minted admin JWT is provided in the extra instructions.

## 2. Public vs protected endpoints

Public (no auth):

- `GET /health` → 200 with `{"status":"ok","service":"cognitive-os"}`
- `GET /openapi.json`, `GET /docs`, `GET /redoc` — Swagger / docs UI

All other endpoints **require** the bearer header. Without it the response is 401 `Not authenticated`.

## 3. Auth model (CRITICAL)

```
Authorization: Bearer <JWT>
```

JWT claims:
- `sub`: operator id (string)
- `roles`: array including `"admin"` for full access
- `exp`: unix epoch seconds (8 h validity by default)
- HS256 signature

If the token is missing → **401**.
If the token is expired → **401** with `JWT has expired`.
If the role is insufficient → **403** `forbidden_role`.

These three error shapes are expected and should be asserted as such — not as bugs.

## 4. Namespaces (21 groups, 140 endpoints)

| Namespace          | Count | Purpose                                                |
|--------------------|------:|--------------------------------------------------------|
| `/actions`         | 53    | Action registry (catalog, dispatch, request, status)   |
| `/deepagents`      | 21    | DeepAgent runs, traces, checkpoints                    |
| `/mail`            | 10    | Gmail digest, threads, READ-ONLY for this window       |
| `/document-analysis`| 7    | Document Analysis agent flows                          |
| `/assist`          | 5     | Personal assistant routes                              |
| `/system`          | 4     | `/system/info`, `/system/readiness`, etc.              |
| `/jobs`            | 4     | Async job inspection                                   |
| `/langsmith`       | 4     | Trace metadata bridge                                  |
| `/research`        | 4     | Research agent                                         |
| `/code-director`   | 4     | Code director adapter                                  |
| `/health`          | 3     | Service health + dashboard + verify                    |
| `/threads`         | 3     | Chat thread CRUD (READ + soft create)                  |
| `/documents`       | 3     | Document index queries                                 |
| `/approvals`       | 3     | Pending approvals (READ + approve)                     |
| `/voice`           | 3     | Voice IO endpoints                                     |
| `/chat`            | 2     | Chat send + stream                                     |
| `/sandbox`         | 2     | Read-only sandbox status                               |
| `/auth`            | 1     | Auth helper                                            |
| `/audit`           | 1     | Audit log query                                        |
| `/knowledge`       | 1     | Knowledge graph query                                  |
| `/config`          | 1     | Configuration snapshot                                 |
| `/agents`          | 1     | Agent catalog                                          |

## 5. Critical journeys (use these as the test plan backbone)

### J1 — Liveness

1. `GET /health` (no auth) → 200, body `{"status":"ok","service":"cognitive-os"}`.

### J2 — Readiness + system info

1. `GET /system/info` (auth) → 200 with environment + version.
2. `GET /system/readiness` (auth) → 200, all dependencies green.
3. `GET /system/credentials-status` (auth) → 200, structured booleans only — must NOT echo any secret values.

### J3 — Catalog discovery

1. `GET /actions` (auth) → 200 with non-empty list.
2. `GET /agents` (auth) → 200.
3. `GET /skills` (auth, if exposed) → 200.

### J4 — Chat round trip

1. `POST /chat` with `{"message":"hello"}` (auth) → 200 with `thread_id`, `message`, `route`.
2. `GET /threads/{thread_id}` → 200, includes the new message.

### J5 — Document index

1. `GET /documents` (auth) → 200 with `items` array (may be empty).
2. If non-empty, `GET /documents/{id}` → 200.

### J6 — Approvals + audit

1. `GET /approvals` (auth) → 200, list (may be empty).
2. `GET /audit?limit=5` (auth) → 200, last 5 audit events.

### J7 — Jobs introspection

1. `GET /jobs?limit=10` (auth) → 200.
2. If non-empty, `GET /jobs/{id}` → 200 with status/progress/events.

### J8 — DeepAgents catalog

1. `GET /deepagents` or `/deepagents/list` (auth) → 200 with available agents.
2. Skip starting a long-running agent unless the test budget allows; a started agent counts against quota.

### J9 — Auth negative paths (assert the guards work)

1. `GET /system/info` **without** Authorization header → 401.
2. `GET /system/info` **with** invalid token → 401 `Invalid JWT signature`.
3. `GET /system/info` with an expired token → 401 `JWT has expired`.

### J10 — CORS preflight

1. `OPTIONS /system/info` with `Origin: https://cognitive.doctormanzur.com` → 200 / 204, response includes `Access-Control-Allow-Origin: https://cognitive.doctormanzur.com` and `Access-Control-Allow-Credentials: true`.

## 6. Out-of-scope — DO NOT call these

| Endpoint pattern                              | Why excluded                                      |
|-----------------------------------------------|---------------------------------------------------|
| `POST /mail/messages/{id}/approve-send`       | Would send real email if guards lifted           |
| `POST /mail/messages/{id}/send`               | Same — outbound SMTP                              |
| Any `POST /actions/dispatch` that targets DNS writes | Could mutate GoDaddy                       |
| `POST /sandbox/exec` with destructive code    | Filesystem risk                                   |
| Any endpoint whose tag/description includes `dangerous` or `destructive` | Self-explanatory  |
| Direct admin endpoints that rotate JWT secret or admin users | Would invalidate the test session |

**Expected response shape when the agent attempts a guarded action:**

- Returns 400 / 403 / 409 with a JSON error like `{"detail":"feature_disabled"}` or `{"detail":"dry_run_only"}`.
- Does NOT return 5xx.
- Does NOT execute the external side effect.

Verifying that these blocks actually fire is **encouraged** — those are valuable negative tests.

## 7. Safety guardrails active during this window

| Flag                              | Value     | Effect                                                  |
|----------------------------------|-----------|---------------------------------------------------------|
| `ENABLE_EMAIL_SEND`              | `false`   | Mail send endpoints respond with "disabled"             |
| `MAIL_ALLOW_EXPLICIT_SEND`       | `false`   | Approve-send requires explicit phrase that we won't send|
| `GODADDY_DNS_DRY_RUN_ONLY`       | `true`    | DNS writes simulate, never execute                      |
| `GODADDY_ALLOW_PRODUCTION_WRITES`| `false`   | Hard block on production DNS                            |
| `TOOLS_READONLY_MODE`            | `true`    | Action registry filters to read-only tools              |
| `ENABLE_BROWSER_AUTOMATION`      | `false`   | Browser tools refuse to drive external pages            |
| `ALLOW_DANGEROUS_TOOLS`          | `false`   | Anything tagged dangerous returns 403                   |

## 8. Performance / response-time expectations

- `/health` < 200 ms typical
- `/system/info`, `/system/readiness` < 1 s
- Chat, agents, research endpoints: 2–60 s depending on backend LLM lane (they hit a remote LLM gateway). Latency outliers are NOT bugs — they are external dependencies.
- Document and audit queries < 2 s.

Flaky 5xx tied to LLM gateway timeouts should be retried once; if the second attempt also 5xxs, report as a real issue.

## 9. Data sensitivity

- Responses may include `redacted_pii=true` markers — this is the structured redaction layer.
- Do NOT exfiltrate full responses to third parties in test reports — TestSprite's own report is fine.
- API keys, JWT secrets, OAuth tokens are NEVER returned by endpoints. If you see one, report it as a security bug.

## 10. Reporting failures back to the operator

For each failure include:

- Method + path
- Request headers (mask Authorization beyond the first 12 chars)
- Request body
- Response status + body
- Latency

The operator will fix issues by namespace and ask for a re-run.

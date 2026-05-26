# 05 — API Contract Full Plan

- Generated: `2026-05-26 02:46 UTC`
- Suite: **B — API CONTRACT FULL**
- Source JSON: `testsprite_tests/testsprite_backend_test_plan.json`
- TestSprite MCP: plan generated/loaded in Cursor session

## Target

- Backend: `https://cognitive-api.doctormanzur.com`
- OpenAPI: `https://cognitive-api.doctormanzur.com/openapi.json`
- Auth: `Authorization: Bearer <JWT>` (file `/tmp/cognitive_os_testsprite_cursor_jwt.txt`)

## Cases

### TCAPI001 — public_health_and_docs_are_reachable
- Priority: `n/a`
- Description: Use the public API base https://cognitive-api.doctormanzur.com. Verify GET /health returns 200 without auth, GET /openapi.json returns a valid OpenAPI document, and GET /docs plus GET /redoc are reachable without exposing secrets.

### TCAPI002 — local_token_system_readiness_no_secret_values
- Priority: `n/a`
- Description: Use POST /auth/local-token and read access_token. GET /system/info, /system/readiness, /system/credentials-status. Verify 2xx, expected readiness keys, and no raw secret values. Do not treat field names, setting names, capability names, or words like jwt_secret/gmail_client_secret/client_secret/token/key as a leak by themselves; they are identifiers. Fail only if a secret-shaped value is returned (Bearer/JWT string, OAuth token, API key value, password value, long unredacted credential) or if endpoint returns unexpected 5xx.

### TCAPI003 — protected_auth_negative_cases
- Priority: `n/a`
- Description: Against protected endpoints such as /system/info and /jobs?limit=1, verify missing token and invalid token return 401/403 as expected, not 500. Do not use or print a real JWT in negative assertions.

### TCAPI004 — critical_read_only_operational_groups
- Priority: `n/a`
- Description: With a JWT from POST /auth/local-token, exercise read-only critical groups: GET /jobs?limit=10, GET /approvals, GET /audit/events?limit=5, GET /actions/capabilities, GET /mail/status, GET /documents?limit=10, GET /health/dashboard. Assert no unexpected 5xx and no destructive write is attempted.

### TCAPI005 — cors_preflight_public_frontend
- Priority: `n/a`
- Description: Send OPTIONS /system/info with Origin https://cognitive.doctormanzur.com and Access-Control-Request-Method GET. Verify CORS permits the public frontend origin without wildcard secret leakage.

### TCAPI006 — forbidden_guards_openapi_and_get_only_no_writes
- Priority: `n/a`
- Description: Use POST /auth/local-token only for auth and access_token. After auth execute only GET /openapi.json, GET /mail/status, GET /mail/messages?limit=1, GET /actions, and safe read-only action/request listing if exposed. Do not execute any POST under /mail, including /mail/sync, /mail/sync/dispatch, /mail/digest/dispatch, /mail/digest/preview, /mail/messages/{id}/ignore, send, draft, approve-send. Do not execute DNS writes, actions dispatch, sandbox exec, or destructive operations. Pass if safe GETs are 2xx/non-5xx and dangerous operations are only documented/guarded; fail only on normal send/draft/write success path, 5xx, secret leak, or executed side effect.

### TCAPI007 — mail_contract_uses_access_token_and_no_send_or_draft
- Priority: `n/a`
- Description: Safe mail contract check. Authentication response from POST /auth/local-token returns JSON key access_token, not token. Use access_token as Bearer. After auth execute only GET /mail/status, GET /mail/messages?limit=1, and GET /openapi.json. Do not execute any POST under /mail. Do not fail merely because OpenAPI documents read-side ingestion/sync/digest-preview paths. Fail only if normal outbound send, draft creation, or unguarded approve-send is exposed as a normal operator flow, or if GETs return 5xx/secrets.

### TCAPI008 — catalogs_deepagents_skills_memory_config_read_only
- Priority: `n/a`
- Description: Use Bearer token from POST /auth/local-token. Exercise read-only catalog/status endpoints for /actions, /agents, /deepagents or /deepagents/list, /knowledge, /config, and /skills if exposed. Accept 404 only for optional /skills. Responses must be 2xx or actionable 4xx/disabled, never expected 500, and must not leak secrets.

### TCAPI009 — chat_thread_roundtrip_accepts_thread_id_schema
- Priority: `n/a`
- Description: Use Bearer token from /auth/local-token access_token. POST /chat with short harmless message. If 200, verify thread_id/message/route. GET /threads/{thread_id}; ThreadResponse schema uses thread_id and values, not id. Accept thread_id as the identifier. If provider unavailable, accept controlled non-5xx actionable error. Retry once for transient 5xx; persistent 5xx is failure.

### TCAPI010 — documents_and_document_analysis_safe_contract
- Priority: `n/a`
- Description: Use Bearer token. GET /documents and GET first document if present. Exercise document-analysis status/list/schema endpoints if exposed. For malformed payload/invalid document id, use clearly invalid IDs and assert 4xx not 500. Do not upload real sensitive files or trigger destructive filesystem writes.

### TCAPI011 — research_code_director_sandbox_read_only_or_guarded_contract
- Priority: `n/a`
- Description: Use Bearer token from POST /auth/local-token (access_token). Verify read-only/status/list/OpenAPI endpoints for /research, /code-director, /sandbox, and /langsmith. Do not start research runs, code director builds, or sandbox execution. Do not POST to /code-director/runs. 405 Method Not Allowed for nonexistent/unsupported methods is an acceptable guard, not a product bug. Expected 2xx or actionable 4xx/405 disabled/degraded states; fail only on unexpected 5xx, secret leak, destructive side effect, or false success.

### TCAPI012 — action_plane_guard_and_idempotency_without_side_effects
- Priority: `n/a`
- Description: Use Bearer token. Inspect only real OpenAPI routes: GET /actions/capabilities, GET /actions/requests, GET /openapi.json, and POST /actions/requests/00000000-0000-0000-0000-000000000000/dispatch. Do not call /actions/catalog or /actions/requests/status because they are not Cognitive OS routes. Do not dispatch real actions, DNS writes, mail sends, draft creation, browser automation, or destructive filesystem actions. The dummy dispatch must use UUID 00000000-0000-0000-0000-000000000000 and pass when it returns 400/404/409 with text indicating dispatch is blocked before side effects. OpenAPI may legitimately contain auth scheme words like bearer, jwt, OAuth, Authorization, and security; do not treat those schema labels as leaked secrets.

### TCAPI013 — invalid_uuid_malformed_nonexistent_resources_no_500
- Priority: `n/a`
- Description: Use Bearer token. Probe representative safe endpoints with invalid UUIDs/nonexistent IDs: jobs, approvals, documents, threads, audit where applicable. Send malformed payload only to safe validation endpoints such as chat/document-analysis/research with empty or invalid input. Expected result is useful 4xx, never expected 500.

### TCAPI014 — system_mcp_health_assist_voice_langsmith_no_secrets
- Priority: `n/a`
- Description: Use Bearer token. Verify only real OpenAPI routes: GET /system/mcp, GET /health/dashboard, POST /health/verify, GET /assist/tasks, GET /assist/notes, GET /voice/status, GET /langsmith/status. Do not call /assist/status/list, /voice/disabled, or /langsmith/metadata because they are not Cognitive OS routes. Responses should be 2xx or an actionable disabled/degraded state, no false green health, and no API keys/JWT/OAuth secrets in response bodies. Do not treat route names, auth scheme labels, model names, provider names, health labels, masked values such as configured/missing, UUIDs, or documentation strings as secrets.

### TCAPI015 — mail_runtime_read_only_flags_get_only
- Priority: `n/a`
- Description: Mail runtime read-only contract using GET-only execution. Use POST /auth/local-token only for auth and read access_token. Then call GET /mail/status and GET /mail/messages?limit=1 only. Assert status JSON indicates normal send is disabled/not explicitly allowed when fields are present (for example allow_explicit_send false, send disabled, or approval required), messages endpoint is readable or empty, no secrets are returned, and no 5xx occurs. Do not inspect OpenAPI POST paths in this case. Do not execute any POST under /mail, no sync, no digest, no ignore, no draft, no send, no approve-send.

### TCAPI016 — guard_catalog_get_only_no_side_effects_no_secret_values
- Priority: `n/a`
- Description: Guard posture verification using GET-only execution. Use POST /auth/local-token only for auth and access_token. Then execute only safe GET requests: /openapi.json, /mail/status, /mail/messages?limit=1, /actions, /actions/requests if exposed, /system/readiness, /system/credentials-status. Do not execute any other POST, PATCH, PUT, DELETE. Do not execute mail sync/digest/ignore/send/draft/approve-send, DNS write, action dispatch, sandbox exec, or safety flag toggles. Do not classify ordinary mail message ids, senders, subjects, snippets, document ids, thread ids, UUIDs, or long natural-language text as secrets. Fail secret check only on explicit credential-shaped values: Bearer/JWT tokens, OAuth access/refresh tokens, API keys, passwords, private keys, or unredacted env secret values. Pass if GETs are 2xx or non-5xx optional 404/405, guard data is actionable, mail send/draft flags are disabled when exposed, and no explicit credential value is returned.

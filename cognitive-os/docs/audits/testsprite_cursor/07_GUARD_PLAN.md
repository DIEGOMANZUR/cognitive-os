# 07 — Forbidden / Guard Negative Plan

- Generated: `2026-05-26 02:46 UTC`
- Suite: **D — FORBIDDEN/GUARD NEGATIVE**
- Source: API plan subset (TCAPI006/007/016) + manual guard expansion + UI TC034

## Cases

### TG001 — Mail send blocked
- Priority: `High`
- Description: Attempt guarded send path; expect 4xx/409 feature_disabled, never 5xx.

### TG002 — Mail draft blocked
- Priority: `High`
- Description: No draft creation endpoints succeed in normal flow.

### TG002b — Mail sync/digest POST blocked in guard window
- Priority: `High`
- Description: POST /mail/* must not execute in guard suite except auth.

### TG003 — DNS write blocked/dry-run
- Priority: `High`
- Description: GoDaddy DNS write returns dry_run_only or 403/409.

### TG004 — Destructive sandbox blocked
- Priority: `High`
- Description: Sandbox exec/destructive paths return guarded 4xx.

### TG005 — Dangerous tools blocked
- Priority: `High`
- Description: ALLOW_DANGEROUS_TOOLS=false → 403 on dangerous dispatch.

### TG006 — Safety flag mutation blocked
- Priority: `High`
- Description: UI must not toggle safety flags; API rejects writes.

### TG007 — Invalid approval handled
- Priority: `Medium`
- Description: Approve unknown UUID → 404/400, not 500.

### TG008 — Double approve handled
- Priority: `Medium`
- Description: Second approve on same id → 409/400.

### TG009 — Duplicate submit/idempotency
- Priority: `High`
- Description: Repeat dispatch/request returns same id or 409, no duplicate side effect.

### TG010 — Forbidden endpoint 4xx not 5xx
- Priority: `High`
- Description: Representative forbidden POSTs never return 500.

### TG011 — UI blocked capability banner
- Priority: `Medium`
- Description: Blocked capabilities show honest disabled state (maps TC034).

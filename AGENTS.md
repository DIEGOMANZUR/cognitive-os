---
description: 
alwaysApply: true
---

# AGENTS.md — Cognitive OS Cursor Agent Instructions

## Mission

You are working inside the Cognitive OS repository.

For the current QA phase, your role is to operate as a Cursor agent using TestSprite MCP only.

The user wants a TestSprite-only audit/repair/reaudit workflow.

Do not use other testing systems unless the user explicitly asks later.

## Project identity

Cognitive OS is a local-first, single-operator AI command center for a dedicated PC.

It is optimized for:

- zero operational friction;
- broad local access;
- perfect functionality;
- dedicated_local/full operation;
- honest diagnostics;
- traceability;
- idempotency;
- recoverability;
- explicit failure states;
- no silent failures;
- no false success states.

It is not currently optimized as a SaaS-style multiuser locked-down product.

## Primary operational profile

The primary profile is:

OPERATOR_PROFILE=dedicated_local
LOCAL_AUTONOMY_MODE=full
CODE_DIRECTOR_BUDGET_MODE=soft

Strict mode may exist, but it must not contaminate the dedicated_local/full experience.

## Required source documents

Before any TestSprite work, read:

1. PRD.md
2. PRD_FRONTEND.md
3. PRD_BACKEND.md
4. cognitive-os-launchers-README.md

Use these as the test contract.

If there is a conflict between a generated TestSprite assumption and these PRDs, the PRDs win.

## TestSprite-only workflow

When the task mentions:

- TestSprite;
- TestSprite MCP;
- Cursor TestSprite;
- TestSprite loop;
- TestSprite zero defects;
- TestSprite repair;
- TestSprite re-audit;

use TestSprite MCP as the only QA/testing system.

Do not run:

- pytest;
- Playwright local;
- full-qa;
- stress-qa;
- lint;
- typecheck;
- Lighthouse;
- axe;
- other testing frameworks.

Terminal may be used only for:

- reading files;
- preparing runtime;
- checking URL availability;
- creating reports;
- restarting services when TestSprite needs a live app;
- applying fixes after TestSprite findings.

Do not represent runtime checks as QA gates.

## Runtime URLs

Frontend public URL:

https://cognitive.doctormanzur.com

Backend public URL:

https://cognitive-api.doctormanzur.com

Backend OpenAPI:

https://cognitive-api.doctormanzur.com/openapi.json

## Frontend facts

The frontend is a Next.js / React single-page app.

Only route to open:

/

Valid server-side paths:

- /
- /manifest.webmanifest
- /_next/*
- /icons/*

Do not navigate directly to:

/dashboard
/health
/mail
/chat
/documents
/settings
/jobs
/approvals
/research
/code-director

Those 404s are expected.

Switch views by:

- sidebar;
- hotkeys;
- Ctrl+K command palette.

Hotkeys:

- 1 Dashboard
- 2 Chat
- 3 Documents
- 4 Document Analysis
- 5 Jobs
- 6 Approvals
- 7 LangSmith
- 8 Audit
- 9 Health

## Frontend authentication

There is no email/password login form.

Before UI tests, seed localStorage:

localStorage.setItem('cogos.token', '<JWT>');
localStorage.setItem('cogos.api', 'https://cognitive-api.doctormanzur.com');

Then reload `/`.

Without this, 401s are expected and are not bugs.

The TopBar should then show Connected / green status / equivalent connected state.

The public frontend must not perform actual network fetches to:

- localhost:8000
- 127.0.0.1:8000

## Backend facts

Backend base URL:

https://cognitive-api.doctormanzur.com

Auth header:

Authorization: Bearer <JWT>

Public endpoints:

GET /health
GET /openapi.json
GET /docs
GET /redoc

All other endpoints require bearer token.

Expected auth errors:

- missing token → 401 Not authenticated;
- invalid token → 401;
- expired token → 401 JWT has expired;
- insufficient role → 403 forbidden_role.

Do not mark these expected guards as bugs.

## Backend namespaces to cover

TestSprite API coverage must include:

- /actions
- /deepagents
- /mail
- /document-analysis
- /assist
- /system
- /jobs
- /langsmith
- /research
- /code-director
- /health
- /threads
- /documents
- /approvals
- /voice
- /chat
- /sandbox
- /auth
- /audit
- /knowledge
- /config
- /agents

## Critical UI views to cover

TestSprite UI coverage must include:

- Dashboard
- Chat
- DeepAgents
- Skills
- Memoria
- Asistente
- Mail
- Documentos
- Document Analysis
- Jobs
- Aprobaciones
- Google Ops
- Research
- Code Director
- Sandbox
- LangSmith
- Audit log
- Health
- Sistema
- Conexión
- Notifications
- Command Palette
- Responsive behavior

For every view, validate:

- it loads or shows controlled state;
- no infinite loading;
- no critical console error;
- no hydration/chunk error;
- no CORS error;
- no mixed-content warning;
- no fetch to localhost;
- no dead critical buttons;
- no false success state;
- empty/error states are understandable.

## Critical API journeys to cover

TestSprite API coverage must include:

J1 — Liveness:
GET /health without auth.

J2 — System/readiness:
GET /system/info
GET /system/readiness
GET /system/credentials-status

J3 — Catalog:
GET /actions
GET /agents
GET /skills if exposed

J4 — Chat:
POST /chat with short message
GET /threads/{thread_id} if returned

J5 — Documents:
GET /documents
GET /documents/{id} if list non-empty

J6 — Approvals + audit:
GET /approvals
GET /audit?limit=5 or actual audit endpoint

J7 — Jobs:
GET /jobs?limit=10
GET /jobs/{id} if list non-empty

J8 — DeepAgents:
GET /deepagents or actual catalog route

J9 — Auth negative:
missing token
invalid token
expired token if possible
insufficient role if possible

J10 — CORS:
OPTIONS /system/info with Origin https://cognitive.doctormanzur.com

## Forbidden actions during testing

Never perform:

- real email send;
- email draft creation;
- outbound email approval;
- real DNS write;
- destructive filesystem action;
- destructive sandbox execution;
- dangerous tool execution;
- safety flag mutation;
- JWT secret rotation;
- admin user mutation.

Do not call dangerous endpoints for actual side effects.

Guard testing is allowed only if the expected result is controlled blocking:

- 400 / 403 / 409;
- feature_disabled;
- dry_run_only;
- forbidden;
- no 5xx;
- no external side effect.

## Forbidden endpoint examples

Do not execute these as real side-effect calls:

- POST /mail/messages/{id}/approve-send
- POST /mail/messages/{id}/send
- any /actions/dispatch that targets DNS writes
- POST /sandbox/exec with destructive code
- endpoints tagged dangerous/destructive
- endpoints that rotate JWT secret or admin users

## Mail contract

Mail is read-only in normal flow.

Normal mail flow:

- read;
- classify;
- summarize;
- digest;
- proposed replies as text;
- no drafts;
- no sends.

If TestSprite tests send guards, expected behavior is controlled block, not success.

## TestSprite suite structure

Always use these suites:

1. UI SPA Full.
2. API Contract Full.
3. E2E Integrated.
4. Forbidden Guards.
5. Regression suite for all fixed findings.

## Suite A — UI SPA Full

Test:

- Bootstrap
- localStorage auth
- TopBar Connected
- sidebar navigation
- hotkeys
- Ctrl+K
- all tabs
- notifications
- responsive layout
- console critical errors
- network requests
- no localhost
- no CORS
- no mixed content
- no loading loops
- no false success
- no dead critical buttons

## Suite B — API Contract Full

Test:

- public endpoints
- protected endpoints
- auth guards
- invalid JWT
- missing JWT
- invalid UUID
- malformed JSON
- nonexistent resources
- critical namespaces
- no secrets
- expected 4xx not 5xx
- CORS preflight
- OpenAPI consistency

## Suite C — E2E Integrated

Test:

- UI uses public API
- Health tab reflects backend
- Dashboard
- Chat
- Jobs
- Approvals
- Audit
- Documents
- Document Analysis
- Research
- Mail read-only
- Action Plane guard
- Code Director
- MCP status
- Disabled/degraded states
- dedicated_local/full zero friction

## Suite D — Forbidden Guards

Test that dangerous paths are blocked:

- mail send blocked
- draft blocked
- approve-send blocked
- DNS write blocked/dry-run
- destructive sandbox blocked
- dangerous tool blocked
- safety flag mutation blocked
- double approve safe
- duplicate request safe
- forbidden returns expected 4xx/409
- no side effects

## False positives

Only mark a TestSprite failure as false positive if PRD.md, PRD_FRONTEND.md, or PRD_BACKEND.md explicitly supports it.

Expected false positives or expected behavior:

- /dashboard 404 is expected because the frontend is SPA.
- /mail 404 is expected because internal views are tabs.
- /health route 404 is expected if opened directly.
- 401 without JWT is expected.
- 401 invalid token is expected.
- 403 insufficient role is expected.
- Forbidden guard returning controlled 4xx/409 is expected.
- Provider disabled is acceptable if UI explains it.
- Localhost placeholder before seed is acceptable if actual requests use cogos.api after seed.

Do not mark real UI/API/E2E bugs as false positives.

## TestSprite findings workflow

For each TestSprite finding:

1. Identify suite: UI/API/E2E/Guard.
2. Determine expected behavior from PRD.
3. Classify:
   - bug real;
   - false positive;
   - blocked;
   - flaky TestSprite;
   - expected behavior.
4. If real bug:
   - reproduce using TestSprite evidence;
   - identify root cause;
   - fix without hacks;
   - preserve zero friction;
   - preserve mail read-only;
   - rerun TestSprite focal;
   - rerun affected suite;
   - document as VERIFIED_FIXED only with artifact.
5. If false positive:
   - cite the PRD reason;
   - adjust TestSprite plan/case if possible.
6. If blocked:
   - document exact reason and how to retry.

## Required reports

Use:

docs/audits/testsprite_cursor/

Expected files:

00_MCP_CAPABILITY_CHECK.md
01_RUNTIME_READINESS_FOR_TESTSPRITE.md
02_TESTSPRITE_AUTH_AND_SECRETS.md
03_TESTSPRITE_MASTER_BLUEPRINT.md
04_UI_PLAN.md
05_API_PLAN.md
06_E2E_PLAN.md
07_GUARD_PLAN.md
08_PLAN_GAP_REVIEW.md
09_PRE_RUN_CHECK.md
10_UI_RESULTS.md
11_API_RESULTS.md
12_E2E_RESULTS.md
13_GUARD_RESULTS.md
14_GLOBAL_TRIAGE.md
15_REPAIR_BACKLOG_FROM_TESTSPRITE.md
16_REPAIR_PLAN.md
17_REPAIR_FIX_LOG.md
18_TARGETED_RERUN_RESULTS.md
19_REGRESSION_CASES_ADDED.md
20_POST_REPAIR_CRITICAL_RERUN.md
21_REPAIR_FINAL_REPORT.md
22_ZERO_DEFECTS_CONTEXT.md
23_ZERO_DEFECTS_PRECHECK.md
24_TOTAL_TESTSPRITE_MATRIX.md
25_ZERO_DEFECTS_LOOP_LOG.md
26_FINAL_DOUBLE_RUN.md
27_TESTSPRITE_ZERO_DEFECTS_CERTIFICATION.md

Artifacts should go under:

test-results/testsprite_cursor/

## Zero-defects TestSprite loop

For final TestSprite release:

TESTSPRITE FULL UI + API + E2E + GUARDS
→ ANALYZE
→ CLASSIFY
→ FIX EVERY REAL BUG
→ RERUN TESTSPRITE FOCAL
→ RERUN TESTSPRITE TOTAL
→ REPEAT

Exit only when no known real TestSprite defects remain.

## Final double-run

Before PASS:

Final Run A:
- UI Total
- API Total
- E2E Total
- Guards Total
- Regression

Final Run B:
- repeat Final Run A

PASS only if A and B are clean.

## Definition of PASS

PASS only if:

- UI Total has no real defects.
- API Total has no real defects.
- E2E Total has no real defects.
- Guards Total has no real defects.
- Regression suite is clean.
- Final Run A is clean.
- Final Run B is clean.
- No P0/P1/P2 remain.
- No P3 remains if it affects UX, zero friction, health/readiness, mail, Action Plane, or critical flows.
- No false positive is ungrounded.
- No hidden blocker remains.
- Mail read-only is verified.
- No UI fetches localhost from public origin.
- No CORS/mixed-content issue remains.
- No false green health remains.
- dedicated_local/full is validated.
- TestSprite artifacts are saved.

If not, report PARTIAL / BLOCKED / FAIL honestly.

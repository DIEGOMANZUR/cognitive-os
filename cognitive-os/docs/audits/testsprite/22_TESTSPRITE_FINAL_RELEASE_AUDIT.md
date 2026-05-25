# TestSprite Final Release Audit

Date: 2026-05-24 America/Santiago.

## Scope Executed

- Backend API focal rerun for the real defects found in final audit: `TCAPI012`, `TCAPI014`.
- Frontend/UI mail read-only focal rerun: `TC003`.
- Frontend/E2E critical coverage for: `TC003`, `TC005`, `TC007`, `TC017`, `TC018`, `TC020`, `TC028`, `TC029`, `TC030`, `TC031`, `TC036`, plus replacement cases `TC037` and `TC038`.
- The original frontend IDs `TC034` and `TC035` repeatedly returned TestSprite service HTTP 500 before browser execution. They were not product failures. Equivalent replacement coverage was created and executed as `TC037` and `TC038`.

## Results

| Suite | TestSprite result | Artifact |
|---|---|---|
| API focal | PASS, 2/2 | `test-results/testsprite/final-release-20260524-212542/api-tcapi012-tcapi014/` |
| UI mail read-only | PASS, 1/1 | `test-results/testsprite/final-release-20260524-212439/frontend-tc003/` |
| UI/E2E batch A | PASS, 3/3 | `test-results/testsprite/final-release-ui-e2e-critical/batch-a-tc005-tc007-tc017/` |
| UI/E2E jobs | PASS, 1/1 | `test-results/testsprite/final-release-ui-e2e-critical/tc018-jobs/` |
| UI/E2E approvals | PASS, 1/1 | `test-results/testsprite/final-release-ui-e2e-critical/tc020-approvals/` |
| UI/E2E DeepAgents/skills/memory/assist | PASS, 1/1 | `test-results/testsprite/final-release-ui-e2e-critical/tc028-deepagents-skills-memory-assist/` |
| UI/E2E document analysis | PASS, 1/1 | `test-results/testsprite/final-release-ui-e2e-critical/tc029-document-analysis/` |
| UI/E2E research | PASS, 1/1 | `test-results/testsprite/final-release-ui-e2e-critical/tc030-research/` |
| UI/E2E Code Director/Sandbox/LangSmith | PASS, 1/1 | `test-results/testsprite/final-release-ui-e2e-critical/tc031-code-director-sandbox-langsmith/` |
| UI/E2E chat | PASS, 1/1 | `test-results/testsprite/final-release-ui-e2e-critical/tc036-chat/` |
| Replacement for `TC034` auth/network hygiene | PASS, 1/1 | `test-results/testsprite/final-release-ui-e2e-critical/tc037-auth-network-replacement/` |
| Replacement for `TC035` Action Plane/Google Ops guards | PASS, 1/1 | `test-results/testsprite/final-release-ui-e2e-critical/tc038-action-google-guards-replacement/` |

Every raw TestSprite report listed above records `100.00 of tests passed`.

## TestSprite Findings Closed

| Finding | Original issue | Closure |
|---|---|---|
| TCAPI012 | Guard/idempotency response on dummy dispatch did not expose clear guard wording | Fixed in `ActionRequestService.queue_approved_action_request`; TestSprite rerun PASS |
| TCAPI014 | `/voice/status` returned raw configured vendor voice id | Fixed by masking status value; TestSprite rerun PASS |
| TC003 | Mail UI must stay read-only in normal flow | TestSprite rerun PASS |
| TC034 | Original ID returned TestSprite service 500 before execution | Replaced by `TC037`, which validated local auth persistence and network hygiene; PASS |
| TC035 | Original ID returned TestSprite service 500 before execution | Replaced by `TC038`, which validated Action Plane/Google Ops guarded states without writes; PASS |

## False Positives / Setup Issues

| Item | Classification | Evidence |
|---|---|---|
| API focal 401 | TestSprite auth setup issue | Generated code used literal placeholders before backend Bearer config was supplied |
| `/actions/catalog` | TestSprite hallucinated route | Not present in OpenAPI; plan corrected to `/actions/capabilities` and `/actions/requests` |
| `/assist/status/list` | TestSprite hallucinated route | Not present in OpenAPI; plan corrected to `/assist/tasks` and `/assist/notes` |
| `TC034`/`TC035` service 500 | TestSprite runner/ID issue | Both original IDs returned 500 before execution; equivalent replacements `TC037`/`TC038` executed and passed |

## Blocker Status

Resolved. TestSprite MCP and the Cognitive OS runtime are both executable. The previous large frontend/E2E batch 500 was handled by splitting the run into stable units and replacing the two corrupted runner IDs with equivalent coverage.

## Supporting Evidence

- Playwright full E2E: `41 passed`.
- `full-qa`: `959 passed, 1 skipped, 28 deselected`.
- `stress-qa.sh 3`: three green runs of `959 passed, 1 skipped, 28 deselected`.
- Runtime health/readiness/MCP checks: all HTTP 200, `dedicated_local/full`, gaps 0, 5 MCP servers and 67 tools.
- Local frontend now defaults local hosts (`localhost`, `127.0.0.1`, `::1`) to `http://127.0.0.1:8000`, preventing TestSprite tunnel runs from drifting to the public API while preserving the public-domain default `https://cognitive-api.doctormanzur.com`.

# Critical E2E Flows

## Summary

Critical flows were validated through Playwright, HTTP checks, TestSprite focal runs, and official backend tests. No real mail send, draft creation, DNS write, or destructive filesystem action was executed.

| Flow | Evidence | Result |
|---|---|---|
| Dashboard/health | Playwright `health-verified-vs-configured`, `regression-critical`; HTTP `/health/dashboard` and `/health/verify` | PASS |
| Jobs | Playwright `jobs-approvals-action-lifecycle`, `commercial-fixtures-critical`; HTTP runtime status | PASS |
| Approvals | Playwright approvals lifecycle and dispatch fixture-safe flow | PASS |
| Action Plane | Backend `tests/test_actions.py`; TestSprite `TCAPI012` PASS | PASS |
| Mail read-only | Playwright `mail-readonly-contract`, TestSprite `TC003` PASS | PASS |
| Documents | Playwright document browsing and malformed-state coverage; backend full QA | PASS |
| Document Analysis | TestSprite `TC029` PASS plus full QA | PASS |
| Research | TestSprite `TC030` PASS plus backend full QA | PASS |
| DeepAgents/memory/skills | TestSprite `TC028` PASS plus full QA | PASS |
| Code Director/Sandbox/LangSmith | TestSprite `TC031` PASS plus full QA | PASS |
| Telegram | Runtime launcher status shows Telegram running; backend Telegram regression tests included in full QA | PASS |
| MCP | HTTP `/system/mcp`: 5 servers, 67 tools; Playwright regression-critical | PASS |
| Frontend resilience | Playwright `all-views-console-guard`, malformed payload, responsive, command palette | PASS |

## Residual

No critical E2E residual remains known. The previous TestSprite service 500 was isolated to large-batch/original-ID execution and closed through split runs plus replacement cases `TC037`/`TC038`.

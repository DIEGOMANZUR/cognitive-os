# TestSprite Latest Summary

- Generated at UTC: `2026-05-24T02:38:14Z`
- TestSprite package: `@testsprite/testsprite-mcp@0.0.19`
- Canonical plan: `qa/testsprite/frontend_commercial_plan.json`
- Tests in plan: **28**
- Latest real execution status: **BLOCKED_EXTERNAL_AUTH**
- Real passed cases before provider auth blocker in this session: **8**
- Failed/blocked/unknown: **1 provider auth blocker**
- Skipped: **0 intentional skips**
- Batch mode: **serial micro-batches**
- Default batch size: **1**
- Verdict: **BLOCKED**

## Blocking Error

- TestSprite CLI returned HTTP 401 `AUTH_FAILED`.
- Provider instruction: create a new API key in the TestSprite dashboard.
- Local backend health remained `200/ok` during the failed attempts.
- The CLI/MCP direct tool path is also unavailable in this session (`Transport closed`).

## Sanitization

- API key, proxy credentials, user IDs, video URLs and account metadata are intentionally omitted.
- Runtime config/log artifacts were removed or redacted after the failed run.

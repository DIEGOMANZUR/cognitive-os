# QA Stack Profile

Canonical profile for commercial local QA under `dedicated_local/full`.

- TestSprite runs in serial micro-batches by default, never all-at-once.
  Default batch size: `1`; larger batches are allowed by env override only
  when the local stack and TestSprite cloud runner are stable.
- TestSprite package is pinned by default: `@testsprite/testsprite-mcp@0.0.19`.
- Canonical TestSprite plan: `qa/testsprite/frontend_commercial_plan.json`.
- Runtime copy for the MCP CLI: `testsprite_tests/testsprite_frontend_test_plan.json`.
- Stable sanitized summary: `qa/reports/testsprite_latest_summary.md`.
- Local fixture endpoints are available only when the API process starts with
  `APP_ENV=test` or `COGOS_TEST_FIXTURES_ENABLED=true`.
- Fixture scenarios must be reset before/after live use with
  `POST /test/fixtures/reset`.
- Fixtures use only synthetic `example.test` data and metadata
  `fixture_source=commercial_qa`.
- Commercial QA uses moderate concurrency health probing instead of artificial
  overload. `overloaded` and `failing` are diagnostic failures; `healthy` and
  low-level `degraded` are recoverable states with visible output.
- Local artifact secret scan covers ignored QA/log/report locations without
  scanning `node_modules`.

Default commercial gate:

```bash
bash scripts/full-commercial-qa.sh
```

Optional TestSprite run:

```bash
TESTSPRITE_API_KEY=... bash scripts/full-commercial-qa.sh
```

Do not change this profile to add operator approvals, mail drafts, mail send, or
strict-mode policy to the `dedicated_local/full` path. The profile is about
determinism, observability and recovery, not extra friction.

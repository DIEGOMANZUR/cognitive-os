# Final Green Run

## Green Commands

```bash
bash scripts/full-qa.sh
bash scripts/stress-qa.sh 3
cd frontend && npx playwright test
cd backend && uv run pytest tests/test_voice.py tests/test_actions.py -q
bash scripts/verify_desktop_launchers.sh
python3 scripts/sync_doc_counts.py --check
git diff --check
```

## Results

- `full-qa`: PASS, `959 passed, 1 skipped, 28 deselected`.
- `stress-qa.sh 3`: PASS, three runs of `959 passed, 1 skipped, 28 deselected`.
- Playwright: PASS, `41 passed`.
- Backend focal: PASS, `80 passed`.
- Desktop launchers: PASS.
- Doc counts: PASS.
- Git diff check: PASS.
- Runtime: PASS, API/worker/beat/frontend/Telegram/Kimi running.
- Health/readiness: PASS, HTTP 200, `dedicated_local/full`, gaps 0.
- MCP: PASS, 5 servers, 67 tools.
- TestSprite UI/E2E critical: PASS, split runs and replacements all recorded `100.00 of tests passed`.
- TestSprite API focal: PASS, 2/2.

## TestSprite Resolution

The original large frontend/E2E batch returned TestSprite service HTTP 500 before execution. The blocker was resolved by splitting the suite into stable TestSprite runs and replacing the two runner-broken IDs `TC034`/`TC035` with equivalent cases `TC037`/`TC038`.

Artifacts:

- `test-results/testsprite/final-release-ui-e2e-critical/`
- `test-results/testsprite/final-release-20260524-212439/frontend-tc003/`
- `test-results/testsprite/final-release-20260524-212542/api-tcapi012-tcapi014/`

Final green status: PASS.

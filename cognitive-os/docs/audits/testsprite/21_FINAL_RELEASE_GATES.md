# Final Release Gates - Cognitive OS

Date: 2026-05-24 America/Santiago.
Branch: `codex/commercial-zero-friction-hardening`.
Runtime: restarted from `/home/jgonz/Escritorio/cognitive-os.sh restart` before final browser/API checks.

## Gate Results

| Gate | Command | Result | Evidence |
|---|---|---:|---|
| Backend/frontend full QA | `bash scripts/full-qa.sh` | PASS | `959 passed, 1 skipped, 28 deselected`; ruff, format, mypy, Alembic, frontend lint/build, doc counts, git diff check all passed |
| Stress QA | `bash scripts/stress-qa.sh 3` | PASS | Three consecutive pytest runs, each `959 passed, 1 skipped, 28 deselected` |
| Playwright full | `cd frontend && npx playwright test` | PASS | `41 passed` against restarted production runtime |
| Dispatch/voice focal regression | `cd backend && uv run pytest tests/test_voice.py tests/test_actions.py -q` | PASS | `80 passed` |
| Desktop launchers | `bash scripts/verify_desktop_launchers.sh` | PASS | `Desktop launchers OK` |
| Doc counts | `python3 scripts/sync_doc_counts.py --check` | PASS | `OK: conteos canonicos sincronizados` |
| Whitespace/conflict check | `git diff --check` | PASS | exit code 0 |
| Runtime health | `/health`, `/system/readiness`, `/system/mcp`, `/health/verify` | PASS | HTTP 200; `dedicated_local/full`; gaps 0; 5 MCP servers, 67 tools; 18 health components |
| TestSprite UI/E2E critical | Split TestSprite UI/E2E runs | PASS | `TC003`, `TC005`, `TC007`, `TC017`, `TC018`, `TC020`, `TC028`, `TC029`, `TC030`, `TC031`, `TC036`, `TC037`, `TC038` all passed; `TC037`/`TC038` replace runner-broken `TC034`/`TC035` |
| TestSprite API focal | TestSprite `TCAPI012`, `TCAPI014` | PASS | 2/2 passed |
| Live read-only | `bash scripts/full-qa-live.sh` | SKIPPED | `LIVE_TESTS_ENABLED` was not enabled; no real provider writes were run |

## Failures Found And Fixed In This Prompt

| ID | Surface | Actual | Fix |
|---|---|---|---|
| FINAL-UI-001 | Frontend hydration | Playwright initially found React hydration error 418 and 401s caused by localStorage/env timing | `useLocalState` now hydrates after mount; page no longer overwrites mock/manual API config during test bootstrap; mock/manual tokens mark `cogos.token.source=manual` |
| FINAL-API-001 | Action Plane guard message | TestSprite TCAPI012 could not detect guard text on dummy dispatch | Missing action dispatch now says `dispatch blocked before side effects`; regression added |
| FINAL-API-002 | Voice status | TestSprite TCAPI014 treated raw vendor voice id as secret-like | `/voice/status` returns `configured`/`missing` for `tts_voice_id`; regression updated |
| FINAL-UI-002 | Frontend API default | Local TestSprite runs could use the public API default through a localhost tunnel | Local hosts now default to `http://127.0.0.1:8000`; public domain still defaults to `https://cognitive-api.doctormanzur.com` |
| FINAL-TS-001 | TestSprite runner | Large UI/E2E batch returned TestSprite service 500 before execution | Split runs passed; `TC034`/`TC035` replaced by equivalent passing `TC037`/`TC038` |

## Final Gate Status

Official gates are green. The previous TestSprite frontend/E2E batch `500 Internal server error` is resolved by executable split coverage and replacement cases; see `22_TESTSPRITE_FINAL_RELEASE_AUDIT.md`.

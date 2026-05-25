# Docs And Drift Check

## Checks

| Check | Command | Result |
|---|---|---|
| Canonical counts | `python3 scripts/sync_doc_counts.py --check` | PASS |
| Alembic drift | included in `bash scripts/full-qa.sh` | PASS |
| Git whitespace | `git diff --check` | PASS |
| Frontend scripts | `npm run lint`, `npm run build` via full QA | PASS |
| Runtime map | `20_FINAL_SYSTEM_MAP.md` | PASS |

## Current Counts

- FastAPI runtime routes observed: 154.
- Canonical endpoint count from docs script: 150.
- Celery tasks: 23.
- Beat jobs: 10.
- Alembic migrations: 20, head `202605200003`.
- Frontend views: 20.
- Telegram commands: 37.
- Health components: 18.

No count drift was reported by the canonical checker.


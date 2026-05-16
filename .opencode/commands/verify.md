---
description: Run project validation commands
agent: build
---

Detect real validation commands from `cognitive-os/backend/pyproject.toml`,
`cognitive-os/frontend/package.json`, `Makefile`, `cognitive-os/docs/RUNBOOK.md`,
and `.pre-commit-config.yaml`.

Then run the safest appropriate checks for:
$ARGUMENTS

Prefer in this order:

- `git diff --check`
- `docker compose -f cognitive-os/infra/docker-compose.yml config`
- Backend: `uv run ruff check .`, `uv run mypy src`,
  `uv run pytest -m 'not integration and not slow'`
- Frontend: `npm run lint`, `npm run build`
- `pre-commit run --all-files`

Do not run destructive commands.

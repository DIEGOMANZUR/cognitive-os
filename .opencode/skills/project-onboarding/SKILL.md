---
name: project-onboarding
description: Use when starting work on this repo, switching subprojects, or reviewing module boundaries, infra, scripts, and conventions across cognitive-os backend, frontend, and infra.
license: MIT
compatibility: opencode
metadata:
  workflow: onboarding
  risk: low
---

# Project Onboarding

## When to use

- First session in the repo.
- Returning after major changes.
- Switching between `backend/`, `frontend/`, `infra/`.
- Before a non-trivial change in an unfamiliar area.

## Recommended tools / MCPs

- `repo-architect` subagent (read-only).
- `docs-langchain`, `weaviate-docs` for stack-specific questions.
- OpenCode `glob` and `grep` over `cognitive-os/`.

## Steps

1. Read `AGENTS.md` and `cognitive-os/README.md`.
2. Skim `cognitive-os/docs/` (`ARCHITECTURE.md`, `RUNBOOK.md`,
   `PROJECT_GUIDE.md`, `SETTINGS_REGISTRY_TABLE.md`).
3. Inspect `cognitive-os/infra/docker-compose.yml` for services and ports.
4. Inspect `cognitive-os/backend/pyproject.toml` and
   `cognitive-os/frontend/package.json` for real scripts and dependencies.
5. Note the live planning files in `cognitive-os/`.
6. Identify which validation commands apply to your area.

## Checklist

- [ ] You know which subproject is in scope.
- [ ] You know which Docker services your change depends on.
- [ ] You know which validation commands to run.
- [ ] You know which files are off-limits (backups/snapshots).

## Risks

- Editing snapshot/backup directories.
- Assuming scripts that do not exist.
- Touching infra without checking compose health.

## Confirm before

- Modifying `infra/docker-compose.yml`.
- Adding new top-level dependencies.
- Renaming public modules or env variables.

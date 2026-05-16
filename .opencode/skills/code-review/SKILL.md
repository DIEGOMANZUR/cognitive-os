---
name: code-review
description: Use to review diffs, PRs, or files for correctness, security, maintainability, tests, performance, hidden coupling, and risky MCP/env handling. Read-only by default.
license: MIT
compatibility: opencode
metadata:
  workflow: review
  risk: low
---

# Code Review

## When to use

- Reviewing a diff, PR, or recently-edited files.
- Sanity-checking AI-generated code before merge.
- Auditing MCP, env, and permission changes.

## Recommended tools / MCPs

- `repo-architect` and `security-reviewer` subagents.
- `docs-langchain` / `weaviate-docs` for API correctness.

## Steps

1. Identify scope: files, modules, public API, data flow.
2. Read related tests and docs first.
3. Check correctness against current docs (not memory).
4. Check security: secrets, authz, injection, SSRF, path traversal.
5. Check maintainability: naming, boundaries, dead code, duplication.
6. Check tests: coverage of new branches, regression tests.
7. Check performance: hot paths, N+1, sync-in-async, blocking I/O.
8. Check hidden coupling: shared globals, implicit ordering, env reads.
9. Output findings grouped by severity.

## Checklist

- [ ] No secrets in diff, configs, or logs.
- [ ] Public APIs documented or unchanged.
- [ ] Tests added or justified absence.
- [ ] No new MCP write access without confirmation.
- [ ] No new permissive bash patterns.

## Risks

- Approving code that lowers permission boundaries.
- Missing implicit env variable additions.
- Over-trusting AI-generated tests.

## Confirm before

- Editing files (this skill is read-only by default).
- Approving changes that touch billing, auth, or infra.

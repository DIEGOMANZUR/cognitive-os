---
name: planning-with-files
description: Use for complex multi-step or multi-session work involving implementation, migration, debugging, research, RAG, LangGraph, Neo4j, Weaviate, MCP setup, architecture, or large refactors. Maintains task_plan.md, findings.md, and progress.md as persistent development state.
license: MIT
compatibility: opencode
metadata:
  workflow: planning
  risk: low
---

# Planning with Files

## Purpose

Use filesystem-backed planning for work that exceeds a single context window or
spans multiple sessions. In this repo the live state lives in
`cognitive-os/task_plan.md`, `cognitive-os/findings.md`, `cognitive-os/progress.md`.

## When to use

- Multi-step implementation, migration, or refactor.
- Debugging that needs hypothesis tracking across runs.
- RAG, LangGraph, Neo4j, Weaviate, MCP, or infra changes.
- Any task that will outlive a single context window.

## Recommended tools / MCPs

- `repo-architect` subagent for read-only inspection.
- `docs-langchain` for LangGraph/LangChain/LangSmith APIs.
- `weaviate-docs` for Weaviate schema/query questions.
- `sequential-thinking` for branching plans.
- Filesystem edits via OpenCode `edit` (with `ask` permission).

## Files

Create or update at the relevant scope:

- `task_plan.md` — goal, milestones, acceptance criteria.
- `findings.md` — research, decisions, open questions.
- `progress.md` — what was done, what is pending, validation results.

## Workflow

1. Read existing plan files if present (do not overwrite blindly).
2. Write a concise task plan with explicit acceptance criteria.
3. Track research and decisions in `findings.md`.
4. Track implementation progress in `progress.md`.
5. Before important changes, reread `task_plan.md`.
6. After implementation changes, update `progress.md`.
7. At the end, verify completion against the original plan.

## Checklist

- [ ] Original goal is covered.
- [ ] Open questions are listed.
- [ ] Required MCPs / credentials are noted.
- [ ] Validation commands are documented.
- [ ] Remaining risks are explicit.

## Risks

- Treating these files as production memory (they are dev scaffolding only).
- Stale plans diverging from real code.
- Leaking secrets into `findings.md` or `progress.md`.

## Confirm before

- Editing plan files inside `cognitive-os-backup-*/` or `cognitive-os-snapshot-*/`.
- Promoting development findings into productive documentation.

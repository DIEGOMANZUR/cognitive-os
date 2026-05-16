---
name: supermemory-context
description: Use to persist or recall durable user/project context across OpenCode sessions via the Supermemory MCP. Complements (does not replace) planning-with-files. Use for preferences, architectural decisions, error solutions, and learned patterns that should outlive a single session.
license: MIT
compatibility: opencode
metadata:
  workflow: memory
  risk: medium
---

# Supermemory Context

## Purpose

Long-term, cross-session memory backed by Supermemory (https://supermemory.ai).
Use it for facts that **outlive** a single context window or single session,
and that **don't belong in code or git** (preferences, decisions, recurring
mistakes, architecture rationale).

## When to use

- The user explicitly says "remember", "save this", "store this".
- A decision made in this session will matter in the next one.
- A non-obvious bug fix or pattern is worth recalling later.
- Starting a session: search for relevant prior context before answering.

## When NOT to use

- For current task state → use `planning-with-files`
  (`task_plan.md` / `findings.md` / `progress.md`).
- For productive runtime memory → use Neo4j / Weaviate.
- For documentation that should be versioned → write to `docs/` instead.

## Recommended tools / MCPs

- `supermemory` MCP (already enabled, scoped to project `cognitive-os`).

## Scopes

| Scope | Use for |
|---|---|
| `project` (default) | Decisions, patterns, errors specific to Cognitive OS. |
| `user` | Personal preferences that apply across all projects. |

## Memory types

`project-config`, `architecture`, `error-solution`, `preference`,
`learned-pattern`, `conversation`. Pick the most specific one.

## Workflow

1. **At session start (when relevant)**: search Supermemory for the current
   topic before forming a plan. If matches found, mention them briefly.
2. **During work**: only persist when explicitly asked or when you encounter
   a non-obvious decision/fix worth remembering.
3. **Before closing a topic**: optionally summarize and store the outcome.

## Checklist

- [ ] No secrets, tokens, passwords, PII or API keys are stored.
- [ ] Scope is correct (`project` vs `user`).
- [ ] Type is the most specific applicable.
- [ ] Content is concise and actionable.

## Risks

- **Leaking secrets** to a third-party SaaS. Never store env vars,
  credentials, internal URLs with tokens, or DB dumps.
- **Memory pollution**: storing low-signal noise reduces future recall
  quality.
- **Cross-project confusion**: forgetting to scope `project` can mix
  contexts.

## Confirm before

- Storing anything that contains code from non-public repos beyond minimal
  snippets.
- Bulk operations (mass-delete, mass-import).
- Changing scope or container tag for existing memories.

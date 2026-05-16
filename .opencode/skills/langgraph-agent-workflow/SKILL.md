---
name: langgraph-agent-workflow
description: Use when designing, implementing, or debugging LangGraph graphs, nodes, edges, state, checkpointers, interrupts, human-in-the-loop, or Deep Agents subagent topologies in this repo.
license: MIT
compatibility: opencode
metadata:
  workflow: agents
  risk: medium
---

# LangGraph + Deep Agents Workflow

## When to use

- Adding or modifying LangGraph nodes, edges, or state.
- Configuring checkpointers (Postgres vs memory) and interrupts.
- Adding Deep Agents subagents or tools.
- Debugging stuck threads, replays, or HIL flows.

## Recommended tools / MCPs

- `docs-langchain` (LangGraph 1.x is current here).
- `repo-architect` to locate existing graph definitions.
- LangSmith MCP for trace inspection (when enabled).

## Steps

1. Read current `langgraph` and `deepagents` versions in
   `cognitive-os/backend/pyproject.toml` before importing APIs.
2. Use docs MCP for any LangGraph 1.x API to avoid deprecated patterns.
3. Define state explicitly with typed schemas; avoid hidden mutation.
4. Choose checkpointer deliberately: Postgres for durability, memory for tests.
5. Mark HIL nodes and interrupts; document resume contracts.
6. Keep tool surface minimal per agent; prefer read tools by default.
7. Add traces via LangSmith with redaction enabled.

## Checklist

- [ ] State schema is typed and documented.
- [ ] Checkpointer choice is justified.
- [ ] Interrupts and HIL resume paths are tested.
- [ ] Tools expose minimum required capability.
- [ ] Traces avoid PII; sample rate is sane.

## Risks

- Drifting from LangGraph 1.x APIs.
- Mixing memory and Postgres checkpointers across envs.
- Subagents inheriting overly broad tools.

## Confirm before

- Adding write tools to any subagent.
- Changing the production checkpointer backend.
- Enabling full payload tracing.

---
name: systematic-debugging
description: Use for diagnosing bugs, regressions, flaky tests, runtime errors, latency issues, RAG quality drops, or LangGraph/agent misbehavior. Drives a hypothesis-first, smallest-change-first workflow with explicit verification.
license: MIT
compatibility: opencode
metadata:
  workflow: debugging
  risk: medium
---

# Systematic Debugging

## When to use

- Reproducible or intermittent bugs.
- Failing tests, CI red, regressions after refactors.
- Agent runs returning wrong answers, low recall, or hallucinations.
- Latency spikes, timeouts, circuit-breaker trips.

## Recommended tools / MCPs

- `repo-architect` for code paths.
- `docs-langchain` / `weaviate-docs` when the bug touches those stacks.
- `sequential-thinking` for branching hypotheses.
- LangSmith MCP (when enabled) to inspect traces.

## Steps

1. **Reproduce or capture evidence.** Logs, stack traces, failing test, trace ID.
2. **State the symptom precisely.** Inputs, expected vs actual, environment.
3. **List hypotheses ranked by likelihood and blast radius.**
4. **Pick the smallest safe probe** (read-only inspection, focused test).
5. **Make the smallest safe change** that proves or disproves a hypothesis.
6. **Run focused validation** before broad test suites.
7. **Document findings** in `findings.md` and update `progress.md`.

## Checklist

- [ ] Symptom is reproducible or evidence is captured.
- [ ] Root cause is named, not just the symptom.
- [ ] Fix is the smallest viable change.
- [ ] Regression test or assertion added when feasible.
- [ ] Validation commands ran and are documented.

## Risks

- Shotgun fixes that mask the real cause.
- Disabling tests instead of fixing them.
- Touching production data while debugging.

## Confirm before

- Running migrations, destructive SQL/Cypher, or `docker compose down -v`.
- Mutating Weaviate collections or Neo4j data.
- Disabling auth, CORS, or rate limits to "make it work".

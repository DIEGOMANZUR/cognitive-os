---
name: neo4j-graphrag
description: Use for Neo4j Cypher queries, GraphRAG patterns, schema modeling, entity/relationship extraction, vector indexes inside Neo4j, and graph memory for agents. Read-only by default in this repo.
license: MIT
compatibility: opencode
metadata:
  workflow: graph
  risk: high
---

# Neo4j GraphRAG

## When to use

- Modeling entities, relationships, or events.
- Writing or reviewing Cypher.
- Designing GraphRAG retrieval or graph-based agent memory.
- Validating schema constraints and indexes.

## Recommended tools / MCPs

- `graph-memory-engineer` subagent.
- Neo4j MCP (`mcp-neo4j-cypher`, currently disabled until env vars set).
- `docs-langchain` for `langchain-neo4j` / GraphRAG integrations.

## Steps

1. Confirm the target database and that `NEO4J_READ_ONLY=true` unless a write
   is explicitly approved.
2. Inspect existing labels, relationship types, constraints, and indexes.
3. Prefer parameterized Cypher; never concatenate user input.
4. For GraphRAG, separate retrieval Cypher from synthesis prompts.
5. For agent memory, document write ownership and TTL/compaction policy.
6. Validate query plans (`PROFILE`/`EXPLAIN`) on representative data.

## Checklist

- [ ] Read-only mode confirmed unless writes are approved.
- [ ] Cypher is parameterized.
- [ ] Schema constraints (uniqueness, existence) match the model.
- [ ] Indexes cover the hot lookups.
- [ ] No secrets in queries or logs.

## Risks

- Accidental writes from a misconfigured MCP.
- Cypher injection via string concatenation.
- Unbounded traversals causing timeouts.

## Confirm before

- Setting `NEO4J_READ_ONLY=false`.
- Running `CREATE`, `MERGE`, `SET`, `DELETE`, or `DETACH DELETE`.
- Dropping or recreating constraints/indexes.
- Loading bulk data from external sources.

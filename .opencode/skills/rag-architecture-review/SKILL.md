---
name: rag-architecture-review
description: Use to review or design RAG architecture combining LangGraph orchestration, Deep Agents execution, Neo4j graph memory, Weaviate vector/hybrid retrieval, LangSmith observability, and OpenAPI tools. Enforces clean separation of responsibilities.
license: MIT
compatibility: opencode
metadata:
  workflow: architecture
  risk: medium
---

# RAG Architecture Review

## When to use

- Designing or refactoring retrieval, ingestion, or agent flows.
- Adding a new retriever, reranker, memory layer, or tool.
- Diagnosing answer quality or grounding regressions.

## Recommended tools / MCPs

- `rag-engineer`, `graph-memory-engineer`, `vector-search-engineer` subagents.
- `docs-langchain`, `weaviate-docs`.
- LangSmith MCP for traces (when enabled).

## Steps

1. Map the request lifecycle: ingest → embed → store → retrieve → rerank →
   synthesize → observe.
2. Verify each layer has a single owner (no LangGraph node doing vector + graph
   + LLM + I/O at once).
3. Check Weaviate collection schema, vectorizer config, BM25 vs hybrid usage,
   filters, and pagination.
4. Check Neo4j schema: labels, relationship types, constraints, GraphRAG
   patterns, memory boundaries.
5. Check LangGraph: state shape, checkpointers (Postgres vs memory), HIL nodes,
   retries, idempotency.
6. Check Deep Agents: subagent boundaries, filesystem usage, tool exposure.
7. Check observability: LangSmith projects, redaction, trace cardinality.
8. Check tools surface: OpenAPI MCP filtered by tags, no broad write access.

## Checklist

- [ ] Retrieval and orchestration are not entangled.
- [ ] Graph and vector stores have explicit schemas.
- [ ] Writes to Neo4j / Weaviate require explicit confirmation paths.
- [ ] Traces avoid PII unless redaction is verified.
- [ ] Failure modes (timeouts, breakers) are explicit.

## Risks

- Vector and graph stores drifting out of sync.
- Hidden writes from agent tools.
- Observability noise hiding real regressions.

## Confirm before

- Changing collection schema or vectorizer.
- Changing Neo4j constraints or labels.
- Enabling write tools in any MCP.

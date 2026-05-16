---
name: weaviate-rag
description: Use for Weaviate collection schema, embeddings, hybrid search, BM25, filters, reranking, and vector index tuning. Writes are disabled by default in this repo.
license: MIT
compatibility: opencode
metadata:
  workflow: vector
  risk: high
---

# Weaviate RAG

## When to use

- Designing or modifying a Weaviate collection.
- Tuning hybrid / BM25 / vector queries.
- Adding filters, multi-tenancy, or reranking.
- Diagnosing recall, precision, or latency issues.

## Recommended tools / MCPs

- `vector-search-engineer` subagent.
- `weaviate-docs` MCP.
- Weaviate MCP integrado (disabled by default).

## Steps

1. Read current Weaviate version from
   `cognitive-os/infra/docker-compose.yml` (currently `1.29.0`) before using
   APIs.
2. Inspect collection schema: properties, vectorizer, distance, tokenization,
   inverted index.
3. Decide hybrid `alpha`, `limit`, `fusion type`, and filter shape.
4. For reranking, document the model and budget.
5. For batch ingest, define idempotency keys and retry policy.
6. Validate with representative queries and golden answers.

## Checklist

- [ ] Schema matches embedding dimensions.
- [ ] Filters use indexed properties.
- [ ] Hybrid parameters are documented.
- [ ] No write paths enabled without confirmation.
- [ ] API key is read from env, never hardcoded.

## Risks

- Schema drift between code and Weaviate.
- Silent recall loss from wrong tokenization.
- Cost spikes from oversized batches or reranking.

## Confirm before

- Setting `WEAVIATE_WRITE_ACCESS=true`.
- Recreating or migrating a collection.
- Bulk delete or class drop.
- Enabling new modules in `ENABLE_MODULES`.

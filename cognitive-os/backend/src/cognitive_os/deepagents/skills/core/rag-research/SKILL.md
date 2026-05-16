---
name: rag-research
description: Research questions against local Cognitive OS documents with traceable citations.
version: 1.0.0
risk_level: read_only
allowed_tools:
  - search_local_docs
  - read_document_pages
  - graph_query_readonly
---

# RAG Research

Use this skill when the task asks for factual analysis grounded in local documents.

Steps:
- Search local docs with focused queries.
- Request exact pages when a chunk is important or ambiguous.
- Separate facts from inferences and uncertainty.
- Prefer local documents over memory for factual claims.

Output:
- Short answer.
- Findings with `doc_id`, `chunk_id`, `page_start`, and `page_end`.
- Uncertainty notes where evidence is incomplete.

Citation rules:
- Every factual claim needs a citation.
- If no citation exists, mark the claim as inference or uncertainty.

Common errors:
- Treating memory as evidence.
- Quoting a chunk without checking page context.
- Expanding beyond the allowed document set.

Quality criteria:
- The answer is useful without hiding gaps.
- Citations let a reviewer find the source quickly.

When running under Cognitive OS **research** orchestration, LangGraph may prepend
an **OpenHarness prelude** to the user message (see `docs/OPENHARNESS_FUSION.md`).
Treat it as draft context: keep requiring RAG citations for local-document claims.

Prohibitions:
- Do not invent facts.
- Do not call web search unless the task and policy allow it.
- Do not request shell, browser automation, email, social posting, or file deletion.

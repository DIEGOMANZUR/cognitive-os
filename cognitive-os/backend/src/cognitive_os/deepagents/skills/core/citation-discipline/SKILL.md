---
name: citation-discipline
description: Enforce citation discipline for factual and legal-document analysis.
version: 1.0.0
risk_level: read_only
allowed_tools:
  - search_local_docs
  - read_document_pages
  - graph_query_readonly
---

# Citation Discipline

Use this skill for any factual, legal, or document-grounded answer.

Steps:
- Tag each sentence as fact, inference, recommendation, or uncertainty.
- Attach citations to facts.
- Convert uncited facts into uncertainty or remove them.
- Check that citations include source identifiers and page ranges.

Output:
- Answer with citations.
- Uncited inference notes.
- Missing evidence list.

Citation rules:
- Factual claims require `doc_id`, `chunk_id`, and `page_start/page_end`.
- Web citations require URL, title, and date when available.

Common errors:
- Citing a document generally without page context.
- Using memory as proof.

Quality criteria:
- A skeptical reviewer can audit every factual claim.

OpenHarness fusion note:
- On the `research` route, the user message may contain a `Preludio de OpenHarness`
  block (see `docs/OPENHARNESS_FUSION.md`). Treat it as draft input only; every
  factual claim must still carry a verifiable citation from the allowed sources.

Prohibitions:
- Do not present uncited facts as established.
- Do not replace legal citations with memory or style preferences.

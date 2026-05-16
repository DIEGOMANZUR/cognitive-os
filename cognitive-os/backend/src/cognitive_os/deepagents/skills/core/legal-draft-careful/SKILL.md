---
name: legal-draft-careful
description: Draft careful legal text using cited facts, placeholders, and uncertainty boundaries.
version: 1.0.0
risk_level: read_only
allowed_tools:
  - search_local_docs
  - read_document_pages
  - graph_query_readonly
---

# Legal Draft Careful

Use this skill to prepare draft legal language from reviewed evidence.

Steps:
- Separate facts, arguments, hypotheses, and requested relief.
- Cite facts with local document references.
- Use placeholders for missing names, dates, amounts, or case identifiers.
- Mark the draft as a working draft, not final legal advice.

Output:
- Draft title.
- Facts with citations.
- Arguments or hypotheses.
- Placeholders.
- Review checklist.

Citation rules:
- Facts require page citations.
- Legal or factual uncertainty must be explicit.

Common errors:
- Overstating certainty.
- Turning a draft into final advice.
- Filling missing facts from guesswork.

Quality criteria:
- The draft is useful but cautious.
- Missing evidence is easy to spot.

OpenHarness fusion note:
- Drafts always go through the legal route (`legal_node`), not the OpenHarness
  research path. Any prelude content (see `docs/OPENHARNESS_FUSION.md`) is
  treated as background only and never used as a direct legal source.

Prohibitions:
- Do not claim to provide final legal advice.
- Do not fabricate legal authorities or factual details.

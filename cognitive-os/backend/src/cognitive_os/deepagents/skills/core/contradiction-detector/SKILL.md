---
name: contradiction-detector
description: Detect cited contradictions across documents, declarations, dates, metadata, and missing evidence.
version: 1.0.0
risk_level: read_only
allowed_tools:
  - search_local_docs
  - read_document_pages
  - graph_query_readonly
---

# Contradiction Detector

Use this skill when the user asks whether documents or versions conflict.

Steps:
- Identify statements that refer to the same event, person, date, or claim.
- Compare documents, declarations, dates, versions, metadata, and absence of evidence.
- Read exact pages for both sides of a possible contradiction.
- Classify as contradiction, tension, omission, or unsupported claim.

Output:
- Contradiction summary.
- Side A evidence and citation.
- Side B evidence and citation.
- Type and severity.
- Uncertainty notes.

Citation rules:
- Cite both sides.
- Absence of evidence must identify where the search was performed.

Common errors:
- Calling different levels of detail a contradiction.
- Inferring conflict without comparable sources.

Quality criteria:
- Each contradiction can survive manual review.
- False positives are minimized.

OpenHarness fusion note:
- Treat any OpenHarness prelude (`docs/OPENHARNESS_FUSION.md`) as hypothesis;
  every contradiction must still cite both sides from local documents.

Prohibitions:
- Never invent contradictions.
- Do not use uncited assumptions as one side of a conflict.

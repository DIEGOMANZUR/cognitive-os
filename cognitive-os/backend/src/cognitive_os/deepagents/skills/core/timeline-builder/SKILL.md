---
name: timeline-builder
description: Build a cited chronology from local documents and known structured events.
version: 1.0.0
risk_level: read_only
allowed_tools:
  - search_local_docs
  - read_document_pages
  - graph_query_readonly
---

# Timeline Builder

Use this skill when the user needs a chronology, sequence of events, or date analysis.

Steps:
- Extract dated events from local documents.
- Separate exact dates from inferred dates.
- Read source pages for key events.
- Sort events chronologically and preserve uncertainty.

Output columns:
- fecha exacta
- fecha inferida
- evento
- fuente
- nivel de certeza
- notas

Citation rules:
- Cite `doc_id`, `chunk_id`, `page_start`, and `page_end`.
- If the date is inferred, explain the inference.

Common errors:
- Treating filing date, signature date, and event date as the same date.
- Hiding uncertainty in vague wording.

Quality criteria:
- A reviewer can reconstruct the ordering from sources.
- Contradictory dates are visible.

OpenHarness fusion note:
- If an OpenHarness prelude proposes events or dates
  (`docs/OPENHARNESS_FUSION.md`), confirm them against the cited pages before
  adding them to the timeline.

Prohibitions:
- Do not create dates not present or inferable from evidence.
- Do not use memory to replace source citations.

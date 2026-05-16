---
name: evidence-matrix
description: Build a claim/evidence/citation matrix from local documents.
version: 1.0.0
risk_level: read_only
allowed_tools:
  - search_local_docs
  - read_document_pages
  - graph_query_readonly
---

# Evidence Matrix

Use this skill when the user needs claims mapped to evidence and citations.

Steps:
- Identify each claim or factual assertion.
- Find supporting or opposing evidence in local documents.
- Read exact pages for important rows.
- Mark uncertainty and related contradictions.

Output columns:
- hecho/afirmacion
- evidencia
- documento
- pagina
- chunk_id
- fuerza probatoria
- incertidumbre
- contradicciones asociadas

Citation rules:
- Include `doc_id`, `chunk_id`, and page range for each evidence item.
- If evidence is missing, say "sin evidencia localizada".

Common errors:
- Treating repeated claims as independent evidence.
- Omitting contradictions.
- Inflating probative force.

Quality criteria:
- Each row is reviewable.
- The matrix distinguishes strong, partial, weak, and absent evidence.

OpenHarness fusion note:
- An OpenHarness prelude (`docs/OPENHARNESS_FUSION.md`) is not evidence; treat
  it as hypothesis to verify against local documents before populating any
  matrix row.

Prohibitions:
- Do not invent evidence.
- Do not use uncited memory as proof.
- Do not perform external actions.

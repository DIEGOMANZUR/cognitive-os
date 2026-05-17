---
name: legal-hold
description: Issue, refresh, release, or report on a litigation hold with a strict structured output and an explicit human-approval gate.
version: 1.0.0
risk_level: approval_required
allowed_tools:
  - search_local_docs
  - read_document_pages
  - write_workspace_file
  - get_relevant_memory
  - propose_memory_update
---

# Legal Hold

Use this skill when the operator asks to **issue**, **refresh**,
**release**, or **report on** a litigation hold (preservation
obligation). The skill never sends notices on its own — it produces a
structured artifact and a `HumanApproval` is required before any
external action.

> Attribution: this skill adapts the *legal-hold* concept and field
> structure from Anthropic's `claude-for-legal` repository
> (Apache 2.0). Prompts and integration are Cognitive OS native. See
> `../NOTICE.md`.

## When to use

- "Pon en hold a las comunicaciones del custodian X relacionadas con Y."
- "Refrescá el hold del matter Z."
- "Liberá el hold porque cerramos el caso."
- "Dame el reporte de holds activos."

## Steps

1. **Identify the action**: `issue`, `refresh`, `release`, or `report`.
2. **Gather the inputs** from the operator (or recent context):
   - matter id / matter name
   - custodians (names, roles, departments)
   - data sources in scope (mailboxes, drives, devices, SaaS apps)
   - subject-matter scope (keywords, date range, jurisdictions)
   - trigger event + date
   - obligation duration / next refresh date
3. **Cross-check** against existing holds in workspace memory (use
   `get_relevant_memory`) to avoid duplicate issuance.
4. **Produce the artifact** below; do not send anything yourself.
5. **Propose the memory update** so the hold register stays current.

## Required structured output

The skill MUST emit a JSON block with this exact shape, in addition to
any human-readable summary:

```json
{
  "action": "issue | refresh | release | report",
  "matter_id": "string",
  "custodians": [
    {"name": "string", "role": "string", "department": "string"}
  ],
  "data_sources": ["string"],
  "scope": {
    "keywords": ["string"],
    "date_range": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD | null"},
    "jurisdictions": ["string"]
  },
  "trigger": {"event": "string", "date": "YYYY-MM-DD"},
  "obligation": {"duration_days": "int | null", "next_refresh": "YYYY-MM-DD | null"},
  "notice_text": "string (template for the hold notice; do NOT send)",
  "open_questions": ["string"],
  "approval_required": true
}
```

## Hard rules

- Never assume custodians or scope. If a field is missing, list it in
  `open_questions` and ask the operator before producing the notice
  text.
- `notice_text` is a **draft** for human review. The skill never calls
  `send_email`, `publish_social_post`, or any external write tool — it
  is not in its `allowed_tools`.
- `release` requires an explicit confirmation prompt in
  `open_questions` ("Confirmar liberación del hold ID=...").
- `report` lists every active hold from memory with `next_refresh`
  flagged red if past due.
- Citations: any factual claim about the matter must include a
  document or memory reference using the `citation-discipline` rules.

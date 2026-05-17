---
name: matter-intake
description: Structured intake of a new legal matter — writes a normalized matter.md and a first chronology entry; requires operator approval before any external action.
version: 1.0.0
risk_level: approval_required
allowed_tools:
  - search_local_docs
  - read_document_pages
  - write_workspace_file
  - get_relevant_memory
  - propose_memory_update
---

# Matter Intake

Use this skill at the very start of a new legal matter (commercial,
employment, IP, litigation, regulatory, etc.). The skill takes the
operator's brief description and produces a normalized `matter.md`
plus a first chronology entry, in the workspace, behind an approval
gate.

> Attribution: adapts the *matter-intake* pattern from Anthropic's
> `claude-for-legal` (Apache 2.0). See `../NOTICE.md`.

## When to use

- "Abramos un matter nuevo para esto."
- "Cargá el caso X con estos datos."
- "Empezá la cronología desde aquí."

## Steps

1. **Collect** the operator's input. The minimum complete set:
   - matter type (commercial | employment | ip | litigation |
     regulatory | privacy | ai_governance | corporate | other)
   - short name + matter id (auto-derive a slug if absent)
   - parties (client side + counterparty side)
   - jurisdiction + venue
   - status (intake | active | stayed | closed)
   - assigned operator(s)
   - opened_at + statute_of_limitations (if any)
   - first event in the chronology
2. **Cross-check** with workspace memory: is there already a matter
   with this name / parties? If yes, do NOT create a duplicate —
   surface the existing one in `open_questions`.
3. **Generate the artifact** (a single `matter.md` body + first
   chronology row). Do not write it until the operator approves.
4. **Propose a memory update** so the matter shows up in the matter
   register.

## Required structured output

```json
{
  "matter": {
    "id": "kebab-slug",
    "short_name": "string",
    "type": "commercial | employment | ip | litigation | regulatory | privacy | ai_governance | corporate | other",
    "client_parties": ["string"],
    "counterparties": ["string"],
    "jurisdiction": "string",
    "venue": "string | null",
    "status": "intake | active | stayed | closed",
    "operators": ["string"],
    "opened_at": "YYYY-MM-DD",
    "statute_of_limitations": "YYYY-MM-DD | null"
  },
  "chronology_first_entry": {
    "date": "YYYY-MM-DD",
    "actor": "string",
    "event": "string",
    "source": "string"
  },
  "matter_md_preview": "string (the full matter.md body, ready for write_workspace_file)",
  "duplicate_check": {"found": "bool", "existing_id": "string | null"},
  "open_questions": ["string"],
  "approval_required": true
}
```

## Hard rules

- `approval_required: true` always. The skill never writes
  `matter.md` directly — it produces the preview and the operator
  approves via `HumanApproval`.
- If `duplicate_check.found == true`, the skill must STOP and ask
  whether to merge / amend / cancel.
- `id` must be a kebab-case slug; if the operator gave a long name,
  derive a short slug and surface it in `open_questions` for
  confirmation.
- Citations: every fact in the chronology entry must include a source
  reference (operator message id, document doc_id+page, or "operator
  verbal" if no document).
- Never invent jurisdiction. If absent, ask.

---
name: privilege-log-review
description: First-pass review of a privilege log — flag insufficient descriptions, missing recipients, weak privilege grounds, and stale dates.
version: 1.0.0
risk_level: read_only
allowed_tools:
  - search_local_docs
  - read_document_pages
  - graph_query_readonly
---

# Privilege Log Review

Use this skill when the operator hands over a privilege log (CSV/XLSX
parsed into the workspace, or rows pulled from the document store) and
asks for a first-pass review. Output is purely advisory — the final
log stays with the operator's privilege coordinator.

> Attribution: adapts the *privilege-log-review* pattern from
> Anthropic's `claude-for-legal` (Apache 2.0). See `../NOTICE.md`.

## When to use

- "Revisame este privilege log del matter X."
- "Mira si hay descripciones flojas o destinatarios sin rol."
- "Detecta entries donde el privilege ground es débil."

## Steps

1. Parse the log into rows: `entry_id`, `date`, `author`, `recipients`,
   `cc/bcc`, `subject`, `description`, `privilege_basis`, `attachments`.
2. For each row, run the **four-check rubric** below.
3. Emit one **issue per row affected**, with the exact reason and the
   suggested fix.

## Four-check rubric

For each entry:

1. **Adequate description?** Description must let a reviewer
   understand subject + reason for privilege without seeing the
   document. Flag entries where the description is generic
   ("communication regarding X") or shorter than 10 meaningful words.
2. **All recipients roleable?** Every name in `to/cc/bcc` must be
   resolvable to a role (counsel, in-house client, third-party agent,
   non-privileged). Flag entries with unresolved recipients.
3. **Privilege ground supported?** Match the asserted ground
   (attorney-client, work product, common interest, joint defense) to
   the recipient set. Flag combinations that *facially* break
   privilege (e.g. attorney-client with a non-client third party and
   no common interest ground stated).
4. **Date consistent?** Date must fall inside the matter window and be
   later than any "earliest preservable date" the operator gave.

## Required structured output

```json
{
  "summary": {
    "rows_reviewed": "int",
    "rows_flagged": "int",
    "by_reason": {
      "description_too_thin": "int",
      "unresolved_recipient": "int",
      "weak_privilege_ground": "int",
      "date_out_of_range": "int"
    }
  },
  "issues": [
    {
      "entry_id": "string",
      "reasons": ["description_too_thin", "weak_privilege_ground"],
      "explanation": "one-paragraph plain-language explanation",
      "suggested_fix": "string"
    }
  ],
  "open_questions": ["string"]
}
```

## Hard rules

- Read-only skill: no writes, no external sends. `risk_level=read_only`.
- Never invent recipients. If a recipient cannot be resolved, list it
  in `open_questions` instead of guessing a role.
- Cite every issue with the entry_id; the operator must be able to
  jump straight to the row.
- Privilege analysis is **jurisdiction-aware** when the operator names
  one; otherwise default to US federal common law and say so in
  `open_questions`.

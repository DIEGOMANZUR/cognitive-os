---
name: worker-classification
description: Classify a worker engagement as employee vs independent contractor under the named jurisdiction's test, with the factors that decided it.
version: 1.0.0
risk_level: read_only
allowed_tools:
  - search_local_docs
  - read_document_pages
  - search_web
---

# Worker Classification

Use this skill when the operator describes a working relationship and
asks whether it should be **employee** or **independent contractor**.
The skill applies the correct legal test for the named jurisdiction
and explains which factors decided the call.

This is decision-support, **not legal advice**. The skill says so.

> Attribution: adapts the *worker-classification* pattern from
> Anthropic's `claude-for-legal` (Apache 2.0). See `../NOTICE.md`.

## When to use

- "Es contractor o empleado bajo California (AB5)?"
- "Bajo regla federal IRS / DOL, ¿qué nos sale?"
- "Aplica el ABC test en este caso?"

## Steps

1. **Identify the jurisdiction** the operator named. If none was
   given, ask in `open_questions` — do NOT default silently.
2. **Pick the correct test** for that jurisdiction. Examples:
   - California → **ABC test** (Dynamex / Lab. Code §2775 et seq.)
   - US federal (DOL, post-2024) → **economic reality, six factors**
   - IRS → **common-law control, three categories**
   - UK → **employment status, multi-factor**
   - Generic / unspecified → list the candidate tests and ask.
3. **For each prong/factor**, gather what the operator told you and
   evaluate it; cite the source where possible.
4. **Produce a result** with explicit confidence and the factors that
   tipped it.

## Required structured output

```json
{
  "jurisdiction": "string",
  "test_applied": "ABC | economic_reality | common_law_control | UK_multi_factor | other",
  "classification": "employee | contractor | mixed | unclear",
  "confidence": "low | medium | high",
  "factor_table": [
    {
      "factor": "string",
      "operator_facts": "string",
      "evaluation": "leans_employee | leans_contractor | neutral | insufficient",
      "weight": "low | medium | high",
      "citation": "string | null"
    }
  ],
  "deciding_factors": ["string"],
  "open_questions": ["string"],
  "next_steps": ["string"]
}
```

## Hard rules

- **Always identify jurisdiction first.** Different states/countries
  have non-equivalent tests; mixing them is a malpractice trap.
- ABC test specifically: any single failed prong forces "employee" —
  state that explicitly.
- Confidence = `high` only when every factor was answered with
  operator-confirmed facts. Missing facts → `medium` or `low`.
- Never call the result "binding". Output ends with:
  *"Esta clasificación es asistencia técnica, no constituye opinión
  legal. Validar con counsel jurisdiccional antes de actuar."*
- Read-only. No edits, no sends, no policy changes.

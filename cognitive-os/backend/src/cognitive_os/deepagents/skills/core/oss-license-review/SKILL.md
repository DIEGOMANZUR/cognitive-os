---
name: oss-license-review
description: Open-source license compliance review for a dependency list — copyleft exposure, attribution gaps, license conflicts, and notice obligations.
version: 1.0.0
risk_level: read_only
allowed_tools:
  - search_local_docs
  - read_document_pages
  - search_web
---

# OSS License Review

Use this skill when the operator hands over a dependency manifest
(`requirements.txt`, `pyproject.toml`, `package.json`, `Cargo.toml`,
`go.mod`, etc.) or a list of (name, version, license) tuples and asks
"can we ship this?".

Output is **a license-risk report**, never legal advice. The skill is
read-only.

> Attribution: adapts the *oss-review* pattern from Anthropic's
> `claude-for-legal` (Apache 2.0). See `../NOTICE.md`.

## When to use

- "Revisame las licencias de este `requirements.txt`."
- "¿Hay incompatibilidad de licencias en este árbol de deps?"
- "Generame el `NOTICE` para los OSS que usamos."

## Steps

1. **Normalize** every dep to `(name, version, declared_license,
   resolved_license)`. If `declared` and `resolved` differ, flag it.
2. **Classify** each license into one of:
   permissive (MIT/BSD/Apache/ISC), weak copyleft (LGPL, MPL, EPL),
   strong copyleft (GPL, AGPL), source-available
   (BUSL/SSPL/Elastic/Confluent), commercial,
   public-domain/CC0/Unlicense, or unknown.
3. **Detect conflicts** against the operator's declared distribution
   model (proprietary SaaS / proprietary on-prem / OSS Apache /
   OSS GPL / internal-only).
4. **Surface attribution gaps**: licenses that require notice
   reproduction (Apache 2.0 §4 (d), MIT, BSD, ISC) but the project
   has no `NOTICE` / `THIRD_PARTY_LICENSES`.
5. **Surface viral exposure**: AGPL / SSPL / BUSL when shipping
   binaries or running them in a hosted service.

## Required structured output

```json
{
  "summary": {
    "deps_reviewed": "int",
    "deps_flagged": "int",
    "highest_severity": "info | warn | block"
  },
  "by_class": {
    "permissive": "int", "weak_copyleft": "int", "strong_copyleft": "int",
    "source_available": "int", "commercial": "int",
    "public_domain": "int", "unknown": "int"
  },
  "issues": [
    {
      "dep": "name@version",
      "license": "SPDX-id-or-string",
      "severity": "info | warn | block",
      "reason": "string",
      "remediation": "string"
    }
  ],
  "missing_notice_for": ["dep@version"],
  "open_questions": ["string"]
}
```

## Hard rules

- **Read-only.** Never edit the project. Never inject licenses you
  could not verify from the dep metadata or a public registry.
- If `declared_license` is missing, mark the dep `unknown` and put it
  in `open_questions`; do not guess.
- Severity ladder:
  - `block` = strong copyleft in a proprietary distribution, or SSPL
    in a hosted service.
  - `warn` = weak copyleft, missing attribution, declared/resolved
    mismatch.
  - `info` = permissive with attribution already satisfied.
- This is not legal advice. The skill output ends with:
  *"Esta revisión es asistencia técnica, no constituye opinión legal."*

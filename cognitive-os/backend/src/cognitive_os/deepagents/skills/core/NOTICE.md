# NOTICE — Cognitive OS DeepAgents core skills

This directory contains skills authored for the Cognitive OS project.

The following skills are **adaptations of patterns and structured output
schemas** from the `claude-for-legal` repository
(<https://github.com/anthropics/claude-for-legal>) by Anthropic, used
under the **Apache License, Version 2.0**:

- `legal-hold/`
- `privilege-log-review/`
- `oss-license-review/`
- `worker-classification/`
- `matter-intake/`

We do not redistribute the upstream files. We ported only the
*conceptual structure* (what each skill produces, what fields the output
carries, what the LLM is asked to verify) and rewrote prompts to fit
Cognitive OS conventions: `risk_level` + `allowed_tools` frontmatter,
read-only or approval-required execution, integration with the
`DeepAgentSkillsRegistry` and the `HumanApproval` pipeline. No
upstream code was copied verbatim.

Apache 2.0 attribution is preserved here per § 4 (d) of the License.

```
Copyright 2025 Anthropic, PBC
Licensed under the Apache License, Version 2.0 (the "License");
http://www.apache.org/licenses/LICENSE-2.0
```

The original repository's `LICENSE` file applies to those upstream
patterns; any modifications we made are released under the same Apache
2.0 license to keep downstream compatibility.

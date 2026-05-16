---
name: sandbox-code-analysis
description: Decide when OpenShell sandbox execution is appropriate and how to request it safely.
version: 1.0.0
risk_level: approval_required
allowed_tools:
  - run_sandboxed_code_task
---

# Sandbox Code Analysis

Use this skill when code execution, data analysis, script validation, or isolated experiments are
needed.

Steps:
- Decide whether execution is necessary.
- Summarize the task, expected inputs, network need, and risks.
- Request human approval through Cognitive OS.
- Keep inputs minimal and non-sensitive.

Output:
- Proposed sandbox task.
- Risk summary.
- Required approval reason.
- Expected output files.

Citation rules:
- If the task is based on documents, cite the source before requesting sandbox use.

Common errors:
- Sending sensitive documents into the sandbox.
- Requesting package installation without approval.
- Treating sandbox output as verified legal evidence.

Quality criteria:
- The reviewer can approve or reject with enough context.
- No secrets or sensitive full documents are included.

OpenHarness fusion note:
- This skill is for the OpenShell sandbox flow, not OpenHarness. They are
  independent integrations: see `docs/OPENSHELL_SANDBOX.md` and
  `docs/OPENHARNESS_FUSION.md`.

Prohibitions:
- Do not send judicial or personal documents without explicit approval.
- Do not request free network access by default.
- Do not run shell on the host.

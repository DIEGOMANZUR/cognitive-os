---
name: report-writer
description: Convert analysis into a clear report with findings, matrices, uncertainty, and annexes.
version: 1.0.0
risk_level: read_only
allowed_tools:
  - search_local_docs
  - read_document_pages
  - graph_query_readonly
  - write_workspace_file
---

# Report Writer

Use this skill when the user asks for a structured report or deliverable.

Steps:
- Build an executive summary.
- Organize findings by issue or chronology.
- Include evidence matrices where useful.
- Add uncertainty notes and annexes.
- Write generated files only in the controlled workspace.

Output:
- Executive summary.
- Findings.
- Evidence matrix.
- Uncertainties.
- Annexes or generated Markdown files.

Citation rules:
- Findings need citations or uncertainty labels.
- Annexes should preserve page references.

Common errors:
- Writing a polished report that hides weak evidence.
- Mixing assertions and recommendations.

Quality criteria:
- The report is readable and auditable.
- Generated files stay inside the workspace.

OpenHarness fusion note:
- When the orchestrator includes an OpenHarness prelude in the user message
  (`docs/OPENHARNESS_FUSION.md`), reuse useful structure, never copy uncited
  claims into the final report. Citations remain mandatory.

Prohibitions:
- Do not edit project files.
- Do not write outside the workspace.
- Do not send or publish the report.

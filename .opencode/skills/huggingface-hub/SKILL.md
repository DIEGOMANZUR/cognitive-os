---
name: huggingface-hub
description: Use when searching Hugging Face models, datasets, Spaces, papers, Hub docs, model cards, or MCP-enabled Hugging Face community tools.
---

# Hugging Face Hub

Use the `huggingface` MCP when a task needs Hugging Face Hub context or tools.

## Use For

- Finding models, datasets, Spaces, papers, and Hub resources.
- Comparing model cards, licenses, downloads, tags, and task support.
- Looking up Hugging Face documentation through the MCP server.
- Using MCP-compatible Hugging Face Spaces when enabled by the account.

## Rules

- Do not expose Hugging Face tokens or credentials in responses.
- Prefer read/search operations unless the user explicitly asks for an action
  that writes to the Hub.
- For model recommendations, mention license, size, task, and hardware fit when
  the MCP returns enough metadata.
- Cross-check critical deployment or licensing claims with official model cards
  or docs.

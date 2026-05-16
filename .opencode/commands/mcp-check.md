---
description: Check MCP configuration and security
agent: plan
---

Inspect MCP configuration for:
$ARGUMENTS

Check:

- secrets are not hardcoded in `opencode.json` or any `.opencode/**` file
- env vars use `{env:VAR}` syntax
- write tools are disabled by default (Neo4j, Weaviate, Postgres)
- OAuth MCPs are documented (e.g. `opencode mcp auth github`)
- risky MCPs are not enabled unnecessarily
- GitHub MCP scope is minimal
- `.gitignore` covers `.env`, `.env.*`, `opencode.local.json`,
  `.opencode/local/`, `*.bak-*`

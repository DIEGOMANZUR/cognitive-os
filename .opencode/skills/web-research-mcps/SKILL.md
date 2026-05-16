# Skill: web-research-mcps

Use this skill when a task needs live web search, repository discovery, GitHub
code/repo research, or cross-source grounding beyond the local repository.

## Tool Selection

- Use `tavily` for broad current web search and quick factual discovery.
- Use `brave-search` for independent web search coverage and SERP-style checks.
- Use `exa` for high-signal web search, code context, page fetches, company,
  people, academic, and financial-report research.
- Use `gh_grep` for GitHub code/repository search across public repositories.
- Use `deepwiki` for repo-level explanations, architecture summaries, and docs
  distilled from GitHub repositories.
- Use `github-official` for authenticated GitHub metadata and repository operations. It is
  configured read-only by default in this workspace.

## Rules

- Do not paste or expose API keys in prompts, logs, docs, or outputs.
- Prefer read-only repository and metadata operations unless the user explicitly
  asks for a write action and the tool policy allows it.
- For claims that affect implementation decisions, cross-check at least two
  sources when feasible.
- For GitHub repository research, start with `gh_grep` or `deepwiki`, then use
  `github` for authenticated details when needed.
- For product/API docs, prefer official docs first; use web MCPs to find the
  canonical docs when the URL is unknown.

## Output Expectations

- Cite source URLs when search tools return them.
- Separate facts, inference, and uncertainty.
- Keep retrieved context compact; summarize instead of dumping raw search output.

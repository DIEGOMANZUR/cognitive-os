---
name: opencode-operator
description: |
  Use when the user wants the agent to operate OpenCode/Claude Code as a real
  development cockpit across multiple PCs: choose LLMs, configure MCPs/skills,
  create projects, manage conversations, run repo workflows, or use the OS.
---

# OpenCode Operator

## Purpose

Operate OpenCode as Diego's development cockpit across Linux and Windows
machines. The agent may use OpenCode, Claude Code, MCPs, local shell, browser
bridges, repo workflows, and project planning files to build apps, pages,
agents, automations and OS-level tasks safely.

## Defaults

- Runtime LLM preference for Cognitive OS: `deepseek-v4-pro`.
- OpenAI-compatible endpoint: `https://api.deepseek.com`.
- Anthropic-compatible endpoint, if a client requires Anthropic wire format:
  `https://api.deepseek.com/anthropic`.
- Do not persist API keys in docs, memory or tracked files.
- Use Supermemory for cross-PC preferences and decisions.
- Use Memory Bank / planning files for workspace-local task state.

## When To Use

- User asks to create or modify apps/web pages/projects.
- User asks to choose or switch an LLM/model/provider in OpenCode.
- User asks to add, repair, authenticate or test MCPs.
- User asks to install or use skills/subagents.
- User asks to operate the filesystem, browser, terminal, or OS.
- User asks to continue work from another PC or another coding tool.

## Workflow

1. Inspect the active repo and `AGENTS.md` before code changes.
2. For multi-step work, update `task_plan.md`, `findings.md`, `progress.md`.
3. Choose the narrowest correct tool:
   - codebase search: `glob`/`grep`;
   - browser with real login: `kimi-webbridge` first, then Playwright/Chrome;
   - GitHub: GitHub MCP or `gh`;
   - durable user context: Supermemory;
   - local continuity: Memory Bank.
4. Keep external actions approval-first unless the user explicitly enabled safe
   automation for that domain.
5. Run the smallest relevant validation before declaring done.

## OpenCode Tasks

### Switch Or Choose Models

- Prefer project/runtime config files over ad-hoc UI changes when the change
  must persist.
- For Cognitive OS backend, update `cognitive-os/.env` LLM variables.
- For OpenCode itself, inspect `opencode.json`, `~/.config/opencode/opencode.json`,
  and any wrapper scripts before changing providers.

### Create Projects

- Create or select a repo folder.
- Add minimal README and `.gitignore` before generated assets.
- Add framework scaffolding only after confirming target stack or inferring from
  the user's stated goal.

### Manage Conversations

- Keep architectural decisions in Supermemory when they should survive machines.
- Keep task execution details in planning files, not in global memory.
- Summarize blockers and next commands at the end of a session.

### MCPs And Skills

- Use `opencode mcp list` to check connection state.
- Use `opencode mcp auth <name>` for OAuth-enabled remotes.
- For local MCPs, prefer wrapper scripts that hardcode safe local fallbacks only
  when env injection is unreliable and files are gitignored.
- Add skills under `.opencode/skills/<name>/SKILL.md` for repo-specific behavior.

## Safety

- Never commit secrets.
- Never send email, alter DNS, post externally, delete files, or run destructive
  system operations without explicit approval.
- For multi-PC work, assume paths differ; verify current machine before acting.

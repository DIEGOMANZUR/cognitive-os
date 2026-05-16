---
name: dual-memory-recall
description: Use when the user asks to use memory, recall context, remember prior work, continue from memory, or when durable context is needed; consult both Supermemory and Memory Bank.
---

# Dual Memory Recall

Use this skill whenever the user asks to "use memory", "recall", "remember",
"continue from last time", "what did we do", or when the task depends on
durable context beyond the current chat.

## Memory Sources

- Supermemory MCP: cross-session user/project memory for preferences,
  architecture decisions, error solutions, learned patterns, and durable
  project facts.
- Memory Bank MCP: workspace-local continuity notes under `memory-bank/`, using
  project namespace `cognitive-os` by default.
- Planning files: active implementation state in `cognitive-os/task_plan.md`,
  `cognitive-os/findings.md`, and `cognitive-os/progress.md`.

## Recall Workflow

1. Search Supermemory for the topic or task intent.
2. Read relevant Memory Bank files for project `cognitive-os`, starting with
   `activeContext.md`, then `projectbrief.md`, `systemPatterns.md`,
   `techContext.md`, or `progress.md` if present.
3. If the task is active implementation work, also inspect the planning files.
4. Merge the context, deduplicate repeated facts, and state only the relevant
   memory briefly before acting.
5. If memory sources disagree, prefer the newest explicit user instruction and
   mention the conflict only if it affects the action.

## Write Workflow

- Save to Supermemory when the information should follow the user or project
  across sessions and workspaces: preferences, decisions, recurring fixes,
  learned patterns.
- Save to Memory Bank when the information is workspace-local continuity:
  current handoff notes, project summaries, architecture reminders, and tool
  setup status.
- Save to planning files when it is active task execution state.
- Do not write to memory for transient logs, obvious facts, or low-signal
  details.

## Safety

- Never store API keys, tokens, passwords, private credentials, `.env` values,
  or secret-bearing URLs.
- Never copy full private files into Supermemory or Memory Bank. Summarize the
  durable lesson instead.
- Keep Memory Bank entries concise and markdown-formatted.
- Use project name `cognitive-os` unless the user explicitly asks otherwise.

## Expected Behavior

- If the user explicitly asks for memory, use both Supermemory and Memory Bank
  before answering.
- If the assistant estimates memory is needed, use both sources unless the task
  is trivial or purely local to the current visible context.
- If a useful durable preference or decision emerges, persist it to the right
  memory store without exposing secrets.

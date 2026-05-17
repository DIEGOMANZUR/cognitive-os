"""Cognitive OS Code Director — orchestrates external coding agents.

The director is a meta-agent: it receives a high-level objective in natural
language (e.g. "build me an app with two RAGs, a Next.js frontend and
JWT-protected backend"), decomposes it into subtasks, and **delegates** each
subtask to an external coding agent (Claude Code CLI, Codex CLI, Kimi CLI,
or in-process DeepAgents) — never writing code in its own process.

Architectural contract:
- The director never touches the user's repo. All work happens inside an
  isolated workspace under `storage/workspaces/<thread>/<task>/`.
- Every coding-agent invocation goes through a `CodingAgentAdapter` Protocol
  so the director stays agnostic of which CLI is doing the work.
- The build is always preceded by a `HumanApproval` on the plan (so the
  operator sees which agent + model will be used and the budget estimate
  before any tokens are spent) and followed by a `HumanApproval` on the
  delivery artifact.
- Budget tracking (max runtime, max calls, optional USD cap) is enforced by
  the director loop. Exceeding any cap stops the build with status=`partial`
  pending operator decision.

This package is read-only from the rest of the codebase: callers consume the
public API via `service.CodeDirectorService` and the Pydantic schemas in
`schemas.py`. Implementation modules (`director.py`, `adapters/*.py`) are
internal.
"""

from cognitive_os.code_director.schemas import (
    AdapterChoice,
    AgentSession,
    BuildEvent,
    BuildEventKind,
    BuildPlan,
    CodeBuildRequest,
    CodeBuildResult,
    CodeBuildStatus,
    StepResult,
    SubtaskSpec,
    SubtaskStatus,
)

__all__ = [
    "AdapterChoice",
    "AgentSession",
    "BuildEvent",
    "BuildEventKind",
    "BuildPlan",
    "CodeBuildRequest",
    "CodeBuildResult",
    "CodeBuildStatus",
    "StepResult",
    "SubtaskSpec",
    "SubtaskStatus",
]

"""Contract that every coding-agent adapter implements.

Adapters wrap the heterogeneous interfaces of external coding agents (CLI,
HTTP, in-process Python) behind a uniform Protocol so the director loop
stays agnostic. Each adapter is responsible for:

- Translating a director prompt into the agent's native invocation
  (subprocess args, HTTP body, Python call).
- Capturing the agent's output (stdout, files written) and reporting back
  as a `StepResult`.
- Failing fast: any timeout, missing binary or non-zero exit becomes a
  `StepResult(success=False, error=...)` — adapters never raise.

The director composes adapters via `default_registry()`, which returns the
mapping `AdapterChoice → CodingAgentAdapter`. Tests inject a `{"fake":
FakeAdapter()}` registry instead.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from cognitive_os.code_director.schemas import (
    AdapterChoice,
    AgentSession,
    StepResult,
)


class CodingAgentAdapter(Protocol):
    """Uniform interface the director uses to talk to any coding agent."""

    name: AdapterChoice

    def is_available(self) -> bool:
        """Return True iff the underlying binary / library / HTTP server is reachable.

        Called during preflight. An unavailable adapter should not raise —
        the director downgrades to a fallback adapter and emits a
        `budget_warning` event.
        """
        ...

    def start_session(
        self,
        *,
        workspace: Path,
        objective: str,
        model: str | None = None,
    ) -> AgentSession:
        """Create a session targeting `workspace`. Session is stateless for one-shot adapters."""
        ...

    def send_prompt(
        self,
        session: AgentSession,
        prompt: str,
        *,
        timeout_seconds: float = 600.0,
    ) -> StepResult:
        """Send `prompt` to the agent. Must NEVER raise — wrap errors into StepResult."""
        ...

    def cleanup(self, session: AgentSession) -> None:
        """Release any resources the adapter holds for this session."""
        ...


AdapterRegistry = dict[AdapterChoice, CodingAgentAdapter]
AdapterFactory = Callable[[], CodingAgentAdapter]

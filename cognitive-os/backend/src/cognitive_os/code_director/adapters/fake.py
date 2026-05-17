"""Deterministic in-memory adapter used by tests.

`FakeAdapter` lets the director loop be exercised end-to-end without
spawning subprocesses or calling external LLM APIs. Tests can program the
adapter's behaviour by setting `responses` (one StepResult per prompt) or
by passing a callable that builds responses on-the-fly.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from cognitive_os.code_director.adapters.base import CodingAgentAdapter
from cognitive_os.code_director.schemas import AgentSession, StepResult


class FakeAdapter(CodingAgentAdapter):
    """Test-only adapter. Never selectable from the API layer."""

    name = "fake"

    def __init__(
        self,
        *,
        responder: Callable[[AgentSession, str], StepResult] | None = None,
        available: bool = True,
    ) -> None:
        self._responder = responder or self._default_responder
        self._available = available
        self.invocations: list[tuple[str, str]] = []  # (session_id, prompt) for assertions
        self._sessions: dict[str, AgentSession] = {}

    def is_available(self) -> bool:
        return self._available

    def start_session(
        self,
        *,
        workspace: Path,
        objective: str,
        model: str | None = None,
    ) -> AgentSession:
        del objective
        session = AgentSession(
            session_id=str(uuid4()),
            adapter="fake",
            workspace=str(workspace),
            model=model,
            state={"calls": 0},
        )
        self._sessions[session.session_id] = session
        return session

    def send_prompt(
        self,
        session: AgentSession,
        prompt: str,
        *,
        timeout_seconds: float = 600.0,
    ) -> StepResult:
        del timeout_seconds
        self.invocations.append((session.session_id, prompt))
        state: dict[str, Any] = session.state
        state["calls"] = int(state.get("calls", 0)) + 1
        return self._responder(session, prompt)

    def cleanup(self, session: AgentSession) -> None:
        self._sessions.pop(session.session_id, None)

    @staticmethod
    def _default_responder(session: AgentSession, prompt: str) -> StepResult:
        del session
        return StepResult(
            success=True,
            stdout=f"fake-ok: handled prompt of {len(prompt)} chars",
            duration_ms=1,
            estimated_input_tokens=max(1, len(prompt) // 4),
            estimated_output_tokens=8,
            estimated_cost_usd=0.0,
        )

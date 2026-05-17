"""In-process adapter delegating to the existing DeepAgents runtime.

This is the safest adapter: no subprocess, no external CLI, runs inside the
same Python process under the same tool policy and budget the rest of
Cognitive OS already enforces. It lets the director be exercised
end-to-end with a real agent before any external CLI is wired (F3).

The DeepAgents `research` task type writes to an isolated workspace and
returns a `DeepAgentResult`. We map that result onto the director's
`StepResult` contract. The runner is injectable so unit tests can supply a
fake without importing the heavy DeepAgents stack.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import structlog

from cognitive_os.code_director.adapters.base import CodingAgentAdapter
from cognitive_os.code_director.schemas import AgentSession, StepResult

_log = structlog.get_logger(__name__)

# (task_dict) -> result-like object with .status / .answer / .generated_files
DeepAgentRunner = Callable[[dict[str, object]], object]


class DeepAgentAdapter(CodingAgentAdapter):
    """Drives the in-process DeepAgents `research` agent as a coding worker."""

    name = "deepagent"

    def __init__(
        self,
        *,
        runner: DeepAgentRunner | None = None,
        web_allowed: bool = False,
        budget_usd_limit: float = 3.0,
        max_iterations: int = 12,
    ) -> None:
        self._runner = runner
        self._web_allowed = web_allowed
        self._budget_usd_limit = budget_usd_limit
        self._max_iterations = max_iterations

    # ---- availability ----------------------------------------------------

    def is_available(self) -> bool:
        """DeepAgents is a first-party dependency; available unless import fails."""
        if self._runner is not None:
            return True
        try:
            import cognitive_os.deepagents.service  # noqa: F401, PLC0415

            return True
        except Exception:  # noqa: BLE001 - missing optional stack
            return False

    def _resolve_runner(self) -> DeepAgentRunner:
        if self._runner is not None:
            return self._runner
        from cognitive_os.deepagents.service import (  # noqa: PLC0415
            run_deepagent_task_from_dict,
        )

        return run_deepagent_task_from_dict

    # ---- session ---------------------------------------------------------

    def start_session(
        self,
        *,
        workspace: Path,
        objective: str,
        model: str | None = None,
    ) -> AgentSession:
        workspace.mkdir(parents=True, exist_ok=True)
        thread_id = f"cd-deepagent-{uuid4().hex[:12]}"
        return AgentSession(
            session_id=str(uuid4()),
            adapter="deepagent",
            workspace=str(workspace),
            model=model,
            state={"thread_id": thread_id, "objective": objective},
        )

    # ---- prompt ----------------------------------------------------------

    def send_prompt(
        self,
        session: AgentSession,
        prompt: str,
        *,
        timeout_seconds: float = 600.0,
    ) -> StepResult:
        del timeout_seconds  # DeepAgents enforces its own iteration/budget caps
        started = time.monotonic()
        thread_id = str(session.state.get("thread_id", session.session_id))
        task_dict: dict[str, object] = {
            "task_id": f"cd-{uuid4().hex[:12]}",
            "thread_id": thread_id,
            "task_type": "research",
            "query": prompt,
            "web_allowed": self._web_allowed,
            "max_iterations": self._max_iterations,
            "budget_usd_limit": self._budget_usd_limit,
            "require_citations": False,
            "metadata": {
                "code_director": True,
                "workspace": session.workspace,
            },
        }
        try:
            result = self._resolve_runner()(task_dict)
        except Exception as exc:  # noqa: BLE001 - adapters never raise
            _log.warning(
                "deepagent_adapter_failed",
                error_type=type(exc).__name__,
                session=session.session_id,
            )
            return StepResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        status = str(getattr(result, "status", "failed"))
        answer = str(getattr(result, "answer", ""))
        generated = list(getattr(result, "generated_files", []) or [])
        success = status in {"ok", "needs_more_info"}
        return StepResult(
            success=success,
            stdout=answer,
            exit_code=0 if success else 1,
            duration_ms=int((time.monotonic() - started) * 1000),
            files_touched=generated,
            error=None if success else f"DeepAgent status={status}",
        )

    def cleanup(self, session: AgentSession) -> None:
        # DeepAgents owns its workspace lifecycle; nothing to release here.
        del session

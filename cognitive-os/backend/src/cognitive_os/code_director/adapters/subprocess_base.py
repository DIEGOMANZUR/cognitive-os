"""Shared machinery for CLI-backed coding adapters.

Claude Code, Codex and Kimi are all headless-capable CLIs invoked as a
one-shot subprocess: the director hands them a prompt and a workspace, the
CLI edits files in place, and the adapter reports back. They differ only in
argv shape, so the common concerns (binary discovery, timeout, output
capture, never-raise) live here and the concrete adapters supply
`build_argv`.

Security posture:
- The workspace is the only writable surface we hand the CLI; we pass it as
  the process cwd AND via the CLI's own workspace flag where supported.
- We never pass the prompt on argv (it can be huge and would leak into
  `ps`); it always goes through stdin.
- A hard wall-clock timeout kills the process group so a hung CLI cannot
  stall a Celery worker forever.
- The adapter never raises: missing binary, timeout, non-zero exit all
  become `StepResult(success=False, ...)`.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import structlog

from cognitive_os.code_director.adapters.base import CodingAgentAdapter
from cognitive_os.code_director.schemas import AdapterChoice, AgentSession, StepResult

_log = structlog.get_logger(__name__)


class SubprocessCodingAdapter(CodingAgentAdapter):
    """Base class for one-shot CLI coding agents.

    Subclasses set `name`, `binary` and implement `build_argv`.
    """

    name: AdapterChoice
    binary: str

    def __init__(self, *, binary_override: str | None = None) -> None:
        self._binary = binary_override or self.binary

    # ---- availability ----------------------------------------------------

    def is_available(self) -> bool:
        return shutil.which(self._binary) is not None

    def resolved_binary(self) -> str | None:
        return shutil.which(self._binary)

    # ---- session ---------------------------------------------------------

    def start_session(
        self,
        *,
        workspace: Path,
        objective: str,
        model: str | None = None,
    ) -> AgentSession:
        workspace.mkdir(parents=True, exist_ok=True)
        return AgentSession(
            session_id=str(uuid4()),
            adapter=self.name,
            workspace=str(workspace),
            model=model,
            state={"objective": objective},
        )

    # ---- prompt ----------------------------------------------------------

    def build_argv(
        self,
        *,
        workspace: Path,
        model: str | None,
    ) -> list[str]:
        """Return the argv (excluding the binary). Subclasses implement this.

        The prompt is delivered on stdin, never on argv.
        """
        raise NotImplementedError

    def send_prompt(
        self,
        session: AgentSession,
        prompt: str,
        *,
        timeout_seconds: float = 600.0,
    ) -> StepResult:
        binary = self.resolved_binary()
        if binary is None:
            return StepResult(
                success=False,
                error=f"binary not found on PATH: {self._binary}",
            )
        workspace = Path(session.workspace)
        argv = [binary, *self.build_argv(workspace=workspace, model=session.model)]
        started = time.monotonic()
        # New process group so we can kill the whole tree on timeout.
        try:
            proc = subprocess.Popen(  # noqa: S603 - argv is constructed, not shell
                argv,
                cwd=str(workspace),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                env=self._child_env(),
            )
        except (OSError, ValueError) as exc:
            return StepResult(
                success=False,
                error=f"failed to spawn {self._binary}: {type(exc).__name__}: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        try:
            stdout, stderr = proc.communicate(input=prompt, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            self._kill_process_group(proc)
            stdout, stderr = proc.communicate()
            return StepResult(
                success=False,
                stdout=stdout or "",
                stderr=stderr or "",
                exit_code=proc.returncode,
                duration_ms=int((time.monotonic() - started) * 1000),
                error=f"{self._binary} timed out after {timeout_seconds:.0f}s",
            )
        except Exception as exc:  # noqa: BLE001 - adapters never raise
            self._kill_process_group(proc)
            return StepResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        duration_ms = int((time.monotonic() - started) * 1000)
        success = proc.returncode == 0
        return StepResult(
            success=success,
            stdout=stdout or "",
            stderr=stderr or "",
            exit_code=proc.returncode,
            duration_ms=duration_ms,
            error=None if success else f"{self._binary} exited {proc.returncode}",
        )

    def cleanup(self, session: AgentSession) -> None:
        del session

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _kill_process_group(proc: subprocess.Popen[str]) -> None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    @staticmethod
    def _child_env() -> dict[str, str]:
        """Inherit the parent env. Each CLI authenticates with its own
        credentials (CLAUDE_* / CODEX_HOME / kimi config); the director
        does not inject keys."""
        return dict(os.environ)

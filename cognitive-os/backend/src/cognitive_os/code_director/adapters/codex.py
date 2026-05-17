"""Codex CLI adapter.

Invocation (headless one-shot):

    codex exec --cd <workspace> --skip-git-repo-check
               --sandbox workspace-write [-m <model>] -

The trailing `-` makes Codex read the prompt from stdin. `exec` is the
non-interactive subcommand. `--sandbox workspace-write` confines
model-generated shell commands to the workspace (Codex's own sandbox);
`--skip-git-repo-check` allows running in a fresh build workspace that is
not a git repo.
"""

from __future__ import annotations

from pathlib import Path

from cognitive_os.code_director.adapters.subprocess_base import SubprocessCodingAdapter


class CodexAdapter(SubprocessCodingAdapter):
    name = "codex"
    binary = "codex"

    def __init__(
        self,
        *,
        binary_override: str | None = None,
        sandbox_mode: str = "workspace-write",
    ) -> None:
        super().__init__(binary_override=binary_override)
        # read-only | workspace-write | danger-full-access. We default to
        # workspace-write: the director's whole point is for the agent to
        # write code into the isolated workspace.
        self._sandbox_mode = sandbox_mode

    def build_argv(self, *, workspace: Path, model: str | None) -> list[str]:
        argv: list[str] = [
            "exec",
            "--cd",
            str(workspace),
            "--skip-git-repo-check",
            "--sandbox",
            self._sandbox_mode,
        ]
        if model:
            argv += ["-m", model]
        argv.append("-")  # read prompt from stdin
        return argv

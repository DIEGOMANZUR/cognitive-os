"""Claude Code CLI adapter.

Invocation (headless one-shot):

    claude -p --add-dir <workspace> [--model <model>] [--max-budget-usd N]

The prompt is piped on stdin. `-p/--print` runs non-interactive and skips
the workspace-trust dialog (we only ever point it at the isolated build
workspace). `--add-dir` widens the writable scope to the workspace; cwd is
already the workspace so this is belt-and-suspenders.
"""

from __future__ import annotations

from pathlib import Path

from cognitive_os.code_director.adapters.subprocess_base import SubprocessCodingAdapter


class ClaudeCodeAdapter(SubprocessCodingAdapter):
    name = "claude_code"
    binary = "claude"

    def __init__(
        self,
        *,
        binary_override: str | None = None,
        max_budget_usd: float | None = None,
    ) -> None:
        super().__init__(binary_override=binary_override)
        self._max_budget_usd = max_budget_usd

    def build_argv(self, *, workspace: Path, model: str | None) -> list[str]:
        argv: list[str] = ["-p", "--add-dir", str(workspace)]
        if model:
            argv += ["--model", model]
        if self._max_budget_usd is not None:
            argv += ["--max-budget-usd", str(self._max_budget_usd)]
        return argv

"""Kimi CLI adapter (official Moonshot AI CLI).

Invocation (headless one-shot, print mode):

    kimi --print --work-dir <workspace> --prompt -

`--print` runs non-interactive (no TUI), auto-approving tools inside the
trusted workspace. `--work-dir` scopes the agent to the build workspace.
The prompt is piped on stdin (`--prompt -`). Kimi reads its model/provider
from its own config file (`~/.kimi/...`); there is no per-invocation
`--model` flag, so `model` is informational only — the director records it
in the plan for transparency but Kimi uses its configured provider.
"""

from __future__ import annotations

from pathlib import Path

from cognitive_os.code_director.adapters.subprocess_base import SubprocessCodingAdapter


class KimiAdapter(SubprocessCodingAdapter):
    name = "kimi"
    binary = "kimi"

    def build_argv(self, *, workspace: Path, model: str | None) -> list[str]:
        # Kimi has no per-call model flag (provider/model come from its
        # config). `model` stays informational; we deliberately do not try
        # to inject it to avoid silently ignoring the operator's intent.
        del model
        return [
            "--print",
            "--work-dir",
            str(workspace),
            "--prompt",
            "-",
        ]

from __future__ import annotations

from pathlib import Path

import pytest

from cognitive_os.deepagents.policies import (
    DeepAgentPolicyViolation,
    validate_tool_allowed,
    validate_workspace_path,
)
from cognitive_os.deepagents.schemas import DeepAgentToolPolicy, DeepAgentWorkspace


def test_tool_not_allowed_is_blocked() -> None:
    with pytest.raises(DeepAgentPolicyViolation):
        validate_tool_allowed("unknown_tool", DeepAgentToolPolicy())


def test_shell_and_execute_are_blocked() -> None:
    policy = DeepAgentToolPolicy(allow_shell=True)
    for tool_name in ("shell", "execute", "bash", "python_exec"):
        with pytest.raises(DeepAgentPolicyViolation):
            validate_tool_allowed(tool_name, policy)


def test_write_workspace_file_blocks_path_traversal(tmp_path: Path) -> None:
    workspace = DeepAgentWorkspace(root_dir=tmp_path, thread_id="t", task_id="task")

    with pytest.raises(DeepAgentPolicyViolation):
        validate_workspace_path(Path("../escape.md"), workspace)


def test_write_workspace_file_allows_valid_relative_path(tmp_path: Path) -> None:
    workspace = DeepAgentWorkspace(root_dir=tmp_path, thread_id="t", task_id="task")

    assert (
        validate_workspace_path(Path("reports/result.md"), workspace)
        == (tmp_path / "reports/result.md").resolve()
    )

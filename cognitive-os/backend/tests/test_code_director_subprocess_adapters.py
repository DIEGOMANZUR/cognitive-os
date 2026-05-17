"""F3 regression: subprocess coding adapters (Claude Code / Codex / Kimi).

These tests must NOT spend real tokens. We verify:
- argv shape per adapter (the contract with each CLI),
- the never-raise guarantee (missing binary, timeout, non-zero exit),
- prompt is delivered on stdin (never argv),
all by pointing the adapter at a fake binary instead of the real CLI.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from cognitive_os.code_director.adapters.claude_code import ClaudeCodeAdapter
from cognitive_os.code_director.adapters.codex import CodexAdapter
from cognitive_os.code_director.adapters.kimi import KimiAdapter
from cognitive_os.code_director.director import default_registry


def _make_fake_binary(path: Path, *, body: str) -> str:
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


# ---------------------------------------------------------------------------
# argv shape
# ---------------------------------------------------------------------------


def test_claude_argv_uses_print_and_add_dir_and_model(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter()
    argv = adapter.build_argv(workspace=tmp_path, model="claude-opus-4-7")
    assert argv[0] == "-p"
    assert "--add-dir" in argv
    assert str(tmp_path) in argv
    assert "--model" in argv
    assert "claude-opus-4-7" in argv


def test_claude_argv_includes_budget_when_set(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter(max_budget_usd=12.5)
    argv = adapter.build_argv(workspace=tmp_path, model=None)
    assert "--max-budget-usd" in argv
    assert "12.5" in argv
    assert "--model" not in argv  # no model => no flag


def test_codex_argv_uses_exec_cd_sandbox_and_stdin_dash(tmp_path: Path) -> None:
    adapter = CodexAdapter()
    argv = adapter.build_argv(workspace=tmp_path, model="gpt-5-codex")
    assert argv[0] == "exec"
    assert "--cd" in argv
    assert str(tmp_path) in argv
    assert "--sandbox" in argv
    assert "workspace-write" in argv
    assert "--skip-git-repo-check" in argv
    assert argv[-1] == "-"  # prompt on stdin
    assert "-m" in argv and "gpt-5-codex" in argv


def test_kimi_argv_uses_print_workdir_and_stdin(tmp_path: Path) -> None:
    adapter = KimiAdapter()
    argv = adapter.build_argv(workspace=tmp_path, model="ignored")
    assert "--print" in argv
    assert "--work-dir" in argv
    assert str(tmp_path) in argv
    assert argv[-2:] == ["--prompt", "-"]


# ---------------------------------------------------------------------------
# never-raise guarantees
# ---------------------------------------------------------------------------


def test_missing_binary_returns_failure_not_raise(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter(binary_override="definitely-not-a-real-binary-xyz")
    assert adapter.is_available() is False
    session = adapter.start_session(workspace=tmp_path, objective="x", model=None)
    result = adapter.send_prompt(session, "do it")
    assert result.success is False
    assert "binary not found" in (result.error or "")


def test_non_zero_exit_maps_to_failure(tmp_path: Path) -> None:
    fake = _make_fake_binary(tmp_path / "fakecli", body="cat >/dev/null; exit 3\n")
    adapter = ClaudeCodeAdapter(binary_override=fake)
    session = adapter.start_session(workspace=tmp_path, objective="x", model=None)
    result = adapter.send_prompt(session, "the prompt")
    assert result.success is False
    assert result.exit_code == 3
    assert "exited 3" in (result.error or "")


def test_success_exit_zero_maps_to_success_and_captures_stdout(tmp_path: Path) -> None:
    # Fake CLI echoes the stdin prompt to stdout and exits 0.
    fake = _make_fake_binary(tmp_path / "fakecli", body="cat\n")
    adapter = CodexAdapter(binary_override=fake)
    session = adapter.start_session(workspace=tmp_path, objective="x", model=None)
    result = adapter.send_prompt(session, "PROMPT-MARKER-123")
    assert result.success is True
    assert result.exit_code == 0
    assert "PROMPT-MARKER-123" in result.stdout


def test_prompt_is_delivered_on_stdin_not_argv(tmp_path: Path) -> None:
    # The fake writes its argv to a file; the prompt must NOT appear there.
    argv_dump = tmp_path / "argv.txt"
    fake = _make_fake_binary(
        tmp_path / "fakecli",
        body=f'echo "$@" > "{argv_dump}"; cat >/dev/null; exit 0\n',
    )
    adapter = KimiAdapter(binary_override=fake)
    session = adapter.start_session(workspace=tmp_path, objective="x", model=None)
    secret_prompt = "DO-NOT-LEAK-TO-PS-MARKER"  # pragma: allowlist secret
    result = adapter.send_prompt(session, secret_prompt)
    assert result.success is True
    recorded_argv = argv_dump.read_text(encoding="utf-8")
    assert secret_prompt not in recorded_argv


def test_timeout_kills_process_and_reports_failure(tmp_path: Path) -> None:
    fake = _make_fake_binary(tmp_path / "fakecli", body="sleep 10\n")
    adapter = ClaudeCodeAdapter(binary_override=fake)
    session = adapter.start_session(workspace=tmp_path, objective="x", model=None)
    result = adapter.send_prompt(session, "do it", timeout_seconds=0.5)
    assert result.success is False
    assert "timed out" in (result.error or "")


def test_default_registry_lists_all_four_adapters() -> None:
    registry = default_registry()
    assert set(registry) == {"deepagent", "claude_code", "codex", "kimi"}
    for name, adapter in registry.items():
        assert adapter.name == name


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="availability depends on host CLI installs; informational only",
)
def test_host_cli_availability_is_reported_without_crash() -> None:
    """is_available() must never raise regardless of whether the CLI exists."""
    for adapter in default_registry().values():
        # Just exercising the call; value depends on the host.
        assert isinstance(adapter.is_available(), bool)

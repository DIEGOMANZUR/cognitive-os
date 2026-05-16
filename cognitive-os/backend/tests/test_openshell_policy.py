from __future__ import annotations

from pathlib import Path

import pytest

from cognitive_os.core.config import Settings
from cognitive_os.deepagents.openshell_policy import (
    OpenShellPolicyViolation,
    redact_openshell_payload,
    sanitize_input_file_paths,
    validate_openshell_task,
)
from cognitive_os.deepagents.openshell_schemas import OpenShellTask


def _task(**overrides: object) -> OpenShellTask:
    payload: dict[str, object] = {
        "task_id": "task-1",
        "thread_id": "thread-1",
        "user_id": "user-1",
        "purpose": "code_test",
        "instruction": "run a tiny isolated check",
    }
    payload.update(overrides)
    return OpenShellTask.model_validate(payload)


def test_sandbox_disabled_blocks_task() -> None:
    app_settings = Settings(enable_openshell_sandbox=False)

    with pytest.raises(OpenShellPolicyViolation, match="disabled"):
        validate_openshell_task(_task(), app_settings)


def test_path_traversal_is_blocked(tmp_path: Path) -> None:
    allowed = tmp_path / "input"
    allowed.mkdir()

    with pytest.raises(OpenShellPolicyViolation, match="traversal"):
        sanitize_input_file_paths(["../secret.txt"], allowed)


def test_env_file_is_blocked(tmp_path: Path) -> None:
    allowed = tmp_path / "input"
    allowed.mkdir()
    env_file = allowed / ".env"
    env_file.write_text("SHOULD_NOT_PASS=1", encoding="utf-8")

    with pytest.raises(OpenShellPolicyViolation, match="Sensitive file type"):
        sanitize_input_file_paths([str(env_file)], allowed)


def test_missing_input_file_is_blocked(tmp_path: Path) -> None:
    allowed = tmp_path / "input"
    allowed.mkdir()

    with pytest.raises(OpenShellPolicyViolation, match="does not exist"):
        sanitize_input_file_paths(["missing.txt"], allowed)


def test_symlink_input_file_is_blocked(tmp_path: Path) -> None:
    allowed = tmp_path / "input"
    allowed.mkdir()
    target = allowed / "target.txt"
    target.write_text("safe", encoding="utf-8")
    link = allowed / "link.txt"
    link.symlink_to(target)

    with pytest.raises(OpenShellPolicyViolation, match="Symlink"):
        sanitize_input_file_paths(["link.txt"], allowed)


def test_redact_openshell_payload_redacts_secret_shaped_strings() -> None:
    redacted = redact_openshell_payload(
        {
            "instruction": "curl -H 'Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456'",
            "metadata": {"token": "secret-value"},
        }
    )

    rendered = str(redacted)
    assert "abcdefghijklmnopqrstuvwxyz123456" not in rendered  # pragma: allowlist secret
    assert "secret-value" not in rendered  # pragma: allowlist secret
    assert "[REDACTED]" in rendered


def test_network_is_blocked_by_default(tmp_path: Path) -> None:
    app_settings = Settings(
        enable_openshell_sandbox=True,
        openshell_allow_network=False,
        openshell_allowed_input_dir=tmp_path / "input",
    )

    with pytest.raises(OpenShellPolicyViolation, match="network"):
        validate_openshell_task(_task(allow_network=True), app_settings)


def test_max_runtime_exceeded_is_blocked(tmp_path: Path) -> None:
    app_settings = Settings(
        enable_openshell_sandbox=True,
        openshell_max_runtime_seconds=10,
        openshell_allowed_input_dir=tmp_path / "input",
    )

    with pytest.raises(OpenShellPolicyViolation, match="runtime"):
        validate_openshell_task(_task(max_runtime_seconds=11), app_settings)

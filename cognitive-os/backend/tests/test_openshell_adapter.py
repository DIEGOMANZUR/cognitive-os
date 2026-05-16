from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

import cognitive_os.deepagents.openshell_adapter as adapter_module
from cognitive_os.core.config import Settings
from cognitive_os.deepagents.openshell_adapter import OpenShellAdapter
from cognitive_os.deepagents.openshell_schemas import OpenShellTask


def _task(**overrides: object) -> OpenShellTask:
    payload: dict[str, object] = {
        "task_id": "task-1",
        "thread_id": "thread-1",
        "user_id": "user-1",
        "purpose": "code_test",
        "instruction": "run a tiny isolated check",
        "require_human_approval": False,
    }
    payload.update(overrides)
    return OpenShellTask.model_validate(payload)


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    payload: dict[str, object] = {
        "enable_openshell_sandbox": True,
        "openshell_project_dir": tmp_path / "openshell",
        "openshell_allowed_input_dir": tmp_path / "input",
        "openshell_allowed_output_dir": tmp_path / "output",
        "openshell_require_human_approval": False,
    }
    payload.update(overrides)
    return Settings(**payload)


@pytest.mark.asyncio
async def test_disabled_returns_not_enabled(tmp_path: Path) -> None:
    app_settings = _settings(tmp_path, enable_openshell_sandbox=False)

    result = await OpenShellAdapter(app_settings).run_task(_task())

    assert result.status == "not_enabled"


@pytest.mark.asyncio
async def test_vendor_missing_returns_clear_error(tmp_path: Path) -> None:
    result = await OpenShellAdapter(_settings(tmp_path)).run_task(_task())

    assert result.status == "failed"
    assert result.summary == "OpenShellDeepAgentNotInstalled"


@pytest.mark.asyncio
async def test_gateway_unavailable_returns_controlled_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_settings = _settings(tmp_path)
    vendor = app_settings.openshell_project_dir / "vendor" / "openshell-deepagent"
    vendor.mkdir(parents=True)
    monkeypatch.setattr(adapter_module.shutil, "which", lambda name: "/usr/bin/docker")

    async def fake_run_command(
        args: list[str],
        *,
        timeout: int,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del timeout, cwd
        return_code = 0 if args == ["docker", "info"] else 1
        return subprocess.CompletedProcess(args, return_code, stdout="", stderr="unavailable")

    adapter = OpenShellAdapter(app_settings)
    monkeypatch.setattr(adapter, "_run_command", fake_run_command)

    result = await adapter.run_task(_task())

    assert result.status == "gateway_unavailable"


@pytest.mark.asyncio
async def test_task_with_input_files_generates_needs_approval(tmp_path: Path) -> None:
    app_settings = _settings(tmp_path, openshell_require_human_approval=False)
    vendor = app_settings.openshell_project_dir / "vendor" / "openshell-deepagent"
    vendor.mkdir(parents=True)
    input_dir = app_settings.openshell_allowed_input_dir
    input_dir.mkdir(parents=True)
    (input_dir / "data.txt").write_text("safe sample", encoding="utf-8")

    result = await OpenShellAdapter(app_settings).run_task(_task(input_files=["data.txt"]))

    assert result.status == "needs_approval"


@pytest.mark.asyncio
async def test_run_command_does_not_use_shell_true(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    completed = await OpenShellAdapter(_settings(tmp_path))._run_command(["echo", "ok"], timeout=1)

    assert completed.returncode == 0
    assert captured["args"] == ["echo", "ok"]
    assert "shell" not in captured["kwargs"]

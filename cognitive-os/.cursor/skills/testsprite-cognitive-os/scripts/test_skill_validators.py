#!/usr/bin/env python3
"""Unit tests for TestSprite skill validators (offline, no cloud)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ASSERT = ROOT / ".cursor/skills/testsprite-cognitive-os/scripts/assert_testsprite_run.py"
VALIDATE = ROOT / ".cursor/skills/testsprite-cognitive-os/scripts/validate_testsprite_config.py"
PLAN = ROOT / "qa/testsprite/frontend_commercial_plan.json"
RESULTS = ROOT / "testsprite_tests/tmp/batched_results.json"


def test_assert_smoke_on_existing_results() -> None:
    if not RESULTS.exists():
        return
    proc = subprocess.run(
        [sys.executable, str(ASSERT), "--mode", "smoke", "--results", str(RESULTS), "--plan", str(PLAN)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_validate_rejects_development_mode(tmp_path: Path) -> None:
    config_dir = tmp_path / "testsprite_tests/tmp"
    config_dir.mkdir(parents=True)
    config = {
        "type": "frontend",
        "localEndpoint": "http://localhost:3001/",
        "serverMode": "development",
        "executionArgs": {
            "projectPath": str(ROOT),
            "serverMode": "development",
            "testIds": [],
            "additionalInstruction": (
                "Cognitive OS audit on port 3001 via POST /auth/local-token. "
                "DO NOT send mail."
            ),
            "envs": {"API_KEY": "sk-user-test"},
        },
    }
    (config_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
    # Monkeypatch by running inline check — validate uses fixed ROOT path, so test via import
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("validate_testsprite_config", VALIDATE)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    original_config = module.CONFIG
    original_plan = module.PLAN
    try:
        module.CONFIG = config_dir / "config.json"
        module.PLAN = PLAN
        try:
            module.main()
            raise AssertionError("expected development mode to fail")
        except SystemExit as exc:
            assert exc.code != 0
    finally:
        module.CONFIG = original_config
        module.PLAN = original_plan

#!/usr/bin/env python3
"""Fail-closed validator for TestSprite config before any execution."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "testsprite_tests/tmp/config.json"
PLAN = ROOT / "qa/testsprite/frontend_commercial_plan.json"

URL_RE = re.compile(r"https?://[^\s\"']+", re.I)
BAD_HOST_FRAGMENTS = (
    "127.0.0.1:8000",
    "127.0.0.1:800",
    "localhost:8000",
    "health:80",
)


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"OK: {msg}")


def main() -> int:
    if not CONFIG.exists():
        fail(f"missing {CONFIG} — run: bash scripts/testsprite_mcp_prepare.sh")

    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    args = data.get("executionArgs") or {}

    endpoint = str(data.get("localEndpoint") or "")
    if endpoint not in ("http://localhost:3001/", "http://127.0.0.1:3001/"):
        fail(f"localEndpoint must be localhost:3001/, got {endpoint!r}")

    for key in ("serverMode",):
        if str(data.get(key) or "") != "production":
            fail(f"config.{key} must be 'production', got {data.get(key)!r}")
    if str(args.get("serverMode") or "") != "production":
        fail(f"executionArgs.serverMode must be 'production', got {args.get('serverMode')!r}")

    if str(data.get("type") or "") != "frontend":
        fail(f"config.type must be 'frontend', got {data.get('type')!r}")

    instr = str(args.get("additionalInstruction") or "")
    if URL_RE.search(instr):
        fail("additionalInstruction contains raw http(s) URL — remove it")
    for frag in BAD_HOST_FRAGMENTS:
        if frag in instr:
            fail(f"additionalInstruction contains forbidden fragment {frag!r}")

    key = (args.get("envs") or {}).get("API_KEY", "")
    if not key or key == "<redacted>":
        fail("API_KEY missing in config — export TESTSPRITE_API_KEY and run prepare.sh")

    test_ids = args.get("testIds")
    if test_ids is not None and not isinstance(test_ids, list):
        fail("executionArgs.testIds must be a list (empty OK for full-testsprite runner)")

    project_path = str(args.get("projectPath") or "")
    if not project_path or not Path(project_path).exists():
        fail(f"executionArgs.projectPath must exist: {project_path!r}")

    required_fragments = (
        "DO NOT send mail",
        "port 3001",
        "POST /auth/local-token",
    )
    for fragment in required_fragments:
        if fragment not in instr:
            fail(f"additionalInstruction missing required fragment {fragment!r}")

    forbidden_modes = ("development", "dev")
    if str(args.get("serverMode") or "").lower() in forbidden_modes:
        fail("serverMode development forbidden for Cognitive OS audits")

    if not PLAN.exists():
        fail(f"missing canonical plan {PLAN}")

    ok("config.json shape safe for TestSprite tunnel")
    ok(f"canonical plan present ({len(json.loads(PLAN.read_text()))} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

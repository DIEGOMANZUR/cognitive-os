#!/usr/bin/env python3
"""Fail-closed post-run validator for TestSprite smoke and full audit phases."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PLAN = ROOT / "qa/testsprite/frontend_commercial_plan.json"
DEFAULT_RESULTS = ROOT / "testsprite_tests/tmp/batched_results.json"

STOP_STRINGS = (
    "Target connect failed",
    "health:80",
    "jobs:80",
    "127.0.0.1:800",
    "127.0.0.1:8",
    "AUTH_FAILED",
    "ERROR: set API_KEY",
)


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"OK: {message}")


def load_plan_ids(plan_path: Path) -> list[str]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(plan, list) or not plan:
        fail(f"invalid plan: {plan_path}")
    ids: list[str] = []
    for item in plan:
        case_id = str(item.get("id") or "").strip()
        if not case_id:
            fail(f"plan case missing id in {plan_path}")
        ids.append(case_id)
    return ids


def load_results(results_path: Path) -> list[dict[str, object]]:
    if not results_path.exists():
        fail(f"missing results: {results_path}")
    data = json.loads(results_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        fail(f"empty results: {results_path}")
    return data


def title_matches_case(title: str, case_id: str) -> bool:
    title = str(title or "")
    return title.startswith(f"{case_id}-") or title.startswith(case_id)


def check_log(log_path: Path | None) -> None:
    if log_path is None or not log_path.exists():
        return
    text = log_path.read_text(encoding="utf-8", errors="replace")
    for stop in STOP_STRINGS:
        if stop in text:
            fail(f"log contains stop string {stop!r} ({log_path})")
    warning_lines = [
        line
        for line in text.splitlines()
        if "BATCH" in line and "warnings=" in line
    ]
    if not warning_lines:
        fail(f"log missing BATCH warnings line ({log_path})")
    for line in warning_lines:
        match = re.search(r"warnings=(\d+)", line)
        if not match:
            fail(f"could not parse warnings from: {line}")
        if int(match.group(1)) != 0:
            fail(f"non-zero tunnel warnings: {line}")


def assert_smoke(results_path: Path, plan_path: Path, log_path: Path | None) -> None:
    check_log(log_path)
    results = load_results(results_path)
    passed_tc001 = [
        item
        for item in results
        if str(item.get("testStatus")) == "PASSED"
        and title_matches_case(str(item.get("title") or ""), "TC001")
    ]
    if len(passed_tc001) != 1:
        fail("smoke requires exactly one PASSED TC001 in batched_results.json")
    ok("smoke TC001 PASSED with warnings=0 and no tunnel stop strings")


def assert_full(results_path: Path, plan_path: Path, log_path: Path | None) -> None:
    check_log(log_path)
    plan_ids = load_plan_ids(plan_path)
    results = load_results(results_path)
    if len(results) != len(plan_ids):
        fail(f"expected {len(plan_ids)} results, got {len(results)}")
    missing: list[str] = []
    not_passed: list[str] = []
    for case_id in plan_ids:
        matches = [
            item
            for item in results
            if title_matches_case(str(item.get("title") or ""), case_id)
        ]
        if not matches:
            missing.append(case_id)
            continue
        if str(matches[0].get("testStatus")) != "PASSED":
            not_passed.append(case_id)
    if missing:
        fail(f"missing cases in batched_results: {', '.join(missing)}")
    if not_passed:
        fail(f"non-PASSED cases: {', '.join(not_passed)}")
    ok(f"full plan {len(plan_ids)}/{len(plan_ids)} PASSED with warnings=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "full"), required=True)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    args = parser.parse_args()

    if args.mode == "smoke":
        assert_smoke(args.results, args.plan, args.log)
    else:
        assert_full(args.results, args.plan, args.log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

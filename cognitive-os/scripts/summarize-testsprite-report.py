#!/usr/bin/env python3
"""Build a stable, sanitized TestSprite summary from batched results."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _status(item: dict[str, Any]) -> str:
    return str(item.get("testStatus") or item.get("status") or item.get("result") or "UNKNOWN")


def _title(item: dict[str, Any]) -> str:
    return str(item.get("title") or item.get("id") or item.get("testId") or "Untitled test")


def _error(item: dict[str, Any]) -> str:
    raw = str(item.get("testError") or item.get("error") or "").replace("\n", " ").strip()
    return raw[:240]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="testsprite_tests/tmp/batched_results.json")
    parser.add_argument("--plan", default="qa/testsprite/frontend_commercial_plan.json")
    parser.add_argument("--output", default="qa/reports/testsprite_latest_summary.md")
    parser.add_argument("--package", default="@testsprite/testsprite-mcp@0.0.19")
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()

    results_path = Path(args.results)
    plan_path = Path(args.plan)
    output_path = Path(args.output)
    results = _load_json(results_path)
    plan = _load_json(plan_path)
    if not isinstance(results, list):
        raise SystemExit(f"results is not a list: {results_path}")
    if not isinstance(plan, list):
        raise SystemExit(f"plan is not a list: {plan_path}")

    counts = Counter(_status(item) for item in results)
    total = len(results)
    passed = counts.get("PASSED", 0)
    failed = sum(count for status, count in counts.items() if status not in {"PASSED", "SKIPPED"})
    skipped = counts.get("SKIPPED", 0)
    batches = (len(plan) + max(args.batch_size, 1) - 1) // max(args.batch_size, 1)
    verdict = "PASS" if total == len(plan) and failed == 0 and passed == len(plan) else "FAIL"

    lines = [
        "# TestSprite Latest Summary",
        "",
        f"- Generated at UTC: `{datetime.now(UTC).isoformat()}`",
        f"- TestSprite package: `{args.package}`",
        f"- Canonical plan: `{plan_path}`",
        f"- Sanitized aggregate results: `{results_path}`",
        f"- Tests in plan: **{len(plan)}**",
        f"- Tests executed: **{total}**",
        f"- Passed: **{passed}**",
        f"- Failed/blocked/unknown: **{failed}**",
        f"- Skipped: **{skipped}**",
        f"- Batch size: **{args.batch_size}**",
        f"- Batches executed: **{batches}**",
        f"- Verdict: **{verdict}**",
        "",
        "## Non-Passed Cases",
        "",
    ]
    non_passed = [item for item in results if _status(item) != "PASSED"]
    if not non_passed:
        lines.append("- None.")
    else:
        for item in non_passed:
            err = _error(item) or "No error detail recorded."
            lines.append(f"- `{_status(item)}` - {_title(item)}: {err}")

    lines.extend(
        [
            "",
            "## Sanitization",
            "",
            "- User IDs, video URLs, account metadata and credentials are intentionally omitted.",
            "- The full ignored TestSprite artifacts remain under `testsprite_tests/` for local debugging.",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: TestSprite summary written to {output_path}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Moderate-concurrency health probe for the local QA stack."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _probe(url: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(1_000_000)
        elapsed = (time.perf_counter() - started) * 1000
        payload: dict[str, Any] = {}
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}
        return {"ok": True, "status": response.status, "latency_ms": elapsed, "payload": payload}
    except Exception as exc:  # noqa: BLE001 - probe reports, it does not crash
        elapsed = (time.perf_counter() - started) * 1000
        return {
            "ok": False,
            "status": getattr(exc, "code", None),
            "latency_ms": elapsed,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _classify(results: list[dict[str, Any]], timeout_ms: float) -> str:
    failures = [item for item in results if not item["ok"] or int(item.get("status") or 0) >= 500]
    latencies = [float(item["latency_ms"]) for item in results if item["ok"]]
    p95 = max(latencies) if len(latencies) < 2 else statistics.quantiles(latencies, n=20)[18]
    failure_rate = len(failures) / max(len(results), 1)
    if failure_rate >= 0.50:
        return "failing"
    if failure_rate >= 0.20 or p95 > timeout_ms * 0.90:
        return "overloaded"
    if failures or p95 > timeout_ms * 0.60:
        return "degraded"
    return "healthy"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/health")
    parser.add_argument("--requests", type=int, default=16)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--output", default="qa/reports/qa_stack_health.json")
    args = parser.parse_args()

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = [pool.submit(_probe, args.url, args.timeout) for _ in range(max(1, args.requests))]
        results = [future.result() for future in as_completed(futures)]

    classification = _classify(results, args.timeout * 1000)
    latencies = [float(item["latency_ms"]) for item in results if item["ok"]]
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "url": args.url,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "timeout_seconds": args.timeout,
        "classification": classification,
        "healthy": classification == "healthy",
        "degraded": classification in {"degraded", "overloaded"},
        "overloaded": classification == "overloaded",
        "failing": classification == "failing",
        "successes": sum(1 for item in results if item["ok"]),
        "failures": sum(1 for item in results if not item["ok"]),
        "latency_ms_max": max(latencies) if latencies else None,
        "latency_ms_avg": statistics.mean(latencies) if latencies else None,
        "sample_errors": [item for item in results if not item["ok"]][:5],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        "QA_STACK_HEALTH "
        f"classification={classification} successes={report['successes']} "
        f"failures={report['failures']} output={output}"
    )
    return 0 if classification in {"healthy", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

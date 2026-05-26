#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

SKILL_ENV="${ROOT_DIR}/.cursor/skills/testsprite-cognitive-os/scripts/load_testsprite_env.sh"
if [[ -f "${SKILL_ENV}" ]]; then
  # shellcheck disable=SC1091
  source "${SKILL_ENV}" "${ROOT_DIR}"
fi

if [[ -z "${API_KEY:-}" && -z "${TESTSPRITE_API_KEY:-}" ]]; then
  CONFIG_FILE="${ROOT_DIR}/testsprite_tests/tmp/config.json"
  if [[ -f "${CONFIG_FILE}" ]]; then
    API_KEY="$(python3 - <<'PY'
import json
from pathlib import Path
p = Path("testsprite_tests/tmp/config.json")
data = json.loads(p.read_text())
key = data.get("executionArgs", {}).get("envs", {}).get("API_KEY", "")
if key and key not in ("<redacted>", ""):
    print(key)
PY
)"
  fi
fi
if [[ -z "${API_KEY:-}" && -z "${TESTSPRITE_API_KEY:-}" ]]; then
  echo "ERROR: set API_KEY or TESTSPRITE_API_KEY with a TestSprite API key." >&2
  echo "Run: bash scripts/testsprite_mcp_prepare.sh (or add TESTSPRITE_API_KEY to .env)" >&2
  echo "See: .cursor/skills/testsprite-cognitive-os/SKILL.md" >&2
  exit 2
fi

export API_KEY="${API_KEY:-${TESTSPRITE_API_KEY}}"
export TESTSPRITE_BATCH_SIZE="${TESTSPRITE_BATCH_SIZE:-1}"
export TESTSPRITE_LOCAL_ENDPOINT="${TESTSPRITE_LOCAL_ENDPOINT:-http://localhost:3001/}"
export TESTSPRITE_BACKEND_HEALTH_URL="${TESTSPRITE_BACKEND_HEALTH_URL:-http://127.0.0.1:8000/health}"
export TESTSPRITE_PACKAGE="${TESTSPRITE_PACKAGE:-@testsprite/testsprite-mcp@0.0.19}"
export TESTSPRITE_COMMAND="${TESTSPRITE_COMMAND:-npx --yes ${TESTSPRITE_PACKAGE} generateCodeAndExecute}"
export TESTSPRITE_CANONICAL_PLAN="${TESTSPRITE_CANONICAL_PLAN:-qa/testsprite/frontend_commercial_plan.json}"
export TESTSPRITE_SUMMARY_PATH="${TESTSPRITE_SUMMARY_PATH:-qa/reports/testsprite_latest_summary.md}"
export TESTSPRITE_BATCH_TIMEOUT_SECONDS="${TESTSPRITE_BATCH_TIMEOUT_SECONDS:-900}"
export TESTSPRITE_BATCH_IDLE_TIMEOUT_SECONDS="${TESTSPRITE_BATCH_IDLE_TIMEOUT_SECONDS:-300}"
export TESTSPRITE_BATCH_RETRIES="${TESTSPRITE_BATCH_RETRIES:-2}"
export TESTSPRITE_TEST_IDS="${TESTSPRITE_TEST_IDS:-}"
export TESTSPRITE_CLEAN_GENERATED="${TESTSPRITE_CLEAN_GENERATED:-1}"

cleanup_testsprite_runtime() {
  python3 - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
config = root / "testsprite_tests/tmp/config.json"
if config.exists():
    data = json.loads(config.read_text())
    # Keep API_KEY in gitignored local config for zero-friction re-runs on the
    # dedicated PC. Only redact the tunnel proxy credential in artifacts.
    if "proxy" in data:
        data["proxy"] = "<redacted>"
    config.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
for rel in ("testsprite_tests/tmp/execution.lock", "testsprite_tests/tmp/mcp.log"):
    try:
        (root / rel).unlink()
    except FileNotFoundError:
        pass
PY
}
trap cleanup_testsprite_runtime EXIT INT TERM

python3 - <<'PY'
from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path.cwd()
CONFIG = ROOT / "testsprite_tests/tmp/config.json"
PLAN = ROOT / "testsprite_tests/testsprite_frontend_test_plan.json"
CANONICAL_PLAN = ROOT / os.environ["TESTSPRITE_CANONICAL_PLAN"]
RESULTS = ROOT / "testsprite_tests/tmp/test_results.json"
RAW = ROOT / "testsprite_tests/tmp/raw_report.md"
REPORT = ROOT / "testsprite_tests/testsprite-mcp-test-report.md"
LOCK = ROOT / "testsprite_tests/tmp/execution.lock"
MCP_LOG = ROOT / "testsprite_tests/tmp/mcp.log"
AGGREGATE = ROOT / "testsprite_tests/tmp/batched_results.json"
SUMMARY = ROOT / os.environ["TESTSPRITE_SUMMARY_PATH"]

api_key = os.environ["API_KEY"]
batch_size = max(1, int(os.environ["TESTSPRITE_BATCH_SIZE"]))
batch_timeout = max(60, int(os.environ["TESTSPRITE_BATCH_TIMEOUT_SECONDS"]))
idle_timeout = max(60, int(os.environ["TESTSPRITE_BATCH_IDLE_TIMEOUT_SECONDS"]))
batch_retries = max(0, int(os.environ["TESTSPRITE_BATCH_RETRIES"]))
endpoint = os.environ["TESTSPRITE_LOCAL_ENDPOINT"]
health_url = os.environ["TESTSPRITE_BACKEND_HEALTH_URL"]
command = shlex.split(os.environ["TESTSPRITE_COMMAND"])
redact = re.compile(r"sk-user-[A-Za-z0-9_\-]+")


def load_plan() -> list[dict[str, object]]:
    if not CANONICAL_PLAN.exists():
        raise SystemExit(
            f"Missing canonical TestSprite plan {CANONICAL_PLAN}. "
            "Update qa/testsprite/frontend_commercial_plan.json before running full-testsprite."
        )
    plan = json.loads(CANONICAL_PLAN.read_text())
    if not isinstance(plan, list) or not plan:
        raise SystemExit(f"Invalid or empty TestSprite frontend plan: {CANONICAL_PLAN}")
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    if os.environ["TESTSPRITE_CLEAN_GENERATED"].strip().lower() in {"1", "true", "yes", "on"}:
        for generated in (ROOT / "testsprite_tests").glob("TC*.py"):
            safe_unlink(generated)
    print(f"PLAN canonical={CANONICAL_PLAN} runtime_copy={PLAN}", flush=True)
    return plan


def redact_config() -> None:
    if not CONFIG.exists():
        return
    data = json.loads(CONFIG.read_text())
    if "proxy" in data:
        data["proxy"] = "<redacted>"
    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def cleanup_runtime_artifacts(*, keep_results: bool = False) -> None:
    targets = [RAW, REPORT, LOCK, MCP_LOG]
    if not keep_results:
        targets.append(RESULTS)
    for path in targets:
        safe_unlink(path)


def health(label: str) -> None:
    with urllib.request.urlopen(health_url, timeout=10) as response:
        print(f"HEALTH {label}: {response.status}", flush=True)


def prepare_config(batch: list[str]) -> None:
    data = {
        "status": "init",
        "scope": "codebase",
        "type": "frontend",
        "localEndpoint": endpoint,
    }
    data["localEndpoint"] = endpoint
    data["serverMode"] = "production"
    args = data.setdefault("executionArgs", {})
    args.update(
        {
            "projectName": ROOT.name,
            "projectPath": str(ROOT),
            "testIds": batch,
            "serverMode": "production",
            "additionalInstruction": (
                "Run this TestSprite batch as part of the complete corrected commercial plan. "
                "Use only the local production frontend/backend. Populated and empty local states "
                "are both valid when the UI is honest, diagnostic, and non-crashing. Do not approve "
                "arbitrary real approvals; only approve explicit safe TestSprite/no-op/dry-run fixtures. "
                "Do not create email drafts, send email, or perform DNS/provider/Drive/Calendar "
                "production writes. For mail digest, either preview or visible disabled/read-only "
                "diagnostic is a pass. For jobs/approvals, rows with statuses/counters or clear empty "
                "states are both passes. Fail on crash, white screen, pageerror, hidden/lying state, "
                "unsafe write, broken navigation, or unclear diagnosis."
            ),
            "envs": {"API_KEY": api_key},
        }
    )
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    cleanup_runtime_artifacts()


def terminate_process(proc: subprocess.Popen[str], *, index: int, reason: str) -> None:
    if proc.poll() is not None:
        return
    print(f"BATCH {index} STOP {reason}", flush=True)
    try:
        os.killpg(proc.pid, signal.SIGINT)
        proc.wait(timeout=15)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass


def run_batch_once(
    index: str,
    total: int | str,
    batch: list[str],
    attempt: int,
) -> list[dict[str, object]]:
    print(f"BATCH {index}/{total} START {','.join(batch)}", flush=True)
    if attempt > 1:
        print(f"BATCH {index} RETRY attempt={attempt}", flush=True)
    health(f"batch {index}")
    prepare_config(batch)
    proc = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    start = time.time()
    last_activity = start
    target_connect_warnings = 0
    recent_lines: list[str] = []
    try:
        while True:
            if proc.stdout is not None:
                import select

                ready, _, _ = select.select([proc.stdout], [], [], 1.0)
                if ready:
                    line = proc.stdout.readline()
                    if line:
                        last_activity = time.time()
                        safe = redact.sub("<redacted>", line.rstrip())
                        recent_lines.append(safe)
                        recent_lines = recent_lines[-80:]
                        if "Target connect failed" in safe:
                            target_connect_warnings += 1
                            if target_connect_warnings <= 3 or target_connect_warnings % 20 == 0:
                                print(
                                    f"BATCH {index} WARN target-connect #{target_connect_warnings}",
                                    flush=True,
                                )
                        elif any(
                            marker in safe
                            for marker in (
                                "Starting test execution",
                                "Test execution completed",
                                "Execution lock released",
                                "Test execution failed",
                            )
                        ):
                            print(f"BATCH {index} {safe}", flush=True)
            if RESULTS.exists() and not LOCK.exists():
                time.sleep(2)
                break
            if proc.poll() is not None:
                break
            elapsed = time.time() - start
            idle = time.time() - last_activity
            if elapsed > batch_timeout:
                terminate_process(proc, index=index, reason=f"timeout after {batch_timeout}s")
                raise TimeoutError(f"batch {index} timed out after {batch_timeout}s")
            if idle > idle_timeout and not RESULTS.exists():
                terminate_process(proc, index=index, reason=f"idle after {idle_timeout}s")
                raise TimeoutError(f"batch {index} idle timeout after {idle_timeout}s")

        if proc.poll() is None:
            terminate_process(proc, index=index, reason="results collected")
        if not RESULTS.exists():
            print(f"BATCH {index} RETURN_CODE {proc.returncode}", flush=True)
            for recent in recent_lines[-20:]:
                print(f"BATCH {index} OUTPUT {recent}", flush=True)
            raise RuntimeError(f"batch {index} did not produce {RESULTS}")
        results = json.loads(RESULTS.read_text())
        counts = Counter(item.get("testStatus", "UNKNOWN") for item in results)
        print(
            f"BATCH {index} RESULTS total={len(results)} {dict(counts)} "
            f"warnings={target_connect_warnings}",
            flush=True,
        )
        for item in results:
            error = str(item.get("testError") or "").replace("\n", " ")[:180]
            print(f"  {item.get('testStatus')}: {item.get('title')} {error}", flush=True)
        if any(item.get("testStatus") != "PASSED" for item in results):
            raise RuntimeError(f"batch {index} had non-passed TestSprite cases")
        health(f"after batch {index}")
        cleanup_runtime_artifacts(keep_results=True)
        return results
    finally:
        terminate_process(proc, index=index, reason="cleanup")
        redact_config()
        safe_unlink(LOCK)


def run_batch(index: str, total: int | str, batch: list[str]) -> list[dict[str, object]]:
    last_error: Exception | None = None
    for attempt in range(1, batch_retries + 2):
        try:
            return run_batch_once(index, total, batch, attempt)
        except Exception as exc:
            last_error = exc
            print(f"BATCH {index} ATTEMPT {attempt} FAILED: {type(exc).__name__}: {exc}", flush=True)
            cleanup_runtime_artifacts()
            redact_config()
            if attempt <= batch_retries:
                health(f"retry-ready batch {index}")
                time.sleep(10)
                continue
            if len(batch) > 1:
                midpoint = max(1, len(batch) // 2)
                left = batch[:midpoint]
                right = batch[midpoint:]
                print(
                    f"BATCH {index} SPLIT after failure into {','.join(left)} "
                    f"and {','.join(right)}",
                    flush=True,
                )
                return run_batch(f"{index}a", total, left) + run_batch(f"{index}b", total, right)
            raise
    raise RuntimeError(f"batch {index} failed") from last_error


def main() -> None:
    plan = load_plan()
    ids = [str(case["id"]) for case in plan]
    requested_ids = [item.strip() for item in os.environ["TESTSPRITE_TEST_IDS"].split(",") if item.strip()]
    if requested_ids:
        unknown = sorted(set(requested_ids) - set(ids))
        if unknown:
            raise SystemExit(f"Unknown TESTSPRITE_TEST_IDS: {', '.join(unknown)}")
        ids = requested_ids
    batches = [ids[start : start + batch_size] for start in range(0, len(ids), batch_size)]
    all_results: list[dict[str, object]] = []
    try:
        for index, batch in enumerate(batches, start=1):
            all_results.extend(run_batch(str(index), len(batches), batch))
            time.sleep(5)
        AGGREGATE.parent.mkdir(parents=True, exist_ok=True)
        AGGREGATE.write_text(json.dumps(all_results, indent=2, ensure_ascii=False) + "\n")
        counts = Counter(item.get("testStatus", "UNKNOWN") for item in all_results)
        print(f"BATCHED COMPLETE total={len(all_results)} {dict(counts)} output={AGGREGATE}", flush=True)
        if len(all_results) != len(ids) or counts != {"PASSED": len(ids)}:
            raise SystemExit(1)
        summary_cmd = [
            str(ROOT / "scripts/summarize-testsprite-report.py"),
            "--results",
            str(AGGREGATE),
            "--plan",
            str(CANONICAL_PLAN),
            "--output",
            str(SUMMARY),
            "--package",
            os.environ["TESTSPRITE_PACKAGE"],
            "--batch-size",
            str(batch_size),
        ]
        if os.environ["TESTSPRITE_TEST_IDS"].strip():
            summary_cmd.append("--partial-ok")
        subprocess.run(summary_cmd, cwd=ROOT, check=True)
    finally:
        redact_config()
        safe_unlink(LOCK)
        safe_unlink(MCP_LOG)


main()
PY

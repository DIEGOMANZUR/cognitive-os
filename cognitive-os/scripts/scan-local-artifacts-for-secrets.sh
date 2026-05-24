#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 - <<'PY'
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
TARGETS = [
    "testsprite_tests/tmp",
    "backend/storage/mail_digests",
    "logs",
    "traces",
    "playwright-report",
    "test-results",
    "frontend/playwright-report",
    "frontend/test-results",
    "qa/reports",
]
SKIP_PARTS = {"node_modules", ".git", ".next", ".next-qa", ".venv", "__pycache__"}
ALLOW_VALUES = {
    "test-token",
    "fake-token",
    "example-key",
    "dummy-secret",
    "changeme",
    "<redacted>",
    "redacted",
}
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("testsprite-token", re.compile(r"sk-user-[A-Za-z0-9_\-]{20,}")),
    ("openai-like-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{24,}")),
    ("anthropic-like-key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{24,}")),
    ("gemini-like-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}")),
    ("bearer-token", re.compile(r"Bearer\s+[A-Za-z0-9._\-]{24,}", re.IGNORECASE)),
    ("url-credential", re.compile(r"://[^\s/:]+:[^\s/@]{12,}@")),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    ),
    (
        "named-secret",
        re.compile(
            r"(?i)\b(api[_-]?key|token|secret|password|authorization)\b"
            r"\s*[:=]\s*['\"]?([A-Za-z0-9_./+\-]{24,})"
        ),
    ),
]


def allowed(match: str) -> bool:
    value = match.strip().strip("'\"").lower()
    return any(token in value for token in ALLOW_VALUES)


def iter_files() -> list[Path]:
    files: list[Path] = []
    for target in TARGETS:
        base = ROOT / target
        if not base.exists():
            continue
        if base.is_file():
            files.append(base)
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            files.append(path)
    return files


findings: list[str] = []
for path in iter_files():
    try:
        handle = path.open(encoding="utf-8", errors="ignore")
    except OSError as exc:
        findings.append(f"{path}: read-error: {exc}")
        continue
    with handle:
        for line_no, line in enumerate(handle, start=1):
            for name, pattern in PATTERNS:
                for match in pattern.finditer(line):
                    raw = match.group(0)
                    candidate = match.group(2) if name == "named-secret" and match.lastindex else raw
                    if allowed(candidate) or allowed(raw):
                        continue
                    findings.append(f"{path}:{line_no}: {name}: {raw[:16]}...")

if findings:
    print("FAIL: critical secret-shaped values found in local QA artifacts:")
    for finding in findings:
        print(f"  - {finding}")
    sys.exit(1)

scanned = len(iter_files())
print(f"OK: no critical secrets found in local QA artifacts ({scanned} files scanned)")
PY

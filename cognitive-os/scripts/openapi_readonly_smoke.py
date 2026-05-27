#!/usr/bin/env python3
"""Read-only OpenAPI GET smoke for Cognitive OS.

This is a deterministic companion to Schemathesis. It intentionally exercises
only GET operations, uses a local JWT when available, substitutes safe path
parameters, and fails on unexpected 5xx/invalid JSON. Expected auth/resource
guards remain valid 4xx outcomes.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


API_BASE = os.environ.get("COGOS_API_BASE", "http://127.0.0.1:8000").rstrip("/")
MAX_GETS = int(os.environ.get("COGOS_OPENAPI_SMOKE_MAX_GETS", "0") or "0")
TIMEOUT = float(os.environ.get("COGOS_OPENAPI_SMOKE_TIMEOUT", "12"))
UUID_ZERO = "00000000-0000-0000-0000-000000000000"
SAFE_ID = "00000000-0000-0000-0000-000000000000"

PUBLIC_GETS = {"/health", "/openapi.json", "/docs", "/redoc"}
SKIP_PREFIXES = (
    "/test-fixtures",
)


@dataclass
class SmokeResult:
    method: str
    path_template: str
    path: str
    status: int | str
    elapsed_ms: float
    ok: bool
    reason: str


def _request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[int | str, Any, float, str | None]:
    data = None
    headers: dict[str, str] = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{API_BASE}{path}", method=method, headers=headers, data=data)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            elapsed = (time.perf_counter() - start) * 1000
            return resp.status, _decode_payload(raw), elapsed, resp.headers.get("content-type")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        elapsed = (time.perf_counter() - start) * 1000
        return exc.code, _decode_payload(raw), elapsed, exc.headers.get("content-type")
    except Exception as exc:  # noqa: BLE001 - report as smoke failure
        elapsed = (time.perf_counter() - start) * 1000
        return "ERROR", {"error_type": type(exc).__name__, "detail": str(exc)}, elapsed, None


def _decode_payload(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return raw.decode("utf-8", errors="replace")[:500]


def _local_token() -> str | None:
    existing = os.environ.get("COGOS_JWT", "").strip()
    if existing:
        return existing
    status, payload, _, _ = _request("POST", "/auth/local-token", body={})
    if status != 200 or not isinstance(payload, dict):
        return None
    token = payload.get("access_token") or payload.get("token")
    return str(token) if token else None


def _safe_path(path_template: str, operation: dict[str, Any]) -> str:
    params = operation.get("parameters") or []
    by_name = {str(param.get("name")): param for param in params if isinstance(param, dict)}

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        param = by_name.get(name) or {}
        schema = param.get("schema") if isinstance(param.get("schema"), dict) else {}
        fmt = str(schema.get("format") or "").lower()
        typ = str(schema.get("type") or "").lower()
        if fmt == "uuid" or name.endswith("_id") or name == "id":
            return UUID_ZERO
        if typ in {"integer", "number"} or name in {"limit", "offset"}:
            return "1"
        return SAFE_ID

    return re.sub(r"\{([^}]+)\}", replace, path_template)


def _query_suffix(operation: dict[str, Any]) -> str:
    params = operation.get("parameters") or []
    query: list[str] = []
    for param in params:
        if not isinstance(param, dict) or param.get("in") != "query":
            continue
        name = str(param.get("name"))
        schema = param.get("schema") if isinstance(param.get("schema"), dict) else {}
        if name in {"limit", "max_results", "per_page"}:
            value = "1"
        elif name in {"offset", "page"}:
            value = "0"
        elif schema.get("type") == "boolean":
            value = "false"
        else:
            continue
        query.append(f"{name}={value}")
    return ("?" + "&".join(query)) if query else ""


def _is_expected_status(path_template: str, status: int | str, payload: Any) -> tuple[bool, str]:
    if status == "ERROR":
        return False, "request_error"
    assert isinstance(status, int)
    if status >= 500:
        return False, "unexpected_5xx"
    if path_template in PUBLIC_GETS and status != 200:
        return False, "public_endpoint_not_200"
    if status in {200, 204, 400, 401, 403, 404, 409, 422}:
        if status == 200 and isinstance(payload, str) and path_template not in {"/health", "/docs", "/redoc"}:
            return False, "unexpected_text_response"
        return True, "expected_status"
    return False, f"unexpected_status_{status}"


def main() -> int:
    token = _local_token()
    status, spec, _, _ = _request("GET", "/openapi.json")
    if status != 200 or not isinstance(spec, dict):
        print(json.dumps({"ok": False, "reason": "openapi_unavailable", "status": status}))
        return 2
    paths = spec.get("paths") if isinstance(spec.get("paths"), dict) else {}
    results: list[SmokeResult] = []
    for path_template, ops in sorted(paths.items()):
        if any(path_template.startswith(prefix) for prefix in SKIP_PREFIXES):
            continue
        if not isinstance(ops, dict) or "get" not in ops:
            continue
        operation = ops["get"] if isinstance(ops["get"], dict) else {}
        path = _safe_path(path_template, operation) + _query_suffix(operation)
        use_token = None if path_template in PUBLIC_GETS else token
        status_code, payload, elapsed, _content_type = _request("GET", path, token=use_token)
        ok, reason = _is_expected_status(path_template, status_code, payload)
        results.append(
            SmokeResult(
                method="GET",
                path_template=path_template,
                path=path,
                status=status_code,
                elapsed_ms=round(elapsed, 1),
                ok=ok,
                reason=reason,
            )
        )
        if MAX_GETS and len(results) >= MAX_GETS:
            break

    failures = [result for result in results if not result.ok]
    summary = {
        "ok": not failures,
        "api_base": API_BASE,
        "token_obtained": bool(token),
        "total_gets": len(results),
        "failures": [result.__dict__ for result in failures],
        "results": [result.__dict__ for result in results],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())

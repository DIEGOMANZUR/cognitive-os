"""Regression for the FastAPI correlation-id middleware.

The middleware honors an incoming `X-Request-ID` (capped to 64 chars) or
generates a fresh uuid4, binds it to structlog contextvars, and echoes it
back on the response so callers can correlate failures with server logs.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _headers(rid: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {create_access_token(user_id='1')}"}
    if rid is not None:
        headers["X-Request-ID"] = rid
    return headers


def test_correlation_id_echoed_when_provided(client: TestClient) -> None:
    rid = "req-test-abc"
    response = client.get("/health", headers={"X-Request-ID": rid})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == rid


def test_correlation_id_generated_when_missing(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    rid = response.headers.get("X-Request-ID", "")
    # uuid4 hex-with-dashes is 36 chars; we accept any non-empty server id.
    assert len(rid) >= 8


def test_correlation_id_truncated_to_safe_length(client: TestClient) -> None:
    long_id = "x" * 200
    response = client.get("/health", headers={"X-Request-ID": long_id})
    rid = response.headers.get("X-Request-ID", "")
    assert len(rid) <= 64


def test_correlation_id_on_authenticated_endpoint(client: TestClient) -> None:
    response = client.get("/system/info", headers=_headers("req-system-1"))
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "req-system-1"

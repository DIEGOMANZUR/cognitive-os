"""P1 commercial-audit hardening — /test/fixtures/* gating.

Contract (`docs/CURRENT_STATE.md` §Hardening; `api/test_fixtures.py:_require_fixtures_enabled`):

  The fixtures endpoints (``POST /test/fixtures/reset``,
  ``POST /test/fixtures/seed/{scenario}``, ``GET /test/fixtures/state``)
  MUST be reachable only when one of:

    1. ``settings.environment == "test"``
    2. ``APP_ENV=test`` (environment variable)
    3. ``COGOS_TEST_FIXTURES_ENABLED in {"1","true","yes","on"}``

  In every other state the endpoints MUST return HTTP 403 with a
  diagnostic message — preventing a production deploy from exposing
  destructive test scaffolding.

This audit exercises the gate over the API surface (not the helper
function) so a future refactor that bypassed ``_require_fixtures_enabled``
in the route layer is caught.

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §C5.
"""

from __future__ import annotations

import httpx
import pytest

import cognitive_os.api.test_fixtures as test_fixtures
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import settings


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='audit-fixtures')}"}


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip the audit env from APP_ENV / COGOS_TEST_FIXTURES_ENABLED.

    The pytest process can have these set; we want each test to control
    them explicitly.
    """
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("COGOS_TEST_FIXTURES_ENABLED", raising=False)


@pytest.mark.asyncio
async def test_fixtures_endpoints_forbidden_in_local_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When environment is `local` and no env override is set, gate fires 403."""
    monkeypatch.setattr(settings, "environment", "local")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        state = await client.get("/test/fixtures/state", headers=_headers())
        reset = await client.post("/test/fixtures/reset", headers=_headers())
        seed = await client.post("/test/fixtures/seed/empty", headers=_headers())

    for response in (state, reset, seed):
        assert response.status_code == 403, response.text
        detail = response.json()["detail"]
        assert "APP_ENV=test" in detail or "COGOS_TEST_FIXTURES_ENABLED" in detail


@pytest.mark.asyncio
async def test_fixtures_endpoints_forbidden_in_production_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `production` environment without overrides MUST 403 — the most
    important case: a deploy that accidentally exposes /test/fixtures/*."""
    monkeypatch.setattr(settings, "environment", "production")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for method, path in (
            ("GET", "/test/fixtures/state"),
            ("POST", "/test/fixtures/reset"),
            ("POST", "/test/fixtures/seed/empty"),
        ):
            response = await client.request(method, path, headers=_headers())
            assert response.status_code == 403, (
                f"{method} {path} in production returned {response.status_code}"
            )


@pytest.mark.asyncio
async def test_fixtures_endpoints_open_when_app_env_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """APP_ENV=test must open the endpoints regardless of settings.environment."""
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setenv("APP_ENV", "test")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        state = await client.get("/test/fixtures/state", headers=_headers())
    # 200 (state ok) — the gate is open.
    assert state.status_code == 200, state.text


@pytest.mark.asyncio
async def test_fixtures_endpoints_open_when_cogos_flag_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """COGOS_TEST_FIXTURES_ENABLED=true opens the gate too."""
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setenv("COGOS_TEST_FIXTURES_ENABLED", "true")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        state = await client.get("/test/fixtures/state", headers=_headers())
    assert state.status_code == 200, state.text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("on", True),
        ("TRUE", True),
        ("false", False),
        ("0", False),
        ("", False),
        ("no", False),
    ],
)
def test_fixtures_enabled_predicate_truthiness(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    """The helper's accepted truthy values are exactly {1,true,yes,on} (case-insensitive)."""
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("COGOS_TEST_FIXTURES_ENABLED", value)
    assert test_fixtures._fixtures_enabled() is expected

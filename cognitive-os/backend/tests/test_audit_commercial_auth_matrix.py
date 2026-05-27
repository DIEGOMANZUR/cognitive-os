"""P1 commercial-audit hardening — Auth matrix for representative endpoints.

Contract (`docs/ARCHITECTURE.md` §9; `docs/CURRENT_STATE.md` Snapshot Tecnico):

  * Almost every REST endpoint requires a JWT (``Depends(require_authenticated_user)``).
  * A subset requires admin (``Depends(require_admin_user)``) when
    ``ADMIN_USER_IDS`` is non-empty or the role appears in ``AUTH_ADMIN_ROLES``.
  * Three endpoints are intentionally public: ``/health``, ``/auth/local-token``
    (only under ``dedicated_local/full``), and the static OpenAPI/docs paths.

This file does not enumerate all 147 endpoints — that would be brittle —
but provides a representative matrix per family. Any future regression
(e.g. forgetting ``_auth_dependency`` on a new endpoint) is also caught
by FastAPI's signature validation, but the matrix surfaces the failure
explicitly with the endpoint name.

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §C2.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _operator_headers() -> dict[str, str]:
    token = create_access_token(user_id="audit-operator", roles=["operator"])
    return {"Authorization": f"Bearer {token}"}


def _admin_headers() -> dict[str, str]:
    token = create_access_token(user_id="audit-admin", roles=["admin"])
    return {"Authorization": f"Bearer {token}"}


# (method, path, requires_auth)
# Public endpoints — no auth needed; anon returns 200 (or 405 for wrong-method).
PUBLIC_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/health"),
]


# Endpoints that any authenticated user (operator) may hit. We pick the
# **GET** variants where the happy path returns 200; some of these may
# return 200 / 404 / 422 depending on whether resources exist — anything
# ≠ 401/403 proves the auth gate passed.
OPERATOR_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/health/dashboard"),
    ("GET", "/system/info"),
    ("GET", "/system/readiness"),
    ("GET", "/system/mcp"),
    ("GET", "/config/public"),
    ("GET", "/knowledge/stats"),
    ("GET", "/agents"),
    ("GET", "/jobs"),
    ("GET", "/approvals"),
    ("GET", "/audit"),
    ("GET", "/audit/events"),
    ("GET", "/documents"),
    ("GET", "/threads"),
    ("GET", "/assist/tasks"),
    ("GET", "/assist/notes"),
    ("GET", "/deepagents"),
    ("GET", "/deepagents/skills"),
    ("GET", "/deepagents/memory/proposals"),
    ("GET", "/actions"),
    ("GET", "/actions/capabilities"),
    ("GET", "/actions/requests"),
    ("GET", "/actions/maps/status"),
    ("GET", "/actions/calendar/status"),
    ("GET", "/actions/drive/status"),
    ("GET", "/actions/gmail/status"),
    ("GET", "/actions/godaddy/status"),
    ("GET", "/actions/documents/status"),
    ("GET", "/actions/webbridge/status"),
    ("GET", "/actions/captcha/status"),
    ("GET", "/mail/status"),
    ("GET", "/mail/messages"),
    ("GET", "/voice/status"),
    ("GET", "/research/runs"),
    ("GET", "/sandbox/openshell/status"),
    ("GET", "/deepagents/memory/recipes"),
    ("GET", "/deepagents/memory/warnings"),
    ("GET", "/deepagents/learning/tool-scorecard"),
    ("GET", "/deepagents/learning/skill-promotions"),
    ("GET", "/deepagents/learning/reflection"),
]


# Endpoints that REQUIRE admin. Operator must get 403; admin must get
# anything that is NOT 401/403 (200 / 404 / 422 are all OK as proof of
# passing the gate).
ADMIN_ONLY_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/system/credentials-status"),
]


# POST-only admin endpoints (these expect a body; we only need to confirm
# the gate fires, so we POST an empty body — operator gets 403 BEFORE the
# body is validated).
ADMIN_ONLY_POST_ENDPOINTS: list[tuple[str, str]] = [
    # Use a syntactically valid UUID so the gate fires BEFORE path-parameter
    # parsing — we are testing auth, not UUID validation.
    ("POST", "/deepagents/memory/proposals/00000000-0000-0000-0000-000000000001/approve"),
    ("POST", "/deepagents/memory/consolidate/run"),
    ("POST", "/deepagents/memory/recipes/extract-now"),
    ("POST", "/deepagents/memory/warnings/scan-now"),
    ("POST", "/deepagents/learning/tool-scorecard/aggregate-now"),
    ("POST", "/deepagents/learning/skill-promotions/evaluate-now"),
    ("POST", "/deepagents/learning/reflection/run-now"),
]


def _hit(client: TestClient, method: str, path: str, **kwargs: object) -> int:
    """Return the response status code; if the handler raises a domain
    exception that bubbles through ``TestClient`` we treat it as proof the
    auth gate already passed (return a synthetic 599) so the matrix can
    focus on auth without coupling to downstream service behaviour."""
    try:
        response = client.request(method, path, **kwargs)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 - the gate is what we're testing
        return 599
    return response.status_code


@pytest.mark.parametrize(
    ("method", "path"),
    PUBLIC_ENDPOINTS,
    ids=[f"{m}_{p}" for m, p in PUBLIC_ENDPOINTS],
)
def test_public_endpoint_no_auth_returns_2xx(client: TestClient, method: str, path: str) -> None:
    code = _hit(client, method, path)
    assert code in {200, 204, 304}, f"public {method} {path} returned {code}"


@pytest.mark.parametrize(
    ("method", "path"),
    OPERATOR_ENDPOINTS,
    ids=[f"{m}_{p}" for m, p in OPERATOR_ENDPOINTS],
)
def test_operator_endpoint_rejects_anon(client: TestClient, method: str, path: str) -> None:
    code = _hit(client, method, path)
    assert code in {401, 403}, f"{method} {path} returned {code} anon (expected 401/403)"


@pytest.mark.parametrize(
    ("method", "path"),
    OPERATOR_ENDPOINTS,
    ids=[f"{m}_{p}" for m, p in OPERATOR_ENDPOINTS],
)
def test_operator_endpoint_accepts_operator_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    """Operator JWT must pass the gate.

    The endpoint can return 200 / 404 / 422 / 500 etc. depending on the
    state of the DB and external services — what we care about is that
    the auth gate did NOT short-circuit to 401/403.
    """
    monkeypatch.setattr(settings, "admin_user_ids", [])
    monkeypatch.setattr(settings, "auth_admin_roles", ["admin"])
    code = _hit(client, method, path, headers=_operator_headers())
    assert code not in {401, 403}, (
        f"{method} {path} returned {code} for an operator JWT (gate misfired)"
    )


@pytest.mark.parametrize(
    ("method", "path"),
    ADMIN_ONLY_ENDPOINTS + ADMIN_ONLY_POST_ENDPOINTS,
    ids=[f"{m}_{p}" for m, p in ADMIN_ONLY_ENDPOINTS + ADMIN_ONLY_POST_ENDPOINTS],
)
def test_admin_endpoint_rejects_operator(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    """Operator JWT must be forbidden from admin-gated endpoints."""
    monkeypatch.setattr(settings, "admin_user_ids", [])
    monkeypatch.setattr(settings, "auth_admin_roles", ["admin"])
    code = _hit(client, method, path, headers=_operator_headers(), json={})
    assert code == 403, f"{method} {path} returned {code} for operator (expected 403)"


@pytest.mark.parametrize(
    ("method", "path"),
    ADMIN_ONLY_ENDPOINTS + ADMIN_ONLY_POST_ENDPOINTS,
    ids=[f"{m}_{p}" for m, p in ADMIN_ONLY_ENDPOINTS + ADMIN_ONLY_POST_ENDPOINTS],
)
def test_admin_endpoint_passes_gate_for_admin_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    """Admin JWT must pass the gate. Service-level errors are fine."""
    monkeypatch.setattr(settings, "admin_user_ids", [])
    monkeypatch.setattr(settings, "auth_admin_roles", ["admin"])
    code = _hit(client, method, path, headers=_admin_headers(), json={})
    assert code not in {401, 403}, f"{method} {path} returned {code} for admin (gate misfired)"


def test_auth_matrix_total_coverage_is_meaningful() -> None:
    """Meta-assertion: ensure the matrix is non-trivial."""
    assert len(OPERATOR_ENDPOINTS) >= 30, "operator matrix too small to detect regressions"
    assert len(ADMIN_ONLY_ENDPOINTS) + len(ADMIN_ONLY_POST_ENDPOINTS) >= 8, (
        "admin matrix too small to detect regressions"
    )

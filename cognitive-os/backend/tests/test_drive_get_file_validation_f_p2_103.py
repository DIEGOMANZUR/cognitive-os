"""Regression tests for F-P2-103.

Schemathesis fuzz hit `GET /actions/drive/files/{file_id}` with a non-ASCII +
control-char file_id (`%C2%B4%16s%C2%BA6`) and the handler returned HTTP 500
because `httpx.InvalidURL` is not a subclass of `httpx.HTTPError` and escaped
the existing `except` clause. Reject malformed Drive IDs at the service layer
so the endpoint returns 400, not 500.

Closes F-P2-103 (P1) from `tmp/v2_02_readonly_execution_20260528_021740/`.
"""

from __future__ import annotations

import httpx
import pytest

from cognitive_os.actions.drive import DriveError, DriveService
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


def test_drive_service_get_file_rejects_non_ascii_id() -> None:
    """Service-level: file_id with non-ASCII bytes is rejected with a
    `DriveError`, NOT a generic exception that would bubble to 500."""
    service = DriveService()
    # ´ (U+00B4) + control \x16 + s + º (U+00BA) + 6 — the exact byte sequence
    # Schemathesis used to surface F-P2-103.
    bad_id = "´\x16sº6"
    with pytest.raises(DriveError) as excinfo:
        service.get_file(bad_id)
    assert "file_id must match" in str(excinfo.value)


@pytest.mark.parametrize(
    "bad_id",
    [
        "\x16abc",  # leading control char
        "ab\x00cd",  # NUL embedded
        "abc def",  # space
        "abc/def",  # slash (would alter path)
        "ácent",  # accented Latin
        "ab​cd",  # zero-width space
        "x" * 250,  # too long
        "",  # empty
    ],
)
def test_drive_service_get_file_rejects_invalid_formats(bad_id: str) -> None:
    """Any file_id that does not match `[A-Za-z0-9_.-]{1,200}` is rejected."""
    service = DriveService()
    with pytest.raises(DriveError):
        service.get_file(bad_id)


@pytest.mark.parametrize(
    "good_id",
    [
        "1A2B3C4D5E6F7G8H9I0J",
        "drive-id_with-dashes_and.dots",
        "Z" * 200,  # max length
        "x",  # 1 char
    ],
)
def test_drive_service_get_file_accepts_valid_format_id_then_status_gates(
    good_id: str,
) -> None:
    """Valid format passes regex but is then gated by Drive readiness (no
    OAuth in test env). The error must mention readiness, NOT validation."""
    service = DriveService()
    with pytest.raises(DriveError) as excinfo:
        service.get_file(good_id)
    detail = str(excinfo.value).lower()
    assert "file_id must" not in detail
    # Realistic blockers (no OAuth in unit-test env):
    assert any(token in detail for token in ("not available", "not configured", "blocked", "drive"))


@pytest.mark.asyncio
async def test_drive_get_file_endpoint_returns_400_for_non_ascii() -> None:
    """End-to-end via FastAPI: the exact Schemathesis case returns 400, not 500."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # %C2%B4%16s%C2%BA6 → decoded by Starlette/FastAPI as "´\x16sº6"
        resp = await client.get(
            "/actions/drive/files/%C2%B4%16s%C2%BA6",
            headers=_headers(),
        )
    assert resp.status_code == 400, (
        f"expected 400 (validation error), got {resp.status_code}: {resp.text[:200]}"
    )
    assert "file_id" in resp.text.lower()


@pytest.mark.asyncio
async def test_drive_get_file_endpoint_returns_4xx_not_5xx_for_garbage() -> None:
    """Any garbage file_id surfaces as 4xx, never 5xx."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for path in [
            "/actions/drive/files/%00",
            "/actions/drive/files/%0A",
            "/actions/drive/files/with%20space",
            "/actions/drive/files/" + "x" * 300,
        ]:
            resp = await client.get(path, headers=_headers())
            assert 400 <= resp.status_code < 500, (
                f"path {path!r}: expected 4xx, got {resp.status_code}: {resp.text[:120]}"
            )

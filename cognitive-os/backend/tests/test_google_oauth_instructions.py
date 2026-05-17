"""Regression: when Google OAuth token is missing, the health detail tells
the operator exactly which command to run."""

from __future__ import annotations

from cognitive_os.core.health import _google_token_instructions


def test_missing_token_detail_gets_actionable_suffix() -> None:
    raw = "No token.json found; run scripts/auth_google.py once."
    enriched = _google_token_instructions(raw)
    assert enriched is not None
    assert "uv run python backend/scripts/auth_google.py" in enriched
    assert "Refresh tokens are renewed automatically" in enriched


def test_unrelated_detail_is_passed_through() -> None:
    assert _google_token_instructions("network unreachable") == "network unreachable"


def test_none_detail_is_passed_through() -> None:
    assert _google_token_instructions(None) is None


def test_auth_google_mention_also_gets_suffix() -> None:
    raw = "Calendar is disabled until auth_google.py runs."
    enriched = _google_token_instructions(raw)
    assert enriched is not None
    assert "uv run python backend/scripts/auth_google.py" in enriched

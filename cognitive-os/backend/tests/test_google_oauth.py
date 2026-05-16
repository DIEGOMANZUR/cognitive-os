from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from cognitive_os.core.google_oauth import (
    GoogleCredentialsLoader,
    GoogleOAuthError,
    redact_google_error,
)


def test_load_raises_when_token_file_missing(tmp_path: Path) -> None:
    loader = GoogleCredentialsLoader(token_path=tmp_path / "token.json")
    with pytest.raises(GoogleOAuthError, match="auth_google.py") as exc_info:
        loader.load()
    assert str(tmp_path) not in str(exc_info.value)
    assert "token.json" not in str(exc_info.value)


def test_load_returns_valid_credentials(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    creds = SimpleNamespace(valid=True, expired=False, refresh_token=None, token="abc123")
    loader = GoogleCredentialsLoader(
        token_path=token_path,
        credentials_loader=lambda _p: creds,
    )
    assert loader.access_token() == "abc123"


def test_load_refreshes_and_persists_expired_token(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    refreshed: list[bool] = []

    class _Creds:
        valid = False
        expired = True
        refresh_token = "refresh-xyz"  # noqa: S105 - test fixture, not a real secret
        token = "old"

        def refresh(self, _request: object) -> None:
            refreshed.append(True)
            self.valid = True
            self.expired = False
            self.token = "new-token"

        def to_json(self) -> str:
            return '{"token": "new-token"}'

    creds = _Creds()
    loader = GoogleCredentialsLoader(
        token_path=token_path,
        credentials_loader=lambda _p: creds,
        request_factory=lambda: object(),
    )
    assert loader.access_token() == "new-token"
    assert refreshed == [True]
    assert "new-token" in token_path.read_text(encoding="utf-8")


def test_load_raises_when_token_invalid(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    creds = SimpleNamespace(valid=False, expired=False, refresh_token=None, token="")
    loader = GoogleCredentialsLoader(
        token_path=token_path,
        credentials_loader=lambda _p: creds,
    )
    with pytest.raises(GoogleOAuthError, match="invalid or missing"):
        loader.load()


def test_redact_google_error_strips_tokens() -> None:
    redacted = redact_google_error("failed bearer ya29.A0ARsecret refresh_token=1//xyz")
    assert "ya29.A0ARsecret" not in redacted
    assert "1//xyz" not in redacted
    assert "[REDACTED]" in redacted

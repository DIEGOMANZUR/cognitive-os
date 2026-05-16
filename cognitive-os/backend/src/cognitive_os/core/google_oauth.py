"""Shared Google OAuth token loading for Calendar and Drive.

The backend deliberately never runs an interactive OAuth flow (it hangs and is
brittle for the operator). Instead, the operator runs `scripts/auth_google.py`
once to produce an authorized-user `token.json`; this loader consumes it,
refreshes it when expired, and persists the refreshed token back to disk.

`google-auth` is lazy-imported inside the default loader so the package stays
importable (and unit-testable with fakes) on hosts that have not installed it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

CredentialsLoaderFn = Callable[[Path], Any]
RequestFactoryFn = Callable[[], Any]

_SECRET_RE = re.compile(
    r"(?i)\b(?:authorization|bearer|access_token|refresh_token|client_secret|token)"
    r"\b\s*[:=]?\s*[A-Za-z0-9._~+/=-]+"
)


class GoogleOAuthError(RuntimeError):
    """Raised when a Google authorized-user token cannot be loaded or refreshed."""


def redact_google_error(value: str) -> str:
    """Strip token-like substrings from any error string before it is surfaced."""
    return _SECRET_RE.sub("[REDACTED]", value)


class GoogleCredentialsLoader:
    """Loads + refreshes a Google `token.json`, shared by the Calendar/Drive providers."""

    def __init__(
        self,
        *,
        token_path: Path,
        credentials_loader: CredentialsLoaderFn | None = None,
        request_factory: RequestFactoryFn | None = None,
    ) -> None:
        self._token_path = token_path
        self._credentials_loader = credentials_loader or self._default_credentials_loader
        self._request_factory = request_factory or self._default_request_factory

    def load(self) -> Any:
        if not self._token_path.exists():
            msg = (
                "Google token is not configured. Run `python scripts/auth_google.py` "
                "once to authorize Calendar/Drive."
            )
            raise GoogleOAuthError(msg)
        credentials = self._credentials_loader(self._token_path)
        if bool(getattr(credentials, "expired", False)) and getattr(
            credentials, "refresh_token", None
        ):
            self._refresh(credentials)
        valid = bool(getattr(credentials, "valid", False)) and bool(
            getattr(credentials, "token", None)
        )
        if not valid:
            msg = (
                "Google token is invalid or missing an access token; re-run scripts/auth_google.py."
            )
            raise GoogleOAuthError(msg)
        return credentials

    def access_token(self) -> str:
        return str(getattr(self.load(), "token", ""))

    def _refresh(self, credentials: Any) -> None:
        try:
            credentials.refresh(self._request_factory())
        except Exception as exc:
            msg = f"Could not refresh Google token: {redact_google_error(str(exc))}"
            raise GoogleOAuthError(msg) from exc
        try:
            self._token_path.write_text(credentials.to_json(), encoding="utf-8")
        except OSError as exc:
            msg = f"Could not persist refreshed Google token: {type(exc).__name__}"
            raise GoogleOAuthError(msg) from exc

    @staticmethod
    def _default_credentials_loader(token_path: Path) -> Any:
        from google.oauth2.credentials import Credentials

        loader = cast(Any, Credentials.from_authorized_user_file)
        return loader(str(token_path))

    @staticmethod
    def _default_request_factory() -> Any:
        from google.auth.transport.requests import Request

        return Request()

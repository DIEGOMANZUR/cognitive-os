#!/usr/bin/env python
"""One-time interactive Google OAuth flow for Calendar + Drive.

Run this once on the operator's machine. It opens a browser, asks the user to
authorize the Cognitive OS "Desktop app" client, and writes an authorized-user
`token.json` into `GOOGLE_TOKEN_DIR`. The backend itself never runs this flow:
it only consumes the resulting token via `core.google_oauth.GoogleCredentialsLoader`.

Usage (from `backend/`):

    uv run python scripts/auth_google.py

Requirements: `google-auth-oauthlib` (install with `uv pip install google-auth-oauthlib`
if it is not already present). GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET must be set
in `.env`.
"""

from __future__ import annotations

import contextlib
import sys

from cognitive_os.core.config import settings


def _existing_token_is_usable(token_path: object) -> bool:
    """Return True iff `token_path` already authorises today's scopes.

    Tries `GoogleCredentialsLoader.load()`, which transparently refreshes the
    access token when the refresh_token is still valid. Failure here is
    expected when the token is missing or scopes have grown — the caller
    falls back to the full interactive flow.
    """
    from pathlib import Path

    from cognitive_os.core.google_oauth import GoogleCredentialsLoader, GoogleOAuthError

    if not Path(token_path).exists():  # type: ignore[arg-type]
        return False
    loader = GoogleCredentialsLoader(token_path=Path(token_path))  # type: ignore[arg-type]
    try:
        loader.load()
    except GoogleOAuthError:
        return False
    except Exception:  # noqa: BLE001 - any import / runtime hiccup -> fall back
        return False
    return True


def main() -> int:
    client_id = settings.google_client_id
    client_secret = settings.google_client_secret.get_secret_value()
    if "CHANGEME" in client_id or "CHANGEME" in client_secret:
        print(
            "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not configured in .env.",
            file=sys.stderr,
        )
        return 1

    token_dir = settings.google_token_dir.expanduser()
    token_path = token_dir / "token.json"

    # Resilience: if the operator already authorised once and the refresh_token
    # is still valid, skip the interactive flow. The GoogleCredentialsLoader
    # transparently refreshes and rewrites token.json. The operator never has
    # to re-authorise just because the short-lived access_token expired.
    if _existing_token_is_usable(token_path):
        print(f"Existing Google token at {token_path} is still valid (auto-refreshed).")
        print("No browser interaction required.")
        return 0

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "google-auth-oauthlib is not installed. Run:\n"
            "    uv pip install google-auth-oauthlib google-auth",
            file=sys.stderr,
        )
        return 1

    scopes = sorted(
        {
            *settings.google_calendar_scopes,
            *settings.google_drive_scopes,
        }
    )
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    print("Requesting Google authorization for scopes:\n  " + "\n  ".join(scopes))
    flow = InstalledAppFlow.from_client_config(client_config, scopes)
    credentials = flow.run_local_server(port=0)

    token_dir.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    with contextlib.suppress(OSError):
        token_path.chmod(0o600)
    print(f"\nAuthorized. Token written to {token_path}")
    print(
        "Calendar/Drive are now usable once ENABLE_GOOGLE_CALENDAR / ENABLE_GOOGLE_DRIVE are true."
    )
    print(
        "Reminder: access tokens are short-lived but the refresh_token saved in "
        "this file lets the backend refresh them transparently."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

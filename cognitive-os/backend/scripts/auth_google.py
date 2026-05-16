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


def main() -> int:
    client_id = settings.google_client_id
    client_secret = settings.google_client_secret.get_secret_value()
    if "CHANGEME" in client_id or "CHANGEME" in client_secret:
        print(
            "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not configured in .env.",
            file=sys.stderr,
        )
        return 1

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

    token_dir = settings.google_token_dir.expanduser()
    token_dir.mkdir(parents=True, exist_ok=True)
    token_path = token_dir / "token.json"
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    with contextlib.suppress(OSError):
        token_path.chmod(0o600)
    print(f"\nAuthorized. Token written to {token_path}")
    print(
        "Calendar/Drive are now usable once ENABLE_GOOGLE_CALENDAR / ENABLE_GOOGLE_DRIVE are true."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

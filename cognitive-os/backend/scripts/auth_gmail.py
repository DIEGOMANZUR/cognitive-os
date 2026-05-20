#!/usr/bin/env python
"""One-time interactive Gmail OAuth flow (read-only digest lane).

Run this once on the operator's machine. It opens a browser, asks the user to
authorize the Cognitive OS Gmail "Desktop app" client, and writes an authorized-user
`token.json` into `GMAIL_TOKEN_DIR`. The backend itself never runs this flow:
the digest reads the resulting token via `actions/gmail_digest.py` and
`mail/service.py`. Gmail runs on its own OAuth lane separate from Calendar/Drive
(distinct scopes, distinct `token.json`) so revoking one does not break the other.

Usage (from `backend/`):

    uv run python scripts/auth_gmail.py

Requirements: `google-auth-oauthlib` (install with
`uv pip install google-auth-oauthlib` if it is not already present).
GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET must be set in `.env`.
"""

from __future__ import annotations

import contextlib
import sys

from cognitive_os.core.config import settings


def _existing_token_is_usable(token_path: object, required_scopes: list[str]) -> bool:
    """Return True iff `token_path` already authorises today's gmail_scopes.

    Diffs granted vs `required_scopes` so changing GMAIL_SCOPES in .env forces
    re-consent instead of leaving Gmail digest silently misconfigured.
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
    missing = loader.missing_scopes(required_scopes)
    if missing:
        print(
            "Existing Gmail token is missing scopes now configured in .env:\n  "
            + "\n  ".join(missing)
            + "\nFalling back to the interactive flow to re-consent.",
            file=sys.stderr,
        )
        return False
    return True


def main() -> int:
    client_id = settings.gmail_client_id
    client_secret = settings.gmail_client_secret.get_secret_value()
    if "CHANGEME" in client_id or "CHANGEME" in client_secret:
        print(
            "GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET are not configured in .env.",
            file=sys.stderr,
        )
        return 1

    token_dir = settings.gmail_token_dir.expanduser()
    token_path = token_dir / "token.json"
    scopes = sorted(set(settings.gmail_scopes))

    if _existing_token_is_usable(token_path, scopes):
        print(f"Existing Gmail token at {token_path} is still valid (auto-refreshed).")
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
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    print("Requesting Gmail authorization for scopes:\n  " + "\n  ".join(scopes))
    flow = InstalledAppFlow.from_client_config(client_config, scopes)
    credentials = flow.run_local_server(port=0)

    token_dir.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    with contextlib.suppress(OSError):
        token_path.chmod(0o600)
    print(f"\nAuthorized. Token written to {token_path}")
    print("Gmail is now usable once GMAIL_READ_ENABLED=true (digest / label TODOS).")
    print(
        "Reminder: access tokens are short-lived but the refresh_token saved in "
        "this file lets the backend refresh them transparently."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

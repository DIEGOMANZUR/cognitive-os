"""Live smoke: the Telegram bot token is valid (AUDIT-2026-E).

Read-only: a single `getMe` call. `getMe` never sends a message, never polls
updates — it just confirms the token authenticates. The token itself is never
written to an assertion message or log.
"""

from __future__ import annotations

import httpx
import pytest

from cognitive_os.core.config import settings

pytestmark = pytest.mark.live_readonly


def test_live_telegram_get_me() -> None:
    token = settings.telegram_bot_token.get_secret_value().strip()
    if not token or token == "CHANGEME":
        pytest.skip("TELEGRAM_BOT_TOKEN not configured")

    response = httpx.get(
        f"https://api.telegram.org/bot{token}/getMe",
        timeout=settings.http_timeout_seconds,
    )

    # Never include the URL (it carries the token) in the failure message.
    assert response.status_code == 200, (
        f"Telegram getMe returned HTTP {response.status_code} — token invalid?"
    )
    payload = response.json()
    assert payload.get("ok") is True
    assert payload.get("result", {}).get("is_bot") is True

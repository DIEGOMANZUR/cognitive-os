from __future__ import annotations

import httpx
import pytest

from cognitive_os.actions.gmail_digest import render_gmail_digest_telegram
from cognitive_os.actions.schemas import GmailDigestPreview
from cognitive_os.api.app import app
from cognitive_os.assist.telegram_routing import telegram_chat_ids_for_owner
from cognitive_os.assist.telegram_user import api_user_for_telegram_chat
from cognitive_os.core.config import Settings


@pytest.mark.asyncio
async def test_assist_requires_auth_before_db_failure() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        tasks_resp = await client.get("/assist/tasks")
        notes_resp = await client.post("/assist/notes", json={"title": "x", "body_markdown": "y"})
    assert tasks_resp.status_code == 401
    assert notes_resp.status_code == 401


def test_telegram_assist_user_map_resolves_via_settings_construct() -> None:
    cfg = Settings.model_construct(telegram_assist_user_map=["424242:operator-9"])
    assert api_user_for_telegram_chat(424242, cfg) == "operator-9"
    assert api_user_for_telegram_chat(111, cfg) == "telegram:111"


def test_reminder_chat_map_owner_and_telegram_prefix() -> None:
    cfg = Settings.model_construct(
        telegram_reminder_chat_map=[
            "myuser:303,304",
        ],
    )
    assert telegram_chat_ids_for_owner("myuser", cfg) == [303, 304]
    bare = Settings.model_construct(telegram_reminder_chat_map=[])
    assert telegram_chat_ids_for_owner("telegram:777", bare) == [777]


def test_render_gmail_digest_telegram_blocked_reason() -> None:
    rendered = render_gmail_digest_telegram(
        GmailDigestPreview(status="blocked", lookback_hours=2, max_messages=3, reason="sin token"),
    )
    assert "blocked" in rendered.lower()
    assert "sin token" in rendered

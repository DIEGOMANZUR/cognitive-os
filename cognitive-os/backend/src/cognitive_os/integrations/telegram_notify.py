from __future__ import annotations

import logging

import httpx

from cognitive_os.core.config import settings

logger = logging.getLogger(__name__)
_CHAR_LIMIT = 4000


def send_telegram_markdown(chat_id: int, text: str, *, timeout_seconds: float = 12.0) -> None:
    """Best-effort send; logs warnings on failures (used by Celery ticks)."""
    if not settings.telegram_enabled:
        return
    raw = settings.telegram_bot_token.get_secret_value().strip()
    if not raw or raw == "CHANGEME":
        logger.warning("telegram_notify_missing_token chat_id=%s", chat_id)
        return
    url = f"https://api.telegram.org/bot{raw}/sendMessage"
    body: dict[str, object] = {
        "chat_id": chat_id,
        "text": text[:_CHAR_LIMIT],
        "parse_mode": "Markdown",
    }
    try:
        response = httpx.post(url, json=body, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            logger.warning("telegram_notify_api_not_ok chat_id=%s payload=%s", chat_id, payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("telegram_notify_failed chat_id=%s exc=%s", chat_id, exc)

from __future__ import annotations

from cognitive_os.core.config import Settings, settings


def api_user_for_telegram_chat(telegram_chat_id: int, app_settings: Settings = settings) -> str:
    """Map Telegram actor to API `user_id` for personal Tasks/Notes.

    Configure `TELEGRAM_ASSIST_USER_MAP` CSV entries formatted as `{chat_id}:{api_user_id}`.
    If no mapping hits, scopes data under ``telegram:<chat_id>`` so multiples cuentas
    no choquearan por defecto.
    """
    key = str(telegram_chat_id)
    for entry in app_settings.telegram_assist_user_map:
        stripped = entry.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lhs, sep, rhs = stripped.partition(":")
        if sep and lhs.strip() == key:
            mapped = rhs.strip()
            return mapped if mapped else f"telegram:{telegram_chat_id}"
    return f"telegram:{telegram_chat_id}"

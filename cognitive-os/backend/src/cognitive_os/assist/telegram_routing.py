from __future__ import annotations

from cognitive_os.core.config import Settings, settings


def telegram_chat_ids_for_owner(api_user_id: str, app_settings: Settings = settings) -> list[int]:
    """Resolve which Telegram chats should receive pings for `api_user_id`."""
    direct: list[int] = []
    stripped = api_user_id.strip()
    prefix = "telegram:"
    if stripped.startswith(prefix):
        suffix = stripped[len(prefix) :].strip()
        try:
            direct.append(int(suffix))
        except ValueError:
            return []

    chats: dict[str, list[int]] = {}
    for entry in app_settings.telegram_reminder_chat_map:
        row = entry.strip()
        if not row or row.startswith("#"):
            continue
        lhs, sep, rhs = row.partition(":")
        if not sep:
            continue
        owner_key = lhs.strip()
        rhs_stripped = rhs.strip()
        raw_ids = rhs_stripped.replace(",", " ").split()
        for token in raw_ids:
            try:
                cid = int(token)
            except ValueError:
                continue
            chats.setdefault(owner_key, []).append(cid)

    return sorted({*direct, *chats.get(stripped, ())})

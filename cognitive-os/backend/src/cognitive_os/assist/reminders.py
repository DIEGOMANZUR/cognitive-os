from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, select

from cognitive_os.assist.telegram_routing import telegram_chat_ids_for_owner
from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import PersonalTask
from cognitive_os.integrations.telegram_notify import send_telegram_markdown


async def deliver_personal_task_reminders(app_settings: Settings = settings) -> dict[str, Any]:
    """Send one-shot Telegram pings for overdue `remind_at` rows."""
    skipped: dict[str, Any] = {}
    if not app_settings.telegram_enabled:
        skipped["reason"] = "telegram_disabled"
        return {"skipped": True, **skipped}
    if not app_settings.enable_personal_reminder_delivery:
        skipped["reason"] = "reminder_delivery_disabled"
        return {"skipped": True, **skipped}
    if not app_settings.enable_personal_assistant_api:
        skipped["reason"] = "personal_assistant_api_disabled"
        return {"skipped": True, **skipped}

    now = datetime.now(tz=UTC)
    notified = 0
    stmt: Select[tuple[PersonalTask]] = (
        select(PersonalTask)
        .where(PersonalTask.remind_at.isnot(None))
        .where(PersonalTask.remind_at <= now)
        .where(PersonalTask.status.in_(("pending", "in_progress")))
    )
    async with session_scope() as session:
        rows = list((await session.execute(stmt)).scalars().all())
        examined = len(rows)
        for row in rows:
            meta = dict(row.metadata_json or {})
            finger = ""
            if row.remind_at is not None:
                finger = row.remind_at.isoformat().replace("+00:00", "Z")
            if meta.get("reminder_sent_for") == finger:
                continue
            targets = telegram_chat_ids_for_owner(row.user_id, app_settings)
            if not targets:
                continue
            headline = row.title.strip() or "(sin titulo)"
            due = ""
            if row.due_at is not None:
                due = row.due_at.strftime("%Y-%m-%d %H:%MZ")
            chunk = f"*{headline[:120]}*\ntask `{str(row.id)[:8]}…` · prio `{row.priority}`\n"
            if due:
                chunk += f"*due*: `{due}`\n"
            if row.description:
                chunk += row.description.strip()[:500] + "\n"
            for chat_id in targets:
                send_telegram_markdown(chat_id, f"Reminder personal\n\n{chunk}")
                notified += 1
            meta["reminder_sent_for"] = finger
            meta["last_reminder_at"] = now.isoformat()
            row.metadata_json = meta
            session.add(row)
    return {"notified_attempts": notified, "examined": examined}

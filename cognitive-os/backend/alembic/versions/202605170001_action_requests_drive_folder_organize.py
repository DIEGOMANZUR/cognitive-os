"""Allow drive_ensure_folder and drive_organize_files action types.

The application code (services, REST endpoints, frontend types and Telegram
handlers) already creates ``ActionRequest`` rows with these two action types
since Fases 47-49 (Drive ensure-folder + organize). The CHECK constraint on
``action_requests.action_type`` was never widened, so in Postgres the INSERT
fails with ``CheckViolation`` and the operator sees a 500. Tests masked the
bug because they monkeypatch the session, never round-tripping to a real DB.

This migration drops and re-creates ``ck_ar_action_type`` to include both new
types. ORM ``__table_args__`` mirror the same set so model-derived autogenerate
no longer diverges from the DB.

Revision ID: 202605170001
Revises: 202605160002
Create Date: 2026-05-17 10:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "202605170001"
down_revision: str | None = "202605160002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_NEW_VALUES = (
    "'computer_organize', 'browser_navigation', 'gmail_query', "
    "'godaddy_dns_change', 'document_generate', 'browser_preview', "
    "'browser_interactive', 'calendar_create_event', 'drive_upload_file', "
    "'drive_ensure_folder', 'drive_organize_files'"
)
_OLD_VALUES = (
    "'computer_organize', 'browser_navigation', 'gmail_query', "
    "'godaddy_dns_change', 'document_generate', 'browser_preview', "
    "'browser_interactive', 'calendar_create_event', 'drive_upload_file'"
)


def upgrade() -> None:
    op.drop_constraint("ck_ar_action_type", "action_requests", type_="check")
    op.create_check_constraint(
        "ck_ar_action_type",
        "action_requests",
        f"action_type IN ({_NEW_VALUES})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ar_action_type", "action_requests", type_="check")
    op.create_check_constraint(
        "ck_ar_action_type",
        "action_requests",
        f"action_type IN ({_OLD_VALUES})",
    )

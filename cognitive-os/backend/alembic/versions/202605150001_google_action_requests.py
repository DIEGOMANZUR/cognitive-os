"""Allow Google Calendar and Drive action requests.

Revision ID: 202605150001
Revises: 202605140001
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "202605150001"
down_revision: str | None = "202605140001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_NEW_VALUES = (
    "'computer_organize', 'browser_navigation', 'gmail_query', "
    "'godaddy_dns_change', 'document_generate', 'browser_preview', "
    "'browser_interactive', 'calendar_create_event', 'drive_upload_file'"
)
_OLD_VALUES = (
    "'computer_organize', 'browser_navigation', 'gmail_query', "
    "'godaddy_dns_change', 'document_generate', 'browser_preview', "
    "'browser_interactive'"
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

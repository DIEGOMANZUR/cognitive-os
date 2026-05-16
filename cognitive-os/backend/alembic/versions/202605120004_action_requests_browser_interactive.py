"""Extend action_requests.action_type allow-list with browser_interactive.

Revision ID: 202605120004
Revises: 202605120003
Create Date: 2026-05-12 00:00:04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from cognitive_os.migrations.action_request_checks import (
    ACTION_TYPE_CHECK_NAME,
    replace_action_type_check,
)

revision: str = "202605120004"
down_revision: str | None = "202605120003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OLD = (
    "action_type IN ("
    "'computer_organize', 'browser_navigation', 'gmail_query', "
    "'godaddy_dns_change', 'document_generate', 'browser_preview'"
    ")"
)
_NEW = (
    "action_type IN ("
    "'computer_organize', 'browser_navigation', 'gmail_query', "
    "'godaddy_dns_change', 'document_generate', 'browser_preview', "
    "'browser_interactive'"
    ")"
)


def upgrade() -> None:
    replace_action_type_check(_NEW)


def downgrade() -> None:
    op.drop_constraint(ACTION_TYPE_CHECK_NAME, "action_requests", type_="check")
    op.create_check_constraint(ACTION_TYPE_CHECK_NAME, "action_requests", _OLD)

"""extend action_requests.action_type allow-list with document_generate

Revision ID: 202605120001
Revises: 202604300005
Create Date: 2026-05-12 00:00:01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from cognitive_os.migrations.action_request_checks import (
    ACTION_TYPE_CHECK_NAME,
    replace_action_type_check,
)

revision: str = "202605120001"
down_revision: str | None = "202604300005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OLD = (
    "action_type IN ("
    "'computer_organize', 'browser_navigation', 'gmail_query', 'godaddy_dns_change'"
    ")"
)
_NEW = (
    "action_type IN ("
    "'computer_organize', 'browser_navigation', 'gmail_query', "
    "'godaddy_dns_change', 'document_generate'"
    ")"
)


def upgrade() -> None:
    replace_action_type_check(_NEW)


def downgrade() -> None:
    op.drop_constraint(ACTION_TYPE_CHECK_NAME, "action_requests", type_="check")
    op.create_check_constraint(ACTION_TYPE_CHECK_NAME, "action_requests", _OLD)

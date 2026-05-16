"""sensitive tool approvals

Revision ID: 202604300003
Revises: 202604300002
Create Date: 2026-04-30 00:00:03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604300003"
down_revision: str | None = "202604300002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "human_approvals",
        sa.Column("requested_action", sa.String(length=200), server_default="", nullable=False),
    )
    op.add_column(
        "human_approvals",
        sa.Column(
            "args_redacted",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "human_approvals",
        sa.Column("approver_user_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "human_approvals",
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE human_approvals SET status = 'pending' WHERE status = 'active'")
    op.create_check_constraint(
        "human_approvals_status_allowed",
        "human_approvals",
        "status IN ('pending', 'approved', 'rejected', 'edited', 'expired')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "human_approvals_status_allowed",
        "human_approvals",
        type_="check",
    )
    op.drop_column("human_approvals", "decided_at")
    op.drop_column("human_approvals", "approver_user_id")
    op.drop_column("human_approvals", "args_redacted")
    op.drop_column("human_approvals", "requested_action")

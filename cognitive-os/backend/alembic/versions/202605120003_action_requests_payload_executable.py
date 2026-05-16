"""Add action_requests.payload_executable to separate execution payload from audit redaction.

Revision ID: 202605120003
Revises: 202605120002
Create Date: 2026-05-12 00:00:03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202605120003"
down_revision: str | None = "202605120002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "action_requests",
        sa.Column(
            "payload_executable",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("action_requests", "payload_executable")

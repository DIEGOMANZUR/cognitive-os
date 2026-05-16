"""human_approvals status/created_at composite index

Adds `ix_human_approvals_status_created_at(status, created_at)` so that the
approvals dashboard listing (`status='pending' ORDER BY created_at DESC`) and
the reaper (`status='pending' AND created_at < cutoff`) both run as bounded
index scans even when the table grows.

Revision ID: 202605160002
Revises: 202605160001
Create Date: 2026-05-16 00:00:02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "202605160002"
down_revision: str | None = "202605160001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_NAME = "ix_human_approvals_status_created_at"


def upgrade() -> None:
    op.create_index(
        _INDEX_NAME,
        "human_approvals",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="human_approvals")

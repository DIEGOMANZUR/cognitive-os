"""personal_tasks + personal_notes for assistant workspace

Revision ID: 202605120006
Revises: 202605120005
Create Date: 2026-05-12 00:00:06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202605120006"
down_revision: str | None = "202605120005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "personal_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="3", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'done', 'cancelled')",
            name="personal_tasks_status_allowed",
        ),
        sa.CheckConstraint("priority >= 1 AND priority <= 5", name="personal_tasks_priority_range"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personal_tasks_user_status", "personal_tasks", ["user_id", "status"])
    op.create_index(
        "ix_personal_tasks_remind_at_partial",
        "personal_tasks",
        ["remind_at"],
        postgresql_where=sa.text("remind_at IS NOT NULL"),
    )

    op.create_table(
        "personal_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=400), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personal_notes_user_updated", "personal_notes", ["user_id", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_personal_notes_user_updated", table_name="personal_notes")
    op.drop_table("personal_notes")
    op.drop_index("ix_personal_tasks_remind_at_partial", table_name="personal_tasks")
    op.drop_index("ix_personal_tasks_user_status", table_name="personal_tasks")
    op.drop_table("personal_tasks")

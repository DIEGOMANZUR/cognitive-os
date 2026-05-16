"""action requests

Revision ID: 202604300005
Revises: 202604300004
Create Date: 2026-04-30 00:00:05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604300005"
down_revision: str | None = "202604300004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_requests",
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=True),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column(
            "payload_redacted",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "preview",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
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
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "action_type IN ("
            "'computer_organize', 'browser_navigation', 'gmail_query', 'godaddy_dns_change'"
            ")",
            name=op.f("ck_action_requests_action_requests_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ("
            "'previewed', 'blocked', 'pending_approval', 'queued', 'running', "
            "'completed', 'failed', 'rejected', 'cancelled'"
            ")",
            name=op.f("ck_action_requests_action_requests_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["human_approvals.id"],
            name=op.f("fk_action_requests_approval_id_human_approvals"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_action_requests_job_id_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_action_requests")),
    )
    op.create_index(
        "ix_action_requests_action_type",
        "action_requests",
        ["action_type"],
    )
    op.create_index(
        "ix_action_requests_status_created_at",
        "action_requests",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_action_requests_status_created_at", table_name="action_requests")
    op.drop_index("ix_action_requests_action_type", table_name="action_requests")
    op.drop_table("action_requests")

"""Persist Research Orchestrator run snapshots.

Revision ID: 202605150002
Revises: 202605150001
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202605150002"
down_revision: str | None = "202605150001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_runs",
        sa.Column("run_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("thread_id", sa.String(length=128), nullable=True),
        sa.Column(
            "request",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "subtasks",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "results",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("synthesis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("score", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "events",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ("
            "'queued', 'planning', 'researching', 'synthesizing', 'scoring', "
            "'completed', 'cancelled', 'failed', 'blocked'"
            ")",
            name=op.f("ck_research_runs_research_runs_status_allowed"),
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_research_runs")),
    )
    op.create_index(
        "ix_research_runs_status_created_at",
        "research_runs",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_research_runs_user_created_at",
        "research_runs",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_runs_user_created_at", table_name="research_runs")
    op.drop_index("ix_research_runs_status_created_at", table_name="research_runs")
    op.drop_table("research_runs")

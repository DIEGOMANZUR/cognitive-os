"""deepagents skills memory

Revision ID: 202604300004
Revises: 202604300003
Create Date: 2026-04-30 00:00:04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604300004"
down_revision: str | None = "202604300003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deepagent_memory_records",
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("case_id", sa.String(length=128), nullable=True),
        sa.Column("thread_id", sa.String(length=128), nullable=True),
        sa.Column("agent_name", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("content_redacted", sa.Text(), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("sensitivity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "scope IN ('global', 'user', 'case', 'thread', 'agent')",
            name="deepagent_memory_scope_allowed",
        ),
        sa.CheckConstraint(
            "kind IN ('preference', 'procedure', 'lesson', 'warning', 'fact', 'style', "
            "'tool_feedback')",
            name="deepagent_memory_kind_allowed",
        ),
        sa.CheckConstraint(
            "source IN ('human', 'agent_proposed', 'consolidated', 'system')",
            name="deepagent_memory_source_allowed",
        ),
        sa.CheckConstraint(
            "sensitivity IN ('public', 'internal', 'sensitive', 'secret')",
            name="deepagent_memory_sensitivity_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'pending_approval', 'rejected', 'archived')",
            name="deepagent_memory_status_allowed",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="deepagent_memory_confidence",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "deepagent_memory_proposals",
        sa.Column("proposed_by_agent", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("proposed_content_redacted", sa.Text(), nullable=False),
        sa.Column("proposed_content_ref", sa.Text(), nullable=True),
        sa.Column("sensitivity", sa.String(length=32), nullable=False),
        sa.Column("source_task_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "scope IN ('global', 'user', 'case', 'thread', 'agent')",
            name="deepagent_memory_proposal_scope_allowed",
        ),
        sa.CheckConstraint(
            "sensitivity IN ('public', 'internal', 'sensitive', 'secret')",
            name="deepagent_memory_proposal_sensitivity_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'applied')",
            name="deepagent_memory_proposal_status_allowed",
        ),
        sa.ForeignKeyConstraint(["approval_id"], ["human_approvals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "deepagent_skill_usage",
        sa.Column("skill_name", sa.String(length=128), nullable=False),
        sa.Column("agent_name", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=True),
        sa.Column("thread_id", sa.String(length=128), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("deepagent_skill_usage")
    op.drop_table("deepagent_memory_proposals")
    op.drop_table("deepagent_memory_records")

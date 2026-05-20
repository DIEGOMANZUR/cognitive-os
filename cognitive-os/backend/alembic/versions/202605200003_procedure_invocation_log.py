"""Add ``procedure_invocation_log`` table for Fase 80 (Fase B of the
agent learning plan — skill promotion).

The skill promoter (see ``deepagents/skill_promoter.py``) tracks each
time a ``kind=procedure`` memory record is referenced by an agent, then
later flags the row with the job outcome (success / failure / partial)
so the promoter can decide when to propose lifting the procedure to a
first-class YAML skill.

We log invocations even before the job finishes because the prompt
inclusion happens at agent build time, hours before the final outcome
is known. The promoter joins the log against ``jobs`` to fill in the
outcome when it sweeps.

Revision ID: 202605200003
Revises: 202605200002
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605200003"
down_revision: str | None = "202605200002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "procedure_invocation_log",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("thread_id", sa.String(length=128), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("agent_name", sa.String(length=128), nullable=True),
        sa.Column(
            "invoked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "metadata_json",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_procedure_invocation_log"),
        sa.CheckConstraint(
            "outcome IN ('pending','success','failure','partial')",
            name="ck_procedure_invocation_log_outcome",
        ),
    )
    op.create_index(
        "ix_procedure_invocation_log_memory_outcome",
        "procedure_invocation_log",
        ["memory_id", "outcome"],
    )
    op.create_index(
        "ix_procedure_invocation_log_job",
        "procedure_invocation_log",
        ["job_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_procedure_invocation_log_job",
        table_name="procedure_invocation_log",
    )
    op.drop_index(
        "ix_procedure_invocation_log_memory_outcome",
        table_name="procedure_invocation_log",
    )
    op.drop_table("procedure_invocation_log")

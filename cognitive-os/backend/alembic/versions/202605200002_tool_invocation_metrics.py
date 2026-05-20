"""Add ``tool_invocation_metrics`` table for Fase 79.4 (Fase C of the
agent learning plan).

The daily scorecard aggregator (see ``deepagents/tool_scorecard.py``)
counts ``tool_invoked / tool_succeeded / tool_failed`` events per
(agent_role, tool_name, day) and writes the rollup here. We do NOT
update this table from the hot path — the aggregator is a maintenance
task with idempotent UPSERT semantics. The hot path stays write-heavy
to ``job_events``; the scorecard only reads.

Why a dedicated table instead of computing on-the-fly:
* Querying ``job_events`` GROUP BY (tool, day) every time the UI loads
  the scorecard tab gets slow once we cross ~50k events. With the
  rollup table the UI does a single index scan over ~N_tools rows.
* The reliability score (0.5*success_rate + 0.3*downstream_use_rate +
  0.2*approve_rate) depends on downstream signals (was the tool result
  cited in the answer? did the operator approve the ActionRequest?)
  that we need to compute and persist alongside the raw counts.

Revision ID: 202605200002
Revises: 202605200001
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605200002"
down_revision: str | None = "202605200001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_invocation_metrics",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_role", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invoke_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("downstream_use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_approve_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_reject_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_tool_invocation_metrics"),
        sa.UniqueConstraint(
            "agent_role",
            "tool_name",
            "period_start",
            name="uq_tool_invocation_metrics_role_tool_period",
        ),
        sa.CheckConstraint(
            "invoke_count >= 0 AND success_count >= 0 AND failure_count >= 0 "
            "AND downstream_use_count >= 0 AND user_approve_count >= 0 "
            "AND user_reject_count >= 0",
            name="ck_tool_invocation_metrics_counts_non_negative",
        ),
    )
    # The UI sorts by reliability descending; the aggregator upserts by
    # (role, tool, period). Index both access paths.
    op.create_index(
        "ix_tool_invocation_metrics_period_role",
        "tool_invocation_metrics",
        ["period_start", "agent_role"],
    )
    op.create_index(
        "ix_tool_invocation_metrics_reliability",
        "tool_invocation_metrics",
        [sa.text("reliability_score DESC NULLS LAST")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tool_invocation_metrics_reliability",
        table_name="tool_invocation_metrics",
    )
    op.drop_index(
        "ix_tool_invocation_metrics_period_role",
        table_name="tool_invocation_metrics",
    )
    op.drop_table("tool_invocation_metrics")

"""Add ``jobs.extracted_recipe_at`` for the recipe extractor (Fase 78).

Fase 78 (Fase A of the agent learning plan) introduces a Celery beat task
that scans successful long-running jobs and distils a reusable procedure
into a ``DeepAgentMemoryProposal(kind="procedure")``. The extractor needs
an idempotency marker so a 30-minute beat cycle does not re-process the
same job over and over. We add a nullable column to ``jobs``: NULL means
"pending extraction", a timestamp means "already processed" (whether the
LLM produced a proposal, skipped it, or the row was force-marked by the
operator).

The column is indexed because the beat task filters on
``extracted_recipe_at IS NULL`` every 30 minutes and ``jobs`` is one of
the hottest tables.

Revision ID: 202605200001
Revises: 202605170001
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202605200001"
down_revision: str | None = "202605170001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "extracted_recipe_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "Fase 78: timestamp at which the recipe extractor processed this "
                "job. NULL = pending. Set to NOW() even when the LLM emitted a "
                "skip signal (no proposal) so the beat does not loop forever."
            ),
        ),
    )
    op.create_index(
        "ix_jobs_extracted_recipe_at",
        "jobs",
        ["extracted_recipe_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_extracted_recipe_at", table_name="jobs")
    op.drop_column("jobs", "extracted_recipe_at")

"""document ingestion traceability

Revision ID: 202604300002
Revises: 202604300001
Create Date: 2026-04-30 00:00:02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604300002"
down_revision: str | None = "202604300001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_pages",
        sa.Column(
            "extraction_method",
            sa.String(length=32),
            server_default="native_pdf",
            nullable=False,
        ),
    )
    op.add_column("document_pages", sa.Column("confidence_score", sa.Integer(), nullable=True))
    op.add_column(
        "document_pages",
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "document_chunks",
        sa.Column("page_start", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "document_chunks",
        sa.Column("page_end", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "document_chunks",
        sa.Column("source_path", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "document_chunks",
        sa.Column("doc_type", sa.String(length=64), server_default="pdf", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "doc_type")
    op.drop_column("document_chunks", "source_path")
    op.drop_column("document_chunks", "page_end")
    op.drop_column("document_chunks", "page_start")
    op.drop_column("document_pages", "warnings")
    op.drop_column("document_pages", "confidence_score")
    op.drop_column("document_pages", "extraction_method")

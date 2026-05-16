"""initial operational schema

Revision ID: 202604300001
Revises:
Create Date: 2026-04-30 00:00:01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604300001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def common_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        *common_columns(),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.CheckConstraint("status <> ''", name=op.f("ck_users_status_not_empty")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("external_id", name="uq_users_external_id"),
    )

    op.create_table(
        "conversation_threads",
        *common_columns(),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.CheckConstraint("status <> ''", name=op.f("ck_conversation_threads_status_not_empty")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_conversation_threads_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_threads")),
    )

    op.create_table(
        "documents",
        *common_columns(),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.CheckConstraint("length(sha256) = 64", name=op.f("ck_documents_sha256_length")),
        sa.CheckConstraint("status <> ''", name=op.f("ck_documents_status_not_empty")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("sha256", "source_path", name="uq_documents_sha256_source_path"),
    )
    op.create_index(op.f("ix_documents_sha256"), "documents", ["sha256"], unique=False)

    op.create_table(
        "audit_events",
        *common_columns(),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("action", sa.String(length=200), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.CheckConstraint("status <> ''", name=op.f("ck_audit_events_status_not_empty")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )

    op.create_table(
        "document_pages",
        *common_columns(),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.CheckConstraint("page_number > 0", name=op.f("ck_document_pages_page_number_positive")),
        sa.CheckConstraint("status <> ''", name=op.f("ck_document_pages_status_not_empty")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_pages_document_id_documents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_pages")),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_pages_document_page"),
    )

    op.create_table(
        "jobs",
        *common_columns(),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name=op.f("ck_jobs_progress_range"),
        ),
        sa.CheckConstraint("status <> ''", name=op.f("ck_jobs_status_not_empty")),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["conversation_threads.id"],
            name=op.f("fk_jobs_thread_id_conversation_threads"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )

    op.create_table(
        "document_chunks",
        *common_columns(),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_id", sa.String(length=128), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name=op.f("ck_document_chunks_chunk_index_non_negative"),
        ),
        sa.CheckConstraint("status <> ''", name=op.f("ck_document_chunks_status_not_empty")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_chunks_document_id_documents"),
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["document_pages.id"],
            name=op.f("fk_document_chunks_page_id_document_pages"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
        sa.UniqueConstraint("document_id", "chunk_id", name="uq_document_chunks_document_chunk_id"),
    )

    op.create_table(
        "job_events",
        *common_columns(),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.CheckConstraint("status <> ''", name=op.f("ck_job_events_status_not_empty")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_job_events_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_events")),
    )

    op.create_table(
        "human_approvals",
        *common_columns(),
        sa.Column("action", sa.String(length=200), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=True),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("thread_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("status <> ''", name=op.f("ck_human_approvals_status_not_empty")),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_human_approvals_job_id_jobs"),
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["conversation_threads.id"],
            name=op.f("fk_human_approvals_thread_id_conversation_threads"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_human_approvals")),
    )


def downgrade() -> None:
    op.drop_table("human_approvals")
    op.drop_table("job_events")
    op.drop_table("document_chunks")
    op.drop_table("jobs")
    op.drop_table("document_pages")
    op.drop_table("audit_events")
    op.drop_index(op.f("ix_documents_sha256"), table_name="documents")
    op.drop_table("documents")
    op.drop_table("conversation_threads")
    op.drop_table("users")

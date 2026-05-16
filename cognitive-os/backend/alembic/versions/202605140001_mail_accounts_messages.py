"""mail accounts, messages and send logs

Revision ID: 202605140001
Revises: 202605120006
Create Date: 2026-05-14 00:00:01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202605140001"
down_revision: str | None = "202605120006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mail_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("email_address", sa.String(length=320), nullable=False),
        sa.Column("username", sa.String(length=320), nullable=True),
        sa.Column("imap_host", sa.String(length=255), nullable=True),
        sa.Column("imap_port", sa.Integer(), nullable=True),
        sa.Column("smtp_host", sa.String(length=255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=True),
        sa.Column(
            "monitor_folders",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("send_capable", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_default_sender", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.CheckConstraint("kind IN ('imap', 'gmail_oauth')", name="mail_accounts_kind_allowed"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_address", name="uq_mail_accounts_email_address"),
        sa.UniqueConstraint("label", name="uq_mail_accounts_label"),
    )

    op.create_table(
        "mail_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("folder", sa.String(length=255), nullable=False),
        sa.Column("uid", sa.String(length=128), nullable=False),
        sa.Column("message_id_header", sa.Text(), nullable=True),
        sa.Column("thread_key", sa.String(length=256), nullable=True),
        sa.Column("sender", sa.String(length=500), nullable=False),
        sa.Column(
            "recipients",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("classification", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("importance_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("proposed_reply_text", sa.Text(), nullable=True),
        sa.Column("proposed_reply_rationale", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="new", nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "classification IN ('important', 'normal', 'spam', 'promo', 'unknown')",
            name="mail_messages_classification_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('new', 'reply_proposed', 'pending_send', 'sent', 'ignored', 'failed')",
            name="mail_messages_status_allowed",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["mail_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "folder", "uid", name="uq_mail_messages_account_folder_uid"
        ),
    )
    op.create_index("ix_mail_messages_account_folder", "mail_messages", ["account_id", "folder"])
    op.create_index("ix_mail_messages_importance", "mail_messages", ["importance_score"])
    op.create_index("ix_mail_messages_status_received", "mail_messages", ["status", "received_at"])
    op.create_index("ix_mail_messages_thread_key", "mail_messages", ["thread_key"])

    op.create_table(
        "mail_send_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column(
            "to_addresses",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed')", name="mail_send_logs_status_allowed"
        ),
        sa.ForeignKeyConstraint(["account_id"], ["mail_accounts.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["mail_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mail_send_logs_message_status", "mail_send_logs", ["message_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_mail_send_logs_message_status", table_name="mail_send_logs")
    op.drop_table("mail_send_logs")
    op.drop_index("ix_mail_messages_thread_key", table_name="mail_messages")
    op.drop_index("ix_mail_messages_status_received", table_name="mail_messages")
    op.drop_index("ix_mail_messages_importance", table_name="mail_messages")
    op.drop_index("ix_mail_messages_account_folder", table_name="mail_messages")
    op.drop_table("mail_messages")
    op.drop_table("mail_accounts")

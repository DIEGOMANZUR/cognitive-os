from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from cognitive_os.core.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)


class StatusMixin:
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class MetadataMixin:
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )


class User(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, MetadataMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status <> ''", name="status_not_empty"),
        UniqueConstraint("external_id", name="uq_users_external_id"),
    )

    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    threads: Mapped[list[ConversationThread]] = relationship(back_populates="user")


class ConversationThread(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, MetadataMixin, Base):
    __tablename__ = "conversation_threads"
    __table_args__ = (CheckConstraint("status <> ''", name="status_not_empty"),)

    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)

    user: Mapped[User | None] = relationship(back_populates="threads")
    jobs: Mapped[list[Job]] = relationship(back_populates="thread")
    human_approvals: Mapped[list[HumanApproval]] = relationship(back_populates="thread")


class Document(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, MetadataMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("status <> ''", name="status_not_empty"),
        CheckConstraint("length(sha256) = 64", name="sha256_length"),
        UniqueConstraint("sha256", "source_path", name="uq_documents_sha256_source_path"),
    )

    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)

    pages: Mapped[list[DocumentPage]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentPage(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, MetadataMixin, Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        CheckConstraint("page_number > 0", name="page_number_positive"),
        CheckConstraint("status <> ''", name="status_not_empty"),
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_document_page"),
    )

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(32), default="native_pdf", nullable=False)
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )

    document: Mapped[Document] = relationship(back_populates="pages")
    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="page")


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, MetadataMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="chunk_index_non_negative"),
        CheckConstraint("status <> ''", name="status_not_empty"),
        UniqueConstraint("document_id", "chunk_id", name="uq_document_chunks_document_chunk_id"),
    )

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    page_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_pages.id"), nullable=True)
    chunk_id: Mapped[str] = mapped_column(String(128), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), default="pdf", nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")
    page: Mapped[DocumentPage | None] = relationship(back_populates="chunks")


class Job(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, MetadataMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("status <> ''", name="status_not_empty"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="progress_range"),
    )

    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    thread_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversation_threads.id"),
        nullable=True,
    )
    # Fase 78 (Fase A): NULL = the recipe extractor has not yet looked at
    # this job. A timestamp means it was processed — whether a procedure
    # proposal was emitted or the LLM signalled "skip". The beat task
    # filters on `IS NULL`, so this is the idempotency anchor.
    extracted_recipe_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    thread: Mapped[ConversationThread | None] = relationship(back_populates="jobs")
    events: Mapped[list[JobEvent]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    human_approvals: Mapped[list[HumanApproval]] = relationship(back_populates="job")


class JobEvent(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, MetadataMixin, Base):
    __tablename__ = "job_events"
    __table_args__ = (CheckConstraint("status <> ''", name="status_not_empty"),)

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped[Job] = relationship(back_populates="events")


class HumanApproval(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, MetadataMixin, Base):
    __tablename__ = "human_approvals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'edited', 'expired')",
            name="human_approvals_status_allowed",
        ),
        # The approvals view sorts pending rows newest-first; the reaper looks
        # them up by `(status, created_at)`. Both queries hit the same index.
        Index("ix_human_approvals_status_created_at", "status", "created_at"),
    )

    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    requested_action: Mapped[str] = mapped_column(String(200), nullable=False)
    args_redacted: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approver_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    thread_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversation_threads.id"),
        nullable=True,
    )

    job: Mapped[Job | None] = relationship(back_populates="human_approvals")
    thread: Mapped[ConversationThread | None] = relationship(back_populates="human_approvals")


class ActionRequest(UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "action_requests"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ("
            "'computer_organize', 'browser_navigation', 'gmail_query', "
            "'godaddy_dns_change', 'document_generate', 'browser_preview', "
            "'browser_interactive', 'calendar_create_event', 'drive_upload_file', "
            "'drive_ensure_folder', 'drive_organize_files'"
            ")",
            name="ck_ar_action_type",
        ),
        CheckConstraint(
            "status IN ("
            "'previewed', 'blocked', 'pending_approval', 'queued', 'running', "
            "'completed', 'failed', 'rejected', 'cancelled'"
            ")",
            name="action_requests_status_allowed",
        ),
        Index("ix_action_requests_status_created_at", "status", "created_at"),
        Index("ix_action_requests_action_type", "action_type"),
        # Partial unique index enforced at the DB layer so racing creators cannot
        # both win past the application-level SELECT in
        # `ActionRequestService._find_active_idempotent_request`. Only active rows
        # participate: terminal states (completed/failed/cancelled/rejected/blocked)
        # are excluded so historical idempotency keys can be reused safely.
        Index(
            "uq_action_requests_active_idempotency",
            "action_type",
            "requested_by",
            "idempotency_key",
            unique=True,
            postgresql_where=sql_text(
                "idempotency_key IS NOT NULL AND requested_by IS NOT NULL "
                "AND status IN ('previewed', 'pending_approval', 'queued', 'running')"
            ),
        ),
    )

    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="previewed", nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approval_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("human_approvals.id"),
        nullable=True,
    )
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_redacted: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    # `payload_executable` holds the unredacted payload used at execute time. We keep
    # it separate from `payload_redacted` so the audit trail (and any UI/API surface
    # that reads `payload_redacted`) never sees secret-shaped values, while the worker
    # still has the exact values the user submitted. Nullable for backward compat with
    # rows created before this migration; callers must default to `payload_redacted`
    # when this is NULL.
    payload_executable: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    preview: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    result: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin, MetadataMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (CheckConstraint("status <> ''", name="status_not_empty"),)

    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ResearchRunRecord(TimestampMixin, Base):
    __tablename__ = "research_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'queued', 'planning', 'researching', 'synthesizing', 'scoring', "
            "'completed', 'cancelled', 'failed', 'blocked'"
            ")",
            name="research_runs_status_allowed",
        ),
        Index("ix_research_runs_status_created_at", "status", "created_at"),
        Index("ix_research_runs_user_created_at", "user_id", "created_at"),
    )

    run_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    subtasks: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    results: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    synthesis: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    score: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    events: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class MailAccount(UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "mail_accounts"
    __table_args__ = (
        CheckConstraint("kind IN ('imap', 'gmail_oauth')", name="mail_accounts_kind_allowed"),
        UniqueConstraint("label", name="uq_mail_accounts_label"),
        UniqueConstraint("email_address", name="uq_mail_accounts_email_address"),
    )

    label: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    email_address: Mapped[str] = mapped_column(String(320), nullable=False)
    username: Mapped[str | None] = mapped_column(String(320), nullable=True)
    imap_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monitor_folders: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    send_capable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default_sender: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    messages: Mapped[list[MailMessage]] = relationship(back_populates="account")


class MailMessage(UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "mail_messages"
    __table_args__ = (
        CheckConstraint(
            "classification IN ('important', 'normal', 'spam', 'promo', 'unknown')",
            name="mail_messages_classification_allowed",
        ),
        CheckConstraint(
            "status IN ('new', 'reply_proposed', 'pending_send', 'sent', 'ignored', 'failed')",
            name="mail_messages_status_allowed",
        ),
        UniqueConstraint("account_id", "folder", "uid", name="uq_mail_messages_account_folder_uid"),
        Index("ix_mail_messages_status_received", "status", "received_at"),
        Index("ix_mail_messages_account_folder", "account_id", "folder"),
        Index("ix_mail_messages_importance", "importance_score"),
    )

    account_id: Mapped[UUID] = mapped_column(ForeignKey("mail_accounts.id"), nullable=False)
    folder: Mapped[str] = mapped_column(String(255), nullable=False)
    uid: Mapped[str] = mapped_column(String(128), nullable=False)
    message_id_header: Mapped[str | None] = mapped_column(Text, nullable=True)
    thread_key: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    sender: Mapped[str] = mapped_column(String(500), nullable=False)
    recipients: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    classification: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    importance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    proposed_reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_reply_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped[MailAccount] = relationship(back_populates="messages")
    send_logs: Mapped[list[MailSendLog]] = relationship(back_populates="message")


class MailSendLog(UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "mail_send_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name="mail_send_logs_status_allowed",
        ),
        Index("ix_mail_send_logs_message_status", "message_id", "status"),
    )

    message_id: Mapped[UUID] = mapped_column(ForeignKey("mail_messages.id"), nullable=False)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("mail_accounts.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    to_addresses: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    message: Mapped[MailMessage] = relationship(back_populates="send_logs")


class DeepAgentMemoryRecord(UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "deepagent_memory_records"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('global', 'user', 'case', 'thread', 'agent')",
            name="deepagent_memory_scope_allowed",
        ),
        CheckConstraint(
            "kind IN ('preference', 'procedure', 'lesson', 'warning', 'fact', 'style', "
            "'tool_feedback', 'episodic')",
            name="deepagent_memory_kind_allowed",
        ),
        CheckConstraint(
            "source IN ('human', 'agent_proposed', 'consolidated', 'system')",
            name="deepagent_memory_source_allowed",
        ),
        CheckConstraint(
            "sensitivity IN ('public', 'internal', 'sensitive', 'secret')",
            name="deepagent_memory_sensitivity_allowed",
        ),
        CheckConstraint(
            "status IN ('active', 'pending_approval', 'rejected', 'archived')",
            name="deepagent_memory_status_allowed",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="deepagent_memory_confidence"),
    )

    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    case_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    content_redacted: Mapped[str] = mapped_column(Text, nullable=False)
    content_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class DeepAgentMemoryProposalRecord(UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "deepagent_memory_proposals"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('global', 'user', 'case', 'thread', 'agent')",
            name="deepagent_memory_proposal_scope_allowed",
        ),
        CheckConstraint(
            "sensitivity IN ('public', 'internal', 'sensitive', 'secret')",
            name="deepagent_memory_proposal_sensitivity_allowed",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'applied')",
            name="deepagent_memory_proposal_status_allowed",
        ),
    )

    proposed_by_agent: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_content_redacted: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_content_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    sensitivity: Mapped[str] = mapped_column(String(32), nullable=False)
    source_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    approval_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("human_approvals.id"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeepAgentSkillUsageRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deepagent_skill_usage"

    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PersonalTask(UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "personal_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'done', 'cancelled')",
            name="personal_tasks_status_allowed",
        ),
        CheckConstraint("priority >= 1 AND priority <= 5", name="personal_tasks_priority_range"),
        Index("ix_personal_tasks_user_status", "user_id", "status"),
        Index(
            "ix_personal_tasks_remind_at_partial",
            "remind_at",
            postgresql_where=sql_text("remind_at IS NOT NULL"),
        ),
    )

    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )


class PersonalNote(UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "personal_notes"
    __table_args__ = (Index("ix_personal_notes_user_updated", "user_id", "updated_at"),)

    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )

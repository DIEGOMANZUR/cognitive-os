from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MailClassification = Literal["important", "normal", "spam", "promo", "unknown"]
MailMessageStatus = Literal["new", "reply_proposed", "pending_send", "sent", "ignored", "failed"]


class MailAccountView(BaseModel):
    id: str
    label: str
    kind: str
    email_address: str
    monitor_folders: list[str]
    send_capable: bool
    is_default_sender: bool
    active: bool
    created_at: datetime
    updated_at: datetime


class MailMessageView(BaseModel):
    id: str
    account_id: str
    account_label: str | None = None
    folder: str
    uid: str
    sender: str
    recipients: list[str]
    subject: str | None
    snippet: str | None
    received_at: datetime | None
    classification: MailClassification
    importance_score: float
    proposed_reply_text: str | None
    proposed_reply_rationale: str | None
    status: MailMessageStatus
    sent_at: datetime | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class MailStatusView(BaseModel):
    enabled: bool
    default_sender: str
    require_approval_for_send: bool
    allow_explicit_send: bool = False
    background_sync_enabled: bool = False
    digest_enabled: bool = True
    digest_hours_local: list[str] = Field(default_factory=list)
    digest_timezone: str = "America/Santiago"
    digest_max_messages: int = 50
    gmail_monitor_labels: list[str] = Field(default_factory=list)
    accounts: list[MailAccountView]
    reasons: list[str] = Field(default_factory=list)


class MailSyncResult(BaseModel):
    accounts_checked: int
    fetched: int
    inserted: int
    skipped_existing: int
    errors: list[str] = Field(default_factory=list)


class MailEditReplyRequest(BaseModel):
    body_text: str = Field(min_length=1, max_length=60_000)
    rationale: str | None = Field(default=None, max_length=2000)


class MailApproveReplyRequest(BaseModel):
    body_text: str | None = Field(default=None, min_length=1, max_length=60_000)
    explicit_send_confirmation: str | None = Field(default=None, max_length=128)


class MailSendResult(BaseModel):
    message: MailMessageView
    send_log_id: str
    sent: bool


class MailDigestRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    sync_first: bool = False
    persist_artifact: bool = False


class MailDigestMessage(BaseModel):
    id: str
    account_label: str | None = None
    folder: str
    sender: str
    subject: str | None
    snippet: str | None
    received_at: datetime | None
    classification: MailClassification
    importance_score: float
    proposed_reply_text: str | None = None
    proposed_reply_rationale: str | None = None


class MailDigestResult(BaseModel):
    generated_at: datetime
    total_considered: int
    included_count: int
    excluded_spam_count: int
    important_count: int
    summary_text: str
    proposed_replies_text: str
    messages: list[MailDigestMessage]
    important_messages: list[MailDigestMessage]
    artifact_markdown_path: str | None = None
    artifact_json_path: str | None = None
    warnings: list[str] = Field(default_factory=list)

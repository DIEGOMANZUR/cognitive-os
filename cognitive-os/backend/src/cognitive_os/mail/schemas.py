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


class MailSendResult(BaseModel):
    message: MailMessageView
    send_log_id: str
    sent: bool

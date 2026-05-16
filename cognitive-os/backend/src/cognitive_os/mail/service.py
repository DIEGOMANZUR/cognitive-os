from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from email.utils import parseaddr
from typing import Any, cast
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import MailAccount, MailMessage, MailSendLog
from cognitive_os.mail.classifier import classify_and_propose
from cognitive_os.mail.gmail_label_reader import GmailLabelReader
from cognitive_os.mail.imap_client import ImapMailClient, RawMailMessage
from cognitive_os.mail.schemas import (
    MailAccountView,
    MailApproveReplyRequest,
    MailEditReplyRequest,
    MailMessageView,
    MailSendResult,
    MailStatusView,
    MailSyncResult,
)
from cognitive_os.mail.smtp_client import SmtpMailClient


class MailServiceError(RuntimeError):
    """Raised for expected mail service failures."""


class PersonalMailService:
    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    async def status(self) -> MailStatusView:
        await self.ensure_configured_accounts()
        accounts = await self.list_accounts()
        reasons: list[str] = []
        if not self._settings.mail_enabled:
            reasons.append("MAIL_ENABLED=false")
        if self._settings.mail_godaddy_enabled and self._settings._is_placeholder(
            self._settings.mail_godaddy_password
        ):
            reasons.append("MAIL_GODADDY_PASSWORD is not configured")
        return MailStatusView(
            enabled=self._settings.mail_enabled,
            default_sender=self._settings.mail_default_sender,
            require_approval_for_send=self._settings.mail_require_approval_for_send,
            accounts=accounts,
            reasons=reasons,
        )

    async def ensure_configured_accounts(self) -> None:
        async with session_scope() as session:
            if self._settings.mail_godaddy_enabled:
                await self._upsert_account(
                    session,
                    label="godaddy-primary",
                    kind="imap",
                    email_address=self._settings.mail_godaddy_username,
                    username=self._settings.mail_godaddy_username,
                    imap_host=self._settings.mail_godaddy_imap_host,
                    imap_port=self._settings.mail_godaddy_imap_port,
                    smtp_host=self._settings.mail_godaddy_smtp_host,
                    smtp_port=self._settings.mail_godaddy_smtp_port,
                    monitor_folders=self._settings.mail_godaddy_monitor_folders,
                    send_capable=True,
                    is_default_sender=True,
                )
            if self._settings.gmail_read_enabled:
                await self._upsert_account(
                    session,
                    label="gmail-forwarded-todos",
                    kind="gmail_oauth",
                    email_address="diegomanzurn@gmail.com",
                    username=None,
                    imap_host=None,
                    imap_port=None,
                    smtp_host=None,
                    smtp_port=None,
                    monitor_folders=[self._settings.mail_gmail_label],
                    send_capable=False,
                    is_default_sender=False,
                )

    async def list_accounts(self) -> list[MailAccountView]:
        async with session_scope() as session:
            result = await session.execute(select(MailAccount).order_by(MailAccount.label))
            return [self._account_view(row) for row in result.scalars().all()]

    async def sync_now(self) -> MailSyncResult:
        if not self._settings.mail_enabled:
            return MailSyncResult(accounts_checked=0, fetched=0, inserted=0, skipped_existing=0)
        await self.ensure_configured_accounts()
        async with session_scope() as session:
            result = await session.execute(select(MailAccount).where(MailAccount.active.is_(True)))
            accounts = list(result.scalars().all())
        checked = 0
        fetched = 0
        inserted = 0
        skipped = 0
        errors: list[str] = []
        for account in accounts:
            checked += 1
            try:
                raw_messages = await asyncio.to_thread(self._fetch_account_messages, account)
                fetched += len(raw_messages)
                for raw in raw_messages:
                    was_inserted = await self._insert_message_if_new(account.id, raw)
                    if was_inserted:
                        inserted += 1
                    else:
                        skipped += 1
            except Exception as exc:
                errors.append(_safe_mail_error(account.label, exc))
        return MailSyncResult(
            accounts_checked=checked,
            fetched=fetched,
            inserted=inserted,
            skipped_existing=skipped,
            errors=errors,
        )

    async def list_messages(
        self,
        *,
        statuses: list[str] | None = None,
        limit: int = 80,
    ) -> list[MailMessageView]:
        capped = max(1, min(limit, 200))
        stmt = (
            select(MailMessage, MailAccount.label)
            .join(MailAccount, MailAccount.id == MailMessage.account_id)
            .order_by(desc(MailMessage.received_at), desc(MailMessage.created_at))
            .limit(capped)
        )
        if statuses:
            stmt = stmt.where(MailMessage.status.in_(statuses))
        async with session_scope() as session:
            result = await session.execute(stmt)
            return [self._message_view(row, account_label=label) for row, label in result.all()]

    async def get_message(self, message_id: UUID) -> MailMessageView | None:
        async with session_scope() as session:
            result = await session.execute(
                select(MailMessage, MailAccount.label)
                .join(MailAccount, MailAccount.id == MailMessage.account_id)
                .where(MailMessage.id == message_id)
            )
            row = result.first()
            if row is None:
                return None
            message, label = row
            return self._message_view(message, account_label=label)

    async def edit_reply(
        self,
        message_id: UUID,
        request: MailEditReplyRequest,
    ) -> MailMessageView | None:
        async with session_scope() as session:
            row = await session.get(MailMessage, message_id)
            if row is None:
                return None
            row.proposed_reply_text = request.body_text
            row.proposed_reply_rationale = request.rationale or row.proposed_reply_rationale
            row.status = "reply_proposed"
            await session.flush()
            return self._message_view(row)

    async def ignore_message(self, message_id: UUID) -> MailMessageView | None:
        async with session_scope() as session:
            row = await session.get(MailMessage, message_id)
            if row is None:
                return None
            row.status = "ignored"
            await session.flush()
            return self._message_view(row)

    async def approve_and_send(
        self,
        message_id: UUID,
        request: MailApproveReplyRequest,
        *,
        approved_by: str,
    ) -> MailSendResult:
        if self._settings.mail_require_approval_for_send is not True:
            raise MailServiceError("Mail send policy must require human approval in this runtime.")
        async with session_scope() as session:
            message = await session.get(MailMessage, message_id)
            if message is None:
                raise MailServiceError("Mail message not found.")
            account = await self._default_sender_account(session)
            body = request.body_text or message.proposed_reply_text
            if not body:
                raise MailServiceError("No reply body was proposed or provided.")
            to_address = parseaddr(message.sender)[1]
            if not to_address:
                raise MailServiceError("Original sender address could not be parsed.")
            send_log = MailSendLog(
                message_id=message.id,
                account_id=account.id,
                status="pending",
                to_addresses=[to_address],
                subject=message.subject or "(sin asunto)",
                body_text=body,
                approved_by=approved_by,
            )
            message.status = "pending_send"
            message.error = None
            session.add(send_log)
            await session.flush()
            log_id = send_log.id
        try:
            await asyncio.to_thread(
                self._send_with_account,
                account,
                to_address,
                message.subject or "(sin asunto)",
                body,
                message.message_id_header,
                message.thread_key,
            )
        except Exception as exc:
            async with session_scope() as session:
                msg = await session.get(MailMessage, message_id)
                log = await session.get(MailSendLog, log_id)
                if msg is not None:
                    msg.status = "failed"
                    msg.error = _safe_mail_error("smtp", exc)
                if log is not None:
                    log.status = "failed"
                    log.error = _safe_mail_error("smtp", exc)
            raise MailServiceError(_safe_mail_error("SMTP send failed", exc)) from exc
        async with session_scope() as session:
            msg = await session.get(MailMessage, message_id)
            log = await session.get(MailSendLog, log_id)
            if msg is None or log is None:
                raise MailServiceError("Message or send log disappeared after send.")
            now = datetime.now(UTC)
            msg.status = "sent"
            msg.sent_at = now
            log.status = "sent"
            log.sent_at = now
            await session.flush()
            return MailSendResult(
                message=self._message_view(msg), send_log_id=str(log.id), sent=True
            )

    async def _insert_message_if_new(self, account_id: UUID, raw: RawMailMessage) -> bool:
        result = classify_and_propose(
            folder=raw.folder,
            sender=raw.sender,
            subject=raw.subject,
            snippet=raw.snippet,
            body_text=raw.body_text,
        )
        status = "reply_proposed" if result.proposed_reply else "new"
        row = MailMessage(
            account_id=account_id,
            folder=raw.folder,
            uid=raw.uid,
            message_id_header=raw.message_id_header,
            thread_key=raw.thread_key,
            sender=raw.sender,
            recipients=raw.recipients,
            subject=raw.subject,
            snippet=raw.snippet,
            body_text=raw.body_text,
            body_html=raw.body_html,
            received_at=raw.received_at,
            classification=result.classification,
            importance_score=result.importance_score,
            proposed_reply_text=result.proposed_reply,
            proposed_reply_rationale=result.rationale,
            status=status,
        )
        try:
            async with session_scope() as session:
                session.add(row)
            return True
        except IntegrityError:
            return False

    def _fetch_account_messages(self, account: MailAccount) -> list[RawMailMessage]:
        folders = [str(x) for x in (account.monitor_folders or []) if str(x)]
        if account.kind == "imap":
            password = self._settings.mail_godaddy_password.get_secret_value()
            client = ImapMailClient(
                host=account.imap_host or self._settings.mail_godaddy_imap_host,
                port=account.imap_port or self._settings.mail_godaddy_imap_port,
                username=account.username or account.email_address,
                password=password,
                timeout_seconds=self._settings.mail_imap_timeout_seconds,
            )
            return client.fetch_recent(
                folders=folders or ["INBOX"],
                max_per_folder=self._settings.mail_fetch_max_per_folder,
            )
        if account.kind == "gmail_oauth":
            token_path = self._settings.gmail_token_dir.expanduser() / "token.json"
            reader = GmailLabelReader(
                token_path=token_path,
                label_name=folders[0] if folders else self._settings.mail_gmail_label,
            )
            return reader.fetch_recent(max_messages=self._settings.mail_fetch_max_per_folder)
        return []

    def _send_with_account(
        self,
        account: MailAccount,
        to_address: str,
        subject: str,
        body: str,
        in_reply_to: str | None,
        references: str | None,
    ) -> None:
        password = self._settings.mail_godaddy_password.get_secret_value()
        client = SmtpMailClient(
            host=account.smtp_host or self._settings.mail_godaddy_smtp_host,
            port=account.smtp_port or self._settings.mail_godaddy_smtp_port,
            username=account.username or account.email_address,
            password=password,
            timeout_seconds=self._settings.mail_smtp_timeout_seconds,
        )
        client.send_reply(
            from_address=account.email_address,
            to_address=to_address,
            subject=subject,
            body_text=body,
            in_reply_to=in_reply_to,
            references=references,
        )

    @staticmethod
    async def _upsert_account(session: Any, **values: Any) -> None:
        result = await session.execute(
            select(MailAccount).where(MailAccount.email_address == values["email_address"])
        )
        row = result.scalar_one_or_none()
        if row is None:
            session.add(MailAccount(**values))
            return
        for key, value in values.items():
            setattr(row, key, value)

    async def _default_sender_account(self, session: Any) -> MailAccount:
        result = await session.execute(
            select(MailAccount)
            .where(MailAccount.send_capable.is_(True))
            .where(MailAccount.is_default_sender.is_(True))
            .limit(1)
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise MailServiceError("No default sender account configured.")
        return cast(MailAccount, account)

    @staticmethod
    def _account_view(row: MailAccount) -> MailAccountView:
        return MailAccountView(
            id=str(row.id),
            label=row.label,
            kind=row.kind,
            email_address=row.email_address,
            monitor_folders=[str(x) for x in (row.monitor_folders or [])],
            send_capable=bool(row.send_capable),
            is_default_sender=bool(row.is_default_sender),
            active=bool(row.active),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _message_view(row: MailMessage, *, account_label: str | None = None) -> MailMessageView:
        return MailMessageView(
            id=str(row.id),
            account_id=str(row.account_id),
            account_label=account_label,
            folder=row.folder,
            uid=row.uid,
            sender=row.sender,
            recipients=[str(x) for x in (row.recipients or [])],
            subject=row.subject,
            snippet=row.snippet,
            received_at=row.received_at,
            classification=row.classification,  # type: ignore[arg-type]
            importance_score=float(row.importance_score),
            proposed_reply_text=row.proposed_reply_text,
            proposed_reply_rationale=row.proposed_reply_rationale,
            status=row.status,  # type: ignore[arg-type]
            sent_at=row.sent_at,
            error=row.error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


def _safe_mail_error(prefix: str, exc: Exception) -> str:
    """Return a provider-safe error without paths, credentials or message bodies."""

    return f"{prefix}: {type(exc).__name__}"

"""Contract tests for `/mail/*` endpoints with a fake PersonalMailService."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import desc, select

import cognitive_os.api.app as api_app
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import Settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import AuditEvent, MailAccount, MailMessage, MailSendLog
from cognitive_os.mail.schemas import (
    MailAccountView,
    MailApproveReplyRequest,
    MailDigestMessage,
    MailDigestRequest,
    MailDigestResult,
    MailEditReplyRequest,
    MailMessageView,
    MailSendResult,
    MailStatusView,
    MailSyncResult,
)
from cognitive_os.mail.service import MailServiceError, PersonalMailService


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


def _now() -> datetime:
    return datetime.now(UTC)


def _account(label: str = "godaddy-primary") -> MailAccountView:
    now = _now()
    return MailAccountView(
        id=str(uuid4()),
        label=label,
        kind="imap",
        email_address="diego@example.test",
        monitor_folders=["INBOX", "Spam"],
        send_capable=True,
        is_default_sender=True,
        active=True,
        created_at=now,
        updated_at=now,
    )


def _message(status_value: str = "reply_proposed") -> MailMessageView:
    now = _now()
    return MailMessageView(
        id=str(uuid4()),
        account_id=str(uuid4()),
        account_label="godaddy-primary",
        folder="INBOX",
        uid="42",
        sender="Client <client@example.test>",
        recipients=["diego@example.test"],
        subject="Hola",
        snippet="contenido…",
        received_at=now,
        classification="important",
        importance_score=0.91,
        proposed_reply_text="Gracias por tu mensaje.",
        proposed_reply_rationale="cliente recurrente",
        status=status_value,  # type: ignore[arg-type]
        sent_at=None,
        error=None,
        created_at=now,
        updated_at=now,
    )


def _read_only_mail_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "mail_enabled": True,
        "mail_godaddy_enabled": True,
        "mail_godaddy_username": "diego@example.test",
        "mail_godaddy_password": "test-password",  # pragma: allowlist secret
        "mail_default_sender": "diego@example.test",
        "mail_require_approval_for_send": True,
        "enable_email_send": False,
        "mail_allow_explicit_send": False,
    }
    values.update(overrides)
    return Settings(**values)


def _explicit_send_mail_settings(**overrides: object) -> Settings:
    return _read_only_mail_settings(
        enable_email_send=True,
        mail_allow_explicit_send=True,
        **overrides,
    )


async def _create_persisted_mail_message(
    service: PersonalMailService,
    *,
    folder: str = "INBOX",
    sender: str = "Client <client@example.test>",
    subject: str = "Consulta",
    snippet: str = "Necesito respuesta",
    body_text: str = "Necesito respuesta",
    classification: str = "important",
    importance_score: float = 0.9,
    proposed_reply_text: str | None = "Respuesta propuesta",
    proposed_reply_rationale: str | None = "test",
) -> UUID:
    await service.ensure_configured_accounts()
    async with session_scope() as session:
        result = await session.execute(
            select(MailAccount).where(MailAccount.email_address == "diego@example.test")
        )
        account = result.scalar_one()
        row = MailMessage(
            account_id=account.id,
            folder=folder,
            uid=str(uuid4()),
            message_id_header=f"<{uuid4()}@example.test>",
            thread_key=str(uuid4()),
            sender=sender,
            recipients=["diego@example.test"],
            subject=subject,
            snippet=snippet,
            body_text=body_text,
            received_at=_now(),
            classification=classification,
            importance_score=importance_score,
            proposed_reply_text=proposed_reply_text,
            proposed_reply_rationale=proposed_reply_rationale,
            status="reply_proposed" if proposed_reply_text else "new",
        )
        session.add(row)
        await session.flush()
        return row.id


class _FakeMailService:
    def __init__(self) -> None:
        self.messages: dict[UUID, MailMessageView] = {}
        self.last_edit: tuple[UUID, str] | None = None
        self.last_approve: tuple[UUID, str | None, str] | None = None
        self.raise_on_send: Exception | None = None

    async def status(self) -> MailStatusView:
        return MailStatusView(
            enabled=True,
            default_sender="diego@example.test",
            require_approval_for_send=True,
            accounts=[_account()],
            reasons=[],
        )

    async def sync_now(self) -> MailSyncResult:
        return MailSyncResult(
            accounts_checked=1,
            fetched=2,
            inserted=1,
            skipped_existing=1,
            errors=[],
        )

    async def build_digest(self, request: MailDigestRequest) -> MailDigestResult:
        del request
        now = _now()
        messages = list(self.messages.values())
        included = [message for message in messages if message.classification != "spam"]
        important = [message for message in included if message.classification == "important"]
        digest_messages = [
            MailDigestMessage(
                id=message.id,
                account_label=message.account_label,
                folder=message.folder,
                sender=message.sender,
                subject=message.subject,
                snippet=message.snippet,
                received_at=message.received_at,
                classification=message.classification,
                importance_score=message.importance_score,
                proposed_reply_text=message.proposed_reply_text,
                proposed_reply_rationale=message.proposed_reply_rationale,
            )
            for message in included
        ]
        return MailDigestResult(
            generated_at=now,
            total_considered=len(messages),
            included_count=len(included),
            excluded_spam_count=len(messages) - len(included),
            important_count=len(important),
            summary_text="Resumen fake",
            proposed_replies_text="Respuesta fake",
            messages=digest_messages,
            important_messages=[
                message for message in digest_messages if message.classification == "important"
            ],
            warnings=[],
        )

    async def list_messages(
        self, *, statuses: list[str] | None = None, limit: int = 80
    ) -> list[MailMessageView]:
        items = list(self.messages.values())
        if statuses:
            items = [m for m in items if m.status in statuses]
        return items[:limit]

    async def get_message(self, message_id: UUID) -> MailMessageView | None:
        return self.messages.get(message_id)

    async def edit_reply(
        self, message_id: UUID, request: MailEditReplyRequest
    ) -> MailMessageView | None:
        msg = self.messages.get(message_id)
        if msg is None:
            return None
        self.last_edit = (message_id, request.body_text)
        updated = msg.model_copy(
            update={"proposed_reply_text": request.body_text, "status": "reply_proposed"}
        )
        self.messages[message_id] = updated
        return updated

    async def ignore_message(self, message_id: UUID) -> MailMessageView | None:
        msg = self.messages.get(message_id)
        if msg is None:
            return None
        updated = msg.model_copy(update={"status": "ignored"})
        self.messages[message_id] = updated
        return updated

    async def approve_and_send(
        self,
        message_id: UUID,
        request: MailApproveReplyRequest,
        *,
        approved_by: str,
    ) -> MailSendResult:
        if self.raise_on_send is not None:
            raise self.raise_on_send
        msg = self.messages.get(message_id)
        if msg is None:
            raise MailServiceError("Mail message not found.")
        self.last_approve = (message_id, request.body_text, approved_by)
        sent = msg.model_copy(update={"status": "sent", "sent_at": _now()})
        self.messages[message_id] = sent
        return MailSendResult(message=sent, send_log_id=str(uuid4()), sent=True)


@pytest.fixture()
def fake_service(monkeypatch: pytest.MonkeyPatch) -> _FakeMailService:
    service = _FakeMailService()
    monkeypatch.setattr(api_app, "PersonalMailService", lambda: service)
    return service


@pytest.mark.asyncio
async def test_mail_endpoints_require_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for path in (
            "/mail/status",
            "/mail/messages",
        ):
            response = await client.get(path)
            assert response.status_code == 401, path
        sync_resp = await client.post("/mail/sync")
        assert sync_resp.status_code == 401
        digest_resp = await client.post("/mail/digest/preview", json={})
        assert digest_resp.status_code == 401


@pytest.mark.asyncio
async def test_mail_status_and_sync_roundtrip(fake_service: _FakeMailService) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        status_resp = await client.get("/mail/status", headers=_headers())
        sync_resp = await client.post("/mail/sync", headers=_headers())

    assert status_resp.status_code == 200
    payload = status_resp.json()
    assert payload["enabled"] is True
    assert payload["require_approval_for_send"] is True
    assert payload["allow_explicit_send"] is False
    assert payload["background_sync_enabled"] is False
    assert payload["digest_hours_local"] == []
    assert payload["accounts"][0]["label"] == "godaddy-primary"

    assert sync_resp.status_code == 200
    sync_payload = sync_resp.json()
    assert sync_payload["accounts_checked"] == 1
    assert sync_payload["inserted"] == 1


@pytest.mark.asyncio
async def test_mail_messages_filter_pending_send(fake_service: _FakeMailService) -> None:
    pending = _message(status_value="pending_send")
    fake_service.messages[UUID(pending.id)] = pending
    other = _message(status_value="reply_proposed")
    fake_service.messages[UUID(other.id)] = other

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/mail/messages?statuses=pending_send", headers=_headers())

    assert response.status_code == 200
    statuses = {row["status"] for row in response.json()}
    assert statuses == {"pending_send"}


@pytest.mark.asyncio
async def test_mail_edit_reply_updates_status(fake_service: _FakeMailService) -> None:
    msg = _message(status_value="new")
    fake_service.messages[UUID(msg.id)] = msg

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            f"/mail/messages/{msg.id}/reply",
            json={"body_text": "Respuesta editada"},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "reply_proposed"
    assert fake_service.last_edit == (UUID(msg.id), "Respuesta editada")


@pytest.mark.asyncio
async def test_mail_digest_preview_returns_separate_text_fields(
    fake_service: _FakeMailService,
) -> None:
    msg = _message(status_value="reply_proposed")
    fake_service.messages[UUID(msg.id)] = msg

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/mail/digest/preview",
            json={"limit": 50, "sync_first": False, "persist_artifact": False},
            headers=_headers(),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary_text"] == "Resumen fake"
    assert payload["proposed_replies_text"] == "Respuesta fake"
    assert payload["total_considered"] == 1


@pytest.mark.asyncio
async def test_mail_approve_send_returns_send_result(fake_service: _FakeMailService) -> None:
    msg = _message(status_value="reply_proposed")
    fake_service.messages[UUID(msg.id)] = msg

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/mail/messages/{msg.id}/approve-send",
            json={
                "body_text": "Texto aprobado",
                "explicit_send_confirmation": "SEND_THIS_EMAIL_EXPLICITLY",
            },
            headers=_headers(),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent"] is True
    assert payload["message"]["status"] == "sent"
    assert fake_service.last_approve is not None
    assert fake_service.last_approve[1] == "Texto aprobado"
    assert fake_service.last_approve[2] == "1"


@pytest.mark.asyncio
async def test_personal_mail_service_read_only_policy_blocks_send_before_smtp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = PersonalMailService(_read_only_mail_settings())
    message_id = await _create_persisted_mail_message(service)

    def fail_send(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("SMTP must not be called in read-only mail policy")

    monkeypatch.setattr(PersonalMailService, "_send_with_account", fail_send)

    with pytest.raises(MailServiceError, match="Mail sending is disabled by policy"):
        await service.approve_and_send(
            message_id,
            MailApproveReplyRequest(
                body_text="Texto",
                explicit_send_confirmation="SEND_THIS_EMAIL_EXPLICITLY",
            ),
            approved_by="operator",
        )

    async with session_scope() as session:
        message = await session.get(MailMessage, message_id)
        logs = (
            (await session.execute(select(MailSendLog).where(MailSendLog.message_id == message_id)))
            .scalars()
            .all()
        )

    assert message is not None
    assert message.status == "reply_proposed"
    assert logs == []


@pytest.mark.asyncio
async def test_personal_mail_service_requires_confirmation_even_when_send_enabled() -> None:
    service = PersonalMailService(_explicit_send_mail_settings())
    message_id = await _create_persisted_mail_message(service)

    with pytest.raises(MailServiceError, match="Explicit send confirmation is required"):
        await service.approve_and_send(
            message_id,
            MailApproveReplyRequest(body_text="Texto"),
            approved_by="operator",
        )


@pytest.mark.asyncio
async def test_personal_mail_service_explicit_send_sends_once_and_audits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = PersonalMailService(_explicit_send_mail_settings())
    message_id = await _create_persisted_mail_message(service)
    sent_calls: list[dict[str, str | None]] = []

    def fake_send(
        self: PersonalMailService,
        account: MailAccount,
        to_address: str,
        subject: str,
        body: str,
        in_reply_to: str | None,
        references: str | None,
    ) -> None:
        del self, account, in_reply_to, references
        sent_calls.append({"to": to_address, "subject": subject, "body": body})

    monkeypatch.setattr(PersonalMailService, "_send_with_account", fake_send)

    result = await service.approve_and_send(
        message_id,
        MailApproveReplyRequest(
            body_text="Texto directo",
            explicit_send_confirmation="SEND_THIS_EMAIL_EXPLICITLY",
        ),
        approved_by="operator",
    )
    duplicate = await service.approve_and_send(
        message_id,
        MailApproveReplyRequest(
            body_text="Texto directo",
            explicit_send_confirmation="SEND_THIS_EMAIL_EXPLICITLY",
        ),
        approved_by="operator",
    )

    assert result.sent is True
    assert duplicate.sent is True
    assert sent_calls == [
        {"to": "client@example.test", "subject": "Consulta", "body": "Texto directo"}
    ]

    async with session_scope() as session:
        logs = (
            (
                await session.execute(
                    select(MailSendLog)
                    .where(MailSendLog.message_id == message_id)
                    .order_by(desc(MailSendLog.created_at))
                )
            )
            .scalars()
            .all()
        )
        events = (
            (
                await session.execute(
                    select(AuditEvent)
                    .where(AuditEvent.resource_id == str(message_id))
                    .order_by(AuditEvent.created_at)
                )
            )
            .scalars()
            .all()
        )

    assert len(logs) == 1
    assert logs[0].status == "sent"
    assert logs[0].approved_by == "operator"
    assert [event.action for event in events] == [
        "mail.send.requested",
        "mail.send.completed",
        "mail.send.duplicate_ignored",
    ]
    assert {event.metadata_json["policy_mode"] for event in events} == {"approved"}
    assert "client@example.test" not in str([event.metadata_json for event in events])


@pytest.mark.asyncio
async def test_personal_mail_digest_excludes_agent_spam_and_persists_artifacts(
    tmp_path: Path,
) -> None:
    service = PersonalMailService(
        _read_only_mail_settings(
            local_storage_dir=str(tmp_path),
            mail_digest_output_dir="mail_digests",
        )
    )
    await _create_persisted_mail_message(
        service,
        folder="Spam",
        sender="Patient <patient@example.test>",
        subject="Consulta paciente urgente",
        snippet="Necesito una hora para consulta",
        body_text="Necesito una hora para consulta",
        classification="important",
        importance_score=0.9,
        proposed_reply_text="Hola, confirmo recibido.",
        proposed_reply_rationale="importante por paciente",
    )
    await _create_persisted_mail_message(
        service,
        folder="INBOX",
        sender="Casino <promo@example.test>",
        subject="Ganaste un premio casino",
        snippet="click here limited time",
        body_text="click here limited time casino",
        classification="spam",
        importance_score=0.05,
        proposed_reply_text=None,
        proposed_reply_rationale="spam por contenido",
    )
    await _create_persisted_mail_message(
        service,
        folder="INBOX",
        sender="Newsletter <news@example.test>",
        subject="Resumen mensual",
        snippet="newsletter",
        body_text="newsletter",
        classification="promo",
        importance_score=0.2,
        proposed_reply_text=None,
        proposed_reply_rationale="promocional",
    )

    digest = await service.build_digest(MailDigestRequest(limit=3, persist_artifact=True))

    assert digest.total_considered == 3
    assert digest.included_count == 2
    assert digest.excluded_spam_count == 1
    assert digest.important_count == 1
    assert "Consulta paciente urgente" in digest.summary_text
    assert "Ganaste un premio casino" not in digest.summary_text
    assert "Hola, confirmo recibido." in digest.proposed_replies_text
    assert digest.artifact_markdown_path is not None
    assert digest.artifact_json_path is not None
    assert (tmp_path / "mail_digests").is_dir()


@pytest.mark.asyncio
async def test_personal_mail_service_smtp_failure_is_persisted_and_audited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = PersonalMailService(_explicit_send_mail_settings())
    message_id = await _create_persisted_mail_message(service)

    def fake_send(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("smtp password leaked here")  # pragma: allowlist secret

    monkeypatch.setattr(PersonalMailService, "_send_with_account", fake_send)

    with pytest.raises(MailServiceError, match="SMTP send failed: RuntimeError"):
        await service.approve_and_send(
            message_id,
            MailApproveReplyRequest(
                body_text="Texto",
                explicit_send_confirmation="SEND_THIS_EMAIL_EXPLICITLY",
            ),
            approved_by="operator",
        )

    async with session_scope() as session:
        message = await session.get(MailMessage, message_id)
        log = (
            await session.execute(
                select(MailSendLog)
                .where(MailSendLog.message_id == message_id)
                .order_by(desc(MailSendLog.created_at))
                .limit(1)
            )
        ).scalar_one()
        failed_event = (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.resource_id == str(message_id))
                .where(AuditEvent.action == "mail.send.failed")
            )
        ).scalar_one()

    assert message is not None
    assert message.status == "failed"
    assert message.error == "smtp: RuntimeError"
    assert log.status == "failed"
    assert log.error == "smtp: RuntimeError"
    assert failed_event.metadata_json["error"] == "smtp: RuntimeError"
    assert "password" not in str(failed_event.metadata_json).lower()


@pytest.mark.asyncio
async def test_mail_approve_send_smtp_failure_becomes_409(
    fake_service: _FakeMailService,
) -> None:
    msg = _message(status_value="reply_proposed")
    fake_service.messages[UUID(msg.id)] = msg
    fake_service.raise_on_send = MailServiceError("SMTP send failed: TimeoutError")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/mail/messages/{msg.id}/approve-send",
            json={
                "body_text": "Texto",
                "explicit_send_confirmation": "SEND_THIS_EMAIL_EXPLICITLY",
            },
            headers=_headers(),
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "SMTP send failed" in detail
    # Ensure the error message stays redacted (no host paths / credentials leak markers)
    forbidden = ("password", "secret", "token", "/home/", "@example.test")
    for marker in forbidden:
        assert marker not in detail, marker


@pytest.mark.asyncio
async def test_mail_message_404_when_missing(fake_service: _FakeMailService) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/mail/messages/{uuid4()}", headers=_headers())

    assert response.status_code == 404

"""Contract tests for `/mail/*` endpoints with a fake PersonalMailService."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest

import cognitive_os.api.app as api_app
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.mail.schemas import (
    MailAccountView,
    MailApproveReplyRequest,
    MailEditReplyRequest,
    MailMessageView,
    MailSendResult,
    MailStatusView,
    MailSyncResult,
)
from cognitive_os.mail.service import MailServiceError


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
async def test_mail_approve_send_returns_send_result(fake_service: _FakeMailService) -> None:
    msg = _message(status_value="reply_proposed")
    fake_service.messages[UUID(msg.id)] = msg

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/mail/messages/{msg.id}/approve-send",
            json={"body_text": "Texto aprobado"},
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
            json={"body_text": "Texto"},
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

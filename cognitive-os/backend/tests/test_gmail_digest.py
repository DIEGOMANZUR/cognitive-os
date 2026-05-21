from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import cognitive_os.api.app as api_app
import cognitive_os.mail.gmail_label_reader as gmail_label_reader_module
from cognitive_os.actions.gmail_digest import (
    FakeGmailReader,
    GmailDigestService,
    GmailReaderError,
    GmailRestReader,
)
from cognitive_os.actions.schemas import GmailDigestRequest
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import Settings
from cognitive_os.mail.gmail_label_reader import GmailLabelReader


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


def _sample_message(
    *,
    msg_id: str,
    sender: str,
    subject: str,
    hours_ago: float = 1.0,
    snippet: str = "snippet text",
    labels: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": msg_id,
        "thread_id": f"t-{msg_id}",
        "sender": sender,
        "subject": subject,
        "snippet": snippet,
        "labels": labels or ["INBOX"],
        "received_at": (datetime.now(tz=UTC) - timedelta(hours=hours_ago)).isoformat(),
    }


def test_digest_blocked_when_gmail_read_disabled() -> None:
    service = GmailDigestService(
        reader=FakeGmailReader([]),
        app_settings=Settings(gmail_read_enabled=False),
    )
    preview = service.build_preview(GmailDigestRequest())
    assert preview.status == "blocked"
    assert preview.reason == "Gmail read is disabled."
    assert preview.total_messages == 0


def test_digest_blocked_when_no_reader_configured() -> None:
    service = GmailDigestService(
        reader=None,
        app_settings=Settings(
            gmail_read_enabled=True,
            gmail_client_id="cid",
            gmail_client_secret="csecret",  # pragma: allowlist secret
        ),
    )
    preview = service.build_preview(GmailDigestRequest())
    assert preview.status == "blocked"
    assert "reader" in (preview.reason or "").lower()


def test_digest_redacts_addresses_and_groups_by_sender() -> None:
    messages = [
        _sample_message(msg_id="m1", sender="alice@example.com", subject="Hello A1"),
        _sample_message(msg_id="m2", sender="alice@example.com", subject="Hello A2"),
        _sample_message(msg_id="m3", sender="Bob <bob@partner.co>", subject="Hi"),
    ]
    settings = Settings(
        gmail_read_enabled=True,
        gmail_client_id="cid",
        gmail_client_secret="csecret",  # pragma: allowlist secret
    )
    service = GmailDigestService(reader=FakeGmailReader(messages), app_settings=settings)

    preview = service.build_preview(GmailDigestRequest(lookback_hours=24, max_messages=10))

    assert preview.status == "ok"
    assert preview.total_messages == 3
    assert preview.dry_run_only is True
    assert preview.requires_approval is False

    for sender in preview.senders:
        assert "@" in sender.address_redacted
        local = sender.address_redacted.split("@")[0]
        assert "*" in local, f"local part not redacted: {sender.address_redacted}"

    domains = {s.domain for s in preview.senders}
    assert domains == {"example.com", "partner.co"}

    alice = next(s for s in preview.senders if s.domain == "example.com")
    assert alice.message_count == 2

    for msg in preview.top_messages:
        assert "@" in msg.sender_redacted
        assert msg.message_id in {"m1", "m2", "m3"}


def test_digest_filters_messages_outside_lookback_window() -> None:
    messages = [
        _sample_message(msg_id="recent", sender="a@x.com", subject="recent", hours_ago=1.0),
        _sample_message(msg_id="old", sender="a@x.com", subject="old", hours_ago=72.0),
    ]
    settings = Settings(
        gmail_read_enabled=True,
        gmail_client_id="cid",
        gmail_client_secret="csecret",  # pragma: allowlist secret
    )
    service = GmailDigestService(reader=FakeGmailReader(messages), app_settings=settings)

    preview = service.build_preview(GmailDigestRequest(lookback_hours=24))

    assert preview.total_messages == 1
    assert preview.top_messages[0].message_id == "recent"


def test_digest_proposes_drafts_but_never_creates_them() -> None:
    messages = [
        _sample_message(msg_id="m1", sender="alice@example.com", subject="Project update"),
        _sample_message(msg_id="m2", sender="bob@partner.co", subject="Quick question"),
    ]
    reader = FakeGmailReader(messages)
    settings = Settings(
        gmail_read_enabled=True,
        gmail_client_id="cid",
        gmail_client_secret="csecret",  # pragma: allowlist secret
    )
    service = GmailDigestService(reader=reader, app_settings=settings)

    preview = service.build_preview(
        GmailDigestRequest(lookback_hours=24, include_proposed_drafts=True)
    )

    assert preview.status == "ok"
    assert len(preview.proposed_drafts) == 2
    for draft in preview.proposed_drafts:
        assert draft.requires_approval is True
        assert "@" in draft.sender_redacted
        local = draft.sender_redacted.split("@")[0]
        assert "*" in local
        assert draft.body_preview
    in_reply = {d.in_reply_to_message_id for d in preview.proposed_drafts}
    assert in_reply == {"m1", "m2"}


def test_digest_includes_warning_when_window_empty() -> None:
    settings = Settings(
        gmail_read_enabled=True,
        gmail_client_id="cid",
        gmail_client_secret="csecret",  # pragma: allowlist secret
    )
    service = GmailDigestService(reader=FakeGmailReader([]), app_settings=settings)
    preview = service.build_preview(GmailDigestRequest(lookback_hours=12))
    assert preview.status == "ok"
    assert "no_messages_in_window" in preview.warnings
    assert preview.total_messages == 0


def test_digest_reader_receives_request_parameters() -> None:
    reader = FakeGmailReader([])
    settings = Settings(
        gmail_read_enabled=True,
        gmail_client_id="cid",
        gmail_client_secret="csecret",  # pragma: allowlist secret
    )
    service = GmailDigestService(reader=reader, app_settings=settings)
    service.build_preview(
        GmailDigestRequest(lookback_hours=48, max_messages=25, labels=["INBOX", "STARRED"])
    )
    assert reader.calls == [
        {"lookback_hours": 48, "max_messages": 25, "labels": ["INBOX", "STARRED"]}
    ]


def test_digest_endpoint_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_app, "_gmail_digest_reader", FakeGmailReader([]))
    monkeypatch.setattr(api_app.settings, "gmail_read_enabled", False, raising=False)

    transport = httpx.ASGITransport(app=app)

    async def call() -> httpx.Response:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/actions/gmail/digest/preview",
                json={"lookback_hours": 24, "max_messages": 10, "include_proposed_drafts": False},
                headers=_headers(),
            )

    import asyncio

    response = asyncio.run(call())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"


def test_digest_endpoint_ok_with_fake_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGmailReader(
        [
            _sample_message(msg_id="m1", sender="alice@example.com", subject="hi"),
        ]
    )
    monkeypatch.setattr(api_app, "_gmail_digest_reader", fake)
    monkeypatch.setattr(api_app.settings, "gmail_read_enabled", True, raising=False)

    transport = httpx.ASGITransport(app=app)

    async def call() -> httpx.Response:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/actions/gmail/digest/preview",
                json={"lookback_hours": 24, "max_messages": 5, "include_proposed_drafts": True},
                headers=_headers(),
            )

    import asyncio

    response = asyncio.run(call())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["total_messages"] == 1
    assert body["proposed_drafts"][0]["in_reply_to_message_id"] == "m1"
    assert body["proposed_drafts"][0]["requires_approval"] is True


def test_digest_endpoint_requires_authentication() -> None:
    transport = httpx.ASGITransport(app=app)

    async def call() -> httpx.Response:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/actions/gmail/digest/preview",
                json={"lookback_hours": 24},
            )

    import asyncio

    response = asyncio.run(call())
    assert response.status_code in (401, 403)


class _FakeCredentials:
    def __init__(
        self,
        *,
        token: str = "token-1",
        valid: bool = True,
        expired: bool = False,
        refresh_token: str | None = None,
    ) -> None:
        self.token = token
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.refresh_calls = 0

    def refresh(self, request: object) -> None:
        del request
        self.refresh_calls += 1
        self.token = "token-refreshed"
        self.expired = False
        self.valid = True

    def to_json(self) -> str:
        return '{"token":"token-refreshed"}'


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeGmailClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __enter__(self) -> _FakeGmailClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: list[tuple[str, str]],
    ) -> _FakeResponse:
        self.calls.append({"url": url, "headers": headers, "params": params})
        if url.endswith("/messages"):
            return _FakeResponse({"messages": [{"id": "m-1"}, {"id": "m-2"}]})
        if url.endswith("/messages/m-1"):
            return _FakeResponse(
                {
                    "id": "m-1",
                    "threadId": "t-1",
                    "snippet": "first",
                    "labelIds": ["INBOX"],
                    "internalDate": "1767139200000",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Alice <alice@example.com>"},
                            {"name": "Subject", "value": "Hello"},
                        ]
                    },
                }
            )
        return _FakeResponse(
            {
                "id": "m-2",
                "threadId": "t-2",
                "snippet": "second",
                "labelIds": ["STARRED"],
                "payload": {
                    "headers": [
                        {"name": "From", "value": "bob@partner.co"},
                        {"name": "Subject", "value": "Question"},
                        {"name": "Date", "value": "Tue, 12 May 2026 12:00:00 +0000"},
                    ]
                },
            }
        )


class _FakeGmailLabelClient:
    def __init__(self, labels: list[dict[str, str]]) -> None:
        self._labels = labels
        self.calls: list[dict[str, object]] = []

    def __enter__(self) -> _FakeGmailLabelClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: list[tuple[str, str]],
    ) -> _FakeResponse:
        self.calls.append({"url": url, "headers": headers, "params": params})
        if url.endswith("/labels"):
            return _FakeResponse({"labels": self._labels})
        if url.endswith("/messages"):
            return _FakeResponse({"messages": []})
        return _FakeResponse({})


def test_gmail_rest_reader_fetches_recent_messages(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    client = _FakeGmailClient()
    reader = GmailRestReader(
        token_path=token_path,
        credentials_loader=lambda _: _FakeCredentials(token="token-live"),
        http_client_factory=lambda: client,
    )

    messages = reader.fetch_recent(
        lookback_hours=24,
        max_messages=2,
        labels=["INBOX"],
    )

    assert [msg["id"] for msg in messages] == ["m-1", "m-2"]
    assert messages[0]["sender"] == "Alice <alice@example.com>"
    assert messages[1]["subject"] == "Question"
    assert client.calls[0]["headers"] == {"Authorization": "Bearer token-live"}
    assert ("q", "newer_than:24h") in client.calls[0]["params"]
    assert ("labelIds", "INBOX") in client.calls[0]["params"]


def test_gmail_rest_reader_refreshes_and_persists_token(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    credentials = _FakeCredentials(
        token="old",
        expired=True,
        valid=True,
        refresh_token="refresh",
    )
    reader = GmailRestReader(
        token_path=token_path,
        credentials_loader=lambda _: credentials,
        http_client_factory=lambda: _FakeGmailClient(),
    )

    reader.fetch_recent(lookback_hours=1, max_messages=1, labels=[])

    assert credentials.refresh_calls == 1
    assert "token-refreshed" in token_path.read_text(encoding="utf-8")


def test_gmail_rest_reader_missing_token_raises_clear_error(tmp_path: Path) -> None:
    token_path = tmp_path / "missing-token.json"
    reader = GmailRestReader(token_path=token_path)

    with pytest.raises(GmailReaderError, match="token not found") as exc_info:
        reader.fetch_recent(lookback_hours=1, max_messages=1, labels=[])

    message = str(exc_info.value)
    assert str(tmp_path) not in message
    assert str(token_path) not in message


def test_gmail_label_reader_missing_token_does_not_expose_path(tmp_path: Path) -> None:
    token_path = tmp_path / "missing-token.json"
    reader = GmailLabelReader(token_path=token_path, label_name="TODOS")

    with pytest.raises(GmailReaderError, match="token not found") as exc_info:
        reader.fetch_recent(max_messages=1)

    message = str(exc_info.value)
    assert str(tmp_path) not in message
    assert str(token_path) not in message


def test_gmail_label_reader_resolves_custom_label_name_to_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    client = _FakeGmailLabelClient(labels=[{"id": "Label_123", "name": "TODOS"}])
    reader = GmailLabelReader(token_path=token_path, label_name="TODOS")
    monkeypatch.setattr(reader, "_load_credentials", lambda: SimpleNamespace(token="token-live"))
    monkeypatch.setattr(gmail_label_reader_module.httpx, "Client", lambda **_: client)

    assert reader.fetch_recent(max_messages=1) == []

    assert ("labelIds", "Label_123") in client.calls[1]["params"]
    assert not any(key == "q" for key, _value in client.calls[1]["params"])


def test_gmail_label_reader_falls_back_to_label_query_when_label_name_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    client = _FakeGmailLabelClient(labels=[{"id": "INBOX", "name": "INBOX"}])
    reader = GmailLabelReader(token_path=token_path, label_name="TODOS")
    monkeypatch.setattr(reader, "_load_credentials", lambda: SimpleNamespace(token="token-live"))
    monkeypatch.setattr(gmail_label_reader_module.httpx, "Client", lambda **_: client)

    assert reader.fetch_recent(max_messages=1) == []

    assert ("q", "in:anywhere -in:trash") in client.calls[1]["params"]
    assert ("includeSpamTrash", "true") in client.calls[1]["params"]
    assert not any(key == "labelIds" for key, _value in client.calls[1]["params"])


def test_gmail_label_reader_includes_spam_when_label_is_spam(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    client = _FakeGmailLabelClient(labels=[{"id": "SPAM", "name": "SPAM"}])
    reader = GmailLabelReader(token_path=token_path, label_name="SPAM")
    monkeypatch.setattr(reader, "_load_credentials", lambda: SimpleNamespace(token="token-live"))
    monkeypatch.setattr(gmail_label_reader_module.httpx, "Client", lambda **_: client)

    assert reader.fetch_recent(max_messages=1) == []

    assert ("labelIds", "SPAM") in client.calls[1]["params"]
    assert ("includeSpamTrash", "true") in client.calls[1]["params"]


def test_digest_reader_errors_are_blocked_and_redacted() -> None:
    class _ExplodingReader:
        def fetch_recent(self, **kwargs: object) -> list[dict[str, object]]:
            del kwargs
            msg = "access_token abc123SECRET"
            raise GmailReaderError(msg)

    service = GmailDigestService(
        reader=_ExplodingReader(),
        app_settings=Settings(
            gmail_read_enabled=True,
            gmail_client_id="cid",
            gmail_client_secret="csecret",  # pragma: allowlist secret
        ),
    )

    preview = service.build_preview(GmailDigestRequest())

    assert preview.status == "blocked"
    assert "abc123SECRET" not in (preview.reason or "")
    assert "[REDACTED]" in (preview.reason or "")

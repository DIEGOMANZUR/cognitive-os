from __future__ import annotations

import imaplib
import smtplib
from typing import Any

from cognitive_os.mail.imap_client import ImapMailClient
from cognitive_os.mail.smtp_client import SmtpMailClient


def test_imap_client_uses_configured_timeout(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeImap:
        def __init__(self, host: str, port: int, *, timeout: int) -> None:
            captured.update(host=host, port=port, timeout=timeout)

        def __enter__(self) -> FakeImap:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def login(self, _username: str, _password: str) -> None:
            return None

        def logout(self) -> None:
            return None

        def select(self, _folder: str, *, readonly: bool) -> tuple[str, list[bytes]]:
            captured["readonly"] = readonly
            return "OK", []

        def uid(self, *_args: str) -> tuple[str, list[bytes]]:
            return "OK", []

    monkeypatch.setattr(imaplib, "IMAP4_SSL", FakeImap)

    client = ImapMailClient(
        host="imap.example.test",
        port=993,
        username="user@example.test",
        password="secret",  # pragma: allowlist secret
        timeout_seconds=12,
    )

    assert client.fetch_recent(folders=["INBOX"], max_per_folder=1) == []
    assert captured["timeout"] == 12
    assert captured["readonly"] is True


def test_smtp_client_uses_configured_timeout(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeSmtp:
        def __init__(self, host: str, port: int, *, context: Any, timeout: int) -> None:
            del context
            captured.update(host=host, port=port, timeout=timeout)

        def __enter__(self) -> FakeSmtp:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def login(self, _username: str, _password: str) -> None:
            return None

        def send_message(self, _message: object) -> None:
            captured["sent"] = True

    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSmtp)

    client = SmtpMailClient(
        host="smtp.example.test",
        port=465,
        username="user@example.test",
        password="secret",  # pragma: allowlist secret
        timeout_seconds=14,
    )

    client.send_reply(
        from_address="user@example.test",
        to_address="client@example.test",
        subject="Hello",
        body_text="Body",
    )
    assert captured["timeout"] == 14
    assert captured["sent"] is True

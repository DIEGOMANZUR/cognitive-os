from __future__ import annotations

import imaplib
from dataclasses import dataclass
from datetime import UTC, datetime
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.policy import default
from email.utils import getaddresses, parsedate_to_datetime


@dataclass(frozen=True)
class RawMailMessage:
    folder: str
    uid: str
    message_id_header: str | None
    sender: str
    recipients: list[str]
    subject: str | None
    snippet: str | None
    body_text: str | None
    body_html: str | None
    received_at: datetime | None
    thread_key: str | None


class ImapMailError(RuntimeError):
    """Raised when IMAP cannot fetch a mailbox safely."""


class ImapMailClient:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        timeout_seconds: int = 30,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._timeout_seconds = timeout_seconds

    def fetch_recent(self, *, folders: list[str], max_per_folder: int) -> list[RawMailMessage]:
        messages: list[RawMailMessage] = []
        with imaplib.IMAP4_SSL(self._host, self._port, timeout=self._timeout_seconds) as client:
            client.login(self._username, self._password)
            for folder in folders:
                messages.extend(self._fetch_folder(client, folder, max_per_folder=max_per_folder))
            client.logout()
        return messages

    def _fetch_folder(
        self,
        client: imaplib.IMAP4_SSL,
        folder: str,
        *,
        max_per_folder: int,
    ) -> list[RawMailMessage]:
        status, _ = client.select(_quote_mailbox(folder), readonly=True)
        if status != "OK":
            return []
        status, payload = client.uid("SEARCH", "ALL")
        if status != "OK" or not payload or not payload[0]:
            return []
        raw_uids = payload[0].decode("ascii", errors="ignore").split()
        selected_uids = raw_uids[-max_per_folder:]
        results: list[RawMailMessage] = []
        for uid in selected_uids:
            status, fetched = client.uid("FETCH", uid, "(RFC822)")
            if status != "OK":
                continue
            raw_bytes = _first_message_bytes(fetched)
            if raw_bytes is None:
                continue
            results.append(_parse_message(folder=folder, uid=uid, raw_bytes=raw_bytes))
        return results


def _quote_mailbox(folder: str) -> str:
    if folder.startswith('"') and folder.endswith('"'):
        return folder
    escaped = folder.replace('"', r"\"")
    return f'"{escaped}"'


def _first_message_bytes(payload: list[bytes | tuple[bytes, bytes]]) -> bytes | None:
    for item in payload:
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], bytes):
            return item[1]
    return None


def _parse_message(*, folder: str, uid: str, raw_bytes: bytes) -> RawMailMessage:
    msg = message_from_bytes(raw_bytes, policy=default)
    sender = _header(msg, "From") or ""
    recipients = [addr for _, addr in getaddresses([_header(msg, "To") or ""])]
    subject = _header(msg, "Subject")
    body_text, body_html = _extract_bodies(msg)
    snippet = _snippet(body_text or body_html)
    received_at = _parse_date(_header(msg, "Date"))
    message_id = _header(msg, "Message-ID")
    thread_key = _thread_key(msg, subject)
    return RawMailMessage(
        folder=folder,
        uid=uid,
        message_id_header=message_id,
        sender=sender,
        recipients=recipients,
        subject=subject,
        snippet=snippet,
        body_text=body_text,
        body_html=body_html,
        received_at=received_at,
        thread_key=thread_key,
    )


def _header(msg: Message, name: str) -> str | None:
    value = msg.get(name)
    if value is None:
        return None
    try:
        return str(make_header(decode_header(str(value)))).strip()
    except Exception:
        return str(value).strip()


def _extract_bodies(msg: Message) -> tuple[str | None, str | None]:
    text_parts: list[str] = []
    html_parts: list[str] = []
    if isinstance(msg, EmailMessage):
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                continue
            content_type = part.get_content_type()
            try:
                content = part.get_content()
            except Exception:
                continue
            if not isinstance(content, str):
                continue
            if content_type == "text/plain":
                text_parts.append(content)
            elif content_type == "text/html":
                html_parts.append(content)
    text = "\n".join(p.strip() for p in text_parts if p.strip()) or None
    html = "\n".join(p.strip() for p in html_parts if p.strip()) or None
    return text, html


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _thread_key(msg: Message, subject: str | None) -> str | None:
    refs = _header(msg, "References") or _header(msg, "In-Reply-To")
    if refs:
        return refs.split()[0][:256]
    if subject:
        lowered = subject.lower().removeprefix("re:").removeprefix("fw:").strip()
        return lowered[:256] or None
    return None


def _snippet(value: str | None, *, limit: int = 500) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit]

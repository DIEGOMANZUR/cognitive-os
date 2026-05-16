from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, cast

import httpx

from cognitive_os.actions.gmail_digest import GmailReaderError
from cognitive_os.mail.imap_client import RawMailMessage

GMAIL_API_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailLabelReader:
    def __init__(self, *, token_path: Path, label_name: str, timeout_seconds: float = 15.0) -> None:
        self._token_path = token_path
        self._label_name = label_name
        self._timeout_seconds = timeout_seconds

    def fetch_recent(self, *, max_messages: int) -> list[RawMailMessage]:
        credentials = self._load_credentials()
        headers = {"Authorization": f"Bearer {credentials.token}"}
        with httpx.Client(timeout=self._timeout_seconds) as client:
            label_id = self._resolve_label_id(client, headers=headers)
            listed = self._gmail_get(
                client,
                f"{GMAIL_API_BASE_URL}/messages",
                headers=headers,
                params=[("maxResults", str(max_messages)), ("labelIds", label_id)],
            )
            raw_items = listed.get("messages") or []
            if not isinstance(raw_items, list):
                raise GmailReaderError("Gmail list response had unexpected shape.")
            messages: list[RawMailMessage] = []
            for raw_item in raw_items[:max_messages]:
                if not isinstance(raw_item, dict):
                    continue
                message_id = str(raw_item.get("id") or "")
                if not message_id:
                    continue
                payload = self._gmail_get(
                    client,
                    f"{GMAIL_API_BASE_URL}/messages/{message_id}",
                    headers=headers,
                    params=[
                        ("format", "metadata"),
                        ("metadataHeaders", "From"),
                        ("metadataHeaders", "To"),
                        ("metadataHeaders", "Subject"),
                        ("metadataHeaders", "Date"),
                        ("metadataHeaders", "Message-ID"),
                        ("metadataHeaders", "References"),
                        ("metadataHeaders", "In-Reply-To"),
                    ],
                )
                messages.append(self._normalize_message(payload, folder=self._label_name))
            return messages

    def _load_credentials(self) -> Any:
        if not self._token_path.exists():
            raise GmailReaderError(f"Gmail token not found at {self._token_path}")
        from google.oauth2.credentials import Credentials

        loader = cast(Any, Credentials.from_authorized_user_file)
        credentials = loader(str(self._token_path))
        if bool(getattr(credentials, "expired", False)) and getattr(
            credentials,
            "refresh_token",
            None,
        ):
            from google.auth.transport.requests import Request

            credentials.refresh(Request())
            self._token_path.write_text(credentials.to_json(), encoding="utf-8")
        if not bool(getattr(credentials, "valid", False)) or not getattr(
            credentials, "token", None
        ):
            raise GmailReaderError("Gmail token is invalid or missing an access token.")
        return credentials

    def _resolve_label_id(self, client: httpx.Client, *, headers: dict[str, str]) -> str:
        data = self._gmail_get(client, f"{GMAIL_API_BASE_URL}/labels", headers=headers, params=[])
        labels = data.get("labels") or []
        if not isinstance(labels, list):
            raise GmailReaderError("Gmail labels response had unexpected shape.")
        wanted = self._label_name.casefold()
        for label in labels:
            if not isinstance(label, dict):
                continue
            if str(label.get("name") or "").casefold() == wanted:
                return str(label.get("id") or "")
        return self._label_name

    @staticmethod
    def _gmail_get(
        client: httpx.Client,
        url: str,
        *,
        headers: dict[str, str],
        params: list[tuple[str, str]],
    ) -> dict[str, object]:
        response = client.get(url, headers=headers, params=cast(Any, params))
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise GmailReaderError("Gmail API returned an unexpected JSON shape.")
        return data

    @staticmethod
    def _normalize_message(payload: dict[str, object], *, folder: str) -> RawMailMessage:
        raw_payload = payload.get("payload")
        headers = raw_payload.get("headers") if isinstance(raw_payload, dict) else []
        sender = _header(headers, "From") or ""
        subject = _header(headers, "Subject")
        date_header = _header(headers, "Date")
        received_at = _parse_date(date_header)
        message_id = _header(headers, "Message-ID")
        refs = _header(headers, "References") or _header(headers, "In-Reply-To")
        snippet = str(payload.get("snippet") or "") or None
        return RawMailMessage(
            folder=folder,
            uid=str(payload.get("id") or ""),
            message_id_header=message_id,
            sender=sender,
            recipients=[_header(headers, "To") or ""],
            subject=subject,
            snippet=snippet,
            body_text=None,
            body_html=None,
            received_at=received_at,
            thread_key=(
                refs.split()[0][:256] if refs else str(payload.get("threadId") or "") or None
            ),
        )


def _header(headers: object, name: str) -> str | None:
    if not isinstance(headers, list):
        return None
    for item in headers:
        if isinstance(item, dict) and str(item.get("name") or "").casefold() == name.casefold():
            return str(item.get("value") or "")
    return None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

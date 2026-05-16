from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Protocol, cast

import httpx

from cognitive_os.actions.schemas import (
    GmailDigestMessage,
    GmailDigestPreview,
    GmailDigestProposedDraft,
    GmailDigestRequest,
    GmailDigestSender,
)
from cognitive_os.core.config import Settings, settings

EMAIL_RE = re.compile(r"<?([^<>\s]+@[^<>\s]+)>?")
TOP_MESSAGES_LIMIT = 20
TOP_SENDERS_LIMIT = 10
SNIPPET_MAX = 280
BODY_PREVIEW_MAX = 400
GMAIL_API_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
SECRET_TEXT_RE = re.compile(
    r"(?i)\b(?:authorization|bearer|access_token|refresh_token|client_secret|token)"
    r"\b\s*[:=]?\s*[A-Za-z0-9._~+/=-]+"
)


class GmailReaderError(RuntimeError):
    """Raised when the read-only Gmail transport cannot produce a safe preview."""


class GmailReader(Protocol):
    def fetch_recent(
        self,
        *,
        lookback_hours: int,
        max_messages: int,
        labels: list[str],
    ) -> list[dict[str, object]]: ...


class FakeGmailReader:
    def __init__(self, messages: list[dict[str, object]]) -> None:
        self._messages = list(messages)
        self.calls: list[dict[str, object]] = []

    def fetch_recent(
        self,
        *,
        lookback_hours: int,
        max_messages: int,
        labels: list[str],
    ) -> list[dict[str, object]]:
        self.calls.append(
            {
                "lookback_hours": lookback_hours,
                "max_messages": max_messages,
                "labels": list(labels),
            }
        )
        return list(self._messages[:max_messages])


class GmailRestReader:
    """Read-only Gmail API reader using an existing OAuth `token.json`.

    The project intentionally does not run a browser OAuth flow from the backend:
    that was brittle for the operator and easy to hang. Instead, this reader
    consumes the standard Google authorized-user token file under
    `GMAIL_TOKEN_DIR/token.json`, refreshes it when possible, and calls Gmail's
    REST API with `gmail.readonly`.
    """

    def __init__(
        self,
        *,
        token_path: Path,
        timeout_seconds: float = 15.0,
        credentials_loader: Any | None = None,
        http_client_factory: Any | None = None,
    ) -> None:
        self._token_path = token_path
        self._timeout_seconds = timeout_seconds
        self._credentials_loader = credentials_loader or self._default_credentials_loader
        self._http_client_factory = http_client_factory or self._default_http_client_factory

    @classmethod
    def from_settings(cls, app_settings: Settings) -> GmailRestReader:
        return cls(token_path=app_settings.gmail_token_dir.expanduser() / "token.json")

    def fetch_recent(
        self,
        *,
        lookback_hours: int,
        max_messages: int,
        labels: list[str],
    ) -> list[dict[str, object]]:
        credentials = self._load_credentials()
        headers = {"Authorization": f"Bearer {credentials.token}"}
        query = f"newer_than:{lookback_hours}h"
        params: list[tuple[str, str]] = [
            ("maxResults", str(max_messages)),
            ("q", query),
        ]
        for label in labels:
            params.append(("labelIds", label))

        with self._http_client_factory() as client:
            listed = self._gmail_get(
                client,
                f"{GMAIL_API_BASE_URL}/messages",
                headers=headers,
                params=params,
            )
            raw_items = listed.get("messages") or []
            if not isinstance(raw_items, list):
                msg = "Gmail list response had unexpected shape."
                raise GmailReaderError(msg)

            messages: list[dict[str, object]] = []
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
                        ("metadataHeaders", "Subject"),
                        ("metadataHeaders", "Date"),
                    ],
                )
                messages.append(_normalize_gmail_api_message(payload))
        return messages

    def _load_credentials(self) -> Any:
        if not self._token_path.exists():
            msg = (
                f"Gmail token not found at {self._token_path}. Create token.json "
                "with the readonly scope before enabling Gmail digest."
            )
            raise GmailReaderError(msg)
        credentials = self._credentials_loader(self._token_path)
        if bool(getattr(credentials, "expired", False)) and getattr(
            credentials,
            "refresh_token",
            None,
        ):
            self._refresh_credentials(credentials)
        has_valid_token = bool(getattr(credentials, "valid", False)) and bool(
            getattr(credentials, "token", None)
        )
        if not has_valid_token:
            msg = "Gmail token is invalid or missing an access token."
            raise GmailReaderError(msg)
        return credentials

    @staticmethod
    def _default_credentials_loader(token_path: Path) -> Any:
        from google.oauth2.credentials import Credentials

        loader = cast(Any, Credentials.from_authorized_user_file)
        return loader(str(token_path))

    def _refresh_credentials(self, credentials: Any) -> None:
        from google.auth.transport.requests import Request

        credentials.refresh(Request())
        try:
            self._token_path.write_text(credentials.to_json(), encoding="utf-8")
        except OSError as exc:
            msg = f"Could not persist refreshed Gmail token: {exc}"
            raise GmailReaderError(msg) from exc

    def _default_http_client_factory(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout_seconds)

    @staticmethod
    def _gmail_get(
        client: httpx.Client,
        url: str,
        *,
        headers: dict[str, str],
        params: list[tuple[str, str]],
    ) -> dict[str, object]:
        try:
            response = client.get(url, headers=headers, params=cast(Any, params))
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            msg = f"Gmail API request failed: {_redact_reader_error(str(exc))}"
            raise GmailReaderError(msg) from exc
        except ValueError as exc:
            msg = "Gmail API returned invalid JSON."
            raise GmailReaderError(msg) from exc
        if not isinstance(data, dict):
            msg = "Gmail API returned an unexpected JSON shape."
            raise GmailReaderError(msg)
        return data


def _redact_address(raw: str) -> tuple[str, str]:
    match = EMAIL_RE.search(raw or "")
    if not match:
        return ("unknown.invalid", "unknown@unknown.invalid")
    email = match.group(1)
    local, _, domain = email.partition("@")
    if not domain:
        return ("unknown.invalid", "unknown@unknown.invalid")
    if len(local) <= 2:
        redacted_local = "*" * len(local)
    else:
        redacted_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return (domain, f"{redacted_local}@{domain}")


def _redact_reader_error(value: str) -> str:
    return SECRET_TEXT_RE.sub("[REDACTED]", value)


def _truncate(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "\u2026"


def _coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _header_value(headers: object, name: str) -> str | None:
    if not isinstance(headers, list):
        return None
    for header in headers:
        if not isinstance(header, dict):
            continue
        if str(header.get("name") or "").casefold() == name.casefold():
            value = header.get("value")
            return str(value) if value is not None else None
    return None


def _normalize_gmail_api_message(payload: dict[str, object]) -> dict[str, object]:
    body = payload.get("payload")
    headers = body.get("headers") if isinstance(body, dict) else None
    internal_date = payload.get("internalDate")
    received_at: datetime | None = None
    if isinstance(internal_date, str) and internal_date.isdigit():
        received_at = datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC)
    if received_at is None:
        date_header = _header_value(headers, "Date")
        if date_header:
            try:
                parsed = parsedate_to_datetime(date_header)
                received_at = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except (TypeError, ValueError, IndexError, OverflowError):
                received_at = None
    label_ids = payload.get("labelIds")
    labels = [str(label) for label in label_ids] if isinstance(label_ids, list) else []
    return {
        "id": str(payload.get("id") or ""),
        "thread_id": str(payload.get("threadId") or "") or None,
        "sender": _header_value(headers, "From") or "",
        "subject": _header_value(headers, "Subject"),
        "snippet": str(payload.get("snippet") or ""),
        "labels": labels,
        "received_at": received_at,
    }


class GmailDigestService:
    def __init__(
        self,
        reader: GmailReader | None = None,
        app_settings: Settings = settings,
    ) -> None:
        self._reader = reader
        self._settings = app_settings

    def build_preview(self, request: GmailDigestRequest) -> GmailDigestPreview:
        scopes = list(self._settings.gmail_scopes)
        if not self._settings.gmail_read_enabled:
            return GmailDigestPreview(
                status="blocked",
                lookback_hours=request.lookback_hours,
                max_messages=request.max_messages,
                scopes=scopes,
                requires_approval=False,
                dry_run_only=True,
                reason="Gmail read is disabled.",
            )
        if self._reader is None:
            return GmailDigestPreview(
                status="blocked",
                lookback_hours=request.lookback_hours,
                max_messages=request.max_messages,
                scopes=scopes,
                requires_approval=False,
                dry_run_only=True,
                reason="No Gmail reader configured for digest preview.",
            )

        try:
            raw_messages = self._reader.fetch_recent(
                lookback_hours=request.lookback_hours,
                max_messages=request.max_messages,
                labels=list(request.labels),
            )
        except Exception as exc:
            return GmailDigestPreview(
                status="blocked",
                lookback_hours=request.lookback_hours,
                max_messages=request.max_messages,
                scopes=scopes,
                requires_approval=False,
                dry_run_only=True,
                reason=f"Gmail reader failed: {_redact_reader_error(str(exc))}",
            )

        cutoff = datetime.now(tz=UTC) - timedelta(hours=request.lookback_hours)
        warnings: list[str] = []
        normalized: list[GmailDigestMessage] = []
        senders_acc: dict[str, list[GmailDigestMessage]] = defaultdict(list)
        domain_counter: Counter[str] = Counter()

        for raw in raw_messages:
            received = _coerce_datetime(raw.get("received_at"))
            if received is not None and received < cutoff:
                continue
            sender_raw = str(raw.get("sender") or raw.get("from") or "")
            domain, redacted = _redact_address(sender_raw)
            message_id = str(raw.get("id") or raw.get("message_id") or "")
            if not message_id:
                warnings.append("skipped_message_without_id")
                continue
            raw_labels = raw.get("labels") or []
            label_values: list[str] = []
            if isinstance(raw_labels, (list, tuple)):
                label_values = [str(label) for label in raw_labels]
            msg = GmailDigestMessage(
                message_id=message_id,
                thread_id=(str(raw.get("thread_id")) if raw.get("thread_id") else None),
                sender_domain=domain,
                sender_redacted=redacted,
                subject=_truncate(
                    str(raw["subject"]) if raw.get("subject") is not None else None,
                    300,
                ),
                snippet=_truncate(
                    str(raw["snippet"]) if raw.get("snippet") is not None else None,
                    SNIPPET_MAX,
                ),
                labels=label_values,
                received_at=received,
            )
            normalized.append(msg)
            senders_acc[redacted].append(msg)
            domain_counter[domain] += 1

        senders: list[GmailDigestSender] = []
        for address_redacted, msgs in senders_acc.items():
            latest = max(
                msgs,
                key=lambda m: m.received_at or datetime.min.replace(tzinfo=UTC),
            )
            senders.append(
                GmailDigestSender(
                    domain=latest.sender_domain,
                    address_redacted=address_redacted,
                    message_count=len(msgs),
                    latest_subject=latest.subject,
                )
            )
        senders.sort(key=lambda s: (-s.message_count, s.address_redacted))
        senders = senders[:TOP_SENDERS_LIMIT]

        normalized.sort(
            key=lambda m: m.received_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        top_messages = normalized[:TOP_MESSAGES_LIMIT]

        proposed_drafts: list[GmailDigestProposedDraft] = []
        if request.include_proposed_drafts:
            seen_senders: set[str] = set()
            for msg in top_messages:
                if msg.sender_redacted in seen_senders:
                    continue
                seen_senders.add(msg.sender_redacted)
                rationale = (
                    f"Pending reply suggestion for {msg.sender_redacted}; "
                    f"based on subject and snippet heuristics."
                )
                body_lines = [
                    f"Hola, gracias por tu mensaje sobre: {msg.subject or '(sin asunto)'}.",
                    "Confirmo recibido y respondo con detalle en breve.",
                ]
                proposed_drafts.append(
                    GmailDigestProposedDraft(
                        in_reply_to_message_id=msg.message_id,
                        sender_redacted=msg.sender_redacted,
                        subject_hint=msg.subject,
                        rationale=rationale,
                        body_preview=_truncate("\n".join(body_lines), BODY_PREVIEW_MAX) or "",
                    )
                )
                if len(proposed_drafts) >= TOP_SENDERS_LIMIT:
                    break

        if not normalized:
            warnings.append("no_messages_in_window")

        return GmailDigestPreview(
            status="ok",
            lookback_hours=request.lookback_hours,
            max_messages=request.max_messages,
            scopes=scopes,
            requires_approval=False,
            dry_run_only=True,
            total_messages=len(normalized),
            senders=senders,
            top_messages=top_messages,
            proposed_drafts=proposed_drafts,
            warnings=warnings,
        )


def render_gmail_digest_telegram(
    preview: GmailDigestPreview, *, headline: str = "Gmail digest read-only"
) -> str:
    """Compact Markdown for Telegram bots (caller truncates externally if needed)."""
    if preview.status != "ok":
        reason = preview.reason or "sin detalle"
        return f"*{headline}*\nestado `{preview.status}` — {reason}"
    lines: list[str] = [
        f"*{headline}* (`{preview.lookback_hours}h`)",
        f"total mensajes agrupados: *{preview.total_messages}*",
    ]
    if preview.top_messages:
        lines.append("")
        lines.append("*Top hilos:*")
        for msg in preview.top_messages[:12]:
            subj = msg.subject or "(sin asunto)"
            lines.append(
                f"- `{msg.sender_redacted}` — {subj[:80]}"
                + (f"\n  _{msg.snippet[:120]}_" if msg.snippet else "")
            )
    elif preview.senders:
        lines.append("")
        lines.append("*Remitentes:*")
        for sender in preview.senders[:10]:
            latest = sender.latest_subject or ""
            lines.append(f"- `{sender.address_redacted}` ×{sender.message_count}: {latest[:80]}")
    if preview.warnings:
        lines.append("")
        lines.append("_warnings_: " + ", ".join(sorted(set(preview.warnings))))
    return "\n".join(lines)

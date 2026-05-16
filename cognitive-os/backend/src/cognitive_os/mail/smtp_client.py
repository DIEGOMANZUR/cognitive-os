from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage


class SmtpMailError(RuntimeError):
    """Raised when SMTP send fails."""


class SmtpMailClient:
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

    def send_reply(
        self,
        *,
        from_address: str,
        to_address: str,
        subject: str,
        body_text: str,
        in_reply_to: str | None = None,
        references: str | None = None,
    ) -> None:
        msg = EmailMessage()
        msg["From"] = from_address
        msg["To"] = to_address
        msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references or in_reply_to:
            msg["References"] = " ".join(x for x in (references, in_reply_to) if x)
        msg.set_content(body_text)

        try:
            if self._port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    self._host,
                    self._port,
                    context=context,
                    timeout=self._timeout_seconds,
                ) as smtp:
                    smtp.login(self._username, self._password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(self._host, self._port, timeout=self._timeout_seconds) as smtp:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.login(self._username, self._password)
                    smtp.send_message(msg)
        except Exception as exc:
            raise SmtpMailError(str(exc)) from exc

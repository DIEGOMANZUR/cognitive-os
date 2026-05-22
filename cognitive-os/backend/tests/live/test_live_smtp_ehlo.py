"""Live smoke: the GoDaddy mailbox answers IMAP + SMTP handshakes.

Strictly read-only: an IMAP SSL login (then logout) and an SMTP EHLO (then
quit). No message is fetched, sent, drafted or deleted. This proves the mail
credentials and hosts are valid before the digest job depends on them.
"""

from __future__ import annotations

import contextlib
import smtplib

import pytest

from cognitive_os.core.config import settings

pytestmark = pytest.mark.live_readonly


def _mail_configured() -> bool:
    if not (settings.mail_enabled and settings.mail_godaddy_enabled):
        return False
    password = settings.mail_godaddy_password.get_secret_value()
    return bool(settings.mail_godaddy_username) and password not in {"", "CHANGEME"}


def test_live_godaddy_imap_login() -> None:
    if not _mail_configured():
        pytest.skip("GoDaddy mail not configured")

    from cognitive_os.core.health import _probe_godaddy_imap

    # Reuses the exact probe behind POST /health/verify — one SSL login + logout.
    assert _probe_godaddy_imap() is True


def test_live_godaddy_smtp_ehlo() -> None:
    if not _mail_configured():
        pytest.skip("GoDaddy mail not configured")

    client = smtplib.SMTP_SSL(
        settings.mail_godaddy_smtp_host,
        settings.mail_godaddy_smtp_port,
        timeout=settings.http_timeout_seconds,
    )
    try:
        code, _ = client.ehlo()
        assert code == 250, f"SMTP EHLO returned {code}, expected 250"
    finally:
        with contextlib.suppress(Exception):
            client.quit()

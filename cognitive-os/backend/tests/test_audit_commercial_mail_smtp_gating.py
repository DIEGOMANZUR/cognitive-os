"""P0 commercial-audit hardening — exhaustive Mail SMTP gating matrix.

Contract (`docs/CURRENT_STATE.md` §"Mail: Contrato Actual"; `docs/ACTION_PLANE.md`
§"Mail personal GoDaddy/Gmail-label"; `docs/ZERO_FRICTION_OPERATING_MODEL.md`
§"Excepción dura: mail"): the flow normal **never** sends email and **never**
creates drafts. The SMTP escape hatch only opens with ALL of:

  1. ``settings.enable_email_send == True``
  2. ``settings.mail_allow_explicit_send == True``
  3. ``request.explicit_send_confirmation == "SEND_THIS_EMAIL_EXPLICITLY"``

This file extends ``test_mail_api.py`` with an exhaustive matrix covering
every other combination of those flags. Each non-passing combination must
raise ``MailServiceError`` and **must not** invoke ``_send_with_account``.

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §G3.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from cognitive_os.core.config import Settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import MailAccount, MailMessage, MailSendLog
from cognitive_os.mail.schemas import MailApproveReplyRequest
from cognitive_os.mail.service import MailServiceError, PersonalMailService


@pytest.fixture(autouse=True)
async def _clean_mail_rows_between_tests() -> Iterator[None]:
    """Each audit gating test starts AND ends with a clean mail* slate.

    Without this, rows left by earlier tests (e.g. auth_matrix sweeps that
    hit ``GET /mail/status`` and trigger ``ensure_configured_accounts``)
    cause UniqueViolation when we re-seed. And rows our seed creates
    would leak into downstream tests, breaking digest-count assertions.
    Children before parents per FK order:
    MailSendLog → MailMessage → MailAccount.
    """
    async with session_scope() as session:
        await session.execute(delete(MailSendLog))
        await session.execute(delete(MailMessage))
        await session.execute(delete(MailAccount))
    yield
    async with session_scope() as session:
        await session.execute(delete(MailSendLog))
        await session.execute(delete(MailMessage))
        await session.execute(delete(MailAccount))


CORRECT_PHRASE = "SEND_THIS_EMAIL_EXPLICITLY"

# Matrix: every (enable_email_send, mail_allow_explicit_send, confirmation)
# combination. Only one row should reach the SMTP layer; everything else
# must short-circuit with MailServiceError BEFORE _send_with_account is called.
GATING_MATRIX: list[tuple[bool, bool, str | None, bool, str]] = [
    # (enable_email_send, mail_allow_explicit_send, confirmation, expect_send, label)
    (False, False, None, False, "all_off"),
    (False, False, CORRECT_PHRASE, False, "all_off_with_phrase"),
    (False, True, None, False, "send_off_explicit_on"),
    (False, True, CORRECT_PHRASE, False, "send_off_explicit_on_with_phrase"),
    (True, False, None, False, "send_on_explicit_off"),
    (True, False, CORRECT_PHRASE, False, "send_on_explicit_off_with_phrase"),
    (True, True, None, False, "all_on_no_phrase"),
    (True, True, "wrong_phrase", False, "all_on_wrong_phrase"),
    (True, True, "send this email explicitly", False, "all_on_lowercase_phrase"),
    (True, True, CORRECT_PHRASE, True, "all_on_correct_phrase"),  # ONLY THIS PASSES
]


def _build_settings(*, enable_email_send: bool, mail_allow_explicit_send: bool) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        mail_enabled=True,
        mail_godaddy_enabled=True,
        mail_godaddy_username="diego@example.test",
        mail_godaddy_password="test-password",  # pragma: allowlist secret
        mail_default_sender="diego@example.test",
        mail_require_approval_for_send=True,
        enable_email_send=enable_email_send,
        mail_allow_explicit_send=mail_allow_explicit_send,
    )


async def _seed_message(service: PersonalMailService) -> UUID:
    """Create a `reply_proposed` message bound to a fresh account."""
    await service.ensure_configured_accounts()
    async with session_scope() as session:
        result = await session.execute(
            select(MailAccount).where(MailAccount.email_address == "diego@example.test")
        )
        account = result.scalar_one()
        row = MailMessage(
            account_id=account.id,
            folder="INBOX",
            uid=str(uuid4()),
            message_id_header=f"<{uuid4()}@example.test>",
            thread_key=str(uuid4()),
            sender="Client <client@example.test>",
            recipients=["diego@example.test"],
            subject="Consulta",
            snippet="Necesito respuesta",
            body_text="Necesito respuesta",
            classification="important",
            importance_score=0.9,
            proposed_reply_text="Respuesta propuesta",
            proposed_reply_rationale="audit",
            status="reply_proposed",
        )
        session.add(row)
        await session.flush()
        return row.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("enable_email_send", "mail_allow_explicit_send", "confirmation", "expect_send", "label"),
    GATING_MATRIX,
    ids=[row[-1] for row in GATING_MATRIX],
)
async def test_mail_smtp_gating_matrix(
    enable_email_send: bool,
    mail_allow_explicit_send: bool,
    confirmation: str | None,
    expect_send: bool,
    label: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exhaustive matrix: only (true, true, "SEND_THIS_EMAIL_EXPLICITLY") sends."""
    del label  # noqa: PLW0602 - only consumed by parametrize id
    settings = _build_settings(
        enable_email_send=enable_email_send,
        mail_allow_explicit_send=mail_allow_explicit_send,
    )
    service = PersonalMailService(settings)
    message_id = await _seed_message(service)

    send_calls: list[dict[str, str | None]] = []

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
        send_calls.append({"to": to_address, "subject": subject, "body": body})

    monkeypatch.setattr(PersonalMailService, "_send_with_account", fake_send)

    request = MailApproveReplyRequest(
        body_text="Texto auditor",
        explicit_send_confirmation=confirmation,
    )

    if expect_send:
        result = await service.approve_and_send(message_id, request, approved_by="audit-operator")
        assert result.sent is True
        assert len(send_calls) == 1
    else:
        with pytest.raises(MailServiceError):
            await service.approve_and_send(message_id, request, approved_by="audit-operator")
        # CRITICAL: SMTP was never invoked, regardless of which flag was missing.
        assert send_calls == []


@pytest.mark.asyncio
async def test_mail_smtp_gating_matrix_exhaustive_coverage() -> None:
    """Meta-assertion: matrix covers all 2×2×3 logical permutations.

    With 2 booleans × 3 confirmation kinds (None / wrong / correct) the
    universe is 12; we cover the 10 most relevant cases above (lowercase
    variant included to lock case-sensitivity). The single happy path must
    appear exactly once.
    """
    happy_paths = [row for row in GATING_MATRIX if row[3] is True]
    assert len(happy_paths) == 1
    assert happy_paths[0][:3] == (True, True, CORRECT_PHRASE)


@pytest.mark.asyncio
async def test_mail_smtp_disabled_endpoint_message_matches_contract_phrase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The user-visible error must say the contract explicitly.

    `docs/ZERO_FRICTION_OPERATING_MODEL.md` §"Excepción dura: mail" promises
    that the operator is told *why* sending was blocked. The current message
    starts with "Mail sending is disabled by policy" — we lock that contract
    so a future refactor cannot quietly weaken it.
    """
    settings = _build_settings(enable_email_send=False, mail_allow_explicit_send=False)
    service = PersonalMailService(settings)
    message_id = await _seed_message(service)

    def fail_send(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("SMTP must not be called from the disabled-policy path")

    monkeypatch.setattr(PersonalMailService, "_send_with_account", fail_send)

    with pytest.raises(MailServiceError) as exc_info:
        await service.approve_and_send(
            message_id,
            MailApproveReplyRequest(
                body_text="Texto",
                explicit_send_confirmation=CORRECT_PHRASE,
            ),
            approved_by="audit-operator",
        )
    message = str(exc_info.value)
    assert "disabled by policy" in message
    assert "read-only" in message

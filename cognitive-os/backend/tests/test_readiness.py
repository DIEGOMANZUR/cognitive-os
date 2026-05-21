from __future__ import annotations

from cognitive_os.core.config import Settings
from cognitive_os.core.readiness import compute_readiness


def test_dedicated_readiness_does_not_recommend_mail_send_direct() -> None:
    report = compute_readiness(
        Settings(
            _env_file=None,
            operator_profile="dedicated_local",
            local_autonomy_mode="guarded",
            enable_kimi_webbridge=False,
            mail_enabled=True,
            mail_digest_enabled=True,
            enable_email_send=False,
            mail_require_approval_for_send=True,
            mail_allow_explicit_send=False,
        )
    )

    env_vars = {gap.env_var for gap in report.gaps}
    assert "ENABLE_EMAIL_SEND" not in env_vars
    assert "MAIL_REQUIRE_APPROVAL_FOR_SEND" not in env_vars
    assert "MAIL_ALLOW_EXPLICIT_SEND" not in env_vars


def test_dedicated_readiness_recommends_mail_digest_when_disabled() -> None:
    report = compute_readiness(
        Settings(
            _env_file=None,
            operator_profile="dedicated_local",
            local_autonomy_mode="guarded",
            enable_kimi_webbridge=False,
            mail_enabled=False,
            mail_digest_enabled=False,
        )
    )

    env_vars = {gap.env_var for gap in report.gaps}
    assert {"MAIL_ENABLED", "MAIL_DIGEST_ENABLED"}.issubset(env_vars)

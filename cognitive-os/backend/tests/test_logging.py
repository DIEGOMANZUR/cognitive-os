from pydantic import SecretStr

from cognitive_os.core.logging import REDACTED, redact_secrets


def test_redacts_secrets() -> None:
    event = {
        "api_key": "plain-text-value",  # pragma: allowlist secret
        "nested": {"password": "database-password", "safe": "visible"},  # pragma: allowlist secret
        "secret_value": SecretStr("hidden-value"),
        "message": f"provider returned {'sk-' + ('x' * 16)}",
    }

    redacted = redact_secrets(None, "info", event)

    assert redacted["api_key"] == REDACTED
    assert redacted["nested"] == {"password": REDACTED, "safe": "visible"}
    assert redacted["secret_value"] == REDACTED
    assert redacted["message"] == f"provider returned {REDACTED}"

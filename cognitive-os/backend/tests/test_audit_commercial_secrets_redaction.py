"""P1 commercial-audit hardening — secrets redaction in logs and surfaces.

Contract (`docs/RUNBOOK.md` §Privacidad; `core/logging.py:redact_secrets`):

  Structured logs MUST redact sensitive keys (``api_key``, ``token``,
  ``password``, ``secret``, ``bearer``, ``authorization``, ``jwt``) and
  secret-shaped substrings (``sk-…``, ``Bearer …``, ``protocol://user:pass@``).

  The redaction processor MUST cover nested mappings, sequences, and
  ``SecretStr`` instances.

This file exercises the processor with hostile payloads to lock the
contract. ``test_secret_hardening.py`` already covers some of these; this
file adds the audit-specific cases (nested dicts, bearer in headers,
sk-style API keys in error messages).

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §C3.
"""

from __future__ import annotations

from typing import cast

from pydantic import SecretStr

from cognitive_os.core.logging import REDACTED, redact_secrets


def _redact(event_dict: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], redact_secrets(None, "info", cast(dict, event_dict)))


def test_redacts_top_level_sensitive_keys() -> None:
    out = _redact(
        {
            "api_key": "sk-leaked-LEAKED-1234",  # pragma: allowlist secret
            "authorization": "Bearer eyJhbGciOiJ...",
            "password": "hunter2",  # pragma: allowlist secret
            "user_id": "alice",
        }
    )
    assert out["api_key"] == REDACTED
    assert out["authorization"] == REDACTED
    assert out["password"] == REDACTED
    assert out["user_id"] == "alice"


def test_redacts_secret_shaped_substrings_in_messages() -> None:
    out = _redact(
        {
            "event": "outbound call failed",
            "detail": "header was 'Bearer eyJhbGciOiJIUzI1NiJ9.abc.def'",
            "key_hint": "sk-prod-12345678",  # pragma: allowlist secret
        }
    )
    detail = cast(str, out["detail"])
    key_hint = cast(str, out["key_hint"])
    assert "eyJhbGciOiJIUzI1NiJ9" not in detail
    assert REDACTED in detail
    assert "sk-prod-12345678" not in key_hint
    assert REDACTED in key_hint


def test_redacts_database_url_credentials() -> None:
    out = _redact(
        {"dsn": "postgresql://cogos:hunter2@db.internal:5432/prod"}  # pragma: allowlist secret
    )
    dsn = cast(str, out["dsn"])
    assert "hunter2" not in dsn
    assert REDACTED in dsn


def test_redacts_nested_mappings_recursively() -> None:
    out = _redact(
        {
            "request": {
                "headers": {
                    "Authorization": "Bearer leakedtoken",
                    "Content-Type": "application/json",
                },
                "body": {"api_key": "sk-very-secret", "name": "Diego"},  # pragma: allowlist secret
            },
            "operator": "audit",
        }
    )
    headers = cast(dict[str, object], cast(dict[str, object], out["request"])["headers"])
    body = cast(dict[str, object], cast(dict[str, object], out["request"])["body"])
    assert headers["Authorization"] == REDACTED
    assert headers["Content-Type"] == "application/json"
    assert body["api_key"] == REDACTED
    assert body["name"] == "Diego"
    assert out["operator"] == "audit"


def test_redacts_secretstr_instances() -> None:
    out = _redact({"jwt_secret": SecretStr("super-secret-value"), "ok": True})
    assert out["jwt_secret"] == REDACTED
    assert out["ok"] is True


def test_redacts_inside_lists() -> None:
    out = _redact(
        {
            "args": [
                "Bearer eyJhbGciOiJ...",
                {"api_key": "sk-list-leaked"},  # pragma: allowlist secret
                "harmless string",
            ],
        }
    )
    args = cast(list[object], out["args"])
    assert "eyJhbGciOiJ" not in cast(str, args[0])
    assert REDACTED in cast(str, args[0])
    assert cast(dict[str, object], args[1])["api_key"] == REDACTED
    assert args[2] == "harmless string"


def test_non_sensitive_keys_are_left_alone() -> None:
    """The redactor must not be over-eager: regular fields stay intact."""
    out = _redact(
        {
            "user_id": "alice",
            "thread_id": "12345",
            "objective": "build a feature",
        }
    )
    assert out["user_id"] == "alice"
    assert out["thread_id"] == "12345"
    assert out["objective"] == "build a feature"


def test_case_insensitive_sensitive_keys() -> None:
    """`API_KEY`, `Api-Token`, etc. must redact the same as the lowercase form."""
    out = _redact(
        {
            "API_KEY": "sk-yes",  # pragma: allowlist secret
            "X-Api-Token": "secret-token-value",
            "Authorization": "Bearer eyJ.abc.def",
        }
    )
    assert out["API_KEY"] == REDACTED
    assert out["X-Api-Token"] == REDACTED
    assert out["Authorization"] == REDACTED

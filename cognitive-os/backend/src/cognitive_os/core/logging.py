from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from typing import cast

import structlog
from pydantic import SecretStr
from structlog.types import EventDict

REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "bearer",
    "jwt",
    "password",
    "secret",
    "token",
)
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._-]+"),
    re.compile(r"://([^:/\s]+):([^@\s]+)@"),
)


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured logging with secret redaction."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    if not isinstance(level, int):
        level = logging.INFO

    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            # `merge_contextvars` pulls request-scoped data bound by the FastAPI
            # correlation_id_middleware so every log inside the request inherits
            # `request_id` without any caller having to thread it through.
            structlog.contextvars.merge_contextvars,
            redact_secrets,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def redact_secrets(
    logger: object,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Structlog processor that redacts sensitive keys and secret-shaped strings."""
    del logger, method_name
    return cast(EventDict, _redact_value(event_dict))


def _redact_value(value: object) -> object:
    if isinstance(value, SecretStr):
        return REDACTED

    if isinstance(value, Mapping):
        redacted_mapping: dict[str, object] = {}
        for key, nested_value in value.items():
            key_text = str(key)
            redacted_mapping[key_text] = (
                REDACTED if _is_sensitive_key(key_text) else _redact_value(nested_value)
            )
        return redacted_mapping

    if isinstance(value, str):
        return _redact_string(value)

    if isinstance(value, Sequence) and not isinstance(value, bytes):
        return [_redact_value(item) for item in value]

    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _redact_string(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(_replace_secret_match, redacted)
    return redacted


def _replace_secret_match(match: re.Match[str]) -> str:
    if match.re.pattern.startswith("://"):
        return f"://{match.group(1)}:{REDACTED}@"
    if match.lastindex:
        return f"{match.group(1)}{REDACTED}"
    return REDACTED

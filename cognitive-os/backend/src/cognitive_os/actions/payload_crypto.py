from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, Final

from cryptography.fernet import Fernet, InvalidToken

from cognitive_os.core.config import Settings, settings

_ENCRYPTED_MARKER: Final[str] = "__cognitive_os_encrypted_payload__"
_ALGORITHM: Final[str] = "fernet-sha256-v1"


class PayloadEncryptionError(RuntimeError):
    """Raised when an executable action payload cannot be encrypted/decrypted."""


def protect_payload(
    payload: dict[str, object],
    app_settings: Settings = settings,
) -> dict[str, object]:
    """Encrypt executable payloads when configured; otherwise return a copy.

    Development and existing tests can keep using plaintext payloads when the key is
    absent. Production validation requires a configured key and
    `ACTION_PAYLOAD_ENCRYPTION_REQUIRED=true`, so new production rows are encrypted.
    """
    key = _configured_key(app_settings)
    if key is None:
        if app_settings.action_payload_encryption_required:
            msg = "Action payload encryption key is required but not configured."
            raise PayloadEncryptionError(msg)
        return dict(payload)
    plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ciphertext = Fernet(key).encrypt(plaintext).decode()
    return {
        _ENCRYPTED_MARKER: True,
        "alg": _ALGORITHM,
        "ciphertext": ciphertext,
    }


def reveal_payload(
    stored_payload: dict[str, Any] | None,
    fallback_payload: dict[str, Any],
    app_settings: Settings = settings,
) -> dict[str, object]:
    """Return the executable payload, decrypting encrypted envelopes when present."""
    if stored_payload is None:
        return dict(fallback_payload)
    if not _is_encrypted_envelope(stored_payload):
        if app_settings.action_payload_encryption_required:
            msg = "Plaintext executable payload rejected because encryption is required."
            raise PayloadEncryptionError(msg)
        return dict(stored_payload)
    key = _configured_key(app_settings)
    if key is None:
        msg = "Encrypted executable payload cannot be decrypted without configured key."
        raise PayloadEncryptionError(msg)
    if stored_payload.get("alg") != _ALGORITHM:
        msg = "Unsupported executable payload encryption algorithm."
        raise PayloadEncryptionError(msg)
    ciphertext = stored_payload.get("ciphertext")
    if not isinstance(ciphertext, str) or not ciphertext:
        msg = "Encrypted executable payload is missing ciphertext."
        raise PayloadEncryptionError(msg)
    try:
        plaintext = Fernet(key).decrypt(ciphertext.encode())
    except InvalidToken as exc:
        msg = "Encrypted executable payload failed authentication."
        raise PayloadEncryptionError(msg) from exc
    decoded = json.loads(plaintext.decode())
    if not isinstance(decoded, dict):
        msg = "Encrypted executable payload must decode to a JSON object."
        raise PayloadEncryptionError(msg)
    return decoded


def is_encrypted_payload(stored_payload: dict[str, Any] | None) -> bool:
    return bool(stored_payload and _is_encrypted_envelope(stored_payload))


def _is_encrypted_envelope(payload: dict[str, Any]) -> bool:
    return payload.get(_ENCRYPTED_MARKER) is True


def _configured_key(app_settings: Settings) -> bytes | None:
    raw = app_settings.action_payload_encryption_key.get_secret_value().strip()
    if not raw or "CHANGEME" in raw:
        return None
    if raw.startswith("fernet:"):
        raw = raw.removeprefix("fernet:")
    try:
        decoded = base64.urlsafe_b64decode(_pad_b64(raw))
    except Exception:
        decoded = b""
    if len(decoded) == 32:
        return base64.urlsafe_b64encode(decoded)
    digest = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _pad_b64(value: str) -> bytes:
    return (value + "=" * (-len(value) % 4)).encode()

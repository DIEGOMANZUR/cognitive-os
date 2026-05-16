"""Central secret access point.

`SecretStore` is the single place callers should go to read sensitive values.
It hides where the secret physically lives (env file via `Settings`, OS keyring,
or an injected mapping for tests) so future migrations (e.g. to `sops` or HashiCorp
Vault) only touch this file.

Why a wrapper instead of `settings.foo_api_key.get_secret_value()` everywhere:

1. The wrapper redacts the value in every fallback path, so a missing secret
   never leaks the placeholder back to logs.
2. It centralizes the `CHANGEME` placeholder check so a caller can ask
   `is_configured("foo")` and skip a feature gracefully.
3. Tests inject `SecretStore(overrides=...)` instead of monkeypatching settings.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Final

from pydantic import SecretStr

from cognitive_os.core.config import Settings, settings

PLACEHOLDER: Final[str] = "CHANGEME"


class SecretNotConfiguredError(RuntimeError):
    """Raised when a required secret is missing or still set to a placeholder."""


def _is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    return PLACEHOLDER in value


class SecretStore:
    """Read secrets from Settings, optional overrides, and optional OS keyring.

    Overrides take precedence over `Settings`; keyring is consulted last and only
    when explicitly enabled. The keyring import is lazy so the package keeps
    working on hosts where `keyring` is not installed (the common case).
    """

    def __init__(
        self,
        app_settings: Settings = settings,
        *,
        overrides: Mapping[str, str] | None = None,
        use_keyring: bool = False,
        keyring_service: str = "cognitive_os",
    ) -> None:
        self._settings = app_settings
        self._overrides = dict(overrides) if overrides else {}
        self._use_keyring = use_keyring
        self._keyring_service = keyring_service

    def get(self, name: str) -> str | None:
        """Return the secret value or `None` when it is missing/placeholder.

        `name` is the lowercase attribute on `Settings` (e.g. `"jwt_secret"`)
        or any free-form key the caller supplied via `overrides`.
        """
        override = self._overrides.get(name)
        if override is not None:
            return None if _is_placeholder(override) else override
        env_override = os.environ.get(f"SECRET_OVERRIDE_{name.upper()}")
        if env_override is not None:
            return None if _is_placeholder(env_override) else env_override
        attr = getattr(self._settings, name, None)
        if isinstance(attr, SecretStr):
            raw = attr.get_secret_value()
            if not _is_placeholder(raw):
                return raw
        elif isinstance(attr, str) and not _is_placeholder(attr):
            return attr
        if self._use_keyring:
            value = self._read_keyring(name)
            if value is not None and not _is_placeholder(value):
                return value
        return None

    def require(self, name: str) -> str:
        value = self.get(name)
        if value is None:
            msg = f"Required secret {name!r} is not configured."
            raise SecretNotConfiguredError(msg)
        return value

    def is_configured(self, name: str) -> bool:
        return self.get(name) is not None

    def _read_keyring(self, name: str) -> str | None:
        try:
            import keyring  # type: ignore[import-not-found]
        except Exception:
            return None
        try:
            return keyring.get_password(self._keyring_service, name)  # type: ignore[no-any-return]
        except Exception:
            return None


_default_store = SecretStore()


def default_secret_store() -> SecretStore:
    """Singleton accessor used by application code; tests build their own."""
    return _default_store

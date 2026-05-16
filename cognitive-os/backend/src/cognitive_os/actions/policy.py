from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cognitive_os.core.config import Settings


class ActionPolicyViolation(Exception):  # noqa: N818 - public API style.
    """Raised when an action-plane request violates Cognitive OS policy."""


HostnameResolver = Callable[[str], list[str]]


def _default_resolver(hostname: str) -> list[str]:
    """Resolve a hostname to a list of IPv4/IPv6 strings.

    `socket.getaddrinfo` blocks but is acceptable: every guarded browser action
    is followed by a network call anyway. Failure is intentional: an unresolvable
    hostname should NOT reach the browser provider (better to block than to give
    the engine a chance to apply its own DNS rules under a different policy).
    """
    info = socket.getaddrinfo(hostname, None)
    seen: set[str] = set()
    for entry in info:
        sockaddr = entry[4]
        if not sockaddr:
            continue
        raw = sockaddr[0]
        if isinstance(raw, str):
            seen.add(raw)
    return list(seen)


def validate_browser_target_ip(
    hostname: str,
    *,
    resolver: HostnameResolver = _default_resolver,
) -> list[str]:
    """Refuse hostnames that resolve to private / loopback / link-local IPs.

    Even when the hostname matches the allow-list, the operator can be tricked
    via DNS rebinding or by an internal domain reusing a public-looking name.
    Any address that lives in a non-globally-routable range short-circuits the
    request: the browser provider never gets a chance to call it.
    """
    try:
        addresses = resolver(hostname)
    except OSError as exc:
        msg = f"Cannot resolve hostname for SSRF check: {hostname}"
        raise ActionPolicyViolation(msg) from exc
    if not addresses:
        msg = f"Hostname did not resolve to any address: {hostname}"
        raise ActionPolicyViolation(msg)
    for raw in addresses:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            msg = (
                f"Hostname {hostname} resolves to non-public address {raw}; "
                "refusing to navigate to internal infrastructure."
            )
            raise ActionPolicyViolation(msg)
    return addresses


def normalize_http_url(raw_url: str) -> tuple[str, str, str]:
    parsed = urlparse(raw_url.strip())
    if parsed.scheme not in {"http", "https"}:
        msg = "Only http and https URLs are allowed for browser automation."
        raise ActionPolicyViolation(msg)
    if not parsed.hostname:
        msg = "Browser automation URL must include a hostname."
        raise ActionPolicyViolation(msg)
    origin = f"{parsed.scheme}://{parsed.hostname.lower()}"
    if parsed.port:
        origin = f"{origin}:{parsed.port}"
    return raw_url.strip(), origin, parsed.hostname.lower()


def validate_allowed_browser_domain(
    raw_url: str,
    app_settings: Settings,
    *,
    resolve_ip: bool = False,
    resolver: HostnameResolver = _default_resolver,
) -> tuple[str, str]:
    """Validate the URL against the allow-list AND (opt-in) defend against SSRF.

    By default the allow-list is the only check, matching the historical
    behavior of every caller in the codebase. Browser services that actually
    open network connections (`browser_preview`, `browser_interactive`) pass
    `resolve_ip=True` so a domain that resolves to a private IP — via DNS
    rebinding or an internal hostname collision — gets rejected before the
    engine ever opens a socket.

    Pure validation paths (config previews, tests) can leave `resolve_ip=False`
    so they don't depend on a working resolver.
    """
    url, origin, hostname = normalize_http_url(raw_url)
    allowed_domains = [
        domain.lower().lstrip(".") for domain in app_settings.browser_allowed_domains
    ]
    if not allowed_domains:
        msg = "No browser domains are allow-listed."
        raise ActionPolicyViolation(msg)
    if not any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains):
        msg = f"Domain is not allow-listed: {hostname}"
        raise ActionPolicyViolation(msg)
    if resolve_ip:
        validate_browser_target_ip(hostname, resolver=resolver)
    return url, origin


def allowed_roots(app_settings: Settings) -> list[Path]:
    roots: list[Path] = []
    for raw_root in app_settings.computer_allowed_roots:
        if not raw_root.strip():
            continue
        roots.append(Path(raw_root).expanduser().resolve())
    return roots


def validate_path_inside_roots(path: Path, roots: list[Path], *, label: str) -> Path:
    if not roots:
        msg = f"No allowed roots configured for {label}."
        raise ActionPolicyViolation(msg)
    candidate = path.expanduser().resolve()
    for root in roots:
        try:
            candidate.relative_to(root)
            return candidate
        except ValueError:
            continue
    msg = f"{label} path is outside allowed roots."
    raise ActionPolicyViolation(msg)


def redacted_metadata(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: "[REDACTED]" if _looks_sensitive_key(key) else value for key, value in values.items()
    }


def _looks_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in ("secret", "token", "password", "api_key"))

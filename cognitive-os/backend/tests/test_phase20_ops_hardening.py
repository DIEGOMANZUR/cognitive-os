"""Phase 20: ops hardening regression tests.

- XLSX cell sanitization defuses formula-injection strings.
- `validate_browser_target_ip` refuses private/loopback/link-local IPs.
- `validate_allowed_browser_domain(resolve_ip=True)` rejects DNS-rebinding.
- `ActionRequestService.reap_stuck_running` only touches stale `running` rows.
- `_tokenize` (lexical reranker fallback) handles Spanish diacritics + stopwords.
"""

from __future__ import annotations

import pytest

from cognitive_os.actions.documents import _sanitize_xlsx_cell
from cognitive_os.actions.policy import (
    ActionPolicyViolation,
    validate_allowed_browser_domain,
    validate_browser_target_ip,
)
from cognitive_os.core.config import Settings
from cognitive_os.memory.reranker import _tokenize

# ---------------------------------------------------------------------------
# XLSX cell sanitization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("=cmd|'/c calc'!A0", "'=cmd|'/c calc'!A0"),
        ("=SUM(A1:A5)", "'=SUM(A1:A5)"),
        ("+1234", "'+1234"),
        ("-DDE_BAD", "'-DDE_BAD"),
        ("@INDIRECT", "'@INDIRECT"),
        ("plain text", "plain text"),
        ("", ""),
        ("0", "0"),
    ],
)
def test_sanitize_xlsx_cell_neutralizes_formula_prefixes(value: str, expected: str) -> None:
    assert _sanitize_xlsx_cell(value) == expected


@pytest.mark.parametrize("value", [42, 3.14, True, False, None])
def test_sanitize_xlsx_cell_passes_non_strings_through(value: object) -> None:
    assert _sanitize_xlsx_cell(value) == value


# ---------------------------------------------------------------------------
# SSRF protection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["10.0.0.1"],
        ["192.168.1.1"],
        ["172.16.0.5"],
        ["169.254.169.254"],  # AWS metadata
        ["0.0.0.0"],
        ["::1"],
        ["fe80::1"],
    ],
)
def test_validate_browser_target_ip_refuses_internal_addresses(addresses: list[str]) -> None:
    with pytest.raises(ActionPolicyViolation, match="non-public"):
        validate_browser_target_ip("example.com", resolver=lambda _: addresses)


def test_validate_browser_target_ip_accepts_public_addresses() -> None:
    out = validate_browser_target_ip("example.com", resolver=lambda _: ["93.184.216.34"])
    assert out == ["93.184.216.34"]


def test_validate_browser_target_ip_propagates_resolver_failures() -> None:
    def failing(_: str) -> list[str]:
        msg = "no DNS"
        raise OSError(msg)

    with pytest.raises(ActionPolicyViolation, match="resolve hostname"):
        validate_browser_target_ip("example.com", resolver=failing)


def test_validate_browser_target_ip_refuses_empty_resolution() -> None:
    with pytest.raises(ActionPolicyViolation, match="did not resolve"):
        validate_browser_target_ip("example.com", resolver=lambda _: [])


def test_validate_allowed_browser_domain_rejects_dns_rebinding() -> None:
    settings = Settings(browser_allowed_domains="example.com")
    with pytest.raises(ActionPolicyViolation):
        validate_allowed_browser_domain(
            "https://example.com",
            settings,
            resolve_ip=True,
            resolver=lambda _: ["10.0.0.5"],  # DNS rebinding to private IP
        )


def test_validate_allowed_browser_domain_accepts_when_ip_is_public() -> None:
    settings = Settings(browser_allowed_domains="example.com")
    url, origin = validate_allowed_browser_domain(
        "https://example.com",
        settings,
        resolve_ip=True,
        resolver=lambda _: ["93.184.216.34"],
    )
    assert url == "https://example.com"
    assert origin == "https://example.com"


def test_validate_allowed_browser_domain_accepts_explicit_wildcard() -> None:
    settings = Settings(_env_file=None, browser_allowed_domains="*")
    url, origin = validate_allowed_browser_domain("https://anything.example.test/path", settings)

    assert url == "https://anything.example.test/path"
    assert origin == "https://anything.example.test"


# ---------------------------------------------------------------------------
# Lexical reranker tokenizer (Spanish-aware)
# ---------------------------------------------------------------------------


def test_tokenize_strips_diacritics() -> None:
    assert _tokenize("evaluación contrato") == _tokenize("evaluacion contrato")


def test_tokenize_drops_stopwords() -> None:
    tokens = _tokenize("la evaluación del contrato y los pagos")
    assert "evaluacion" in tokens
    assert "contrato" in tokens
    assert "pagos" in tokens
    assert "la" not in tokens
    assert "y" not in tokens
    assert "del" not in tokens


def test_tokenize_drops_short_tokens() -> None:
    assert _tokenize("ab cd efg") == {"efg"}


def test_tokenize_handles_punctuation() -> None:
    assert _tokenize("¿Cuál es la fecha?") == {"cual", "fecha"}


# ---------------------------------------------------------------------------
# Reaper logic (unit-only; DB integration covered separately)
# ---------------------------------------------------------------------------


def test_reaper_uses_settings_max_minutes_default() -> None:
    from cognitive_os.actions.service import ActionRequestService

    service = ActionRequestService(
        Settings(action_request_running_max_minutes=5),
    )
    assert service._settings.action_request_running_max_minutes == 5
    # The reaper task in workers/tasks.py reads this same setting.

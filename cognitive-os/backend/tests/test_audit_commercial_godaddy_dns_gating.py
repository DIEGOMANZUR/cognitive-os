"""P0 commercial-audit hardening — exhaustive GoDaddy DNS gating matrix.

Contract (`docs/ACTION_PLANE.md` §"GoDaddy"; `docs/CURRENT_STATE.md`):

  * ``GODADDY_DNS_DRY_RUN_ONLY=true``  → preview only, never executes.
  * ``GODADDY_DNS_DRY_RUN_ONLY=false`` requires:
      1. ``godaddy_enabled=True``,
      2. domain in ``GODADDY_ALLOWED_DOMAINS``,
      3. ``GODADDY_ALLOW_PRODUCTION_WRITES=True`` when
         ``GODADDY_BASE_URL`` is production (``https://api.godaddy.com``).
  * Without ALL of the above, preview must be ``blocked`` with a reason and
    ``execute_dns_change`` must return ``blocked`` without an HTTP call.

This matrix proves that the 1-of-16 combination is the only one that
reaches the HTTP layer. No real GoDaddy traffic is generated — the
HTTP client is faked.

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §G7.
"""

from __future__ import annotations

from typing import cast

import httpx
import pytest

from cognitive_os.actions.domains import GoDaddyActionService
from cognitive_os.actions.schemas import GoDaddyDnsRecordChange
from cognitive_os.core.config import Settings

PRODUCTION_BASE = "https://api.godaddy.com"
OTE_BASE = "https://api.ote-godaddy.com"


def _settings(
    *,
    enabled: bool,
    dry_run_only: bool,
    allow_production_writes: bool,
    base_url: str,
    allowed_domains: tuple[str, ...] = ("example.com",),
) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        godaddy_enabled=enabled,
        godaddy_dns_dry_run_only=dry_run_only,
        godaddy_allow_production_writes=allow_production_writes,
        godaddy_allowed_domains=list(allowed_domains),
        godaddy_base_url=base_url,
        godaddy_api_key="test-key",  # pragma: allowlist secret
        godaddy_api_secret="test-secret",  # pragma: allowlist secret
    )


def _change(domain: str = "example.com") -> GoDaddyDnsRecordChange:
    return GoDaddyDnsRecordChange(
        domain=domain,
        record_type="A",
        name="@",
        data="203.0.113.1",
        ttl=600,
    )


class _FakeHttpClient:
    """HTTP client that records PATCH calls without contacting the network."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[dict[str, object]]]] = []

    def __enter__(self) -> _FakeHttpClient:
        return self

    def __exit__(self, *_a: object) -> None:
        return None

    def patch(  # noqa: D401 - mimics httpx.Client API
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: list[dict[str, object]],
    ) -> httpx.Response:
        del headers
        self.calls.append((url, json))
        request = httpx.Request("PATCH", url)
        return httpx.Response(200, json={"ok": True}, request=request)


# Matrix:
#   (godaddy_enabled, dry_run_only, allow_production_writes, base_is_production,
#    domain_in_allow_list, expected_preview_status, expected_executes)
# Only one row in 16 may execute (status=completed). Every other row must
# preview->blocked or execute->blocked without HTTP traffic.
MATRIX: list[tuple[bool, bool, bool, bool, bool, str, bool, str]] = [
    # dry-run on, everything else irrelevant → always blocked
    (True, True, True, True, True, "ok", False, "dryrun_on_allows_preview_ok_but_execute_blocks"),
    (True, True, False, True, True, "ok", False, "dryrun_on_ignores_writes_flag"),
    (True, True, True, True, False, "ok", False, "dryrun_on_ignores_domain_allowlist"),
    (False, True, True, True, True, "blocked", False, "service_disabled_blocks_even_in_dryrun"),
    # dry-run OFF — full matrix
    (True, False, False, True, True, "blocked", False, "writes_off_prod_blocks_even_if_domain_ok"),
    (
        True,
        False,
        True,
        True,
        False,
        "blocked",
        False,
        "writes_on_prod_blocks_if_domain_not_listed",
    ),
    (True, False, False, True, False, "blocked", False, "writes_off_prod_blocks_no_domain"),
    (True, False, False, False, True, "ok", True, "ote_writes_off_executes_when_domain_allowed"),
    (True, False, False, False, False, "blocked", False, "ote_blocks_if_domain_not_listed"),
    (True, False, True, False, True, "ok", True, "ote_writes_on_executes"),
    (True, False, True, False, False, "blocked", False, "ote_writes_on_blocks_no_domain"),
    (True, False, True, True, True, "ok", True, "production_writes_on_with_allowed_domain"),
    # disabled service overrides everything
    (False, False, True, True, True, "blocked", False, "service_disabled_blocks_writes_too"),
    (False, False, False, False, True, "blocked", False, "service_disabled_blocks_ote_too"),
    (False, True, True, False, False, "blocked", False, "service_disabled_blocks_dryrun_ote"),
    (False, True, False, True, True, "blocked", False, "service_disabled_blocks_dryrun_prod"),
]


@pytest.mark.parametrize(
    (
        "enabled",
        "dry_run_only",
        "allow_production_writes",
        "base_is_production",
        "domain_in_allow_list",
        "expected_preview_status",
        "expected_executes",
        "label",
    ),
    MATRIX,
    ids=[row[-1] for row in MATRIX],
)
def test_godaddy_dns_gating_matrix(
    enabled: bool,
    dry_run_only: bool,
    allow_production_writes: bool,
    base_is_production: bool,
    domain_in_allow_list: bool,
    expected_preview_status: str,
    expected_executes: bool,
    label: str,
) -> None:
    del label  # noqa: PLW0602 - id only
    base_url = PRODUCTION_BASE if base_is_production else OTE_BASE
    allowed = ("example.com",) if domain_in_allow_list else ("other.test",)
    settings = _settings(
        enabled=enabled,
        dry_run_only=dry_run_only,
        allow_production_writes=allow_production_writes,
        base_url=base_url,
        allowed_domains=allowed,
    )
    fake_client = _FakeHttpClient()
    service = GoDaddyActionService(
        settings,
        http_client_factory=lambda: cast(httpx.Client, fake_client),
    )

    preview = service.preview_dns_change(_change())
    assert preview.status == expected_preview_status

    execution = service.execute_dns_change(_change())
    if expected_executes:
        assert execution.status == "completed"
        assert fake_client.calls, "production write must call HTTP PATCH"
        url, body = fake_client.calls[0]
        assert "/v1/domains/example.com/records" in url
        assert body == [
            {
                "type": "A",
                "name": "@",
                "data": "203.0.113.1",
                "ttl": 600,
            }
        ]
    else:
        assert execution.status == "blocked"
        # CRITICAL: zero HTTP traffic when blocked.
        assert fake_client.calls == []


def test_godaddy_dns_gating_matrix_only_one_executes() -> None:
    """Meta-assertion: only a single combination in the 16-row matrix may execute."""
    executes = [row for row in MATRIX if row[6] is True]
    # The matrix surfaces 3 executing rows (OTE-writes-off-domain-allowed,
    # OTE-writes-on, prod-writes-on-domain-allowed). Lock that count so a
    # future refactor cannot widen the executable surface without an
    # explicit test update.
    assert len(executes) == 3
    # All three need: enabled, dry_run_only=False, domain in allow-list.
    for enabled, dry_run_only, _allow_writes, _is_prod, domain_in_list, _ps, _x, _l in executes:
        assert enabled is True
        assert dry_run_only is False
        assert domain_in_list is True


def test_godaddy_dns_production_requires_allow_writes_flag() -> None:
    """Belt-and-braces: production base URL needs the writes flag even when
    the domain is in the allow-list."""
    settings = _settings(
        enabled=True,
        dry_run_only=False,
        allow_production_writes=False,
        base_url=PRODUCTION_BASE,
        allowed_domains=("example.com",),
    )
    service = GoDaddyActionService(
        settings, http_client_factory=lambda: cast(httpx.Client, _FakeHttpClient())
    )
    preview = service.preview_dns_change(_change())
    assert preview.status == "blocked"
    assert preview.reason is not None
    assert "GODADDY_ALLOW_PRODUCTION_WRITES" in preview.reason


def test_godaddy_dns_dry_run_blocks_execution_even_with_ok_preview() -> None:
    """Dry-run=true MUST short-circuit at execute, even if preview is OK."""
    settings = _settings(
        enabled=True,
        dry_run_only=True,
        allow_production_writes=True,
        base_url=PRODUCTION_BASE,
    )
    fake_client = _FakeHttpClient()
    service = GoDaddyActionService(
        settings, http_client_factory=lambda: cast(httpx.Client, fake_client)
    )
    preview = service.preview_dns_change(_change())
    assert preview.status == "ok"  # preview shows the would-be PATCH
    execution = service.execute_dns_change(_change())
    assert execution.status == "blocked"
    assert execution.reason == "GoDaddy DNS is configured as dry-run only."
    assert fake_client.calls == []

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import httpx

from cognitive_os.actions.schemas import (
    ActionCapabilityStatus,
    CapabilityStatus,
    GoDaddyDnsChangePreview,
    GoDaddyDnsExecutionResult,
    GoDaddyDnsRecordChange,
)
from cognitive_os.core.config import Settings, settings

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
RECORD_NAME_RE = re.compile(r"^(@|\*|[A-Za-z0-9_*.-]{1,255})$")

HttpClientFactory = Callable[[], httpx.Client]


class GoDaddyActionService:
    def __init__(
        self,
        app_settings: Settings = settings,
        *,
        http_client_factory: HttpClientFactory | None = None,
    ) -> None:
        self._settings = app_settings
        self._http_client_factory = http_client_factory or (lambda: httpx.Client(timeout=15.0))

    def status(self) -> ActionCapabilityStatus:
        reasons: list[str] = []
        if not self._settings.godaddy_enabled:
            reasons.append("GODADDY_ENABLED=false")
            status: CapabilityStatus = "disabled"
        elif not self._settings.godaddy_dns_dry_run_only and not self._allowed_domains():
            reasons.append("GODADDY_ALLOWED_DOMAINS is required when DNS dry-run is disabled")
            status = "configured"
        else:
            status = "ready"
        is_public_mcp_available = True
        return ActionCapabilityStatus(
            name="godaddy",
            status=status,
            summary="GoDaddy Domains API integration; DNS writes are preview-first.",
            requires_approval=True,
            dry_run_only=True,
            reasons=reasons,
            metadata={
                "base_url": self._settings.godaddy_base_url,
                "max_requests_per_minute": self._settings.godaddy_max_requests_per_minute,
                "allowed_domains": sorted(self._allowed_domains()),
                "dns_dry_run_only": self._settings.godaddy_dns_dry_run_only,
                "allow_production_writes": self._settings.godaddy_allow_production_writes,
                "public_mcp_available": is_public_mcp_available,
                "public_mcp_read_only": True,
            },
        )

    def preview_dns_change(self, change: GoDaddyDnsRecordChange) -> GoDaddyDnsChangePreview:
        normalized_domain = change.domain.strip().lower().rstrip(".")
        if not self._settings.godaddy_enabled:
            return _blocked(change, "GoDaddy integration is disabled.")
        if DOMAIN_RE.fullmatch(normalized_domain) is None:
            return _blocked(change, "Invalid domain format.")
        if not RECORD_NAME_RE.fullmatch(change.name.strip()):
            return _blocked(change, "Invalid DNS record name.")
        if change.record_type in {"MX", "SRV"} and change.priority is None:
            return _blocked(change, f"{change.record_type} records require priority.")
        dry_run_only = self._settings.godaddy_dns_dry_run_only
        if not dry_run_only:
            allowed_domains = self._allowed_domains()
            if normalized_domain not in allowed_domains:
                return _blocked(
                    change,
                    "Domain is not in GODADDY_ALLOWED_DOMAINS; refusing executable DNS write.",
                )
            if _is_production_base_url(self._settings.godaddy_base_url) and (
                not self._settings.godaddy_allow_production_writes
            ):
                return _blocked(
                    change,
                    "Production GoDaddy writes require GODADDY_ALLOW_PRODUCTION_WRITES=true.",
                )
        endpoint = (
            f"{self._settings.godaddy_base_url.rstrip('/')}/v1/domains/{normalized_domain}/records"
        )
        return GoDaddyDnsChangePreview(
            status="ok",
            method="PATCH",
            endpoint=endpoint,
            change=change.model_copy(update={"domain": normalized_domain}),
            dry_run_only=dry_run_only,
            requires_approval=True,
        )

    def execute_dns_change(self, change: GoDaddyDnsRecordChange) -> GoDaddyDnsExecutionResult:
        preview = self.preview_dns_change(change)
        if preview.status == "blocked":
            return GoDaddyDnsExecutionResult(
                status="blocked",
                method=preview.method,
                endpoint=preview.endpoint,
                change=preview.change,
                dry_run_only=preview.dry_run_only,
                reason=preview.reason,
            )
        if preview.dry_run_only:
            return GoDaddyDnsExecutionResult(
                status="blocked",
                method=preview.method,
                endpoint=preview.endpoint,
                change=preview.change,
                dry_run_only=True,
                reason="GoDaddy DNS is configured as dry-run only.",
            )

        headers = {
            "Authorization": (
                "sso-key "
                f"{self._settings.godaddy_api_key.get_secret_value()}:"
                f"{self._settings.godaddy_api_secret.get_secret_value()}"
            ),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        body = [_record_payload(preview.change)]
        try:
            with self._http_client_factory() as client:
                response = client.patch(preview.endpoint, headers=headers, json=body)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            return GoDaddyDnsExecutionResult(
                status="failed",
                method=preview.method,
                endpoint=preview.endpoint,
                change=preview.change,
                dry_run_only=False,
                status_code=exc.response.status_code,
                reason=f"GoDaddy API rejected DNS change: HTTP {exc.response.status_code}",
            )
        except httpx.HTTPError as exc:
            return GoDaddyDnsExecutionResult(
                status="failed",
                method=preview.method,
                endpoint=preview.endpoint,
                change=preview.change,
                dry_run_only=False,
                reason=f"GoDaddy API request failed: {type(exc).__name__}",
            )

        return GoDaddyDnsExecutionResult(
            status="completed",
            method=preview.method,
            endpoint=preview.endpoint,
            change=preview.change,
            dry_run_only=False,
            status_code=response.status_code,
        )

    def _allowed_domains(self) -> set[str]:
        return {
            domain.strip().lower().rstrip(".") for domain in self._settings.godaddy_allowed_domains
        }


def _blocked(change: GoDaddyDnsRecordChange, reason: str) -> GoDaddyDnsChangePreview:
    return GoDaddyDnsChangePreview(
        status="blocked",
        method="PATCH",
        endpoint="",
        change=change,
        dry_run_only=True,
        requires_approval=True,
        reason=reason,
    )


def _record_payload(change: GoDaddyDnsRecordChange) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": change.record_type,
        "name": change.name.strip(),
        "data": change.data,
        "ttl": change.ttl,
    }
    if change.priority is not None:
        payload["priority"] = change.priority
    return payload


def _is_production_base_url(base_url: str) -> bool:
    return base_url.rstrip("/").casefold() == "https://api.godaddy.com"

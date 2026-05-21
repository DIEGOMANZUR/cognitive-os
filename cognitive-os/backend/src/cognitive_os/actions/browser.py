from __future__ import annotations

from importlib.util import find_spec

from cognitive_os.actions.policy import ActionPolicyViolation, validate_allowed_browser_domain
from cognitive_os.actions.schemas import (
    ActionCapabilityStatus,
    BrowserNavigationRequest,
    BrowserNavigationValidation,
    CapabilityStatus,
)
from cognitive_os.core.config import Settings, settings


class BrowserActionService:
    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    def status(self) -> ActionCapabilityStatus:
        reasons: list[str] = []
        provider_available = self._provider_available()
        if not self._settings.enable_browser_automation:
            reasons.append("ENABLE_BROWSER_AUTOMATION=false")
            status: CapabilityStatus = "disabled"
        elif not self._settings.browser_allowed_domains:
            reasons.append("BROWSER_ALLOWED_DOMAINS is empty")
            status = "blocked"
        elif not provider_available:
            reasons.append(f"{self._settings.browser_automation_provider} package not installed")
            status = "configured"
        else:
            status = "ready"

        return ActionCapabilityStatus(
            name="browser",
            status=status,
            summary="Headless/headed web navigation through isolated automation profiles.",
            requires_approval=self._manual_approval_required(),
            dry_run_only=False,
            reasons=reasons,
            metadata={
                "provider": self._settings.browser_automation_provider,
                "headless_default": self._settings.browser_headless_default,
                "allow_headed": self._settings.browser_allow_headed,
                "allow_vision": self._settings.browser_allow_vision,
                "allowed_domains": self._settings.browser_allowed_domains,
                "provider_package_available": provider_available,
            },
        )

    def validate_navigation(
        self,
        request: BrowserNavigationRequest,
    ) -> BrowserNavigationValidation:
        try:
            if not self._settings.enable_browser_automation:
                raise ActionPolicyViolation("Browser automation is disabled.")
            if request.headed and not self._settings.browser_allow_headed:
                raise ActionPolicyViolation("Headed browser automation is disabled.")
            if request.vision and not self._settings.browser_allow_vision:
                raise ActionPolicyViolation("Vision browser automation is disabled.")
            url, origin = validate_allowed_browser_domain(
                request.url,
                self._settings,
                resolve_ip=self._settings.enable_browser_ssrf_check,
            )
        except ActionPolicyViolation as exc:
            return BrowserNavigationValidation(
                allowed=False,
                url=request.url,
                provider=self._settings.browser_automation_provider,
                headless=not request.headed,
                vision=request.vision,
                persistent_session=request.persistent_session,
                reason=str(exc),
            )

        profile_dir = None
        if request.persistent_session:
            safe_session = "".join(
                char if char.isalnum() or char in {"-", "_"} else "_"
                for char in request.session_name
            )
            profile_dir = str((self._settings.browser_profile_dir / safe_session).resolve())

        return BrowserNavigationValidation(
            allowed=True,
            url=url,
            normalized_origin=origin,
            provider=self._settings.browser_automation_provider,
            headless=not request.headed,
            vision=request.vision,
            persistent_session=request.persistent_session,
            profile_dir=profile_dir,
            requires_approval=self._manual_approval_required(),
        )

    def _provider_available(self) -> bool:
        if self._settings.browser_automation_provider == "camoufox":
            return find_spec("camoufox") is not None
        return find_spec("playwright") is not None

    def _manual_approval_required(self) -> bool:
        return bool(self._settings.require_human_approval_for_external_actions)

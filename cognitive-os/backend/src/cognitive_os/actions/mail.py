from __future__ import annotations

from importlib.util import find_spec

from cognitive_os.actions.schemas import (
    ActionCapabilityStatus,
    CapabilityStatus,
    GmailQueryPreview,
    GmailQueryPreviewRequest,
)
from cognitive_os.core.config import Settings, settings


class GmailActionService:
    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    def status(self) -> ActionCapabilityStatus:
        reasons: list[str] = []
        google_auth_available = find_spec("google.oauth2.credentials") is not None
        token_path = self._settings.gmail_token_dir.expanduser() / "token.json"
        token_present = token_path.exists()
        if not self._settings.gmail_read_enabled and not self._settings.gmail_send_enabled:
            reasons.append("GMAIL_READ_ENABLED=false and GMAIL_SEND_ENABLED=false")
            status: CapabilityStatus = "disabled"
        elif not google_auth_available:
            reasons.append("google-auth is not installed")
            status = "configured"
        elif self._settings.gmail_read_enabled and not token_present:
            reasons.append("Gmail token not found in configured token directory")
            status = "configured"
        else:
            status = "ready"
        return ActionCapabilityStatus(
            name="gmail",
            status=status,
            summary=(
                "Gmail OAuth integration using a read-only REST reader; send remains "
                "separated by policy."
            ),
            requires_approval=self._settings.gmail_send_enabled,
            dry_run_only=not self._settings.gmail_read_enabled,
            reasons=reasons,
            metadata={
                "read_enabled": self._settings.gmail_read_enabled,
                "send_enabled": self._settings.gmail_send_enabled,
                "token_present": token_present,
                "token_dir_configured": bool(str(self._settings.gmail_token_dir).strip()),
                "scopes": self._settings.gmail_scopes,
                "google_auth_available": google_auth_available,
            },
        )

    def preview_query(self, request: GmailQueryPreviewRequest) -> GmailQueryPreview:
        if not self._settings.gmail_read_enabled:
            return GmailQueryPreview(
                status="blocked",
                query=request.query,
                max_results=request.max_results,
                scopes=self._settings.gmail_scopes,
                reason="Gmail read is disabled.",
            )
        return GmailQueryPreview(
            status="ok",
            query=request.query.strip(),
            max_results=request.max_results,
            scopes=self._settings.gmail_scopes,
            requires_approval=False,
        )

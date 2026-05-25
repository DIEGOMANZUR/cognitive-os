from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

import cognitive_os.actions.service as action_service_module
import cognitive_os.api.app as api_app
from cognitive_os.actions.browser import BrowserActionService
from cognitive_os.actions.browser_preview import (
    BrowserPreviewProviderResult,
    BrowserPreviewService,
)
from cognitive_os.actions.calendar import CalendarStatus, EventCreatePreview, EventCreateRequest
from cognitive_os.actions.computer import ComputerActionService
from cognitive_os.actions.documents import DocumentActionService
from cognitive_os.actions.domains import GoDaddyActionService
from cognitive_os.actions.drive import (
    DriveFolderPreview,
    DriveFolderRequest,
    DriveOrganizePreview,
    DriveOrganizeRequest,
    DriveStatus,
    DriveUploadPreview,
    DriveUploadRequest,
)
from cognitive_os.actions.mail import GmailActionService
from cognitive_os.actions.payload_crypto import is_encrypted_payload, reveal_payload
from cognitive_os.actions.schemas import (
    ActionRequestView,
    BrowserNavigationRequest,
    BrowserPreviewRequest,
    ComputerOrganizeRequest,
    DocumentGenerateRequest,
    DocumentSection,
    GmailQueryPreviewRequest,
    GoDaddyDnsRecordChange,
    SlideContent,
    SpreadsheetSheet,
)
from cognitive_os.actions.service import ActionDispatchReservation, ActionRequestService
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import Settings
from cognitive_os.db.models import ActionRequest, AuditEvent, HumanApproval, Job, JobEvent


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


class _FakeActionRequestSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.executed_stmts: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def execute(self, stmt: object) -> object:
        """Default fake: every SELECT returns no rows.

        Tests that need to simulate an existing ActionRequest (idempotency dedup)
        should subclass and override.
        """
        self.executed_stmts.append(stmt)

        class _EmptyResult:
            @staticmethod
            def scalar_one_or_none() -> None:
                return None

        return _EmptyResult()

    async def flush(self) -> None:
        now = datetime.now(UTC)
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()
            if getattr(obj, "created_at", None) is None:
                obj.created_at = now
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = now
            if hasattr(obj, "result") and getattr(obj, "result", None) is None:
                obj.result = {}


def _install_fake_action_session(
    monkeypatch: pytest.MonkeyPatch,
) -> list[_FakeActionRequestSession]:
    sessions: list[_FakeActionRequestSession] = []

    @asynccontextmanager
    async def fake_session_scope():
        session = _FakeActionRequestSession()
        sessions.append(session)
        yield session

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)
    return sessions


def _only_added(session: _FakeActionRequestSession, model: type[object]) -> object:
    matches = [obj for obj in session.added if isinstance(obj, model)]
    assert len(matches) == 1
    return matches[0]


def test_browser_validation_blocks_when_disabled() -> None:
    service = BrowserActionService(Settings(_env_file=None, enable_browser_automation=False))

    result = service.validate_navigation(BrowserNavigationRequest(url="https://example.com"))

    assert result.allowed is False
    assert result.reason == "Browser automation is disabled."


def test_browser_validation_requires_allowlisted_domain() -> None:
    service = BrowserActionService(
        Settings(
            _env_file=None,
            enable_browser_automation=True,
            browser_allowed_domains="example.com",
            enable_browser_ssrf_check=False,
        )
    )

    denied = service.validate_navigation(BrowserNavigationRequest(url="https://evil.test"))
    allowed = service.validate_navigation(
        BrowserNavigationRequest(
            url="https://app.example.com/dashboard",
            persistent_session=True,
            session_name="user profile",
        )
    )

    assert denied.allowed is False
    assert denied.reason == "Domain is not allow-listed: evil.test"
    assert allowed.allowed is True
    assert allowed.normalized_origin == "https://app.example.com"
    assert allowed.profile_dir is not None
    assert allowed.profile_dir.endswith("user_profile")


def test_browser_validation_blocks_headed_and_vision_unless_enabled() -> None:
    service = BrowserActionService(
        Settings(
            _env_file=None,
            enable_browser_automation=True,
            browser_allowed_domains="example.com",
            browser_allow_headed=False,
            browser_allow_vision=False,
            enable_browser_ssrf_check=False,
        )
    )

    headed = service.validate_navigation(
        BrowserNavigationRequest(url="https://example.com", headed=True)
    )
    vision = service.validate_navigation(
        BrowserNavigationRequest(url="https://example.com", vision=True)
    )

    assert headed.allowed is False
    assert headed.reason == "Headed browser automation is disabled."
    assert vision.allowed is False
    assert vision.reason == "Vision browser automation is disabled."


def test_computer_organize_plan_is_preview_only(tmp_path: Path) -> None:
    root = tmp_path / "downloads"
    root.mkdir()
    (root / "contract.pdf").write_text("pdf", encoding="utf-8")
    (root / "photo.png").write_text("png", encoding="utf-8")
    (root / "unknown.bin").write_text("bin", encoding="utf-8")
    service = ComputerActionService(
        Settings(
            _env_file=None,
            enable_computer_actions=True,
            computer_allowed_roots=[str(tmp_path)],
            computer_max_files_per_plan=10,
            computer_organize_dry_run_only=True,
        )
    )

    plan = service.build_organize_plan(ComputerOrganizeRequest(root_path=str(root)))

    assert plan.status == "ok"
    assert plan.dry_run_only is True
    assert [operation.destination for operation in plan.operations] == [
        "PDFs/contract.pdf",
        "Images/photo.png",
    ]
    assert (root / "contract.pdf").exists()


def test_computer_organize_execution_moves_files_when_enabled(tmp_path: Path) -> None:
    root = tmp_path / "downloads"
    root.mkdir()
    (root / "contract.pdf").write_text("pdf", encoding="utf-8")
    (root / "photo.png").write_text("png", encoding="utf-8")
    service = ComputerActionService(
        Settings(
            _env_file=None,
            enable_computer_actions=True,
            computer_allowed_roots=[str(tmp_path)],
            computer_organize_dry_run_only=False,
            computer_max_files_per_plan=10,
        )
    )

    result = service.execute_organize_plan(ComputerOrganizeRequest(root_path=str(root)))

    assert result.status == "completed"
    assert result.moved_count == 2
    assert not (root / "contract.pdf").exists()
    assert (root / "PDFs" / "contract.pdf").read_text(encoding="utf-8") == "pdf"
    assert (root / "Images" / "photo.png").read_text(encoding="utf-8") == "png"


def test_computer_organize_execution_blocks_when_dry_run_only(tmp_path: Path) -> None:
    root = tmp_path / "downloads"
    root.mkdir()
    (root / "contract.pdf").write_text("pdf", encoding="utf-8")
    service = ComputerActionService(
        Settings(
            _env_file=None,
            enable_computer_actions=True,
            computer_allowed_roots=[str(tmp_path)],
            computer_organize_dry_run_only=True,
        )
    )

    result = service.execute_organize_plan(ComputerOrganizeRequest(root_path=str(root)))

    assert result.status == "blocked"
    assert result.reason == "Computer organize execution is dry-run only by configuration."
    assert (root / "contract.pdf").exists()


def test_computer_organize_blocks_paths_outside_allowed_roots(tmp_path: Path) -> None:
    service = ComputerActionService(
        Settings(
            enable_computer_actions=True,
            computer_allowed_roots=[str(tmp_path / "allowed")],
        )
    )

    plan = service.build_organize_plan(ComputerOrganizeRequest(root_path=str(tmp_path)))

    assert plan.status == "blocked"
    assert plan.reason == "computer path is outside allowed roots."


def test_gmail_query_preview_respects_read_flag() -> None:
    disabled = GmailActionService(Settings(gmail_read_enabled=False)).preview_query(
        GmailQueryPreviewRequest(query="from:client")
    )
    enabled = GmailActionService(
        Settings(
            gmail_read_enabled=True,
            gmail_client_id="client-id",
            gmail_client_secret="client-secret",  # pragma: allowlist secret
        )
    ).preview_query(GmailQueryPreviewRequest(query="from:client", max_results=5))

    assert disabled.status == "blocked"
    assert disabled.reason == "Gmail read is disabled."
    assert enabled.status == "ok"
    assert enabled.max_results == 5
    assert "gmail.readonly" in enabled.scopes[0]


def test_gmail_status_does_not_expose_token_paths(tmp_path: Path) -> None:
    service = GmailActionService(
        Settings(
            gmail_read_enabled=True,
            gmail_client_id="client-id",
            gmail_client_secret="client-secret",  # pragma: allowlist secret
            gmail_token_dir=tmp_path / "oauth" / "gmail",
        )
    )

    status = service.status()

    assert status.status == "configured"
    assert "token_path" not in status.metadata
    assert "token_dir" not in status.metadata
    assert str(tmp_path) not in " ".join(status.reasons)


def test_godaddy_dns_preview_is_dry_run_and_requires_approval() -> None:
    service = GoDaddyActionService(
        Settings(
            _env_file=None,
            godaddy_enabled=True,
            godaddy_api_key="key",  # pragma: allowlist secret
            godaddy_api_secret="secret",  # pragma: allowlist secret
            godaddy_base_url="https://api.ote-godaddy.com",
            require_human_approval_for_external_actions=True,
        )
    )

    result = service.preview_dns_change(
        GoDaddyDnsRecordChange(
            domain="Example.COM.",
            record_type="A",
            name="@",
            data="203.0.113.10",
        )
    )

    assert result.status == "ok"
    assert result.dry_run_only is True
    assert result.requires_approval is True
    assert result.change.domain == "example.com"
    assert result.endpoint == "https://api.ote-godaddy.com/v1/domains/example.com/records"


def test_godaddy_dns_preview_blocks_invalid_domain() -> None:
    result = GoDaddyActionService(
        Settings(
            godaddy_enabled=True,
            godaddy_api_key="key",  # pragma: allowlist secret
            godaddy_api_secret="secret",  # pragma: allowlist secret
        )
    ).preview_dns_change(
        GoDaddyDnsRecordChange(
            domain="../example.com",
            record_type="TXT",
            name="@",
            data="hello",
        )
    )

    assert result.status == "blocked"
    assert result.reason == "Invalid domain format."


def test_godaddy_dns_preview_requires_allowed_domain_for_real_writes() -> None:
    service = GoDaddyActionService(
        Settings(
            godaddy_enabled=True,
            godaddy_api_key="key",  # pragma: allowlist secret
            godaddy_api_secret="secret",  # pragma: allowlist secret
            godaddy_base_url="https://api.ote-godaddy.com",
            godaddy_dns_dry_run_only=False,
            godaddy_allowed_domains=[],
        )
    )

    result = service.preview_dns_change(
        GoDaddyDnsRecordChange(
            domain="example.com",
            record_type="A",
            name="@",
            data="203.0.113.10",
        )
    )

    assert result.status == "blocked"
    assert "GODADDY_ALLOWED_DOMAINS" in (result.reason or "")


def test_godaddy_dns_preview_blocks_production_writes_without_explicit_flag() -> None:
    service = GoDaddyActionService(
        Settings(
            godaddy_enabled=True,
            godaddy_api_key="key",  # pragma: allowlist secret
            godaddy_api_secret="secret",  # pragma: allowlist secret
            godaddy_base_url="https://api.godaddy.com",
            godaddy_dns_dry_run_only=False,
            godaddy_allowed_domains=["example.com"],
            godaddy_allow_production_writes=False,
        )
    )

    result = service.preview_dns_change(
        GoDaddyDnsRecordChange(
            domain="example.com",
            record_type="TXT",
            name="_verify",
            data="ok",
        )
    )

    assert result.status == "blocked"
    assert "GODADDY_ALLOW_PRODUCTION_WRITES" in (result.reason or "")


class _FakeGoDaddyResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None


class _FakeGoDaddyClient:
    def __init__(self) -> None:
        self.patch_calls: list[dict[str, object]] = []

    def __enter__(self) -> _FakeGoDaddyClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def patch(
        self,
        endpoint: str,
        *,
        headers: dict[str, str],
        json: list[dict[str, object]],
    ) -> _FakeGoDaddyResponse:
        self.patch_calls.append({"endpoint": endpoint, "headers": headers, "json": json})
        return _FakeGoDaddyResponse()


def test_godaddy_dns_execute_real_write_uses_approved_payload() -> None:
    client = _FakeGoDaddyClient()
    service = GoDaddyActionService(
        Settings(
            godaddy_enabled=True,
            godaddy_api_key="key",  # pragma: allowlist secret
            godaddy_api_secret="secret",  # pragma: allowlist secret
            godaddy_base_url="https://api.ote-godaddy.com",
            godaddy_dns_dry_run_only=False,
            godaddy_allowed_domains=["example.com"],
        ),
        http_client_factory=lambda: client,
    )

    result = service.execute_dns_change(
        GoDaddyDnsRecordChange(
            domain="Example.COM.",
            record_type="MX",
            name="@",
            data="mail.example.com",
            priority=10,
        )
    )

    assert result.status == "completed"
    assert result.dry_run_only is False
    assert client.patch_calls
    call = client.patch_calls[0]
    assert call["endpoint"] == "https://api.ote-godaddy.com/v1/domains/example.com/records"
    assert call["headers"]["Authorization"] == "sso-key key:secret"  # type: ignore[index]
    assert call["json"] == [
        {"type": "MX", "name": "@", "data": "mail.example.com", "ttl": 600, "priority": 10}
    ]


def test_godaddy_dns_execute_blocks_when_still_dry_run() -> None:
    service = GoDaddyActionService(
        Settings(
            godaddy_enabled=True,
            godaddy_api_key="key",  # pragma: allowlist secret
            godaddy_api_secret="secret",  # pragma: allowlist secret
        )
    )

    result = service.execute_dns_change(
        GoDaddyDnsRecordChange(
            domain="example.com",
            record_type="A",
            name="@",
            data="203.0.113.10",
        )
    )

    assert result.status == "blocked"
    assert "dry-run" in (result.reason or "")


def test_godaddy_status_reflects_execution_policy() -> None:
    service = GoDaddyActionService(
        Settings(
            _env_file=None,
            godaddy_enabled=True,
            godaddy_api_key="key",  # pragma: allowlist secret
            godaddy_api_secret="secret",  # pragma: allowlist secret
            godaddy_base_url="https://api.ote-godaddy.com",
            godaddy_dns_dry_run_only=False,
            godaddy_allowed_domains=["example.com"],
            require_human_approval_for_external_actions=False,
        )
    )

    status = service.status()

    assert status.status == "ready"
    assert status.dry_run_only is False
    assert status.requires_approval is False


@pytest.mark.asyncio
async def test_action_capabilities_endpoint_requires_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.get("/actions/capabilities")
        authorized = await client.get("/actions/capabilities", headers=_headers())

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert {item["name"] for item in authorized.json()} == {
        "browser",
        "computer",
        "documents",
        "gmail",
        "godaddy",
        "maps",
        "google_calendar",
        "google_drive",
    }


@pytest.mark.asyncio
async def test_computer_organize_request_endpoint_uses_action_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(status="previewed", job_id=None)

    class FakeActionRequestService:
        async def create_computer_organize_request(
            self,
            request: ComputerOrganizeRequest,
            *,
            requested_by: str,
        ) -> ActionRequestView:
            assert request.root_path == "/tmp/downloads"
            assert requested_by == "1"
            return view

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/computer/organize/request",
            json={"root_path": "/tmp/downloads"},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(view.id)
    assert response.json()["status"] == "previewed"


@pytest.mark.asyncio
async def test_calendar_request_endpoint_uses_action_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(
        status="pending_approval",
        job_id=UUID("22222222-2222-2222-2222-222222222222"),
        action_type="calendar_create_event",
    )

    class FakeActionRequestService:
        async def create_calendar_event_request(
            self,
            request: EventCreateRequest,
            *,
            requested_by: str,
        ) -> ActionRequestView:
            assert request.summary == "Reunion"
            assert requested_by == "1"
            return view

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/calendar/events/request",
            json={
                "summary": "Reunion",
                "start": "2026-06-01T10:00:00Z",
                "end": "2026-06-01T11:00:00Z",
            },
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["action_type"] == "calendar_create_event"
    assert response.json()["status"] == "pending_approval"


@pytest.mark.asyncio
async def test_drive_upload_request_endpoint_uses_action_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(
        status="pending_approval",
        job_id=UUID("22222222-2222-2222-2222-222222222222"),
        action_type="drive_upload_file",
    )

    class FakeActionRequestService:
        async def create_drive_upload_request(
            self,
            request: DriveUploadRequest,
            *,
            requested_by: str,
        ) -> ActionRequestView:
            assert request.local_path == "/tmp/result.md"
            assert request.use_deliverables_folder is True
            assert requested_by == "1"
            return view

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/drive/files/upload/request",
            json={"local_path": "/tmp/result.md"},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["action_type"] == "drive_upload_file"
    assert response.json()["status"] == "pending_approval"


@pytest.mark.asyncio
async def test_drive_folder_request_endpoint_uses_action_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(
        status="pending_approval",
        job_id=UUID("22222222-2222-2222-2222-222222222222"),
        action_type="drive_ensure_folder",
    )

    class FakeActionRequestService:
        async def create_drive_folder_request(
            self,
            request: DriveFolderRequest,
            *,
            requested_by: str,
        ) -> ActionRequestView:
            assert request.dry_run is False
            assert requested_by == "1"
            return view

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/drive/folders/ensure/request",
            json={"dry_run": False},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["action_type"] == "drive_ensure_folder"
    assert response.json()["status"] == "pending_approval"


@pytest.mark.asyncio
async def test_drive_organize_request_endpoint_uses_action_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(
        status="pending_approval",
        job_id=UUID("22222222-2222-2222-2222-222222222222"),
        action_type="drive_organize_files",
    )

    class FakeActionRequestService:
        async def create_drive_organize_request(
            self,
            request: DriveOrganizeRequest,
            *,
            requested_by: str,
        ) -> ActionRequestView:
            assert request.query == "factura"
            assert request.target_folder_name == "Finanzas"
            assert request.dry_run is False
            assert requested_by == "1"
            return view

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/drive/organize/request",
            json={"query": "factura", "target_folder_name": "Finanzas", "dry_run": False},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["action_type"] == "drive_organize_files"
    assert response.json()["status"] == "pending_approval"


@pytest.mark.asyncio
async def test_calendar_action_request_service_persists_approval_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions = _install_fake_action_session(monkeypatch)

    class FakeCalendarService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def create_event(self, request: EventCreateRequest) -> EventCreatePreview:
            assert request.dry_run is True
            return EventCreatePreview(status="preview", payload={"summary": request.summary})

        def status(self) -> CalendarStatus:
            return CalendarStatus(status="ready", write_enabled=True)

    monkeypatch.setattr(action_service_module, "CalendarService", FakeCalendarService)
    service = ActionRequestService(
        Settings(
            _env_file=None,
            enable_google_calendar=True,
            enable_google_calendar_write=True,
            google_client_id="client-id",
            google_client_secret="client-secret",  # pragma: allowlist secret
        )
    )

    view = await service.create_calendar_event_request(
        EventCreateRequest(
            summary="Reunion",
            start=datetime(2026, 6, 1, 10, tzinfo=UTC),
            end=datetime(2026, 6, 1, 11, tzinfo=UTC),
        ),
        requested_by="operator-1",
    )

    assert len(sessions) == 1
    session = sessions[0]
    action_request = _only_added(session, ActionRequest)
    job = _only_added(session, Job)
    approval = _only_added(session, HumanApproval)
    job_event = _only_added(session, JobEvent)
    audit_event = _only_added(session, AuditEvent)

    assert isinstance(action_request, ActionRequest)
    assert isinstance(job, Job)
    assert isinstance(approval, HumanApproval)
    assert isinstance(job_event, JobEvent)
    assert isinstance(audit_event, AuditEvent)
    assert view.status == "pending_approval"
    assert view.action_type == "calendar_create_event"
    assert action_request.status == "pending_approval"
    assert action_request.action_type == "calendar_create_event"
    assert action_request.payload_executable is not None
    assert action_request.payload_executable["dry_run"] is False
    assert action_request.preview["status"] == "preview"
    assert action_request.job_id == job.id
    assert action_request.approval_id == approval.id
    assert approval.requested_action == f"execute_action_request:{action_request.id}"
    assert job.status == "waiting_approval"
    assert job_event.event_type == "action_approval_required"
    assert audit_event.action == "action_request.created"


@pytest.mark.asyncio
async def test_action_request_payload_executable_is_encrypted_when_key_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions = _install_fake_action_session(monkeypatch)

    class FakeCalendarService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def create_event(self, request: EventCreateRequest) -> EventCreatePreview:
            assert request.dry_run is True
            return EventCreatePreview(status="preview", payload={"summary": request.summary})

        def status(self) -> CalendarStatus:
            return CalendarStatus(status="ready", write_enabled=True)

    cfg = Settings(
        _env_file=None,
        enable_google_calendar=True,
        enable_google_calendar_write=True,
        google_client_id="client-id",
        google_client_secret="client-secret",  # pragma: allowlist secret
        action_payload_encryption_key="unit-test-action-payload-key",  # pragma: allowlist secret
        action_payload_encryption_required=True,
    )
    monkeypatch.setattr(action_service_module, "CalendarService", FakeCalendarService)
    service = ActionRequestService(cfg)

    await service.create_calendar_event_request(
        EventCreateRequest(
            summary="Reunion cifrada",
            start=datetime(2026, 6, 1, 10, tzinfo=UTC),
            end=datetime(2026, 6, 1, 11, tzinfo=UTC),
        ),
        requested_by="operator-1",
    )

    action_request = _only_added(sessions[0], ActionRequest)
    assert isinstance(action_request, ActionRequest)
    assert is_encrypted_payload(action_request.payload_executable)
    assert "Reunion cifrada" not in str(action_request.payload_executable)
    revealed = reveal_payload(
        action_request.payload_executable,
        action_request.payload_redacted,
        cfg,
    )
    assert revealed["summary"] == "Reunion cifrada"
    assert revealed["dry_run"] is False


@pytest.mark.asyncio
async def test_calendar_action_request_dedups_repeat_submissions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same (action_type, requester, payload) within an active state -> no duplicate."""
    sessions: list[_FakeActionRequestSession] = []
    now = datetime.now(UTC)
    existing_request = ActionRequest(
        id=UUID("99999999-9999-9999-9999-999999999999"),
        action_type="calendar_create_event",
        status="pending_approval",
        requested_by="operator-1",
        idempotency_key=None,
        approval_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        job_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        payload_redacted={},
        payload_executable={},
        preview={"status": "preview"},
        result={},
        created_at=now,
        updated_at=now,
    )

    class _DedupSession(_FakeActionRequestSession):
        async def execute(self, stmt: object) -> object:
            self.executed_stmts.append(stmt)

            class _Result:
                @staticmethod
                def scalar_one_or_none() -> ActionRequest:
                    return existing_request

            return _Result()

    @asynccontextmanager
    async def fake_session_scope():
        session = _DedupSession()
        sessions.append(session)
        yield session

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)

    class FakeCalendarService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def create_event(self, request: EventCreateRequest) -> EventCreatePreview:
            return EventCreatePreview(status="preview", payload={"summary": request.summary})

        def status(self) -> CalendarStatus:
            return CalendarStatus(status="ready", write_enabled=True)

    monkeypatch.setattr(action_service_module, "CalendarService", FakeCalendarService)
    service = ActionRequestService(
        Settings(
            _env_file=None,
            enable_google_calendar=True,
            enable_google_calendar_write=True,
            google_client_id="client-id",
            google_client_secret="client-secret",  # pragma: allowlist secret
        )
    )

    view = await service.create_calendar_event_request(
        EventCreateRequest(
            summary="Reunion repetida",
            start=datetime(2026, 6, 1, 10, tzinfo=UTC),
            end=datetime(2026, 6, 1, 11, tzinfo=UTC),
        ),
        requested_by="operator-1",
    )

    assert view.id == existing_request.id
    assert view.status == "pending_approval"
    # No new ActionRequest/HumanApproval/Job rows were inserted.
    assert sessions[0].added == []


@pytest.mark.asyncio
async def test_drive_upload_action_request_service_persists_approval_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions = _install_fake_action_session(monkeypatch)

    class FakeDriveService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def upload_file(self, request: DriveUploadRequest) -> DriveUploadPreview:
            assert request.dry_run is True
            return DriveUploadPreview(
                status="preview",
                drive_name="result.md",
                mime_type="text/markdown",
                size_bytes=123,
                folder_name="Cognitive OS Deliverables",
            )

        def status(self) -> DriveStatus:
            return DriveStatus(
                status="ready",
                write_enabled=True,
                upload_max_bytes=2048,
                deliverables_folder_name="Cognitive OS Deliverables",
            )

    monkeypatch.setattr(action_service_module, "DriveService", FakeDriveService)
    service = ActionRequestService(
        Settings(
            _env_file=None,
            enable_google_drive=True,
            enable_google_drive_write=True,
            google_client_id="client-id",
            google_client_secret="client-secret",  # pragma: allowlist secret
            google_drive_upload_max_bytes=2048,
        )
    )

    view = await service.create_drive_upload_request(
        DriveUploadRequest(local_path="/tmp/result.md", mime_type="text/markdown"),
        requested_by="operator-1",
    )

    assert len(sessions) == 1
    session = sessions[0]
    action_request = _only_added(session, ActionRequest)
    job = _only_added(session, Job)
    approval = _only_added(session, HumanApproval)
    job_event = _only_added(session, JobEvent)
    audit_event = _only_added(session, AuditEvent)

    assert isinstance(action_request, ActionRequest)
    assert isinstance(job, Job)
    assert isinstance(approval, HumanApproval)
    assert isinstance(job_event, JobEvent)
    assert isinstance(audit_event, AuditEvent)
    assert view.status == "pending_approval"
    assert view.action_type == "drive_upload_file"
    assert action_request.status == "pending_approval"
    assert action_request.action_type == "drive_upload_file"
    assert action_request.payload_executable is not None
    assert action_request.payload_executable["dry_run"] is False
    assert action_request.payload_executable["use_deliverables_folder"] is True
    assert action_request.preview["folder_name"] == "Cognitive OS Deliverables"
    assert action_request.job_id == job.id
    assert action_request.approval_id == approval.id
    assert approval.requested_action == f"execute_action_request:{action_request.id}"
    assert job.status == "waiting_approval"
    assert job_event.event_type == "action_approval_required"
    assert audit_event.action == "action_request.created"


@pytest.mark.asyncio
async def test_drive_folder_action_request_service_persists_approval_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions = _install_fake_action_session(monkeypatch)

    class FakeDriveService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def ensure_deliverables_folder(
            self,
            request: DriveFolderRequest,
            *,
            requested_by: str | None = None,
        ) -> DriveFolderPreview:
            assert request.dry_run is True
            assert requested_by == "operator-1"
            return DriveFolderPreview(
                status="preview",
                folder_name="Cognitive OS Deliverables",
            )

        def status(self) -> DriveStatus:
            return DriveStatus(
                status="ready",
                write_enabled=True,
                upload_max_bytes=2048,
                deliverables_folder_name="Cognitive OS Deliverables",
            )

    monkeypatch.setattr(action_service_module, "DriveService", FakeDriveService)
    service = ActionRequestService(
        Settings(
            _env_file=None,
            enable_google_drive=True,
            enable_google_drive_write=True,
            google_client_id="client-id",
            google_client_secret="client-secret",  # pragma: allowlist secret
            google_drive_upload_max_bytes=2048,
        )
    )

    view = await service.create_drive_folder_request(
        DriveFolderRequest(dry_run=False),
        requested_by="operator-1",
    )

    session = sessions[0]
    action_request = _only_added(session, ActionRequest)
    job = _only_added(session, Job)
    approval = _only_added(session, HumanApproval)
    job_event = _only_added(session, JobEvent)

    assert isinstance(action_request, ActionRequest)
    assert isinstance(job, Job)
    assert isinstance(approval, HumanApproval)
    assert isinstance(job_event, JobEvent)
    assert view.status == "pending_approval"
    assert view.action_type == "drive_ensure_folder"
    assert action_request.status == "pending_approval"
    assert action_request.action_type == "drive_ensure_folder"
    assert action_request.payload_executable is not None
    assert action_request.payload_executable["dry_run"] is False
    assert action_request.preview["folder_name"] == "Cognitive OS Deliverables"
    assert action_request.job_id == job.id
    assert action_request.approval_id == approval.id
    assert approval.requested_action == f"execute_action_request:{action_request.id}"
    assert job.status == "waiting_approval"
    assert job_event.event_type == "action_approval_required"


@pytest.mark.asyncio
async def test_drive_organize_action_request_service_persists_approval_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions = _install_fake_action_session(monkeypatch)

    class FakeDriveService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def organize_files(
            self,
            request: DriveOrganizeRequest,
            *,
            requested_by: str | None = None,
        ) -> DriveOrganizePreview:
            assert request.dry_run is True
            assert requested_by == "operator-1"
            return DriveOrganizePreview(
                status="preview",
                query=request.query,
                target_folder_name=request.target_folder_name or "Cognitive OS Deliverables",
                dry_run=True,
                operation_count=1,
                operations=[],
            )

        def status(self) -> DriveStatus:
            return DriveStatus(
                status="ready",
                write_enabled=True,
                upload_max_bytes=2048,
                deliverables_folder_name="Cognitive OS Deliverables",
            )

    monkeypatch.setattr(action_service_module, "DriveService", FakeDriveService)
    service = ActionRequestService(
        Settings(
            _env_file=None,
            enable_google_drive=True,
            enable_google_drive_write=True,
            google_client_id="client-id",
            google_client_secret="client-secret",  # pragma: allowlist secret
            google_drive_upload_max_bytes=2048,
        )
    )

    view = await service.create_drive_organize_request(
        DriveOrganizeRequest(query="factura", target_folder_name="Finanzas", dry_run=False),
        requested_by="operator-1",
    )

    session = sessions[0]
    action_request = _only_added(session, ActionRequest)
    job = _only_added(session, Job)
    approval = _only_added(session, HumanApproval)
    job_event = _only_added(session, JobEvent)

    assert isinstance(action_request, ActionRequest)
    assert isinstance(job, Job)
    assert isinstance(approval, HumanApproval)
    assert isinstance(job_event, JobEvent)
    assert view.status == "pending_approval"
    assert view.action_type == "drive_organize_files"
    assert action_request.status == "pending_approval"
    assert action_request.action_type == "drive_organize_files"
    assert action_request.payload_executable is not None
    assert action_request.payload_executable["dry_run"] is False
    assert action_request.preview["target_folder_name"] == "Finanzas"
    assert action_request.job_id == job.id
    assert action_request.approval_id == approval.id
    assert approval.requested_action == f"execute_action_request:{action_request.id}"
    assert job.status == "waiting_approval"
    assert job_event.event_type == "action_approval_required"


@pytest.mark.asyncio
async def test_dispatch_missing_action_request_reports_blocked_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_id = UUID("00000000-0000-0000-0000-000000000000")
    calls: list[dict[str, object]] = []

    class FakeActionRequestService:
        async def queue_approved_action_request(self, action_request_id: UUID) -> ActionRequestView:
            assert action_request_id == missing_id
            msg = (
                "Action request not found; dispatch blocked before side effects: "
                f"{action_request_id}"
            )
            raise action_service_module.ActionRequestError(msg)

    class FakeTask:
        @staticmethod
        def apply_async(*, args: list[str], queue: str) -> None:
            calls.append({"args": args, "queue": queue})

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)
    monkeypatch.setattr(api_app, "run_action_request_task_async", FakeTask)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/actions/requests/{missing_id}/dispatch",
            headers=_headers(),
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "not found" in detail.lower()
    assert "dispatch blocked before side effects" in detail.lower()
    assert calls == []


@pytest.mark.asyncio
async def test_dispatch_action_request_enqueues_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(
        status="queued",
        job_id=UUID("22222222-2222-2222-2222-222222222222"),
    )
    calls: list[dict[str, object]] = []
    events: list[dict[str, object]] = []

    class FakeActionRequestService:
        async def queue_approved_action_request(self, action_request_id: UUID) -> ActionRequestView:
            assert action_request_id == view.id
            return view

        async def reserve_action_dispatch(
            self, action_request_id: UUID
        ) -> ActionDispatchReservation:
            assert action_request_id == view.id
            return ActionDispatchReservation(action_request=view, should_dispatch=True)

        async def record_action_dispatch_event(
            self,
            *,
            job_id: UUID,
            action_request_id: UUID,
            event_type: str,
            status: str,
            message: str,
            metadata_json: dict[str, object] | None = None,
        ) -> None:
            events.append(
                {
                    "job_id": job_id,
                    "action_request_id": action_request_id,
                    "event_type": event_type,
                    "status": status,
                    "message": message,
                    "metadata_json": metadata_json or {},
                }
            )

    class FakeTask:
        @staticmethod
        def apply_async(*, args: list[str], queue: str) -> None:
            calls.append({"args": args, "queue": queue})

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)
    monkeypatch.setattr(api_app, "run_action_request_task_async", FakeTask)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/actions/requests/{view.id}/dispatch",
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["dispatched"] is True
    assert calls == [
        {
            "args": [str(view.id), str(view.job_id)],
            "queue": "agent_longrun",
        }
    ]
    assert events == [
        {
            "job_id": view.job_id,
            "action_request_id": view.id,
            "event_type": "action_request_dispatch_submitted",
            "status": "queued",
            "message": "Action request submitted to Celery",
            "metadata_json": {"queue": "agent_longrun"},
        }
    ]


@pytest.mark.asyncio
async def test_dispatch_action_request_reports_celery_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(
        status="queued",
        job_id=UUID("22222222-2222-2222-2222-222222222222"),
    )
    events: list[dict[str, object]] = []

    class FakeActionRequestService:
        async def queue_approved_action_request(self, action_request_id: UUID) -> ActionRequestView:
            assert action_request_id == view.id
            return view

        async def reserve_action_dispatch(
            self, action_request_id: UUID
        ) -> ActionDispatchReservation:
            assert action_request_id == view.id
            return ActionDispatchReservation(action_request=view, should_dispatch=True)

        async def record_action_dispatch_event(
            self,
            *,
            job_id: UUID,
            action_request_id: UUID,
            event_type: str,
            status: str,
            message: str,
            metadata_json: dict[str, object] | None = None,
        ) -> None:
            events.append(
                {
                    "job_id": job_id,
                    "action_request_id": action_request_id,
                    "event_type": event_type,
                    "status": status,
                    "message": message,
                    "metadata_json": metadata_json or {},
                }
            )

    class FakeTask:
        @staticmethod
        def apply_async(*, args: list[str], queue: str) -> None:
            assert args == [str(view.id), str(view.job_id)]
            assert queue == "agent_longrun"
            raise RuntimeError("broker down")

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)
    monkeypatch.setattr(api_app, "run_action_request_task_async", FakeTask)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/actions/requests/{view.id}/dispatch",
            headers=_headers(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["dispatched"] is False
    assert "Celery dispatch failed (RuntimeError)" in body["reason"]
    assert events == [
        {
            "job_id": view.job_id,
            "action_request_id": view.id,
            "event_type": "action_request_dispatch_failed",
            "status": "queued",
            "message": "Action request dispatch failed before Celery accepted it",
            "metadata_json": {"error_type": "RuntimeError"},
        }
    ]


@pytest.mark.asyncio
async def test_dispatch_action_request_does_not_enqueue_when_already_submitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(
        status="queued",
        job_id=UUID("22222222-2222-2222-2222-222222222222"),
    )
    calls: list[dict[str, object]] = []

    class FakeActionRequestService:
        async def queue_approved_action_request(self, action_request_id: UUID) -> ActionRequestView:
            assert action_request_id == view.id
            return view

        async def reserve_action_dispatch(
            self, action_request_id: UUID
        ) -> ActionDispatchReservation:
            assert action_request_id == view.id
            return ActionDispatchReservation(
                action_request=view,
                should_dispatch=False,
                reason="Action request dispatch already submitted; waiting for worker.",
            )

    class FakeTask:
        @staticmethod
        def apply_async(*, args: list[str], queue: str) -> None:
            calls.append({"args": args, "queue": queue})

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)
    monkeypatch.setattr(api_app, "run_action_request_task_async", FakeTask)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/actions/requests/{view.id}/dispatch",
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["dispatched"] is False
    assert response.json()["reason"] == (
        "Action request dispatch already submitted; waiting for worker."
    )
    assert calls == []


@pytest.mark.asyncio
async def test_dispatch_action_request_does_not_enqueue_non_queued_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(
        status="completed",
        job_id=UUID("22222222-2222-2222-2222-222222222222"),
    )
    calls: list[dict[str, object]] = []

    class FakeActionRequestService:
        async def queue_approved_action_request(self, action_request_id: UUID) -> ActionRequestView:
            assert action_request_id == view.id
            return view

    class FakeTask:
        @staticmethod
        def apply_async(*, args: list[str], queue: str) -> None:
            calls.append({"args": args, "queue": queue})

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)
    monkeypatch.setattr(api_app, "run_action_request_task_async", FakeTask)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/actions/requests/{view.id}/dispatch",
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["dispatched"] is False
    assert response.json()["reason"] == "Action request status is completed; nothing queued."
    assert calls == []


@pytest.mark.asyncio
async def test_queue_approved_action_request_locks_row_before_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action_request_id = UUID("12121212-1212-1212-1212-121212121212")
    approval_id = UUID("34343434-3434-3434-3434-343434343434")
    job_id = UUID("56565656-5656-5656-5656-565656565656")
    now = datetime.now(UTC)
    action_request = ActionRequest(
        id=action_request_id,
        action_type="browser_preview",
        status="pending_approval",
        requested_by="operator-1",
        approval_id=approval_id,
        job_id=job_id,
        idempotency_key="idem",
        payload_redacted={},
        payload_executable={},
        preview={},
        result={},
        metadata_json={},
        created_at=now,
        updated_at=now,
    )
    approval = HumanApproval(
        id=approval_id,
        status="approved",
        action="execute_action_request",
        requested_action=f"execute_action_request:{action_request_id}",
        args_redacted={},
        requested_by="operator-1",
        job_id=job_id,
    )
    job = Job(
        id=job_id,
        job_type="external_action",
        status="waiting_approval",
        progress=0,
        created_at=now,
        updated_at=now,
    )
    captured: dict[str, object] = {}

    class _Scalar:
        def scalar_one_or_none(self) -> ActionRequest:
            return action_request

    class _Session(_FakeActionRequestSession):
        async def execute(self, stmt: object) -> _Scalar:
            captured["for_update"] = getattr(stmt, "_for_update_arg", None) is not None
            return _Scalar()

        async def get(self, model: type[object], row_id: UUID) -> object | None:
            if model is HumanApproval and row_id == approval_id:
                return approval
            if model is Job and row_id == job_id:
                return job
            return None

    @asynccontextmanager
    async def fake_session_scope():
        yield _Session()

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)

    view = await ActionRequestService().queue_approved_action_request(action_request_id)

    assert captured["for_update"] is True
    assert view.status == "queued"
    assert action_request.status == "queued"
    assert job.status == "queued"


@pytest.mark.asyncio
async def test_cancel_action_request_revokes_submitted_celery_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    action_request_id = UUID("41414141-4141-4141-4141-414141414141")
    job_id = UUID("51515151-5151-5151-5151-515151515151")
    action_request = ActionRequest(
        id=action_request_id,
        action_type="browser_preview",
        status="queued",
        requested_by="operator-1",
        job_id=job_id,
        payload_redacted={},
        payload_executable={},
        preview={},
        result={},
        metadata_json={},
        created_at=now,
        updated_at=now,
    )
    job = Job(
        id=job_id,
        job_type="external_action",
        status="queued",
        progress=10,
        metadata_json={"celery_task_id": "celery-action-1"},
        created_at=now,
        updated_at=now,
    )
    calls: list[dict[str, object]] = []
    added: list[object] = []

    class _Session(_FakeActionRequestSession):
        def add(self, obj: object) -> None:
            added.append(obj)

        async def get(self, model: type[object], row_id: UUID) -> object | None:
            if model is ActionRequest and row_id == action_request_id:
                return action_request
            if model is Job and row_id == job_id:
                return job
            return None

    @asynccontextmanager
    async def fake_session_scope():
        yield _Session()

    def fake_revoke(task_id: str, *, terminate: bool, signal: str) -> None:
        calls.append({"task_id": task_id, "terminate": terminate, "signal": signal})

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(action_service_module.celery_app.control, "revoke", fake_revoke)

    view = await ActionRequestService().cancel_action_request(
        action_request_id,
        requested_by="operator-1",
    )

    assert view.status == "cancelled"
    assert action_request.status == "cancelled"
    assert job.status == "cancelled"
    assert job.progress == 100
    assert job.metadata_json["celery_revoke_signal"] == "SIGTERM"
    assert calls == [{"task_id": "celery-action-1", "terminate": True, "signal": "SIGTERM"}]
    job_event = next(item for item in added if isinstance(item, JobEvent))
    assert job_event.event_type == "action_request_cancelled"
    assert job_event.metadata_json["celery_revoke_requested"] is True


@pytest.mark.asyncio
async def test_cancel_action_request_revoke_failure_keeps_queued_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    action_request_id = UUID("42424242-4242-4242-4242-424242424242")
    job_id = UUID("52525252-5252-5252-5252-525252525252")
    action_request = ActionRequest(
        id=action_request_id,
        action_type="browser_preview",
        status="queued",
        requested_by="operator-1",
        job_id=job_id,
        payload_redacted={},
        payload_executable={},
        preview={},
        result={},
        metadata_json={},
        created_at=now,
        updated_at=now,
    )
    job = Job(
        id=job_id,
        job_type="external_action",
        status="queued",
        progress=10,
        metadata_json={"celery_task_id": "celery-action-err"},
        created_at=now,
        updated_at=now,
    )
    added: list[object] = []

    class _Session(_FakeActionRequestSession):
        def add(self, obj: object) -> None:
            added.append(obj)

        async def get(self, model: type[object], row_id: UUID) -> object | None:
            if model is ActionRequest and row_id == action_request_id:
                return action_request
            if model is Job and row_id == job_id:
                return job
            return None

    @asynccontextmanager
    async def fake_session_scope():
        yield _Session()

    def fake_revoke(task_id: str, *, terminate: bool, signal: str) -> None:
        del task_id, terminate, signal
        raise RuntimeError("broker offline")

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(action_service_module.celery_app.control, "revoke", fake_revoke)

    view = await ActionRequestService().cancel_action_request(
        action_request_id,
        requested_by="operator-1",
    )

    assert view.status == "queued"
    assert action_request.status == "queued"
    assert job.status == "queued"
    assert job.metadata_json["celery_revoke_error_type"] == "RuntimeError"
    job_event = next(item for item in added if isinstance(item, JobEvent))
    audit_event = next(item for item in added if isinstance(item, AuditEvent))
    assert job_event.event_type == "action_request_cancel_failed"
    assert audit_event.action == "action_request.cancel_failed"


@pytest.mark.asyncio
async def test_reserve_action_dispatch_sets_submitting_and_blocks_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action_request_id = UUID("abababab-abab-abab-abab-abababababab")
    now = datetime.now(UTC)
    action_request = ActionRequest(
        id=action_request_id,
        action_type="browser_preview",
        status="queued",
        requested_by="operator-1",
        job_id=UUID("cdcdcdcd-cdcd-cdcd-cdcd-cdcdcdcdcdcd"),
        payload_redacted={},
        payload_executable={},
        preview={},
        result={},
        metadata_json={},
        created_at=now,
        updated_at=now,
    )
    captured: dict[str, object] = {}

    class _Scalar:
        def scalar_one_or_none(self) -> ActionRequest:
            return action_request

    class _Session(_FakeActionRequestSession):
        async def execute(self, stmt: object) -> _Scalar:
            captured["for_update"] = getattr(stmt, "_for_update_arg", None) is not None
            return _Scalar()

    @asynccontextmanager
    async def fake_session_scope():
        yield _Session()

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)

    first = await ActionRequestService().reserve_action_dispatch(action_request_id)
    second = await ActionRequestService().reserve_action_dispatch(action_request_id)

    assert captured["for_update"] is True
    assert first.should_dispatch is True
    assert action_request.metadata_json["dispatch_state"] == "submitting"
    assert "dispatch_claimed_at" in action_request.metadata_json
    assert second.should_dispatch is False
    assert second.reason == "Action request dispatch already in progress."


@pytest.mark.asyncio
async def test_record_action_dispatch_event_marks_submitted_and_failed_for_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action_request_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    job_id = UUID("ffffffff-1111-2222-3333-444444444444")
    now = datetime.now(UTC)
    action_request = ActionRequest(
        id=action_request_id,
        action_type="browser_preview",
        status="queued",
        requested_by="operator-1",
        job_id=job_id,
        payload_redacted={},
        payload_executable={},
        preview={},
        result={},
        metadata_json={"dispatch_state": "submitting", "dispatch_claimed_at": "now"},
        created_at=now,
        updated_at=now,
    )
    added: list[object] = []

    class _Session(_FakeActionRequestSession):
        def add(self, obj: object) -> None:
            added.append(obj)

        async def get(self, model: type[object], row_id: UUID) -> object | None:
            if model is ActionRequest and row_id == action_request_id:
                return action_request
            return None

    @asynccontextmanager
    async def fake_session_scope():
        yield _Session()

    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)
    service = ActionRequestService()

    await service.record_action_dispatch_event(
        job_id=job_id,
        action_request_id=action_request_id,
        event_type="action_request_dispatch_submitted",
        status="queued",
        message="submitted",
        metadata_json={"queue": "agent_longrun"},
    )

    assert action_request.metadata_json["dispatch_state"] == "submitted"
    assert action_request.metadata_json["dispatch_queue"] == "agent_longrun"
    assert "dispatch_claimed_at" not in action_request.metadata_json
    assert any(
        isinstance(item, JobEvent) and item.event_type == "action_request_dispatch_submitted"
        for item in added
    )

    await service.record_action_dispatch_event(
        job_id=job_id,
        action_request_id=action_request_id,
        event_type="action_request_dispatch_failed",
        status="queued",
        message="failed",
        metadata_json={"error_type": "RuntimeError"},
    )

    assert action_request.metadata_json["dispatch_state"] == "failed"
    assert action_request.metadata_json["dispatch_last_error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_approval_decision_is_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    approval_id = UUID("33333333-3333-3333-3333-333333333333")
    approval = HumanApproval(
        id=approval_id,
        status="approved",
        action="execute_action_request",
        requested_action="execute_action_request:abc",
        args_redacted={},
        requested_by="operator",
        approver_user_id="1",
        approved_by="1",
        created_at=now,
        updated_at=now,
        decided_at=now,
    )

    class FakeSession:
        async def get(self, model: type[object], obj_id: UUID) -> object | None:
            assert model is HumanApproval
            assert obj_id == approval_id
            return approval

        async def flush(self) -> None:
            raise AssertionError("decided approvals must not be mutated")

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(api_app, "session_scope", fake_session_scope)
    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/approvals/{approval_id}/reject",
            headers=_headers(),
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Approval already decided: approved"
    assert approval.status == "approved"


@pytest.mark.asyncio
async def test_openshell_approval_dispatches_queued_job(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    approval_id = UUID("33333333-3333-3333-3333-333333333333")
    job_id = UUID("44444444-4444-4444-4444-444444444444")
    task_payload = {
        "task_id": "task-1",
        "thread_id": "thread-1",
        "user_id": "1",
        "purpose": "other",
        "instruction": "Run a safe smoke command",
        "input_files": [],
        "allow_network": False,
        "max_runtime_seconds": 300,
        "max_output_bytes": 200000,
        "require_human_approval": True,
        "metadata": {},
    }
    approval = HumanApproval(
        id=approval_id,
        status="pending",
        action="run_sandboxed_code_task",
        requested_action="run_sandboxed_code_task",
        args_redacted={"instruction": "Run a safe smoke command"},
        requested_by="operator",
        job_id=job_id,
        created_at=now,
        updated_at=now,
    )
    job = Job(
        id=job_id,
        job_type="openshell_sandbox",
        status="waiting_approval",
        progress=0,
        metadata_json={
            "task_id": "task-1",
            "thread_id": "thread-1",
            "requested_by": "operator",
            "task_payload_executable": task_payload,
            "task_payload_redacted": {"instruction": "Run a safe smoke command"},
        },
        created_at=now,
        updated_at=now,
    )
    added: list[object] = []
    calls: list[dict[str, object]] = []

    class FakeSession:
        async def get(self, model: type[object], obj_id: UUID) -> object | None:
            if model is HumanApproval:
                assert obj_id == approval_id
                return approval
            if model is Job:
                assert obj_id == job_id
                return job
            raise AssertionError(f"Unexpected model: {model}")

        def add(self, obj: object) -> None:
            added.append(obj)

        async def flush(self) -> None:
            return None

    class FakeTask:
        @staticmethod
        def apply_async(*, args: list[object], queue: str) -> None:
            calls.append({"args": args, "queue": queue})

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(api_app, "session_scope", fake_session_scope)
    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(api_app, "run_openshell_task_async", FakeTask)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/approvals/{approval_id}/approve",
            headers=_headers(),
        )

    assert response.status_code == 200
    assert approval.status == "approved"
    assert job.status == "queued"
    assert any(
        isinstance(item, JobEvent) and item.event_type == "openshell_approval_approved"
        for item in added
    )
    audit_events = [item for item in added if isinstance(item, AuditEvent)]
    assert len(audit_events) == 1
    assert audit_events[0].action == "approval.approved"
    assert audit_events[0].resource_id == str(approval_id)
    assert audit_events[0].actor_id == "1"
    assert calls == [{"args": [task_payload, str(job_id)], "queue": "agent_longrun"}]


@pytest.mark.asyncio
async def test_rejected_approval_closes_linked_job_and_action_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    approval_id = UUID("33333333-3333-3333-3333-333333333333")
    job_id = UUID("44444444-4444-4444-4444-444444444444")
    action_request_id = UUID("55555555-5555-5555-5555-555555555555")
    approval = HumanApproval(
        id=approval_id,
        status="pending",
        action="execute_action_request",
        requested_action=f"execute_action_request:{action_request_id}",
        args_redacted={},
        requested_by="operator",
        job_id=job_id,
        created_at=now,
        updated_at=now,
    )
    job = Job(
        id=job_id,
        job_type="action_request",
        status="waiting_approval",
        progress=0,
        metadata_json={},
        created_at=now,
        updated_at=now,
    )
    action_request = ActionRequest(
        id=action_request_id,
        action_type="computer_organize",
        status="pending_approval",
        requested_by="operator",
        approval_id=approval_id,
        job_id=job_id,
        payload_redacted={},
        payload_executable={},
        preview={},
        result={},
        created_at=now,
        updated_at=now,
    )
    added: list[object] = []

    class FakeResult:
        @staticmethod
        def scalar_one_or_none() -> ActionRequest:
            return action_request

    class FakeSession:
        async def get(self, model: type[object], obj_id: UUID) -> object | None:
            if model is HumanApproval:
                assert obj_id == approval_id
                return approval
            if model is Job:
                assert obj_id == job_id
                return job
            raise AssertionError(f"Unexpected model: {model}")

        async def execute(self, _stmt: object) -> FakeResult:
            return FakeResult()

        def add(self, obj: object) -> None:
            added.append(obj)

        async def flush(self) -> None:
            return None

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(api_app, "session_scope", fake_session_scope)
    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/approvals/{approval_id}/reject",
            headers=_headers(),
        )

    assert response.status_code == 200
    assert approval.status == "rejected"
    assert job.status == "rejected"
    assert job.progress == 100
    assert action_request.status == "rejected"
    assert action_request.error == "Human approval rejected"
    assert any(
        isinstance(item, JobEvent) and item.event_type == "approval_rejected" for item in added
    )


@pytest.mark.asyncio
async def test_approval_self_decision_blocked_by_four_eyes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The user that requested an action cannot approve their own approval."""
    now = datetime.now(UTC)
    approval_id = UUID("66666666-6666-6666-6666-666666666666")
    approval = HumanApproval(
        id=approval_id,
        status="pending",
        action="execute_action_request",
        requested_action="execute_action_request:demo",
        args_redacted={},
        requested_by="1",  # same identity as the JWT used in _headers()
        created_at=now,
        updated_at=now,
    )

    class FakeSession:
        async def get(self, model: type[object], obj_id: UUID) -> object | None:
            assert model is HumanApproval
            assert obj_id == approval_id
            return approval

        async def flush(self) -> None:
            raise AssertionError("self-approval must not mutate state")

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(api_app, "session_scope", fake_session_scope)
    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(api_app.settings, "approval_require_four_eyes", True)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        approve_response = await client.post(
            f"/approvals/{approval_id}/approve",
            headers=_headers(),
        )
        reject_response = await client.post(
            f"/approvals/{approval_id}/reject",
            headers=_headers(),
        )

    assert approve_response.status_code == 403
    assert "four-eyes" in approve_response.json()["detail"].lower()
    assert reject_response.status_code == 403
    assert approval.status == "pending"


@pytest.mark.asyncio
async def test_approval_self_decision_allowed_when_four_eyes_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single-operator dev/test setups can disable the four-eyes contract."""
    now = datetime.now(UTC)
    approval_id = UUID("77777777-7777-7777-7777-777777777777")
    approval = HumanApproval(
        id=approval_id,
        status="pending",
        action="execute_action_request",
        requested_action="execute_action_request:demo",
        args_redacted={},
        requested_by="1",
        created_at=now,
        updated_at=now,
    )

    class FakeSession:
        async def get(self, model: type[object], obj_id: UUID) -> object | None:
            if model is HumanApproval:
                return approval
            return None

        async def execute(self, _stmt: object) -> object:
            class _Result:
                @staticmethod
                def scalar_one_or_none() -> None:
                    return None

            return _Result()

        def add(self, _obj: object) -> None:
            return None

        async def flush(self) -> None:
            return None

    @asynccontextmanager
    async def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(api_app, "session_scope", fake_session_scope)
    monkeypatch.setattr(action_service_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(api_app.settings, "approval_require_four_eyes", False)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/approvals/{approval_id}/approve",
            headers=_headers(),
        )

    assert response.status_code == 200
    assert approval.status == "approved"
    assert approval.approver_user_id == "1"


def _action_request_view(
    *,
    status: str,
    job_id: UUID | None,
    action_type: str = "computer_organize",
) -> ActionRequestView:
    now = datetime.now(UTC)
    return ActionRequestView(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        action_type=action_type,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        requested_by="1",
        approval_id=UUID("33333333-3333-3333-3333-333333333333"),
        job_id=job_id,
        payload_redacted={"root_path": "/tmp/downloads"},
        preview={"status": "ok"},
        result={},
        error=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_browser_request_endpoint_uses_action_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(status="previewed", job_id=None, action_type="browser_navigation")

    class FakeActionRequestService:
        async def create_browser_navigation_request(
            self,
            request: BrowserNavigationRequest,
            *,
            requested_by: str,
        ) -> ActionRequestView:
            assert request.url == "https://example.com"
            assert requested_by == "1"
            return view

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/browser/request",
            json={"url": "https://example.com"},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["action_type"] == "browser_navigation"
    assert response.json()["status"] == "previewed"


@pytest.mark.asyncio
async def test_gmail_request_endpoint_uses_action_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(status="blocked", job_id=None, action_type="gmail_query")

    class FakeActionRequestService:
        async def create_gmail_query_request(
            self,
            request: GmailQueryPreviewRequest,
            *,
            requested_by: str,
        ) -> ActionRequestView:
            assert request.query == "from:client"
            assert requested_by == "1"
            return view

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/gmail/query/request",
            json={"query": "from:client"},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["action_type"] == "gmail_query"
    assert response.json()["status"] == "blocked"


@pytest.mark.asyncio
async def test_godaddy_request_endpoint_uses_action_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(status="previewed", job_id=None, action_type="godaddy_dns_change")

    class FakeActionRequestService:
        async def create_godaddy_dns_change_request(
            self,
            change: GoDaddyDnsRecordChange,
            *,
            requested_by: str,
        ) -> ActionRequestView:
            assert change.domain == "example.com"
            assert requested_by == "1"
            return view

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/godaddy/dns/request",
            json={
                "domain": "example.com",
                "record_type": "A",
                "name": "@",
                "data": "203.0.113.10",
            },
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["action_type"] == "godaddy_dns_change"
    assert response.json()["status"] == "previewed"


@pytest.mark.asyncio
async def test_list_action_requests_forwards_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(status="previewed", job_id=None, action_type="browser_navigation")
    received: dict[str, object] = {}

    class FakeActionRequestService:
        async def list_action_requests(
            self,
            *,
            limit: int = 50,
            action_type: str | None = None,
            status: str | None = None,
        ) -> list[ActionRequestView]:
            received["limit"] = limit
            received["action_type"] = action_type
            received["status"] = status
            return [view]

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/actions/requests",
            params={"limit": 5, "action_type": "browser_navigation", "status": "previewed"},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert received == {
        "limit": 5,
        "action_type": "browser_navigation",
        "status": "previewed",
    }
    assert response.json()[0]["action_type"] == "browser_navigation"


@pytest.mark.asyncio
async def test_cancel_action_request_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(status="cancelled", job_id=None, action_type="browser_navigation")
    received: dict[str, object] = {}

    class FakeActionRequestService:
        async def cancel_action_request(
            self,
            action_request_id: UUID,
            *,
            requested_by: str,
        ) -> ActionRequestView:
            received["action_request_id"] = action_request_id
            received["requested_by"] = requested_by
            return view

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/actions/requests/{view.id}/cancel",
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert received["action_request_id"] == view.id
    assert received["requested_by"] == "1"


@pytest.mark.asyncio
async def test_cancel_action_request_conflict_when_service_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeActionRequestService:
        async def cancel_action_request(
            self,
            action_request_id: UUID,
            *,
            requested_by: str,
        ) -> ActionRequestView:
            from cognitive_os.actions.service import ActionRequestError

            raise ActionRequestError("Cannot cancel a running action request.")

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/requests/11111111-1111-1111-1111-111111111111/cancel",
            headers=_headers(),
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Cannot cancel a running action request."


def test_document_generate_blocks_when_disabled(tmp_path: Path) -> None:
    service = DocumentActionService(
        Settings(
            enable_document_generation=False,
            document_output_root=tmp_path,
        )
    )

    result = service.execute(DocumentGenerateRequest(format="docx", output_filename="report.docx"))

    assert result.status == "blocked"
    assert result.reason == "Document generation is disabled."


def test_document_generate_blocks_path_traversal(tmp_path: Path) -> None:
    service = DocumentActionService(
        Settings(
            enable_document_generation=True,
            document_output_root=tmp_path,
        )
    )

    preview = service.build_preview(
        DocumentGenerateRequest(format="docx", output_filename="../evil.docx")
    )

    assert preview.status == "blocked"
    assert "parent references" in (preview.reason or "")


def test_document_generate_writes_docx(tmp_path: Path) -> None:
    service = DocumentActionService(
        Settings(
            enable_document_generation=True,
            document_output_root=tmp_path,
        )
    )

    result = service.execute(
        DocumentGenerateRequest(
            format="docx",
            output_filename="report.docx",
            title="Hello",
            subtitle="World",
            docx_sections=[
                DocumentSection(heading="Intro", paragraphs=["Line A", "Line B"]),
            ],
        )
    )

    assert result.status == "completed"
    assert result.bytes_written > 0
    assert Path(result.output_path).exists()
    assert Path(result.output_path).suffix == ".docx"


def test_document_generate_writes_xlsx(tmp_path: Path) -> None:
    service = DocumentActionService(
        Settings(
            enable_document_generation=True,
            document_output_root=tmp_path,
        )
    )

    result = service.execute(
        DocumentGenerateRequest(
            format="xlsx",
            output_filename="data.xlsx",
            xlsx_sheets=[
                SpreadsheetSheet(
                    name="Summary",
                    headers=["A", "B"],
                    rows=[[1, 2], [3, 4]],
                )
            ],
        )
    )

    assert result.status == "completed"
    assert Path(result.output_path).exists()
    assert Path(result.output_path).suffix == ".xlsx"


def test_document_generate_writes_pptx(tmp_path: Path) -> None:
    service = DocumentActionService(
        Settings(
            enable_document_generation=True,
            document_output_root=tmp_path,
        )
    )

    result = service.execute(
        DocumentGenerateRequest(
            format="pptx",
            output_filename="deck.pptx",
            title="Quarterly",
            subtitle="Review",
            pptx_slides=[
                SlideContent(title="Slide 1", bullets=["Point A", "Point B"]),
            ],
        )
    )

    assert result.status == "completed"
    assert Path(result.output_path).exists()
    assert Path(result.output_path).suffix == ".pptx"


def test_document_generate_blocks_when_size_exceeds_limit(tmp_path: Path) -> None:
    service = DocumentActionService(
        Settings(
            enable_document_generation=True,
            document_output_root=tmp_path,
            document_max_size_bytes=1,
        )
    )

    result = service.execute(DocumentGenerateRequest(format="docx", output_filename="too_big.docx"))

    assert result.status == "blocked"
    assert "DOCUMENT_MAX_SIZE_BYTES" in (result.reason or "")
    assert not Path(result.output_path).exists()


@pytest.mark.asyncio
async def test_document_request_endpoint_uses_action_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(
        status="pending_approval",
        job_id=UUID("44444444-4444-4444-4444-444444444444"),
        action_type="document_generate",
    )

    class FakeActionRequestService:
        async def create_document_generate_request(
            self,
            request: DocumentGenerateRequest,
            *,
            requested_by: str,
        ) -> ActionRequestView:
            assert request.format == "docx"
            assert request.output_filename == "report.docx"
            assert requested_by == "1"
            return view

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/documents/request",
            json={"format": "docx", "output_filename": "report.docx"},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["action_type"] == "document_generate"
    assert response.json()["status"] == "pending_approval"


def test_browser_preview_blocks_when_disabled(tmp_path: Path) -> None:
    service = BrowserPreviewService(
        Settings(
            _env_file=None,
            enable_browser_automation=False,
            browser_screenshot_dir=tmp_path,
        )
    )

    result = service.execute(BrowserPreviewRequest(url="https://example.com"))

    assert result.status == "blocked"
    assert result.reason == "Browser automation is disabled."


def test_browser_preview_blocks_non_allowlisted_domain(tmp_path: Path) -> None:
    service = BrowserPreviewService(
        Settings(
            _env_file=None,
            enable_browser_automation=True,
            browser_allowed_domains="example.com",
            browser_screenshot_dir=tmp_path,
        )
    )

    result = service.execute(BrowserPreviewRequest(url="https://evil.test"))

    assert result.status == "blocked"
    assert "evil.test" in (result.reason or "")


def test_browser_preview_blocks_when_provider_missing(tmp_path: Path) -> None:
    service = BrowserPreviewService(
        Settings(
            _env_file=None,
            enable_browser_automation=True,
            browser_allowed_domains="example.com",
            browser_screenshot_dir=tmp_path,
        ),
        provider_factory=lambda _s: None,  # type: ignore[arg-type, return-value]
    )

    result = service.execute(BrowserPreviewRequest(url="https://example.com"))

    assert result.status == "blocked"
    assert "Playwright" in (result.reason or "")


def test_browser_preview_executes_with_fake_provider(tmp_path: Path) -> None:
    class FakeProvider:
        def run(
            self,
            *,
            url: str,
            wait_until: str,
            timeout_ms: int,
            capture_screenshot: bool,
            screenshot_path: Path,
        ) -> BrowserPreviewProviderResult:
            del wait_until, timeout_ms
            if capture_screenshot:
                screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
            return BrowserPreviewProviderResult(
                final_url=url,
                title="Example Domain",
                screenshot_bytes=screenshot_path.stat().st_size if capture_screenshot else 0,
            )

    service = BrowserPreviewService(
        Settings(
            enable_browser_automation=True,
            browser_allowed_domains="example.com",
            browser_screenshot_dir=tmp_path,
        ),
        provider_factory=lambda _s: FakeProvider(),
    )

    result = service.execute(BrowserPreviewRequest(url="https://example.com"))

    assert result.status == "completed"
    assert result.title == "Example Domain"
    assert result.final_url == "https://example.com"
    assert result.screenshot_path is not None
    assert Path(result.screenshot_path).exists()
    assert result.bytes_written > 0


def test_browser_preview_blocks_oversized_screenshot(tmp_path: Path) -> None:
    class HugeProvider:
        def run(
            self,
            *,
            url: str,
            wait_until: str,
            timeout_ms: int,
            capture_screenshot: bool,
            screenshot_path: Path,
        ) -> BrowserPreviewProviderResult:
            del wait_until, timeout_ms, capture_screenshot
            screenshot_path.write_bytes(b"X" * 1024)
            return BrowserPreviewProviderResult(
                final_url=url,
                title="big",
                screenshot_bytes=1024,
            )

    service = BrowserPreviewService(
        Settings(
            enable_browser_automation=True,
            browser_allowed_domains="example.com",
            browser_screenshot_dir=tmp_path,
            browser_screenshot_max_bytes=10,
        ),
        provider_factory=lambda _s: HugeProvider(),
    )

    result = service.execute(BrowserPreviewRequest(url="https://example.com"))

    assert result.status == "blocked"
    assert "BROWSER_SCREENSHOT_MAX_BYTES" in (result.reason or "")
    assert result.screenshot_path is None


@pytest.mark.asyncio
async def test_browser_preview_request_endpoint_uses_action_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _action_request_view(
        status="pending_approval",
        job_id=UUID("55555555-5555-5555-5555-555555555555"),
        action_type="browser_preview",
    )

    class FakeActionRequestService:
        async def create_browser_preview_request(
            self,
            request: BrowserPreviewRequest,
            *,
            requested_by: str,
        ) -> ActionRequestView:
            assert request.url == "https://example.com"
            assert requested_by == "1"
            return view

    monkeypatch.setattr(api_app, "ActionRequestService", FakeActionRequestService)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/browser/preview/request",
            json={"url": "https://example.com"},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json()["action_type"] == "browser_preview"
    assert response.json()["status"] == "pending_approval"


# -- Fase 69 P0.2 — dedicated_local auto-approve for reversible actions ------


class _FakeReadyDriveService:
    """Stub Drive service used by auto-approve gating tests.

    The real ``DriveService.status()`` returns ``blocked`` when there is no
    ``token.json`` on disk, so without a stub the auto-approve assertions
    below never reach the gate logic — they short-circuit at the readiness
    check. The stub mirrors the shape used by
    ``test_drive_organize_action_request_service_persists_approval_lifecycle``.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    def ensure_deliverables_folder(
        self,
        request: DriveFolderRequest | None = None,
        *,
        requested_by: str | None = None,
    ) -> DriveFolderPreview:
        del requested_by
        folder_request = request or DriveFolderRequest()
        return DriveFolderPreview(
            status="preview",
            folder_name=folder_request.folder_name or "Cognitive OS Deliverables",
        )

    def organize_files(
        self,
        request: DriveOrganizeRequest,
        *,
        requested_by: str | None = None,
    ) -> DriveOrganizePreview:
        del requested_by
        return DriveOrganizePreview(
            status="preview",
            query=request.query,
            target_folder_name=request.target_folder_name or "Cognitive OS Deliverables",
            dry_run=True,
            operation_count=0,
            operations=[],
        )

    def status(self) -> DriveStatus:
        return DriveStatus(
            status="ready",
            write_enabled=True,
            upload_max_bytes=2048,
            deliverables_folder_name="Cognitive OS Deliverables",
        )


@pytest.mark.asyncio
async def test_drive_folder_request_auto_approves_in_dedicated_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """drive_ensure_folder is on the auto-approve whitelist: with
    auto_approve_reversible_actions=True the service must invoke
    `_auto_approve_and_dispatch` so the operator does not have to click."""
    _install_fake_action_session(monkeypatch)
    monkeypatch.setattr(action_service_module, "DriveService", _FakeReadyDriveService)
    captured: dict[str, object] = {}

    async def _spy(self: object, **kwargs: object) -> object:  # type: ignore[no-redef]
        captured.update(kwargs)
        from cognitive_os.actions.service import ActionRequestView  # noqa: PLC0415

        return ActionRequestView(
            id=kwargs["action_request_id"],  # type: ignore[arg-type]
            action_type="drive_ensure_folder",
            status="queued",
            requested_by="operator-1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            preview={},
            payload_redacted={},
            error=None,
            metadata_json={},
            idempotency_key=None,
            job_id=None,
            approval_id=None,
            workflow_run_id=None,
        )

    monkeypatch.setattr(
        ActionRequestService,
        "_auto_approve_and_dispatch",
        _spy,
        raising=True,
    )

    service = ActionRequestService(
        Settings(
            _env_file=None,
            operator_profile="dedicated_local",
            enable_google_drive=True,
            enable_google_drive_write=True,
            google_client_id="client-id",
            google_client_secret="client-secret",  # pragma: allowlist secret
        )
    )
    assert service._settings.auto_approve_reversible_actions is True

    view = await service.create_drive_folder_request(
        DriveFolderRequest(dry_run=False),
        requested_by="operator-1",
    )

    assert captured, "_auto_approve_and_dispatch must be called for whitelisted reversibles"
    assert view.status == "queued"


@pytest.mark.asyncio
async def test_drive_organize_does_not_auto_approve_in_guarded_dedicated_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guarded dedicated_local preserves the old approval-heavy behavior for
    drive_organize_files."""
    _install_fake_action_session(monkeypatch)
    monkeypatch.setattr(action_service_module, "DriveService", _FakeReadyDriveService)
    called: list[bool] = []

    async def _spy(self: object, **_kwargs: object) -> object:
        called.append(True)
        raise AssertionError("auto-approve must not fire for drive_organize_files")

    monkeypatch.setattr(
        ActionRequestService,
        "_auto_approve_and_dispatch",
        _spy,
        raising=True,
    )

    service = ActionRequestService(
        Settings(
            _env_file=None,
            operator_profile="dedicated_local",
            local_autonomy_mode="guarded",
            enable_google_drive=True,
            enable_google_drive_write=True,
            google_client_id="client-id",
            google_client_secret="client-secret",  # pragma: allowlist secret
        )
    )

    view = await service.create_drive_organize_request(
        DriveOrganizeRequest(),
        requested_by="operator-1",
    )

    assert not called
    assert view.status == "pending_approval"


@pytest.mark.asyncio
async def test_drive_organize_auto_approves_in_full_dedicated_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full dedicated_local is intentionally zero-friction: executable Action
    Plane requests auto-approve through the canonical queue/dispatch path."""
    _install_fake_action_session(monkeypatch)
    monkeypatch.setattr(action_service_module, "DriveService", _FakeReadyDriveService)
    captured: dict[str, object] = {}

    async def _spy(self: object, **kwargs: object) -> object:  # type: ignore[no-redef]
        captured.update(kwargs)
        from cognitive_os.actions.service import ActionRequestView  # noqa: PLC0415

        return ActionRequestView(
            id=kwargs["action_request_id"],  # type: ignore[arg-type]
            action_type="drive_organize_files",
            status="queued",
            requested_by="operator-1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            preview={},
            payload_redacted={},
            error=None,
            metadata_json={},
            idempotency_key=None,
            job_id=None,
            approval_id=None,
            workflow_run_id=None,
        )

    monkeypatch.setattr(
        ActionRequestService,
        "_auto_approve_and_dispatch",
        _spy,
        raising=True,
    )

    service = ActionRequestService(
        Settings(
            _env_file=None,
            operator_profile="dedicated_local",
            enable_google_drive=True,
            enable_google_drive_write=True,
            google_client_id="client-id",
            google_client_secret="client-secret",  # pragma: allowlist secret
        )
    )

    view = await service.create_drive_organize_request(
        DriveOrganizeRequest(),
        requested_by="operator-1",
    )

    assert captured
    assert view.status == "queued"


def test_drive_upload_file_is_auto_approvable_when_reversible_policy_enabled() -> None:
    service = ActionRequestService(
        Settings(
            _env_file=None,
            auto_approve_reversible_actions=True,
        )
    )

    assert service._should_auto_approve_action("drive_upload_file") is True


@pytest.mark.asyncio
async def test_drive_folder_request_does_not_auto_approve_in_strict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even for whitelisted action_types: strict profile keeps approval flow."""
    _install_fake_action_session(monkeypatch)
    monkeypatch.setattr(action_service_module, "DriveService", _FakeReadyDriveService)
    called: list[bool] = []

    async def _spy(self: object, **_kwargs: object) -> object:
        called.append(True)
        raise AssertionError("auto-approve must not fire under OPERATOR_PROFILE=strict")

    monkeypatch.setattr(
        ActionRequestService,
        "_auto_approve_and_dispatch",
        _spy,
        raising=True,
    )

    service = ActionRequestService(
        Settings(
            _env_file=None,
            operator_profile="strict",
            auto_approve_reversible_actions=False,
            enable_google_drive=True,
            enable_google_drive_write=True,
            google_client_id="client-id",
            google_client_secret="client-secret",  # pragma: allowlist secret
        )
    )

    view = await service.create_drive_folder_request(
        DriveFolderRequest(dry_run=False),
        requested_by="operator-1",
    )

    assert not called
    assert view.status == "pending_approval"


# -- Fase 71 P0.A — _auto_approve_and_dispatch end-to-end (no spy) -----------


@pytest.mark.asyncio
async def test_auto_approve_calls_queue_then_reserve_then_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: _auto_approve_and_dispatch must call decide_approval →
    queue_approved_action_request → reserve_action_dispatch → Celery in that
    exact order. Without the queue step the AR stays `pending_approval` and
    `reserve` returns should_dispatch=False (silent no-op). Fase 71 P0.A.
    """
    from cognitive_os.actions import service as service_module  # noqa: PLC0415

    _install_fake_action_session(monkeypatch)
    call_order: list[str] = []

    async def fake_decide(
        approval_id: UUID,
        *,
        status_value: str,
        approver_user_id: str,
        payload_resolver: object | None = None,
        app_settings: object | None = None,
    ) -> object:
        call_order.append("decide_approval")
        return SimpleNamespace(
            approval=SimpleNamespace(requested_action="execute_action_request:xx"),
            openshell_dispatch=None,
            code_build_job_id=None,
        )

    async def fake_queue(self: object, action_request_id: UUID) -> object:
        call_order.append("queue_approved_action_request")
        return SimpleNamespace(id=action_request_id, status="queued")

    async def fake_reserve(self: object, action_request_id: UUID) -> object:
        call_order.append("reserve_action_dispatch")
        ar_view = SimpleNamespace(
            id=action_request_id,
            status="queued",
            job_id=UUID("11111111-1111-1111-1111-111111111111"),
        )
        return SimpleNamespace(
            action_request=ar_view,
            should_dispatch=True,
            reason=None,
        )

    async def fake_record(*args: object, **kwargs: object) -> None:
        return None

    class FakeTaskWithApply:
        @staticmethod
        def apply_async(*args: object, **kwargs: object) -> None:
            call_order.append("celery_apply_async")

    monkeypatch.setattr(service_module, "decide_approval", fake_decide)
    monkeypatch.setattr(ActionRequestService, "queue_approved_action_request", fake_queue)
    monkeypatch.setattr(ActionRequestService, "reserve_action_dispatch", fake_reserve)
    monkeypatch.setattr(ActionRequestService, "record_action_dispatch_event", fake_record)
    monkeypatch.setattr(
        "cognitive_os.workers.tasks.run_action_request_task_async",
        FakeTaskWithApply,
    )

    service = ActionRequestService(Settings(_env_file=None))
    await service._auto_approve_and_dispatch(
        approval_id=UUID("22222222-2222-2222-2222-222222222222"),
        action_request_id=UUID("33333333-3333-3333-3333-333333333333"),
        requested_by="operator-1",
    )

    assert call_order == [
        "decide_approval",
        "queue_approved_action_request",
        "reserve_action_dispatch",
        "celery_apply_async",
    ], (
        "Without queue_approved_action_request between decide and reserve, "
        "the AR stays in pending_approval and dispatch silently no-ops."
    )

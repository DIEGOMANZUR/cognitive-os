from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
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
from cognitive_os.actions.drive import DriveStatus, DriveUploadPreview, DriveUploadRequest
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
from cognitive_os.actions.service import ActionRequestService
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import Settings
from cognitive_os.db.models import ActionRequest, AuditEvent, HumanApproval, Job, JobEvent


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


class _FakeActionRequestSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

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
    service = BrowserActionService(Settings(enable_browser_automation=False))

    result = service.validate_navigation(BrowserNavigationRequest(url="https://example.com"))

    assert result.allowed is False
    assert result.reason == "Browser automation is disabled."


def test_browser_validation_requires_allowlisted_domain() -> None:
    service = BrowserActionService(
        Settings(
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
            enable_computer_actions=True,
            computer_allowed_roots=[str(tmp_path)],
            computer_max_files_per_plan=10,
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
            godaddy_enabled=True,
            godaddy_api_key="key",  # pragma: allowlist secret
            godaddy_api_secret="secret",  # pragma: allowlist secret
            godaddy_base_url="https://api.ote-godaddy.com",
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
async def test_dispatch_action_request_enqueues_worker(
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
            enable_browser_automation=True,
            browser_allowed_domains="example.com",
            browser_screenshot_dir=tmp_path,
        ),
        provider_factory=lambda _s: None,  # type: ignore[arg-type, return-value]
    )

    # Falls through to find_spec; in test env playwright is not installed.
    service_no_factory = BrowserPreviewService(
        Settings(
            enable_browser_automation=True,
            browser_allowed_domains="example.com",
            browser_screenshot_dir=tmp_path,
        )
    )
    result = service_no_factory.execute(BrowserPreviewRequest(url="https://example.com"))

    assert result.status == "blocked"
    assert "Playwright" in (result.reason or "")
    del service  # keep ruff happy


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

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from cognitive_os.actions.drive import (
    DriveError,
    DriveFile,
    DriveFolderRequest,
    DriveOrganizeRequest,
    DriveSearchRequest,
    DriveService,
    DriveUploadRequest,
    FakeDriveProvider,
    GoogleDriveProvider,
    _build_drive_query,
    _parse_file,
)
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import Settings
from cognitive_os.core.google_oauth import GoogleCredentialsLoader


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


def _settings(tmp_path: Path, *, enabled: bool = True, client_id: str = "id.apps") -> Settings:
    return Settings.model_construct(
        enable_google_drive=enabled,
        google_client_id=client_id,
        google_token_dir=tmp_path,
        google_drive_scopes=["https://www.googleapis.com/auth/drive"],
        google_drive_deliverables_folder_name="Cognitive OS Deliverables",
        http_timeout_seconds=5.0,
    )


def _loader(tmp_path: Path, *, token: str = "tok") -> GoogleCredentialsLoader:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    creds = SimpleNamespace(valid=True, expired=False, refresh_token=None, token=token)
    return GoogleCredentialsLoader(token_path=token_path, credentials_loader=lambda _p: creds)


def _file(file_id: str, name: str) -> DriveFile:
    return DriveFile(file_id=file_id, name=name, mime_type="application/pdf")


def test_status_disabled_blocked_ready(tmp_path: Path) -> None:
    assert DriveService(app_settings=_settings(tmp_path, enabled=False)).status().status == (
        "disabled"
    )
    blocked = DriveService(app_settings=_settings(tmp_path, client_id="CHANGEME"))
    assert blocked.status().status == "blocked"
    assert DriveService(app_settings=_settings(tmp_path)).status().status == "blocked"
    ready = DriveService(provider=FakeDriveProvider(), app_settings=_settings(tmp_path))
    assert ready.status().status == "ready"
    assert ready.status().deliverables_folder_name == "Cognitive OS Deliverables"


def test_list_files_blocked_when_disabled(tmp_path: Path) -> None:
    service = DriveService(app_settings=_settings(tmp_path, enabled=False))
    with pytest.raises(DriveError, match="ENABLE_GOOGLE_DRIVE"):
        service.list_files(DriveSearchRequest())


def test_list_and_get_file_use_provider(tmp_path: Path) -> None:
    files = [_file("f1", "informe.pdf"), _file("f2", "notas.pdf")]
    provider = FakeDriveProvider(files=files)
    service = DriveService(provider=provider, app_settings=_settings(tmp_path))
    assert service.list_files(DriveSearchRequest(query="informe")) == [files[0]]
    assert provider.calls == ["list:name:user:informe"]
    assert service.get_file("f2").name == "notas.pdf"
    with pytest.raises(DriveError, match="not found"):
        service.get_file("missing")
    with pytest.raises(DriveError, match="must not be empty"):
        service.get_file("   ")


def test_parse_file_handles_size_and_owner() -> None:
    parsed = _parse_file(
        {
            "id": "f9",
            "name": "doc.txt",
            "mimeType": "text/plain",
            "size": "2048",
            "owners": [{"displayName": "Diego"}],
            "parents": ["root"],
        }
    )
    assert parsed is not None
    assert parsed.size_bytes == 2048
    assert parsed.owner == "Diego"
    assert parsed.parent_ids == ["root"]
    assert _parse_file({"name": "no id"}) is None


def test_drive_query_builder_supports_full_text_all_and_filters() -> None:
    assert _build_drive_query(DriveSearchRequest(query="contrato", search_mode="name")) == (
        "trashed = false and name contains 'contrato'"
    )
    assert _build_drive_query(
        DriveSearchRequest(
            query="important",
            search_mode="full_text",
            include_folders=False,
            mime_type="application/pdf",
        )
    ) == (
        "trashed = false and fullText contains 'important' and "
        "mimeType != 'application/vnd.google-apps.folder' and mimeType = 'application/pdf'"
    )
    assert _build_drive_query(
        DriveSearchRequest(query="quinn's paper\\essay", search_mode="all")
    ) == (
        "trashed = false and (name contains 'quinn\\'s paper\\\\essay' or "
        "fullText contains 'quinn\\'s paper\\\\essay')"
    )


def test_google_provider_lists_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "files": [
            {
                "id": "drv-1",
                "name": "contrato.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "2026-05-01T12:00:00Z",
                "size": "5120",
                "webViewLink": "https://drive.google.com/drv-1",
            }
        ]
    }

    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        params = kwargs["params"]
        assert params["q"] == (
            "trashed = false and (name contains 'contrato' or fullText contains 'contrato')"
        )
        assert params["corpora"] == "allDrives"
        assert params["includeItemsFromAllDrives"] == "true"
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    provider = GoogleDriveProvider(_settings(tmp_path), credentials_loader=_loader(tmp_path))
    files = provider.list_files(
        query="contrato",
        max_results=10,
        search_mode="all",
        corpus="all_drives",
    )
    assert len(files) == 1
    assert files[0].file_id == "drv-1"
    assert files[0].size_bytes == 5120


def test_google_provider_get_file_raises_on_bad_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    provider = GoogleDriveProvider(_settings(tmp_path), credentials_loader=_loader(tmp_path))
    with pytest.raises(DriveError, match="not found or has an unexpected shape"):
        provider.get_file("whatever")


def test_google_provider_moves_file_between_folders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "id": "drv-1",
        "name": "contrato.pdf",
        "mimeType": "application/pdf",
        "parents": ["new-folder"],
    }

    def fake_patch(url: str, **kwargs: object) -> httpx.Response:
        params = kwargs["params"]
        assert url.endswith("/files/drv-1")
        assert params["addParents"] == "new-folder"
        assert params["removeParents"] == "old-folder"
        assert params["supportsAllDrives"] == "true"
        return httpx.Response(200, json=payload, request=httpx.Request("PATCH", url))

    monkeypatch.setattr(httpx, "patch", fake_patch)
    provider = GoogleDriveProvider(_settings(tmp_path), credentials_loader=_loader(tmp_path))
    moved = provider.move_file(
        file_id="drv-1",
        destination_folder_id="new-folder",
        remove_parent_ids=["old-folder"],
    )
    assert moved.parent_ids == ["new-folder"]


@pytest.mark.asyncio
async def test_drive_endpoints_require_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        status_resp = await client.get("/actions/drive/status")
        files_resp = await client.post("/actions/drive/files", json={})
        get_resp = await client.get("/actions/drive/files/abc")
        upload_resp = await client.post(
            "/actions/drive/files/upload",
            json={"local_path": "/tmp/x"},
        )
        folder_resp = await client.post(
            "/actions/drive/folders/ensure",
            json={},
        )
        folder_request_resp = await client.post(
            "/actions/drive/folders/ensure/request",
            json={},
        )
        organize_preview_resp = await client.post(
            "/actions/drive/organize/preview",
            json={},
        )
        organize_request_resp = await client.post(
            "/actions/drive/organize/request",
            json={},
        )
        upload_request_resp = await client.post(
            "/actions/drive/files/upload/request",
            json={"local_path": "/tmp/x"},
        )
    assert status_resp.status_code == 401
    assert files_resp.status_code == 401
    assert get_resp.status_code == 401
    assert upload_resp.status_code == 401
    assert folder_resp.status_code == 401
    assert folder_request_resp.status_code == 401
    assert organize_preview_resp.status_code == 401
    assert organize_request_resp.status_code == 401
    assert upload_request_resp.status_code == 401


@pytest.mark.asyncio
async def test_drive_direct_upload_rejects_real_write() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/drive/files/upload",
            json={"local_path": "/tmp/result.md", "dry_run": False},
            headers=_headers(),
        )

    assert response.status_code == 409
    assert "/actions/drive/files/upload/request" in response.json()["detail"]


@pytest.mark.asyncio
async def test_drive_direct_folder_ensure_rejects_real_write() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/drive/folders/ensure",
            json={"dry_run": False},
            headers=_headers(),
        )

    assert response.status_code == 409
    assert "Direct Drive folder writes are disabled" in response.json()["detail"]


@pytest.mark.asyncio
async def test_drive_direct_organize_rejects_real_write() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/drive/organize/preview",
            json={"query": "factura", "dry_run": False},
            headers=_headers(),
        )

    assert response.status_code == 409
    assert "/actions/drive/organize/request" in response.json()["detail"]


def _upload_settings(
    tmp_path: Path,
    *,
    enabled: bool = True,
    write_enabled: bool = False,
    upload_cap: int = 1_000_000,
) -> Settings:
    storage_dir = tmp_path / "storage"
    return Settings.model_construct(
        enable_google_drive=enabled,
        enable_google_drive_write=write_enabled,
        google_client_id="id.apps",
        google_token_dir=tmp_path,
        google_drive_scopes=["https://www.googleapis.com/auth/drive"],
        computer_allowed_roots=[str(tmp_path)],
        document_output_root=tmp_path / "documents",
        local_storage_dir=str(storage_dir),
        openshell_allowed_output_dir=tmp_path / "sandbox_outputs",
        google_drive_upload_max_bytes=upload_cap,
        google_drive_deliverables_folder_name="Cognitive OS Deliverables",
        http_timeout_seconds=5.0,
    )


def _make_source(tmp_path: Path, *, content: bytes = b"hello world") -> Path:
    src = tmp_path / "doc.txt"
    src.write_bytes(content)
    return src


def test_upload_file_dry_run_returns_preview(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    provider = FakeDriveProvider()
    service = DriveService(provider=provider, app_settings=_upload_settings(tmp_path))
    result = service.upload_file(
        DriveUploadRequest(
            local_path=str(src),
            drive_name="custom.txt",
            mime_type="text/plain",
            dry_run=True,
        )
    )
    assert result.status == "preview"
    assert result.drive_name == "custom.txt"
    assert result.folder_name == "Cognitive OS Deliverables"
    assert result.size_bytes == len(b"hello world")
    assert provider.upload_calls == []


def test_ensure_deliverables_folder_dry_run_and_write_gate(tmp_path: Path) -> None:
    provider = FakeDriveProvider()
    service = DriveService(provider=provider, app_settings=_upload_settings(tmp_path))
    preview = service.ensure_deliverables_folder(DriveFolderRequest(dry_run=True))
    assert preview.status == "preview"
    assert provider.calls == []

    blocked = service.ensure_deliverables_folder(DriveFolderRequest(dry_run=False))
    assert blocked.status == "blocked"
    assert "ENABLE_GOOGLE_DRIVE_WRITE" in (blocked.reason or "")
    assert provider.calls == []


def test_ensure_deliverables_folder_creates_when_write_enabled(tmp_path: Path) -> None:
    provider = FakeDriveProvider()
    service = DriveService(
        provider=provider,
        app_settings=_upload_settings(tmp_path, write_enabled=True),
    )
    result = service.ensure_deliverables_folder(DriveFolderRequest(dry_run=False))
    assert result.status == "ready"
    assert result.folder is not None
    assert result.folder.is_folder is True
    assert provider.calls == ["ensure_folder:Cognitive OS Deliverables"]


def test_upload_file_blocked_when_write_disabled(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    provider = FakeDriveProvider()
    service = DriveService(
        provider=provider,
        app_settings=_upload_settings(tmp_path, write_enabled=False),
    )
    result = service.upload_file(
        DriveUploadRequest(local_path=str(src), dry_run=False),
    )
    assert result.status == "blocked"
    assert "ENABLE_GOOGLE_DRIVE_WRITE" in (result.reason or "")
    assert provider.upload_calls == []


def test_upload_file_blocked_when_size_exceeds_cap(tmp_path: Path) -> None:
    src = _make_source(tmp_path, content=b"x" * 200)
    provider = FakeDriveProvider()
    service = DriveService(
        provider=provider,
        app_settings=_upload_settings(tmp_path, write_enabled=True, upload_cap=100),
    )
    result = service.upload_file(
        DriveUploadRequest(local_path=str(src), dry_run=False),
    )
    assert result.status == "blocked"
    assert "GOOGLE_DRIVE_UPLOAD_MAX_BYTES" in (result.reason or "")
    assert provider.upload_calls == []


def test_upload_file_rejects_path_outside_allowed_roots(tmp_path: Path) -> None:
    # Build settings whose only allowed root is tmp_path/foo, then point at tmp_path/bar
    allowed = tmp_path / "foo"
    allowed.mkdir()
    other = tmp_path / "bar"
    other.mkdir()
    outside_file = other / "secret.txt"
    outside_file.write_bytes(b"x")
    cfg = Settings.model_construct(
        enable_google_drive=True,
        enable_google_drive_write=True,
        google_client_id="id.apps",
        google_token_dir=tmp_path,
        google_drive_scopes=["https://www.googleapis.com/auth/drive"],
        computer_allowed_roots=[str(allowed)],
        document_output_root=tmp_path / "documents",
        local_storage_dir=str(tmp_path / "storage"),
        openshell_allowed_output_dir=tmp_path / "sandbox_outputs",
        google_drive_upload_max_bytes=1_000_000,
        google_drive_deliverables_folder_name="Cognitive OS Deliverables",
        http_timeout_seconds=5.0,
    )
    service = DriveService(provider=FakeDriveProvider(), app_settings=cfg)
    with pytest.raises(DriveError, match="outside configured Drive upload roots") as exc_info:
        service.upload_file(
            DriveUploadRequest(local_path=str(outside_file), dry_run=False),
        )
    assert str(tmp_path) not in str(exc_info.value)


def test_upload_file_allows_document_output_root_without_computer_roots(tmp_path: Path) -> None:
    document_root = tmp_path / "documents"
    document_root.mkdir()
    src = document_root / "report.md"
    src.write_text("ok", encoding="utf-8")
    cfg = Settings.model_construct(
        enable_google_drive=True,
        enable_google_drive_write=False,
        google_client_id="id.apps",
        google_token_dir=tmp_path,
        google_drive_scopes=["https://www.googleapis.com/auth/drive"],
        computer_allowed_roots=[],
        document_output_root=document_root,
        local_storage_dir=str(tmp_path / "storage"),
        openshell_allowed_output_dir=tmp_path / "sandbox_outputs",
        google_drive_upload_max_bytes=1_000_000,
        google_drive_deliverables_folder_name="Cognitive OS Deliverables",
        http_timeout_seconds=5.0,
    )
    service = DriveService(provider=FakeDriveProvider(), app_settings=cfg)
    result = service.upload_file(DriveUploadRequest(local_path=str(src), dry_run=True))
    assert result.status == "preview"


def test_upload_file_allows_workspace_exports_but_rejects_oauth_storage(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    workspace_file = storage_root / "workspaces" / "task-1" / "answer.md"
    workspace_file.parent.mkdir(parents=True)
    workspace_file.write_text("ok", encoding="utf-8")
    oauth_file = storage_root / "oauth" / "token.json"
    oauth_file.parent.mkdir(parents=True)
    oauth_file.write_text("{}", encoding="utf-8")
    cfg = Settings.model_construct(
        enable_google_drive=True,
        enable_google_drive_write=False,
        google_client_id="id.apps",
        google_token_dir=tmp_path,
        google_drive_scopes=["https://www.googleapis.com/auth/drive"],
        computer_allowed_roots=[],
        document_output_root=tmp_path / "documents",
        local_storage_dir=str(storage_root),
        openshell_allowed_output_dir=tmp_path / "sandbox_outputs",
        google_drive_upload_max_bytes=1_000_000,
        google_drive_deliverables_folder_name="Cognitive OS Deliverables",
        http_timeout_seconds=5.0,
    )
    service = DriveService(provider=FakeDriveProvider(), app_settings=cfg)
    assert (
        service.upload_file(DriveUploadRequest(local_path=str(workspace_file))).status == "preview"
    )
    with pytest.raises(DriveError, match="outside configured Drive upload roots") as exc_info:
        service.upload_file(DriveUploadRequest(local_path=str(oauth_file)))
    assert str(tmp_path) not in str(exc_info.value)


def test_upload_file_rejects_traversal(tmp_path: Path) -> None:
    service = DriveService(
        provider=FakeDriveProvider(),
        app_settings=_upload_settings(tmp_path, write_enabled=True),
    )
    with pytest.raises(DriveError, match="'..'"):
        service.upload_file(
            DriveUploadRequest(local_path="/tmp/../etc/passwd", dry_run=False),
        )


def test_upload_file_rejects_nonexistent_path(tmp_path: Path) -> None:
    service = DriveService(
        provider=FakeDriveProvider(),
        app_settings=_upload_settings(tmp_path, write_enabled=True),
    )
    with pytest.raises(DriveError, match="does not exist") as exc_info:
        service.upload_file(
            DriveUploadRequest(local_path=str(tmp_path / "missing"), dry_run=False),
        )
    assert str(tmp_path) not in str(exc_info.value)


def test_upload_file_executes_when_all_gates_pass(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    provider = FakeDriveProvider(
        uploaded_file=DriveFile(
            file_id="drv-real",
            name="doc.txt",
            mime_type="text/plain",
            size_bytes=11,
        )
    )
    service = DriveService(
        provider=provider,
        app_settings=_upload_settings(tmp_path, write_enabled=True),
    )
    result = service.upload_file(
        DriveUploadRequest(local_path=str(src), dry_run=False),
    )
    assert result.status == "uploaded"
    assert result.file is not None
    assert result.file.file_id == "drv-real"
    assert provider.calls == ["ensure_folder:Cognitive OS Deliverables"]
    assert provider.upload_calls == [
        {
            "source_path": str(src),
            "drive_name": "doc.txt",
            "mime_type": "application/octet-stream",
            "folder_id": "fake-folder-1",
        }
    ]


def test_organize_files_dry_run_lists_candidates_without_writes(tmp_path: Path) -> None:
    files = [
        DriveFile(
            file_id="file-1",
            name="factura-enero.pdf",
            mime_type="application/pdf",
            parent_ids=["old"],
        )
    ]
    provider = FakeDriveProvider(files=files)
    service = DriveService(provider=provider, app_settings=_upload_settings(tmp_path))
    preview = service.organize_files(
        DriveOrganizeRequest(query="factura", target_folder_name="Finanzas", dry_run=True)
    )
    assert preview.status == "preview"
    assert preview.operation_count == 1
    assert preview.operations[0].file.file_id == "file-1"
    assert provider.calls == ["list:all:user:factura"]
    assert provider.move_calls == []


def test_organize_files_blocks_real_move_when_write_disabled(tmp_path: Path) -> None:
    provider = FakeDriveProvider(files=[_file("file-1", "factura.pdf")])
    service = DriveService(provider=provider, app_settings=_upload_settings(tmp_path))
    result = service.organize_files(
        DriveOrganizeRequest(query="factura", target_folder_name="Finanzas", dry_run=False)
    )
    assert result.status == "blocked"
    assert "ENABLE_GOOGLE_DRIVE_WRITE" in (result.reason or "")
    assert provider.move_calls == []


def test_organize_files_moves_candidates_when_write_enabled(tmp_path: Path) -> None:
    provider = FakeDriveProvider(
        files=[
            DriveFile(
                file_id="file-1",
                name="factura.pdf",
                mime_type="application/pdf",
                parent_ids=["old-folder"],
            )
        ]
    )
    service = DriveService(
        provider=provider,
        app_settings=_upload_settings(tmp_path, write_enabled=True),
    )
    result = service.organize_files(
        DriveOrganizeRequest(query="factura", target_folder_name="Finanzas", dry_run=False)
    )
    assert result.status == "completed"
    assert result.operation_count == 1
    assert result.operations[0].status == "moved"
    assert result.operations[0].removed_parent_ids == ["old-folder"]
    assert provider.calls == ["list:all:user:factura", "ensure_folder:Finanzas"]
    assert provider.move_calls == [
        {
            "file_id": "file-1",
            "destination_folder_id": "fake-folder-2",
            "remove_parent_ids": ["old-folder"],
        }
    ]


def test_organize_files_execute_uses_frozen_ids_not_a_research(tmp_path: Path) -> None:
    """Regression (GPT-5.5 P1): the execute path must move EXACTLY the files
    the operator approved at preview time, never a fresh search. Otherwise the
    human-approval guarantee is meaningless (approve set A, move set B)."""
    provider = FakeDriveProvider(
        files=[
            DriveFile(file_id="file-1", name="factura.pdf", mime_type="application/pdf"),
            DriveFile(file_id="file-2", name="factura2.pdf", mime_type="application/pdf"),
            # file-3 matches the same query but appeared AFTER approval. A
            # re-search would wrongly sweep it; the frozen list must not.
            DriveFile(file_id="file-3", name="factura3.pdf", mime_type="application/pdf"),
        ]
    )
    service = DriveService(
        provider=provider,
        app_settings=_upload_settings(tmp_path, write_enabled=True),
    )
    result = service.organize_files(
        DriveOrganizeRequest(
            query="factura",
            target_folder_name="Finanzas",
            dry_run=False,
            file_ids=["file-1", "file-2"],  # frozen at preview time
        )
    )
    assert result.status == "completed"
    moved_ids = sorted(c["file_id"] for c in provider.move_calls)
    assert moved_ids == ["file-1", "file-2"]  # NOT file-3
    assert "file-3" not in moved_ids
    # No list/search call was issued on the execute path.
    assert not any(c.startswith("list:") for c in provider.calls)


def test_organize_files_execute_skips_deleted_frozen_file(tmp_path: Path) -> None:
    """A file deleted between approve and execute is skipped, never substituted."""
    provider = FakeDriveProvider(
        files=[DriveFile(file_id="file-1", name="factura.pdf", mime_type="application/pdf")]
    )
    service = DriveService(
        provider=provider,
        app_settings=_upload_settings(tmp_path, write_enabled=True),
    )
    result = service.organize_files(
        DriveOrganizeRequest(
            query="factura",
            target_folder_name="Finanzas",
            dry_run=False,
            file_ids=["file-1", "file-gone"],  # file-gone no longer exists
        )
    )
    assert result.status == "completed"
    assert sorted(c["file_id"] for c in provider.move_calls) == ["file-1"]


def test_organize_files_skips_files_already_in_target(tmp_path: Path) -> None:
    provider = FakeDriveProvider(
        files=[
            DriveFile(
                file_id="folder-1",
                name="Finanzas",
                mime_type="application/vnd.google-apps.folder",
                is_folder=True,
            ),
            DriveFile(
                file_id="file-1",
                name="factura.pdf",
                mime_type="application/pdf",
                parent_ids=["folder-1"],
            ),
        ]
    )
    service = DriveService(
        provider=provider,
        app_settings=_upload_settings(tmp_path, write_enabled=True),
    )
    result = service.organize_files(
        DriveOrganizeRequest(query="factura", target_folder_name="Finanzas", dry_run=False)
    )
    assert result.status == "completed"
    assert result.operations[0].status == "skipped"
    assert provider.move_calls == []

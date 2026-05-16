"""Google Drive for the personal assistant.

Default: read-only — list and inspect Drive files. Uploads are an opt-in WRITE
capability gated by two independent flags (`ENABLE_GOOGLE_DRIVE_WRITE` server
setting AND per-call `dry_run=false`) plus a path allow-list rooted in
`COMPUTER_ALLOWED_ROOTS`. Every attempt is audited. Tests inject
`FakeDriveProvider`, so the suite never touches Google.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx
import structlog
from pydantic import BaseModel, Field

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.google_oauth import (
    GoogleCredentialsLoader,
    GoogleOAuthError,
    redact_google_error,
)
from cognitive_os.core.resilience import retry_transient_http
from cognitive_os.tools.policy import ToolAuditRecord, ToolRiskLevel, record_audit_event

_log = structlog.get_logger(__name__)

_DRIVE_API = "https://www.googleapis.com/drive/v3"
_DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
_FILE_FIELDS = "id,name,mimeType,modifiedTime,size,webViewLink,owners(displayName)"
_FOLDER_MIME = "application/vnd.google-apps.folder"
_MAX_RESULTS = 100


class DriveError(RuntimeError):
    """Raised when a Drive query cannot be completed."""


class DriveFile(BaseModel):
    file_id: str
    name: str
    mime_type: str
    modified_time: str | None = None
    size_bytes: int | None = None
    web_view_link: str | None = None
    owner: str | None = None
    is_folder: bool = False


class DriveStatus(BaseModel):
    status: Literal["disabled", "blocked", "ready"]
    reason: str | None = None
    write_enabled: bool = False
    upload_max_bytes: int = 0
    deliverables_folder_name: str


class DriveSearchRequest(BaseModel):
    query: str = Field(default="", max_length=2000)
    max_results: int = Field(default=20, ge=1, le=_MAX_RESULTS)


class DriveUploadRequest(BaseModel):
    local_path: str = Field(min_length=1, max_length=4096)
    drive_name: str | None = Field(default=None, max_length=400)
    mime_type: str | None = Field(default=None, max_length=200)
    folder_id: str | None = Field(default=None, min_length=1, max_length=256)
    folder_name: str | None = Field(default=None, min_length=1, max_length=400)
    use_deliverables_folder: bool = True
    dry_run: bool = True


class DriveFolderRequest(BaseModel):
    folder_name: str | None = Field(default=None, min_length=1, max_length=400)
    dry_run: bool = True


class DriveFolderPreview(BaseModel):
    status: Literal["preview", "blocked", "ready", "created"]
    reason: str | None = None
    folder_name: str
    folder: DriveFile | None = None


class DriveUploadPreview(BaseModel):
    status: Literal["preview", "blocked", "uploaded"]
    reason: str | None = None
    drive_name: str
    mime_type: str
    size_bytes: int = 0
    folder_id: str | None = None
    folder_name: str | None = None
    file: DriveFile | None = None


class DriveProvider(Protocol):
    def list_files(self, *, query: str, max_results: int) -> list[DriveFile]: ...

    def get_file(self, file_id: str) -> DriveFile: ...

    def upload_file(
        self,
        *,
        source_path: Path,
        drive_name: str,
        mime_type: str,
        folder_id: str | None,
    ) -> DriveFile: ...

    def ensure_folder(self, *, folder_name: str) -> DriveFile: ...


class FakeDriveProvider:
    def __init__(
        self,
        *,
        files: list[DriveFile] | None = None,
        raises: bool = False,
        uploaded_file: DriveFile | None = None,
        raise_on_upload: bool = False,
    ) -> None:
        self._files = files or []
        self._raises = raises
        self._uploaded_file = uploaded_file
        self._raise_on_upload = raise_on_upload
        self.calls: list[str] = []
        self.upload_calls: list[dict[str, Any]] = []

    def list_files(self, *, query: str, max_results: int) -> list[DriveFile]:
        self.calls.append(f"list:{query}")
        if self._raises:
            raise DriveError("fake drive failure")
        return list(self._files[:max_results])

    def get_file(self, file_id: str) -> DriveFile:
        self.calls.append(f"get:{file_id}")
        if self._raises:
            raise DriveError("fake drive failure")
        for item in self._files:
            if item.file_id == file_id:
                return item
        raise DriveError(f"File {file_id!r} not found.")

    def upload_file(
        self,
        *,
        source_path: Path,
        drive_name: str,
        mime_type: str,
        folder_id: str | None,
    ) -> DriveFile:
        self.upload_calls.append(
            {
                "source_path": str(source_path),
                "drive_name": drive_name,
                "mime_type": mime_type,
                "folder_id": folder_id,
            }
        )
        if self._raise_on_upload:
            raise DriveError("fake upload failure")
        if self._uploaded_file is not None:
            return self._uploaded_file
        size = source_path.stat().st_size if source_path.exists() else 0
        return DriveFile(
            file_id="fake-upload",
            name=drive_name,
            mime_type=mime_type,
            size_bytes=size,
        )

    def ensure_folder(self, *, folder_name: str) -> DriveFile:
        self.calls.append(f"ensure_folder:{folder_name}")
        if self._raises:
            raise DriveError("fake drive failure")
        for item in self._files:
            if item.name == folder_name and item.is_folder:
                return item
        folder = DriveFile(
            file_id=f"fake-folder-{len(self._files) + 1}",
            name=folder_name,
            mime_type=_FOLDER_MIME,
            is_folder=True,
        )
        self._files.append(folder)
        return folder


def _parse_file(raw: dict[str, Any]) -> DriveFile | None:
    file_id = str(raw.get("id") or "")
    if not file_id:
        return None
    size_raw = raw.get("size")
    size_bytes = (
        int(size_raw) if isinstance(size_raw, (str, int)) and str(size_raw).isdigit() else None
    )
    owners = raw.get("owners") or []
    owner = None
    if isinstance(owners, list) and owners and isinstance(owners[0], dict):
        owner = str(owners[0].get("displayName") or "") or None
    return DriveFile(
        file_id=file_id,
        name=str(raw.get("name") or "(sin nombre)"),
        mime_type=str(raw.get("mimeType") or "application/octet-stream"),
        modified_time=str(raw["modifiedTime"]) if raw.get("modifiedTime") else None,
        size_bytes=size_bytes,
        web_view_link=str(raw["webViewLink"]) if raw.get("webViewLink") else None,
        owner=owner,
        is_folder=str(raw.get("mimeType") or "") == _FOLDER_MIME,
    )


def _escape_drive_query(value: str) -> str:
    return value.replace("'", "\\'")


class GoogleDriveProvider:
    """Real provider: Google Drive API v3 over an authorized-user token."""

    def __init__(
        self,
        app_settings: Settings = settings,
        credentials_loader: GoogleCredentialsLoader | None = None,
    ) -> None:
        self._settings = app_settings
        self._loader = credentials_loader or GoogleCredentialsLoader(
            token_path=app_settings.google_token_dir.expanduser() / "token.json"
        )

    def _token(self) -> str:
        try:
            return self._loader.access_token()
        except GoogleOAuthError as exc:
            raise DriveError(str(exc)) from exc

    def list_files(self, *, query: str, max_results: int) -> list[DriveFile]:
        params: dict[str, str] = {
            "pageSize": str(max_results),
            "fields": f"files({_FILE_FIELDS})",
            "orderBy": "modifiedTime desc",
        }
        if query.strip():
            # Escape single quotes to keep the Drive query grammar well-formed.
            safe = query.strip().replace("'", "\\'")
            params["q"] = f"name contains '{safe}' and trashed = false"
        else:
            params["q"] = "trashed = false"
        try:
            response = retry_transient_http(
                lambda: httpx.get(
                    f"{_DRIVE_API}/files",
                    params=params,
                    headers={"Authorization": f"Bearer {self._token()}"},
                    timeout=self._settings.http_timeout_seconds,
                )
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise DriveError(f"Drive request failed: {redact_google_error(str(exc))}") from exc
        except ValueError as exc:
            raise DriveError("Drive API returned invalid JSON.") from exc
        files: list[DriveFile] = []
        for raw in payload.get("files") or []:
            if isinstance(raw, dict):
                parsed = _parse_file(raw)
                if parsed is not None:
                    files.append(parsed)
        return files

    def get_file(self, file_id: str) -> DriveFile:
        try:
            response = retry_transient_http(
                lambda: httpx.get(
                    f"{_DRIVE_API}/files/{file_id}",
                    params={"fields": _FILE_FIELDS},
                    headers={"Authorization": f"Bearer {self._token()}"},
                    timeout=self._settings.http_timeout_seconds,
                )
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise DriveError(f"Drive request failed: {redact_google_error(str(exc))}") from exc
        except ValueError as exc:
            raise DriveError("Drive API returned invalid JSON.") from exc
        parsed = _parse_file(payload) if isinstance(payload, dict) else None
        if parsed is None:
            raise DriveError(f"File {file_id!r} not found or has an unexpected shape.")
        return parsed

    def upload_file(
        self,
        *,
        source_path: Path,
        drive_name: str,
        mime_type: str,
        folder_id: str | None,
    ) -> DriveFile:
        try:
            data = source_path.read_bytes()
        except OSError as exc:
            raise DriveError(f"Could not read local file: {exc}") from exc
        boundary = "cognitive_os_drive_boundary"
        metadata_obj: dict[str, Any] = {"name": drive_name}
        if folder_id:
            metadata_obj["parents"] = [folder_id]
        metadata = json.dumps(metadata_obj, ensure_ascii=False).encode()
        body = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
            + metadata
            + f"\r\n--{boundary}\r\n".encode()
            + f"Content-Type: {mime_type}\r\n\r\n".encode()
            + data
            + f"\r\n--{boundary}--".encode()
        )
        headers = {
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        }
        try:
            response = retry_transient_http(
                lambda: httpx.post(
                    f"{_DRIVE_UPLOAD}?uploadType=multipart&fields={_FILE_FIELDS}",
                    content=body,
                    headers=headers,
                    timeout=self._settings.http_timeout_seconds,
                )
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise DriveError(f"Drive upload failed: {redact_google_error(str(exc))}") from exc
        except ValueError as exc:
            raise DriveError("Drive upload returned invalid JSON.") from exc
        parsed = _parse_file(payload) if isinstance(payload, dict) else None
        if parsed is None:
            raise DriveError("Drive upload returned an unexpected payload shape.")
        return parsed

    def ensure_folder(self, *, folder_name: str) -> DriveFile:
        safe = _escape_drive_query(folder_name)
        params: dict[str, str] = {
            "q": f"mimeType = '{_FOLDER_MIME}' and name = '{safe}' and trashed = false",
            "pageSize": "1",
            "fields": f"files({_FILE_FIELDS})",
        }
        try:
            response = retry_transient_http(
                lambda: httpx.get(
                    f"{_DRIVE_API}/files",
                    params=params,
                    headers={"Authorization": f"Bearer {self._token()}"},
                    timeout=self._settings.http_timeout_seconds,
                )
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise DriveError(
                f"Drive folder lookup failed: {redact_google_error(str(exc))}"
            ) from exc
        except ValueError as exc:
            raise DriveError("Drive folder lookup returned invalid JSON.") from exc
        for raw in payload.get("files") or []:
            if isinstance(raw, dict):
                parsed = _parse_file(raw)
                if parsed is not None:
                    return parsed

        metadata = {"name": folder_name, "mimeType": _FOLDER_MIME}
        try:
            response = retry_transient_http(
                lambda: httpx.post(
                    f"{_DRIVE_API}/files",
                    json=metadata,
                    params={"fields": _FILE_FIELDS},
                    headers={"Authorization": f"Bearer {self._token()}"},
                    timeout=self._settings.http_timeout_seconds,
                )
            )
            response.raise_for_status()
            created = response.json()
        except httpx.HTTPError as exc:
            raise DriveError(
                f"Drive folder create failed: {redact_google_error(str(exc))}"
            ) from exc
        except ValueError as exc:
            raise DriveError("Drive folder create returned invalid JSON.") from exc
        parsed = _parse_file(created) if isinstance(created, dict) else None
        if parsed is None:
            raise DriveError("Drive folder create returned an unexpected payload shape.")
        return parsed


class DriveService:
    """Capability-gated, read-only Drive facade."""

    def __init__(
        self,
        provider: DriveProvider | None = None,
        app_settings: Settings = settings,
    ) -> None:
        self._settings = app_settings
        self._provider = provider

    def status(self) -> DriveStatus:
        write_enabled = bool(self._settings.enable_google_drive_write)
        upload_cap = int(self._settings.google_drive_upload_max_bytes)
        folder_name = self._settings.google_drive_deliverables_folder_name
        if not self._settings.enable_google_drive:
            return DriveStatus(
                status="disabled",
                reason="ENABLE_GOOGLE_DRIVE is false.",
                write_enabled=write_enabled,
                upload_max_bytes=upload_cap,
                deliverables_folder_name=folder_name,
            )
        client_id = self._settings.google_client_id
        if not client_id or "CHANGEME" in client_id:
            return DriveStatus(
                status="blocked",
                reason="GOOGLE_CLIENT_ID is not configured.",
                write_enabled=write_enabled,
                upload_max_bytes=upload_cap,
                deliverables_folder_name=folder_name,
            )
        token_path = self._settings.google_token_dir.expanduser() / "token.json"
        if self._provider is None and not token_path.exists():
            return DriveStatus(
                status="blocked",
                reason="No token.json found; run scripts/auth_google.py once.",
                write_enabled=write_enabled,
                upload_max_bytes=upload_cap,
                deliverables_folder_name=folder_name,
            )
        return DriveStatus(
            status="ready",
            reason=None,
            write_enabled=write_enabled,
            upload_max_bytes=upload_cap,
            deliverables_folder_name=folder_name,
        )

    def _resolve_provider(self) -> DriveProvider:
        if self._provider is None:
            self._provider = GoogleDriveProvider(self._settings)
        return self._provider

    def _require_ready(self) -> None:
        current = self.status()
        if current.status != "ready":
            raise DriveError(current.reason or "Drive is not available.")

    def list_files(self, request: DriveSearchRequest) -> list[DriveFile]:
        self._require_ready()
        return self._resolve_provider().list_files(
            query=request.query,
            max_results=request.max_results,
        )

    def get_file(self, file_id: str) -> DriveFile:
        cleaned = file_id.strip()
        if not cleaned:
            raise DriveError("file_id must not be empty.")
        self._require_ready()
        return self._resolve_provider().get_file(cleaned)

    def ensure_deliverables_folder(
        self,
        request: DriveFolderRequest | None = None,
        *,
        requested_by: str | None = None,
    ) -> DriveFolderPreview:
        folder_request = request or DriveFolderRequest()
        self._require_ready()
        folder_name = _folder_name(folder_request.folder_name, self._settings)
        audit_args: dict[str, Any] = {
            "folder_name_len": len(folder_name),
            "dry_run": folder_request.dry_run,
        }
        if folder_request.dry_run:
            _audit_drive("preview_deliverables_folder", audit_args, requested_by, "preview")
            return DriveFolderPreview(status="preview", folder_name=folder_name)
        if not self._settings.enable_google_drive_write:
            _audit_drive("blocked_deliverables_folder", audit_args, requested_by, "blocked")
            return DriveFolderPreview(
                status="blocked",
                reason="ENABLE_GOOGLE_DRIVE_WRITE is false; refusing to create Drive folder.",
                folder_name=folder_name,
            )
        try:
            folder = self._resolve_provider().ensure_folder(folder_name=folder_name)
        except DriveError:
            _audit_drive("deliverables_folder_failed", audit_args, requested_by, "error")
            raise
        _audit_drive(
            "deliverables_folder_ready",
            {**audit_args, "folder_id": folder.file_id},
            requested_by,
            "ok",
        )
        return DriveFolderPreview(status="ready", folder_name=folder_name, folder=folder)

    def upload_file(
        self,
        request: DriveUploadRequest,
        *,
        requested_by: str | None = None,
    ) -> DriveUploadPreview:
        """Upload a local file with preview-first + double opt-in.

        Three independent gates protect this path:

        1. `ENABLE_GOOGLE_DRIVE_WRITE` (server policy).
        2. Per-call `dry_run=false`.
        3. `local_path` must resolve inside `COMPUTER_ALLOWED_ROOTS`.

        The size cap `GOOGLE_DRIVE_UPLOAD_MAX_BYTES` is enforced before the
        upload, so we never read a multi-GB file into memory on a `dry_run`
        either: dry runs just resolve metadata.
        """
        self._require_ready()
        source = _validate_upload_path(request.local_path, self._settings)
        size = source.stat().st_size
        folder_name = _folder_name(request.folder_name, self._settings)
        if size > self._settings.google_drive_upload_max_bytes:
            _audit_drive(
                "blocked_upload",
                {"size": size, "cap": self._settings.google_drive_upload_max_bytes},
                requested_by,
                "blocked: size_cap",
            )
            return DriveUploadPreview(
                status="blocked",
                reason=(
                    f"File exceeds GOOGLE_DRIVE_UPLOAD_MAX_BYTES "
                    f"({self._settings.google_drive_upload_max_bytes} bytes)."
                ),
                drive_name=request.drive_name or source.name,
                mime_type=request.mime_type or "application/octet-stream",
                size_bytes=size,
                folder_name=folder_name if request.use_deliverables_folder else None,
            )

        drive_name = (request.drive_name or source.name).strip() or source.name
        mime_type = (request.mime_type or "application/octet-stream").strip()
        audit_args: dict[str, Any] = {
            "drive_name": drive_name,
            "size": size,
            "mime_type": mime_type,
            "dry_run": request.dry_run,
        }

        if request.dry_run:
            _audit_drive("preview_upload", audit_args, requested_by, "preview")
            return DriveUploadPreview(
                status="preview",
                drive_name=drive_name,
                mime_type=mime_type,
                size_bytes=size,
                folder_id=request.folder_id,
                folder_name=folder_name if request.use_deliverables_folder else None,
            )

        if not self._settings.enable_google_drive_write:
            _audit_drive("blocked_upload", audit_args, requested_by, "blocked: write_disabled")
            return DriveUploadPreview(
                status="blocked",
                reason="ENABLE_GOOGLE_DRIVE_WRITE is false; refusing to upload.",
                drive_name=drive_name,
                mime_type=mime_type,
                size_bytes=size,
                folder_id=request.folder_id,
                folder_name=folder_name if request.use_deliverables_folder else None,
            )

        folder_id = request.folder_id
        if request.use_deliverables_folder and not folder_id:
            folder_result = self.ensure_deliverables_folder(
                DriveFolderRequest(folder_name=folder_name, dry_run=False),
                requested_by=requested_by,
            )
            if folder_result.status == "blocked":
                return DriveUploadPreview(
                    status="blocked",
                    reason=folder_result.reason,
                    drive_name=drive_name,
                    mime_type=mime_type,
                    size_bytes=size,
                    folder_name=folder_name,
                )
            folder_id = folder_result.folder.file_id if folder_result.folder is not None else None

        try:
            uploaded = self._resolve_provider().upload_file(
                source_path=source,
                drive_name=drive_name,
                mime_type=mime_type,
                folder_id=folder_id,
            )
        except DriveError:
            _audit_drive("upload_failed", audit_args, requested_by, "error")
            raise
        _audit_drive(
            "upload_succeeded",
            {**audit_args, "file_id": uploaded.file_id},
            requested_by,
            "ok",
        )
        return DriveUploadPreview(
            status="uploaded",
            drive_name=drive_name,
            mime_type=mime_type,
            size_bytes=size,
            folder_id=folder_id,
            folder_name=folder_name if request.use_deliverables_folder else None,
            file=uploaded,
        )


def _folder_name(raw: str | None, app_settings: Settings) -> str:
    cleaned = (raw or app_settings.google_drive_deliverables_folder_name).strip()
    if not cleaned:
        raise DriveError("Drive folder name must not be empty.")
    return cleaned


def _validate_upload_path(raw: str, app_settings: Settings) -> Path:
    """Resolve `raw` and refuse anything outside COMPUTER_ALLOWED_ROOTS.

    A defensive check against arbitrary-file exfiltration: even if the operator
    enables the upload flag, the agent can only push files from operator-allowed
    directories.
    """
    cleaned = raw.strip()
    if not cleaned:
        raise DriveError("local_path must not be empty.")
    if ".." in Path(cleaned).parts:
        raise DriveError("local_path must not contain '..' components.")
    candidate = Path(cleaned).expanduser().resolve()
    if not candidate.exists() or not candidate.is_file():
        raise DriveError("local_path does not exist or is not a file.")
    roots = [Path(root).expanduser().resolve() for root in app_settings.computer_allowed_roots]
    if not roots:
        raise DriveError(
            "COMPUTER_ALLOWED_ROOTS is empty; configure allowed roots before uploading."
        )
    for root in roots:
        if candidate == root or candidate.is_relative_to(root):
            return candidate
    raise DriveError("local_path is outside COMPUTER_ALLOWED_ROOTS.")


def _audit_drive(
    action: str,
    args_redacted: dict[str, Any],
    requested_by: str | None,
    result: str,
) -> None:
    try:
        record_audit_event(
            ToolAuditRecord(
                tool_name=f"drive.{action}",
                risk_level=ToolRiskLevel.EXTERNAL_ACTION,
                args_redacted=args_redacted,
                result_summary=result,
                actor_id=requested_by,
            )
        )
    except Exception as exc:
        _log.warning("drive_audit_failed", action=action, error=str(exc))

"""Google Drive for the personal assistant.

Default: read-only — list and inspect Drive files. Uploads and file moves are
opt-in WRITE capabilities gated by `ENABLE_GOOGLE_DRIVE_WRITE`, per-call
`dry_run=false`, ActionRequest approval in the API layer and narrow source-path
allow-lists. Every attempt is audited. Tests inject `FakeDriveProvider`, so the
suite never touches Google.
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
_FILE_FIELDS = "id,name,mimeType,modifiedTime,size,webViewLink,owners(displayName),parents"
_FOLDER_MIME = "application/vnd.google-apps.folder"
_MAX_RESULTS = 100
DriveSearchMode = Literal["name", "full_text", "all"]
DriveCorpus = Literal["user", "all_drives"]


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
    parent_ids: list[str] = Field(default_factory=list)


class DriveStatus(BaseModel):
    status: Literal["disabled", "blocked", "ready"]
    reason: str | None = None
    write_enabled: bool = False
    upload_max_bytes: int = 0
    deliverables_folder_name: str
    # GPT-5.5 P1 Fase 68b: scopes que el token actual aún no tiene.
    missing_scopes: list[str] = []


class DriveSearchRequest(BaseModel):
    query: str = Field(default="", max_length=2000)
    max_results: int = Field(default=20, ge=1, le=_MAX_RESULTS)
    search_mode: DriveSearchMode = "name"
    include_folders: bool = True
    mime_type: str | None = Field(default=None, max_length=200)
    corpus: DriveCorpus = "user"


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


class DriveOrganizeRequest(BaseModel):
    query: str = Field(default="", max_length=2000)
    target_folder_name: str | None = Field(default=None, min_length=1, max_length=400)
    max_files: int = Field(default=20, ge=1, le=50)
    search_mode: DriveSearchMode = "all"
    corpus: DriveCorpus = "user"
    dry_run: bool = True
    # Frozen file IDs captured at preview time. When set (execute path), the
    # service moves EXACTLY these files instead of re-searching — the operator
    # approved a specific set; a fresh search at execute time could move a
    # different set and break the human-approval guarantee. Empty/None only on
    # the preview pass itself.
    file_ids: list[str] | None = Field(default=None, max_length=50)


class DriveOrganizeOperation(BaseModel):
    file: DriveFile
    target_folder_name: str
    target_folder_id: str | None = None
    removed_parent_ids: list[str] = Field(default_factory=list)
    status: Literal["planned", "moved", "skipped"] = "planned"
    reason: str | None = None


class DriveOrganizePreview(BaseModel):
    status: Literal["preview", "blocked", "completed"]
    reason: str | None = None
    query: str
    target_folder_name: str
    dry_run: bool
    operation_count: int
    operations: list[DriveOrganizeOperation] = Field(default_factory=list)


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
    def list_files(
        self,
        *,
        query: str,
        max_results: int,
        search_mode: DriveSearchMode = "name",
        include_folders: bool = True,
        mime_type: str | None = None,
        corpus: DriveCorpus = "user",
    ) -> list[DriveFile]: ...

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

    def move_file(
        self,
        *,
        file_id: str,
        destination_folder_id: str,
        remove_parent_ids: list[str],
    ) -> DriveFile: ...


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
        self.move_calls: list[dict[str, Any]] = []

    def list_files(
        self,
        *,
        query: str,
        max_results: int,
        search_mode: DriveSearchMode = "name",
        include_folders: bool = True,
        mime_type: str | None = None,
        corpus: DriveCorpus = "user",
    ) -> list[DriveFile]:
        self.calls.append(f"list:{search_mode}:{corpus}:{query}")
        if self._raises:
            raise DriveError("fake drive failure")
        results = self._files
        if query:
            needle = query.lower()
            results = [item for item in results if needle in item.name.lower()]
        if not include_folders:
            results = [item for item in results if not item.is_folder]
        if mime_type:
            results = [item for item in results if item.mime_type == mime_type]
        return list(results[:max_results])

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

    def move_file(
        self,
        *,
        file_id: str,
        destination_folder_id: str,
        remove_parent_ids: list[str],
    ) -> DriveFile:
        self.move_calls.append(
            {
                "file_id": file_id,
                "destination_folder_id": destination_folder_id,
                "remove_parent_ids": list(remove_parent_ids),
            }
        )
        if self._raises:
            raise DriveError("fake drive failure")
        for index, item in enumerate(self._files):
            if item.file_id == file_id:
                moved = item.model_copy(update={"parent_ids": [destination_folder_id]})
                self._files[index] = moved
                return moved
        raise DriveError(f"File {file_id!r} not found.")


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
        parent_ids=[str(parent) for parent in raw.get("parents") or []],
    )


def _escape_drive_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _build_drive_query(request: DriveSearchRequest) -> str:
    clauses = ["trashed = false"]
    query = request.query.strip()
    if query:
        safe = _escape_drive_query(query)
        if request.search_mode == "name":
            clauses.append(f"name contains '{safe}'")
        elif request.search_mode == "full_text":
            clauses.append(f"fullText contains '{safe}'")
        else:
            clauses.append(f"(name contains '{safe}' or fullText contains '{safe}')")
    if not request.include_folders:
        clauses.append(f"mimeType != '{_FOLDER_MIME}'")
    if request.mime_type:
        clauses.append(f"mimeType = '{_escape_drive_query(request.mime_type)}'")
    return " and ".join(clauses)


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

    def list_files(
        self,
        *,
        query: str,
        max_results: int,
        search_mode: DriveSearchMode = "name",
        include_folders: bool = True,
        mime_type: str | None = None,
        corpus: DriveCorpus = "user",
    ) -> list[DriveFile]:
        request = DriveSearchRequest(
            query=query,
            max_results=max_results,
            search_mode=search_mode,
            include_folders=include_folders,
            mime_type=mime_type,
            corpus=corpus,
        )
        params: dict[str, str] = {
            "pageSize": str(max_results),
            "fields": f"files({_FILE_FIELDS})",
            "orderBy": "modifiedTime desc",
            "q": _build_drive_query(request),
        }
        if corpus == "all_drives":
            params.update(
                {
                    "corpora": "allDrives",
                    "includeItemsFromAllDrives": "true",
                    "supportsAllDrives": "true",
                }
            )
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

    def move_file(
        self,
        *,
        file_id: str,
        destination_folder_id: str,
        remove_parent_ids: list[str],
    ) -> DriveFile:
        params: dict[str, str] = {
            "addParents": destination_folder_id,
            "fields": _FILE_FIELDS,
            "supportsAllDrives": "true",
        }
        if remove_parent_ids:
            params["removeParents"] = ",".join(remove_parent_ids)
        try:
            response = retry_transient_http(
                lambda: httpx.patch(
                    f"{_DRIVE_API}/files/{file_id}",
                    params=params,
                    json={},
                    headers={"Authorization": f"Bearer {self._token()}"},
                    timeout=self._settings.http_timeout_seconds,
                )
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise DriveError(f"Drive move failed: {redact_google_error(str(exc))}") from exc
        except ValueError as exc:
            raise DriveError("Drive move returned invalid JSON.") from exc
        parsed = _parse_file(payload) if isinstance(payload, dict) else None
        if parsed is None:
            raise DriveError("Drive move returned an unexpected payload shape.")
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
        # Scope check (GPT-5.5 P1 Fase 68b): drive.readonly is enough for
        # search/list; upload/folder/organize need `drive` (full). If the
        # write scope is missing while writes are enabled, the capability
        # would say `ready` and fail later — surface the gap now.
        required = self._required_scopes(write_enabled, self._settings.google_drive_scopes)
        missing: list[str] = []
        if self._provider is None and token_path.exists() and required:
            try:
                from cognitive_os.core.google_oauth import (  # noqa: PLC0415
                    GoogleCredentialsLoader,
                )

                missing = GoogleCredentialsLoader(token_path=token_path).missing_scopes(required)
            except Exception:  # noqa: BLE001 - best-effort scope check
                missing = []
        if missing:
            return DriveStatus(
                status="blocked",
                reason=(
                    "Google token is missing required Drive scopes: "
                    + ", ".join(missing)
                    + ". Delete token.json and re-run scripts/auth_google.py "
                    "to re-consent."
                ),
                write_enabled=write_enabled,
                upload_max_bytes=upload_cap,
                deliverables_folder_name=folder_name,
                missing_scopes=missing,
            )
        return DriveStatus(
            status="ready",
            reason=None,
            write_enabled=write_enabled,
            upload_max_bytes=upload_cap,
            deliverables_folder_name=folder_name,
        )

    @staticmethod
    def _required_scopes(write_enabled: bool, configured: list[str]) -> list[str]:
        """Scopes Drive must have to operate at this configuration.

        Honor whatever the operator put in `GOOGLE_DRIVE_SCOPES` — that is
        the consent we asked them to grant via `scripts/auth_google.py` and the
        validation should match. Falls back to a sensible baseline only if the
        env var is empty (search/list/get under `drive.readonly`; upload /
        folder ensure / organize under the broader `drive`).
        """
        if configured:
            return list(configured)
        scopes = ["https://www.googleapis.com/auth/drive.readonly"]
        if write_enabled:
            scopes.append("https://www.googleapis.com/auth/drive")
        return scopes

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
            search_mode=request.search_mode,
            include_folders=request.include_folders,
            mime_type=request.mime_type,
            corpus=request.corpus,
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

    def organize_files(
        self,
        request: DriveOrganizeRequest,
        *,
        requested_by: str | None = None,
    ) -> DriveOrganizePreview:
        """Preview or move matched files into a target folder.

        This is intentionally conservative: no deletion, no permission changes,
        no folder moves, and a hard per-request cap. Real execution requires the
        same Drive write flag used by uploads and is expected to run only through
        approved ActionRequests at the API layer.
        """
        self._require_ready()
        query = request.query.strip()
        target_folder_name = _folder_name(request.target_folder_name, self._settings)
        provider = self._resolve_provider()
        missing_frozen = 0
        if request.file_ids:
            # Execute path: move EXACTLY the approved preview set. No re-search
            # (same guarantee as computer_organize: run the approved plan, not
            # a fresh scan). Files deleted between approve and execute are
            # skipped, never substituted.
            files = []
            for fid in request.file_ids[: request.max_files]:
                try:
                    files.append(provider.get_file(fid))
                except DriveError:
                    missing_frozen += 1
        else:
            files = provider.list_files(
                query=query,
                max_results=request.max_files,
                search_mode=request.search_mode,
                include_folders=False,
                mime_type=None,
                corpus=request.corpus,
            )
        operations = [
            DriveOrganizeOperation(file=file, target_folder_name=target_folder_name)
            for file in files
        ]
        audit_args: dict[str, Any] = {
            "query_len": len(query),
            "target_folder_name_len": len(target_folder_name),
            "max_files": request.max_files,
            "operation_count": len(operations),
            "frozen_file_ids": len(request.file_ids or []),
            "missing_frozen": missing_frozen,
            "dry_run": request.dry_run,
        }
        if request.dry_run:
            _audit_drive("preview_organize_files", audit_args, requested_by, "preview")
            return DriveOrganizePreview(
                status="preview",
                query=query,
                target_folder_name=target_folder_name,
                dry_run=True,
                operation_count=len(operations),
                operations=operations,
            )

        if not self._settings.enable_google_drive_write:
            _audit_drive("blocked_organize_files", audit_args, requested_by, "blocked")
            return DriveOrganizePreview(
                status="blocked",
                reason="ENABLE_GOOGLE_DRIVE_WRITE is false; refusing to move Drive files.",
                query=query,
                target_folder_name=target_folder_name,
                dry_run=False,
                operation_count=len(operations),
                operations=operations,
            )

        try:
            folder = provider.ensure_folder(folder_name=target_folder_name)
            completed: list[DriveOrganizeOperation] = []
            for operation in operations:
                file = operation.file
                remove_parent_ids = [
                    parent_id for parent_id in file.parent_ids if parent_id != folder.file_id
                ]
                if folder.file_id in file.parent_ids and not remove_parent_ids:
                    completed.append(
                        operation.model_copy(
                            update={
                                "target_folder_id": folder.file_id,
                                "status": "skipped",
                                "reason": "File is already in the target folder.",
                            }
                        )
                    )
                    continue
                moved = provider.move_file(
                    file_id=file.file_id,
                    destination_folder_id=folder.file_id,
                    remove_parent_ids=remove_parent_ids,
                )
                completed.append(
                    DriveOrganizeOperation(
                        file=moved,
                        target_folder_name=target_folder_name,
                        target_folder_id=folder.file_id,
                        removed_parent_ids=remove_parent_ids,
                        status="moved",
                    )
                )
        except DriveError:
            _audit_drive("organize_files_failed", audit_args, requested_by, "error")
            raise

        _audit_drive(
            "organize_files_succeeded",
            {**audit_args, "folder_id": folder.file_id},
            requested_by,
            "ok",
        )
        return DriveOrganizePreview(
            status="completed",
            query=query,
            target_folder_name=target_folder_name,
            dry_run=False,
            operation_count=len(completed),
            operations=completed,
        )

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
        3. `local_path` must resolve inside a safe export root:
           `DOCUMENT_OUTPUT_ROOT`, `LOCAL_STORAGE_DIR/workspaces`,
           `OPENSHELL_ALLOWED_OUTPUT_DIR`, or `COMPUTER_ALLOWED_ROOTS`.

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
    """Resolve `raw` and refuse anything outside safe upload roots.

    A defensive check against arbitrary-file exfiltration: even if the operator
    enables the upload flag, the agent can only push files from operator-allowed
    directories and system-generated deliverable roots. We deliberately allow
    `LOCAL_STORAGE_DIR/workspaces`, not the whole storage root, so OAuth tokens
    and other runtime state under `storage/` are never in scope by default.
    """
    cleaned = raw.strip()
    if not cleaned:
        raise DriveError("local_path must not be empty.")
    if ".." in Path(cleaned).parts:
        raise DriveError("local_path must not contain '..' components.")
    candidate = Path(cleaned).expanduser().resolve()
    if not candidate.exists() or not candidate.is_file():
        raise DriveError("local_path does not exist or is not a file.")
    roots = _allowed_upload_roots(app_settings)
    if not roots:
        raise DriveError(
            "No Drive upload roots are configured; configure deliverable or allowed roots."
        )
    for root in roots:
        if candidate == root or candidate.is_relative_to(root):
            return candidate
    raise DriveError("local_path is outside configured Drive upload roots.")


def _allowed_upload_roots(app_settings: Settings) -> list[Path]:
    roots: list[Path] = []
    candidates: list[Path | str] = [
        app_settings.document_output_root,
        Path(app_settings.local_storage_dir) / "workspaces",
        app_settings.openshell_allowed_output_dir,
        *app_settings.computer_allowed_roots,
    ]
    for raw in candidates:
        try:
            root = Path(raw).expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if root not in roots:
            roots.append(root)
    return roots


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

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from cognitive_os.actions.policy import (
    ActionPolicyViolation,
    allowed_roots,
    validate_path_inside_roots,
)
from cognitive_os.actions.schemas import (
    ActionCapabilityStatus,
    CapabilityStatus,
    ComputerInventoryRequest,
    ComputerInventoryResult,
    ComputerOrganizeExecutionResult,
    ComputerOrganizePlan,
    ComputerOrganizeRequest,
    FileInventoryEntry,
    FileMovePreview,
    FileMoveResult,
)
from cognitive_os.core.config import Settings, settings

TYPE_DIRS: dict[str, set[str]] = {
    "Documents": {".doc", ".docx", ".odt", ".rtf", ".txt", ".md"},
    "PDFs": {".pdf"},
    "Spreadsheets": {".csv", ".tsv", ".xls", ".xlsx", ".ods"},
    "Presentations": {".ppt", ".pptx", ".odp"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".heic"},
    "Audio": {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"},
    "Video": {".mp4", ".mov", ".mkv", ".webm", ".avi"},
    "Archives": {".zip", ".tar", ".gz", ".tgz", ".rar", ".7z"},
    "Code": {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".toml"},
}

SENSITIVE_PATH_MARKERS = {
    ".env",
    ".git",
    ".ssh",
    ".gnupg",
    "credentials",
    "credential",
    "secret",
    "secrets",
    "token",
    "tokens",
    "password",
    "keychain",
}


class ComputerActionService:
    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    def status(self) -> ActionCapabilityStatus:
        roots = allowed_roots(self._settings)
        reasons: list[str] = []
        if not self._settings.enable_computer_actions:
            reasons.append("ENABLE_COMPUTER_ACTIONS=false")
            status: CapabilityStatus = "disabled"
        elif not roots:
            reasons.append("COMPUTER_ALLOWED_ROOTS is empty")
            status = "blocked"
        else:
            status = "ready"
        return ActionCapabilityStatus(
            name="computer",
            status=status,
            summary="Local filesystem organization through preview-first move plans.",
            requires_approval=self._manual_approval_required(),
            dry_run_only=self._settings.computer_organize_dry_run_only,
            reasons=reasons,
            metadata={
                "allowed_roots": [str(root) for root in roots],
                "max_files_per_plan": self._settings.computer_max_files_per_plan,
                "inventory_storage": str(Path(self._settings.local_storage_dir) / "file_inventory"),
            },
        )

    def build_organize_plan(self, request: ComputerOrganizeRequest) -> ComputerOrganizePlan:
        try:
            if not self._settings.enable_computer_actions:
                raise ActionPolicyViolation("Computer actions are disabled.")
            roots = allowed_roots(self._settings)
            root = validate_path_inside_roots(Path(request.root_path), roots, label="computer")
            if _is_sensitive_root(root):
                # V2-EVAL-200: never plan moves under ~/.ssh, ~/.gnupg, etc.
                raise ActionPolicyViolation(
                    "Root path contains a sensitive marker (.ssh/.gnupg/credentials/...)."
                )
            if not root.exists() or not root.is_dir():
                raise ActionPolicyViolation("Root path does not exist or is not a directory.")
            operations = self._preview_moves(root, request)
            return ComputerOrganizePlan(
                status="ok",
                root_path=str(root),
                dry_run_only=self._settings.computer_organize_dry_run_only,
                requires_approval=self._manual_approval_required(),
                operations=operations,
                warnings=[],
            )
        except ActionPolicyViolation as exc:
            return ComputerOrganizePlan(
                status="blocked",
                root_path=request.root_path,
                dry_run_only=True,
                requires_approval=self._manual_approval_required(),
                reason=str(exc),
            )

    def execute_organize_plan(
        self,
        request: ComputerOrganizeRequest,
    ) -> ComputerOrganizeExecutionResult:
        """Build a plan from `request` then execute it.

        Kept as a convenience for callers that have only a request (no stored plan)
        and for backward compatibility. Production paths should call
        `execute_approved_plan(plan)` with the operator-approved plan so that the
        bytes actually moved on disk match the bytes the operator inspected.
        """
        plan = self.build_organize_plan(request)
        return self.execute_approved_plan(plan)

    def execute_approved_plan(
        self,
        plan: ComputerOrganizePlan,
    ) -> ComputerOrganizeExecutionResult:
        """Execute an already-approved plan without re-scanning the directory.

        The audit chain is: build_organize_plan -> human approval over the exact
        preview -> dispatch -> this method. Re-running `build_organize_plan` here
        would silently swap in whatever the filesystem looks like NOW, breaking the
        HITL guarantee. Each individual move is still re-validated (path inside
        root, source still a regular file, destination still free) so operations
        whose preconditions changed between approval and dispatch are reported as
        `failed_revalidation` rather than blindly applied.
        """
        if plan.status == "blocked":
            return ComputerOrganizeExecutionResult(
                status="blocked",
                root_path=plan.root_path,
                reason=plan.reason,
            )
        if self._settings.computer_organize_dry_run_only:
            return ComputerOrganizeExecutionResult(
                status="blocked",
                root_path=plan.root_path,
                reason="Computer organize execution is dry-run only by configuration.",
                warnings=plan.warnings,
            )

        # Re-validate the root against the allow-list — config may have changed
        # between approval and dispatch (root removed, flag flipped).
        roots = allowed_roots(self._settings)
        try:
            root = validate_path_inside_roots(Path(plan.root_path), roots, label="computer")
            if _is_sensitive_root(root):
                # V2-EVAL-200: defense in depth — never execute a plan whose
                # root resolves under a sensitive marker, even if it slipped
                # past the planner (e.g. legacy ActionRequest from before fix).
                raise ActionPolicyViolation(
                    "Root path contains a sensitive marker (.ssh/.gnupg/credentials/...)."
                )
        except ActionPolicyViolation as exc:
            return ComputerOrganizeExecutionResult(
                status="blocked",
                root_path=plan.root_path,
                reason=str(exc),
                warnings=plan.warnings,
            )

        results: list[FileMoveResult] = []
        for operation in plan.operations:
            source = (root / operation.source).resolve()
            destination = (root / operation.destination).resolve()
            try:
                validate_path_inside_roots(source, [root], label="computer source")
                validate_path_inside_roots(destination, [root], label="computer destination")
                if source.is_symlink() or not source.is_file():
                    raise ActionPolicyViolation(
                        "Source is no longer a regular file (changed after approval)."
                    )
                if destination.exists():
                    raise ActionPolicyViolation(
                        "Destination already exists (changed after approval)."
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                source.replace(destination)
                results.append(
                    FileMoveResult(
                        source=operation.source,
                        destination=operation.destination,
                        status="moved",
                    )
                )
            except Exception as exc:
                results.append(
                    FileMoveResult(
                        source=operation.source,
                        destination=operation.destination,
                        status="failed",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

        failed = [result for result in results if result.status == "failed"]
        return ComputerOrganizeExecutionResult(
            status="failed" if failed else "completed",
            root_path=plan.root_path,
            moved_count=len([result for result in results if result.status == "moved"]),
            operations=results,
            warnings=plan.warnings,
            reason=f"{len(failed)} move(s) failed." if failed else None,
        )

    def build_inventory(self, request: ComputerInventoryRequest) -> ComputerInventoryResult:
        """Create a read-only filesystem inventory under an allow-listed root.

        The inventory records metadata only: relative path, extension, size,
        modification time, category and optional sha256. It deliberately skips
        sensitive paths and symlinks, and writes the same result to
        `LOCAL_STORAGE_DIR/file_inventory/*.json` so the agent can compare future
        scans without rereading the whole filesystem from memory.
        """
        try:
            if not self._settings.enable_computer_actions:
                raise ActionPolicyViolation("Computer actions are disabled.")
            roots = allowed_roots(self._settings)
            root = validate_path_inside_roots(Path(request.root_path), roots, label="computer")
            if _is_sensitive_root(root):
                # V2-EVAL-200: do not enumerate ~/.ssh, ~/.gnupg, credentials dirs.
                raise ActionPolicyViolation(
                    "Root path contains a sensitive marker (.ssh/.gnupg/credentials/...)."
                )
            if not root.exists() or not root.is_dir():
                raise ActionPolicyViolation("Root path does not exist or is not a directory.")
            result = self._scan_inventory(root, request)
            inventory_path = self._write_inventory(result)
            return result.model_copy(update={"inventory_path": str(inventory_path)})
        except ActionPolicyViolation as exc:
            return ComputerInventoryResult(
                status="blocked",
                root_path=request.root_path,
                reason=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - safe metadata scan reports failure
            return ComputerInventoryResult(
                status="failed",
                root_path=request.root_path,
                reason=f"{type(exc).__name__}: {exc}",
            )

    def _preview_moves(
        self,
        root: Path,
        request: ComputerOrganizeRequest,
    ) -> list[FileMovePreview]:
        limit = min(
            request.max_files or self._settings.computer_max_files_per_plan,
            self._settings.computer_max_files_per_plan,
        )
        files = root.rglob("*") if request.recursive else root.iterdir()
        operations: list[FileMovePreview] = []
        claimed_destinations: set[str] = set()
        for candidate in files:
            if len(operations) >= limit:
                break
            if candidate.is_symlink() or not candidate.is_file():
                continue
            if not request.include_hidden and any(part.startswith(".") for part in candidate.parts):
                continue
            category = _category_for(candidate)
            if category == "Other":
                continue
            destination = _deduped_destination(
                root / category / candidate.name,
                claimed_destinations,
            )
            if destination.resolve() == candidate.resolve():
                continue
            claimed_destinations.add(destination.as_posix())
            operations.append(
                FileMovePreview(
                    source=candidate.relative_to(root).as_posix(),
                    destination=destination.relative_to(root).as_posix(),
                    category=category,
                    reason=f"Extension {candidate.suffix.lower() or '[none]'} maps to {category}.",
                )
            )
        return operations

    def _scan_inventory(
        self,
        root: Path,
        request: ComputerInventoryRequest,
    ) -> ComputerInventoryResult:
        iterator = root.rglob("*") if request.recursive else root.iterdir()
        entries: list[FileInventoryEntry] = []
        warnings: list[str] = []
        by_category: Counter[str] = Counter()
        by_extension: Counter[str] = Counter()
        total_bytes = 0

        for candidate in iterator:
            if len(entries) >= request.max_files:
                warnings.append(f"inventory_truncated_at_{request.max_files}_files")
                break
            try:
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                relative = candidate.relative_to(root)
                if _is_sensitive_path(relative):
                    warnings.append(f"skipped_sensitive_path:{relative.as_posix()}")
                    continue
                if not request.include_hidden and any(
                    part.startswith(".") for part in relative.parts
                ):
                    continue
                stat = candidate.stat()
                category = _category_for(candidate)
                extension = candidate.suffix.lower() or "[none]"
                digest = _sha256_file(candidate) if request.include_sha256 else None
                entry = FileInventoryEntry(
                    relative_path=relative.as_posix(),
                    category=category,
                    extension=extension,
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                    sha256=digest,
                )
                entries.append(entry)
                by_category[category] += 1
                by_extension[extension] += 1
                total_bytes += stat.st_size
            except OSError as exc:
                warnings.append(f"skipped_unreadable_path:{candidate.name}:{type(exc).__name__}")

        return ComputerInventoryResult(
            status="completed",
            root_path=str(root),
            file_count=len(entries),
            total_bytes=total_bytes,
            by_category=dict(sorted(by_category.items())),
            by_extension=dict(sorted(by_extension.items())),
            entries=entries,
            warnings=warnings[:200],
        )

    def _write_inventory(self, result: ComputerInventoryResult) -> Path:
        root = Path(self._settings.local_storage_dir).expanduser().resolve() / "file_inventory"
        root.mkdir(parents=True, exist_ok=True)
        slug = hashlib.sha256(result.root_path.encode("utf-8")).hexdigest()[:12]
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = root / f"inventory-{slug}-{stamp}.json"
        path.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def _manual_approval_required(self) -> bool:
        return bool(self._settings.require_human_approval_for_external_actions)


def _category_for(path: Path) -> str:
    suffix = path.suffix.lower()
    for category, suffixes in TYPE_DIRS.items():
        if suffix in suffixes:
            return category
    return "Other"


def _is_sensitive_path(relative: Path) -> bool:
    parts = {part.casefold() for part in relative.parts}
    return any(marker in parts for marker in SENSITIVE_PATH_MARKERS)


def _is_sensitive_root(root: Path) -> bool:
    """Return True if `root` (or any ancestor) is a sensitive directory.

    V2-EVAL-200 (P1): `_is_sensitive_path(relative)` walks the path RELATIVE to
    root, so passing `root_path=/home/jgonz/.ssh` would yield `id_ed25519` as a
    relative path with no `.ssh` component and the per-entry check would let it
    through. Guard the root itself with the same marker set, evaluating the
    resolved absolute path so symlinks or `..` traversals cannot disguise the
    leaf directory.
    """
    resolved = root.expanduser().resolve(strict=False)
    parts = {part.casefold() for part in resolved.parts}
    return any(marker in parts for marker in SENSITIVE_PATH_MARKERS)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _deduped_destination(destination: Path, claimed: set[str]) -> Path:
    if destination.as_posix() not in claimed and not destination.exists():
        return destination
    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    for index in range(2, 1000):
        candidate = parent / f"{stem}-{index}{suffix}"
        if candidate.as_posix() not in claimed and not candidate.exists():
            return candidate
    return parent / f"{stem}-999{suffix}"

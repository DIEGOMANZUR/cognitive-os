from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from cognitive_os.core.config import Settings
from cognitive_os.deepagents.openshell_schemas import OpenShellTask
from cognitive_os.tools.policy import redact_tool_args


class OpenShellPolicyViolation(Exception):  # noqa: N818 - required public API name.
    """Raised when an OpenShell task violates Cognitive OS policy."""


BLOCKED_NAMES = {".env"}
BLOCKED_SUFFIXES = {".pem", ".key", ".p12"}
SENSITIVE_NAME_MARKERS = ("credential", "credentials", "secret", "backup")
SENSITIVE_PDF_MARKERS = ("judicial", "personal", "causa", "case", "tribunal")


def validate_openshell_task(task: OpenShellTask, settings: Settings) -> None:
    if not settings.enable_openshell_sandbox:
        raise OpenShellPolicyViolation("OpenShell sandbox is disabled.")
    if task.allow_network and not settings.openshell_allow_network:
        raise OpenShellPolicyViolation("OpenShell network access is disabled by policy.")
    if task.max_runtime_seconds > settings.openshell_max_runtime_seconds:
        raise OpenShellPolicyViolation("OpenShell task exceeds max runtime policy.")
    if task.max_output_bytes > settings.openshell_max_output_bytes:
        raise OpenShellPolicyViolation("OpenShell task exceeds max output policy.")
    sanitize_input_file_paths(task.input_files, settings.openshell_allowed_input_dir)


def sanitize_input_file_paths(input_files: list[str], allowed_input_dir: Path) -> list[Path]:
    root = allowed_input_dir.resolve()
    sanitized: list[Path] = []
    for raw_file in input_files:
        raw_path = Path(raw_file)
        if any(part == ".." for part in raw_path.parts):
            raise OpenShellPolicyViolation("Input path traversal is blocked.")
        raw_candidate = raw_path if raw_path.is_absolute() else root / raw_path
        if raw_candidate.is_symlink():
            raise OpenShellPolicyViolation("Symlink input files are blocked.")
        candidate = raw_candidate.resolve()
        _ensure_inside(candidate, root, "Input file escapes allowed input directory.")
        _ensure_file_allowed(candidate)
        sanitized.append(candidate)
    return sanitized


def validate_output_file_path(path: Path, allowed_output_dir: Path) -> Path:
    if path.is_absolute():
        raise OpenShellPolicyViolation("Absolute output paths are blocked.")
    if any(part == ".." for part in path.parts):
        raise OpenShellPolicyViolation("Output path traversal is blocked.")
    root = allowed_output_dir.resolve()
    candidate = (root / path).resolve()
    _ensure_inside(candidate, root, "Output file escapes allowed output directory.")
    return candidate


def redact_openshell_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], redact_tool_args(payload))


def _ensure_inside(candidate: Path, root: Path, message: str) -> None:
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise OpenShellPolicyViolation(message) from exc


def _ensure_file_allowed(path: Path) -> None:
    lowered_name = path.name.lower()
    lowered_full = path.as_posix().lower()
    if path.is_symlink():
        raise OpenShellPolicyViolation("Symlink input files are blocked.")
    if not path.exists() or not path.is_file():
        raise OpenShellPolicyViolation("Input file does not exist or is not a regular file.")
    if lowered_name in BLOCKED_NAMES or path.suffix.lower() in BLOCKED_SUFFIXES:
        raise OpenShellPolicyViolation("Sensitive file type is blocked.")
    if any(marker in lowered_full for marker in SENSITIVE_NAME_MARKERS):
        raise OpenShellPolicyViolation("Sensitive file path is blocked.")
    if path.suffix.lower() == ".pdf" and any(
        marker in lowered_full for marker in SENSITIVE_PDF_MARKERS
    ):
        raise OpenShellPolicyViolation("Sensitive PDF requires explicit human approval.")

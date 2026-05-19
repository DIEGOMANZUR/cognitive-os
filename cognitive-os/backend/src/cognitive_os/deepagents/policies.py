from __future__ import annotations

from pathlib import Path

from cognitive_os.deepagents.schemas import DeepAgentToolPolicy, DeepAgentWorkspace


class DeepAgentPolicyViolation(Exception):  # noqa: N818 - required public API name.
    """Raised when a DeepAgent tool request violates Cognitive OS policy."""


ALWAYS_BLOCKED_TOOLS = {
    "execute",
    "shell",
    "bash",
    "python_exec",
    "browser_action",
    "send_email",
    "publish_social_post",
    "delete_file",
    "edit_project_file",
}


def validate_tool_allowed(tool_name: str, policy: DeepAgentToolPolicy) -> None:
    if tool_name in ALWAYS_BLOCKED_TOOLS:
        _raise_blocked(tool_name)

    allowed = {
        "search_local_docs": policy.allow_local_rag,
        "read_document_pages": policy.allow_local_rag,
        "graph_query_readonly": policy.allow_neo4j_read,
        "search_web": policy.allow_web,
        "write_workspace_file": policy.allow_workspace_write,
        "plan_route": policy.allow_maps,
        "geocode_address": policy.allow_maps,
        "list_calendar_events": policy.allow_calendar_read,
        "check_calendar_freebusy": policy.allow_calendar_read,
        "search_drive_files": policy.allow_drive_read,
        "preview_drive_organization": policy.allow_drive_read,
        "search_notes": policy.allow_notes_read,
        "browse_real_navigate": policy.allow_kimi_webbridge,
        "browse_real_snapshot": policy.allow_kimi_webbridge,
        "browse_real_screenshot": policy.allow_kimi_webbridge,
        "solve_image_captcha": policy.allow_captcha_solving,
        "solve_token_captcha": policy.allow_captcha_solving,
    }
    if not allowed.get(tool_name, False):
        _raise_blocked(tool_name)


def validate_workspace_path(path: Path, workspace: DeepAgentWorkspace) -> Path:
    if path.is_absolute():
        msg = "Absolute paths are not allowed in DeepAgent workspaces."
        raise DeepAgentPolicyViolation(msg)
    if any(part == ".." for part in path.parts):
        msg = "Path traversal is not allowed in DeepAgent workspaces."
        raise DeepAgentPolicyViolation(msg)

    root = workspace.root_dir.resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        msg = "Workspace path escapes the controlled workspace."
        raise DeepAgentPolicyViolation(msg) from exc

    parent = candidate.parent
    if parent.exists() and parent.is_symlink():
        msg = "Symlink parents are not allowed in DeepAgent workspaces."
        raise DeepAgentPolicyViolation(msg)
    if candidate.exists() and candidate.is_symlink():
        msg = "Symlink targets are not allowed in DeepAgent workspaces."
        raise DeepAgentPolicyViolation(msg)
    return candidate


def _raise_blocked(tool_name: str) -> None:
    msg = f"DeepAgent tool blocked by policy: {tool_name}"
    raise DeepAgentPolicyViolation(msg)

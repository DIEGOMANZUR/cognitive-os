from __future__ import annotations

from pathlib import Path
from typing import Any

from cognitive_os.core.config import Settings, settings
from cognitive_os.deepagents.memory_schemas import DeepAgentSkillDescriptor

ALLOWED_SKILL_TOOLS = {
    "search_local_docs",
    "read_document_pages",
    "graph_query_readonly",
    "search_web",
    "write_workspace_file",
    "list_available_skills",
    "read_skill",
    "get_relevant_memory",
    "propose_memory_update",
    "run_sandboxed_code_task",
}
DANGEROUS_SKILL_TOOLS = {
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


class SkillValidationError(ValueError):
    """Raised when a DeepAgents skill does not satisfy Cognitive OS policy."""


class DeepAgentSkillsRegistry:
    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    def discover_core_skills(self) -> list[DeepAgentSkillDescriptor]:
        return self._discover(self._core_skills_dir())

    def discover_user_skills(self, user_id: str | None) -> list[DeepAgentSkillDescriptor]:
        root = self._settings.deepagents_user_skills_dir
        if user_id:
            user_root = _safe_child_dir(root, user_id)
            if user_root is None:
                return []
            if user_root.exists():
                root = user_root
        return self._discover(root, allow_missing=True)

    def get_enabled_skill_paths(
        self,
        agent_name: str,
        task_type: str,
        user_id: str | None = None,
    ) -> list[str]:
        del agent_name
        if not self._settings.deepagents_enable_skills:
            return []
        skills = self.discover_core_skills() + self.discover_user_skills(user_id)
        enabled: list[str] = []
        for skill in skills:
            if not skill.enabled:
                continue
            if task_type in {"research", "document_analysis"} and skill.risk_level != "read_only":
                continue
            enabled.append(skill.path)
        return enabled

    def validate_skill(self, skill_path: Path) -> DeepAgentSkillDescriptor:
        skill_file = skill_path if skill_path.name == "SKILL.md" else skill_path / "SKILL.md"
        if not skill_file.exists():
            msg = f"Skill file not found: {skill_file}"
            raise SkillValidationError(msg)
        frontmatter = _parse_frontmatter(skill_file.read_text(encoding="utf-8"))
        required = {"name", "description", "version", "risk_level", "allowed_tools"}
        missing = sorted(required - set(frontmatter))
        if missing:
            msg = f"Skill frontmatter missing required keys: {', '.join(missing)}"
            raise SkillValidationError(msg)
        allowed_tools = frontmatter["allowed_tools"]
        if not isinstance(allowed_tools, list) or not all(
            isinstance(tool, str) for tool in allowed_tools
        ):
            msg = "Skill allowed_tools must be a list of strings."
            raise SkillValidationError(msg)
        dangerous = sorted(set(allowed_tools) & DANGEROUS_SKILL_TOOLS)
        if dangerous:
            msg = f"Skill declares dangerous tools: {', '.join(dangerous)}"
            raise SkillValidationError(msg)
        unknown = sorted(set(allowed_tools) - ALLOWED_SKILL_TOOLS)
        if unknown:
            msg = f"Skill declares unknown tools: {', '.join(unknown)}"
            raise SkillValidationError(msg)
        risk_level = str(frontmatter["risk_level"])
        enabled = risk_level in {"read_only", "approval_required"}
        return DeepAgentSkillDescriptor(
            name=str(frontmatter["name"]),
            description=str(frontmatter["description"]),
            path=str(skill_file.parent),
            version=str(frontmatter["version"]),
            risk_level=risk_level,
            allowed_tools=allowed_tools,
            enabled=enabled,
        )

    def _discover(
        self,
        root: Path,
        *,
        allow_missing: bool = False,
    ) -> list[DeepAgentSkillDescriptor]:
        if not root.exists():
            return [] if allow_missing else []
        root = root.resolve()
        skills: list[DeepAgentSkillDescriptor] = []
        for skill_file in sorted(root.glob("*/SKILL.md")):
            resolved_skill_file = skill_file.resolve()
            try:
                resolved_skill_file.relative_to(root)
            except ValueError as exc:
                msg = f"Skill file escapes configured skill root: {skill_file}"
                raise SkillValidationError(msg) from exc
            skills.append(self.validate_skill(resolved_skill_file.parent))
        return skills

    def _core_skills_dir(self) -> Path:
        configured = self._settings.deepagents_core_skills_dir
        if configured.exists():
            return configured
        return Path(__file__).resolve().parent / "skills" / "core"


def _parse_frontmatter(content: str) -> dict[str, Any]:
    if not content.startswith("---\n"):
        msg = "Skill file must start with YAML frontmatter."
        raise SkillValidationError(msg)
    try:
        _, raw_frontmatter, _ = content.split("---", 2)
    except ValueError as exc:
        msg = "Skill file has invalid frontmatter delimiters."
        raise SkillValidationError(msg) from exc
    parsed: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in raw_frontmatter.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.startswith("  - ") and current_list_key is not None:
            value = line.removeprefix("  - ").strip()
            existing = parsed.setdefault(current_list_key, [])
            if isinstance(existing, list):
                existing.append(value)
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            parsed[key] = value
            current_list_key = None
        else:
            parsed[key] = []
            current_list_key = key
    return parsed


def _safe_child_dir(root: Path, child: str) -> Path | None:
    child_path = Path(child)
    if child_path.is_absolute() or any(part in {"", ".", ".."} for part in child_path.parts):
        return None
    if len(child_path.parts) != 1:
        return None
    root_resolved = root.resolve()
    candidate = (root_resolved / child_path).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    return candidate

from __future__ import annotations

from pathlib import Path

import pytest

from cognitive_os.core.config import Settings
from cognitive_os.deepagents.skills_registry import DeepAgentSkillsRegistry, SkillValidationError


def test_discovers_core_skills() -> None:
    skills = DeepAgentSkillsRegistry().discover_core_skills()

    names = {skill.name for skill in skills}

    assert "rag-research" in names
    assert "evidence-matrix" in names
    assert "sandbox-code-analysis" in names


def test_validates_frontmatter() -> None:
    skill = DeepAgentSkillsRegistry().validate_skill(
        Path("src/cognitive_os/deepagents/skills/core/evidence-matrix")
    )

    assert skill.name == "evidence-matrix"
    assert skill.allowed_tools == [
        "search_local_docs",
        "read_document_pages",
        "graph_query_readonly",
    ]


def test_blocks_skill_without_skill_md(tmp_path: Path) -> None:
    with pytest.raises(SkillValidationError, match="Skill file not found"):
        DeepAgentSkillsRegistry().validate_skill(tmp_path / "missing")


def test_blocks_skill_with_dangerous_tool(tmp_path: Path) -> None:
    skill_dir = tmp_path / "danger"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: danger
description: Bad skill.
version: 1.0.0
risk_level: high
allowed_tools:
  - shell
---
Nope.
""",
        encoding="utf-8",
    )

    with pytest.raises(SkillValidationError, match="dangerous tools"):
        DeepAgentSkillsRegistry().validate_skill(skill_dir)


def test_user_skill_discovery_rejects_path_traversal_user_id(tmp_path: Path) -> None:
    skill_dir = tmp_path / "shared"
    _write_skill(skill_dir, name="shared")
    registry = DeepAgentSkillsRegistry(
        Settings(deepagents_user_skills_dir=tmp_path, _env_file=None)
    )

    assert registry.discover_user_skills("../shared") == []


def test_discovery_blocks_symlinked_skill_files_that_escape_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _write_skill(outside, name="outside")
    root = tmp_path / "root"
    skill_dir = root / "linked"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").symlink_to(outside / "SKILL.md")
    registry = DeepAgentSkillsRegistry(Settings(deepagents_user_skills_dir=root, _env_file=None))

    with pytest.raises(SkillValidationError, match="escapes configured skill root"):
        registry.discover_user_skills(None)


def _write_skill(skill_dir: Path, *, name: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"""---
name: {name}
description: Safe skill.
version: 1.0.0
risk_level: read_only
allowed_tools:
  - search_local_docs
---
Safe.
""",
        encoding="utf-8",
    )

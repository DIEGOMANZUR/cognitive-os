"""Fase 42: legal-pack skills ported from claude-for-legal (Apache 2.0).

Five new skills land in `skills/core/` adapting structured patterns
from Anthropic's claude-for-legal repo. They must register cleanly,
declare only allow-listed tools, and have a known risk-level so the
existing approval/HITL pipeline can keep them under control.
"""

from __future__ import annotations

from pathlib import Path

from cognitive_os.deepagents.skills_registry import (
    ALLOWED_SKILL_TOOLS,
    DeepAgentSkillsRegistry,
)

_NEW_SKILLS = {
    "legal-hold",
    "privilege-log-review",
    "oss-license-review",
    "worker-classification",
    "matter-intake",
}


def test_legal_pack_skills_are_discovered() -> None:
    names = {s.name for s in DeepAgentSkillsRegistry().discover_core_skills()}
    missing = _NEW_SKILLS - names
    assert not missing, f"missing legal-pack skills: {missing}"


def test_legal_pack_skills_have_safe_tools() -> None:
    skills = {s.name: s for s in DeepAgentSkillsRegistry().discover_core_skills()}
    for slug in _NEW_SKILLS:
        s = skills[slug]
        # Every declared tool must be on the allowlist (never dangerous).
        unknown = set(s.allowed_tools) - ALLOWED_SKILL_TOOLS
        assert not unknown, f"{slug} declares non-allowlisted tools: {unknown}"


def test_legal_pack_skills_risk_levels() -> None:
    """Each skill picks the right risk level so the registry enables it."""
    skills = {s.name: s for s in DeepAgentSkillsRegistry().discover_core_skills()}
    expected: dict[str, str] = {
        # Pure analysis → read_only.
        "privilege-log-review": "read_only",
        "oss-license-review": "read_only",
        "worker-classification": "read_only",
        # Produce an artifact ready for HumanApproval before any write.
        "legal-hold": "approval_required",
        "matter-intake": "approval_required",
    }
    for slug, expected_risk in expected.items():
        assert skills[slug].risk_level == expected_risk, slug
        assert skills[slug].enabled, slug


def test_legal_pack_attribution_notice_present() -> None:
    """Apache 2.0 attribution is preserved alongside the skills."""
    notice = (
        Path(__file__).resolve().parent.parent / "src/cognitive_os/deepagents/skills/core/NOTICE.md"
    )
    assert notice.is_file()
    body = notice.read_text(encoding="utf-8")
    assert "Apache" in body
    assert "claude-for-legal" in body
    for slug in _NEW_SKILLS:
        assert f"`{slug}/`" in body, f"NOTICE.md does not list {slug}"


def test_legal_pack_skills_do_not_disable_existing() -> None:
    """Adding the pack must not shadow or drop any pre-existing skill."""
    names = {s.name for s in DeepAgentSkillsRegistry().discover_core_skills()}
    for legacy in (
        "citation-discipline",
        "contradiction-detector",
        "evidence-matrix",
        "legal-draft-careful",
        "rag-research",
        "report-writer",
        "sandbox-code-analysis",
        "timeline-builder",
    ):
        assert legacy in names

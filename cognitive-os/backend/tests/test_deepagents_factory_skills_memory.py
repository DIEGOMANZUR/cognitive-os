from __future__ import annotations

from pathlib import Path
from typing import Any

from cognitive_os.deepagents.factory import create_controlled_deep_agent
from cognitive_os.deepagents.schemas import DeepAgentTask, DeepAgentToolPolicy, DeepAgentWorkspace
from cognitive_os.deepagents.skills_registry import DeepAgentSkillsRegistry
from cognitive_os.deepagents.tools import build_deepagent_tools


def _task() -> DeepAgentTask:
    return DeepAgentTask(
        task_id="task-1",
        thread_id="thread-1",
        user_id="user-1",
        task_type="research",
        query="question",
    )


def _policy() -> DeepAgentToolPolicy:
    return DeepAgentToolPolicy()


def test_create_controlled_deep_agent_receives_skills_paths(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_create_deep_agent(
        model: object | None = None,
        tools: object | None = None,
        *,
        system_prompt: str | None = None,
        skills: list[str] | None = None,
        memory: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured.update(
            {
                "model": model,
                "tools": tools,
                "system_prompt": system_prompt,
                "skills": skills,
                "memory": memory,
                "kwargs": kwargs,
            }
        )
        return captured

    monkeypatch.setattr("cognitive_os.deepagents.factory.create_agent_chat_model", lambda: "llm")
    monkeypatch.setattr("cognitive_os.deepagents.factory.create_deep_agent", fake_create_deep_agent)

    create_controlled_deep_agent(
        _task(),
        _policy(),
        DeepAgentWorkspace(root_dir=tmp_path, thread_id="thread-1", task_id="task-1"),
        system_prompt="system",
        skills_paths=["/skills/rag-research"],
        memory_paths=["/memory/AGENTS.md"],
    )

    assert captured["skills"] == ["/skills/rag-research"]
    assert captured["memory"] == ["/memory/AGENTS.md"]


def test_startup_memory_is_injected(tmp_path: Path, monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_create_deep_agent(
        *,
        memory: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured.update(kwargs)
        captured["memory"] = memory
        return captured

    monkeypatch.setattr("cognitive_os.deepagents.factory.create_agent_chat_model", lambda: "llm")
    monkeypatch.setattr("cognitive_os.deepagents.factory.create_deep_agent", fake_create_deep_agent)

    create_controlled_deep_agent(
        _task(),
        _policy(),
        DeepAgentWorkspace(root_dir=tmp_path, thread_id="thread-1", task_id="task-1"),
        system_prompt="system",
        startup_memory="Remember: cite everything.",
    )

    assert "Remember: cite everything." in captured["system_prompt"]
    assert captured["memory"] == ["./.cognitive_os/AGENTS.md"]
    memory_file = tmp_path / ".cognitive_os" / "AGENTS.md"
    assert memory_file.exists()
    assert "Remember: cite everything." in memory_file.read_text(encoding="utf-8")


def test_create_controlled_deep_agent_receives_safe_subagents(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_create_deep_agent(
        *,
        subagents: list[Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured.update(kwargs)
        captured["subagents"] = subagents
        return captured

    monkeypatch.setattr("cognitive_os.deepagents.factory.create_agent_chat_model", lambda: "llm")
    monkeypatch.setattr("cognitive_os.deepagents.factory.create_deep_agent", fake_create_deep_agent)

    create_controlled_deep_agent(
        _task(),
        _policy(),
        DeepAgentWorkspace(root_dir=tmp_path, thread_id="thread-1", task_id="task-1"),
        system_prompt="system",
        skills_paths=["/skills/rag-research"],
    )

    names = {subagent["name"] for subagent in captured["subagents"]}
    assert {"local-rag-researcher", "citation-auditor"}.issubset(names)
    assert "web-researcher" not in names
    for subagent in captured["subagents"]:
        assert subagent["interrupt_on"]["execute"] is True
        assert subagent["skills"] == ["/skills/rag-research"]
        assert subagent["permissions"]


def test_create_controlled_deep_agent_can_disable_subagents_per_task(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_create_deep_agent(
        *,
        subagents: list[Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured.update(kwargs)
        if subagents is not None:
            captured["subagents"] = subagents
        return captured

    task = _task().model_copy(update={"metadata": {"enable_subagents": False}})
    monkeypatch.setattr("cognitive_os.deepagents.factory.create_agent_chat_model", lambda: "llm")
    monkeypatch.setattr("cognitive_os.deepagents.factory.create_deep_agent", fake_create_deep_agent)

    create_controlled_deep_agent(
        task,
        _policy(),
        DeepAgentWorkspace(root_dir=tmp_path, thread_id="thread-1", task_id="task-1"),
        system_prompt="system",
    )

    assert "subagents" not in captured


def test_core_skills_are_read_only_or_approval_gated() -> None:
    skills = DeepAgentSkillsRegistry().discover_core_skills()

    for skill in skills:
        assert skill.risk_level in {"read_only", "approval_required"}


def test_no_direct_memory_update_tool_exists(tmp_path: Path) -> None:
    tools = build_deepagent_tools(
        policy=_policy(),
        workspace=DeepAgentWorkspace(root_dir=tmp_path, thread_id="thread-1", task_id="task-1"),
    )
    names = {tool.name for tool in tools}

    assert "propose_memory_update" in names
    assert "write_memory" not in names
    assert "edit_memory" not in names

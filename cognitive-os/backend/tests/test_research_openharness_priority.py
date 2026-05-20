"""OpenHarness short-circuit before DeepAgents when enabled (fusion path)."""

from __future__ import annotations

import pytest

from cognitive_os.agents.graph import initial_state, research_node
from cognitive_os.core.config import settings
from cognitive_os.integrations.openharness_research import (
    OpenHarnessResearchResult,
    run_openharness_research_sync,
)


def test_build_research_user_message_includes_openharness_prelude() -> None:
    from cognitive_os.deepagents.research_deepagent import build_research_user_message_content
    from cognitive_os.deepagents.schemas import DeepAgentTask

    task = DeepAgentTask(
        task_id="x-research",
        thread_id="x",
        task_type="research",
        query="¿Hay evidencia?",
        metadata={"openharness_prelude": "  nota rápida  "},
    )
    content = build_research_user_message_content(task)
    assert "nota rápida" in content
    assert content.startswith("Preludio de OpenHarness")


def test_openharness_empty_query_skipped() -> None:
    cfg = settings.model_copy(update={"enable_openharness_research": True})
    out = run_openharness_research_sync(cfg, "  \t  ")
    # Either skip reason is acceptable: `empty_query` is reached only when
    # the `openharness-ai` extra is installed; otherwise the check short-
    # circuits earlier on `openharness_not_installed`. Both keep us from
    # actually invoking OH on an empty query, which is what this test cares
    # about.
    assert out.skipped_reason in {"empty_query", "openharness_not_installed"}
    assert not out.ok


def test_research_node_uses_openharness_before_deepagent(monkeypatch: pytest.MonkeyPatch) -> None:
    harness_answer = "respuesta-solo-openharness"

    def fake_run(s, msg: str, **kwargs: object) -> OpenHarnessResearchResult:  # noqa: ARG001
        assert msg.strip() == "pizza"
        return OpenHarnessResearchResult(ok=True, answer=harness_answer)

    def must_not_run(_task):  # noqa: ANN001
        raise AssertionError("DeepAgent runner must not run when OpenHarness succeeds")

    patched_settings = settings.model_copy(
        update={
            "enable_openharness_research": True,
            "openharness_research_pipeline": "short_circuit",
        }
    )
    monkeypatch.setattr("cognitive_os.agents.graph.settings", patched_settings)
    monkeypatch.setattr(
        "cognitive_os.integrations.openharness_research.run_openharness_research_sync",
        fake_run,
    )
    monkeypatch.setattr(
        "cognitive_os.integrations.openharness_research.is_openharness_available",
        lambda: True,
    )

    state = initial_state("pizza", thread_id="thread-oh")
    result = research_node(state, deepagent_runner=must_not_run)
    agent = result.get("agent_result")
    assert agent is not None
    assert agent.content == harness_answer
    assert agent.route == "research"


def test_research_node_prelude_merge_stashes_openharness_in_task_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathlib import Path

    prelude_text = "apuntes-de-openharness"
    patched_settings = settings.model_copy(
        update={
            "enable_openharness_research": True,
            "openharness_research_pipeline": "prelude_merge",
        }
    )

    def fake_run(
        cfg,  # noqa: ANN001, ARG001
        msg: str,
        *,
        workspace_root,
        thread_id: str | None,
        task_id: str | None,
        web_allowed: bool,
    ) -> OpenHarnessResearchResult:
        assert msg.strip() == "queso"
        assert thread_id == "thr1"
        assert task_id == "thr1-research"
        assert web_allowed is patched_settings.web_search_enabled
        expected_ws = (
            Path(patched_settings.local_storage_dir).resolve()
            / "workspaces"
            / "thr1"
            / "thr1-research"
        )
        assert workspace_root.resolve() == expected_ws
        return OpenHarnessResearchResult(ok=True, answer=prelude_text)

    captured: dict[str, object] = {}

    def runner(task):  # noqa: ANN001
        captured["meta"] = dict(task.metadata)
        from cognitive_os.deepagents.schemas import DeepAgentResult

        return DeepAgentResult(
            task_id=task.task_id,
            thread_id=task.thread_id,
            status="ok",
            answer="respuesta deep",
            findings=[],
            citations=[],
            uncertainty_notes=[],
            generated_files=[],
            requested_external_actions=[],
            raw_summary=None,
        )

    monkeypatch.setattr("cognitive_os.agents.graph.settings", patched_settings)
    monkeypatch.setattr(
        "cognitive_os.integrations.openharness_research.run_openharness_research_sync",
        fake_run,
    )
    monkeypatch.setattr(
        "cognitive_os.integrations.openharness_research.is_openharness_available",
        lambda: True,
    )

    state = initial_state("queso", thread_id="thr1")
    research_node(state, deepagent_runner=runner)
    meta = captured.get("meta", {})
    assert meta.get("openharness_prelude") == prelude_text

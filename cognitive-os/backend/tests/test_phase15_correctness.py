"""Regression tests for Phase 15 correctness/security fixes.

Each test pins a specific bug from the audit so future refactors cannot silently
revert the fix. Numbering matches the audit punch list:

- Bug #1: `computer_organize` executes the approved plan, not a re-scan.
- Bug #2: `_execute` uses `payload_executable` (unredacted) when available.
- Bug #3: `research_node` triggers fallback when DeepAgent returns empty answer.
- Bug #5: `execute_action_request` is atomic — double dispatch is a no-op.
- Bug #6: `read_document_pages` enforces the task's `allowed_doc_ids`.
- Bug #8: `search_local_docs` excludes web-indexed snippets by default.
- Bug #10: failed/blocked DeepAgent tool calls are audited (not only successes).
- Bug #20: citations render basename, never an absolute filesystem path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cognitive_os.actions.computer import ComputerActionService
from cognitive_os.actions.schemas import (
    ComputerOrganizePlan,
    FileMovePreview,
)
from cognitive_os.agents.graph import research_node
from cognitive_os.agents.state import (
    AgentResult,
    BudgetState,
    CognitiveState,
    RetrievalCitation,
    ToolPolicy,
)
from cognitive_os.core.config import Settings
from cognitive_os.deepagents.policies import DeepAgentPolicyViolation
from cognitive_os.deepagents.schemas import (
    DeepAgentResult,
    DeepAgentTask,
    DeepAgentToolPolicy,
    DeepAgentWorkspace,
)
from cognitive_os.deepagents.tools import (
    build_deepagent_tools,
    read_document_pages,
    search_local_docs,
    search_web,
)
from cognitive_os.memory.retrieval import RetrievedContext

# ---------------------------------------------------------------------------
# Bug #1: computer_organize executes the approved plan, not a re-scan
# ---------------------------------------------------------------------------


def test_execute_approved_plan_runs_only_the_supplied_operations(tmp_path: Path) -> None:
    # Create one file inside the approved plan...
    (tmp_path / "approved.pdf").write_bytes(b"x")
    # ...and one file the operator never saw (created between preview and dispatch).
    (tmp_path / "stowaway.png").write_bytes(b"y")

    plan = ComputerOrganizePlan(
        status="ok",
        root_path=str(tmp_path),
        dry_run_only=False,
        requires_approval=True,
        operations=[
            FileMovePreview(
                source="approved.pdf",
                destination="PDFs/approved.pdf",
                category="PDFs",
                reason="approved",
            )
        ],
    )
    service = ComputerActionService(
        Settings(
            _env_file=None,
            enable_computer_actions=True,
            computer_allowed_roots=str(tmp_path),
            computer_organize_dry_run_only=False,
        )
    )

    result = service.execute_approved_plan(plan)

    assert result.status == "completed"
    assert result.moved_count == 1
    # The new "stowaway" file must NOT have been moved — it was never approved.
    assert (tmp_path / "stowaway.png").exists()
    assert not (tmp_path / "Images" / "stowaway.png").exists()
    # The approved file moved to its approved destination.
    assert (tmp_path / "PDFs" / "approved.pdf").exists()


def test_execute_approved_plan_blocks_when_dry_run_only(tmp_path: Path) -> None:
    plan = ComputerOrganizePlan(
        status="ok",
        root_path=str(tmp_path),
        dry_run_only=True,
        requires_approval=True,
        operations=[],
    )
    service = ComputerActionService(
        Settings(
            _env_file=None,
            enable_computer_actions=True,
            computer_allowed_roots=str(tmp_path),
            computer_organize_dry_run_only=True,
        )
    )
    result = service.execute_approved_plan(plan)
    assert result.status == "blocked"
    assert "dry-run only" in (result.reason or "")


def test_execute_approved_plan_revalidates_each_move(tmp_path: Path) -> None:
    """An operation whose source no longer exists is reported, not blindly applied."""
    (tmp_path / "kept.pdf").write_bytes(b"x")
    plan = ComputerOrganizePlan(
        status="ok",
        root_path=str(tmp_path),
        dry_run_only=False,
        requires_approval=True,
        operations=[
            FileMovePreview(
                source="kept.pdf",
                destination="PDFs/kept.pdf",
                category="PDFs",
                reason="approved",
            ),
            FileMovePreview(
                source="vanished.pdf",
                destination="PDFs/vanished.pdf",
                category="PDFs",
                reason="approved before deletion",
            ),
        ],
    )
    service = ComputerActionService(
        Settings(
            enable_computer_actions=True,
            computer_allowed_roots=str(tmp_path),
            computer_organize_dry_run_only=False,
        )
    )

    result = service.execute_approved_plan(plan)

    assert result.status == "failed"
    statuses = {op.source: op.status for op in result.operations}
    assert statuses["kept.pdf"] == "moved"
    assert statuses["vanished.pdf"] == "failed"


# ---------------------------------------------------------------------------
# Bug #3: research_node falls back when DeepAgent returns empty answer
# ---------------------------------------------------------------------------


def _empty_runner(task: DeepAgentTask) -> DeepAgentResult:
    return DeepAgentResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="ok",
        answer="   ",  # status ok but no actual content
        findings=[],
        citations=[],
        uncertainty_notes=[],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=None,
    )


def test_research_node_falls_back_when_deepagent_returns_empty_answer() -> None:
    """status="ok" with a whitespace-only answer must NOT be returned as success."""

    class _StubAgent:
        def run(self, query: str, *, retrieved_context: object = None) -> object:
            del query, retrieved_context

            class _Report:
                answer = "RAG fallback answered."
                citations: list[object] = []
                uncertainty_notes: list[str] = []

                def model_dump(self) -> dict[str, object]:
                    return {"answer": self.answer}

            return _Report()

    state: CognitiveState = {
        "messages": [],
        "thread_id": "t1",
        "user_id": "u1",
        "budget": BudgetState(),
        "tool_policy": ToolPolicy(),
        "error_count": 0,
    }
    result = research_node(state, research_agent=_StubAgent(), deepagent_runner=_empty_runner)  # type: ignore[arg-type]
    agent_result = result["agent_result"]
    assert isinstance(agent_result, AgentResult)
    # Must surface the fallback message, not the empty deepagent answer.
    assert "RAG fallback" in agent_result.content
    assert "empty answer" in agent_result.content


def _needs_more_info_runner(task: DeepAgentTask) -> DeepAgentResult:
    return DeepAgentResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="needs_more_info",
        answer="Necesito mas evidencia: adjunte el contrato.",
        findings=[],
        citations=[],
        uncertainty_notes=["incomplete inputs"],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=None,
    )


def test_research_node_surfaces_needs_more_info_with_uncertainty() -> None:
    """A non-empty needs_more_info answer is shown to the user but marked uncertain."""
    state: CognitiveState = {
        "messages": [],
        "thread_id": "t2",
        "user_id": "u1",
        "budget": BudgetState(),
        "tool_policy": ToolPolicy(),
        "error_count": 0,
    }
    result = research_node(state, deepagent_runner=_needs_more_info_runner)
    agent_result = result["agent_result"]
    assert isinstance(agent_result, AgentResult)
    assert "adjunte el contrato" in agent_result.content
    assert agent_result.uncertainty is not None
    assert "needs_more_info" in agent_result.uncertainty


# ---------------------------------------------------------------------------
# Bug #6: read_document_pages enforces allowed_doc_ids
# ---------------------------------------------------------------------------


def test_read_document_pages_rejects_doc_id_outside_allowlist() -> None:
    allowed = ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]
    result = read_document_pages(
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        1,
        2,
        policy=DeepAgentToolPolicy(),
        allowed_doc_ids=allowed,
    )
    assert result["error"] == "doc_id_not_authorized"
    assert result["pages"] == []


def test_read_document_pages_rejects_when_allowlist_is_empty() -> None:
    """Empty/None allowed list must mean "no doc readable" (default deny)."""
    result = read_document_pages(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        1,
        2,
        policy=DeepAgentToolPolicy(),
        allowed_doc_ids=[],
    )
    assert result["error"] == "doc_id_not_authorized"


def test_build_deepagent_tools_threads_allowed_doc_ids(tmp_path: Path) -> None:
    """The factory must thread the task's allowed_doc_ids into read_document_pages."""
    workspace = DeepAgentWorkspace(root_dir=tmp_path, thread_id="t", task_id="tk")
    policy = DeepAgentToolPolicy()
    tools = build_deepagent_tools(
        policy=policy,
        workspace=workspace,
        allowed_doc_ids=["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
    )
    read_tool = next(tool for tool in tools if tool.name == "read_document_pages")
    # Calling with an unauthorized doc_id returns the controlled error.
    response = read_tool.invoke(
        {
            "doc_id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "page_start": 1,
            "page_end": 2,
        }
    )
    assert response["error"] == "doc_id_not_authorized"


# ---------------------------------------------------------------------------
# Bug #8: search_local_docs excludes doc_type=web by default
# ---------------------------------------------------------------------------


def test_search_local_docs_passes_exclude_web_to_retriever() -> None:
    captured: dict[str, object] = {}

    def fake_retriever(
        query: str,
        *,
        exclude_doc_types: tuple[str, ...] = (),
    ) -> list[RetrievedContext]:
        captured["query"] = query
        captured["exclude_doc_types"] = exclude_doc_types
        return [
            RetrievedContext(
                text="local doc text",
                citation="local.pdf:1-1",
                score=0.9,
                metadata={
                    "doc_id": "d1",
                    "chunk_id": "c1",
                    "page_start": 1,
                    "page_end": 1,
                    "doc_type": "pdf",
                },
            )
        ]

    response = search_local_docs(
        "what is X",
        policy=DeepAgentToolPolicy(),
        local_retriever=fake_retriever,
    )
    assert captured["exclude_doc_types"] == ("web",)
    assert response["results"][0]["doc_type"] == "pdf"
    assert response["citations"][0]["source_type"] == "local_doc"


def test_search_local_docs_falls_back_when_retriever_rejects_kwarg() -> None:
    """Legacy retrievers without `exclude_doc_types` kwarg must still work."""

    def legacy_retriever(query: str) -> list[RetrievedContext]:
        del query
        return [
            RetrievedContext(
                text="legacy doc",
                citation="legacy.pdf:1-1",
                score=0.5,
                metadata={"doc_id": "d1", "chunk_id": "c1"},
            )
        ]

    response = search_local_docs(
        "legacy",
        policy=DeepAgentToolPolicy(),
        local_retriever=legacy_retriever,
    )
    assert response["results"][0]["doc_id"] == "d1"


# ---------------------------------------------------------------------------
# Bug #10: errors and blocks are audited (not only success)
# ---------------------------------------------------------------------------


def test_controlled_error_records_audit_event(monkeypatch: pytest.MonkeyPatch) -> None:
    from cognitive_os.deepagents import tools as tools_module

    captured: list[object] = []

    def fake_recorder(record: object) -> None:
        captured.append(record)

    monkeypatch.setattr(tools_module, "record_audit_event", fake_recorder)

    # Trigger a policy violation: search_web requires allow_web=True.
    result = search_web("query", policy=DeepAgentToolPolicy(allow_web=False))
    assert result["error"] == "policy_violation"
    assert captured, "audit recorder must be called for policy violations"
    record = captured[0]
    assert getattr(record, "tool_name", "") == "deepagents.search_web"
    assert "error" in (getattr(record, "result_summary", "") or "")


def test_search_web_disabled_audits_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabled web search must also be audited (it is a soft block, not just OK)."""
    from cognitive_os.core import config as config_module
    from cognitive_os.deepagents import tools as tools_module

    captured: list[object] = []
    monkeypatch.setattr(
        tools_module,
        "record_audit_event",
        lambda record: captured.append(record),
    )
    monkeypatch.setattr(config_module.settings, "web_search_enabled", False, raising=False)

    result = search_web("query", policy=DeepAgentToolPolicy(allow_web=True))
    assert result["error"] == "web_search_disabled"
    assert captured, "soft block must be audited"
    assert "web_search_disabled" in (getattr(captured[0], "result_summary", "") or "")


# ---------------------------------------------------------------------------
# Bug #20: citations never leak absolute paths
# ---------------------------------------------------------------------------


def test_retrieval_citation_uses_basename_not_absolute_path() -> None:
    citation = RetrievalCitation(
        source_path="/var/data/cases/2026/contract.pdf",
        page_start=4,
        page_end=5,
        doc_id="doc-1",
        chunk_id="chunk-1",
    )
    rendered = citation.citation
    assert "/var/data/cases/2026" not in rendered
    assert "contract.pdf:4-5" in rendered
    assert "doc_id=doc-1" in rendered
    assert "chunk_id=chunk-1" in rendered


def test_retrieval_citation_prefers_title_over_basename() -> None:
    citation = RetrievalCitation(
        source_path="/var/data/cases/2026/contract.pdf",
        page_start=4,
        page_end=5,
        title="Contrato 2026 - Resumen Ejecutivo",
        doc_id="doc-1",
    )
    rendered = citation.citation
    assert rendered.startswith("Contrato 2026 - Resumen Ejecutivo")
    assert "/var/data" not in rendered


def test_retrieval_citation_handles_windows_paths() -> None:
    # Single-backslash Windows path (as Windows itself would produce).
    citation = RetrievalCitation(
        source_path="C:\\Users\\Cognitive\\docs\\report.pdf",
        page_start=1,
        page_end=1,
    )
    rendered = citation.citation
    assert "C:\\" not in rendered, f"drive prefix leaked: {rendered}"
    assert "Users" not in rendered, f"intermediate folder leaked: {rendered}"
    assert rendered.startswith("report.pdf:1-1")


# ---------------------------------------------------------------------------
# Bug #6 sanity: the policy violation path itself still works (existing tests)
# ---------------------------------------------------------------------------


def test_search_local_docs_blocked_when_policy_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cognitive_os.deepagents import tools as tools_module

    captured: list[object] = []
    monkeypatch.setattr(
        tools_module,
        "record_audit_event",
        lambda record: captured.append(record),
    )
    result = search_local_docs(
        "blocked query",
        policy=DeepAgentToolPolicy(allow_local_rag=False),
    )
    assert result["error"] == "policy_violation"
    assert captured, "the policy violation must show up in the audit log"
    record = captured[0]
    assert "policy_violation" in (getattr(record, "result_summary", "") or "")
    # The exception remains a controlled type, never bubbling up to the agent loop.
    with pytest.raises(DeepAgentPolicyViolation):
        from cognitive_os.deepagents.policies import validate_tool_allowed

        validate_tool_allowed("search_local_docs", DeepAgentToolPolicy(allow_local_rag=False))

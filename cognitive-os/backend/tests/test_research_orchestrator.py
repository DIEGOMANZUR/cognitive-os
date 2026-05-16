from __future__ import annotations

import time

import httpx
import pytest

import cognitive_os.api.app as api_app
from cognitive_os.agents.research_orchestrator import (
    FakePlanner,
    FakeResearcher,
    FakeScorer,
    FakeSynthesizer,
    HeuristicScorer,
    HeuristicSynthesizer,
    ResearchOrchestrator,
    ResearchRun,
    ResearchRunRequest,
    ResearchSubtask,
    ResearchSynthesis,
    ScoreResult,
)
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import settings as _settings
from cognitive_os.deepagents.schemas import DeepAgentCitation, DeepAgentResult, DeepAgentTask


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


class _FakeResearchRunStore:
    def __init__(self) -> None:
        self.saved: dict[str, ResearchRun] = {}
        self.save_count = 0

    def save_run(self, run: ResearchRun) -> None:
        self.saved[run.run_id] = run
        self.save_count += 1

    def get_run(self, run_id: str) -> ResearchRun | None:
        return self.saved.get(run_id)

    def list_runs(self, *, limit: int = 50) -> list[ResearchRun]:
        return list(self.saved.values())[:limit]


def _fake_result(
    task_id: str, *, status: str = "ok", with_citation: bool = True
) -> DeepAgentResult:
    citations = (
        [
            DeepAgentCitation(
                source_type="local_doc",
                doc_id=f"doc-{task_id}",
                chunk_id=f"chunk-{task_id}",
                page_start=1,
                page_end=1,
                quote="evidence snippet",
            )
        ]
        if with_citation
        else []
    )
    return DeepAgentResult(
        task_id=task_id,
        thread_id="thread",
        status=status,  # type: ignore[arg-type]
        answer=f"answer for {task_id}",
        findings=[f"finding-{task_id}-a", f"finding-{task_id}-b"],
        citations=citations,
        uncertainty_notes=[f"limit-{task_id}"],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=None,
    )


def test_orchestrator_full_pipeline_with_fakes() -> None:
    subtasks = [
        ResearchSubtask(subtask_id="st-1", query="q1"),
        ResearchSubtask(subtask_id="st-2", query="q2"),
    ]
    results = {
        "st-1": _fake_result("st-1"),
        "st-2": _fake_result("st-2"),
    }
    orchestrator = ResearchOrchestrator(
        planner=FakePlanner(subtasks),
        researcher=FakeResearcher(results),
        synthesizer=HeuristicSynthesizer(),
        scorer=HeuristicScorer(),
    )
    started = orchestrator.start_run(
        ResearchRunRequest(query="test", time_budget_seconds=10, max_subtasks=2)
    )
    run = orchestrator.wait_for_run(started.run_id, timeout=10.0)
    assert run is not None
    assert run.status == "completed"
    assert len(run.subtasks) == 2
    assert len(run.results) == 2
    assert all(r.status == "ok" for r in run.results)
    assert run.synthesis is not None
    assert run.synthesis.citations, "synthesis must keep citations"
    assert run.score is not None
    assert 0.0 <= run.score.score <= 1.0
    assert run.score.rubric["completion"] == 1.0


def test_orchestrator_persists_run_snapshots_to_store() -> None:
    store = _FakeResearchRunStore()
    subtasks = [ResearchSubtask(subtask_id="st-1", query="q1")]
    orchestrator = ResearchOrchestrator(
        planner=FakePlanner(subtasks),
        researcher=FakeResearcher({"st-1": _fake_result("st-1")}),
        store=store,
    )

    started = orchestrator.start_run(
        ResearchRunRequest(query="persist me", time_budget_seconds=5, max_subtasks=1)
    )
    run = orchestrator.wait_for_run(started.run_id, timeout=10.0)

    assert run is not None
    assert store.save_count >= 2
    assert store.get_run(started.run_id) is run


def test_orchestrator_hydrates_run_from_store_when_memory_is_empty() -> None:
    store = _FakeResearchRunStore()
    first = ResearchOrchestrator(
        planner=FakePlanner([ResearchSubtask(subtask_id="st-1", query="q1")]),
        researcher=FakeResearcher({"st-1": _fake_result("st-1")}),
        store=store,
    )
    started = first.start_run(
        ResearchRunRequest(query="restore me", time_budget_seconds=5, max_subtasks=1)
    )
    first.wait_for_run(started.run_id, timeout=10.0)
    restored = ResearchOrchestrator(store=store)

    run = restored.get_run(started.run_id)

    assert run is not None
    assert run.run_id == started.run_id
    assert restored.list_runs(limit=10)


def test_orchestrator_blocks_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_settings, "enable_research_orchestrator", False)
    orchestrator = ResearchOrchestrator()
    with pytest.raises(Exception) as exc:
        orchestrator.start_run(ResearchRunRequest(query="hello"))
    assert "disabled" in str(exc.value).lower()


def test_orchestrator_reports_failed_subtask_via_uncertainty() -> None:
    subtasks = [
        ResearchSubtask(subtask_id="st-1", query="q1"),
        ResearchSubtask(subtask_id="st-2", query="q2"),
    ]
    results = {
        "st-1": _fake_result("st-1"),
        "st-2": _fake_result("st-2", status="blocked", with_citation=False),
    }
    orchestrator = ResearchOrchestrator(
        planner=FakePlanner(subtasks),
        researcher=FakeResearcher(results),
    )
    started = orchestrator.start_run(
        ResearchRunRequest(query="test", time_budget_seconds=10, max_subtasks=2)
    )
    run = orchestrator.wait_for_run(started.run_id, timeout=10.0)
    assert run is not None
    statuses = {r.status for r in run.results}
    assert "blocked" in statuses
    assert run.score is not None
    assert run.score.rubric["no_failed"] < 1.0


def test_orchestrator_emits_events_in_order() -> None:
    subtasks = [ResearchSubtask(subtask_id="st-1", query="q1")]
    results = {"st-1": _fake_result("st-1")}
    orchestrator = ResearchOrchestrator(
        planner=FakePlanner(subtasks),
        researcher=FakeResearcher(results),
    )
    started = orchestrator.start_run(
        ResearchRunRequest(query="test", time_budget_seconds=5, max_subtasks=1)
    )
    run = orchestrator.wait_for_run(started.run_id, timeout=10.0)
    assert run is not None
    kinds = [e.kind for e in run.events]
    assert kinds[0] == "run_started"
    assert "plan_ready" in kinds
    assert "subtask_started" in kinds
    assert "subtask_finished" in kinds
    assert "synthesis_ready" in kinds
    assert "score_ready" in kinds
    assert kinds[-1] == "run_completed"


def test_orchestrator_subtask_timeout_marks_subtask_as_timeout() -> None:
    subtasks = [ResearchSubtask(subtask_id="st-1", query="q1")]
    results = {"st-1": _fake_result("st-1")}

    class SleepyResearcher:
        def __init__(self, base: FakeResearcher) -> None:
            self._base = base

        def run(self, task: DeepAgentTask) -> DeepAgentResult:
            time.sleep(10)
            return self._base.run(task)

    orchestrator = ResearchOrchestrator(
        planner=FakePlanner(subtasks),
        researcher=SleepyResearcher(FakeResearcher(results)),
    )
    started = orchestrator.start_run(
        ResearchRunRequest(query="x", time_budget_seconds=5, max_subtasks=1)
    )
    run = orchestrator.wait_for_run(started.run_id, timeout=10.0)
    assert run is not None
    assert run.status == "completed"
    assert len(run.results) == 1
    assert run.results[0].status == "timeout"


def test_orchestrator_cancel_sets_run_status() -> None:
    subtasks = [ResearchSubtask(subtask_id="st-1", query="q1")]
    results = {"st-1": _fake_result("st-1")}

    class SleepyResearcher:
        def __init__(self, base: FakeResearcher) -> None:
            self._base = base

        def run(self, task: DeepAgentTask) -> DeepAgentResult:
            time.sleep(0.5)
            return self._base.run(task)

    orchestrator = ResearchOrchestrator(
        planner=FakePlanner(subtasks),
        researcher=SleepyResearcher(FakeResearcher(results)),
    )
    started = orchestrator.start_run(
        ResearchRunRequest(query="long", time_budget_seconds=5, max_subtasks=1)
    )
    # start_run now returns immediately; the run executes on a daemon thread.
    time.sleep(0.05)
    cancelled = orchestrator.cancel_run(started.run_id)
    assert cancelled is not None
    final = orchestrator.wait_for_run(started.run_id, timeout=5.0)
    assert final is not None
    assert final.status in {"cancelled", "completed"}


def test_orchestrator_clamps_budget_and_subtasks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_settings, "research_max_time_budget_seconds", 30)
    monkeypatch.setattr(_settings, "research_max_subtasks", 2)
    orchestrator = ResearchOrchestrator(
        planner=FakePlanner([ResearchSubtask(subtask_id="st-1", query="q")]),
        researcher=FakeResearcher({"st-1": _fake_result("st-1")}),
    )
    started = orchestrator.start_run(
        ResearchRunRequest(query="x", time_budget_seconds=3600, max_subtasks=32)
    )
    assert started.request.time_budget_seconds == 30
    assert started.request.max_subtasks == 2
    orchestrator.wait_for_run(started.run_id, timeout=10.0)


def test_synthesizer_dedups_citations() -> None:
    subtasks = [
        ResearchSubtask(subtask_id="st-1", query="q1"),
        ResearchSubtask(subtask_id="st-2", query="q2"),
    ]
    shared = DeepAgentCitation(
        source_type="web",
        url="https://example.com/a",
        title="A",
        quote="x",
    )
    results = {
        "st-1": DeepAgentResult(
            task_id="st-1",
            thread_id="t",
            status="ok",
            answer="a1",
            findings=["dup"],
            citations=[shared],
            uncertainty_notes=[],
            generated_files=[],
            requested_external_actions=[],
        ),
        "st-2": DeepAgentResult(
            task_id="st-2",
            thread_id="t",
            status="ok",
            answer="a2",
            findings=["dup"],
            citations=[shared],
            uncertainty_notes=[],
            generated_files=[],
            requested_external_actions=[],
        ),
    }
    orchestrator = ResearchOrchestrator(
        planner=FakePlanner(subtasks),
        researcher=FakeResearcher(results),
    )
    started = orchestrator.start_run(
        ResearchRunRequest(query="test", time_budget_seconds=5, max_subtasks=2)
    )
    run = orchestrator.wait_for_run(started.run_id, timeout=10.0)
    assert run is not None
    assert run.synthesis is not None
    urls = [c.url for c in run.synthesis.citations]
    assert urls.count("https://example.com/a") == 1
    assert run.synthesis.findings.count("dup") == 1


@pytest.mark.asyncio
async def test_start_research_run_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    subtasks = [ResearchSubtask(subtask_id="st-1", query="q1")]
    results = {"st-1": _fake_result("st-1")}
    test_orchestrator = ResearchOrchestrator(
        planner=FakePlanner(subtasks),
        researcher=FakeResearcher(results),
    )
    monkeypatch.setattr(api_app, "_research_orchestrator", test_orchestrator)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/research/runs",
            json={"query": "test", "time_budget_seconds": 5, "max_subtasks": 1},
            headers=_headers(),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        run_id = body["run_id"]
        assert run_id.startswith("rr-")
        # Async start: status should be a non-terminal value initially; we then
        # wait for completion via the orchestrator and re-fetch the snapshot.
        test_orchestrator.wait_for_run(run_id, timeout=5.0)
        final = await client.get(f"/research/runs/{run_id}", headers=_headers())
    assert final.status_code == 200, final.text
    final_body = final.json()
    assert final_body["status"] == "completed"
    assert final_body["score"]["score"] >= 0.0


@pytest.mark.asyncio
async def test_get_and_list_and_cancel_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    subtasks = [ResearchSubtask(subtask_id="st-1", query="q1")]
    results = {"st-1": _fake_result("st-1")}
    test_orchestrator = ResearchOrchestrator(
        planner=FakePlanner(subtasks),
        researcher=FakeResearcher(results),
        synthesizer=FakeSynthesizer(
            ResearchSynthesis(
                answer="ok",
                findings=["one"],
                citations=[],
                uncertainty_notes=["note"],
                used_sources=[],
            )
        ),
        scorer=FakeScorer(ScoreResult(score=0.42, rubric={"x": 0.5}, reasons=["r"])),
    )
    monkeypatch.setattr(api_app, "_research_orchestrator", test_orchestrator)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start = await client.post(
            "/research/runs",
            json={"query": "q", "time_budget_seconds": 5, "max_subtasks": 1},
            headers=_headers(),
        )
        run_id = start.json()["run_id"]
        test_orchestrator.wait_for_run(run_id, timeout=5.0)
        listing = await client.get("/research/runs", headers=_headers())
        single = await client.get(f"/research/runs/{run_id}", headers=_headers())
        cancel = await client.post(f"/research/runs/{run_id}/cancel", headers=_headers())
        missing = await client.get("/research/runs/rr-missing", headers=_headers())
    assert listing.status_code == 200
    assert any(r["run_id"] == run_id for r in listing.json())
    assert single.status_code == 200
    assert single.json()["score"]["score"] == 0.42
    assert cancel.status_code == 200
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_start_research_run_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_settings, "enable_research_orchestrator", False)
    monkeypatch.setattr(api_app, "_research_orchestrator", ResearchOrchestrator())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/research/runs",
            json={"query": "test"},
            headers=_headers(),
        )
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"].lower()


def test_wait_for_run_returns_none_for_unknown_id() -> None:
    orchestrator = ResearchOrchestrator()
    assert orchestrator.wait_for_run("rr-missing", timeout=0.1) is None


def test_start_run_returns_immediately_with_non_terminal_status() -> None:
    """`start_run` must not block; the run should still be non-terminal."""
    subtasks = [ResearchSubtask(subtask_id="st-1", query="q1")]
    results = {"st-1": _fake_result("st-1")}

    class SlowResearcher:
        def __init__(self, base: FakeResearcher) -> None:
            self._base = base

        def run(self, task: DeepAgentTask) -> DeepAgentResult:
            time.sleep(0.3)
            return self._base.run(task)

    orchestrator = ResearchOrchestrator(
        planner=FakePlanner(subtasks),
        researcher=SlowResearcher(FakeResearcher(results)),
    )
    start_ts = time.monotonic()
    started = orchestrator.start_run(
        ResearchRunRequest(query="q", time_budget_seconds=5, max_subtasks=1)
    )
    elapsed = time.monotonic() - start_ts
    assert elapsed < 0.2, f"start_run blocked for {elapsed:.3f}s, expected <0.2s"
    # The run is still active; do not assume terminal state yet.
    assert started.status in {
        "queued",
        "planning",
        "researching",
        "synthesizing",
        "scoring",
    }
    final = orchestrator.wait_for_run(started.run_id, timeout=5.0)
    assert final is not None
    assert final.status == "completed"


@pytest.mark.asyncio
async def test_research_events_sse_endpoint_streams_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subtasks = [ResearchSubtask(subtask_id="st-1", query="q1")]
    results = {"st-1": _fake_result("st-1")}
    test_orchestrator = ResearchOrchestrator(
        planner=FakePlanner(subtasks),
        researcher=FakeResearcher(results),
    )
    monkeypatch.setattr(api_app, "_research_orchestrator", test_orchestrator)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start = await client.post(
            "/research/runs",
            json={"query": "stream me", "time_budget_seconds": 5, "max_subtasks": 1},
            headers=_headers(),
        )
        assert start.status_code == 200
        run_id = start.json()["run_id"]
        # Wait for terminal state so the SSE generator finishes promptly.
        test_orchestrator.wait_for_run(run_id, timeout=5.0)
        events: list[dict[str, object]] = []
        async with client.stream(
            "GET", f"/research/runs/{run_id}/events", headers=_headers()
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                import json as _json

                events.append(_json.loads(line.removeprefix("data: ")))
    kinds = [event["event"] for event in events]
    assert "run_started" in kinds
    assert "plan_ready" in kinds
    assert "subtask_started" in kinds
    assert "subtask_finished" in kinds
    assert "synthesis_ready" in kinds
    assert "score_ready" in kinds
    assert "run_completed" in kinds
    assert kinds[-2] == "snapshot"
    assert kinds[-1] == "done"
    snapshot = next(e for e in events if e["event"] == "snapshot")
    assert snapshot["payload"]["status"] == "completed"
    assert snapshot["payload"]["run_id"] == run_id


@pytest.mark.asyncio
async def test_research_events_sse_endpoint_404_for_unknown_run() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/research/runs/rr-does-not-exist/events", headers=_headers())
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_research_events_sse_endpoint_requires_authentication() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/research/runs/rr-any/events")
    assert response.status_code in (401, 403)

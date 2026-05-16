from __future__ import annotations

import json

import httpx
import pytest
from langgraph.checkpoint.memory import MemorySaver

import cognitive_os.api.app as api_app
from cognitive_os.agents.graph import build_graph
from cognitive_os.agents.research import ReadOnlyResearchTools, ResearchAgent
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.deepagents.schemas import DeepAgentResult, DeepAgentTask


class EmptyWebClient:
    def search(self, query: str) -> list[object]:  # noqa: ARG002
        return []


def _failed_runner(task: DeepAgentTask) -> DeepAgentResult:
    return DeepAgentResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="failed",
        answer="mocked",
        findings=[],
        citations=[],
        uncertainty_notes=["mocked"],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=None,
    )


@pytest.mark.asyncio
async def test_chat_stream_emits_sse_events(monkeypatch: pytest.MonkeyPatch) -> None:
    test_graph = build_graph(
        checkpointer=MemorySaver(),
        retriever=api_app._empty_retriever,
        research_agent=ResearchAgent(
            tools=ReadOnlyResearchTools(
                local_search=api_app._empty_retriever,
                web_client=EmptyWebClient(),
            )
        ),
        deepagent_runner=_failed_runner,
    )
    monkeypatch.setattr(api_app, "_api_graph", test_graph)
    headers = {"Authorization": f"Bearer {create_access_token(user_id='1')}"}
    transport = httpx.ASGITransport(app=app)

    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        client.stream(
            "POST",
            "/chat/stream",
            json={"message": "investiga algo"},
            headers=headers,
        ) as response,
    ):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        chunks: list[dict[str, object]] = []
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            chunks.append(json.loads(line.removeprefix("data: ")))

    events = [chunk["event"] for chunk in chunks]
    assert "thread_started" in events
    assert "node_update" in events
    assert "final_response" in events
    assert events[-1] == "done"
    final = next(chunk for chunk in chunks if chunk["event"] == "final_response")
    assert final["route"] == "research"


@pytest.mark.asyncio
async def test_chat_stream_emits_error_event_when_graph_stream_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingGraph:
        def stream(self, *_args: object, **_kwargs: object) -> object:
            raise RuntimeError("boom")

        def get_state(self, *_args: object, **_kwargs: object) -> object:
            return type("Snapshot", (), {"values": {}})()

    monkeypatch.setattr(api_app, "_api_graph", FailingGraph())
    headers = {"Authorization": f"Bearer {create_access_token(user_id='1')}"}
    transport = httpx.ASGITransport(app=app)

    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        client.stream(
            "POST",
            "/chat/stream",
            json={"message": "trigger failure"},
            headers=headers,
        ) as response,
    ):
        assert response.status_code == 200
        chunks: list[dict[str, object]] = []
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            chunks.append(json.loads(line.removeprefix("data: ")))

    events = [chunk["event"] for chunk in chunks]
    assert events == ["thread_started", "error", "done"]
    error = chunks[1]
    assert error["thread_id"] == chunks[0]["thread_id"]
    assert error["detail"] == "RuntimeError: boom"

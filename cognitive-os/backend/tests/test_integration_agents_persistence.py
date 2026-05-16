from __future__ import annotations

import shutil
import subprocess

import pytest

from cognitive_os.agents.graph import build_graph, cast_state, initial_state, postgres_checkpointer
from cognitive_os.memory.retrieval import RetrievedContext


def _docker_is_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )
    return result.returncode == 0


def fake_retriever(query: str) -> list[RetrievedContext]:
    return [
        RetrievedContext(
            text=query,
            citation="/tmp/persist.pdf:1-1",
            score=1.0,
            metadata={"source_path": "/tmp/persist.pdf", "page_start": 1, "page_end": 1},
        )
    ]


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _docker_is_available(), reason="Docker is not available"),
]


def test_state_persists_in_postgres_checkpointer() -> None:
    thread_id = "persist-thread-p8"
    with postgres_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer, retriever=fake_retriever)
        first = cast_state(
            graph.invoke(
                initial_state("consulta legal sobre contrato", thread_id=thread_id),
                config={"configurable": {"thread_id": thread_id}},
            )
        )
        assert first["active_route"] == "legal"

        state_snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
        persisted = cast_state(state_snapshot.values)
        assert persisted["thread_id"] == thread_id
        assert persisted["agent_result"].route == "legal"

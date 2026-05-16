from __future__ import annotations

import pytest

from cognitive_os.core.config import Settings
from cognitive_os.deepagents.memory_service import DeepAgentMemoryError, DeepAgentMemoryService


@pytest.mark.asyncio
async def test_record_episodic_user_scope_lists() -> None:
    svc = DeepAgentMemoryService(use_database=False)
    await svc.record_episodic_memory(
        user_id="alice",
        summary="usuario pidió resumen gmail matutino",
        agent_name="assistant",
    )
    items = await svc.list_memory("user", user_id="alice")
    assert any(it.kind == "episodic" for it in items)


@pytest.mark.asyncio
async def test_record_episodic_thread_scope_startup() -> None:
    svc = DeepAgentMemoryService(use_database=False)
    await svc.record_episodic_memory(
        user_id="alice",
        thread_id="thr-001",
        summary="dentro del hilo: recordar renovar dns semanalmente",
        agent_name="assistant",
    )
    startup = await svc.get_startup_memory("assistant", user_id="alice", thread_id="thr-001")

    assert "episodic" in startup
    assert "dns" in startup.lower()


@pytest.mark.asyncio
async def test_record_episodic_disabled_raises() -> None:
    svc = DeepAgentMemoryService(app_settings=Settings(deepagents_enable_memory=False))

    with pytest.raises(DeepAgentMemoryError, match="disabled"):
        await svc.record_episodic_memory(
            user_id="bob",
            summary="1234567890abcdefghij",
            agent_name="research",
        )

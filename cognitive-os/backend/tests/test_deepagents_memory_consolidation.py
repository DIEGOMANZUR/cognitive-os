from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cognitive_os.deepagents.memory_consolidation import DeepAgentMemoryConsolidator
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService


@pytest.mark.asyncio
async def test_consolidates_lesson_from_fake_job_event() -> None:
    service = DeepAgentMemoryService(use_database=False)
    consolidator = DeepAgentMemoryConsolidator(
        service,
        job_events=[
            {
                "thread_id": "thread-1",
                "agent_name": "research",
                "event_type": "agent_failed",
                "message": "Fallback was needed after missing citation.",
                "created_at": datetime.now(UTC),
            }
        ],
    )

    proposals = await consolidator.consolidate_thread("thread-1")

    assert len(proposals) == 1
    assert "Fallback" in proposals[0].proposed_content


@pytest.mark.asyncio
async def test_consolidation_generates_proposal_not_active_memory() -> None:
    service = DeepAgentMemoryService(use_database=False)
    consolidator = DeepAgentMemoryConsolidator(
        service,
        job_events=[
            {
                "thread_id": "thread-1",
                "agent_name": "research",
                "event_type": "agent_failed",
                "message": "Human correction required citation discipline.",
                "created_at": datetime.now(UTC),
            }
        ],
    )

    await consolidator.consolidate_thread("thread-1")
    proposals = await service.list_memory_proposals()
    active = await service.list_memory("agent")

    assert len(proposals) == 1
    assert active == []


@pytest.mark.asyncio
async def test_consolidation_deduplicates_repeated_lessons_in_one_run() -> None:
    service = DeepAgentMemoryService(use_database=False)
    repeated_event = {
        "thread_id": "thread-1",
        "agent_name": "research",
        "event_type": "agent_failed",
        "message": "Fallback was needed after missing citation.",
        "created_at": datetime.now(UTC),
    }
    consolidator = DeepAgentMemoryConsolidator(
        service,
        job_events=[repeated_event, repeated_event],
    )

    proposals = await consolidator.consolidate_thread("thread-1")

    assert len(proposals) == 1
    assert len(await service.list_memory_proposals()) == 1


@pytest.mark.asyncio
async def test_consolidation_deduplicates_against_existing_proposals() -> None:
    service = DeepAgentMemoryService(use_database=False)
    event = {
        "thread_id": "thread-1",
        "agent_name": "research",
        "event_type": "agent_failed",
        "message": "Fallback was needed after missing citation.",
        "created_at": datetime.now(UTC),
    }
    consolidator = DeepAgentMemoryConsolidator(service, job_events=[event])

    first = await consolidator.consolidate_thread("thread-1")
    second = await consolidator.consolidate_thread("thread-1")

    assert len(first) == 1
    assert second == []
    assert len(await service.list_memory_proposals()) == 1

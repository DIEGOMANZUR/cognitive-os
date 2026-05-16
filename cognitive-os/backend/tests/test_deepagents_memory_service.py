from __future__ import annotations

from uuid import uuid4

import pytest

from cognitive_os.deepagents.memory_schemas import DeepAgentMemoryProposal
from cognitive_os.deepagents.memory_service import DeepAgentMemoryError, DeepAgentMemoryService


def _service() -> DeepAgentMemoryService:
    return DeepAgentMemoryService(use_database=False)


def _proposal(content: str = "Prefer concise cited summaries.") -> DeepAgentMemoryProposal:
    return DeepAgentMemoryProposal(
        proposal_id=str(uuid4()),
        proposed_by_agent="research",
        scope="agent",
        reason="Useful correction from prior run",
        proposed_content=content,
        sensitivity="internal",
        source_task_id="task-1",
    )


@pytest.mark.asyncio
async def test_proposes_memory_pending_approval() -> None:
    service = _service()
    proposal = await service.propose_memory_update(_proposal())

    proposals = await service.list_memory_proposals()

    assert proposal.requires_approval is True
    assert proposals[0]["proposal_id"] == proposal.proposal_id


@pytest.mark.asyncio
async def test_rejects_secrets() -> None:
    service = _service()

    with pytest.raises(DeepAgentMemoryError, match="secret"):
        await service.propose_memory_update(_proposal("api_key=SHOULD_NOT_BE_STORED"))


@pytest.mark.asyncio
async def test_approves_proposal() -> None:
    service = _service()
    proposal = await service.propose_memory_update(_proposal())

    item = await service.approve_memory_proposal(proposal.proposal_id, "admin-1")

    assert item.status == "active"
    assert item.metadata["approved_by"] == "admin-1"


@pytest.mark.asyncio
async def test_exports_memory() -> None:
    service = _service()
    proposal = await service.propose_memory_update(_proposal())
    await service.approve_memory_proposal(proposal.proposal_id, "admin-1")

    exported = await service.export_memory("agent")

    assert exported["scope"] == "agent"
    assert len(exported["items"]) == 1


@pytest.mark.asyncio
async def test_archives_memory() -> None:
    service = _service()
    proposal = await service.propose_memory_update(_proposal())
    item = await service.approve_memory_proposal(proposal.proposal_id, "admin-1")

    await service.archive_memory(item.memory_id)
    exported = await service.export_memory("agent")

    assert exported["items"] == []

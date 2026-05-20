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


@pytest.mark.asyncio
async def test_proposal_kind_propagates_through_approve() -> None:
    """Fase 78: approving a procedure proposal must materialise kind=procedure.

    Pre-Fase-78 the approve path hardcoded kind="lesson" and silently
    dropped the proposal's intended kind, which would have prevented the
    recipe extractor from ever surfacing a procedure record. Regression
    test.
    """
    service = _service()
    proposal = await service.propose_memory_update(
        DeepAgentMemoryProposal(
            proposal_id=str(uuid4()),
            proposed_by_agent="research",
            scope="agent",
            reason="distilled recipe",
            proposed_content="Procedure: do X then Y.",
            sensitivity="internal",
            kind="procedure",
            confidence=0.42,
            metadata={"recipe": {"title": "do X then Y"}},
        )
    )

    item = await service.approve_memory_proposal(proposal.proposal_id, "admin-1")

    assert item.kind == "procedure"
    assert item.confidence == pytest.approx(0.42)
    assert item.metadata["recipe"] == {"title": "do X then Y"}


@pytest.mark.asyncio
async def test_list_memory_proposals_filters_by_kind() -> None:
    service = _service()
    await service.propose_memory_update(_proposal())  # default lesson
    await service.propose_memory_update(
        DeepAgentMemoryProposal(
            proposal_id=str(uuid4()),
            proposed_by_agent="research",
            scope="agent",
            reason="recipe",
            proposed_content="procedure body",
            sensitivity="internal",
            kind="procedure",
        )
    )

    procedures = await service.list_memory_proposals(kind="procedure")
    lessons = await service.list_memory_proposals(kind="lesson")

    assert len(procedures) == 1
    assert len(lessons) == 1
    assert procedures[0]["proposed_content"] == "procedure body"

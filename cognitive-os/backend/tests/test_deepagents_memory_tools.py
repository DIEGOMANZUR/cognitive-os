from __future__ import annotations

import asyncio
from uuid import uuid4

from cognitive_os.deepagents.memory_schemas import DeepAgentMemoryProposal
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService
from cognitive_os.deepagents.tools import (
    get_relevant_memory,
    list_available_skills,
    propose_memory_update,
    read_skill,
)


def test_list_available_skills() -> None:
    result = list_available_skills(task_type="research")

    names = {skill["name"] for skill in result["skills"]}

    assert "rag-research" in names
    assert "sandbox-code-analysis" not in names


def test_read_skill_blocks_path_traversal() -> None:
    result = read_skill("../rag-research")

    assert result["error"] == "invalid_skill_name"


def test_get_relevant_memory_redacts() -> None:
    service = DeepAgentMemoryService(use_database=False)
    proposal = asyncio.run(
        service.propose_memory_update(
            DeepAgentMemoryProposal(
                proposal_id=str(uuid4()),
                proposed_by_agent="research",
                scope="agent",
                reason="PII redaction check",
                proposed_content="User email test@example.com prefers short reports.",
                sensitivity="internal",
            )
        )
    )
    asyncio.run(service.approve_memory_proposal(proposal.proposal_id, "admin-1"))

    result = get_relevant_memory("agent", "reports", memory_service=service)

    assert "[REDACTED_PII]" in result["items"][0]["content"]


def test_propose_memory_update_does_not_apply_directly() -> None:
    service = DeepAgentMemoryService(use_database=False)

    result = propose_memory_update(
        "lesson",
        "Prefer evidence matrices for disputed facts.",
        "The user corrected a prior answer.",
        "agent",
        memory_service=service,
    )

    assert result["status"] == "pending_approval"
    assert result["applied"] is False

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from cognitive_os.core.db import session_scope
from cognitive_os.db.models import JobEvent
from cognitive_os.deepagents.memory_schemas import DeepAgentMemoryProposal
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService


class DeepAgentMemoryConsolidator:
    def __init__(
        self,
        memory_service: DeepAgentMemoryService | None = None,
        *,
        job_events: list[dict[str, Any]] | None = None,
    ) -> None:
        self._memory_service = memory_service or DeepAgentMemoryService()
        self._job_events = job_events

    async def consolidate_thread(self, thread_id: str) -> list[DeepAgentMemoryProposal]:
        events = await self._events_for_thread(thread_id)
        return await self._propose_lessons(events, source_task_id=thread_id)

    async def consolidate_agent_lessons(
        self,
        agent_name: str,
        since: datetime,
    ) -> list[DeepAgentMemoryProposal]:
        events = await self._events_for_agent(agent_name, since)
        return await self._propose_lessons(events, agent_name=agent_name)

    async def _propose_lessons(
        self,
        events: list[dict[str, Any]],
        *,
        agent_name: str = "deepagent",
        source_task_id: str | None = None,
    ) -> list[DeepAgentMemoryProposal]:
        proposals: list[DeepAgentMemoryProposal] = []
        seen_lesson_keys = await self._existing_lesson_keys(agent_name)
        for event in events:
            message = str(event.get("message") or "")
            event_type = str(event.get("event_type") or "")
            if not _is_learning_event(event_type, message):
                continue
            content = _lesson_from_event(event_type, message)
            lesson_key = _lesson_key(content)
            if lesson_key in seen_lesson_keys:
                continue
            seen_lesson_keys.add(lesson_key)
            proposal = DeepAgentMemoryProposal(
                proposal_id=str(uuid4()),
                proposed_by_agent=agent_name,
                scope="agent",
                reason=f"Consolidated from JobEvent {event_type}",
                proposed_content=content,
                sensitivity="internal",
                source_task_id=source_task_id or str(event.get("task_id") or ""),
                requires_approval=True,
            )
            await self._memory_service.propose_memory_update(proposal)
            proposals.append(proposal)
        return proposals

    async def _existing_lesson_keys(self, agent_name: str) -> set[str]:
        keys: set[str] = set()
        for proposal in await self._memory_service.list_memory_proposals():
            if proposal.get("proposed_by_agent") == agent_name:
                content = str(proposal.get("proposed_content") or "")
                if content:
                    keys.add(_lesson_key(content))
        for item in await self._memory_service.list_memory("agent", agent_name=agent_name):
            if item.content:
                keys.add(_lesson_key(item.content))
        return keys

    async def _events_for_thread(self, thread_id: str) -> list[dict[str, Any]]:
        if self._job_events is not None:
            return [event for event in self._job_events if event.get("thread_id") == thread_id]
        async with session_scope() as session:
            result = await session.execute(
                select(JobEvent).where(JobEvent.metadata_json["thread_id"].astext == thread_id)
            )
            return [_event_to_dict(event) for event in result.scalars().all()]

    async def _events_for_agent(self, agent_name: str, since: datetime) -> list[dict[str, Any]]:
        if self._job_events is not None:
            return [
                event
                for event in self._job_events
                if event.get("agent_name") == agent_name and event.get("created_at", since) >= since
            ]
        async with session_scope() as session:
            result = await session.execute(
                select(JobEvent).where(
                    JobEvent.created_at >= since,
                    JobEvent.metadata_json["agent_name"].astext == agent_name,
                )
            )
            return [_event_to_dict(event) for event in result.scalars().all()]


_NEGATIVE_MARKERS = ("failed", "error", "correction", "fallback", "warning")
_POSITIVE_MARKERS = (
    "completed",
    "approved",
    "indexed",
    "success",
    "research_finished",
    "ingestion_completed",
)


def _is_learning_event(event_type: str, message: str) -> bool:
    lowered = f"{event_type} {message}".lower()
    return any(marker in lowered for marker in (*_NEGATIVE_MARKERS, *_POSITIVE_MARKERS))


def _lesson_from_event(event_type: str, message: str) -> str:
    lowered = f"{event_type} {message}".lower()
    is_negative = any(marker in lowered for marker in _NEGATIVE_MARKERS)
    prefix = "Failure pattern observed" if is_negative else "Success pattern observed"
    bounded_message = message[:500]
    return f"{prefix} for event '{event_type}': {bounded_message}"


def _lesson_key(content: str) -> str:
    return " ".join(content.casefold().split())


def _event_to_dict(event: JobEvent) -> dict[str, Any]:
    return {
        "event_type": event.event_type,
        "message": event.message,
        "created_at": event.created_at,
        **event.metadata_json,
    }

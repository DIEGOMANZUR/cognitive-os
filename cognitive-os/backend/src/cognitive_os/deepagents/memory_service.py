from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import select

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import (
    AuditEvent,
    DeepAgentMemoryProposalRecord,
    DeepAgentMemoryRecord,
    HumanApproval,
)
from cognitive_os.deepagents.memory_schemas import (
    DeepAgentMemoryItem,
    DeepAgentMemoryKind,
    DeepAgentMemoryProposal,
    DeepAgentMemoryScope,
    DeepAgentMemorySensitivity,
    DeepAgentMemorySource,
    DeepAgentMemoryStatus,
)

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[=:]\s*\S+"),
    re.compile(r"\b[A-Za-z0-9]{33,}\b"),
)
PII_PATTERNS = (
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    re.compile(r"\+?\d[\d\s().-]{7,}\d"),
    re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b"),
)


class DeepAgentMemoryError(ValueError):
    """Raised when a memory operation violates Cognitive OS policy."""


class DeepAgentMemoryService:
    def __init__(
        self,
        app_settings: Settings = settings,
        *,
        use_database: bool = True,
    ) -> None:
        self._settings = app_settings
        self._use_database = use_database
        self._memory: dict[str, DeepAgentMemoryItem] = {}
        self._proposals: dict[str, DeepAgentMemoryProposal] = {}

    async def list_memory(
        self,
        scope: DeepAgentMemoryScope,
        user_id: str | None = None,
        case_id: str | None = None,
        thread_id: str | None = None,
        agent_name: str | None = None,
    ) -> list[DeepAgentMemoryItem]:
        if not self._settings.deepagents_enable_memory:
            return []
        if not self._use_database:
            return [
                item
                for item in self._memory.values()
                if item.scope == scope
                and item.status == "active"
                and _matches(item.user_id, user_id)
                and _matches(item.case_id, case_id)
                and _matches(item.thread_id, thread_id)
                and _matches(item.agent_name, agent_name)
            ]
        async with session_scope() as session:
            query = select(DeepAgentMemoryRecord).where(
                DeepAgentMemoryRecord.scope == scope,
                DeepAgentMemoryRecord.status == "active",
            )
            if user_id is not None:
                query = query.where(DeepAgentMemoryRecord.user_id == user_id)
            if case_id is not None:
                query = query.where(DeepAgentMemoryRecord.case_id == case_id)
            if thread_id is not None:
                query = query.where(DeepAgentMemoryRecord.thread_id == thread_id)
            if agent_name is not None:
                query = query.where(DeepAgentMemoryRecord.agent_name == agent_name)
            result = await session.execute(query.order_by(DeepAgentMemoryRecord.created_at))
            return [_item_from_record(record) for record in result.scalars().all()]

    async def get_startup_memory(
        self,
        agent_name: str,
        user_id: str | None = None,
        case_id: str | None = None,
        thread_id: str | None = None,
    ) -> str:
        sections: list[str] = []
        for scope in ("global", "agent", "user", "case", "thread"):
            items = await self.list_memory(
                scope,
                user_id=user_id,
                case_id=case_id,
                thread_id=thread_id,
                agent_name=agent_name if scope == "agent" else None,
            )
            if items:
                sections.append(f"## {scope}")
                sections.extend(f"- {item.kind}: {item.content}" for item in items)
        return "\n".join(sections)

    async def propose_memory_update(
        self,
        proposal: DeepAgentMemoryProposal,
    ) -> DeepAgentMemoryProposal:
        self._validate_content(proposal.proposed_content, proposal.sensitivity)
        requires_approval = (
            proposal.requires_approval
            or proposal.scope == "global"
            or self._settings.deepagents_memory_require_approval
        )
        normalized = proposal.model_copy(update={"requires_approval": requires_approval})
        redacted = await self.redact_memory_content(normalized.proposed_content)
        if not self._use_database:
            self._proposals[normalized.proposal_id] = normalized
            return normalized
        async with session_scope() as session:
            approval_id: UUID | None = None
            if requires_approval:
                approval = HumanApproval(
                    action="deepagents_memory_update",
                    requested_action="deepagents_memory_update",
                    args_redacted={
                        "proposal_id": normalized.proposal_id,
                        "scope": normalized.scope,
                        "reason": normalized.reason,
                        "content": redacted,
                    },
                    requested_by=normalized.proposed_by_agent,
                )
                session.add(approval)
                await session.flush()
                approval_id = approval.id
            record = DeepAgentMemoryProposalRecord(
                id=UUID(normalized.proposal_id),
                proposed_by_agent=normalized.proposed_by_agent,
                scope=normalized.scope,
                reason=normalized.reason,
                proposed_content_redacted=redacted,
                sensitivity=normalized.sensitivity,
                source_task_id=normalized.source_task_id,
                status="pending",
                approval_id=approval_id,
                metadata_json={"requires_approval": requires_approval},
            )
            session.add(record)
            session.add(
                _audit_event(
                    "deepagents.memory.propose",
                    normalized.proposed_by_agent,
                    normalized.proposal_id,
                    {"scope": normalized.scope, "sensitivity": normalized.sensitivity},
                )
            )
        return normalized

    async def approve_memory_proposal(
        self,
        proposal_id: str,
        approver_user_id: str,
    ) -> DeepAgentMemoryItem:
        now = datetime.now(UTC)
        if not self._use_database:
            proposal = self._get_in_memory_proposal(proposal_id)
            item = DeepAgentMemoryItem(
                memory_id=str(uuid4()),
                scope=proposal.scope,
                user_id=None,
                case_id=None,
                thread_id=None,
                agent_name=proposal.proposed_by_agent,
                kind="lesson",
                content=await self.redact_memory_content(proposal.proposed_content),
                source="agent_proposed",
                confidence=0.7,
                sensitivity=proposal.sensitivity,
                status="active",
                created_at=now,
                updated_at=now,
                metadata={"approved_by": approver_user_id, "proposal_id": proposal_id},
            )
            self._memory[item.memory_id] = item
            self._proposals.pop(proposal_id, None)
            return item
        async with session_scope() as session:
            record = await session.get(DeepAgentMemoryProposalRecord, UUID(proposal_id))
            if record is None:
                msg = f"Memory proposal not found: {proposal_id}"
                raise DeepAgentMemoryError(msg)
            record.status = "applied"
            record.decided_at = now
            item_record = DeepAgentMemoryRecord(
                scope=record.scope,
                user_id=None,
                case_id=None,
                thread_id=None,
                agent_name=record.proposed_by_agent,
                kind="lesson",
                content_redacted=record.proposed_content_redacted,
                source="agent_proposed",
                confidence=0.7,
                sensitivity=record.sensitivity,
                status="active",
                metadata_json={
                    "approved_by": approver_user_id,
                    "proposal_id": proposal_id,
                    "source_task_id": record.source_task_id,
                },
            )
            session.add(item_record)
            await session.flush()
            session.add(
                _audit_event(
                    "deepagents.memory.approve",
                    approver_user_id,
                    str(item_record.id),
                    {"proposal_id": proposal_id},
                )
            )
            return _item_from_record(item_record)

    async def reject_memory_proposal(
        self,
        proposal_id: str,
        approver_user_id: str,
        reason: str,
    ) -> None:
        if not self._use_database:
            self._proposals.pop(proposal_id, None)
            return
        async with session_scope() as session:
            record = await session.get(DeepAgentMemoryProposalRecord, UUID(proposal_id))
            if record is None:
                msg = f"Memory proposal not found: {proposal_id}"
                raise DeepAgentMemoryError(msg)
            record.status = "rejected"
            record.decided_at = datetime.now(UTC)
            record.metadata_json = {**record.metadata_json, "rejected_reason": reason}
            session.add(
                _audit_event(
                    "deepagents.memory.reject",
                    approver_user_id,
                    proposal_id,
                    {"reason": reason},
                )
            )

    async def record_episodic_memory(
        self,
        *,
        user_id: str,
        summary: str,
        agent_name: str,
        thread_id: str | None = None,
        case_id: str | None = None,
        sensitivity: DeepAgentMemorySensitivity = "internal",
        reference_metadata: dict[str, Any] | None = None,
        confidence: float = 1.0,
    ) -> DeepAgentMemoryItem:
        """Append an auditable episodic fact for timelines (user or thread scoped).

        Bypasses proposals: intended for short operational notes wired from trusted
        services (manual operator, Telegram webhook, Celery callbacks). Prefer
        `propose_memory_update` for enduring preferences needing review.
        """
        if not self._settings.deepagents_enable_memory:
            msg = "DeepAgents memory is disabled."
            raise DeepAgentMemoryError(msg)
        if sensitivity == "secret":
            msg = "Episodic memory cannot use sensitivity=secret."
            raise DeepAgentMemoryError(msg)
        uid = user_id.strip()
        if not uid:
            msg = "user_id cannot be empty."
            raise DeepAgentMemoryError(msg)
        trimmed_summary = summary.strip()
        self._validate_content(trimmed_summary, sensitivity)
        c = float(confidence)
        if not 0 <= c <= 1:
            msg = "confidence must be between 0 and 1."
            raise DeepAgentMemoryError(msg)
        tid = thread_id.strip() if thread_id and thread_id.strip() else None
        cid = case_id.strip() if case_id and case_id.strip() else None
        scope: DeepAgentMemoryScope = "thread" if tid else "user"
        ag = agent_name.strip() or "cognitive-os"
        redacted = await self.redact_memory_content(trimmed_summary)
        now = datetime.now(UTC)
        meta = {"channel": "episodic_endpoint", **(reference_metadata or {})}
        if not self._use_database:
            mid = str(uuid4())
            item = DeepAgentMemoryItem(
                memory_id=mid,
                scope=scope,
                user_id=uid,
                case_id=cid,
                thread_id=tid,
                agent_name=ag,
                kind="episodic",
                content=redacted,
                source="system",
                confidence=c,
                sensitivity=sensitivity,
                status="active",
                created_at=now,
                updated_at=now,
                metadata=meta,
            )
            self._memory[mid] = item
            return item

        rid = uuid4()
        async with session_scope() as session:
            item_record = DeepAgentMemoryRecord(
                id=rid,
                scope=scope,
                user_id=uid,
                case_id=cid,
                thread_id=tid,
                agent_name=ag,
                kind="episodic",
                content_redacted=redacted,
                source="system",
                confidence=c,
                sensitivity=sensitivity,
                status="active",
                metadata_json=meta,
            )
            session.add(item_record)
            await session.flush()
            session.add(
                _audit_event(
                    "deepagents.memory.episodic_append",
                    uid,
                    str(rid),
                    {"thread_id": tid, "case_id": cid, "agent_name": ag},
                )
            )
            return _item_from_record(item_record)

    async def archive_memory(self, memory_id: str) -> None:
        if not self._use_database:
            item = self._memory[memory_id]
            self._memory[memory_id] = item.model_copy(
                update={"status": "archived", "updated_at": datetime.now(UTC)}
            )
            return
        async with session_scope() as session:
            record = await session.get(DeepAgentMemoryRecord, UUID(memory_id))
            if record is None:
                msg = f"Memory not found: {memory_id}"
                raise DeepAgentMemoryError(msg)
            record.status = "archived"
            session.add(_audit_event("deepagents.memory.archive", None, memory_id, {}))

    async def export_memory(
        self,
        scope: DeepAgentMemoryScope,
        user_id: str | None = None,
        case_id: str | None = None,
    ) -> dict[str, Any]:
        items = await self.list_memory(scope, user_id=user_id, case_id=case_id)
        return {
            "scope": scope,
            "user_id": user_id,
            "case_id": case_id,
            "items": [item.model_dump(mode="json") for item in items],
        }

    async def list_memory_proposals(self) -> list[dict[str, Any]]:
        if not self._use_database:
            return [proposal.model_dump(mode="json") for proposal in self._proposals.values()]
        async with session_scope() as session:
            result = await session.execute(
                select(DeepAgentMemoryProposalRecord).order_by(
                    DeepAgentMemoryProposalRecord.created_at.desc()
                )
            )
            return [_proposal_record_to_dict(record) for record in result.scalars().all()]

    async def redact_memory_content(self, content: str) -> str:
        redacted = content
        if self._settings.deepagents_memory_redact_pii:
            for pattern in PII_PATTERNS:
                redacted = pattern.sub("[REDACTED_PII]", redacted)
        return redacted

    def _validate_content(
        self,
        content: str,
        sensitivity: DeepAgentMemorySensitivity,
    ) -> None:
        if sensitivity == "secret":
            msg = "Secret memory cannot be stored."
            raise DeepAgentMemoryError(msg)
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            msg = "Memory content appears to contain a secret."
            raise DeepAgentMemoryError(msg)

    def _get_in_memory_proposal(self, proposal_id: str) -> DeepAgentMemoryProposal:
        try:
            return self._proposals[proposal_id]
        except KeyError as exc:
            msg = f"Memory proposal not found: {proposal_id}"
            raise DeepAgentMemoryError(msg) from exc


def _matches(value: str | None, expected: str | None) -> bool:
    return expected is None or value == expected


def _item_from_record(record: DeepAgentMemoryRecord) -> DeepAgentMemoryItem:
    return DeepAgentMemoryItem(
        memory_id=str(record.id),
        scope=cast(DeepAgentMemoryScope, record.scope),
        user_id=record.user_id,
        case_id=record.case_id,
        thread_id=record.thread_id,
        agent_name=record.agent_name,
        kind=cast(DeepAgentMemoryKind, record.kind),
        content=record.content_redacted,
        source=cast(DeepAgentMemorySource, record.source),
        confidence=record.confidence,
        sensitivity=cast(DeepAgentMemorySensitivity, record.sensitivity),
        status=cast(DeepAgentMemoryStatus, record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
        metadata=record.metadata_json,
    )


def _audit_event(
    action: str,
    actor_id: str | None,
    resource_id: str,
    metadata: dict[str, Any],
) -> AuditEvent:
    return AuditEvent(
        actor_id=actor_id,
        action=action,
        resource_type="deepagent_memory",
        resource_id=resource_id,
        metadata_json=metadata,
    )


def _proposal_record_to_dict(record: DeepAgentMemoryProposalRecord) -> dict[str, Any]:
    return {
        "proposal_id": str(record.id),
        "proposed_by_agent": record.proposed_by_agent,
        "scope": record.scope,
        "reason": record.reason,
        "proposed_content": record.proposed_content_redacted,
        "sensitivity": record.sensitivity,
        "source_task_id": record.source_task_id,
        "status": record.status,
        "approval_id": str(record.approval_id) if record.approval_id else None,
        "created_at": record.created_at.isoformat(),
        "decided_at": record.decided_at.isoformat() if record.decided_at else None,
        "metadata": record.metadata_json,
    }

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from cognitive_os.agents.state import HumanReviewItem
from cognitive_os.agents.state import ToolRiskLevel as ReviewRiskLevel
from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import AuditEvent, HumanApproval


class ToolRiskLevel(StrEnum):
    READ_ONLY = "read_only"
    REVERSIBLE_WRITE = "reversible_write"
    EXTERNAL_ACTION = "external_action"
    SANDBOX_EXECUTE = "sandbox_execute"
    DANGEROUS = "dangerous"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    EXPIRED = "expired"


class ToolExecutionBlockedError(RuntimeError):
    """Raised when policy blocks a tool call before execution."""


class ToolExecutionRejectedError(RuntimeError):
    """Raised when a human reviewer rejected a pending tool call."""


class HumanApprovalRequiredError(RuntimeError):
    def __init__(self, review_item: HumanReviewItem, approval_request: ToolApprovalRequest) -> None:
        super().__init__(review_item.reason)
        self.review_item = review_item
        self.approval_request = approval_request


class ToolApprovalRequest(BaseModel):
    tool_name: str
    args_redacted: dict[str, Any]
    request_key: str
    status: ApprovalStatus = ApprovalStatus.PENDING


class ToolAuditRecord(BaseModel):
    tool_name: str
    risk_level: ToolRiskLevel
    args_redacted: dict[str, Any] = Field(default_factory=dict)
    result_summary: str | None = None
    actor_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


ToolHandler = Callable[[dict[str, Any]], Any]
AuditRecorder = Callable[[ToolAuditRecord], None]
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\b(?:sk|pk|rk|pat|ghp|github_pat)_[A-Za-z0-9_=-]{12,}\b"),
    re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^,\s;]+", re.IGNORECASE),
)


@dataclass(frozen=True)
class GuardedTool:
    name: str
    risk_level: ToolRiskLevel
    handler: ToolHandler
    audit_recorder: AuditRecorder | None = None
    app_settings: Settings = dataclass_field(default_factory=lambda: settings)

    def invoke(self, args: Mapping[str, Any] | None, state: Mapping[str, Any]) -> Any:
        normalized_args = dict(args or {})
        if self.risk_level is ToolRiskLevel.READ_ONLY:
            return self.handler(normalized_args)

        if self.risk_level is ToolRiskLevel.REVERSIBLE_WRITE:
            result = self.handler(normalized_args)
            self._record_audit(normalized_args, state, result)
            return result

        if self.risk_level is ToolRiskLevel.EXTERNAL_ACTION:
            return self._invoke_external_action(normalized_args, state)

        if self.risk_level is ToolRiskLevel.SANDBOX_EXECUTE:
            return self._invoke_external_action(normalized_args, state)

        if not self._dangerous_override_enabled(state):
            msg = f"Tool {self.name} is dangerous and blocked by policy."
            raise ToolExecutionBlockedError(msg)
        result = self.handler(normalized_args)
        self._record_audit(normalized_args, state, result)
        return result

    def _invoke_external_action(self, args: dict[str, Any], state: Mapping[str, Any]) -> Any:
        status = approval_status(self.name, args, state)
        if status is ApprovalStatus.APPROVED:
            result = self.handler(args)
            self._record_audit(args, state, result)
            return result
        if status in {ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED}:
            msg = f"Tool {self.name} was {status.value} by human review."
            raise ToolExecutionRejectedError(msg)

        request = build_approval_request(self.name, args)
        raise HumanApprovalRequiredError(
            HumanReviewItem(
                reason=f"Tool {self.name} requires human approval before external action.",
                risk_level=ReviewRiskLevel.HIGH,
                proposed_action=self.name,
                payload=request.model_dump(),
            ),
            request,
        )

    def _record_audit(
        self,
        args: dict[str, Any],
        state: Mapping[str, Any],
        result: Any,
    ) -> None:
        recorder = self.audit_recorder or record_audit_event
        recorder(
            ToolAuditRecord(
                tool_name=self.name,
                risk_level=self.risk_level,
                args_redacted=redact_tool_args(args),
                result_summary=_summarize_result(result),
                actor_id=_actor_id(state),
            )
        )

    def _dangerous_override_enabled(self, state: Mapping[str, Any]) -> bool:
        return bool(state.get("allow_dangerous_tools") or self.app_settings.allow_dangerous_tools)


def guarded_tool(
    tool_name: str,
    risk_level: ToolRiskLevel,
    handler: ToolHandler,
    *,
    audit_recorder: AuditRecorder | None = None,
    app_settings: Settings = settings,
) -> GuardedTool:
    return GuardedTool(
        name=tool_name,
        risk_level=risk_level,
        handler=handler,
        audit_recorder=audit_recorder,
        app_settings=app_settings,
    )


def requires_approval(
    tool_name: str,
    args: Mapping[str, Any] | None,
    state: Mapping[str, Any],
) -> bool:
    risk_level = classify_tool(tool_name)
    if risk_level not in {ToolRiskLevel.EXTERNAL_ACTION, ToolRiskLevel.SANDBOX_EXECUTE}:
        return False
    return approval_status(tool_name, dict(args or {}), state) is not ApprovalStatus.APPROVED


def classify_tool(tool_name: str) -> ToolRiskLevel:
    lowered = tool_name.lower()
    if "delete" in lowered or "remove" in lowered or "drop" in lowered:
        return ToolRiskLevel.DANGEROUS
    risk_map = {
        "create_email_draft": ToolRiskLevel.REVERSIBLE_WRITE,
        "create_calendar_draft": ToolRiskLevel.REVERSIBLE_WRITE,
        "send_email": ToolRiskLevel.EXTERNAL_ACTION,
        "publish_social_post": ToolRiskLevel.EXTERNAL_ACTION,
        "browser_action": ToolRiskLevel.DANGEROUS,
        "run_sandboxed_code_task": ToolRiskLevel.SANDBOX_EXECUTE,
    }
    return risk_map.get(tool_name, ToolRiskLevel.READ_ONLY)


def approval_status(
    tool_name: str,
    args: Mapping[str, Any],
    state: Mapping[str, Any],
) -> ApprovalStatus | None:
    approvals = state.get("tool_approvals", {})
    if not isinstance(approvals, Mapping):
        return None
    request_key = tool_request_key(tool_name, args)
    raw_status = approvals.get(request_key, approvals.get(tool_name))
    if raw_status is None:
        return None
    return ApprovalStatus(str(raw_status))


def build_approval_request(tool_name: str, args: Mapping[str, Any]) -> ToolApprovalRequest:
    args_redacted = redact_tool_args(args)
    return ToolApprovalRequest(
        tool_name=tool_name,
        args_redacted=args_redacted,
        request_key=tool_request_key(tool_name, args),
    )


def tool_request_key(tool_name: str, args: Mapping[str, Any]) -> str:
    payload = json.dumps(redact_tool_args(args), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{tool_name}:{payload}".encode()).hexdigest()
    return f"{tool_name}:{digest}"


def redact_tool_args(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if _is_secret_key(key_text):
                redacted[key_text] = "[REDACTED]"
            else:
                redacted[key_text] = redact_tool_args(nested)
        return redacted
    if isinstance(value, list):
        return [redact_tool_args(item) for item in value]
    if isinstance(value, tuple):
        return [redact_tool_args(item) for item in value]
    if isinstance(value, str):
        return _redact_secret_string(value)
    return value


def record_human_approval_request(
    request: ToolApprovalRequest,
    *,
    requested_by: str | None = None,
) -> None:
    _run_async(_insert_human_approval_request(request, requested_by=requested_by))


def record_audit_event(record: ToolAuditRecord) -> None:
    _run_async(_insert_audit_event(record))


async def _insert_human_approval_request(
    request: ToolApprovalRequest,
    *,
    requested_by: str | None,
) -> None:
    async with session_scope() as session:
        session.add(
            HumanApproval(
                action=request.tool_name,
                requested_action=request.tool_name,
                args_redacted=request.args_redacted,
                status=request.status.value,
                requested_by=requested_by,
                metadata_json={"request_key": request.request_key},
            )
        )


async def _insert_audit_event(record: ToolAuditRecord) -> None:
    async with session_scope() as session:
        session.add(
            AuditEvent(
                actor_id=record.actor_id,
                action=f"tool.{record.tool_name}",
                resource_type="tool",
                resource_id=record.tool_name,
                metadata_json={
                    "risk_level": record.risk_level.value,
                    "args_redacted": record.args_redacted,
                    "result_summary": record.result_summary,
                    "created_at": record.created_at.isoformat(),
                },
            )
        )


def _run_async[T](awaitable: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    msg = "Synchronous tool policy persistence cannot run inside an active event loop."
    raise RuntimeError(msg)


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(
        marker in lowered
        for marker in ("secret", "token", "password", "api_key", "apikey", "authorization")
    )


def _redact_secret_string(value: str) -> str:
    redacted = value
    for pattern in SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _summarize_result(result: Any) -> str:
    if isinstance(result, Mapping):
        status = result.get("status")
        identifier = result.get("id") or result.get("draft_id") or result.get("message_id")
        return f"status={status} id={identifier}"
    return type(result).__name__


def _actor_id(state: Mapping[str, Any]) -> str | None:
    raw_user_id = state.get("user_id")
    return str(raw_user_id) if raw_user_id is not None else None

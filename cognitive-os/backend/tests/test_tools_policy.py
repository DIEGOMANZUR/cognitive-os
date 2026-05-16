from __future__ import annotations

import pytest

from cognitive_os.tools.policy import (
    ApprovalStatus,
    HumanApprovalRequiredError,
    ToolAuditRecord,
    ToolExecutionBlockedError,
    ToolExecutionRejectedError,
    ToolRiskLevel,
    guarded_tool,
    redact_tool_args,
    requires_approval,
    tool_request_key,
)


def test_read_only_tool_executes() -> None:
    tool = guarded_tool(
        "search_local_docs",
        ToolRiskLevel.READ_ONLY,
        lambda args: {"status": "ok", "query": args["query"]},
    )

    assert tool.invoke({"query": "contrato"}, {"user_id": "u-1"}) == {
        "status": "ok",
        "query": "contrato",
    }


def test_send_email_generates_interrupt_request() -> None:
    tool = guarded_tool(
        "send_email",
        ToolRiskLevel.EXTERNAL_ACTION,
        lambda args: {"status": "sent", "to": args["to"]},
    )

    with pytest.raises(HumanApprovalRequiredError) as exc_info:
        tool.invoke({"to": "a@example.test", "api_token": "secret-value"}, {"user_id": "u-1"})

    request = exc_info.value.approval_request
    assert request.tool_name == "send_email"
    assert request.status is ApprovalStatus.PENDING
    assert request.args_redacted["api_token"] == "[REDACTED]"
    assert exc_info.value.review_item.proposed_action == "send_email"
    assert requires_approval("send_email", {"to": "a@example.test"}, {}) is True


def test_redact_tool_args_removes_secret_shaped_strings() -> None:
    jwt_like = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6Ikp1YW4ifQ."
        "TJVA95OrM7E2cBab30RMHrHDcEfxjoYZgeFONFh7HgQ"  # pragma: allowlist secret
    )
    message_with_secret = (
        "Use Bearer abcdefghijklmnopqrstuvwxyz123456 "  # pragma: allowlist secret
        "and token=super-secret-value"  # pragma: allowlist secret
    )
    redacted = redact_tool_args(
        {
            "headers": {"Authorization": "Bearer secret-because-key-redacts"},
            "message": message_with_secret,
            "nested": [f"jwt {jwt_like}"],
        }
    )
    rendered = str(redacted)

    assert "abcdefghijklmnopqrstuvwxyz123456" not in rendered  # pragma: allowlist secret
    assert "super-secret-value" not in rendered  # pragma: allowlist secret
    assert jwt_like not in rendered
    assert "[REDACTED]" in rendered


def test_reject_does_not_execute_external_tool() -> None:
    calls: list[dict[str, object]] = []
    tool = guarded_tool(
        "send_email",
        ToolRiskLevel.EXTERNAL_ACTION,
        lambda args: calls.append(args) or {"status": "sent"},
    )
    args = {"to": "a@example.test"}
    state = {"tool_approvals": {tool_request_key("send_email", args): "rejected"}}

    with pytest.raises(ToolExecutionRejectedError):
        tool.invoke(args, state)

    assert calls == []


def test_approve_executes_external_mock_and_audits() -> None:
    audit_records: list[ToolAuditRecord] = []
    tool = guarded_tool(
        "send_email",
        ToolRiskLevel.EXTERNAL_ACTION,
        lambda args: {"status": "sent_mock", "to": args["to"]},
        audit_recorder=audit_records.append,
    )
    args = {"to": "a@example.test"}
    state = {
        "user_id": "approver-subject",
        "tool_approvals": {tool_request_key("send_email", args): "approved"},
    }

    result = tool.invoke(args, state)

    assert result == {"status": "sent_mock", "to": "a@example.test"}
    assert audit_records[0].tool_name == "send_email"
    assert audit_records[0].actor_id == "approver-subject"


def test_dangerous_tool_is_blocked_by_default() -> None:
    tool = guarded_tool(
        "delete_everything",
        ToolRiskLevel.DANGEROUS,
        lambda args: {"status": "deleted"},
    )

    with pytest.raises(ToolExecutionBlockedError):
        tool.invoke({}, {})

from __future__ import annotations

from typing import Any

from cognitive_os.tools.policy import ToolRiskLevel, guarded_tool


def _create_email_draft(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "draft_created",
        "draft_id": "mock-email-draft",
        "to": args.get("to"),
        "subject": args.get("subject"),
    }


def _send_email(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "sent_mock",
        "message_id": "mock-email-message",
        "to": args.get("to"),
    }


def _create_calendar_draft(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "draft_created",
        "draft_id": "mock-calendar-draft",
        "title": args.get("title"),
    }


def _publish_social_post(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "published_mock",
        "post_id": "mock-social-post",
        "network": args.get("network"),
    }


def _browser_action(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "browser_action_mock",
        "action": args.get("action"),
    }


create_email_draft = guarded_tool(
    "create_email_draft",
    ToolRiskLevel.REVERSIBLE_WRITE,
    _create_email_draft,
)
send_email = guarded_tool("send_email", ToolRiskLevel.EXTERNAL_ACTION, _send_email)
create_calendar_draft = guarded_tool(
    "create_calendar_draft",
    ToolRiskLevel.REVERSIBLE_WRITE,
    _create_calendar_draft,
)
publish_social_post = guarded_tool(
    "publish_social_post",
    ToolRiskLevel.EXTERNAL_ACTION,
    _publish_social_post,
)
browser_action = guarded_tool("browser_action", ToolRiskLevel.DANGEROUS, _browser_action)

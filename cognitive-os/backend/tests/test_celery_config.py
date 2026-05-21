from __future__ import annotations

import pickle
from typing import Any, cast

import pytest

from cognitive_os.workers.celery_app import beat_schedule, celery_app


def test_celery_declares_expected_queues() -> None:
    queue_names = {queue.name for queue in celery_app.conf.task_queues}

    assert {"default", "ingestion", "agent_longrun", "maintenance", "mail"}.issubset(queue_names)


def test_celery_routes_commercial_tasks_to_expected_queues() -> None:
    routes = cast("dict[str, dict[str, str]]", celery_app.conf.task_routes)

    assert routes["cognitive_os.ingest_pdf"]["queue"] == "ingestion"
    assert routes["cognitive_os.run_deepagent_task"]["queue"] == "agent_longrun"
    assert routes["cognitive_os.run_action_request"]["queue"] == "agent_longrun"
    assert routes["cognitive_os.run_openshell_task"]["queue"] == "agent_longrun"
    assert routes["cognitive_os.run_document_analysis"]["queue"] == "agent_longrun"
    assert routes["cognitive_os.sync_personal_mail"]["queue"] == "mail"
    assert routes["cognitive_os.build_personal_mail_digest"]["queue"] == "mail"
    assert routes["cognitive_os.reap_stuck_action_requests"]["queue"] == "maintenance"


def test_action_request_reaper_is_scheduled_on_maintenance_beat() -> None:
    schedule = cast("dict[str, Any]", beat_schedule["action-request-reaper"])

    assert schedule["task"] == "cognitive_os.reap_stuck_action_requests"


def test_approval_reaper_is_routed_and_scheduled() -> None:
    routes = cast("dict[str, dict[str, str]]", celery_app.conf.task_routes)
    assert routes["cognitive_os.reap_stale_approvals"]["queue"] == "maintenance"

    schedule = cast("dict[str, Any]", beat_schedule["approval-reaper"])
    assert schedule["task"] == "cognitive_os.reap_stale_approvals"


def test_personal_mail_digest_is_scheduled_on_mail_beat() -> None:
    if "personal-mail-digest" not in beat_schedule:
        pytest.skip("MAIL_ENABLED=false in this test environment")
    schedule = cast("dict[str, Any]", beat_schedule["personal-mail-digest"])

    assert schedule["task"] == "cognitive_os.build_personal_mail_digest"
    pickle.dumps(schedule["schedule"])


def test_personal_mail_background_sync_is_not_scheduled_by_default() -> None:
    assert "personal-mail-sync" not in beat_schedule

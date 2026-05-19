from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init
from kombu import Exchange, Queue

from cognitive_os.core.config import settings
from cognitive_os.core.observability import configure_langsmith

celery_app = Celery(
    "cognitive_os",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["cognitive_os.workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=settings.celery_task_soft_time_limit_seconds,
    task_time_limit=settings.celery_task_time_limit_seconds,
    result_expires=settings.celery_result_expires_seconds,
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("ingestion", Exchange("ingestion"), routing_key="ingestion"),
        Queue("agent_longrun", Exchange("agent_longrun"), routing_key="agent_longrun"),
        Queue("maintenance", Exchange("maintenance"), routing_key="maintenance"),
        Queue("mail", Exchange("mail"), routing_key="mail"),
    ),
    task_routes={
        "cognitive_os.ingest_pdf": {"queue": "ingestion", "routing_key": "ingestion"},
        "cognitive_os.health_check": {"queue": "maintenance", "routing_key": "maintenance"},
        "cognitive_os.cleanup_old_jobs": {"queue": "maintenance", "routing_key": "maintenance"},
        "cognitive_os.reap_stuck_action_requests": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
        "cognitive_os.reap_stale_approvals": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
        "cognitive_os.debug_fast": {"queue": "default", "routing_key": "default"},
        "cognitive_os.run_deepagent_task": {
            "queue": "agent_longrun",
            "routing_key": "agent_longrun",
        },
        "cognitive_os.run_action_request": {
            "queue": "agent_longrun",
            "routing_key": "agent_longrun",
        },
        "cognitive_os.run_openshell_task": {
            "queue": "agent_longrun",
            "routing_key": "agent_longrun",
        },
        "cognitive_os.consolidate_deepagent_memory": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
        "cognitive_os.consolidate_all_deepagent_memory": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
        "cognitive_os.run_document_analysis": {
            "queue": "agent_longrun",
            "routing_key": "agent_longrun",
        },
        "cognitive_os.run_code_build": {
            "queue": "agent_longrun",
            "routing_key": "agent_longrun",
        },
        "cognitive_os.deliver_personal_reminders": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
        "cognitive_os.telegram_gmail_digest": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
        "cognitive_os.sync_personal_mail": {"queue": "mail", "routing_key": "mail"},
    },
    timezone="UTC",
    enable_utc=True,
)

beat_schedule: dict[str, object] = {}
if settings.deepagents_memory_consolidation_enabled:
    minute, hour, day_of_month, month_of_year, day_of_week = (
        settings.deepagents_memory_consolidation_cron.split()
    )
    beat_schedule["consolidate-deepagent-memory-all"] = {
        "task": "cognitive_os.consolidate_all_deepagent_memory",
        "schedule": crontab(
            minute=minute,
            hour=hour,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
            day_of_week=day_of_week,
        ),
    }
if settings.telegram_enabled and settings.enable_personal_reminder_delivery:
    beat_schedule["personal-assistant-reminders"] = {
        "task": "cognitive_os.deliver_personal_reminders",
        "schedule": crontab(minute="*/5"),
    }
if (
    settings.telegram_enabled
    and settings.telegram_gmail_digest_enabled
    and settings.gmail_read_enabled
):
    digest_hour = settings.telegram_gmail_digest_hour_utc
    beat_schedule["telegram-gmail-digest"] = {
        "task": "cognitive_os.telegram_gmail_digest",
        "schedule": crontab(minute=12, hour=digest_hour),
    }
if settings.mail_enabled:
    beat_schedule["personal-mail-sync"] = {
        "task": "cognitive_os.sync_personal_mail",
        "schedule": settings.mail_poll_interval_seconds,
    }
beat_schedule["action-request-reaper"] = {
    "task": "cognitive_os.reap_stuck_action_requests",
    "schedule": crontab(minute="*/10"),
}
beat_schedule["approval-reaper"] = {
    "task": "cognitive_os.reap_stale_approvals",
    "schedule": crontab(minute=15),
}
# Stale jobs reaper: rescata zombies queued/running/waiting_approval cuya
# updated_at hace > STALE_JOB_MAX_HOURS. Diario a las 03:30 UTC. (Fase 72 C.)
beat_schedule["stale-jobs-reaper"] = {
    "task": "cognitive_os.reap_stale_running_jobs",
    "schedule": crontab(minute=30, hour=3),
}
if beat_schedule:
    celery_app.conf.beat_schedule = beat_schedule


@worker_process_init.connect  # type: ignore[untyped-decorator]
def _bootstrap_observability(**_kwargs: object) -> None:
    """Export LangSmith credentials in every Celery worker process."""
    configure_langsmith()

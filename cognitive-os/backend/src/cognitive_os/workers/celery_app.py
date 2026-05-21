from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

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
        "cognitive_os.reap_stale_running_jobs": {
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
        "cognitive_os.build_personal_mail_digest": {"queue": "mail", "routing_key": "mail"},
        # Fase 78 — recipe extractor reuses the maintenance queue, same
        # tier as the existing memory consolidator. Cheap CPU work plus
        # one short LLM call per job; no need for a dedicated queue.
        "cognitive_os.extract_pending_recipes": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
        # Fase 79.3 — failure post-mortem scanner. Runs daily, reads-only
        # past job events, may emit warning proposals or auto-promote.
        "cognitive_os.scan_failure_postmortems": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
        # Fase 79.4 — tool scorecard aggregator. Runs daily, UPSERTs the
        # rollup table; pure read of job_events + action_requests.
        "cognitive_os.aggregate_tool_scorecard": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
        # Fase 80 — skill promoter. Daily, reads procedure records +
        # procedure_invocation_log and emits skill_promotion proposals.
        "cognitive_os.evaluate_skill_promotions": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
        # Fase 81 — nightly reflection. Pulls last 24h of threads,
        # runs the primary LLM, emits preference/lesson proposals with
        # mandatory evidence quotes.
        "cognitive_os.nightly_reflection": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
    },
    timezone="UTC",
    enable_utc=True,
)


def mail_digest_now() -> datetime:
    """Return Chile-local time for the personal mail digest crontab."""

    return datetime.now(ZoneInfo(settings.mail_digest_timezone))


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
if settings.mail_enabled and settings.mail_background_sync_enabled:
    beat_schedule["personal-mail-sync"] = {
        "task": "cognitive_os.sync_personal_mail",
        "schedule": settings.mail_poll_interval_seconds,
    }
if settings.mail_enabled and settings.mail_digest_enabled:
    digest_hours = ",".join(str(int(hour)) for hour in settings.mail_digest_hours_local)
    beat_schedule["personal-mail-digest"] = {
        "task": "cognitive_os.build_personal_mail_digest",
        "schedule": crontab(
            minute=0,
            hour=digest_hours,
            nowfun=mail_digest_now,
        ),
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
# Fase 78 (Fase A) — recipe extractor beat. Gated by a feature flag so
# operators can disable the autonomous loop without redeploying. The
# cron string lives in settings (default `*/30 * * * *`) so on-call can
# tune cadence without touching code.
if settings.recipe_extractor_enabled:
    re_minute, re_hour, re_dom, re_moy, re_dow = settings.recipe_extractor_cron.split()
    beat_schedule["recipe-extractor"] = {
        "task": "cognitive_os.extract_pending_recipes",
        "schedule": crontab(
            minute=re_minute,
            hour=re_hour,
            day_of_month=re_dom,
            month_of_year=re_moy,
            day_of_week=re_dow,
        ),
    }
# Fase 79.3 — failure post-mortem scanner. Gated by FAILURE_POSTMORTEM_ENABLED.
if settings.failure_postmortem_enabled:
    fp_minute, fp_hour, fp_dom, fp_moy, fp_dow = settings.failure_postmortem_cron.split()
    beat_schedule["failure-postmortem-scanner"] = {
        "task": "cognitive_os.scan_failure_postmortems",
        "schedule": crontab(
            minute=fp_minute,
            hour=fp_hour,
            day_of_month=fp_dom,
            month_of_year=fp_moy,
            day_of_week=fp_dow,
        ),
    }
# Fase 79.4 — tool effectiveness scorecard. Gated by TOOL_SCORECARD_ENABLED.
if settings.tool_scorecard_enabled:
    ts_minute, ts_hour, ts_dom, ts_moy, ts_dow = settings.tool_scorecard_cron.split()
    beat_schedule["tool-scorecard-aggregator"] = {
        "task": "cognitive_os.aggregate_tool_scorecard",
        "schedule": crontab(
            minute=ts_minute,
            hour=ts_hour,
            day_of_month=ts_dom,
            month_of_year=ts_moy,
            day_of_week=ts_dow,
        ),
    }
# Fase 80 — skill promoter. Gated by SKILL_PROMOTER_ENABLED.
if settings.skill_promoter_enabled:
    sp_minute, sp_hour, sp_dom, sp_moy, sp_dow = settings.skill_promoter_cron.split()
    beat_schedule["skill-promoter"] = {
        "task": "cognitive_os.evaluate_skill_promotions",
        "schedule": crontab(
            minute=sp_minute,
            hour=sp_hour,
            day_of_month=sp_dom,
            month_of_year=sp_moy,
            day_of_week=sp_dow,
        ),
    }
# Fase 81 — nightly reflection. Gated by NIGHTLY_REFLECTION_ENABLED.
if settings.nightly_reflection_enabled:
    nr_minute, nr_hour, nr_dom, nr_moy, nr_dow = settings.nightly_reflection_cron.split()
    beat_schedule["nightly-reflection"] = {
        "task": "cognitive_os.nightly_reflection",
        "schedule": crontab(
            minute=nr_minute,
            hour=nr_hour,
            day_of_month=nr_dom,
            month_of_year=nr_moy,
            day_of_week=nr_dow,
        ),
    }
if beat_schedule:
    celery_app.conf.beat_schedule = beat_schedule


@worker_process_init.connect  # type: ignore[untyped-decorator]
def _bootstrap_observability(**_kwargs: object) -> None:
    """Export LangSmith credentials in every Celery worker process."""
    configure_langsmith()

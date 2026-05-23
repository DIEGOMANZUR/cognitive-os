from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from cognitive_os.core.config import settings
from cognitive_os.core.db import async_session_factory
from cognitive_os.core.observability import configure_langsmith
from cognitive_os.core.resilience import embeddings_circuit_breaker, llm_circuit_breaker
from cognitive_os.workers.celery_app import celery_app


class ComponentHealth(BaseModel):
    name: str
    status: str
    detail: str | None = None
    latency_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthDashboard(BaseModel):
    status: str
    checked_at: datetime
    components: list[ComponentHealth]


# A component is "verified" only when its status came from a real probe (a live
# query against the dependency) or it is honestly off. `configured` means the
# wiring looks complete but no live call was made — that is NOT the same as
# healthy, and the dashboard must not paint it green. `degraded`/anything else
# is a failure. See AUDIT-2026-B: a dashboard that reports "ok" while half its
# components were never dialled is dishonest.
_VERIFIED_STATES = frozenset({"ok", "ready", "disabled"})
_CONFIGURED_STATES = frozenset({"configured"})


def _overall_status(components: list[ComponentHealth]) -> str:
    """Roll component statuses into one honest overall verdict.

    - `degraded` if any component is broken/unknown.
    - `configured` if every component is verified-or-configured but at least
      one is merely `configured` (wired, never probed live).
    - `ok` only when every component was verified by a live probe (or is off).
    """
    statuses = {component.status for component in components}
    if statuses - (_VERIFIED_STATES | _CONFIGURED_STATES):
        return "degraded"
    if statuses & _CONFIGURED_STATES:
        return "configured"
    return "ok"


def _inspect_workers_snapshot() -> dict[str, Any]:
    """Inspect only the worker facts needed by the dashboard.

    Celery inspect calls are broadcast RPCs. Calling registered/active/reserved/
    scheduled/queues sequentially can exceed the dashboard timeout even when the
    worker is healthy. Commercial health only needs two hard facts here:
    expected task registration and consumed queues. Deeper job activity belongs
    in job/worker diagnostics, not in every frontend poll.
    """
    inspector = celery_app.control.inspect(timeout=1.0)
    return {
        "registered": inspector.registered() or {},
        "active_queues": inspector.active_queues() or {},
        "active": {},
        "reserved": {},
        "scheduled": {},
    }


def _inspect_item_count(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    total = 0
    for items in value.values():
        if isinstance(items, list):
            total += len(items)
    return total


def _registered_task_names(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    names: set[str] = set()
    for items in value.values():
        if not isinstance(items, list):
            continue
        names.update(str(item) for item in items)
    return names


def _consumed_queue_names(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    names: set[str] = set()
    for items in value.values():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.add(item["name"])
    return names


async def check_health_dashboard(*, verify_live: bool = False) -> HealthDashboard:
    """Build the component dashboard.

    With `verify_live=True` the spend-bearing / latency-bearing components
    (`primary_llm`, `embeddings`, `mail`) run a real probe instead of just
    reporting `configured`. That path is operator-triggered only (the
    `POST /health/verify` endpoint) so a passive `/health/dashboard` poll never
    burns tokens or opens IMAP sockets. See AUDIT-2026-B.
    """
    components = await asyncio.gather(
        _safe_check("postgres", _check_postgres()),
        _safe_check("redis", _check_redis()),
        _safe_check("weaviate", _check_weaviate()),
        _safe_check("neo4j", _check_neo4j()),
        _safe_check("primary_llm", _check_primary_llm(verify_live=verify_live)),
        _safe_check("embeddings", _check_embeddings(verify_live=verify_live)),
        _safe_check("workers", _check_workers()),
        _safe_check("langsmith", _check_langsmith()),
        _safe_check("voice", _check_voice()),
        _safe_check("maps", _check_maps()),
        _safe_check("google_calendar", _check_calendar()),
        _safe_check("google_drive", _check_drive()),
        _safe_check("kimi_webbridge", _check_webbridge()),
        _safe_check("captcha_solver", _check_captcha()),
        _safe_check("mail", _check_mail(verify_live=verify_live)),
        _safe_check("mcp_client", _check_mcp()),
        _safe_check("operational_backlog", _check_operational_backlog()),
    )
    component_list = list(components)
    return HealthDashboard(
        status=_overall_status(component_list),
        checked_at=datetime.now(UTC),
        components=component_list,
    )


async def _check_postgres() -> ComponentHealth:
    started = _now_ms()
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return ComponentHealth(name="postgres", status="ok", latency_ms=_elapsed_ms(started))
    except Exception as exc:
        return _failed("postgres", exc, started)


async def _check_redis() -> ComponentHealth:
    started = _now_ms()
    try:
        from redis import asyncio as redis_asyncio

        redis_module = cast(Any, redis_asyncio)
        client = redis_module.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.http_timeout_seconds,
            socket_timeout=settings.http_timeout_seconds,
        )
        try:
            pong = await client.ping()
        finally:
            await client.aclose()
        status = "ok" if pong else "degraded"
        return ComponentHealth(name="redis", status=status, latency_ms=_elapsed_ms(started))
    except Exception as exc:
        return _failed("redis", exc, started)


async def _check_weaviate() -> ComponentHealth:
    started = _now_ms()
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.get(
                f"{settings.weaviate_url.rstrip('/')}/v1/.well-known/ready",
                headers={"Authorization": f"Bearer {settings.weaviate_api_key.get_secret_value()}"},
            )
        response.raise_for_status()
        return ComponentHealth(name="weaviate", status="ok", latency_ms=_elapsed_ms(started))
    except Exception as exc:
        return _failed("weaviate", exc, started)


async def _check_neo4j() -> ComponentHealth:
    started = _now_ms()
    try:
        http_url = _neo4j_http_url()
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(
                f"{http_url}/db/neo4j/tx/commit",
                auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
                json={"statements": [{"statement": "RETURN 1 AS ok"}]},
            )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            return ComponentHealth(
                name="neo4j",
                status="degraded",
                detail="Neo4j returned query errors.",
                latency_ms=_elapsed_ms(started),
            )
        return ComponentHealth(name="neo4j", status="ok", latency_ms=_elapsed_ms(started))
    except Exception as exc:
        return _failed("neo4j", exc, started)


async def _check_primary_llm(*, verify_live: bool = False) -> ComponentHealth:
    configured = settings.primary_llm_api_key.get_secret_value() != "CHANGEME"
    base_metadata: dict[str, Any] = {
        "provider": settings.primary_llm_provider,
        "model": settings.primary_llm_model,
        "circuit": llm_circuit_breaker.state.value,
    }
    if not configured:
        return ComponentHealth(
            name="primary_llm",
            status="degraded",
            detail="PRIMARY_LLM_API_KEY is not configured.",
            metadata={"circuit": llm_circuit_breaker.state.value},
        )
    if not verify_live:
        return ComponentHealth(
            name="primary_llm",
            status="configured",
            detail="Provider is configured; live call skipped to avoid spend.",
            metadata=base_metadata,
        )
    started = _now_ms()
    try:
        from cognitive_os.agents.llm_factory import create_primary_chat_model

        model = create_primary_chat_model()
        result = await model.ainvoke("ping")
        ok = bool(getattr(result, "content", None) is not None)
        return ComponentHealth(
            name="primary_llm",
            status="ok" if ok else "degraded",
            detail=(
                "Live completion succeeded."
                if ok
                else "Live completion returned an empty response."
            ),
            latency_ms=_elapsed_ms(started),
            metadata=base_metadata,
        )
    except Exception as exc:  # noqa: BLE001 - health degrades, never raises
        return _failed("primary_llm", exc, started)


async def _check_embeddings(*, verify_live: bool = False) -> ComponentHealth:
    keys_count = len(settings.embeddings_api_keys)
    configured = (
        settings.embeddings_base_url != "CHANGEME"
        and keys_count > 0
        and settings.embeddings_model != "CHANGEME"
    )
    if not configured:
        return ComponentHealth(
            name="embeddings",
            status="degraded",
            detail="Embeddings provider is not fully configured.",
            metadata={"circuit": embeddings_circuit_breaker.state.value},
        )
    base_metadata: dict[str, Any] = {
        "provider": settings.embeddings_provider,
        "model": settings.embeddings_model,
        "dimension": settings.embeddings_dimension,
        "key_pool_size": keys_count,
        "circuit": embeddings_circuit_breaker.state.value,
    }
    if not verify_live:
        return ComponentHealth(
            name="embeddings",
            status="configured",
            detail="Provider is configured; live embedding skipped to avoid spend.",
            metadata=base_metadata,
        )
    started = _now_ms()
    try:
        from cognitive_os.memory.embeddings import build_embedding_provider_from_settings

        provider = build_embedding_provider_from_settings()
        vector = await asyncio.to_thread(provider.embed_text, "ping", kind="query")
        ok = isinstance(vector, list) and len(vector) > 0
        return ComponentHealth(
            name="embeddings",
            status="ok" if ok else "degraded",
            detail=(
                f"Live embedding returned {len(vector)} dimensions."
                if ok
                else "Live embedding returned an empty vector."
            ),
            latency_ms=_elapsed_ms(started),
            metadata={**base_metadata, "live_dimension": len(vector) if ok else 0},
        )
    except Exception as exc:  # noqa: BLE001 - health degrades, never raises
        return _failed("embeddings", exc, started)


async def _check_langsmith() -> ComponentHealth:
    info = await asyncio.to_thread(configure_langsmith)
    metadata = {key: value for key, value in info.items() if key not in {"status", "detail"}}
    return ComponentHealth(
        name="langsmith",
        status=info["status"],
        detail=info.get("detail"),
        metadata=metadata,
    )


async def _check_voice() -> ComponentHealth:
    from cognitive_os.voice.service import VoiceService

    voice_status = await asyncio.to_thread(VoiceService().status)
    return ComponentHealth(
        name="voice",
        status=voice_status.status,
        detail=voice_status.reason,
        metadata={
            "stt_model": voice_status.stt_model,
            "tts_model": voice_status.tts_model,
            "max_audio_bytes": voice_status.max_audio_bytes,
        },
    )


async def _check_maps() -> ComponentHealth:
    from cognitive_os.actions.maps import MapsService

    maps_status = await asyncio.to_thread(MapsService().status)
    return ComponentHealth(
        name="maps",
        status=maps_status.status,
        detail=maps_status.reason,
        metadata={"default_travel_mode": maps_status.default_travel_mode},
    )


def _google_token_instructions(detail: str | None) -> str | None:
    """Append actionable next-step text when the failure is a missing token.

    `scripts/auth_google.py` is the canonical one-time OAuth flow. The check
    already redacts paths and credentials; here we keep that contract and only
    add a deterministic next-step pointer.
    """
    if not detail:
        return detail
    if "token.json" in detail or "auth_google.py" in detail:
        return (
            f"{detail} Run once: `uv run python backend/scripts/auth_google.py`. "
            "Refresh tokens are renewed automatically once the file exists."
        )
    return detail


async def _check_calendar() -> ComponentHealth:
    from cognitive_os.actions.calendar import CalendarService

    cal = await asyncio.to_thread(CalendarService().status)
    return ComponentHealth(
        name="google_calendar",
        status=cal.status,
        detail=_google_token_instructions(cal.reason),
        metadata={"write_enabled": cal.write_enabled, "calendar_id": cal.calendar_id},
    )


async def _check_drive() -> ComponentHealth:
    from cognitive_os.actions.drive import DriveService

    drv = await asyncio.to_thread(DriveService().status)
    return ComponentHealth(
        name="google_drive",
        status=drv.status,
        detail=_google_token_instructions(drv.reason),
        metadata={
            "write_enabled": drv.write_enabled,
            "upload_max_bytes": drv.upload_max_bytes,
        },
    )


async def _check_webbridge() -> ComponentHealth:
    from cognitive_os.actions.kimi_webbridge import KimiWebBridgeService

    wb = await asyncio.to_thread(KimiWebBridgeService().status)
    return ComponentHealth(
        name="kimi_webbridge",
        status=wb.status,
        detail=wb.reason,
        metadata={
            "daemon_url": wb.daemon_url,
            "daemon_running": wb.daemon_running,
            "extension_connected": wb.extension_connected,
            "active_provider": wb.active_provider,
            "edge_devtools_url": wb.edge_devtools_url,
            "edge_devtools_running": wb.edge_devtools_running,
            "allow_mutations": wb.allow_mutations,
            "allowed_domain_count": wb.allowed_domain_count,
        },
    )


async def _check_captcha() -> ComponentHealth:
    from cognitive_os.actions.captcha import CaptchaSolverService

    cap = await asyncio.to_thread(CaptchaSolverService().status)
    return ComponentHealth(
        name="captcha_solver",
        status=cap.status,
        detail=cap.reason,
        metadata={"base_url": cap.base_url},
    )


async def _check_mail(*, verify_live: bool = False) -> ComponentHealth:
    """Report mail wiring; optionally probe IMAP live.

    Passive `/health/dashboard` polls report `configured` (wiring complete, no
    live call) to avoid per-poll latency and keep credentials off every hit.
    `verify_live=True` (operator-triggered `/health/verify`) opens a real IMAP
    login so the operator can confirm the GoDaddy mailbox actually answers.
    """
    if not settings.mail_enabled:
        return ComponentHealth(
            name="mail",
            status="disabled",
            detail="MAIL_ENABLED=false",
            metadata={
                "godaddy_enabled": settings.mail_godaddy_enabled,
                "approval_required": settings.mail_require_approval_for_send,
            },
        )
    providers: list[str] = []
    if settings.mail_godaddy_enabled:
        password_set = settings.mail_godaddy_password.get_secret_value() not in {"", "CHANGEME"}
        if settings.mail_godaddy_username and password_set:
            providers.append("godaddy")
    if not providers:
        return ComponentHealth(
            name="mail",
            status="degraded",
            detail="MAIL_ENABLED=true but no provider has credentials configured.",
            metadata={
                "godaddy_enabled": settings.mail_godaddy_enabled,
                "approval_required": settings.mail_require_approval_for_send,
            },
        )
    base_metadata: dict[str, Any] = {
        "providers": providers,
        "approval_required": settings.mail_require_approval_for_send,
        "gmail_label": settings.mail_gmail_label,
    }
    if not verify_live:
        return ComponentHealth(
            name="mail",
            status="configured",
            detail="Mail providers wired; IMAP/SMTP live calls skipped to avoid latency.",
            metadata=base_metadata,
        )
    started = _now_ms()
    try:
        ok = await asyncio.to_thread(_probe_godaddy_imap)
        return ComponentHealth(
            name="mail",
            status="ok" if ok else "degraded",
            detail=(
                "GoDaddy IMAP login succeeded."
                if ok
                else "GoDaddy IMAP login did not authenticate."
            ),
            latency_ms=_elapsed_ms(started),
            metadata=base_metadata,
        )
    except Exception as exc:  # noqa: BLE001 - health degrades, never raises
        return _failed("mail", exc, started)


def _probe_godaddy_imap() -> bool:
    """Open a real IMAP login against the GoDaddy mailbox and log out.

    Synchronous (`imaplib` is blocking) — callers run it via `asyncio.to_thread`.
    """
    import contextlib
    import imaplib

    host = settings.mail_godaddy_imap_host
    port = settings.mail_godaddy_imap_port
    client = imaplib.IMAP4_SSL(host, port, timeout=settings.http_timeout_seconds)
    try:
        status, _ = client.login(
            settings.mail_godaddy_username,
            settings.mail_godaddy_password.get_secret_value(),
        )
        return status == "OK"
    finally:
        with contextlib.suppress(Exception):
            client.logout()


async def _check_mcp() -> ComponentHealth:
    """Report the MCP client wiring without live RPC calls.

    Live connectivity is exposed by the dedicated `/system/mcp` endpoint
    (which DOES dial every server). Here we only surface the parsed config
    so `/health/dashboard` stays fast — matching the `mail` contract.
    (Fase 74.)
    """
    if not settings.enable_mcp_client:
        return ComponentHealth(
            name="mcp_client",
            status="disabled",
            detail="ENABLE_MCP_CLIENT=false",
            metadata={"declared_servers": 0},
        )
    from cognitive_os.integrations.mcp_client import parse_mcp_servers

    specs = parse_mcp_servers(settings.mcp_servers)
    if not specs:
        return ComponentHealth(
            name="mcp_client",
            status="degraded",
            detail="ENABLE_MCP_CLIENT=true but MCP_SERVERS declares no valid server.",
            metadata={"declared_servers": 0},
        )
    return ComponentHealth(
        name="mcp_client",
        status="configured",
        detail=(f"{len(specs)} MCP server(s) declared; live status at /system/mcp."),
        metadata={
            "declared_servers": len(specs),
            "server_names": [s.name for s in specs],
        },
    )


# If neither the 10-minute action-request reaper nor the hourly approval
# reaper has completed in this many minutes, Celery beat is effectively dead
# and the backlog will grow silently. See AUDIT-2026-F.
_BEAT_LAG_DEGRADE_MINUTES = 120.0


async def _check_operational_backlog() -> ComponentHealth:
    """Surface the backlog the three reapers are supposed to keep at zero.

    AUDIT-2026-F: the reapers (`reap_stale_approvals`,
    `reap_stuck_action_requests`, `reap_stale_running_jobs`) exist, but if a
    reaper stops running (dead worker, stalled beat) the backlog grows with no
    alarm. This check degrades when a row has been stuck *past its own reaper
    threshold* — i.e. the reaper should already have cleared it — or when no
    reaper has completed recently. The operator should not have to guess.
    """
    from cognitive_os.db.models import ActionRequest, HumanApproval, Job, JobEvent

    started = _now_ms()
    now = datetime.now(UTC)
    approval_cutoff = now - timedelta(hours=settings.approval_pending_max_hours)
    job_cutoff = now - timedelta(hours=settings.stale_job_max_hours)
    action_cutoff = now - timedelta(minutes=settings.action_request_running_max_minutes)
    active_states = ("queued", "running")
    try:
        async with async_session_factory() as session:
            approvals_pending = (
                await session.scalar(
                    select(func.count(HumanApproval.id)).where(HumanApproval.status == "pending")
                )
            ) or 0
            approvals_stale = (
                await session.scalar(
                    select(func.count(HumanApproval.id)).where(
                        HumanApproval.status == "pending",
                        HumanApproval.created_at < approval_cutoff,
                    )
                )
            ) or 0
            jobs_stale = (
                await session.scalar(
                    select(func.count(Job.id)).where(
                        Job.status.in_(active_states),
                        Job.updated_at < job_cutoff,
                    )
                )
            ) or 0
            action_requests_stuck = (
                await session.scalar(
                    select(func.count(ActionRequest.id)).where(
                        ActionRequest.status.in_(active_states),
                        ActionRequest.updated_at < action_cutoff,
                    )
                )
            ) or 0
            last_reap = await session.scalar(
                select(func.max(JobEvent.created_at)).where(JobEvent.event_type == "reap_completed")
            )
    except Exception as exc:
        return _failed("operational_backlog", exc, started)

    beat_lag_minutes: float | None = None
    if last_reap is not None:
        if last_reap.tzinfo is None:
            last_reap = last_reap.replace(tzinfo=UTC)
        beat_lag_minutes = round((now - last_reap).total_seconds() / 60.0, 1)

    breaches: list[str] = []
    if approvals_stale:
        breaches.append(
            f"{approvals_stale} approval(s) pendiente(s) más de "
            f"{settings.approval_pending_max_hours}h"
        )
    if jobs_stale:
        breaches.append(f"{jobs_stale} job(s) atascado(s) más de {settings.stale_job_max_hours}h")
    if action_requests_stuck:
        breaches.append(
            f"{action_requests_stuck} action request(s) atascada(s) más de "
            f"{settings.action_request_running_max_minutes}min"
        )
    if beat_lag_minutes is not None and beat_lag_minutes > _BEAT_LAG_DEGRADE_MINUTES:
        breaches.append(
            f"ningún reaper completó en {beat_lag_minutes:g}min (Celery beat podría estar caído)"
        )

    return ComponentHealth(
        name="operational_backlog",
        status="degraded" if breaches else "ok",
        detail=("; ".join(breaches) if breaches else "Backlog dentro de umbrales."),
        latency_ms=_elapsed_ms(started),
        metadata={
            "approvals_pending": approvals_pending,
            "approvals_stale": approvals_stale,
            "jobs_stale": jobs_stale,
            "action_requests_stuck": action_requests_stuck,
            "beat_lag_minutes": beat_lag_minutes,
            "beat_lag_degrade_minutes": _BEAT_LAG_DEGRADE_MINUTES,
        },
    )


async def _check_workers() -> ComponentHealth:
    started = _now_ms()
    try:
        expected_tasks = set(celery_app.conf.task_routes.keys())
        expected_queues = {queue.name for queue in celery_app.conf.task_queues}
        snapshot: dict[str, Any] = {}
        inspect_error: str | None = None
        try:
            snapshot = await asyncio.to_thread(_inspect_workers_snapshot)
        except Exception as exc:  # noqa: BLE001 - health must degrade, not raise
            inspect_error = f"{type(exc).__name__}: {_sanitize_detail(str(exc))}"
        registered_tasks = _registered_task_names(snapshot.get("registered"))
        consumed_queues = _consumed_queue_names(snapshot.get("active_queues"))
        worker_names = sorted(
            {
                *(
                    snapshot.get("registered", {})
                    if isinstance(snapshot.get("registered"), dict)
                    else {}
                ),
                *(
                    snapshot.get("active_queues", {})
                    if isinstance(snapshot.get("active_queues"), dict)
                    else {}
                ),
            }
        )
        missing_tasks = sorted(expected_tasks - registered_tasks)
        missing_queues = sorted(expected_queues - consumed_queues)
        status = "ok"
        details: list[str] = []
        if not worker_names:
            status = "degraded"
            details.append("No active Celery workers exposed registered tasks or queues.")
        if inspect_error:
            status = "degraded"
            details.append(f"Worker inspect failed: {inspect_error}")
        if missing_tasks:
            status = "degraded"
            details.append(f"Missing registered task(s): {', '.join(missing_tasks[:5])}.")
        if missing_queues:
            status = "degraded"
            details.append(f"Worker is not consuming queue(s): {', '.join(missing_queues)}.")
        return ComponentHealth(
            name="workers",
            status=status,
            detail=" ".join(details) if details else None,
            latency_ms=_elapsed_ms(started),
            metadata={
                "workers": worker_names,
                "worker_count": len(worker_names),
                "registered_task_count": len(registered_tasks),
                "expected_task_count": len(expected_tasks),
                "missing_registered_tasks": missing_tasks,
                "consumed_queues": sorted(consumed_queues),
                "expected_queues": sorted(expected_queues),
                "missing_queues": missing_queues,
                "active_count": _inspect_item_count(snapshot.get("active")),
                "reserved_count": _inspect_item_count(snapshot.get("reserved")),
                "scheduled_count": _inspect_item_count(snapshot.get("scheduled")),
                "activity_counts_skipped": True,
            },
        )
    except Exception as exc:
        return _failed("workers", exc, started)


def _neo4j_http_url() -> str:
    if settings.neo4j_uri.startswith("bolt://"):
        host = settings.neo4j_uri.removeprefix("bolt://").split(":", 1)[0]
        return f"http://{host}:{settings.neo4j_http_port}"
    return settings.neo4j_uri.rstrip("/")


def _failed(name: str, exc: Exception, started: float) -> ComponentHealth:
    return ComponentHealth(
        name=name,
        status="degraded",
        detail=f"{type(exc).__name__}: {_sanitize_detail(str(exc))}",
        latency_ms=_elapsed_ms(started),
    )


async def _safe_check(name: str, check: Awaitable[ComponentHealth]) -> ComponentHealth:
    started = _now_ms()
    # Components that hit an LLM gateway get a more generous wait_for budget.
    # A 3s ceiling produced false `degraded` reports on cold start (the
    # TestSprite re-audit captured this on `primary_llm`). LLM probes are
    # operator-triggered (`POST /health/verify`), so the wider window does not
    # affect passive polling.
    if name in {"primary_llm", "embeddings"}:
        component_timeout = settings.health_llm_probe_timeout_seconds
    else:
        component_timeout = settings.health_component_timeout_seconds
    try:
        return await asyncio.wait_for(check, timeout=component_timeout)
    except TimeoutError:
        return ComponentHealth(
            name=name,
            status="degraded",
            detail=f"Health check timed out after {component_timeout:g}s.",
            latency_ms=_elapsed_ms(started),
        )
    except Exception as exc:
        return _failed(name, exc, started)


_SECRET_DETAIL_RE = re.compile(
    r"(?i)(bearer\s+|token\s*[=:]\s*|password\s*[=:]\s*|secret\s*[=:]\s*)[^\s,;]+"
)
_ABS_PATH_RE = re.compile(r"(?:/[A-Za-z0-9._ -]+){2,}")


def _sanitize_detail(value: str) -> str:
    redacted = _SECRET_DETAIL_RE.sub(r"\1[REDACTED]", value)
    return _ABS_PATH_RE.sub("[PATH]", redacted)


def _now_ms() -> float:
    return datetime.now(UTC).timestamp() * 1000


def _elapsed_ms(started: float) -> float:
    return round(_now_ms() - started, 2)

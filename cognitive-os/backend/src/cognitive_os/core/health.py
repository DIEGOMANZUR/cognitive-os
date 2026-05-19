from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import text

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


async def check_health_dashboard() -> HealthDashboard:
    components = await asyncio.gather(
        _safe_check("postgres", _check_postgres()),
        _safe_check("redis", _check_redis()),
        _safe_check("weaviate", _check_weaviate()),
        _safe_check("neo4j", _check_neo4j()),
        _safe_check("primary_llm", _check_primary_llm()),
        _safe_check("embeddings", _check_embeddings()),
        _safe_check("workers", _check_workers()),
        _safe_check("langsmith", _check_langsmith()),
        _safe_check("voice", _check_voice()),
        _safe_check("maps", _check_maps()),
        _safe_check("google_calendar", _check_calendar()),
        _safe_check("google_drive", _check_drive()),
        _safe_check("kimi_webbridge", _check_webbridge()),
        _safe_check("captcha_solver", _check_captcha()),
        _safe_check("mail", _check_mail()),
    )
    overall = (
        "ok"
        if all(
            component.status in {"ok", "configured", "disabled", "ready"}
            for component in components
        )
        else "degraded"
    )
    return HealthDashboard(
        status=overall,
        checked_at=datetime.now(UTC),
        components=list(components),
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


async def _check_primary_llm() -> ComponentHealth:
    configured = settings.primary_llm_api_key.get_secret_value() != "CHANGEME"
    if not configured:
        return ComponentHealth(
            name="primary_llm",
            status="degraded",
            detail="PRIMARY_LLM_API_KEY is not configured.",
            metadata={"circuit": llm_circuit_breaker.state.value},
        )
    return ComponentHealth(
        name="primary_llm",
        status="configured",
        detail="Provider is configured; live call skipped to avoid spend.",
        metadata={
            "provider": settings.primary_llm_provider,
            "model": settings.primary_llm_model,
            "circuit": llm_circuit_breaker.state.value,
        },
    )


async def _check_embeddings() -> ComponentHealth:
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
    return ComponentHealth(
        name="embeddings",
        status="configured",
        detail="Provider is configured; live embedding skipped to avoid spend.",
        metadata={
            "provider": settings.embeddings_provider,
            "model": settings.embeddings_model,
            "dimension": settings.embeddings_dimension,
            "key_pool_size": keys_count,
            "circuit": embeddings_circuit_breaker.state.value,
        },
    )


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


async def _check_mail() -> ComponentHealth:
    """Report mail wiring without IMAP/SMTP live calls.

    No live connection: avoids per-/health latency and keeps the GoDaddy/Gmail
    credentials out of every dashboard hit. Matches the contract used by
    primary_llm and embeddings ("configured" iff wiring is complete).
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
    return ComponentHealth(
        name="mail",
        status="configured",
        detail="Mail providers wired; IMAP/SMTP live calls skipped to avoid latency.",
        metadata={
            "providers": providers,
            "approval_required": settings.mail_require_approval_for_send,
            "gmail_label": settings.mail_gmail_label,
        },
    )


async def _check_workers() -> ComponentHealth:
    started = _now_ms()
    try:
        replies = await asyncio.to_thread(celery_app.control.ping, timeout=1.0)
        status = "ok" if replies else "degraded"
        return ComponentHealth(
            name="workers",
            status=status,
            detail=None if replies else "No active Celery workers replied.",
            latency_ms=_elapsed_ms(started),
            metadata={"replies": replies},
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
    try:
        return await check
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

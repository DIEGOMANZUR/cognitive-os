"""Telegram bot exposing the Cognitive OS via slash commands.

Designed to run as a standalone process alongside the API + Celery worker:

    uv run python -m cognitive_os.integrations.telegram_bot

Behavior:
* Long-polls Telegram `/getUpdates` (no webhook required, works behind NAT).
* Authorises only Telegram user IDs declared in `TELEGRAM_AUTHORIZED_USER_IDS`.
* Calls into the same service layer the HTTP API uses, so every command goes
  through the existing tool policy / human-approval gates.
* Replies are Markdown, capped at 4000 chars (Telegram limit).

Slash commands:
    /start /help                      — welcome, list commands
    /health                           — components healthy/degraded summary
    /stats                            — knowledge stats (docs/pages/chunks/jobs/approvals)
    /config                           — non-secret config flags
    /agents                           — DeepAgents status + policy + recent activity
    /skills                           — enabled DeepAgent skills
    /memory                           — pending memory proposals
    /consolidate                      — dispatch memory consolidation now
    /jobs                             — recent jobs
    /job <id>                         — job detail + last events
    /cancel <id>                      — cancel a job (idempotent)
    /approvals                        — pending human approvals
    /approve <id> | /reject <id>      — decide on an approval
    /threads                          — recent LangGraph threads
    /chat <message>                   — talk to the orchestrator (REST path)
    /ingest <absolute_path>           — enqueue a PDF ingestion
    /runs                             — recent LangSmith runs
    /tasks /task /done                — personal tasks (map chat→user with TELEGRAM_ASSIST_USER_MAP)
    /notes /note                      — personal notes Markdown
    /gmaildigest                      — Gmail sólo lectura (GMAIL_READ + token.json)
    /maps origen | destino            — ruta con tráfico (read-only)
    /calendar [max]                   — próximos eventos
    /freebusy [días]                  — disponibilidad calendar
    /drive <query>                    — buscar archivos Drive
    /documents [max]                  — documentos ingestados
    /audit [max]                      — últimos audit events
    /mail [max]                       — bandeja mail multicuenta
    /research [max]                   — research runs recientes
    /codebuild [max]                  — code-director builds
    /sandbox                          — estado OpenShell sandbox
    /capabilities                     — capacidades de action plane
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import String, cast, desc, func, select

from cognitive_os.actions.gmail_digest import (
    GmailDigestService,
    GmailRestReader,
    render_gmail_digest_telegram,
)
from cognitive_os.actions.schemas import GmailDigestRequest
from cognitive_os.agents.graph import initial_state
from cognitive_os.assist.schemas import (
    PersonalNoteCreate,
    PersonalTaskCreate,
    PersonalTaskUpdate,
    PersonalTaskView,
)
from cognitive_os.assist.service import PersonalAssistDisabledError, PersonalAssistService
from cognitive_os.assist.telegram_user import api_user_for_telegram_chat
from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.core.health import check_health_dashboard
from cognitive_os.core.observability import configure_langsmith
from cognitive_os.db.models import (
    Document,
    DocumentChunk,
    HumanApproval,
    Job,
    JobEvent,
)
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService
from cognitive_os.deepagents.skills_registry import DeepAgentSkillsRegistry
from cognitive_os.workers.tasks import (
    consolidate_all_deepagent_memory_task,
    ingest_pdf_task,
)

logger = logging.getLogger("cognitive_os.telegram")
HandlerFn = Callable[["TelegramBot", int, str], None]
COMMAND_HANDLERS: dict[str, HandlerFn] = {}
HELP_LINES: list[str] = []

POLL_TIMEOUT_SECONDS = 25
MESSAGE_CHAR_LIMIT = 4000


_MD_V1_RESERVED = ("_", "*", "[", "`")


def _md_escape(text: str) -> str:
    """Escape Telegram Markdown v1 reserved chars in dynamic text.

    Why: summaries / responses may contain stray `_` (e.g. `<ruta_absoluta>`)
    that Telegram interprets as italic-open without a matching close, returning
    HTTP 400 ``can't parse entities``. Used by the ``@command`` decorator and
    anywhere we splice user-controlled or doc-controlled strings into a
    Markdown-rendered message.
    """
    for ch in _MD_V1_RESERVED:
        text = text.replace(ch, f"\\{ch}")
    return text


def command(name: str, summary: str) -> Callable[[HandlerFn], HandlerFn]:
    def decorator(fn: HandlerFn) -> HandlerFn:
        COMMAND_HANDLERS[name] = fn
        HELP_LINES.append(f"/{name} — {_md_escape(summary)}")
        return fn

    return decorator


@dataclass
class TelegramBot:
    token: str
    allowed_user_ids: set[int]
    api_base: str = "https://api.telegram.org"
    offset: int = 0

    def url(self, method: str) -> str:
        return f"{self.api_base}/bot{self.token}/{method}"

    def send(self, chat_id: int, text: str, *, markdown: bool = True) -> None:
        body: dict[str, Any] = {"chat_id": chat_id, "text": text[:MESSAGE_CHAR_LIMIT]}
        if markdown:
            body["parse_mode"] = "Markdown"
        try:
            response = httpx.post(self.url("sendMessage"), json=body, timeout=10)
        except Exception as exc:
            logger.warning("telegram_send_failed: %s", exc)
            return
        # Telegram answers HTTP 200 + ok=true on success; surface non-2xx
        # (and parse_mode parse errors that return 400) so a silent UI failure
        # never goes unnoticed in the operator's logs. We do NOT raise: send
        # is best-effort from the bot's perspective (the handler logic
        # already ran), but observability is non-negotiable. (Fase 71 P0.C.)
        if response.status_code >= 400:
            logger.warning(
                "telegram_send_non_2xx status=%d markdown=%s body=%s",
                response.status_code,
                markdown,
                response.text[:300],
            )

    def run_forever(self) -> None:
        configure_langsmith()
        logger.info("telegram_bot_started authorized=%d", len(self.allowed_user_ids))
        while True:
            try:
                response = httpx.get(
                    self.url("getUpdates"),
                    params={"offset": self.offset, "timeout": POLL_TIMEOUT_SECONDS},
                    timeout=POLL_TIMEOUT_SECONDS + 5,
                )
                payload = response.json()
            except Exception as exc:
                logger.warning("telegram_poll_failed: %s", exc)
                time.sleep(5)
                continue
            for update in payload.get("result", []):
                self.offset = update["update_id"] + 1
                self._dispatch(update)

    def _dispatch(self, update: dict[str, Any]) -> None:
        message = update.get("message") or update.get("edited_message") or {}
        text = str(message.get("text") or "").strip()
        if not text:
            return
        chat = message.get("chat") or {}
        from_user = message.get("from") or {}
        chat_id = int(chat.get("id", 0))
        user_id = int(from_user.get("id", 0))
        if not chat_id:
            return
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            self.send(
                chat_id,
                "🚫 *Forbidden*. Tu user_id no está en TELEGRAM_AUTHORIZED_USER_IDS.",
            )
            return
        if not text.startswith("/"):
            # Plain message routing. In `dedicated_local` (single operator, his
            # own PC) we treat any non-slash message as a chat turn with the
            # orchestrator — same lane as `/chat`. In `strict` we still demand
            # explicit commands so an unintended LLM call can never happen.
            if settings.operator_profile == "dedicated_local":
                try:
                    cmd_chat(self, chat_id, text)
                except Exception:  # noqa: BLE001 - report and continue polling
                    logger.exception("plain_message_chat_failed")
                    self.send(
                        chat_id,
                        "❌ No pude procesar el mensaje como chat. /help para los comandos.",
                        markdown=False,
                    )
                return
            self.send(
                chat_id,
                "Usá un slash command. /help para la lista.",
                markdown=False,
            )
            return
        head, _, tail = text.partition(" ")
        cmd = head.lstrip("/").split("@")[0].lower()
        arg = tail.strip()
        handler = COMMAND_HANDLERS.get(cmd)
        if handler is None:
            self.send(chat_id, f"Comando desconocido: `/{cmd}` — usá /help")
            return
        try:
            handler(self, chat_id, arg)
        except Exception as exc:  # noqa: BLE001 - report any handler error
            logger.exception("handler_error %s", cmd)
            self.send(chat_id, f"❌ Error en /{cmd}: `{type(exc).__name__}: {exc}`")


# -- helpers ------------------------------------------------------------------


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _format_when(value: datetime | None) -> str:
    if value is None:
        return "—"
    delta = datetime.now(UTC) - (value if value.tzinfo else value.replace(tzinfo=UTC))
    minutes = int(delta.total_seconds() / 60)
    if minutes < 1:
        return "ahora"
    if minutes < 60:
        return f"{minutes}m"
    if minutes < 60 * 48:
        return f"{minutes // 60}h"
    return f"{minutes // (60 * 24)}d"


def _join(lines: list[str]) -> str:
    return "\n".join(lines)


def _safe_md_fragment(text: str, limit: int = 160) -> str:
    cleaned = (
        text.replace("*", "")
        .replace("_", "")
        .replace("`", "")
        .replace("[", "(")
        .replace("]", ")")
        .strip()
    )
    return cleaned[:limit] + ("…" if len(cleaned) > limit else "")


def _assist_user(chat_id: int) -> str:
    return api_user_for_telegram_chat(chat_id)


# -- commands -----------------------------------------------------------------


@command("start", "saludo y listado de comandos")
def cmd_start(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    cmd_help(bot, chat_id, "")


@command("help", "lista todos los comandos disponibles")
def cmd_help(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    title = "*Cognitive OS · comandos disponibles*"
    bot.send(chat_id, title + "\n\n" + _join(sorted(HELP_LINES)))


@command("health", "estado de cada componente del sistema")
def cmd_health(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    dashboard = _run(check_health_dashboard())
    lines = [f"*Health: {dashboard.status}*"]
    for component in dashboard.components:
        emoji = (
            "✅"
            if component.status in {"ok", "configured", "ready"}
            else "⚠️"
            if component.status in {"degraded", "disabled", "blocked"}
            else "❌"
        )
        latency = f" · {component.latency_ms}ms" if component.latency_ms else ""
        lines.append(f"{emoji} `{component.name}` · {component.status}{latency}")
    bot.send(chat_id, _join(lines))


@command("stats", "knowledge stats (docs / chunks / jobs / approvals)")
def cmd_stats(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    async def _gather() -> dict[str, int]:
        async with session_scope() as session:
            docs = await session.scalar(select(func.count(Document.id))) or 0
            chunks = await session.scalar(select(func.count(DocumentChunk.id))) or 0
            running = (
                await session.scalar(
                    select(func.count(Job.id)).where(Job.status.in_(("queued", "running")))
                )
                or 0
            )
            completed = (
                await session.scalar(select(func.count(Job.id)).where(Job.status == "completed"))
                or 0
            )
            failed = (
                await session.scalar(select(func.count(Job.id)).where(Job.status == "failed")) or 0
            )
            pending = (
                await session.scalar(
                    select(func.count(HumanApproval.id)).where(HumanApproval.status == "pending")
                )
                or 0
            )
            return {
                "docs": int(docs),
                "chunks": int(chunks),
                "running": int(running),
                "completed": int(completed),
                "failed": int(failed),
                "pending": int(pending),
            }

    data = _run(_gather())
    lines = [
        "*Knowledge stats*",
        f"📄 Documentos: *{data['docs']}*",
        f"🧩 Chunks: *{data['chunks']}*",
        f"▶ Jobs activos: *{data['running']}*",
        f"✅ Completados: *{data['completed']}*",
        f"❌ Fallidos: *{data['failed']}*",
        f"🟡 Aprobaciones pendientes: *{data['pending']}*",
    ]
    bot.send(chat_id, _join(lines))


@command("config", "flags y proveedores activos (sin secretos)")
def cmd_config(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    lines = [
        f"*Config · {settings.environment}*",
        f"`tools_readonly_mode` = {settings.tools_readonly_mode}",
        f"`approval_for_external` = {settings.require_human_approval_for_external_actions}",
        f"`web_search_enabled` = {settings.web_search_enabled}",
        f"`enable_email_send` = {settings.enable_email_send}",
        f"`enable_social_posting` = {settings.enable_social_posting}",
        f"`enable_openshell_sandbox` = {settings.enable_openshell_sandbox}",
        f"`primary_llm` = {settings.primary_llm_model}",
        (
            f"`embeddings` = {settings.embeddings_provider} · {settings.embeddings_model} "
            f"({settings.embeddings_dimension}d, pool={len(settings.embeddings_api_keys)})"
        ),
    ]
    bot.send(chat_id, _join(lines))


@command("agents", "DeepAgents activos con stats")
def cmd_agents(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    job_types = {
        "research": "deepagent_research",
        "document-analysis": "document_analysis",
        "openshell-sandbox": "openshell_sandbox",
    }

    async def _stats() -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        async with session_scope() as session:
            for name, job_type in job_types.items():
                total = (
                    await session.scalar(select(func.count(Job.id)).where(Job.job_type == job_type))
                    or 0
                )
                running = (
                    await session.scalar(
                        select(func.count(Job.id))
                        .where(Job.job_type == job_type)
                        .where(Job.status.in_(("queued", "running", "waiting_approval")))
                    )
                    or 0
                )
                last_at = await session.scalar(
                    select(Job.updated_at)
                    .where(Job.job_type == job_type)
                    .order_by(desc(Job.updated_at))
                    .limit(1)
                )
                out[name] = {"total": int(total), "running": int(running), "last": last_at}
        return out

    data = _run(_stats())
    lines = ["*DeepAgents*"]
    for name, stats in data.items():
        lines.append(
            f"• `{name}` · jobs={stats['total']} live={stats['running']} "
            f"last={_format_when(stats['last'])}"
        )
    bot.send(chat_id, _join(lines))


@command("skills", "skills DeepAgents habilitadas")
def cmd_skills(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    registry = DeepAgentSkillsRegistry()
    skills = registry.discover_core_skills() + registry.discover_user_skills(None)
    enabled = [skill for skill in skills if skill.enabled]
    lines = [f"*Skills habilitadas ({len(enabled)})*"]
    for skill in enabled:
        lines.append(f"• `{skill.name}` v{skill.version} · {skill.risk_level}")
    bot.send(chat_id, _join(lines))


@command("memory", "propuestas de memoria pendientes")
def cmd_memory(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    proposals = _run(DeepAgentMemoryService().list_memory_proposals())
    pending = [p for p in proposals if p.get("status") == "pending"]
    lines = [f"*Propuestas pendientes ({len(pending)})*"]
    for proposal in pending[:10]:
        lines.append(
            f"• `{proposal['proposal_id'][:8]}…` · {proposal['proposed_by_agent']} "
            f"({proposal['scope']}): {str(proposal['proposed_content'])[:120]}"
        )
    bot.send(chat_id, _join(lines))


@command("consolidate", "dispara consolidación de memoria DeepAgents")
def cmd_consolidate(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    result = consolidate_all_deepagent_memory_task.apply_async(queue="maintenance")
    bot.send(chat_id, f"🔄 Consolidación encolada: `{result.id}`")


@command("jobs", "lista los últimos 10 jobs")
def cmd_jobs(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    async def _query() -> list[Job]:
        async with session_scope() as session:
            result = await session.execute(select(Job).order_by(desc(Job.created_at)).limit(10))
            return list(result.scalars().all())

    jobs = _run(_query())
    lines = [f"*Últimos jobs ({len(jobs)})*"]
    for job in jobs:
        emoji = (
            "✅"
            if job.status == "completed"
            else "❌"
            if job.status in {"failed", "cancelled"}
            else "⏳"
        )
        lines.append(
            f"{emoji} `{str(job.id)[:8]}…` {job.job_type} · {job.status} "
            f"({job.progress}%) · {_format_when(job.updated_at)}"
        )
    bot.send(chat_id, _join(lines))


@command("job", "detalle de un job — uso: /job <id>")
def cmd_job(bot: TelegramBot, chat_id: int, arg: str) -> None:
    if not arg:
        bot.send(chat_id, "Uso: `/job <job_id>` (los primeros 8 chars sirven)")
        return

    async def _query() -> tuple[Job | None, list[JobEvent]]:
        async with session_scope() as session:
            job: Job | None
            try:
                job = await session.get(Job, UUID(arg))
            except ValueError:
                # partial id: prefix match on stringified UUID. Reject
                # anything outside hex/dash so SQL LIKE wildcards ('%', '_')
                # from user input never reach the pattern.
                prefix = arg.lower()
                if any(ch not in "0123456789abcdef-" for ch in prefix) or len(prefix) < 4:
                    job = None
                else:
                    result = await session.execute(
                        select(Job).where(cast(Job.id, String).ilike(f"{prefix}%")).limit(1)
                    )
                    job = result.scalars().first()
            events: list[JobEvent] = []
            if job is not None:
                event_result = await session.execute(
                    select(JobEvent)
                    .where(JobEvent.job_id == job.id)
                    .order_by(desc(JobEvent.created_at))
                    .limit(5)
                )
                events = list(event_result.scalars().all())
            return job, events

    job, events = _run(_query())
    if job is None:
        bot.send(chat_id, "Job no encontrado.")
        return
    lines = [
        f"*Job `{str(job.id)[:8]}…`*",
        f"tipo: `{job.job_type}` · estado: *{job.status}* · {job.progress}%",
        f"creado: {job.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"actualizado: {job.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "*Últimos eventos:*",
    ]
    for event in events:
        lines.append(
            f"• {event.created_at.strftime('%H:%M:%S')} · `{event.event_type}` "
            f"({event.status}): {(event.message or '')[:120]}"
        )
    bot.send(chat_id, _join(lines))


@command("cancel", "cancela un job — uso: /cancel <id>")
def cmd_cancel(bot: TelegramBot, chat_id: int, arg: str) -> None:
    if not arg:
        bot.send(chat_id, "Uso: `/cancel <job_id>`")
        return

    async def _cancel() -> str:
        async with session_scope() as session:
            try:
                job_uuid = UUID(arg)
            except ValueError:
                return "id inválido"
            job = await session.get(Job, job_uuid)
            if job is None:
                return "no encontrado"
            if job.status in {"completed", "failed", "cancelled"}:
                return f"ya estaba {job.status}"
            job.status = "cancelled"
            session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="job_cancelled",
                    status="cancelled",
                    message="Cancelled from Telegram bot",
                    metadata_json={"by": "telegram"},
                )
            )
            return "cancelado"

    result = _run(_cancel())
    bot.send(chat_id, f"`/cancel {arg[:8]}…` → {result}")


@command("approvals", "aprobaciones humanas pendientes")
def cmd_approvals(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    async def _query() -> list[HumanApproval]:
        async with session_scope() as session:
            result = await session.execute(
                select(HumanApproval)
                .where(HumanApproval.status == "pending")
                .order_by(desc(HumanApproval.created_at))
                .limit(10)
            )
            return list(result.scalars().all())

    approvals = _run(_query())
    if not approvals:
        bot.send(chat_id, "Sin aprobaciones pendientes.")
        return
    lines = [f"*Pendientes ({len(approvals)})*"]
    for approval in approvals:
        lines.append(
            f"• `{str(approval.id)[:8]}…` · *{approval.requested_action}* "
            f"· solicitada {_format_when(approval.created_at)}"
        )
    lines.append("")
    lines.append("Usá `/approve <id>` o `/reject <id>`.")
    bot.send(chat_id, _join(lines))


@command("approve", "aprueba una aprobación pendiente — uso: /approve <id>")
def cmd_approve(bot: TelegramBot, chat_id: int, arg: str) -> None:
    _decide_approval(bot, chat_id, arg, "approved")


@command("reject", "rechaza una aprobación pendiente — uso: /reject <id>")
def cmd_reject(bot: TelegramBot, chat_id: int, arg: str) -> None:
    _decide_approval(bot, chat_id, arg, "rejected")


def _normalise_approval_arg(raw: str) -> str:
    return raw.strip().strip("`").rstrip("…").rstrip(".").strip()


async def _resolve_approval_id(raw: str) -> tuple[UUID | None, str | None]:
    cleaned = _normalise_approval_arg(raw)
    if not cleaned:
        return None, None
    try:
        return UUID(cleaned), None
    except ValueError:
        pass

    if any(ch not in "0123456789abcdefABCDEF-" for ch in cleaned):  # pragma: allowlist secret
        return None, "id inválido"
    if len(cleaned) < 4:
        return None, "prefijo demasiado corto; usá al menos 4 caracteres"

    async with session_scope() as session:
        result = await session.execute(
            select(HumanApproval.id)
            .where(cast(HumanApproval.id, String).ilike(f"{cleaned}%"))
            .order_by(desc(HumanApproval.created_at))
            .limit(2)
        )
        matches = list(result.scalars().all())

    if not matches:
        return None, "no encontrado"
    if len(matches) > 1:
        return None, "prefijo ambiguo; usá más caracteres del approval_id"
    return matches[0], None


def _extract_action_request_id(requested_action: str) -> UUID | None:
    prefix = "execute_action_request:"
    if not requested_action.startswith(prefix):
        return None
    try:
        return UUID(requested_action.removeprefix(prefix))
    except ValueError:
        return None


async def _dispatch_approved_action_request(action_request_id: UUID) -> tuple[str, bool]:
    from cognitive_os.actions.service import ActionRequestError, ActionRequestService
    from cognitive_os.workers.tasks import run_action_request_task_async

    action_service = ActionRequestService()
    try:
        action_request = await action_service.queue_approved_action_request(action_request_id)
    except ActionRequestError as exc:
        return f"ActionRequest `{str(action_request_id)[:8]}…` no encolado: {exc}", False

    if action_request.job_id is None:
        return (
            f"ActionRequest `{str(action_request.id)[:8]}…` aprobado sin job para despachar.",
            False,
        )
    if action_request.status != "queued":
        return (
            f"ActionRequest `{str(action_request.id)[:8]}…` quedó en `{action_request.status}`; "
            "no se despachó tarea nueva.",
            False,
        )
    try:
        reservation = await action_service.reserve_action_dispatch(action_request.id)
    except ActionRequestError as exc:
        return f"ActionRequest `{str(action_request.id)[:8]}…` no reservado: {exc}", False
    action_request = reservation.action_request
    if not reservation.should_dispatch:
        return (
            f"ActionRequest `{str(action_request.id)[:8]}…`: "
            f"{reservation.reason or 'dispatch no requerido'}",
            False,
        )
    if action_request.job_id is None:
        return (
            f"ActionRequest `{str(action_request.id)[:8]}…` aprobado sin job para despachar.",
            False,
        )

    try:
        run_action_request_task_async.apply_async(
            args=[str(action_request.id), str(action_request.job_id)],
            queue="agent_longrun",
        )
    except Exception as exc:  # noqa: BLE001 - broker offline is an operator-facing state
        logger.warning(
            "telegram_action_request_dispatch_failed",
            extra={
                "action_request_id": str(action_request.id),
                "error_type": type(exc).__name__,
            },
        )
        with contextlib.suppress(Exception):
            await action_service.record_action_dispatch_event(
                job_id=action_request.job_id,
                action_request_id=action_request.id,
                event_type="action_request_dispatch_failed",
                status="queued",
                message="Telegram dispatch failed before Celery accepted it",
                metadata_json={"error_type": type(exc).__name__, "surface": "telegram"},
            )
        return (
            f"ActionRequest `{str(action_request.id)[:8]}…` aprobado, "
            f"pero Celery no aceptó el dispatch ({type(exc).__name__}).",
            False,
        )
    with contextlib.suppress(Exception):
        await action_service.record_action_dispatch_event(
            job_id=action_request.job_id,
            action_request_id=action_request.id,
            event_type="action_request_dispatch_submitted",
            status="queued",
            message="Telegram submitted action request to Celery",
            metadata_json={"queue": "agent_longrun", "surface": "telegram"},
        )
    return f"ActionRequest `{str(action_request.id)[:8]}…` despachado en `agent_longrun`.", True


def _decide_approval(bot: TelegramBot, chat_id: int, arg: str, status_value: str) -> None:
    """Telegram adapter for `actions.service.decide_approval`.

    Sharing the helper with the REST endpoint guarantees that approving from
    Telegram inherits four-eyes (when enabled), cascade-to-Job/ActionRequest on
    reject and AuditEvent emission, and dispatches OpenShell sandbox jobs the
    same way the panel does.
    """
    from cognitive_os.actions.service import (
        ApprovalAlreadyDecidedError,
        ApprovalDecisionError,
        ApprovalNotFoundError,
        ApprovalPayloadCorruptError,
        ApprovalSelfDecisionError,
        decide_approval,
    )
    from cognitive_os.api.app import _openshell_task_payload_from_job

    if not arg:
        command_name = "approve" if status_value == "approved" else "reject"
        bot.send(chat_id, f"Uso: `/{command_name} <approval_id>`")
        return
    approval_id, resolve_error = _run(_resolve_approval_id(arg))
    if approval_id is None:
        bot.send(chat_id, resolve_error or "id inválido")
        return

    async def _decide() -> tuple[str, object | None]:
        try:
            result = await decide_approval(
                approval_id,
                status_value=status_value,
                approver_user_id=f"telegram:{chat_id}",
                payload_resolver=_openshell_task_payload_from_job,
            )
        except ApprovalNotFoundError:
            return "no encontrado", None
        except ApprovalAlreadyDecidedError as exc:
            return f"ya estaba {exc.current_status}", None
        except ApprovalSelfDecisionError:
            return "rechazado por four-eyes (mismo solicitante)", None
        except ApprovalPayloadCorruptError:
            return "payload corrupto, no se pudo despachar", None
        except ApprovalDecisionError as exc:
            return f"error: {exc}", None
        return status_value, result

    status_label, decision = _run(_decide())
    if decision is not None and decision.openshell_dispatch is not None:
        try:
            from cognitive_os.workers.tasks import run_openshell_task_async

            run_openshell_task_async.apply_async(
                args=[decision.openshell_dispatch.task_payload, decision.openshell_dispatch.job_id],
                queue="agent_longrun",
            )
        except Exception as exc:  # noqa: BLE001 - Celery may be offline; report it
            logging.getLogger(__name__).warning(
                "telegram_openshell_dispatch_failed",
                extra={"error_type": type(exc).__name__},
            )
    if decision is not None and decision.code_build_job_id is not None:
        try:
            from cognitive_os.workers.tasks import run_code_build_task_async

            run_code_build_task_async.apply_async(
                args=[decision.code_build_job_id],
                queue="agent_longrun",
            )
        except Exception as exc:  # noqa: BLE001 - Celery may be offline; report it
            logging.getLogger(__name__).warning(
                "telegram_code_build_dispatch_failed",
                extra={"error_type": type(exc).__name__},
            )
    dispatch_message: str | None = None
    if decision is not None and status_value == "approved":
        action_request_id = _extract_action_request_id(decision.approval.requested_action)
        if action_request_id is not None:
            dispatch_message, _dispatched = _run(
                _dispatch_approved_action_request(action_request_id)
            )

    lines = [f"`/approval {str(approval_id)[:8]}…` → {status_label}"]
    if dispatch_message:
        lines.append(dispatch_message)
    bot.send(chat_id, _join(lines))


@command("threads", "últimos LangGraph threads")
def cmd_threads(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    async def _query() -> list[tuple[str, datetime | None]]:
        out: list[tuple[str, datetime | None]] = []
        seen: set[str] = set()
        try:
            async with session_scope() as session:
                from sqlalchemy import text as sql_text

                rows = await session.execute(
                    sql_text(
                        "SELECT thread_id, MAX(checkpoint_id) FROM checkpoints "
                        "GROUP BY thread_id ORDER BY MAX(checkpoint_id) DESC LIMIT 10"
                    )
                )
                for row in rows:
                    tid = str(row[0])
                    if tid not in seen:
                        seen.add(tid)
                        out.append((tid, None))
        except Exception as exc:
            logger.warning("telegram_threads_checkpoint_query_failed: %s", exc)
        async with session_scope() as session:
            jobs = await session.execute(select(Job).order_by(desc(Job.updated_at)).limit(40))
            for job in jobs.scalars().all():
                raw = (job.metadata_json or {}).get("thread_id")
                if isinstance(raw, str) and raw not in seen:
                    seen.add(raw)
                    out.append((raw, job.updated_at))
                if len(out) >= 10:
                    break
        return out

    threads = _run(_query())
    if not threads:
        bot.send(chat_id, "Sin threads recientes.")
        return
    lines = [f"*Threads ({len(threads)})*"]
    for tid, last in threads:
        lines.append(f"• `{tid[:12]}…` · {_format_when(last)}")
    bot.send(chat_id, _join(lines))


_REDIS_SALT_KEY = "telegram:thread_salt:{chat_id}"
_REDIS_SALT_DEFAULT = "v1"


def _thread_id_for_chat(chat_id: int) -> str:
    """Deterministic thread per Telegram chat, salted.

    Same `chat_id` + same salt → same `thread_id` → the LangGraph
    PostgresCheckpointer keeps every turn's state on disk so consecutive
    messages share context. `/reset` rotates the salt to start a fresh
    conversation without dropping history.

    The salt is persisted in Redis (key `telegram:thread_salt:{chat_id}`) so
    a bot restart does NOT silently reopen the previous thread the operator
    explicitly closed. Falls back to in-memory + "v1" if Redis is offline.
    (Fase 71 P1.F.)
    """
    salt = _load_salt_from_redis(chat_id) or _CHAT_THREAD_SALT.get(chat_id, _REDIS_SALT_DEFAULT)
    return f"telegram-chat-{chat_id}-{salt}"


# In-memory salt registry. Used as fallback when Redis is unavailable.
_CHAT_THREAD_SALT: dict[int, str] = {}


def _load_salt_from_redis(chat_id: int) -> str | None:
    try:
        import redis as redis_lib  # noqa: PLC0415

        client = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=1.0)
        value = client.get(_REDIS_SALT_KEY.format(chat_id=chat_id))
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)
    except Exception:  # noqa: BLE001 - Redis down → fall back to in-memory
        return None


def _persist_salt_to_redis(chat_id: int, salt: str) -> bool:
    try:
        import redis as redis_lib  # noqa: PLC0415

        client = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=1.0)
        # 365d TTL — long enough to survive month-long pauses, short enough
        # that abandoned chats eventually expire.
        client.set(_REDIS_SALT_KEY.format(chat_id=chat_id), salt, ex=365 * 24 * 3600)
    except Exception:  # noqa: BLE001 - best-effort persistence
        return False
    return True


@command("chat", "chat con el orquestador — uso: /chat <mensaje>")
def cmd_chat(bot: TelegramBot, chat_id: int, arg: str) -> None:
    if not arg:
        bot.send(chat_id, "Uso: `/chat <mensaje>`")
        return
    bot.send(chat_id, "🧠 procesando…", markdown=False)
    from cognitive_os.api.app import _api_graph

    thread_id = _thread_id_for_chat(chat_id)
    state = initial_state(arg, thread_id=thread_id, user_id=f"telegram:{chat_id}")
    raw = _api_graph.invoke(
        state,
        config={"configurable": {"thread_id": thread_id}},
    )
    if isinstance(raw, dict) and "__interrupt__" in raw:
        bot.send(
            chat_id,
            f"⏸ El thread `{thread_id[-8:]}` requiere aprobación humana. Revisá /approvals.",
        )
        return
    values = raw if isinstance(raw, dict) else {}
    messages = values.get("messages") or []
    last = messages[-1] if messages else None
    content = str(getattr(last, "content", "")) if last else "(sin respuesta)"
    route = str(values.get("active_route") or "?")
    # LLM output may contain unescaped Markdown V1 reserved chars (`_`, `*`,
    # `[`, backtick) that Telegram refuses with HTTP 400 silent. The header
    # we control still goes Markdown; the LLM body goes as plain text. Two
    # separate sends so the header stays formatted (Fase 71 P0.C).
    bot.send(chat_id, f"*ruta:* `{route}` · *thread:* `{thread_id[-8:]}`")
    bot.send(chat_id, content[:3500] or "(sin respuesta)", markdown=False)


@command("reset", "reinicia la memoria de la conversación (thread nuevo)")
def cmd_reset(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    new_salt = uuid4().hex[:8]
    _CHAT_THREAD_SALT[chat_id] = new_salt
    persisted = _persist_salt_to_redis(chat_id, new_salt)
    suffix = "" if persisted else " (⚠ no pude persistir el reset en Redis)"
    bot.send(
        chat_id,
        (
            "🧹 listo, empezás un thread nuevo. Los turnos previos siguen "
            "guardados en DB pero no los voy a leer." + suffix
        ),
        markdown=False,
    )


@command("ingest", "ingesta un PDF — uso: /ingest <ruta_absoluta>")
def cmd_ingest(bot: TelegramBot, chat_id: int, arg: str) -> None:
    if not arg:
        bot.send(chat_id, "Uso: `/ingest </ruta/absoluta.pdf>`")
        return

    async def _enqueue() -> tuple[UUID, str]:
        async with session_scope() as session:
            job = Job(
                job_type="document_ingestion",
                status="queued",
                progress=0,
                metadata_json={"document_path": arg, "requested_by": "telegram"},
            )
            session.add(job)
            await session.flush()
            session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="job_queued",
                    status="queued",
                    message="Document ingestion queued via Telegram",
                    metadata_json={"document_path": arg},
                )
            )
            return job.id, "queued"

    job_id, status_value = _run(_enqueue())
    ingest_pdf_task.apply_async(args=[arg, str(job_id)], queue="ingestion")
    bot.send(
        chat_id,
        f"📥 Ingesta encolada: `{str(job_id)[:8]}…` · status={status_value}\n"
        f"Seguilo con `/job {str(job_id)[:8]}`",
    )


@command("tasks", "tareas personales — /tasks")
def cmd_personal_tasks(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    uid = _assist_user(chat_id)
    try:
        rows = _run(PersonalAssistService().list_tasks(uid, limit=35))
    except PersonalAssistDisabledError:
        bot.send(
            chat_id,
            "Asistente personal desactivado: `ENABLE_PERSONAL_ASSISTANT_API=false`.",
            markdown=False,
        )
        return
    if not rows:
        bot.send(chat_id, "No hay tareas.")
        return
    status_emoji = {"pending": "⬜", "in_progress": "🔄", "done": "✅", "cancelled": "⛔"}
    lines = [f"*Tareas ({len(rows)})* · user `{uid}`"]
    for t in rows[:24]:
        em = status_emoji.get(t.status, "•")
        title_s = _safe_md_fragment(t.title, 140)
        due = f" · due `{t.due_at.strftime('%Y-%m-%d')}`" if t.due_at else ""
        lines.append(f"{em} `{str(t.id)[:8]}…` · {title_s} · `{t.status}`{due}")
    bot.send(chat_id, _join(lines))


@command("task", "nueva tarea — /task titulo [| descripción]")
def cmd_personal_task_add(bot: TelegramBot, chat_id: int, arg: str) -> None:
    if not arg:
        bot.send(chat_id, "Uso: `/task título` o `/task título | detalle`")
        return
    uid = _assist_user(chat_id)
    if "|" in arg:
        title, desc_raw = [p.strip() for p in arg.split("|", 1)]
        desc = desc_raw or None
    else:
        title, desc = arg.strip(), None
    if not title:
        bot.send(chat_id, "El título no puede estar vacío.")
        return
    body = PersonalTaskCreate(title=title, description=desc)
    try:
        created = _run(PersonalAssistService().create_task(uid, body))
    except PersonalAssistDisabledError:
        bot.send(
            chat_id,
            "Asistente personal desactivado: `ENABLE_PERSONAL_ASSISTANT_API=false`.",
            markdown=False,
        )
        return
    pref = created.id[:8]
    title_line = _safe_md_fragment(created.title, 180)
    bot.send(chat_id, f"Tarea creada `{pref}…`\n*{title_line}*\n`/done {pref}`")


@command("done", "marca done — /done <prefijo id>")
def cmd_personal_task_done(bot: TelegramBot, chat_id: int, arg: str) -> None:
    if not arg:
        bot.send(chat_id, "Uso: `/done <primeros caracteres del uuid>`")
        return
    uid = _assist_user(chat_id)

    async def _match() -> list[PersonalTaskView]:
        svc = PersonalAssistService()
        rows = await svc.list_tasks(uid, limit=200)
        needle = arg.strip().lower()
        return [r for r in rows if str(r.id).lower().startswith(needle)]

    try:
        cand = _run(_match())
    except PersonalAssistDisabledError:
        bot.send(
            chat_id,
            "Asistente personal desactivado: `ENABLE_PERSONAL_ASSISTANT_API=false`.",
            markdown=False,
        )
        return

    if not cand:
        bot.send(chat_id, "Sin coincidencias.")
        return
    if len(cand) != 1:
        bot.send(
            chat_id,
            "Hay varias o ninguna coincide: probá más caracteres del id.\n"
            + ", ".join(f"`{str(c.id)[:12]}…`" for c in cand[:5]),
        )
        return

    async def _patch() -> bool:
        out = await PersonalAssistService().update_task(
            uid, UUID(cand[0].id), PersonalTaskUpdate(status="done")
        )
        return out is not None

    if not _run(_patch()):
        bot.send(chat_id, "No se pudo actualizar (¿otro usuario?).")
        return
    bot.send(chat_id, f"Listo ✅ `{arg[:16]}…` → done")


@command("notes", "notas personales — /notes")
def cmd_personal_notes(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    uid = _assist_user(chat_id)
    try:
        rows = _run(PersonalAssistService().list_notes(uid, limit=30))
    except PersonalAssistDisabledError:
        bot.send(
            chat_id,
            "Asistente personal desactivado: `ENABLE_PERSONAL_ASSISTANT_API=false`.",
            markdown=False,
        )
        return
    if not rows:
        bot.send(chat_id, "No hay notas.")
        return
    lines = [f"*Notas ({len(rows)})* · `{uid}`"]
    for n in rows[:20]:
        title_s = _safe_md_fragment(n.title, 140)
        lines.append(f"`{str(n.id)[:8]}…` · {title_s}")
    bot.send(chat_id, _join(lines))


@command("note", "nota nueva — /note titulo | cuerpo")
def cmd_personal_note_add(bot: TelegramBot, chat_id: int, arg: str) -> None:
    if "|" not in arg:
        bot.send(chat_id, "Uso: `/note Mi título | cuerpo en markdown opcional`")
        return
    title, body_raw = [p.strip() for p in arg.split("|", 1)]
    if not title:
        bot.send(chat_id, "El título no puede estar vacío.")
        return
    uid = _assist_user(chat_id)
    body = PersonalNoteCreate(title=title, body_markdown=body_raw or "")
    try:
        created = _run(PersonalAssistService().create_note(uid, body))
    except PersonalAssistDisabledError:
        bot.send(
            chat_id,
            "Asistente personal desactivado: `ENABLE_PERSONAL_ASSISTANT_API=false`.",
            markdown=False,
        )
        return
    pref = created.id[:8]
    title_nt = _safe_md_fragment(created.title, 160)
    bot.send(chat_id, f"Nota guardada `{pref}…`\n*{title_nt}*")


@command("gmaildigest", "resumen Gmail solo lectura (token.json)")
def cmd_gmail_digest(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    if not settings.gmail_read_enabled:
        bot.send(
            chat_id,
            "`GMAIL_READ_ENABLED=false` — sin lectura Gmail.",
            markdown=False,
        )
        return
    reader = GmailRestReader.from_settings(settings)
    preview = GmailDigestService(reader=reader, app_settings=settings).build_preview(
        GmailDigestRequest(
            lookback_hours=settings.telegram_gmail_digest_lookback_hours,
            max_messages=35,
        )
    )
    text = render_gmail_digest_telegram(preview)
    bot.send(chat_id, text[:MESSAGE_CHAR_LIMIT])


@command("runs", "últimos LangSmith runs (si tracing está ok)")
def cmd_runs(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    langsmith_credential = settings.langsmith_personal_access_token.get_secret_value().strip()
    if not langsmith_credential or langsmith_credential == "CHANGEME":
        langsmith_credential = settings.langsmith_api_key.get_secret_value().strip()
    if not langsmith_credential or langsmith_credential == "CHANGEME":
        bot.send(chat_id, "LangSmith no configurado.")
        return
    try:
        from langsmith import Client

        client = Client(
            api_key=langsmith_credential,
            api_url=os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
        )
        runs = list(
            client.list_runs(project_name=settings.langsmith_project, limit=8, is_root=True)
        )
    except Exception as exc:
        bot.send(chat_id, f"LangSmith error: `{type(exc).__name__}: {exc}`")
        return
    if not runs:
        bot.send(chat_id, "Sin runs en el proyecto LangSmith.")
        return
    lines = [f"*Runs LangSmith ({settings.langsmith_project})*"]
    for run in runs:
        name = getattr(run, "name", None) or "(sin nombre)"
        status = getattr(run, "status", "?")
        latency_ms = None
        start = getattr(run, "start_time", None)
        end = getattr(run, "end_time", None)
        if start and end:
            latency_ms = (end - start).total_seconds() * 1000
        latency_str = f" · {int(latency_ms)}ms" if latency_ms else ""
        emoji = "❌" if getattr(run, "error", None) else "✅"
        lines.append(f"{emoji} {name[:36]} · {status}{latency_str}")
    bot.send(chat_id, _join(lines))


# -- Google Ops / Action Plane (read-only) -----------------------------------


def _parse_int_arg(arg: str, default: int, *, low: int = 1, high: int = 100) -> int:
    """Parse `arg` as an integer constrained to [low, high]; fall back to default."""
    raw = arg.strip()
    if not raw:
        return default
    try:
        return max(low, min(int(raw), high))
    except ValueError:
        return default


@command("maps", "ruta con tráfico — uso: /maps origen | destino")
def cmd_maps(bot: TelegramBot, chat_id: int, arg: str) -> None:
    if "|" not in arg:
        bot.send(chat_id, "Uso: `/maps origen | destino`")
        return
    origin, destination = (part.strip() for part in arg.split("|", 1))
    if not origin or not destination:
        bot.send(chat_id, "Tanto origen como destino son obligatorios.")
        return
    from cognitive_os.actions.maps import MapsError, MapsService

    service = MapsService()
    if service.status().status != "ready":
        reason = service.status().reason or "Maps no está disponible."
        bot.send(chat_id, f"Maps: `{reason}`")
        return
    try:
        plan = service.plan_route(
            origin=origin,
            destination=destination,
            traffic_aware=True,
            compute_alternatives=True,
        )
    except MapsError as exc:
        bot.send(chat_id, f"Maps error: `{exc}`")
        return
    lines = [
        f"*{plan.distance_text} · {plan.duration_text}*",
        f"{_safe_md_fragment(plan.route_advice, 240)}" if plan.route_advice else "",
        f"Tráfico: `{plan.traffic_severity}`"
        + (f" · retraso {plan.traffic_delay_text}" if plan.traffic_delay_text else "")
        + (f" · alternativas {plan.alternative_count}" if plan.alternative_count else ""),
    ]
    if plan.google_maps_url:
        lines.append(plan.google_maps_url)
    bot.send(chat_id, _join([line for line in lines if line]))


@command("calendar", "próximos eventos (lectura) — uso: /calendar [max]")
def cmd_calendar(bot: TelegramBot, chat_id: int, arg: str) -> None:
    from cognitive_os.actions.calendar import (
        CalendarError,
        CalendarService,
        ListEventsRequest,
    )

    service = CalendarService()
    if service.status().status != "ready":
        reason = service.status().reason or "Calendar no está disponible."
        bot.send(chat_id, f"Calendar: `{reason}`")
        return
    limit = _parse_int_arg(arg, default=10, low=1, high=25)
    try:
        events = service.list_events(ListEventsRequest(max_results=limit))
    except CalendarError as exc:
        bot.send(chat_id, f"Calendar error: `{exc}`")
        return
    if not events:
        bot.send(chat_id, "Sin eventos próximos.")
        return
    lines = [f"*Eventos próximos ({len(events)})*"]
    for event in events:
        start = event.start.replace("T", " ")[:16] if event.start else "?"
        title = _safe_md_fragment(event.summary, 80)
        loc = f" · {_safe_md_fragment(event.location, 40)}" if event.location else ""
        lines.append(f"• `{start}` · {title}{loc}")
    bot.send(chat_id, _join(lines))


@command("freebusy", "disponibilidad calendar — uso: /freebusy [días]")
def cmd_freebusy(bot: TelegramBot, chat_id: int, arg: str) -> None:
    from datetime import timedelta

    from cognitive_os.actions.calendar import (
        CalendarError,
        CalendarService,
        FreeBusyRequest,
    )

    service = CalendarService()
    if service.status().status != "ready":
        reason = service.status().reason or "Calendar no está disponible."
        bot.send(chat_id, f"Calendar: `{reason}`")
        return
    days = _parse_int_arg(arg, default=7, low=1, high=30)
    now = datetime.now(UTC)
    try:
        result = service.freebusy(
            FreeBusyRequest(
                time_min=now,
                time_max=now + timedelta(days=days),
                calendars=["primary"],
            )
        )
    except CalendarError as exc:
        bot.send(chat_id, f"Calendar error: `{exc}`")
        return
    lines = [
        f"*Free/busy próximos {days} día(s)* · ocupados: {result.busy_count}",
    ]
    for calendar_item in result.calendars:
        lines.append(f"• `{calendar_item.calendar_id}`")
        for slot in calendar_item.busy[:8]:
            start = slot.start[:16].replace("T", " ")
            end = slot.end[:16].replace("T", " ")
            lines.append(f"  ⛔ {start} → {end}")
    bot.send(chat_id, _join(lines))


@command("drive", "buscar en Drive — uso: /drive <query>")
def cmd_drive(bot: TelegramBot, chat_id: int, arg: str) -> None:
    query = arg.strip()
    if not query:
        bot.send(chat_id, "Uso: `/drive <texto a buscar>`")
        return
    from cognitive_os.actions.drive import (
        DriveError,
        DriveSearchRequest,
        DriveService,
    )

    service = DriveService()
    if service.status().status != "ready":
        reason = service.status().reason or "Drive no está disponible."
        bot.send(chat_id, f"Drive: `{reason}`")
        return
    try:
        files = service.list_files(
            DriveSearchRequest(query=query, max_results=15, search_mode="all")
        )
    except DriveError as exc:
        bot.send(chat_id, f"Drive error: `{exc}`")
        return
    if not files:
        bot.send(chat_id, "Sin coincidencias en Drive.")
        return
    lines = [f"*Drive · {len(files)} resultado(s)*"]
    for file_view in files[:12]:
        tag = "📁" if file_view.is_folder else "📄"
        name = _safe_md_fragment(file_view.name, 80)
        link = f" · {file_view.web_view_link}" if file_view.web_view_link else ""
        lines.append(f"{tag} {name}{link}")
    bot.send(chat_id, _join(lines))


@command("documents", "documentos ingestados — uso: /documents [max]")
def cmd_documents(bot: TelegramBot, chat_id: int, arg: str) -> None:
    limit = _parse_int_arg(arg, default=10, low=1, high=25)

    async def _query() -> list[Document]:
        async with session_scope() as session:
            result = await session.execute(
                select(Document).order_by(desc(Document.created_at)).limit(limit)
            )
            return list(result.scalars().all())

    docs = _run(_query())
    if not docs:
        bot.send(chat_id, "No hay documentos ingestados.")
        return
    lines = [f"*Documentos ({len(docs)})*"]
    for doc in docs:
        title = _safe_md_fragment(doc.title or doc.source_path, 80)
        lines.append(
            f"• `{str(doc.id)[:8]}…` · {title} · {doc.status} "
            f"· {doc.page_count}p · {doc.chunk_count}ch · {_format_when(doc.created_at)}"
        )
    bot.send(chat_id, _join(lines))


@command("audit", "últimos audit events — uso: /audit [max]")
def cmd_audit(bot: TelegramBot, chat_id: int, arg: str) -> None:
    from cognitive_os.db.models import AuditEvent  # noqa: PLC0415 - local import

    limit = _parse_int_arg(arg, default=15, low=1, high=50)

    async def _query() -> list[AuditEvent]:
        async with session_scope() as session:
            result = await session.execute(
                select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(limit)
            )
            return list(result.scalars().all())

    events = _run(_query())
    if not events:
        bot.send(chat_id, "Sin eventos de auditoría.")
        return
    lines = [f"*Audit ({len(events)})*"]
    for event in events:
        actor = event.actor_id or "—"
        resource = (
            f"{event.resource_type}:{str(event.resource_id)[:8]}…"
            if event.resource_type and event.resource_id
            else event.resource_type or "—"
        )
        lines.append(
            f"• {_format_when(event.created_at)} · `{event.action}` · {actor} · {resource}"
        )
    bot.send(chat_id, _join(lines))


@command("mail", "bandeja mail multicuenta — uso: /mail [max]")
def cmd_mail(bot: TelegramBot, chat_id: int, arg: str) -> None:
    from cognitive_os.db.models import MailMessage  # noqa: PLC0415 - local import

    if not settings.mail_enabled:
        bot.send(chat_id, "`MAIL_ENABLED=false` — mail multicuenta desactivado.", markdown=False)
        return
    limit = _parse_int_arg(arg, default=10, low=1, high=25)

    async def _query() -> list[MailMessage]:
        async with session_scope() as session:
            result = await session.execute(
                select(MailMessage).order_by(desc(MailMessage.created_at)).limit(limit)
            )
            return list(result.scalars().all())

    messages = _run(_query())
    if not messages:
        bot.send(chat_id, "No hay mensajes.")
        return
    status_emoji = {
        "new": "🆕",
        "reply_proposed": "✍️",
        "pending_send": "⏳",
        "sent": "✅",
        "ignored": "🙈",
        "failed": "❌",
    }
    lines = [f"*Mail · {len(messages)} mensaje(s)*"]
    for msg in messages:
        emoji = status_emoji.get(msg.status, "•")
        sender = _safe_md_fragment(msg.sender, 36)
        subject = _safe_md_fragment(msg.subject or "(sin asunto)", 70)
        lines.append(f"{emoji} `{str(msg.id)[:8]}…` · {sender} · {subject} · {msg.classification}")
    bot.send(chat_id, _join(lines))


@command("research", "últimos research runs — uso: /research [max]")
def cmd_research(bot: TelegramBot, chat_id: int, arg: str) -> None:
    from cognitive_os.db.models import ResearchRunRecord  # noqa: PLC0415 - local import

    limit = _parse_int_arg(arg, default=8, low=1, high=20)

    async def _query() -> list[ResearchRunRecord]:
        async with session_scope() as session:
            result = await session.execute(
                select(ResearchRunRecord).order_by(desc(ResearchRunRecord.created_at)).limit(limit)
            )
            return list(result.scalars().all())

    try:
        runs = _run(_query())
    except Exception as exc:  # noqa: BLE001 - research table may be missing in legacy installs
        bot.send(chat_id, f"Research no disponible: `{type(exc).__name__}: {exc}`")
        return
    if not runs:
        bot.send(chat_id, "Sin research runs.")
        return
    lines = [f"*Research runs ({len(runs)})*"]
    for run in runs:
        request_blob = run.request if isinstance(run.request, dict) else {}
        raw_query = str(request_blob.get("query") or "")
        query = _safe_md_fragment(raw_query or "(sin query)", 70)
        lines.append(
            f"• `{str(run.run_id)[:8]}…` · {run.status} · {query} · {_format_when(run.created_at)}"
        )
    bot.send(chat_id, _join(lines))


@command("codebuild", "últimos code-director builds — uso: /codebuild [max]")
def cmd_codebuild(bot: TelegramBot, chat_id: int, arg: str) -> None:
    limit = _parse_int_arg(arg, default=10, low=1, high=25)

    async def _query() -> list[Job]:
        async with session_scope() as session:
            result = await session.execute(
                select(Job)
                .where(Job.job_type == "code_build")
                .order_by(desc(Job.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())

    jobs = _run(_query())
    if not jobs:
        bot.send(chat_id, "Sin code builds recientes.")
        return
    lines = [f"*Code builds ({len(jobs)})*"]
    for job in jobs:
        rationale = _safe_md_fragment(
            str((job.metadata_json or {}).get("objective", ""))[:80] or "—",
            80,
        )
        lines.append(
            f"• `{str(job.id)[:8]}…` · {job.status} ({job.progress}%) · "
            f"{rationale} · {_format_when(job.updated_at)}"
        )
    bot.send(chat_id, _join(lines))


@command("sandbox", "estado openshell sandbox — /sandbox")
def cmd_sandbox(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    if not settings.enable_openshell_sandbox:
        bot.send(chat_id, "`ENABLE_OPENSHELL_SANDBOX=false`.", markdown=False)
        return

    async def _query() -> list[Job]:
        async with session_scope() as session:
            result = await session.execute(
                select(Job)
                .where(Job.job_type == "openshell_sandbox")
                .order_by(desc(Job.created_at))
                .limit(10)
            )
            return list(result.scalars().all())

    jobs = _run(_query())
    lines = ["*OpenShell sandbox*"]
    if not jobs:
        lines.append("Sin tareas recientes.")
    else:
        for job in jobs:
            lines.append(
                f"• `{str(job.id)[:8]}…` · {job.status} ({job.progress}%) "
                f"· {_format_when(job.updated_at)}"
            )
    bot.send(chat_id, _join(lines))


@command("capabilities", "capacidades del action plane")
def cmd_capabilities(bot: TelegramBot, chat_id: int, _arg: str) -> None:
    lines = [
        "*Action plane*",
        f"`browser_automation` = {settings.enable_browser_automation}",
        f"`computer_actions` = {settings.enable_computer_actions}",
        f"`gmail_read` = {settings.gmail_read_enabled}"
        f" · `gmail_send` = {settings.gmail_send_enabled}",
        f"`maps_routing` = {settings.enable_maps_routing}",
        f"`google_calendar` = {settings.enable_google_calendar}"
        f" · write = {settings.enable_google_calendar_write}",
        f"`google_drive` = {settings.enable_google_drive}"
        f" · write = {settings.enable_google_drive_write}",
        f"`godaddy_dns` = {settings.godaddy_enabled}"
        f" · dry-only = {settings.godaddy_dns_dry_run_only}",
        f"`mail_multi_account` = {settings.mail_enabled}"
        f" · godaddy = {settings.mail_godaddy_enabled}"
        f" · approval = {settings.mail_require_approval_for_send}",
        f"`document_generation` = {settings.enable_document_generation}",
        f"`research_orchestrator` = {settings.enable_research_orchestrator}",
        f"`openshell_sandbox` = {settings.enable_openshell_sandbox}",
        f"`voice` = {settings.voice_enabled}",
        f"`webbridge` = {settings.enable_kimi_webbridge}",
    ]
    bot.send(chat_id, _join(lines))


# -- entrypoint ---------------------------------------------------------------


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not settings.telegram_enabled:
        logger.info("TELEGRAM_ENABLED=false; no arranco. Setealo a true en .env.")
        return 0
    token = settings.telegram_bot_token.get_secret_value().strip()
    if not token or token == "CHANGEME":
        logger.error("TELEGRAM_BOT_TOKEN no configurado.")
        return 1
    allowed = set(settings.telegram_authorized_user_ids)
    if not allowed:
        logger.warning(
            "TELEGRAM_AUTHORIZED_USER_IDS vacío — el bot rechazará todos los mensajes. "
            "Pegale tu user_id (entero, separado por coma)."
        )
    bot = TelegramBot(token=token, allowed_user_ids=allowed)
    bot.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Iterator, Sequence
from contextlib import asynccontextmanager, contextmanager, suppress
from pathlib import Path
from typing import Any, Literal, cast

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from cognitive_os.agents.llm_factory import (
    create_agent_chat_model,
    create_primary_chat_model,
    create_secondary_chat_model,
)
from cognitive_os.agents.research import ReadOnlyResearchTools, ResearchAgent
from cognitive_os.agents.state import (
    AgentResult,
    BudgetState,
    CognitiveState,
    HumanReviewItem,
    RetrievalCitation,
    RouterDecision,
    ToolPolicy,
    ToolRiskLevel,
)
from cognitive_os.core.config import settings
from cognitive_os.deepagents.document_analysis.schemas import (
    DocumentAnalysisMode,
    DocumentAnalysisResult,
    DocumentAnalysisTask,
)
from cognitive_os.deepagents.document_analysis.service import DocumentAnalysisService
from cognitive_os.deepagents.schemas import DeepAgentCitation, DeepAgentResult, DeepAgentTask
from cognitive_os.deepagents.service import run_deepagent_task
from cognitive_os.memory.retrieval import RetrievedContext, retrieve_context
from cognitive_os.tools.policy import (
    ToolAuditRecord,
    record_audit_event,
)
from cognitive_os.tools.policy import (
    ToolRiskLevel as PolicyToolRiskLevel,
)

Retriever = Callable[[str], list[RetrievedContext]]
DeepAgentRunner = Callable[[DeepAgentTask], DeepAgentResult]
DocumentAnalysisRunner = Callable[[DocumentAnalysisTask], DocumentAnalysisResult]

log = structlog.get_logger(__name__)


def build_graph(
    *,
    checkpointer: BaseCheckpointSaver[str] | None = None,
    router_llm: Any | None = None,
    retriever: Retriever | None = None,
    research_agent: ResearchAgent | None = None,
    deepagent_runner: DeepAgentRunner | None = None,
    document_analysis_runner: DocumentAnalysisRunner | None = None,
) -> Any:
    graph = StateGraph(CognitiveState)
    active_router_llm = router_llm
    active_retriever = retriever or _default_retriever
    active_research_agent = research_agent or ResearchAgent()
    active_deepagent_runner = deepagent_runner or run_deepagent_task
    active_document_analysis_runner = document_analysis_runner or _run_document_analysis_sync

    graph.add_node("router", lambda state: router_node(state, router_llm=active_router_llm))
    graph.add_node(
        "retrieve_context",
        lambda state: retrieve_context_node(state, retriever=active_retriever),
    )
    graph.add_node(
        "research",
        lambda state: research_node(
            state,
            research_agent=active_research_agent,
            deepagent_runner=active_deepagent_runner,
        ),
    )
    graph.add_node(
        "legal",
        lambda state: legal_node(state, document_analysis_runner=active_document_analysis_runner),
    )
    graph.add_node("comm", comm_node)
    graph.add_node("social", social_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("final_response", final_response_node)
    graph.add_node("error", error_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _after_router,
        {
            "human_review": "human_review",
            "retrieve_context": "retrieve_context",
            "error": "error",
        },
    )
    graph.add_conditional_edges(
        "retrieve_context",
        _route_after_retrieval,
        {
            "research": "research",
            "legal": "legal",
            "comm": "comm",
            "social": "social",
            "error": "error",
        },
    )
    for node_name in ("research", "legal", "comm", "social"):
        graph.add_conditional_edges(
            node_name,
            _after_agent_node,
            {"human_review": "human_review", "final_response": "final_response"},
        )
    graph.add_conditional_edges(
        "human_review",
        _after_human_review,
        {"retrieve_context": "retrieve_context", "final_response": "final_response"},
    )
    graph.add_edge("error", "final_response")
    graph.add_edge("final_response", END)

    return graph.compile(checkpointer=checkpointer)


def router_node(state: CognitiveState, *, router_llm: Any | None = None) -> CognitiveState:
    try:
        _require_thread_id(state)
        budget = _consume_budget(state, estimated_tokens=_estimate_state_tokens(state))
        if budget.used_tokens > budget.max_tokens:
            return {
                "budget": budget,
                "pending_human_review": HumanReviewItem(
                    reason="Budget exceeded before routing.",
                    risk_level=ToolRiskLevel.MEDIUM,
                    proposed_action="Approve additional budget or edit the request.",
                ),
            }
        # Explicit doc_ids attached to the request are an unambiguous signal that
        # the user wants document-grounded analysis, bypass LLM/keyword guess.
        if state.get("requested_doc_ids"):
            return {
                "active_route": "legal",
                "budget": budget,
                "pending_human_review": None,
                "route_reason": "Explicit doc_ids supplied; routing to document analysis.",
            }
        decision = route_request(state, router_llm=router_llm)
        pending_review = None
        if decision.needs_human_review:
            pending_review = HumanReviewItem(
                reason=decision.reason,
                risk_level=ToolRiskLevel.MEDIUM,
                proposed_action=f"Route request to {decision.route}",
            )
        return {
            "active_route": decision.route,
            "budget": budget,
            "pending_human_review": pending_review,
            "route_reason": decision.reason,
        }
    except Exception as exc:
        return _error_state(state, exc)


def route_request(state: CognitiveState, *, router_llm: Any | None = None) -> RouterDecision:
    messages = state.get("messages", [])
    latest_text = _latest_user_text(messages)
    llm = router_llm
    if llm is None:
        # The router uses `with_structured_output`, which forces a
        # `tool_choice`. Some models (notably reasoner-only endpoints like
        # DeepSeek's `deepseek-v4-pro`) return HTTP 400 when forced
        # tool_choice is set — so we start from the dedicated agent lane
        # (`gpt-5.5` via the operator's gateway in the current chain) and
        # fall back to secondary/primary as plain models, then to a
        # deterministic regex router as last resort.
        try:
            llm = create_agent_chat_model()
        except Exception:
            try:
                llm = create_secondary_chat_model()
            except Exception:
                try:
                    llm = create_primary_chat_model()
                except Exception:
                    return deterministic_route(latest_text)

    try:
        structured = llm.with_structured_output(RouterDecision)
        decision = structured.invoke(
            [
                (
                    "system",
                    "Route the user request to one of: research, legal, comm, social. "
                    "Use needs_human_review for sensitive or high-risk requests.",
                ),
                ("human", latest_text),
            ]
        )
        if isinstance(decision, RouterDecision):
            return decision
        return RouterDecision.model_validate(decision)
    except Exception:
        return deterministic_route(latest_text)


def deterministic_route(text: str) -> RouterDecision:
    lowered = text.lower()
    route: Literal["research", "legal", "comm", "social"]
    legal_keywords = (
        "legal",
        "ley",
        "contrato",
        "articulo",
        "artículo",
        "analiza documentos",
        "matriz hecho",
        "matriz evidencia",
        "hecho evidencia",
        "evidencia cita",
        "evidencia/cita",
        "contradicciones",
        "linea de tiempo",
        "línea de tiempo",
        "resumen del caso",
        "borrador con citas",
    )
    # `comm`/`social` require an explicit *action intent*, not just a topic
    # noun. Pre-Fase 74 a plain informational message that merely mentioned
    # "mensaje" or "telegram" (e.g. "qué mensajes tengo") was misrouted to
    # `comm`, which triggers a human-review interrupt. Now we demand a verb
    # that signals the operator wants something SENT/DRAFTED. Pure questions
    # fall through to `research`, which answers directly without interrupt.
    comm_action = (
        "redact",
        "enviá",
        "envia",
        "enviar",
        "mandá",
        "manda",
        "mandar",
        "responder",
        "respondé",
        "contestá",
        "contestar",
        "escrib",
        "prepar",
        "armá",
        "arma",
        "armar",
        "creá",
        "crea",
        "crear",
    )
    social_action = (
        "publicá",
        "publica",
        "publicar",
        "postear",
        "posteá",
        "tuiteá",
        "tweet",
        "prepar",
        "armá",
        "arma",
        "armar",
        "creá",
        "crea",
        "crear",
        "escrib",
    )
    mentions_comm = any(
        k in lowered for k in ("email", "correo", "mail", "comunica", "mensaje", "telegram")
    )
    mentions_social = any(
        k in lowered for k in ("social", "post", "twitter", "linkedin", "instagram")
    )
    if any(keyword in lowered for keyword in legal_keywords):
        route = "legal"
    elif mentions_comm and any(verb in lowered for verb in comm_action):
        route = "comm"
    elif mentions_social and any(verb in lowered for verb in social_action):
        route = "social"
    else:
        route = "research"

    needs_review = any(keyword in lowered for keyword in ("enviar", "publicar", "delete", "borrar"))
    return RouterDecision(
        route=route,
        confidence=0.55,
        reason="Deterministic keyword fallback.",
        needs_human_review=needs_review,
    )


def retrieve_context_node(state: CognitiveState, *, retriever: Retriever) -> CognitiveState:
    try:
        query = _latest_user_text(state.get("messages", []))
        contexts = retriever(query)
        citations = [
            RetrievalCitation(
                source_path=context.metadata.get("source_path", context.citation.split(":", 1)[0]),
                page_start=int(context.metadata.get("page_start", 1)),
                page_end=int(context.metadata.get("page_end", 1)),
                quote=context.text,
                doc_id=str(context.metadata.get("doc_id", "")) or None,
                chunk_id=str(context.metadata.get("chunk_id", "")) or None,
            )
            for context in contexts
        ]
        return {"retrieved_context": citations}
    except Exception as exc:
        return _error_state(state, exc)


def research_node(
    state: CognitiveState,
    *,
    research_agent: ResearchAgent | None = None,
    deepagent_runner: DeepAgentRunner | None = None,
) -> CognitiveState:
    try:
        query = _latest_user_text(state.get("messages", []))

        thread_tid = state.get("thread_id", "missing-thread")
        deep_task_id = f"{state.get('thread_id', 'thread')}-research"
        web_ok = settings.web_search_enabled
        oh_prelude: str | None = None

        if settings.enable_openharness_research:
            from cognitive_os.integrations.openharness_research import (
                is_openharness_available,
                resolve_openharness_cwd,
                run_openharness_research_sync,
            )

            if is_openharness_available():
                oh_cwd = resolve_openharness_cwd(settings, thread_tid, deep_task_id)
                oh_result = run_openharness_research_sync(
                    settings,
                    query,
                    workspace_root=oh_cwd,
                    thread_id=thread_tid,
                    task_id=deep_task_id,
                    web_allowed=web_ok,
                )
                oh_text = (oh_result.answer or "").strip()
                if oh_result.ok and oh_text:
                    if settings.openharness_research_pipeline == "short_circuit":
                        return {
                            "agent_result": AgentResult(
                                route="research",
                                content=oh_result.answer,
                                citations=[],
                                uncertainty="OpenHarness QueryEngine (restricted tools).",
                            ),
                        }
                    oh_prelude = oh_text
                if oh_result.error:
                    log.warning("openharness_research_fallback", error=oh_result.error)
                elif oh_result.skipped_reason and oh_result.skipped_reason not in {
                    "disabled",
                    "empty_query",
                }:
                    log.info("openharness_skipped", reason=oh_result.skipped_reason)
            else:
                log.warning("openharness_enabled_but_package_missing")

        task_metadata: dict[str, Any] = {}
        if oh_prelude:
            task_metadata["openharness_prelude"] = oh_prelude

        task = DeepAgentTask(
            task_id=deep_task_id,
            thread_id=thread_tid,
            user_id=state.get("user_id"),
            task_type="research",
            query=query,
            web_allowed=web_ok,
            metadata=task_metadata,
        )
        runner = deepagent_runner or run_deepagent_task
        deep_result = runner(task)
        if deep_result.requested_external_actions:
            return {
                "pending_human_review": HumanReviewItem(
                    reason="DeepAgent requested external actions.",
                    risk_level=ToolRiskLevel.HIGH,
                    proposed_action="Review DeepAgent requested_external_actions",
                    payload={
                        "task_id": deep_result.task_id,
                        "actions": deep_result.requested_external_actions,
                    },
                ),
                "last_deepagent_result": deep_result.model_dump(),
            }
        # Surface deepagent result only when the answer is substantive. `status="ok"` with
        # an empty/whitespace answer means the agent reported success but produced nothing
        # (a known degradation path); in that case we must fall back to the deterministic
        # RAG agent instead of returning an empty bubble to the user.
        answer_text = (deep_result.answer or "").strip()
        if deep_result.status == "ok" and answer_text:
            return {
                "agent_result": AgentResult(
                    route="research",
                    content=deep_result.answer,
                    citations=[
                        _citation_from_deepagent(citation)
                        for citation in deep_result.citations
                        if citation.source_type in {"local_doc", "web"}
                    ],
                    uncertainty=(
                        "\n".join(deep_result.uncertainty_notes)
                        if deep_result.uncertainty_notes
                        else None
                    ),
                ),
                "last_deepagent_result": deep_result.model_dump(),
            }
        if deep_result.status in {"needs_more_info", "blocked"} and answer_text:
            # Agent communicated a meaningful state; surface it with explicit uncertainty.
            extra_uncertainty = (
                "DeepAgent status: needs_more_info; revise el alcance o adjunte mas evidencia."
                if deep_result.status == "needs_more_info"
                else "DeepAgent status: blocked by policy or missing capability."
            )
            uncertainty_notes = [*deep_result.uncertainty_notes, extra_uncertainty]
            return {
                "agent_result": AgentResult(
                    route="research",
                    content=deep_result.answer,
                    citations=[
                        _citation_from_deepagent(citation)
                        for citation in deep_result.citations
                        if citation.source_type in {"local_doc", "web"}
                    ],
                    uncertainty="\n".join(uncertainty_notes),
                ),
                "last_deepagent_result": deep_result.model_dump(),
            }

        agent = research_agent or _fallback_research_agent(state)
        report = agent.run(query, retrieved_context=state.get("retrieved_context", []))
        uncertainty = "\n".join(report.uncertainty_notes) if report.uncertainty_notes else None
        fallback_reason = {
            "failed": "DeepAgent failed",
            "ok": "DeepAgent returned empty answer",
            "needs_more_info": "DeepAgent returned empty answer (needs_more_info)",
            "blocked": "DeepAgent returned empty answer (blocked)",
        }.get(deep_result.status, f"DeepAgent status={deep_result.status}")
        content = f"{fallback_reason}; Cognitive OS used direct RAG fallback.\n\n{report.answer}"
        return {
            "agent_result": AgentResult(
                route="research",
                content=content,
                citations=report.citations,
                uncertainty=uncertainty,
            ),
            "last_research_report": report.model_dump(),
            "last_deepagent_result": deep_result.model_dump(),
        }
    except Exception as exc:
        try:
            query = _latest_user_text(state.get("messages", []))
            agent = research_agent or _fallback_research_agent(state)
            report = agent.run(query, retrieved_context=state.get("retrieved_context", []))
            uncertainty = "\n".join(report.uncertainty_notes) if report.uncertainty_notes else None
            return {
                "agent_result": AgentResult(
                    route="research",
                    content=(
                        "DeepAgent raised an exception; Cognitive OS used direct RAG fallback.\n\n"
                        f"{report.answer}"
                    ),
                    citations=report.citations,
                    uncertainty=uncertainty,
                ),
                "last_error": f"{type(exc).__name__}: {exc}",
                "error_count": state.get("error_count", 0) + 1,
            }
        except Exception as fallback_exc:
            return _error_state(state, fallback_exc)


def legal_node(
    state: CognitiveState,
    *,
    document_analysis_runner: DocumentAnalysisRunner | None = None,
) -> CognitiveState:
    query = _latest_user_text(state.get("messages", []))
    requested_doc_ids = list(state.get("requested_doc_ids") or [])
    if _looks_like_document_analysis(query) or requested_doc_ids:
        doc_ids = list(dict.fromkeys(requested_doc_ids + _doc_ids_from_request(query)))
        if not doc_ids:
            doc_ids = [
                citation.doc_id
                for citation in state.get("retrieved_context", [])
                if citation.doc_id is not None
            ]
        if not doc_ids:
            return {
                "agent_result": AgentResult(
                    route="legal",
                    content="Selecciona doc_ids autorizados para el analisis documental.",
                    uncertainty="No hay documentos autorizados en el request ni en el contexto.",
                )
            }
        task = DocumentAnalysisTask(
            task_id=f"{state.get('thread_id', 'thread')}-document-analysis",
            thread_id=state.get("thread_id", "missing-thread"),
            user_id=state.get("user_id"),
            case_id=state.get("case_id"),
            doc_ids=doc_ids,
            query=query,
            modes=_analysis_modes_from_request(query),
            require_human_review_for_drafts=True,
        )
        runner = document_analysis_runner or _run_document_analysis_sync
        result = runner(task)
        citations = [
            _citation_from_document_analysis(citation) for citation in result.citations[:8]
        ]
        if result.draft_sections:
            pending = HumanReviewItem(
                reason="Document analysis produced legal draft sections.",
                risk_level=ToolRiskLevel.HIGH,
                proposed_action="Review legal draft sections before use.",
                payload={"task_id": result.task_id, "draft_sections": list(result.draft_sections)},
            )
        else:
            pending = None
        return {
            "agent_result": AgentResult(
                route="legal",
                content=(
                    f"{result.executive_summary}\n\n"
                    f"Reportes: {', '.join(result.generated_files) or 'sin archivos'}"
                    + ("\n\nRequiere revision humana." if result.human_review_required else "")
                ),
                citations=citations,
                uncertainty="\n".join(result.uncertainty_notes) or None,
            ),
            "pending_human_review": pending,
            "last_document_analysis_result": result.model_dump(mode="json"),
        }
    citations = state.get("retrieved_context", [])
    uncertainty = None if citations else "No citations were retrieved; legal certainty is limited."
    return _placeholder_result(
        state,
        route="legal",
        content="Legal placeholder completed with citation-aware context.",
        uncertainty=uncertainty,
    )


def comm_node(state: CognitiveState) -> CognitiveState:
    """Generate a draft message and require human approval before sending.

    Cognitive OS never sends email/Telegram autonomously: it produces a
    citation-grounded draft via the primary LLM and surfaces it as a
    `HumanReviewItem`. Even when `enable_email_send=True`, the user has to
    approve via `/threads/{id}/resume` before any external action runs.
    """
    query = _latest_user_text(state.get("messages", []))
    citations = state.get("retrieved_context", [])
    draft = _draft_communication(query, citations)
    channel = _detect_channel(query)
    policy = state.get("tool_policy") or ToolPolicy()
    requires_review = policy.require_human_approval_for_external_actions or not _channel_enabled(
        channel
    )
    pending = (
        HumanReviewItem(
            reason=(
                f"Outbound {channel} draft needs human approval before sending; "
                "the system never executes external comms autonomously."
            ),
            risk_level=ToolRiskLevel.HIGH,
            proposed_action=f"send_{channel}",
            payload={
                "channel": channel,
                "draft": draft,
                "requires_external_credentials": not _channel_enabled(channel),
            },
        )
        if requires_review
        else None
    )
    return {
        "agent_result": AgentResult(
            route="comm",
            content=draft,
            citations=list(citations),
            uncertainty=(
                "Borrador generado; sin envio real hasta que se apruebe via /threads/{id}/resume."
                if requires_review
                else None
            ),
        ),
        "pending_human_review": pending,
    }


def social_node(state: CognitiveState) -> CognitiveState:
    """Generate a social-post draft and require approval before publishing."""
    query = _latest_user_text(state.get("messages", []))
    citations = state.get("retrieved_context", [])
    platform = _detect_platform(query)
    draft = _draft_social_post(query, citations, platform=platform)
    policy = state.get("tool_policy") or ToolPolicy()
    requires_review = (
        policy.require_human_approval_for_external_actions or not settings.enable_social_posting
    )
    pending = (
        HumanReviewItem(
            reason=(
                f"Outbound {platform} post needs human approval; the system never "
                "publishes social content autonomously."
            ),
            risk_level=ToolRiskLevel.HIGH,
            proposed_action=f"post_{platform}",
            payload={
                "platform": platform,
                "draft": draft,
                "requires_external_credentials": not settings.enable_social_posting,
            },
        )
        if requires_review
        else None
    )
    return {
        "agent_result": AgentResult(
            route="social",
            content=draft,
            citations=list(citations),
            uncertainty=(
                "Borrador generado; sin publicacion real hasta que se apruebe via "
                "/threads/{id}/resume."
                if requires_review
                else None
            ),
        ),
        "pending_human_review": pending,
    }


def _detect_channel(text: str) -> str:
    lowered = text.lower()
    if "telegram" in lowered:
        return "telegram"
    if "whatsapp" in lowered:
        return "whatsapp"
    if "slack" in lowered:
        return "slack"
    return "email"


def _detect_platform(text: str) -> str:
    lowered = text.lower()
    if "linkedin" in lowered:
        return "linkedin"
    if "twitter" in lowered or " x " in f" {lowered} ":
        return "twitter"
    if "instagram" in lowered:
        return "instagram"
    return "social"


def _channel_enabled(channel: str) -> bool:
    if channel == "email":
        return settings.enable_email_send
    if channel == "telegram":
        return settings.telegram_enabled
    return False


def _draft_communication(query: str, citations: Sequence[RetrievalCitation]) -> str:
    cites = "\n".join(f"- {c.citation}" for c in list(citations)[:5]) or "- ninguna"
    fallback = (
        "Hola,\n\n"
        f"En relación a: {query.strip()[:600]}\n\n"
        "[Borrador generado automáticamente. Editar y aprobar antes de enviar.]\n\n"
        f"Fuentes consultadas:\n{cites}"
    )
    try:
        llm = create_primary_chat_model()
    except Exception:
        return fallback
    try:
        result = llm.invoke(
            [
                (
                    "system",
                    "Eres un asistente que redacta comunicaciones profesionales y "
                    "concisas. No inventes hechos; si la solicitud requiere datos "
                    "que no estan en las fuentes, indica que faltan. Devuelve solo "
                    "el cuerpo del mensaje, sin meta-comentarios.",
                ),
                (
                    "human",
                    f"Solicitud: {query}\n\nFuentes disponibles:\n{cites}\n\n"
                    "Redacta un borrador claro y editable (5-10 lineas).",
                ),
            ]
        )
    except Exception:
        return fallback
    content = getattr(result, "content", result)
    return str(content) if content else fallback


def _draft_social_post(
    query: str,
    citations: Sequence[RetrievalCitation],
    *,
    platform: str,
) -> str:
    cites = "\n".join(f"- {c.citation}" for c in list(citations)[:3]) or "- ninguna"
    fallback = (
        f"[{platform.upper()}] {query.strip()[:240]}\n\n"
        "[Borrador automatico. Editar y aprobar antes de publicar.]\n\n"
        f"Fuentes:\n{cites}"
    )
    char_budget = 240 if platform == "twitter" else 600
    try:
        llm = create_primary_chat_model()
    except Exception:
        return fallback
    try:
        result = llm.invoke(
            [
                (
                    "system",
                    f"Eres un asistente que redacta posts para {platform}. "
                    f"Mantente bajo {char_budget} caracteres, no inventes hechos, "
                    "no incluyas hashtags si la solicitud no los pide. Devuelve solo "
                    "el texto del post.",
                ),
                (
                    "human",
                    f"Tema: {query}\n\nFuentes disponibles:\n{cites}\n\n"
                    f"Redacta un post para {platform}.",
                ),
            ]
        )
    except Exception:
        return fallback
    content = getattr(result, "content", result)
    return str(content) if content else fallback


def human_review_node(state: CognitiveState) -> CognitiveState:
    pending = state.get("pending_human_review")
    if pending is None:
        return {}

    decision = interrupt(
        {
            "reason": pending.reason,
            "risk_level": pending.risk_level,
            "proposed_action": pending.proposed_action,
            "payload": pending.payload,
        }
    )
    action = str(decision.get("action", "reject")).lower()
    if action == "approve":
        _record_approval_event(state, "approved")
        return {"pending_human_review": None}
    if action == "edit":
        edited_text = str(decision.get("message", ""))
        _record_approval_event(state, "edited")
        return {
            "messages": [HumanMessage(content=edited_text)],
            "pending_human_review": None,
            "active_route": "research",
        }
    _record_approval_event(state, "rejected")
    return {
        "pending_human_review": None,
        "agent_result": AgentResult(
            route=state.get("active_route", "unknown"),
            content="Request rejected by human reviewer.",
            uncertainty="Human reviewer rejected the pending action.",
        ),
    }


def final_response_node(state: CognitiveState) -> CognitiveState:
    result = state.get("agent_result")
    if result is None:
        result = AgentResult(
            route=state.get("active_route", "unknown"),
            content="No agent result was produced.",
            uncertainty=state.get("last_error"),
        )
    citations = "\n".join(f"- {citation.citation}" for citation in result.citations)
    content = result.content if not citations else f"{result.content}\n\n**Fuentes:**\n{citations}"
    return {"messages": [AIMessage(content=content)], "agent_result": result}


def error_node(state: CognitiveState) -> CognitiveState:
    error = state.get("last_error") or "Unknown graph error."
    return {
        "agent_result": AgentResult(
            route="error",
            content="The orchestrator recovered from an internal error.",
            uncertainty=error,
        )
    }


def _placeholder_result(
    state: CognitiveState,
    *,
    route: str,
    content: str,
    uncertainty: str | None = None,
) -> CognitiveState:
    citations = state.get("retrieved_context", [])
    return {
        "agent_result": AgentResult(
            route=route,
            content=content,
            citations=citations,
            uncertainty=uncertainty,
        )
    }


def _fallback_research_agent(state: CognitiveState) -> ResearchAgent:
    if state.get("retrieved_context"):
        return ResearchAgent()
    return ResearchAgent(tools=ReadOnlyResearchTools(local_search=lambda query: []))


def _citation_from_deepagent(citation: DeepAgentCitation) -> RetrievalCitation:
    return RetrievalCitation(
        source_path=citation.title or citation.url or "",
        page_start=citation.page_start or 0,
        page_end=citation.page_end or citation.page_start or 0,
        quote=citation.quote,
        doc_id=citation.doc_id,
        chunk_id=citation.chunk_id,
        url=citation.url,
        title=citation.title,
    )


def _citation_from_document_analysis(citation: object) -> RetrievalCitation:
    return RetrievalCitation(
        source_path=getattr(citation, "source_path", None) or "",
        page_start=getattr(citation, "page_start", 0),
        page_end=getattr(citation, "page_end", 0),
        quote=getattr(citation, "quote", None),
        doc_id=getattr(citation, "doc_id", None),
        chunk_id=getattr(citation, "chunk_id", None),
    )


def _looks_like_document_analysis(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "analiza estos documentos",
            "analiza documentos",
            "matriz hecho",
            "matriz evidencia",
            "hecho evidencia",
            "evidencia cita",
            "evidencia/cita",
            "contradicciones",
            "línea de tiempo",
            "linea de tiempo",
            "resumen del caso",
            "borrador con citas",
        )
    )


def _analysis_modes_from_request(text: str) -> list[DocumentAnalysisMode]:
    lowered = text.lower()
    modes: list[DocumentAnalysisMode] = []
    if "matriz" in lowered or "evidencia" in lowered:
        modes.append("evidence_matrix")
    if "timeline" in lowered or "línea de tiempo" in lowered or "linea de tiempo" in lowered:
        modes.append("timeline")
    if "contradic" in lowered:
        modes.append("contradictions")
    if "borrador" in lowered:
        modes.append("legal_draft_support")
    if "resumen" in lowered:
        modes.append("case_summary")
    return modes or ["full_report"]


def _doc_ids_from_request(text: str) -> list[str]:
    explicit = re.findall(r"doc[_-]?id\s*[:=]\s*([A-Za-z0-9_-]+)", text, flags=re.I)
    uuids = re.findall(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        text,
    )
    return list(dict.fromkeys([*explicit, *uuids]))


def _run_document_analysis_sync(task: DocumentAnalysisTask) -> DocumentAnalysisResult:
    return asyncio.run(DocumentAnalysisService().run_analysis(task))


def _after_router(state: CognitiveState) -> str:
    if state.get("last_error"):
        return "error"
    if state.get("pending_human_review") is not None:
        return "human_review"
    return "retrieve_context"


def _route_after_retrieval(state: CognitiveState) -> str:
    if state.get("last_error"):
        return "error"
    route = state.get("active_route", "research")
    return route if route in {"research", "legal", "comm", "social"} else "research"


def _after_agent_node(state: CognitiveState) -> str:
    if state.get("pending_human_review") is not None:
        return "human_review"
    return "final_response"


def _after_human_review(state: CognitiveState) -> str:
    if state.get("agent_result") is not None:
        return "final_response"
    return "retrieve_context"


def _require_thread_id(state: CognitiveState) -> None:
    if not state.get("thread_id"):
        msg = "thread_id is required for persistent orchestration."
        raise ValueError(msg)


def _consume_budget(state: CognitiveState, *, estimated_tokens: int) -> BudgetState:
    budget = state.get("budget") or BudgetState()
    return budget.model_copy(update={"used_tokens": budget.used_tokens + estimated_tokens})


def _estimate_state_tokens(state: CognitiveState) -> int:
    text = _latest_user_text(state.get("messages", []))
    return max(1, len(text.split()) + 20)


def _latest_user_text(messages: Sequence[BaseMessage]) -> str:
    for message in reversed(messages):
        if message.type == "human":
            return str(message.content)
    if messages:
        return str(messages[-1].content)
    return ""


def _error_state(state: CognitiveState, exc: Exception) -> CognitiveState:
    return {
        "last_error": f"{type(exc).__name__}: {exc}",
        "error_count": state.get("error_count", 0) + 1,
    }


def _record_approval_event(state: CognitiveState, decision: str) -> None:
    """Emit an audit record so approval patterns are visible in the audit log."""
    with suppress(Exception):
        record_audit_event(
            ToolAuditRecord(
                tool_name="cognitive_os.human_review",
                risk_level=PolicyToolRiskLevel.EXTERNAL_ACTION,
                args_redacted={
                    "decision": decision,
                    "thread_id": state.get("thread_id"),
                    "route": state.get("active_route"),
                },
                result_summary=decision,
                actor_id=state.get("user_id"),
            )
        )


def _default_retriever(query: str) -> list[RetrievedContext]:
    return retrieve_context(query)


def postgres_sync_dsn() -> str:
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@contextmanager
def postgres_checkpointer(
    *,
    min_size: int = 1,
    max_size: int = 8,
) -> Iterator[PostgresSaver]:
    """Yield a `PostgresSaver` backed by a `psycopg_pool.ConnectionPool`.

    The pool keeps `min_size` connections warm and elastically scales up to
    `max_size` for concurrent FastAPI/`to_thread` workers, replacing the old
    single-connection design that serialized all checkpoint writes.
    """
    pool: ConnectionPool[Connection[DictRow]] = ConnectionPool(
        conninfo=postgres_sync_dsn(),
        min_size=min_size,
        max_size=max_size,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=False,
    )
    pool.open(wait=True)
    try:
        saver = PostgresSaver(conn=pool)
        saver.setup()
        yield saver
    finally:
        pool.close()


@asynccontextmanager
async def async_postgres_checkpointer() -> Any:
    async with AsyncPostgresSaver.from_conn_string(postgres_sync_dsn()) as saver:
        await saver.setup()
        yield saver


def resume_graph(
    compiled_graph: Any,
    *,
    thread_id: str,
    action: str,
    message: str | None = None,
) -> Any:
    payload = {"action": action}
    if message is not None:
        payload["message"] = message
    return compiled_graph.invoke(
        Command(resume=payload),
        config={"configurable": {"thread_id": thread_id}},
    )


_AGENT_SELF_MESSAGE_ID = "agent_self_system_prompt"

# Resolved from this file's location, not from CWD, so the loader works the
# same from API processes, Celery workers and the Telegram bot.
_AGENT_SELF_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent / "docs" / "AGENT_SELF.md"
)


def load_agent_self_prompt() -> str:
    """Return the content of `docs/AGENT_SELF.md` or "" when missing.

    Read on every call so the operator can edit the file and have the next
    `initial_state()` pick the new identity up without restarting the API.
    A missing file is non-fatal — the orchestrator just runs without the
    self-identity system message (back to pre-Fase 70 behavior).
    """
    try:
        return _AGENT_SELF_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except OSError:
        return ""


def initial_state(
    message: str,
    *,
    thread_id: str,
    user_id: str = "local-user",
    doc_ids: list[str] | None = None,
    case_id: str | None = None,
) -> CognitiveState:
    # SystemMessage with a stable id so `add_messages` upserts (does not
    # duplicate) on subsequent turns of the same thread. If the operator edits
    # docs/AGENT_SELF.md the next initial_state() reload picks the new content
    # up; LangGraph replaces the old SystemMessage in-place by id.
    messages: list[Any] = []
    agent_self = load_agent_self_prompt()
    if agent_self:
        messages.append(SystemMessage(content=agent_self, id=_AGENT_SELF_MESSAGE_ID))
    messages.append(HumanMessage(content=message))
    state: CognitiveState = {
        "messages": messages,
        "thread_id": thread_id,
        "user_id": user_id,
        "budget": BudgetState(),
        "tool_policy": ToolPolicy(
            readonly_mode=settings.tools_readonly_mode,
            require_human_approval_for_external_actions=(
                settings.require_human_approval_for_external_actions
            ),
        ),
        "error_count": 0,
    }
    if doc_ids:
        state["requested_doc_ids"] = list(doc_ids)
    if case_id is not None:
        state["case_id"] = case_id
    return state


def cast_state(value: Any) -> CognitiveState:
    return cast(CognitiveState, value)

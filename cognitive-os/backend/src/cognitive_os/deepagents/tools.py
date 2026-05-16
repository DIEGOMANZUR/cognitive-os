from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Iterable, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from langchain_core.tools import StructuredTool
from sqlalchemy import select

from cognitive_os.actions.calendar import CalendarError, CalendarService, ListEventsRequest
from cognitive_os.actions.captcha import (
    CaptchaKind,
    CaptchaSolverError,
    CaptchaSolverService,
)
from cognitive_os.actions.drive import DriveError, DriveSearchRequest, DriveService
from cognitive_os.actions.kimi_webbridge import (
    KimiWebBridgeError,
    KimiWebBridgeService,
    NavigateRequest,
    ScreenshotRequest,
    SnapshotRequest,
)
from cognitive_os.actions.maps import MapsError, MapsService, TravelMode
from cognitive_os.agents.web_search import (
    WebSearchClient,
    build_default_web_search_client,
)
from cognitive_os.assist.note_index import NoteIndexService
from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import Document, DocumentPage
from cognitive_os.deepagents.memory_schemas import DeepAgentMemoryProposal, DeepAgentMemoryScope
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService
from cognitive_os.deepagents.policies import (
    DeepAgentPolicyViolation,
    validate_tool_allowed,
    validate_workspace_path,
)
from cognitive_os.deepagents.schemas import DeepAgentToolPolicy, DeepAgentWorkspace
from cognitive_os.deepagents.skills_registry import DeepAgentSkillsRegistry
from cognitive_os.ingestion.neo4j import Neo4jGraphReader, _build_default_neo4j_reader
from cognitive_os.memory.retrieval import RetrievedContext, retrieve_context
from cognitive_os.memory.web_indexer import index_web_results_async
from cognitive_os.tools.policy import ToolAuditRecord, ToolRiskLevel, record_audit_event

MAX_DOCUMENT_PAGES_PER_CALL = 20
MAX_LOCAL_DOC_RESULTS_PER_CALL = 20
MAX_WEB_RESULTS_PER_CALL = 20
MAX_WORKSPACE_FILE_BYTES = 2 * 1024 * 1024
LocalRetriever = Callable[[str], list[RetrievedContext]]


def build_deepagent_tools(
    *,
    policy: DeepAgentToolPolicy,
    workspace: DeepAgentWorkspace,
    local_retriever: LocalRetriever = retrieve_context,
    allowed_doc_ids: Sequence[str] | None = None,
    user_id: str | None = None,
    maps_service: MapsService | None = None,
    calendar_service: CalendarService | None = None,
    drive_service: DriveService | None = None,
    note_index: NoteIndexService | None = None,
    webbridge_service: KimiWebBridgeService | None = None,
    captcha_service: CaptchaSolverService | None = None,
) -> list[StructuredTool]:
    """Build the controlled DeepAgent tool list.

    `allowed_doc_ids` enforces the per-task document allow-list inside
    `read_document_pages`: an empty/None list means "no doc_id is readable"
    rather than "all doc_ids are readable", so callers MUST pass the task's
    `allowed_doc_ids` to enable reads.

    Personal-assistant tools (`search_notes`, `list_calendar_events`,
    `search_drive_files`, `plan_route`, `geocode_address`) are read-only and
    delegate capability gating to the underlying services; they return a
    controlled error dict when a service is `disabled`/`blocked` instead of
    raising. `user_id` scopes note search to a single owner.
    """
    permitted_doc_ids = frozenset(allowed_doc_ids or ())
    resolved_maps = maps_service or MapsService()
    resolved_calendar = calendar_service or CalendarService()
    resolved_drive = drive_service or DriveService()
    resolved_notes = note_index or NoteIndexService()
    resolved_webbridge = webbridge_service or KimiWebBridgeService()
    resolved_captcha = captcha_service or CaptchaSolverService()
    tools: list[StructuredTool] = [
        StructuredTool.from_function(
            func=lambda query, limit=8: search_local_docs(
                query,
                limit=limit,
                policy=policy,
                local_retriever=local_retriever,
            ),
            name="search_local_docs",
            description=(
                "Busca en documentos locales ingeridos (excluye snippets re-indexados desde "
                "la web) y devuelve citas trazables."
            ),
        ),
        StructuredTool.from_function(
            func=lambda doc_id, page_start, page_end: read_document_pages(
                doc_id,
                page_start,
                page_end,
                policy=policy,
                allowed_doc_ids=permitted_doc_ids,
            ),
            name="read_document_pages",
            description="Lee paginas ya ingeridas desde Postgres por doc_id y rango.",
        ),
        StructuredTool.from_function(
            func=lambda question: graph_query_readonly(question, policy=policy),
            name="graph_query_readonly",
            description="Consulta segura y predefinida contra el grafo; no acepta Cypher libre.",
        ),
        StructuredTool.from_function(
            func=lambda query: search_web(query, policy=policy),
            name="search_web",
            description="Busqueda web solo si esta habilitada por configuracion y politica.",
        ),
        StructuredTool.from_function(
            func=lambda relative_path, content: write_workspace_file(
                relative_path,
                content,
                policy=policy,
                workspace=workspace,
            ),
            name="write_workspace_file",
            description="Escribe archivos solo dentro del workspace temporal controlado.",
        ),
        StructuredTool.from_function(
            func=lambda: list_available_skills(),
            name="list_available_skills",
            description="Lista skills habilitadas para DeepAgents bajo politica Cognitive OS.",
        ),
        StructuredTool.from_function(
            func=lambda skill_name: read_skill(skill_name),
            name="read_skill",
            description="Lee una skill habilitada por nombre sin aceptar rutas arbitrarias.",
        ),
        StructuredTool.from_function(
            func=lambda scope, query: get_relevant_memory(scope, query),
            name="get_relevant_memory",
            description="Devuelve memoria persistente relevante, filtrada y redactada.",
        ),
        StructuredTool.from_function(
            func=lambda kind, content, reason, scope: propose_memory_update(
                kind,
                content,
                reason,
                scope,
            ),
            name="propose_memory_update",
            description="Propone memoria nueva; nunca aplica cambios directos.",
        ),
        StructuredTool.from_function(
            func=lambda origin, destination, travel_mode="driving": plan_route(
                origin,
                destination,
                travel_mode=travel_mode,
                policy=policy,
                maps_service=resolved_maps,
            ),
            name="plan_route",
            description=(
                "Planifica una ruta entre dos direcciones via Google Maps Routes API "
                "(modo: driving|walking|bicycling|transit). Read-only."
            ),
        ),
        StructuredTool.from_function(
            func=lambda address: geocode_address(
                address,
                policy=policy,
                maps_service=resolved_maps,
            ),
            name="geocode_address",
            description="Convierte una direccion textual en lat/lng via Geocoding API. Read-only.",
        ),
        StructuredTool.from_function(
            func=lambda days_ahead=7, max_results=10: list_calendar_events(
                days_ahead=days_ahead,
                max_results=max_results,
                policy=policy,
                calendar_service=resolved_calendar,
            ),
            name="list_calendar_events",
            description=(
                "Lista los próximos eventos del calendario primario (Google Calendar). "
                "Read-only, ventana N días hacia adelante."
            ),
        ),
        StructuredTool.from_function(
            func=lambda query="", max_results=10: search_drive_files(
                query=query,
                max_results=max_results,
                policy=policy,
                drive_service=resolved_drive,
            ),
            name="search_drive_files",
            description=(
                "Busca archivos en Google Drive del usuario por nombre. Read-only, ordenado "
                "por modificado más reciente."
            ),
        ),
        StructuredTool.from_function(
            func=lambda query, limit=10: search_notes(
                query=query,
                limit=limit,
                user_id=user_id,
                policy=policy,
                note_index=resolved_notes,
            ),
            name="search_notes",
            description=(
                "Busca notas personales del usuario (PersonalNote) por similitud semántica. "
                "Aislada por user_id; read-only."
            ),
        ),
        StructuredTool.from_function(
            func=lambda url, session=None: browse_real_navigate(
                url=url,
                session=session,
                policy=policy,
                webbridge_service=resolved_webbridge,
                user_id=user_id,
            ),
            name="browse_real_navigate",
            description=(
                "Abre una URL en el navegador real del usuario via Kimi WebBridge. "
                "Sólo dominios en KIMI_WEBBRIDGE_ALLOWED_DOMAINS."
            ),
        ),
        StructuredTool.from_function(
            func=lambda session=None: browse_real_snapshot(
                session=session,
                policy=policy,
                webbridge_service=resolved_webbridge,
                user_id=user_id,
            ),
            name="browse_real_snapshot",
            description=(
                "Lee el árbol de accesibilidad de la pestaña activa (texto). "
                "Read-only. Devuelve refs @e usables por click/fill."
            ),
        ),
        StructuredTool.from_function(
            func=lambda session=None, fmt="png": browse_real_screenshot(
                session=session,
                fmt=fmt,
                policy=policy,
                webbridge_service=resolved_webbridge,
                user_id=user_id,
            ),
            name="browse_real_screenshot",
            description=(
                "Captura screenshot de la pestaña activa via Kimi WebBridge. "
                "Read-only. Devuelve solo metadata (no base64 inline)."
            ),
        ),
        StructuredTool.from_function(
            func=lambda image_base64: solve_image_captcha(
                image_base64=image_base64,
                policy=policy,
                captcha_service=resolved_captcha,
                user_id=user_id,
            ),
            name="solve_image_captcha",
            description=(
                "Resuelve un captcha de imagen (texto distorsionado) con CapSolver. "
                "Pasa el PNG/JPEG en base64; devuelve el texto reconocido para "
                "escribirlo en el formulario."
            ),
        ),
        StructuredTool.from_function(
            func=lambda kind, website_url, website_key, page_action=None: solve_token_captcha(
                kind=kind,
                website_url=website_url,
                website_key=website_key,
                page_action=page_action,
                policy=policy,
                captcha_service=resolved_captcha,
                user_id=user_id,
            ),
            name="solve_token_captcha",
            description=(
                "Resuelve reCAPTCHA v2/v3, hCaptcha o Cloudflare Turnstile con "
                "CapSolver. kind ∈ {recaptcha_v2,recaptcha_v3,hcaptcha,turnstile}; "
                "necesita website_url y website_key (sitekey). Devuelve el token "
                "para inyectarlo en la página y continuar la navegación."
            ),
        ),
    ]
    return tools


def search_local_docs(
    query: str,
    limit: int = 8,
    *,
    policy: DeepAgentToolPolicy,
    local_retriever: LocalRetriever = retrieve_context,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {"query_length": len(query), "limit": limit}
    try:
        validate_tool_allowed("search_local_docs", policy)
        bounded_limit = _bounded_int(
            limit,
            name="limit",
            minimum=1,
            maximum=MAX_LOCAL_DOC_RESULTS_PER_CALL,
        )
        # `retrieve_context` accepts an `exclude_doc_types` kwarg; the default retriever
        # honours it. Custom retrievers passed by tests may not — we degrade gracefully
        # to "no exclusion" rather than crashing search.
        try:
            contexts = local_retriever(query, exclude_doc_types=("web",))[:bounded_limit]  # type: ignore[call-arg]
        except TypeError:
            contexts = local_retriever(query)[:bounded_limit]
        citations = [_citation_from_context(context) for context in contexts]
        _audit("search_local_docs", {**args_redacted, "limit": bounded_limit})
        return {
            "results": [
                {
                    "text": context.text,
                    "score": context.score,
                    "doc_id": context.metadata.get("doc_id"),
                    "chunk_id": context.metadata.get("chunk_id"),
                    "page_start": context.metadata.get("page_start"),
                    "page_end": context.metadata.get("page_end"),
                    "doc_type": context.metadata.get("doc_type"),
                }
                for context in contexts
            ],
            "citations": citations,
            "warnings": [],
        }
    except Exception as exc:
        return _controlled_error("search_local_docs", args_redacted, exc)


def read_document_pages(
    doc_id: str,
    page_start: int,
    page_end: int,
    *,
    policy: DeepAgentToolPolicy,
    allowed_doc_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {
        "doc_id": doc_id,
        "page_start": page_start,
        "page_end": page_end,
    }
    try:
        validate_tool_allowed("read_document_pages", policy)
        start = _coerce_int(page_start, name="page_start")
        end = _coerce_int(page_end, name="page_end")
        if start < 1 or end < 1 or end < start:
            _audit_error(
                "read_document_pages",
                args_redacted,
                "invalid_page_range",
            )
            return {"error": "invalid_page_range", "pages": []}
        if end - start + 1 > MAX_DOCUMENT_PAGES_PER_CALL:
            _audit_error(
                "read_document_pages",
                args_redacted,
                "too_many_pages",
            )
            return {"error": "too_many_pages", "max_pages": MAX_DOCUMENT_PAGES_PER_CALL}
        # Enforce per-task allow-list: callers (the factory) supply the DeepAgentTask's
        # `allowed_doc_ids`. An empty list explicitly means "no doc is readable" — the
        # tool refuses rather than defaulting to "all docs", which would leak any UUID
        # an agent guesses.
        allowed_set = frozenset(allowed_doc_ids or ())
        if not allowed_set or doc_id not in allowed_set:
            _audit_error(
                "read_document_pages",
                args_redacted,
                "doc_id_not_authorized",
            )
            return {
                "error": "doc_id_not_authorized",
                "detail": (
                    "doc_id is not in the task's allowed_doc_ids; the agent cannot read pages "
                    "outside its assignment."
                ),
                "pages": [],
            }
        document_id = UUID(doc_id)
        result: dict[str, Any] = _run_async(_read_document_pages(document_id, start, end))
        _audit(
            "read_document_pages",
            {"doc_id": doc_id, "page_start": start, "page_end": end},
        )
        return result
    except Exception as exc:
        return _controlled_error("read_document_pages", args_redacted, exc)


def graph_query_readonly(
    question: str,
    *,
    policy: DeepAgentToolPolicy,
    neo4j_reader: Neo4jGraphReader | None = None,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {"question_length": len(question)}
    try:
        validate_tool_allowed("graph_query_readonly", policy)
        lowered = question.lower()
        cypher_keywords = ("match ", "merge ", "delete ", "create ", "cypher")
        if any(keyword in lowered for keyword in cypher_keywords):
            _audit_error("graph_query_readonly", args_redacted, "unsupported_graph_query")
            return {"error": "unsupported_graph_query", "reason": "Cypher libre no permitido."}

        reader = neo4j_reader or _build_default_neo4j_reader()
        if reader is None:
            _audit_error("graph_query_readonly", args_redacted, "neo4j_not_configured")
            return {"available": False, "reason": "neo4j_not_configured", "results": []}
        if not reader.is_available():
            _audit_error("graph_query_readonly", args_redacted, "neo4j_unreachable")
            return {"available": False, "reason": "neo4j_unreachable", "results": []}

        # Classify question type and extract key term
        if "entity" in lowered or "entidad" in lowered:
            fragment = _extract_term(question)
            results = reader.find_entities(fragment)
            _audit("graph_query_readonly", {"query_type": "find_entities", "fragment": fragment})
            return {"query_type": "find_entities", "results": results, "warnings": []}

        if "doc" in lowered or "documento" in lowered:
            term = _extract_term(question)
            results = reader.find_docs_for_entity(term)
            _audit("graph_query_readonly", {"query_type": "find_docs_for_entity", "term": term})
            return {"query_type": "find_docs_for_entity", "results": results, "warnings": []}

        # Default: entity search
        fragment = _extract_term(question)
        results = reader.find_entities(fragment)
        _audit(
            "graph_query_readonly",
            {"query_type": "find_entities_fallback", "fragment": fragment},
        )
        return {"query_type": "find_entities", "results": results, "warnings": []}
    except Exception as exc:
        return _controlled_error("graph_query_readonly", args_redacted, exc)


_default_web_search_client: WebSearchClient | None = None


def _get_web_search_client() -> WebSearchClient:
    global _default_web_search_client
    if _default_web_search_client is None:
        _default_web_search_client = build_default_web_search_client()
    return _default_web_search_client


def search_web(
    query: str,
    *,
    policy: DeepAgentToolPolicy,
    client: WebSearchClient | None = None,
    max_results: int = 10,
) -> dict[str, Any]:
    """Multi-provider web search (Tavily + Brave + Perplexity + Exa, merged + ranked)."""
    args_redacted: dict[str, Any] = {"query_length": len(query), "max_results": max_results}
    try:
        validate_tool_allowed("search_web", policy)
        if not settings.web_search_enabled:
            _audit_error("search_web", args_redacted, "web_search_disabled")
            return {"error": "web_search_disabled", "results": []}
        active_client = client or _get_web_search_client()
        bounded_max_results = _bounded_int(
            max_results,
            name="max_results",
            minimum=1,
            maximum=MAX_WEB_RESULTS_PER_CALL,
        )
        results = active_client.search(query)[:bounded_max_results]
        if not results:
            _audit("search_web", {"query_length": len(query), "providers": []})
            return {
                "results": [],
                "citations": [],
                "providers": [],
                "warnings": [
                    "Ningun proveedor web devolvio resultados (claves vacias o todas fallaron)."
                ],
            }
        providers = sorted({provider for result in results for provider in result.all_providers})
        _audit(
            "search_web",
            {"query_length": len(query), "providers": providers, "count": len(results)},
        )
        # Feed results back into Weaviate so future RAG queries can reuse them without
        # hitting the web again. This is intentionally fire-and-forget; errors are swallowed.
        with suppress(Exception):
            index_web_results_async(query=query, results=results)
        return {
            "results": [
                {
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                    "date": result.date,
                    "score": result.score,
                    "providers": result.all_providers,
                }
                for result in results
            ],
            "citations": [result.to_citation().model_dump(mode="json") for result in results],
            "providers": providers,
            "warnings": [],
        }
    except Exception as exc:
        return _controlled_error("search_web", args_redacted, exc)


def write_workspace_file(
    relative_path: str,
    content: str,
    *,
    policy: DeepAgentToolPolicy,
    workspace: DeepAgentWorkspace,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {
        "relative_path": relative_path,
        "content_bytes": len(content.encode()),
    }
    try:
        validate_tool_allowed("write_workspace_file", policy)
        content_bytes = content.encode()
        if len(content_bytes) > MAX_WORKSPACE_FILE_BYTES:
            _audit_error("write_workspace_file", args_redacted, "file_too_large")
            return {"error": "file_too_large", "max_bytes": MAX_WORKSPACE_FILE_BYTES}
        destination = validate_workspace_path(Path(relative_path), workspace)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        _audit(
            "write_workspace_file",
            {"relative_path": relative_path, "content_bytes": len(content_bytes)},
        )
        return {
            "relative_path": destination.relative_to(workspace.root_dir.resolve()).as_posix(),
            "bytes": len(content_bytes),
        }
    except Exception as exc:
        return _controlled_error("write_workspace_file", args_redacted, exc)


def list_available_skills(
    *,
    registry: DeepAgentSkillsRegistry | None = None,
    agent_name: str = "deepagent",
    task_type: str = "research",
    user_id: str | None = None,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {"agent_name": agent_name, "task_type": task_type}
    try:
        active_registry = registry or DeepAgentSkillsRegistry()
        enabled_paths = set(
            active_registry.get_enabled_skill_paths(agent_name, task_type, user_id=user_id)
        )
        skills = active_registry.discover_core_skills() + active_registry.discover_user_skills(
            user_id
        )
        _audit("list_available_skills", args_redacted)
        return {
            "skills": [
                skill.model_dump()
                for skill in skills
                if skill.path in enabled_paths and skill.enabled
            ]
        }
    except Exception as exc:
        return _controlled_error("list_available_skills", args_redacted, exc)


def read_skill(
    skill_name: str,
    *,
    registry: DeepAgentSkillsRegistry | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {"skill_name": skill_name}
    try:
        if "/" in skill_name or "\\" in skill_name or ".." in skill_name:
            _audit_error("read_skill", args_redacted, "invalid_skill_name")
            return {"error": "invalid_skill_name"}
        active_registry = registry or DeepAgentSkillsRegistry()
        skills = active_registry.discover_core_skills() + active_registry.discover_user_skills(
            user_id
        )
        for skill in skills:
            if skill.name == skill_name and skill.enabled:
                content = (Path(skill.path) / "SKILL.md").read_text(encoding="utf-8")
                _audit("read_skill", args_redacted)
                return {"skill": skill.model_dump(), "content": content}
        _audit_error("read_skill", args_redacted, "skill_not_found")
        return {"error": "skill_not_found"}
    except Exception as exc:
        return _controlled_error("read_skill", args_redacted, exc)


def get_relevant_memory(
    scope: str,
    query: str,
    *,
    memory_service: DeepAgentMemoryService | None = None,
    user_id: str | None = None,
    case_id: str | None = None,
    thread_id: str | None = None,
    agent_name: str | None = None,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {"scope": scope, "query_length": len(query)}
    try:
        active_service = memory_service or DeepAgentMemoryService()
        items = _run_async(
            active_service.list_memory(
                scope=_scope(scope),
                user_id=user_id,
                case_id=case_id,
                thread_id=thread_id,
                agent_name=agent_name,
            )
        )
        query_terms = {term.lower() for term in query.split() if len(term) > 2}
        if query_terms:
            items = [
                item for item in items if any(term in item.content.lower() for term in query_terms)
            ]
        _audit("get_relevant_memory", args_redacted)
        return {"items": [item.model_dump(mode="json") for item in items]}
    except Exception as exc:
        return _controlled_error("get_relevant_memory", args_redacted, exc)


def propose_memory_update(
    kind: str,
    content: str,
    reason: str,
    scope: str,
    *,
    memory_service: DeepAgentMemoryService | None = None,
    proposed_by_agent: str = "deepagent",
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {"scope": scope, "kind": kind, "reason_length": len(reason)}
    try:
        active_service = memory_service or DeepAgentMemoryService()
        proposal = _run_async(
            active_service.propose_memory_update(
                DeepAgentMemoryProposal(
                    proposal_id=str(uuid4()),
                    proposed_by_agent=proposed_by_agent,
                    scope=_scope(scope),
                    reason=f"{kind}: {reason}",
                    proposed_content=content,
                    sensitivity="internal",
                    requires_approval=True,
                )
            )
        )
        _audit("propose_memory_update", args_redacted)
        return {
            "status": "pending_approval",
            "proposal": proposal.model_dump(mode="json"),
            "applied": False,
        }
    except Exception as exc:
        return _controlled_error("propose_memory_update", args_redacted, exc)


async def _read_document_pages(
    doc_id: UUID,
    page_start: int,
    page_end: int,
) -> dict[str, Any]:
    async with session_scope() as session:
        document = await session.get(Document, doc_id)
        if document is None:
            return {"error": "document_not_found", "pages": []}
        result = await session.execute(
            select(DocumentPage)
            .where(
                DocumentPage.document_id == doc_id,
                DocumentPage.page_number >= page_start,
                DocumentPage.page_number <= page_end,
            )
            .order_by(DocumentPage.page_number)
        )
        pages = list(result.scalars().all())
        return {
            "doc_id": str(doc_id),
            "title": document.title,
            "pages": [
                {
                    "page_number": page.page_number,
                    "text": page.text,
                    "extraction_method": page.extraction_method,
                    "warnings": page.warnings,
                }
                for page in pages
            ],
        }


def plan_route(
    origin: str,
    destination: str,
    *,
    travel_mode: str = "driving",
    policy: DeepAgentToolPolicy,
    maps_service: MapsService,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {
        "origin_len": len(origin or ""),
        "destination_len": len(destination or ""),
        "travel_mode": travel_mode,
    }
    try:
        validate_tool_allowed("plan_route", policy)
        if travel_mode not in {"driving", "walking", "bicycling", "transit"}:
            msg = f"Unsupported travel_mode: {travel_mode}"
            raise ValueError(msg)
        mode = cast(TravelMode, travel_mode)
        plan = maps_service.plan_route(
            origin=origin,
            destination=destination,
            travel_mode=mode,
        )
        _audit("plan_route", args_redacted)
        return plan.model_dump()
    except MapsError as exc:
        return _controlled_error("plan_route", args_redacted, exc)
    except Exception as exc:
        return _controlled_error("plan_route", args_redacted, exc)


def geocode_address(
    address: str,
    *,
    policy: DeepAgentToolPolicy,
    maps_service: MapsService,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {"address_len": len(address or "")}
    try:
        validate_tool_allowed("geocode_address", policy)
        result = maps_service.geocode(address)
        _audit("geocode_address", args_redacted)
        return result.model_dump()
    except MapsError as exc:
        return _controlled_error("geocode_address", args_redacted, exc)
    except Exception as exc:
        return _controlled_error("geocode_address", args_redacted, exc)


def list_calendar_events(
    *,
    days_ahead: int = 7,
    max_results: int = 10,
    policy: DeepAgentToolPolicy,
    calendar_service: CalendarService,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {
        "days_ahead": days_ahead,
        "max_results": max_results,
    }
    try:
        validate_tool_allowed("list_calendar_events", policy)
        from datetime import UTC, datetime, timedelta

        bounded_days = _bounded_int(days_ahead, name="days_ahead", minimum=1, maximum=60)
        bounded_max = _bounded_int(max_results, name="max_results", minimum=1, maximum=50)
        now = datetime.now(tz=UTC)
        request = ListEventsRequest(
            time_min=now,
            time_max=now + timedelta(days=bounded_days),
            max_results=bounded_max,
        )
        events = calendar_service.list_events(request)
        _audit("list_calendar_events", args_redacted)
        return {"events": [event.model_dump() for event in events]}
    except CalendarError as exc:
        return _controlled_error("list_calendar_events", args_redacted, exc)
    except Exception as exc:
        return _controlled_error("list_calendar_events", args_redacted, exc)


def search_drive_files(
    *,
    query: str = "",
    max_results: int = 10,
    policy: DeepAgentToolPolicy,
    drive_service: DriveService,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {
        "query_len": len(query or ""),
        "max_results": max_results,
    }
    try:
        validate_tool_allowed("search_drive_files", policy)
        bounded_max = _bounded_int(max_results, name="max_results", minimum=1, maximum=50)
        files = drive_service.list_files(
            DriveSearchRequest(query=query, max_results=bounded_max),
        )
        _audit("search_drive_files", args_redacted)
        return {"files": [file.model_dump() for file in files]}
    except DriveError as exc:
        return _controlled_error("search_drive_files", args_redacted, exc)
    except Exception as exc:
        return _controlled_error("search_drive_files", args_redacted, exc)


def search_notes(
    *,
    query: str,
    limit: int = 10,
    user_id: str | None,
    policy: DeepAgentToolPolicy,
    note_index: NoteIndexService,
) -> dict[str, Any]:
    """Search the operator's PersonalNote vault. Returns empty on missing user_id."""
    args_redacted: dict[str, Any] = {
        "query_len": len(query or ""),
        "limit": limit,
        "user_scoped": bool(user_id),
    }
    try:
        validate_tool_allowed("search_notes", policy)
        if not user_id:
            # No DeepAgent task on Cognitive OS should run without a user_id, but
            # a future caller that omits it must not leak notes across users.
            _audit("search_notes", {**args_redacted, "result": "no_user_scope"})
            return {"hits": [], "warning": "no_user_scope"}
        bounded_limit = _bounded_int(limit, name="limit", minimum=1, maximum=50)
        hits = note_index.search_notes(user_id, query, limit=bounded_limit)
        _audit("search_notes", args_redacted)
        return {"hits": [hit.model_dump() for hit in hits]}
    except Exception as exc:
        return _controlled_error("search_notes", args_redacted, exc)


def browse_real_navigate(
    *,
    url: str,
    session: str | None,
    policy: DeepAgentToolPolicy,
    webbridge_service: KimiWebBridgeService,
    user_id: str | None,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {"url_len": len(url or ""), "session": session}
    try:
        validate_tool_allowed("browse_real_navigate", policy)
        result = webbridge_service.navigate(
            NavigateRequest(url=url, new_tab=True, session=session),
            requested_by=user_id,
        )
        _audit("browse_real_navigate", args_redacted)
        return result.model_dump()
    except KimiWebBridgeError as exc:
        return _controlled_error("browse_real_navigate", args_redacted, exc)
    except Exception as exc:
        return _controlled_error("browse_real_navigate", args_redacted, exc)


def browse_real_snapshot(
    *,
    session: str | None,
    policy: DeepAgentToolPolicy,
    webbridge_service: KimiWebBridgeService,
    user_id: str | None,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {"session": session}
    try:
        validate_tool_allowed("browse_real_snapshot", policy)
        result = webbridge_service.snapshot(
            SnapshotRequest(session=session),
            requested_by=user_id,
        )
        _audit("browse_real_snapshot", args_redacted)
        return result.model_dump()
    except KimiWebBridgeError as exc:
        return _controlled_error("browse_real_snapshot", args_redacted, exc)
    except Exception as exc:
        return _controlled_error("browse_real_snapshot", args_redacted, exc)


def browse_real_screenshot(
    *,
    session: str | None,
    fmt: str = "png",
    policy: DeepAgentToolPolicy,
    webbridge_service: KimiWebBridgeService,
    user_id: str | None,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {"session": session, "format": fmt}
    try:
        validate_tool_allowed("browse_real_screenshot", policy)
        if fmt not in {"png", "jpeg"}:
            msg = f"Unsupported screenshot format: {fmt}"
            raise ValueError(msg)
        result = webbridge_service.screenshot(
            ScreenshotRequest(session=session, format=cast(Any, fmt)),
            requested_by=user_id,
        )
        _audit("browse_real_screenshot", args_redacted)
        # Strip the base64 payload from the agent-visible result: a full screenshot
        # is hundreds of KB of text and floods the LLM context. The audit row
        # already records the call; the operator can fetch the bytes via the
        # `/actions/webbridge/screenshot` endpoint if needed.
        dump = result.model_dump()
        payload = dump.get("payload") or {}
        if "data" in payload:
            payload["data_truncated"] = True
            payload.pop("data", None)
        return dump
    except KimiWebBridgeError as exc:
        return _controlled_error("browse_real_screenshot", args_redacted, exc)
    except Exception as exc:
        return _controlled_error("browse_real_screenshot", args_redacted, exc)


def solve_image_captcha(
    *,
    image_base64: str,
    policy: DeepAgentToolPolicy,
    captcha_service: CaptchaSolverService,
    user_id: str | None,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {"image_b64_len": len(image_base64 or "")}
    try:
        validate_tool_allowed("solve_image_captcha", policy)
        solution = captcha_service.solve_image(image_base64, requested_by=user_id)
        _audit("solve_image_captcha", args_redacted)
        return {"text": solution.token, "kind": solution.kind}
    except CaptchaSolverError as exc:
        return _controlled_error("solve_image_captcha", args_redacted, exc)
    except Exception as exc:
        return _controlled_error("solve_image_captcha", args_redacted, exc)


def solve_token_captcha(
    *,
    kind: str,
    website_url: str,
    website_key: str,
    page_action: str | None,
    policy: DeepAgentToolPolicy,
    captcha_service: CaptchaSolverService,
    user_id: str | None,
) -> dict[str, Any]:
    args_redacted: dict[str, Any] = {
        "kind": kind,
        "url_len": len(website_url or ""),
    }
    try:
        validate_tool_allowed("solve_token_captcha", policy)
        if kind not in {"recaptcha_v2", "recaptcha_v3", "hcaptcha", "turnstile"}:
            msg = f"Unsupported captcha kind: {kind}"
            raise ValueError(msg)
        solution = captcha_service.solve_token(
            cast(CaptchaKind, kind),
            website_url=website_url,
            website_key=website_key,
            page_action=page_action,
            requested_by=user_id,
        )
        _audit("solve_token_captcha", args_redacted)
        return {"token": solution.token, "kind": solution.kind, "task_id": solution.task_id}
    except CaptchaSolverError as exc:
        return _controlled_error("solve_token_captcha", args_redacted, exc)
    except Exception as exc:
        return _controlled_error("solve_token_captcha", args_redacted, exc)


def _citation_from_context(context: RetrievedContext) -> dict[str, Any]:
    metadata = context.metadata
    return {
        "source_type": "local_doc",
        "doc_id": metadata.get("doc_id"),
        "chunk_id": metadata.get("chunk_id"),
        "page_start": metadata.get("page_start"),
        "page_end": metadata.get("page_end"),
        "quote": context.text[:500],
        "relevance": context.score,
    }


def _controlled_error(
    tool_name: str,
    args_redacted: dict[str, Any],
    exc: Exception,
) -> dict[str, Any]:
    """Convert an exception to a controlled dict response AND audit the failure.

    Auditing on error (not only on success) closes a real gap: a policy violation,
    invalid input, or unexpected exception used to disappear silently because
    `_audit` was only called after the happy path. Each call site now reports the
    tool name and the redacted args, so the audit trail mirrors every attempted
    invocation regardless of outcome.
    """
    if isinstance(exc, DeepAgentPolicyViolation):
        _audit_error(tool_name, args_redacted, f"policy_violation: {exc}")
        return {"error": "policy_violation", "detail": str(exc)}
    _audit_error(tool_name, args_redacted, f"{type(exc).__name__}: {exc}")
    return {"error": type(exc).__name__, "detail": str(exc)}


def _audit(tool_name: str, args_redacted: dict[str, Any]) -> None:
    try:
        record_audit_event(
            ToolAuditRecord(
                tool_name=f"deepagents.{tool_name}",
                risk_level=ToolRiskLevel.READ_ONLY,
                args_redacted=args_redacted,
                result_summary="ok",
            )
        )
    except Exception:
        return


def _audit_error(tool_name: str, args_redacted: dict[str, Any], reason: str) -> None:
    """Record a failure/block of a DeepAgent tool so it shows up in the audit log."""
    try:
        record_audit_event(
            ToolAuditRecord(
                tool_name=f"deepagents.{tool_name}",
                risk_level=ToolRiskLevel.READ_ONLY,
                args_redacted=args_redacted,
                result_summary=f"error: {reason}",
            )
        )
    except Exception:
        return


def _extract_term(question: str) -> str:
    """Heuristically extract the most meaningful term from a natural-language question."""
    stop_words = {
        "de",
        "la",
        "el",
        "los",
        "las",
        "del",
        "para",
        "en",
        "con",
        "sobre",
        "que",
        "me",
        "quién",
        "qué",
        "cual",
        "cuales",
        "busca",
        "find",
        "search",
        "show",
        "get",
        "the",
        "a",
        "an",
        "of",
        "for",
        "in",
        "with",
        "entity",
        "entities",
        "entidad",
        "entidades",
        "documento",
        "doc",
        "document",
        "query",
        "consulta",
        "dame",
        "muestra",
        "buscar",
        "related",
        "about",
    }
    words = [w.strip(".,;?!\"'") for w in question.split()]
    meaningful = [w for w in words if w.lower() not in stop_words and len(w) > 2]
    return " ".join(meaningful[:3]) if meaningful else question[:50]


def _scope(scope: str) -> DeepAgentMemoryScope:
    allowed = {"global", "user", "case", "thread", "agent"}
    if scope not in allowed:
        msg = f"Invalid memory scope: {scope}"
        raise ValueError(msg)
    return cast(DeepAgentMemoryScope, scope)


def _bounded_int(value: object, *, name: str, minimum: int, maximum: int) -> int:
    parsed = _coerce_int(value, name=name)
    if parsed < minimum:
        return minimum
    if parsed > maximum:
        return maximum
    return parsed


def _coerce_int(value: object, *, name: str) -> int:
    if isinstance(value, bool):
        msg = f"{name} must be an integer."
        raise ValueError(msg)
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        msg = f"{name} must be an integer."
        raise ValueError(msg)
    try:
        parsed = int(value.strip())
    except (TypeError, ValueError) as exc:
        msg = f"{name} must be an integer."
        raise ValueError(msg) from exc
    return parsed


def _run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    msg = "DeepAgent sync tool cannot perform database IO inside an active event loop."
    raise RuntimeError(msg)

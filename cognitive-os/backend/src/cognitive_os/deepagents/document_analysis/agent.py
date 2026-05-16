from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any, Literal

from langchain_core.messages import HumanMessage

from cognitive_os.deepagents.document_analysis.evaluators import apply_quality_evaluation
from cognitive_os.deepagents.document_analysis.exporters import DocumentAnalysisExporter
from cognitive_os.deepagents.document_analysis.prompts import (
    MODE_INSTRUCTIONS,
    QUALITY_CHECK_PROMPT,
    SYSTEM_PROMPT_DOCUMENT_ANALYST,
)
from cognitive_os.deepagents.document_analysis.schemas import (
    ContradictionFinding,
    DocumentAnalysisResult,
    DocumentAnalysisTask,
    EvidenceCitation,
    EvidenceMatrixRow,
    MissingEvidenceFinding,
    TimelineEvent,
)
from cognitive_os.deepagents.document_analysis.tools import (
    Retriever,
    analysis_workspace,
    build_document_analysis_tools,
    search_within_allowed_docs,
)
from cognitive_os.deepagents.factory import create_controlled_deep_agent
from cognitive_os.deepagents.memory_service import DeepAgentMemoryService
from cognitive_os.deepagents.schemas import DeepAgentTask, DeepAgentToolPolicy, DeepAgentWorkspace
from cognitive_os.deepagents.skills_registry import DeepAgentSkillsRegistry


class DocumentAnalysisDeepAgent:
    def __init__(
        self,
        *,
        retriever: Retriever | None = None,
        agent_factory: Any | None = None,
    ) -> None:
        self._retriever = retriever
        self._agent_factory = agent_factory or create_controlled_deep_agent

    async def run(self, task: DocumentAnalysisTask) -> DocumentAnalysisResult:
        workspace = analysis_workspace(task)
        try:
            result = await self._run_deepagent(task, workspace)
        except Exception as exc:
            result = await self._fallback(
                task,
                warning=f"deepagent_failed_fallback_used:{type(exc).__name__}",
            )
        result = apply_quality_evaluation(result, task)
        exported = self._export(result, workspace, task.output_formats)
        result.generated_files = sorted({*result.generated_files, *exported})
        return result

    async def _run_deepagent(
        self,
        task: DocumentAnalysisTask,
        workspace: Path,
    ) -> DocumentAnalysisResult:
        deep_task = DeepAgentTask(
            task_id=task.task_id,
            thread_id=task.thread_id,
            user_id=task.user_id,
            task_type="document_analysis",
            query=task.query,
            allowed_doc_ids=task.doc_ids,
            web_allowed=False,
            require_citations=task.require_citations,
            metadata=task.metadata,
        )
        policy = DeepAgentToolPolicy(
            allow_local_rag=True,
            allow_neo4j_read=task.use_graph,
            allow_web=False,
            allow_workspace_write=True,
            allow_shell=False,
            allow_browser=False,
            allow_email=False,
            allow_social_posting=False,
            allow_delete=False,
        )
        skills_paths = _skill_paths(task)
        try:
            startup_memory = await DeepAgentMemoryService().get_startup_memory(
                "document-analysis",
                user_id=task.user_id,
                case_id=task.case_id,
                thread_id=task.thread_id,
            )
        except Exception:
            startup_memory = None
        agent = self._agent_factory(
            deep_task,
            policy,
            DeepAgentWorkspace(root_dir=workspace, thread_id=task.thread_id, task_id=task.task_id),
            system_prompt=_system_prompt(task),
            skills_paths=skills_paths,
            startup_memory=startup_memory,
            tools=build_document_analysis_tools(
                task,
                workspace_root=workspace,
                retriever=self._retriever,
            ),
            response_format=DocumentAnalysisResult,
        )
        raw = await asyncio.to_thread(
            agent.invoke,
            {
                "messages": [
                    HumanMessage(
                        content=(
                            f"Analiza doc_ids autorizados {task.doc_ids}. Query: {task.query}. "
                            "Devuelve DocumentAnalysisResult estructurado."
                        )
                    )
                ]
            },
        )
        return _coerce_result(raw, task)

    async def _fallback(
        self, task: DocumentAnalysisTask, *, warning: str
    ) -> DocumentAnalysisResult:
        search_result = search_within_allowed_docs(
            task.query,
            task.doc_ids,
            limit=12,
            task=task,
            retriever=self._retriever,
        )
        citations = [
            EvidenceCitation.model_validate(citation)
            for citation in search_result.get("citations", [])
        ]
        matrix = [
            EvidenceMatrixRow(
                claim_id=f"claim-{index + 1}",
                claim=_claim_from_quote(citation.quote or task.query),
                claim_type="fact",
                supporting_evidence=[citation],
                opposing_evidence=[],
                strength="moderate" if citation.quote else "weak",
                notes="Fallback deterministico desde citas recuperadas.",
                needs_human_review=False,
            )
            for index, citation in enumerate(citations[:8])
        ]
        timeline = _timeline_from_citations(citations)
        contradictions = _detect_date_contradictions(citations)
        missing = _missing_evidence(task, matrix)
        draft_sections = {}
        human_review = False
        if "legal_draft_support" in task.modes:
            draft_sections["working_draft_support"] = (
                "Borrador de apoyo sujeto a revision humana. Basado solo en citas disponibles."
            )
            human_review = task.require_human_review_for_drafts
        status: Literal["ok", "partial"] = "partial" if warning else "ok"
        return DocumentAnalysisResult(
            task_id=task.task_id,
            thread_id=task.thread_id,
            status=status,
            executive_summary=_summary(task, matrix, timeline, contradictions, missing),
            evidence_matrix=matrix,
            timeline=timeline,
            contradictions=contradictions,
            missing_evidence=missing,
            draft_sections=draft_sections,
            citations=citations,
            uncertainty_notes=["Analisis fallback; revisar manualmente evidencia clave."],
            generated_files=[],
            human_review_required=human_review,
            warnings=[warning],
            raw_agent_summary=None,
        )

    def _export(
        self,
        result: DocumentAnalysisResult,
        workspace: Path,
        output_formats: Sequence[str],
    ) -> list[str]:
        exporter = DocumentAnalysisExporter()
        generated: list[str] = []
        if "json" in output_formats:
            generated.append(exporter.export_json(result, workspace).name)
        if "markdown" in output_formats:
            generated.append(exporter.export_markdown(result, workspace).name)
        if "csv" in output_formats:
            generated.extend(path.name for path in exporter.export_csvs(result, workspace))
        if "docx" in output_formats:
            docx_path = exporter.export_docx(result, workspace)
            if docx_path is None:
                result.warnings.append("docx_export_unavailable")
            else:
                generated.append(docx_path.name)
        return generated


def _coerce_result(raw: Any, task: DocumentAnalysisTask) -> DocumentAnalysisResult:
    if isinstance(raw, DocumentAnalysisResult):
        return raw
    if isinstance(raw, dict):
        structured = raw.get("structured_response")
        if isinstance(structured, DocumentAnalysisResult):
            return structured
        if isinstance(structured, dict):
            return DocumentAnalysisResult.model_validate(structured)
        if "task_id" in raw and "evidence_matrix" in raw:
            return DocumentAnalysisResult.model_validate(raw)
    return DocumentAnalysisResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="partial",
        executive_summary=str(raw)[:1000],
        evidence_matrix=[],
        timeline=[],
        contradictions=[],
        missing_evidence=[],
        draft_sections={},
        citations=[],
        uncertainty_notes=["El agente devolvio texto no estructurado."],
        generated_files=[],
        human_review_required=True,
        warnings=["unstructured_agent_output"],
        raw_agent_summary=str(raw)[:2000],
    )


def _system_prompt(task: DocumentAnalysisTask) -> str:
    mode_text = "\n".join(f"- {mode}: {MODE_INSTRUCTIONS[mode]}" for mode in task.modes)
    return (
        f"{SYSTEM_PROMPT_DOCUMENT_ANALYST}\n\nModos solicitados:\n{mode_text}\n\n"
        f"Doc ids autorizados: {task.doc_ids}\n"
        f"Allowed page ranges: {task.allowed_page_ranges}\n\n{QUALITY_CHECK_PROMPT}"
    )


def _skill_paths(task: DocumentAnalysisTask) -> list[str]:
    registry = DeepAgentSkillsRegistry()
    paths = registry.get_enabled_skill_paths("document-analysis", "document_analysis", task.user_id)
    selected = []
    always_on = {
        "rag-research",
        "evidence-matrix",
        "timeline-builder",
        "contradiction-detector",
        "citation-discipline",
        "report-writer",
    }
    for path in paths:
        name = Path(path).name
        if name in always_on:
            selected.append(path)
        if "legal_draft_support" in task.modes and name == "legal-draft-careful":
            selected.append(path)
    return selected


def _claim_from_quote(text: str) -> str:
    return " ".join(text.strip().split())[:240]


def _timeline_from_citations(citations: list[EvidenceCitation]) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for index, citation in enumerate(citations):
        date_text = _extract_date(citation.quote or "")
        if not date_text:
            continue
        normalized = _normalize_spanish_date(date_text)
        events.append(
            TimelineEvent(
                event_id=f"event-{index + 1}",
                date_text=date_text,
                normalized_date=normalized,
                date_certainty="exact" if normalized else "unknown",
                event_summary=_claim_from_quote(citation.quote or ""),
                involved_entities=[],
                citations=[citation],
                contradictions=[],
                notes="Extraido deterministamente desde cita.",
            )
        )
    return events


def _detect_date_contradictions(citations: list[EvidenceCitation]) -> list[ContradictionFinding]:
    dated = [(citation, _extract_date(citation.quote or "")) for citation in citations]
    dated = [(citation, date_text) for citation, date_text in dated if date_text]
    if len(dated) < 2:
        return []
    first_citation, first_date = dated[0]
    contradictions: list[ContradictionFinding] = []
    for index, (citation, date_text) in enumerate(dated[1:], start=2):
        if date_text != first_date:
            contradictions.append(
                ContradictionFinding(
                    contradiction_id=f"contradiction-{index - 1}",
                    topic="Fecha del hecho",
                    statement_a=f"El hecho ocurrio el {first_date}.",
                    statement_b=f"El hecho ocurrio el {date_text}.",
                    citation_a=first_citation,
                    citation_b=citation,
                    contradiction_type="date",
                    severity="high",
                    explanation=(
                        "Las citas indican fechas distintas para el mismo hecho consultado."
                    ),
                    needs_human_review=True,
                )
            )
            break
    return contradictions


def _missing_evidence(
    task: DocumentAnalysisTask,
    matrix: list[EvidenceMatrixRow],
) -> list[MissingEvidenceFinding]:
    if matrix:
        return []
    return [
        MissingEvidenceFinding(
            finding_id="missing-1",
            expected_evidence=f"Evidencia documental para: {task.query}",
            why_it_matters="Sin evidencia localizada no corresponde afirmar el hecho.",
            related_claims=[],
            search_attempts=[task.query],
            status="not_found",
        )
    ]


def _summary(
    task: DocumentAnalysisTask,
    matrix: list[EvidenceMatrixRow],
    timeline: list[TimelineEvent],
    contradictions: list[ContradictionFinding],
    missing: list[MissingEvidenceFinding],
) -> str:
    return (
        f"Analisis documental para {len(task.doc_ids)} documento(s). "
        f"Matriz: {len(matrix)} fila(s). Timeline: {len(timeline)} evento(s). "
        f"Contradicciones: {len(contradictions)}. Vacios: {len(missing)}."
    )


def _extract_date(text: str) -> str | None:
    match = re.search(r"\b\d{1,2}\s+de\s+[a-zA-Záéíóúñ]+\s+de\s+\d{4}\b", text, flags=re.I)
    if match:
        return match.group(0)
    iso = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    return iso.group(0) if iso else None


def _normalize_spanish_date(text: str) -> date | None:
    months = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return date.fromisoformat(text)
    match = re.fullmatch(r"(\d{1,2})\s+de\s+([a-zA-Záéíóúñ]+)\s+de\s+(\d{4})", text, flags=re.I)
    if not match:
        return None
    day = int(match.group(1))
    month = months.get(match.group(2).lower())
    year = int(match.group(3))
    return date(year, month, day) if month else None

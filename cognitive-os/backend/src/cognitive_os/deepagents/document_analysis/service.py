from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from cognitive_os.core.config import settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import AuditEvent, HumanApproval, Job, JobEvent
from cognitive_os.deepagents.document_analysis.agent import DocumentAnalysisDeepAgent
from cognitive_os.deepagents.document_analysis.schemas import (
    DocumentAnalysisResult,
    DocumentAnalysisTask,
)
from cognitive_os.deepagents.document_analysis.tools import analysis_workspace


class DocumentAnalysisService:
    def __init__(self, agent: DocumentAnalysisDeepAgent | None = None) -> None:
        self._agent = agent or DocumentAnalysisDeepAgent()

    async def run_analysis(self, task: DocumentAnalysisTask) -> DocumentAnalysisResult:
        self._validate_authorization(task)
        result = await self._agent.run(task)
        await self._persist_result(task, result)
        if result.draft_sections and task.require_human_review_for_drafts:
            await self._create_draft_review(task, result)
        return result

    async def run_analysis_as_job(
        self,
        task: DocumentAnalysisTask,
        job_id: str,
    ) -> DocumentAnalysisResult:
        active_job_id = UUID(job_id)
        await self._job_event(
            active_job_id,
            "document_scope_validated",
            "running",
            "Document analysis scope validation started",
            {"task_id": task.task_id},
        )
        self._validate_authorization(task)
        await self._job_event(
            active_job_id,
            "document_analysis_agent_started",
            "running",
            "Document analysis agent started",
            {"task_id": task.task_id},
        )
        for event_type in (
            "retrieval_started",
            "evidence_matrix_started",
            "timeline_started",
            "contradiction_detection_started",
            "export_started",
        ):
            await self._job_event(
                active_job_id,
                event_type,
                "running",
                event_type.replace("_", " "),
                {"task_id": task.task_id},
            )
        result = await self.run_analysis(task)
        await self._job_event(
            active_job_id,
            "quality_evaluation_finished",
            "running",
            "Document analysis quality evaluation finished",
            {"warnings": result.warnings},
        )
        terminal_status = (
            "completed" if result.status in {"ok", "partial", "needs_human_review"} else "failed"
        )
        await self._update_job(
            active_job_id,
            terminal_status,
            100,
            "document_analysis_finished",
            f"Document analysis finished with status {result.status}",
            {"task_id": task.task_id, "result": result.model_dump(mode="json")},
        )
        return result

    async def get_analysis_result(self, task_id: str) -> DocumentAnalysisResult | None:
        result_path = self._result_path(task_id)
        if not result_path.exists():
            return None
        return DocumentAnalysisResult.model_validate_json(result_path.read_text(encoding="utf-8"))

    def _validate_authorization(self, task: DocumentAnalysisTask) -> None:
        if not task.doc_ids:
            msg = "No authorized doc_ids were provided."
            raise ValueError(msg)
        if task.web_allowed:
            msg = "Document analysis does not allow web access."
            raise ValueError(msg)

    async def _persist_result(
        self,
        task: DocumentAnalysisTask,
        result: DocumentAnalysisResult,
    ) -> None:
        workspace = analysis_workspace(task)
        (workspace / "result.json").write_text(
            json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        async with session_scope() as session:
            session.add(
                AuditEvent(
                    actor_id=task.user_id,
                    action="document_analysis.completed",
                    resource_type="document_analysis",
                    resource_id=task.task_id,
                    metadata_json={
                        "status": result.status,
                        "human_review_required": result.human_review_required,
                    },
                )
            )

    async def _create_draft_review(
        self,
        task: DocumentAnalysisTask,
        result: DocumentAnalysisResult,
    ) -> None:
        async with session_scope() as session:
            session.add(
                HumanApproval(
                    action="document_analysis_draft_sections",
                    requested_action="document_analysis_draft_sections",
                    args_redacted={
                        "task_id": task.task_id,
                        "sections": list(result.draft_sections),
                        "citations": [
                            {
                                "doc_id": citation.doc_id,
                                "page_start": citation.page_start,
                                "page_end": citation.page_end,
                            }
                            for citation in result.citations[:20]
                        ],
                    },
                    requested_by=task.user_id,
                )
            )

    async def _job_event(
        self,
        job_id: UUID,
        event_type: str,
        status: str,
        message: str,
        metadata_json: dict[str, object] | None = None,
    ) -> None:
        async with session_scope() as session:
            session.add(
                JobEvent(
                    job_id=job_id,
                    event_type=event_type,
                    status=status,
                    message=message,
                    metadata_json=metadata_json or {},
                )
            )

    async def _update_job(
        self,
        job_id: UUID,
        status: str,
        progress: int,
        event_type: str,
        message: str,
        metadata_json: dict[str, object] | None = None,
    ) -> None:
        async with session_scope() as session:
            job = await session.get(Job, job_id)
            if job is None:
                msg = f"Job not found: {job_id}"
                raise ValueError(msg)
            if job.status in {"cancelled", "rejected"} and status not in {
                "cancelled",
                "rejected",
            }:
                session.add(
                    JobEvent(
                        job_id=job_id,
                        event_type=f"{event_type}_ignored_after_{job.status}",
                        status=job.status,
                        message=(
                            f"Ignored document-analysis update to {status}; "
                            f"job is already {job.status}."
                        ),
                        metadata_json={
                            "attempted_status": status,
                            "attempted_event_type": event_type,
                            **(metadata_json or {}),
                        },
                    )
                )
                return
            job.status = status
            job.progress = progress
            if metadata_json:
                job.metadata_json = {**job.metadata_json, **metadata_json}
            session.add(
                JobEvent(
                    job_id=job_id,
                    event_type=event_type,
                    status=status,
                    message=message,
                    metadata_json=metadata_json or {},
                )
            )

    def _result_path(self, task_id: str) -> Path:
        root = Path(settings.local_storage_dir) / "workspaces"
        matches = list(root.glob(f"*/{task_id}/analysis/result.json"))
        return matches[0] if matches else root / "_missing" / task_id / "result.json"

from __future__ import annotations

from typing import Any

import structlog

from cognitive_os.deepagents.document_deepagent import run_document_analysis_deepagent
from cognitive_os.deepagents.policies import DeepAgentPolicyViolation
from cognitive_os.deepagents.research_deepagent import run_research_deepagent
from cognitive_os.deepagents.schemas import DeepAgentResult, DeepAgentTask

logger = structlog.get_logger(__name__)


def run_deepagent_task(task: DeepAgentTask) -> DeepAgentResult:
    try:
        if task.task_type == "research":
            return run_research_deepagent(task)
        if task.task_type == "document_analysis":
            return run_document_analysis_deepagent(task)
        return DeepAgentResult(
            task_id=task.task_id,
            thread_id=task.thread_id,
            status="failed",
            answer=f"Unsupported DeepAgent task_type: {task.task_type}",
            findings=[],
            citations=[],
            uncertainty_notes=["Tipo de tarea no soportado."],
            generated_files=[],
            requested_external_actions=[],
            raw_summary=None,
        )
    except DeepAgentPolicyViolation as exc:
        return _blocked(task, str(exc))
    except TimeoutError as exc:
        return _failed(task, f"DeepAgent timeout: {exc}")
    except Exception as exc:
        logger.exception(
            "deepagent_task_failed",
            task_id=task.task_id,
            task_type=task.task_type,
            error_type=type(exc).__name__,
        )
        return _failed(task, f"{type(exc).__name__}: {exc}")


def _blocked(task: DeepAgentTask, detail: str) -> DeepAgentResult:
    return DeepAgentResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="blocked",
        answer="DeepAgent task blocked by Cognitive OS policy.",
        findings=[],
        citations=[],
        uncertainty_notes=[detail],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=detail,
    )


def _failed(task: DeepAgentTask, detail: str) -> DeepAgentResult:
    return DeepAgentResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="failed",
        answer="DeepAgent task failed before producing a reliable result.",
        findings=[],
        citations=[],
        uncertainty_notes=[detail],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=detail,
    )


def run_deepagent_task_from_dict(task_dict: dict[str, Any]) -> DeepAgentResult:
    return run_deepagent_task(DeepAgentTask.model_validate(task_dict))

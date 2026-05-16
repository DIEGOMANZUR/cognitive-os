"""Research Orchestrator (Phase 12).

Coordina N `deepagents` de investigacion en paralelo bajo presupuesto de
tiempo, con un nodo de calificacion al final. Reusa el subagente real
`run_research_deepagent` y mantiene las politicas existentes (deny-by-default,
sin shell, sin browser, citas obligatorias).

Diseno:
* `Planner` descompone una pregunta en subtasks acotadas.
* `Researcher` (default = run_research_deepagent) ejecuta cada subtask en
  un thread pool con `time_budget_seconds` global.
* `Synthesizer` consolida hallazgos y citas, deduplica y propaga incertidumbres.
* `Scorer` califica el informe final con una rubrica auditable.
* Cada nodo emite `ResearchEvent` a una cola por run, para streaming SSE.
* Todos los providers son inyectables (Protocol) para que las pruebas no
  necesiten LLMs reales.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import UTC, datetime
from queue import Empty, Queue
from typing import Literal, Protocol

import structlog
from pydantic import BaseModel, Field

from cognitive_os.core.config import Settings, settings
from cognitive_os.deepagents.schemas import (
    DeepAgentCitation,
    DeepAgentResult,
    DeepAgentTask,
)

__all__ = [
    "FakePlanner",
    "FakeResearcher",
    "FakeScorer",
    "FakeSynthesizer",
    "PlannerProvider",
    "ResearchEvent",
    "ResearchOrchestrator",
    "ResearchOrchestratorDisabledError",
    "ResearchRun",
    "ResearchRunRequest",
    "ResearchSubtask",
    "ResearchSubtaskResult",
    "ResearchSynthesis",
    "ResearcherProvider",
    "ResearchRunStore",
    "ScoreResult",
    "ScorerProvider",
    "SynthesizerProvider",
]

logger = structlog.get_logger(__name__)


RunStatus = Literal[
    "queued",
    "planning",
    "researching",
    "synthesizing",
    "scoring",
    "completed",
    "cancelled",
    "failed",
    "blocked",
]


class ResearchOrchestratorDisabledError(RuntimeError):
    """Raised when `ENABLE_RESEARCH_ORCHESTRATOR=false`."""


class ResearchRunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    user_id: str | None = None
    thread_id: str | None = None
    time_budget_seconds: int = Field(default=120, ge=5, le=3600)
    max_subtasks: int = Field(default=3, ge=1, le=32)
    web_allowed: bool = False


class ResearchSubtask(BaseModel):
    subtask_id: str
    query: str
    rationale: str = ""


class ResearchSubtaskResult(BaseModel):
    subtask_id: str
    status: Literal["ok", "needs_more_info", "blocked", "failed", "timeout", "cancelled"]
    answer: str = ""
    findings: list[str] = Field(default_factory=list)
    citations: list[DeepAgentCitation] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    duration_ms: int = 0


class ResearchSynthesis(BaseModel):
    answer: str
    findings: list[str] = Field(default_factory=list)
    citations: list[DeepAgentCitation] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    used_sources: list[str] = Field(default_factory=list)


class ScoreResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    rubric: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class ResearchEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str
    kind: Literal[
        "run_started",
        "plan_ready",
        "subtask_started",
        "subtask_finished",
        "synthesis_ready",
        "score_ready",
        "run_completed",
        "run_cancelled",
        "run_failed",
        "run_blocked",
    ]
    payload: dict[str, object] = Field(default_factory=dict)


@dataclass
class ResearchRun:
    run_id: str
    request: ResearchRunRequest
    status: RunStatus = "queued"
    subtasks: list[ResearchSubtask] = field(default_factory=list)
    results: list[ResearchSubtaskResult] = field(default_factory=list)
    synthesis: ResearchSynthesis | None = None
    score: ScoreResult | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    events: list[ResearchEvent] = field(default_factory=list)
    cancel_flag: threading.Event = field(default_factory=threading.Event)
    event_queue: Queue[ResearchEvent | None] = field(default_factory=Queue)
    done_flag: threading.Event = field(default_factory=threading.Event)
    executor_thread: threading.Thread | None = None


class PlannerProvider(Protocol):
    def plan(self, request: ResearchRunRequest) -> list[ResearchSubtask]: ...


class ResearcherProvider(Protocol):
    def run(self, task: DeepAgentTask) -> DeepAgentResult: ...


class SynthesizerProvider(Protocol):
    def synthesize(
        self,
        request: ResearchRunRequest,
        subtasks: list[ResearchSubtask],
        results: list[ResearchSubtaskResult],
    ) -> ResearchSynthesis: ...


class ScorerProvider(Protocol):
    def score(
        self,
        request: ResearchRunRequest,
        synthesis: ResearchSynthesis,
        results: list[ResearchSubtaskResult],
    ) -> ScoreResult: ...


class ResearchRunStore(Protocol):
    def save_run(self, run: ResearchRun) -> None: ...

    def get_run(self, run_id: str) -> ResearchRun | None: ...

    def list_runs(self, *, limit: int = 50) -> list[ResearchRun]: ...


class HeuristicPlanner:
    """Default planner: split the query into focused subtasks without LLM.

    Phase 12 ships a deterministic planner so the orchestrator works
    out-of-the-box even without LLM keys. An LLM planner can be swapped in
    later via `planner=` on the orchestrator.
    """

    def plan(self, request: ResearchRunRequest) -> list[ResearchSubtask]:
        q = request.query.strip()
        n = max(1, min(request.max_subtasks, 4))
        templates = [
            ("background", "Contexto y antecedentes: {q}"),
            ("evidence", "Evidencia documentada y citas verificables: {q}"),
            ("counterpoints", "Contraejemplos, riesgos y limitaciones: {q}"),
            ("synthesis", "Conclusiones y siguientes pasos: {q}"),
        ]
        return [
            ResearchSubtask(
                subtask_id=f"st-{i + 1}",
                query=template.format(q=q),
                rationale=f"Cubrir dimension '{name}' de la pregunta.",
            )
            for i, (name, template) in enumerate(templates[:n])
        ]


class DeepAgentResearcher:
    """Default researcher: delegate to `run_research_deepagent`."""

    def __init__(self, runner: Callable[[DeepAgentTask], DeepAgentResult] | None = None) -> None:
        if runner is None:
            from cognitive_os.deepagents.research_deepagent import run_research_deepagent

            runner = run_research_deepagent
        self._runner = runner

    def run(self, task: DeepAgentTask) -> DeepAgentResult:
        return self._runner(task)


class HeuristicSynthesizer:
    def synthesize(
        self,
        request: ResearchRunRequest,
        subtasks: list[ResearchSubtask],
        results: list[ResearchSubtaskResult],
    ) -> ResearchSynthesis:
        findings: list[str] = []
        citations: list[DeepAgentCitation] = []
        uncertainty: list[str] = []
        used_sources: set[str] = set()
        ok_results = [r for r in results if r.status == "ok" and r.answer]
        for result in results:
            findings.extend(result.findings)
            uncertainty.extend(result.uncertainty_notes)
            citations.extend(result.citations)
            for citation in result.citations:
                key = citation.url or (
                    f"doc:{citation.doc_id}:{citation.chunk_id}" if citation.doc_id else None
                )
                if key:
                    used_sources.add(key)
        deduped_citations = _dedupe_citations(citations)
        if not ok_results:
            return ResearchSynthesis(
                answer=(
                    "No se obtuvo evidencia suficiente para responder con seguridad. "
                    "Revisa las notas de incertidumbre y reintenta con mas presupuesto."
                ),
                findings=findings,
                citations=deduped_citations,
                uncertainty_notes=_dedupe(uncertainty)
                or ["Ningun subagente completo con estado ok."],
                used_sources=sorted(used_sources),
            )
        bullets = "\n".join(f"- {finding}" for finding in _dedupe(findings)[:12])
        answer_lines = [f"Pregunta: {request.query}", "", "Sintesis basada en subagentes:"]
        for subtask, result in zip(subtasks, results, strict=False):
            if result.status == "ok":
                answer_lines.append(f"- [{subtask.subtask_id}] {result.answer.splitlines()[0]}")
        if bullets:
            answer_lines.extend(["", "Hallazgos consolidados:", bullets])
        return ResearchSynthesis(
            answer="\n".join(answer_lines),
            findings=_dedupe(findings),
            citations=deduped_citations,
            uncertainty_notes=_dedupe(uncertainty),
            used_sources=sorted(used_sources),
        )


class HeuristicScorer:
    """Rubric-based scorer (auditable, no LLM)."""

    def score(
        self,
        request: ResearchRunRequest,
        synthesis: ResearchSynthesis,
        results: list[ResearchSubtaskResult],
    ) -> ScoreResult:
        total = max(1, len(results))
        ok = sum(1 for r in results if r.status == "ok")
        completion = ok / total
        coverage = min(1.0, len(synthesis.findings) / 8.0)
        evidence = 1.0 if synthesis.citations else 0.0
        humility = 1.0 if synthesis.uncertainty_notes else 0.5
        no_failed = 1.0 - (sum(1 for r in results if r.status in {"failed", "blocked"}) / total)
        rubric = {
            "completion": round(completion, 3),
            "coverage": round(coverage, 3),
            "evidence": round(evidence, 3),
            "humility": round(humility, 3),
            "no_failed": round(no_failed, 3),
        }
        score = round(
            (
                completion * 0.30
                + coverage * 0.20
                + evidence * 0.30
                + humility * 0.10
                + no_failed * 0.10
            ),
            3,
        )
        reasons: list[str] = []
        if completion < 1.0:
            reasons.append(f"{total - ok} subtask(s) no completaron ok.")
        if not synthesis.citations:
            reasons.append("Sintesis sin citas verificables.")
        if not synthesis.uncertainty_notes:
            reasons.append("No se reportan limites/incertidumbres explicitos.")
        return ScoreResult(score=score, rubric=rubric, reasons=reasons)


class ResearchOrchestrator:
    """Coordinates planner -> N researchers -> synthesizer -> scorer."""

    def __init__(
        self,
        app_settings: Settings = settings,
        *,
        planner: PlannerProvider | None = None,
        researcher: ResearcherProvider | None = None,
        synthesizer: SynthesizerProvider | None = None,
        scorer: ScorerProvider | None = None,
        store: ResearchRunStore | None = None,
    ) -> None:
        self._settings = app_settings
        self._planner = planner or HeuristicPlanner()
        self._researcher = researcher or DeepAgentResearcher()
        self._synthesizer = synthesizer or HeuristicSynthesizer()
        self._scorer = scorer or HeuristicScorer()
        self._store = store
        self._runs: dict[str, ResearchRun] = {}
        self._lock = threading.Lock()

    def start_run(self, request: ResearchRunRequest) -> ResearchRun:
        """Schedule a run on a daemon thread and return immediately.

        Returning immediately keeps `POST /research/runs` responsive (no blocking
        for `time_budget_seconds`), and is what makes `cancel_run` and the SSE
        events endpoint actually useful: clients can act on the run while it is
        still in progress.

        Callers that need terminal-state semantics (tests, CLIs) should call
        `wait_for_run(run_id)` after `start_run`.
        """
        if not self._settings.enable_research_orchestrator:
            raise ResearchOrchestratorDisabledError(
                "Research orchestrator is disabled. Set ENABLE_RESEARCH_ORCHESTRATOR=true."
            )
        clamped = request.model_copy(
            update={
                "time_budget_seconds": min(
                    request.time_budget_seconds,
                    self._settings.research_max_time_budget_seconds,
                ),
                "max_subtasks": min(request.max_subtasks, self._settings.research_max_subtasks),
            }
        )
        run = ResearchRun(run_id=f"rr-{uuid.uuid4()}", request=clamped)
        with self._lock:
            self._runs[run.run_id] = run
        self._persist_run(run)
        thread = threading.Thread(
            target=self._execute,
            args=(run,),
            daemon=True,
            name=f"research-{run.run_id}",
        )
        run.executor_thread = thread
        thread.start()
        return run

    def wait_for_run(self, run_id: str, *, timeout: float = 60.0) -> ResearchRun | None:
        """Block until the run reaches a terminal state or `timeout` elapses.

        Returns the run snapshot (or `None` if the run is unknown). Does not
        raise on timeout; callers should inspect `run.status` to distinguish
        "still running" from "completed". Safe to call multiple times.
        """
        run = self.get_run(run_id)
        if run is None:
            return None
        run.done_flag.wait(timeout=timeout)
        return run

    def get_run(self, run_id: str) -> ResearchRun | None:
        with self._lock:
            run = self._runs.get(run_id)
        if run is not None:
            return run
        if self._store is None:
            return None
        try:
            stored = self._store.get_run(run_id)
        except Exception as exc:
            logger.warning(
                "research_run_store_get_failed",
                run_id=run_id,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return None
        if stored is not None:
            with self._lock:
                self._runs[stored.run_id] = stored
        return stored

    def list_runs(self, *, limit: int = 50) -> list[ResearchRun]:
        with self._lock:
            runs = list(self._runs.values())
        if self._store is not None:
            try:
                stored_runs = self._store.list_runs(limit=limit)
            except Exception as exc:
                logger.warning(
                    "research_run_store_list_failed",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            else:
                by_id = {run.run_id: run for run in stored_runs}
                by_id.update({run.run_id: run for run in runs})
                runs = list(by_id.values())
        runs.sort(key=lambda r: r.started_at or datetime.fromtimestamp(0, UTC), reverse=True)
        return runs[:limit]

    def cancel_run(self, run_id: str) -> ResearchRun | None:
        with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            return None
        if run.status in {"completed", "failed", "cancelled", "blocked"}:
            return run
        run.cancel_flag.set()
        if run.executor_thread is None or not run.executor_thread.is_alive():
            run.status = "cancelled"
            run.finished_at = datetime.now(UTC)
            run.done_flag.set()
            self._emit(run, "run_cancelled", {"reason": "Run cancelled after restore."})
            self._persist_run(run)
        return run

    def drain_events(self, run_id: str, *, timeout: float = 0.5) -> Iterable[ResearchEvent]:
        run = self.get_run(run_id)
        if run is None:
            return []
        out: list[ResearchEvent] = []
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                event = run.event_queue.get(timeout=max(0.0, end - time.monotonic()))
            except Empty:
                break
            if event is None:
                break
            out.append(event)
        return out

    def _execute(self, run: ResearchRun) -> None:
        run.started_at = datetime.now(UTC)
        self._emit(run, "run_started", {"query": run.request.query})
        try:
            run.status = "planning"
            run.subtasks = list(self._planner.plan(run.request))[: run.request.max_subtasks]
            self._emit(
                run,
                "plan_ready",
                {"subtasks": [s.model_dump(mode="json") for s in run.subtasks]},
            )
            run.status = "researching"
            run.results = self._fan_out(run)
            run.status = "synthesizing"
            synthesis = self._synthesizer.synthesize(run.request, run.subtasks, run.results)
            run.synthesis = synthesis
            self._emit(run, "synthesis_ready", {"synthesis": synthesis.model_dump(mode="json")})
            run.status = "scoring"
            score = self._scorer.score(run.request, synthesis, run.results)
            run.score = score
            self._emit(run, "score_ready", {"score": score.model_dump(mode="json")})
            if run.cancel_flag.is_set():
                run.status = "cancelled"
                self._emit(run, "run_cancelled", {})
            else:
                run.status = "completed"
                self._emit(run, "run_completed", {"score": score.score})
        except Exception as exc:
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"
            self._emit(run, "run_failed", {"error": run.error})
        finally:
            run.finished_at = datetime.now(UTC)
            self._persist_run(run)
            run.event_queue.put(None)
            run.done_flag.set()

    def _fan_out(self, run: ResearchRun) -> list[ResearchSubtaskResult]:
        max_workers = max(
            1, min(self._settings.research_max_parallel_workers, len(run.subtasks) or 1)
        )
        deadline = time.monotonic() + run.request.time_budget_seconds
        results: dict[str, ResearchSubtaskResult] = {}
        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            futures: dict[Future[ResearchSubtaskResult], ResearchSubtask] = {}
            for subtask in run.subtasks:
                if run.cancel_flag.is_set():
                    break
                self._emit(run, "subtask_started", {"subtask_id": subtask.subtask_id})
                futures[executor.submit(self._run_subtask, run, subtask)] = subtask
            remaining = max(0.0, deadline - time.monotonic())
            done, not_done = wait(futures.keys(), timeout=remaining)
            for fut in done:
                subtask = futures[fut]
                try:
                    res = fut.result(timeout=0)
                except Exception as exc:
                    res = ResearchSubtaskResult(
                        subtask_id=subtask.subtask_id,
                        status="failed",
                        answer="",
                        uncertainty_notes=[f"{type(exc).__name__}: {exc}"],
                    )
                results[subtask.subtask_id] = res
                self._emit(run, "subtask_finished", {"result": res.model_dump(mode="json")})
            for fut in not_done:
                subtask = futures[fut]
                fut.cancel()
                res = ResearchSubtaskResult(
                    subtask_id=subtask.subtask_id,
                    status=("cancelled" if run.cancel_flag.is_set() else "timeout"),
                    answer="",
                    uncertainty_notes=[
                        "Subtask cancelled by user."
                        if run.cancel_flag.is_set()
                        else "Subtask exceeded time budget."
                    ],
                )
                results[subtask.subtask_id] = res
                self._emit(run, "subtask_finished", {"result": res.model_dump(mode="json")})
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return [results[s.subtask_id] for s in run.subtasks if s.subtask_id in results]

    def _run_subtask(self, run: ResearchRun, subtask: ResearchSubtask) -> ResearchSubtaskResult:
        if run.cancel_flag.is_set():
            return ResearchSubtaskResult(
                subtask_id=subtask.subtask_id,
                status="cancelled",
                uncertainty_notes=["Cancelled before start."],
            )
        started = time.monotonic()
        task = DeepAgentTask(
            task_id=subtask.subtask_id,
            thread_id=run.run_id,
            user_id=run.request.user_id,
            task_type="research",
            query=subtask.query,
            web_allowed=run.request.web_allowed,
        )
        result = self._researcher.run(task)
        duration_ms = int((time.monotonic() - started) * 1000)
        status: Literal["ok", "needs_more_info", "blocked", "failed", "timeout", "cancelled"] = (
            result.status
        )
        return ResearchSubtaskResult(
            subtask_id=subtask.subtask_id,
            status=status,
            answer=result.answer,
            findings=result.findings,
            citations=result.citations,
            uncertainty_notes=result.uncertainty_notes,
            duration_ms=duration_ms,
        )

    def _emit(self, run: ResearchRun, kind: str, payload: dict[str, object]) -> None:
        event = ResearchEvent(run_id=run.run_id, kind=kind, payload=payload)  # type: ignore[arg-type]
        run.events.append(event)
        run.event_queue.put(event)
        self._persist_run(run)

    def _persist_run(self, run: ResearchRun) -> None:
        if self._store is None:
            return
        try:
            self._store.save_run(run)
        except Exception as exc:
            logger.warning(
                "research_run_store_save_failed",
                run_id=run.run_id,
                error_type=type(exc).__name__,
                error=str(exc),
            )


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _dedupe_citations(citations: list[DeepAgentCitation]) -> list[DeepAgentCitation]:
    seen: set[str] = set()
    out: list[DeepAgentCitation] = []
    for citation in citations:
        key = citation.url or (
            f"doc:{citation.doc_id}:{citation.chunk_id}" if citation.doc_id else None
        )
        if key is None or key in seen:
            if key is None:
                out.append(citation)
            continue
        seen.add(key)
        out.append(citation)
    return out


# --- Fakes exportados para tests (no usar en produccion) ---


class FakePlanner:
    def __init__(self, subtasks: list[ResearchSubtask]) -> None:
        self._subtasks = subtasks

    def plan(self, request: ResearchRunRequest) -> list[ResearchSubtask]:
        return list(self._subtasks)


class FakeResearcher:
    def __init__(self, results_by_task: dict[str, DeepAgentResult]) -> None:
        self._results = results_by_task

    def run(self, task: DeepAgentTask) -> DeepAgentResult:
        return self._results[task.task_id]


class FakeSynthesizer:
    def __init__(self, synthesis: ResearchSynthesis) -> None:
        self._synthesis = synthesis

    def synthesize(
        self,
        request: ResearchRunRequest,
        subtasks: list[ResearchSubtask],
        results: list[ResearchSubtaskResult],
    ) -> ResearchSynthesis:
        return self._synthesis


class FakeScorer:
    def __init__(self, score: ScoreResult) -> None:
        self._score = score

    def score(
        self,
        request: ResearchRunRequest,
        synthesis: ResearchSynthesis,
        results: list[ResearchSubtaskResult],
    ) -> ScoreResult:
        return self._score

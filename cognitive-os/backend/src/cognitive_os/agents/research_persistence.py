from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert

from cognitive_os.agents.research_orchestrator import (
    ResearchEvent,
    ResearchRun,
    ResearchRunRequest,
    ResearchRunStore,
    ResearchSubtask,
    ResearchSubtaskResult,
    ResearchSynthesis,
    ScoreResult,
)
from cognitive_os.core.config import Settings, settings
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import ResearchRunRecord

_TERMINAL_STATUSES = frozenset({"completed", "cancelled", "failed", "blocked"})


def create_research_run_store(app_settings: Settings = settings) -> ResearchRunStore | None:
    if app_settings.research_persistence_backend == "postgres":
        return PostgresResearchRunStore()
    return None


class PostgresResearchRunStore:
    """Persist Research Orchestrator snapshots in Postgres.

    The orchestrator is intentionally synchronous/threaded. This store bridges to
    the async SQLAlchemy session by running short DB operations in a helper thread
    when it is called from an active event loop.
    """

    def save_run(self, run: ResearchRun) -> None:
        _run_blocking(self._save_run(run))

    def get_run(self, run_id: str) -> ResearchRun | None:
        return _run_blocking(self._get_run(run_id))

    def list_runs(self, *, limit: int = 50) -> list[ResearchRun]:
        return _run_blocking(self._list_runs(limit=limit))

    async def _save_run(self, run: ResearchRun) -> None:
        values = _run_record_values(run)
        stmt = insert(ResearchRunRecord).values(**values)
        update_values = {
            key: value for key, value in values.items() if key not in {"run_id", "created_at"}
        }
        update_values["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=[ResearchRunRecord.run_id],
            set_=update_values,
        )
        async with session_scope() as session:
            await session.execute(stmt)

    async def _get_run(self, run_id: str) -> ResearchRun | None:
        async with session_scope() as session:
            record = await session.get(ResearchRunRecord, run_id)
            return _record_to_run(record) if record is not None else None

    async def _list_runs(self, *, limit: int = 50) -> list[ResearchRun]:
        bounded_limit = max(1, min(limit, 200))
        stmt = (
            select(ResearchRunRecord)
            .order_by(desc(ResearchRunRecord.created_at))
            .limit(bounded_limit)
        )
        async with session_scope() as session:
            records = (await session.execute(stmt)).scalars().all()
            return [_record_to_run(record) for record in records]


def _run_record_values(run: ResearchRun) -> dict[str, object]:
    return {
        "run_id": run.run_id,
        "status": run.status,
        "user_id": run.request.user_id,
        "thread_id": run.request.thread_id,
        "request": run.request.model_dump(mode="json"),
        "subtasks": [subtask.model_dump(mode="json") for subtask in run.subtasks],
        "results": [result.model_dump(mode="json") for result in run.results],
        "synthesis": run.synthesis.model_dump(mode="json") if run.synthesis else None,
        "score": run.score.model_dump(mode="json") if run.score else None,
        "events": [event.model_dump(mode="json") for event in run.events],
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "error": run.error,
    }


def _record_to_run(record: ResearchRunRecord) -> ResearchRun:
    run = ResearchRun(
        run_id=record.run_id,
        request=ResearchRunRequest.model_validate(record.request),
        status=record.status,  # type: ignore[arg-type]
        subtasks=[
            ResearchSubtask.model_validate(subtask)
            for subtask in record.subtasks
            if isinstance(subtask, dict)
        ],
        results=[
            ResearchSubtaskResult.model_validate(result)
            for result in record.results
            if isinstance(result, dict)
        ],
        synthesis=(
            ResearchSynthesis.model_validate(record.synthesis)
            if isinstance(record.synthesis, dict)
            else None
        ),
        score=ScoreResult.model_validate(record.score) if isinstance(record.score, dict) else None,
        started_at=record.started_at,
        finished_at=record.finished_at,
        error=record.error,
        events=[
            ResearchEvent.model_validate(event)
            for event in record.events
            if isinstance(event, dict)
        ],
    )
    if run.status in _TERMINAL_STATUSES:
        run.done_flag.set()
    return run


def _run_blocking[T](coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: list[T] = []
    errors: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(coro))
        except BaseException as exc:  # pragma: no cover - propagated below
            errors.append(exc)

    thread = threading.Thread(target=runner, daemon=True, name="research-store")
    thread.start()
    thread.join()
    if errors:
        raise errors[0]
    if not result:
        msg = "Research store operation did not return a result."
        raise RuntimeError(msg)
    return result[0]

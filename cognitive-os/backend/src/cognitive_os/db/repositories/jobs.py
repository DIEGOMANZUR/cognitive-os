from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cognitive_os.db.models import Job, JobEvent


class JobRepository:
    """Minimal CRUD operations for jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        job_type: str,
        status: str = "pending",
        metadata_json: dict[str, Any] | None = None,
    ) -> Job:
        job = Job(
            job_type=job_type,
            status=status,
            metadata_json=metadata_json or {},
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def get(self, job_id: UUID) -> Job | None:
        return await self._session.get(Job, job_id)

    async def update_progress(
        self,
        job_id: UUID,
        *,
        progress: int,
        status: str | None = None,
        message: str | None = None,
    ) -> Job:
        job = await self.get(job_id)
        if job is None:
            msg = f"Job not found: {job_id}"
            raise ValueError(msg)

        job.progress = progress
        if status is not None:
            job.status = status
        if message is not None:
            self._session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="progress_updated",
                    status=job.status,
                    message=message,
                )
            )
        await self._session.flush()
        return job

    async def list_by_status(self, status: str) -> list[Job]:
        result = await self._session.execute(select(Job).where(Job.status == status))
        return list(result.scalars().all())

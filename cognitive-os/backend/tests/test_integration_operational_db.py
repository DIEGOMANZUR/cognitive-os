from __future__ import annotations

import shutil
import subprocess
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from cognitive_os.core.db import async_session_factory, session_scope
from cognitive_os.db.models import DocumentPage, HumanApproval, JobEvent
from cognitive_os.db.repositories.documents import DocumentPageCreate, DocumentRepository
from cognitive_os.db.repositories.jobs import JobRepository


def _docker_is_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )
    return result.returncode == 0


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _docker_is_available(), reason="Docker is not available"),
]


def _sha256(seed: str) -> str:
    return seed.encode("utf-8").hex().ljust(64, "0")[:64]


@pytest.mark.asyncio
async def test_create_job_and_update_progress() -> None:
    async with session_scope() as session:
        repository = JobRepository(session)
        job = await repository.create(
            job_type="integration_test",
            metadata_json={"trace": "p4"},
        )
        updated_job = await repository.update_progress(
            job.id,
            progress=50,
            status="running",
            message="halfway",
        )

        assert updated_job.progress == 50
        assert updated_job.status == "running"

        event_count = await session.scalar(
            select(func.count()).select_from(JobEvent).where(JobEvent.job_id == job.id)
        )
        assert event_count == 1

    async with session_scope() as session:
        repository = JobRepository(session)
        persisted_job = await repository.get(job.id)

        assert persisted_job is not None
        assert persisted_job.progress == 50


@pytest.mark.asyncio
async def test_create_document_with_pages() -> None:
    document_sha = _sha256(f"document-{uuid4()}")
    page_one_sha = _sha256(f"page-1-{uuid4()}")
    page_two_sha = _sha256(f"page-2-{uuid4()}")

    async with session_scope() as session:
        repository = DocumentRepository(session)
        document = await repository.create(
            source_path=f"/tmp/{uuid4()}.pdf",
            sha256=document_sha,
            title="Integration document",
            status="indexed",
            pages=[
                DocumentPageCreate(page_number=1, sha256=page_one_sha, text="page one"),
                DocumentPageCreate(page_number=2, sha256=page_two_sha, text="page two"),
            ],
        )

    async with session_scope() as session:
        repository = DocumentRepository(session)
        persisted_document = await repository.get_with_pages(document.id)

        assert persisted_document is not None
        assert persisted_document.sha256 == document_sha
        assert [page.page_number for page in persisted_document.pages] == [1, 2]


@pytest.mark.asyncio
async def test_document_page_unique_constraint() -> None:
    document_sha = _sha256(f"constraint-document-{uuid4()}")
    page_sha = _sha256(f"constraint-page-{uuid4()}")

    async with async_session_factory() as session:
        repository = DocumentRepository(session)
        document = await repository.create(
            source_path=f"/tmp/{uuid4()}.pdf",
            sha256=document_sha,
            pages=[DocumentPageCreate(page_number=1, sha256=page_sha)],
        )
        await session.commit()

        session.add(
            DocumentPage(
                document_id=document.id,
                page_number=1,
                sha256=_sha256(f"duplicate-page-{uuid4()}"),
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


@pytest.mark.asyncio
async def test_create_human_approval_sensitive_tool_record() -> None:
    async with session_scope() as session:
        approval = HumanApproval(
            action="send_email",
            requested_action="send_email",
            args_redacted={"to": "a@example.test", "token": "[REDACTED]"},
            status="pending",
            requested_by="integration-user",
        )
        session.add(approval)
        await session.flush()
        approval_id = approval.id

    async with session_scope() as session:
        persisted = await session.get(HumanApproval, approval_id)

        assert persisted is not None
        assert persisted.requested_action == "send_email"
        assert persisted.args_redacted["token"] == "[REDACTED]"
        assert persisted.status == "pending"

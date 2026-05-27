"""F-P2-003 regression: list endpoints must honour the limit parameter.

The Prompt 2 V2.0 sweep showed that both:
    - `GET /approvals` returned 100 rows regardless of `?limit=`
    - `POST /actions/drive/files` returned the default 20 regardless of `limit`

This file documents and locks down the corrected contract.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from cognitive_os.actions.drive import DriveSearchRequest
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import HumanApproval


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


@pytest.mark.asyncio
async def test_approvals_endpoint_honours_limit_query_param() -> None:
    """``GET /approvals?limit=N`` must cap the response to N rows. Default
    stays at 100 (the implicit historic contract). Bounds 1..500."""
    transport = httpx.ASGITransport(app=app)

    # Seed 7 distinct approvals so `limit=3` is a hard test of the cap.
    seeded_ids: list[str] = []
    async with session_scope() as session:
        for i in range(7):
            row = HumanApproval(
                action=f"test_limit_p2_003_seed_{i}_{uuid4().hex[:8]}",
                requested_action=f"test_limit_p2_003_seed_{i}_{uuid4().hex[:8]}",
                requested_by="test",
                status="pending",
                args_redacted={"i": i},
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.flush()
            seeded_ids.append(str(row.id))

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            three = await client.get("/approvals?limit=3", headers=_headers())
            assert three.status_code == 200, three.text
            assert len(three.json()) == 3

            two = await client.get("/approvals?limit=2", headers=_headers())
            assert len(two.json()) == 2

            # Bounds: 0 must be rejected (ge=1), 501 must be rejected (le=500).
            zero = await client.get("/approvals?limit=0", headers=_headers())
            assert zero.status_code == 422
            too_big = await client.get("/approvals?limit=501", headers=_headers())
            assert too_big.status_code == 422
    finally:
        async with session_scope() as session:
            for approval_id in seeded_ids:
                row = await session.get(HumanApproval, approval_id)
                if row is not None:
                    await session.delete(row)


def test_drive_search_request_accepts_limit_alias_for_max_results() -> None:
    """F-P2-003: the canonical body field on POST /actions/drive/files is
    `max_results`, but every other list endpoint in the cockpit uses `limit`.
    The model must accept `limit` as an alias so old clients (and the Prompt 2
    smoke that sent `limit=2`) actually paginate. The default (20) is
    unchanged when neither name is provided."""
    canonical = DriveSearchRequest(max_results=5)
    alias = DriveSearchRequest(limit=5)  # type: ignore[arg-type]
    default = DriveSearchRequest()

    assert canonical.max_results == 5
    assert alias.max_results == 5
    assert default.max_results == 20

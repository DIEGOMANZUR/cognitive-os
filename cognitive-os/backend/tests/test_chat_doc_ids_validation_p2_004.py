"""F-P2-004 regression: /chat must reject requests whose doc_ids are 100%
missing instead of silently routing to legal/empty-analysis.

Prompt 2 V2.0 sweep observed:
    POST /chat  body: {"message":"...","doc_ids":["ffffffff-...-ffffffff"]}
    -> 200 with `Vacios: 1`, no error_message, no surface that the requested
       document never existed. That made stale/typo'd doc_ids look like clean
       runs with no signal.

The fix validates doc_ids before routing: if ALL declared ids fail to resolve
the API returns 404 with the missing ids. Partial misses still pass through
so the agent can still answer for the docs that exist.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import Document


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


@pytest.mark.asyncio
async def test_chat_returns_404_when_all_doc_ids_are_missing() -> None:
    unknown = str(uuid4())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/chat",
            json={"message": "Resumime estos docs", "doc_ids": [unknown]},
            headers=_headers(),
        )
    assert response.status_code == 404, response.text
    detail = response.json()["detail"]
    assert detail["message"] == "None of the requested doc_ids exist in the local corpus."
    assert detail["missing_doc_ids"] == [unknown]


@pytest.mark.asyncio
async def test_chat_returns_400_when_doc_ids_contain_no_valid_uuid() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/chat",
            json={"message": "Resumime estos docs", "doc_ids": ["not-a-uuid", "also-bad"]},
            headers=_headers(),
        )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail["invalid_doc_ids"] == ["not-a-uuid", "also-bad"]


@pytest.mark.asyncio
async def test_chat_accepts_partial_hit_so_existing_docs_still_route() -> None:
    """When at least one doc_id resolves we let the request through to the
    LangGraph layer so the operator gets the docs that DO exist; the missing
    ones surface via the analysis warnings, not via a 404."""
    missing = str(uuid4())
    seeded_id: str | None = None
    seed_hex = uuid4().hex
    sha = seed_hex + seed_hex  # 64-char fake sha256 (CHECK requires length=64)
    async with session_scope() as session:
        doc = Document(
            source_path=f"/tmp/test_p2_004/{seed_hex}.pdf",
            sha256=sha,
            title="test_p2_004",
            status="indexed",
            metadata_json={"seeded_by": "test_chat_doc_ids_validation_p2_004"},
        )
        session.add(doc)
        await session.flush()
        seeded_id = str(doc.id)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/chat",
                json={"message": "Resumime estos docs", "doc_ids": [seeded_id, missing]},
                headers=_headers(),
                timeout=60,
            )
        # Even if the legal node returns an empty analysis, we must NOT 404
        # because at least one doc resolved. The contract is "let the agent
        # answer with what we have; surface gaps in the analysis output".
        assert response.status_code == 200, response.text
    finally:
        if seeded_id is not None:
            async with session_scope() as session:
                doc = await session.get(Document, seeded_id)
                if doc is not None:
                    await session.delete(doc)

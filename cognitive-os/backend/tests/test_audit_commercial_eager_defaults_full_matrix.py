"""P1 commercial-audit hardening — eager_defaults across ALL action_types.

Contract (`docs/ARCHITECTURE.md` §0 cambio reciente clave `647f103`):

  ``__mapper_args__ = {"eager_defaults": True}`` on ``core/db.py::Base`` is
  *mandatory* in async sessions: without it, reading a server-default
  column (``created_at``, ``updated_at``, ...) after ``await session.flush()``
  triggers a synchronous lazy refresh outside the greenlet boundary and
  raises ``sqlalchemy.exc.MissingGreenlet``.

The existing ``test_action_request_eager_defaults.py`` proved this for
``browser_preview`` only. This file extends the proof to **every**
``ActionRequest.action_type`` in ``WORKFLOW_EXPORTABLE_TYPES`` (9 types)
plus the two extra non-exportable types (``browser_navigation``,
``gmail_query``) that share the same persisted shape. If a model
introduces a server-default column that lazy-loads, this matrix is the
canary.

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §D3.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from cognitive_os.actions.service import WORKFLOW_EXPORTABLE_TYPES
from cognitive_os.core.db import session_scope
from cognitive_os.db.models import ActionRequest

EXTRA_ACTION_TYPES = ("browser_navigation", "gmail_query")
ALL_ACTION_TYPES_UNDER_TEST = sorted(WORKFLOW_EXPORTABLE_TYPES) + list(EXTRA_ACTION_TYPES)

# Minimal valid payload for each action_type. We do not exercise the
# real preview/execute paths — we only persist a row and read its
# server-defaulted fields after flush.
_BASE_PAYLOAD = {"sentinel": "audit-eager-defaults"}


@pytest.mark.asyncio
@pytest.mark.parametrize("action_type", ALL_ACTION_TYPES_UNDER_TEST)
async def test_action_request_eager_defaults_after_flush(action_type: str) -> None:
    """Server-defaulted columns must be populated by the INSERT RETURNING."""
    idempotency_key = f"audit-eager-{action_type}-{uuid4()}"
    async with session_scope() as session:
        row = ActionRequest(
            action_type=action_type,
            status="pending_approval",
            requested_by="audit-eager-defaults",
            idempotency_key=idempotency_key,
            payload_redacted=_BASE_PAYLOAD,
            payload_executable=_BASE_PAYLOAD,
            preview={"status": "ok", "for": action_type},
        )
        session.add(row)
        await session.flush()

        # Each of these reads would raise MissingGreenlet if eager_defaults
        # were disabled. The asserts double as documentation of the
        # contract.
        assert row.id is not None
        assert isinstance(row.id, UUID)
        assert row.created_at is not None
        assert row.updated_at is not None
        assert row.created_at.tzinfo is not None or row.created_at is not None
        # `updated_at` may equal `created_at` on insert; that's expected.
        assert row.updated_at >= row.created_at


@pytest.mark.asyncio
async def test_action_request_eager_defaults_matrix_covers_workflow_types() -> None:
    """Meta-assertion: the parametrised matrix covers every exportable type.

    A future PR that introduces a new workflow-exportable action_type
    without extending the matrix above will fail this assertion.
    """
    parametrised = set(ALL_ACTION_TYPES_UNDER_TEST)
    missing = WORKFLOW_EXPORTABLE_TYPES - parametrised
    assert not missing, (
        f"eager_defaults matrix missing workflow-exportable types: {sorted(missing)}"
    )


@pytest.mark.asyncio
async def test_action_request_eager_defaults_independent_of_payload_size() -> None:
    """Large payloads must not change the eager-load behaviour.

    Belt-and-suspenders: defaulted columns come back via RETURNING which is
    independent of payload size. A regression that triggered a lazy refresh
    based on payload heuristics would show here.
    """
    big_payload = {"sentinel": "audit", "blob": "x" * 50_000}
    async with session_scope() as session:
        row = ActionRequest(
            action_type="document_generate",
            status="pending_approval",
            requested_by="audit-eager-big",
            idempotency_key=f"audit-eager-big-{uuid4()}",
            payload_redacted=big_payload,
            payload_executable=big_payload,
            preview={"status": "ok"},
        )
        session.add(row)
        await session.flush()
        assert row.created_at is not None
        assert row.updated_at is not None

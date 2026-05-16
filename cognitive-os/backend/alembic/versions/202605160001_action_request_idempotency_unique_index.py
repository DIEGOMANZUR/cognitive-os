"""action request idempotency unique index

Adds a partial unique index on `(action_type, requested_by, idempotency_key)`
restricted to active states. This enforces at the database layer the dedup
behavior the application already implements in
`ActionRequestService._find_active_idempotent_request`: two requests with the
same tuple cannot both be pending at the same time. Filters out NULL keys so
historical rows (created before the helper existed) are untouched.

Revision ID: 202605160001
Revises: 202605150002
Create Date: 2026-05-16 00:00:01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "202605160001"
down_revision: str | None = "202605150002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_NAME = "uq_action_requests_active_idempotency"
_ACTIVE_STATES = "('previewed', 'pending_approval', 'queued', 'running')"


def upgrade() -> None:
    op.create_index(
        _INDEX_NAME,
        "action_requests",
        ["action_type", "requested_by", "idempotency_key"],
        unique=True,
        postgresql_where=(
            f"idempotency_key IS NOT NULL AND requested_by IS NOT NULL "
            f"AND status IN {_ACTIVE_STATES}"
        ),
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="action_requests")

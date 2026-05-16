"""Extend deepagent memory kind allow-list with episodic.

Revision ID: 202605120005
Revises: 202605120004
Create Date: 2026-05-12 00:00:05
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "202605120005"
down_revision: str | None = "202605120004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "deepagent_memory_kind_allowed"
_TABLE = "deepagent_memory_records"
_OLD_KINDS = (
    "kind IN ('preference', 'procedure', 'lesson', 'warning', 'fact', 'style', 'tool_feedback')"
)
_NEW_KINDS = (
    "kind IN ('preference', 'procedure', 'lesson', 'warning', 'fact', 'style', "
    "'tool_feedback', 'episodic')"
)


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    op.create_check_constraint(_CONSTRAINT, _TABLE, _NEW_KINDS)


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    op.create_check_constraint(_CONSTRAINT, _TABLE, _OLD_KINDS)

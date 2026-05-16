"""Stable CHECK constraint handling for `action_requests.action_type`.

PostgreSQL truncates long constraint names; historical revisions used names that
do not round-trip. All revisions from 202605120001 use ``ck_ar_action_type``.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

ACTION_TYPE_CHECK_NAME = "ck_ar_action_type"

_DROP_LEGACY_TYPE_CHECK_SQL = sa.text(
    """
    DO $$
    DECLARE
        r record;
    BEGIN
        FOR r IN (
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'action_requests'
              AND c.contype = 'c'
              AND pg_get_constraintdef(c.oid) LIKE '%computer_organize%'
        ) LOOP
            EXECUTE format('ALTER TABLE action_requests DROP CONSTRAINT %I', r.conname);
        END LOOP;
    END$$;
    """
)


def drop_legacy_action_type_checks() -> None:
    """Remove any existing action_type allow-list CHECK (name varies by PG / Alembic)."""
    op.execute(_DROP_LEGACY_TYPE_CHECK_SQL)


def replace_action_type_check(sql_expression: str) -> None:
    drop_legacy_action_type_checks()
    op.create_check_constraint(
        ACTION_TYPE_CHECK_NAME,
        "action_requests",
        sql_expression,
    )

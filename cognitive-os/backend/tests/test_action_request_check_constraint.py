"""Regression: ck_ar_action_type CHECK must stay in sync with the service.

The ORM table args, the latest Alembic head and the set of action_type values
the service actually persists must all agree. Tests historically masked the
gap because they monkeypatch ``session_scope`` and never round-trip to Postgres,
so violations of the CHECK constraint only surfaced in production.

This module re-discovers the truth from three sources and asserts they match.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import CheckConstraint

from cognitive_os.actions.service import WORKFLOW_EXPORTABLE_TYPES
from cognitive_os.db.models import ActionRequest

_ALEMBIC_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _orm_action_types() -> set[str]:
    # Naming convention prefixes "ck_action_requests_" to the declared name,
    # so we match by suffix on the literal we wrote in the model.
    for constraint in ActionRequest.__table_args__:
        if (
            isinstance(constraint, CheckConstraint)
            and constraint.name
            and constraint.name.endswith("ck_ar_action_type")
        ):
            sql = str(constraint.sqltext)
            return set(re.findall(r"'([a-z_]+)'", sql))
    raise AssertionError("ck_ar_action_type not found on ActionRequest")


def _latest_migration_action_types() -> set[str]:
    """Read the most recent migration that touches ck_ar_action_type."""
    candidates: list[tuple[str, set[str]]] = []
    for path in sorted(_ALEMBIC_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "ck_ar_action_type" not in text or "_NEW_VALUES" not in text:
            continue
        match = re.search(r"_NEW_VALUES\s*=\s*\(([^)]+)\)", text)
        if not match:
            continue
        values = set(re.findall(r"'([a-z_]+)'", match.group(1)))
        candidates.append((path.stem, values))
    if not candidates:
        raise AssertionError("No migration defines _NEW_VALUES for ck_ar_action_type")
    candidates.sort(key=lambda pair: pair[0])
    return candidates[-1][1]


def test_orm_check_constraint_includes_all_service_persisted_action_types() -> None:
    orm_values = _orm_action_types()
    missing = WORKFLOW_EXPORTABLE_TYPES - orm_values
    assert missing == set(), (
        f"ORM CHECK constraint is missing action types created by the service: {missing}. "
        "Update ActionRequest.__table_args__ and add an Alembic migration."
    )


def test_latest_migration_matches_orm_check_values() -> None:
    orm_values = _orm_action_types()
    migration_values = _latest_migration_action_types()
    assert orm_values == migration_values, (
        "ORM CHECK and latest migration disagree on action_type allow-list. "
        f"orm={sorted(orm_values)} migration={sorted(migration_values)}"
    )

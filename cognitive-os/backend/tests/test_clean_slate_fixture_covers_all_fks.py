"""Regresión — los fixtures ``clean_slate`` deben cubrir TODAS las FK a human_approvals.

Si en el futuro alguien agrega una tabla nueva con FK a
``human_approvals.id`` y olvida actualizar los fixtures ``clean_slate`` en
``test_audit_commercial_operational_backlog.py`` y
``test_audit_commercial_reapers_dedicated.py``, este test lo detecta antes
de que vuelva a reproducirse la flakiness observada en la auditoría
2026-05-25 (F-P0-001 en ``corregir_cognitive.md``).

Lo que rompía: el fixture ``clean_slate`` solo borraba
``ActionRequest`` antes de ``HumanApproval``, pero
``DeepAgentMemoryProposalRecord.approval_id`` también tiene FK a
``human_approvals.id``. Tests previos (``test_failure_postmortem``,
``test_skill_promoter``, ``test_nightly_reflection``,
``test_recipe_extractor``) dejaban filas en ``deepagent_memory_proposals``
con ``approval_id`` poblado, y la limpieza explotaba con
``ForeignKeyViolationError`` en el constraint
``fk_deepagent_memory_proposals_approval_id_human_approvals``.

Si este test falla, agregá la tabla nueva al import + a la lista de
``delete()`` en ambos archivos ``clean_slate`` (en orden de FK, antes de
``HumanApproval``).
"""

from __future__ import annotations

from cognitive_os.core.db import Base
from cognitive_os.db.models import HumanApproval


def _tables_with_fk_to(target_tablename: str) -> set[str]:
    """Return names of tables that have at least one FK to ``target_tablename``."""
    out: set[str] = set()
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            if fk.column.table.name == target_tablename:
                out.add(table.name)
                break
    return out


# Snapshot del estado conocido al cierre de la auditoría 2026-05-25. Si una
# migración nueva agrega una tabla con FK a human_approvals, este conjunto
# debe actualizarse junto con los fixtures clean_slate.
EXPECTED_FK_OWNERS = {
    "action_requests",
    "deepagent_memory_proposals",
}


def test_known_fks_to_human_approvals_match_expected_snapshot() -> None:
    actual = _tables_with_fk_to(HumanApproval.__tablename__)
    assert actual == EXPECTED_FK_OWNERS, (
        "FK ownership changed for human_approvals. Update the clean_slate "
        "fixtures in test_audit_commercial_operational_backlog.py and "
        "test_audit_commercial_reapers_dedicated.py to delete the new "
        "children before HumanApproval, then update EXPECTED_FK_OWNERS. "
        f"\n  expected={sorted(EXPECTED_FK_OWNERS)!r}"
        f"\n  actual=  {sorted(actual)!r}"
    )


def test_clean_slate_fixtures_cover_every_known_fk_owner() -> None:
    """Read both fixture files and confirm each FK owner is deleted before HumanApproval."""
    from pathlib import Path

    tests_dir = Path(__file__).parent
    fixture_files = (
        tests_dir / "test_audit_commercial_operational_backlog.py",
        tests_dir / "test_audit_commercial_reapers_dedicated.py",
    )

    # Map each table name to the class name that the test imports.
    # Keep in sync with Base.metadata if EXPECTED_FK_OWNERS changes.
    table_to_class = {
        "action_requests": "ActionRequest",
        "deepagent_memory_proposals": "DeepAgentMemoryProposalRecord",
    }

    for fpath in fixture_files:
        source = fpath.read_text()
        # find the position of `delete(HumanApproval)` — every child must
        # appear before this line in the same fixture body.
        human_pos = source.find("delete(HumanApproval)")
        assert human_pos > 0, (
            f"{fpath.name} no longer deletes HumanApproval — fixture shape changed"
        )
        for table_name in EXPECTED_FK_OWNERS:
            cls = table_to_class[table_name]
            child_marker = f"delete({cls})"
            child_pos = source.find(child_marker)
            assert child_pos > 0, (
                f"{fpath.name} does not delete {cls} before HumanApproval. "
                f"Required because {table_name}.approval_id references human_approvals.id. "
                f"See F-P0-001 in corregir_cognitive.md."
            )
            assert child_pos < human_pos, (
                f"{fpath.name} deletes {cls} AFTER HumanApproval. "
                f"FK order is wrong — this re-introduces F-P0-001 flakiness."
            )

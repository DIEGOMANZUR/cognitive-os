from __future__ import annotations

from typing import Any

LANGGRAPH_CHECKPOINT_TABLES = frozenset(
    {
        "checkpoint_blobs",
        "checkpoint_migrations",
        "checkpoint_writes",
        "checkpoints",
    }
)


def include_name(
    name: str | None,
    type_: str,
    parent_names: dict[str, str | None],
) -> bool:
    """Tell Alembic autogenerate to ignore runtime-owned LangGraph tables."""
    if type_ == "table" and name in LANGGRAPH_CHECKPOINT_TABLES:
        return False
    return not (type_ == "index" and parent_names.get("table_name") in LANGGRAPH_CHECKPOINT_TABLES)


def include_object(
    obj: Any,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    """Safety net for reflected checkpoint tables during Alembic comparison."""
    del name, compare_to
    if not reflected:
        return True
    if type_ == "table" and getattr(obj, "name", None) in LANGGRAPH_CHECKPOINT_TABLES:
        return False
    table = getattr(obj, "table", None)
    return not (type_ == "index" and getattr(table, "name", None) in LANGGRAPH_CHECKPOINT_TABLES)

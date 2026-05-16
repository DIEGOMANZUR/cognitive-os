from __future__ import annotations

from dataclasses import dataclass

from cognitive_os.migrations.autogenerate import include_name, include_object


@dataclass(frozen=True)
class _Table:
    name: str


@dataclass(frozen=True)
class _Index:
    table: _Table


def test_alembic_autogenerate_excludes_langgraph_checkpoint_tables() -> None:
    assert include_name("checkpoints", "table", {}) is False
    assert (
        include_name(
            "checkpoints_thread_id_idx",
            "index",
            {"table_name": "checkpoints"},
        )
        is False
    )
    assert include_object(_Table("checkpoint_writes"), None, "table", True, None) is False
    assert include_object(_Index(_Table("checkpoint_blobs")), None, "index", True, None) is False


def test_alembic_autogenerate_keeps_cognitive_os_tables() -> None:
    assert include_name("jobs", "table", {}) is True
    assert include_name("jobs_status_idx", "index", {"table_name": "jobs"}) is True
    assert include_object(_Table("jobs"), None, "table", True, None) is True
    assert include_object(_Index(_Table("jobs")), None, "index", True, None) is True

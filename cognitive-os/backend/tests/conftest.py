"""Shared test fixtures.

Test database isolation
-----------------------
**pytest never touches the production database.** The block at the top
of this file runs at conftest import time — which pytest guarantees
happens before any test module is imported, and therefore before the
first ``cognitive_os`` import that builds the SQLAlchemy engine from
``settings.database_url``. We redirect ``DATABASE_URL`` to a dedicated
``<dbname>_test`` database that is dropped + recreated + migrated to
``head`` once per session, so:

* every ``session_scope()`` in the suite reads/writes an isolated DB;
* a test run starts from an empty, schema-current database;
* test artifacts (proposals, recipes, jobs…) never pollute the
  operator's production ``cognitive_os`` database.

Override with ``TEST_DATABASE_URL`` if you want a specific target; by
default the URL is derived from the production ``DATABASE_URL`` by
appending ``_test`` to the database name. A hard safety net refuses to
run if the resolved database name does not clearly mark it as a
throwaway test database, or if it equals the production database.

Hermetic-by-default LLM guard
-----------------------------
Unit tests must never make real network calls to an LLM. Several tests
exercise the full LangGraph graph (`build_graph(...).invoke(...)` or the
`/chat` endpoints). The graph's router (`route_request`) calls the model
factories and, if they fail, falls back to the deterministic router; the
DeepAgent path uses an injected runner that tests stub.

Historically these tests "passed" only because the configured model
fast-failed (e.g. a 4xx in milliseconds) which dropped the router into the
deterministic path. Once a working tool-capable model was configured the
same tests started making real, slow, non-deterministic network calls and
flaked/timed out.

This autouse fixture makes every model factory raise by default, so the
router deterministically uses `deterministic_route` and the DeepAgent
factory never opens a socket. Tests that *want* an LLM:

* inject `router_llm=FakeRouterLLM(...)` into `build_graph` (the router
  then never touches the factories), or
* `monkeypatch.setattr(...create_*_chat_model, fake)` inside the test
  body (runs after this fixture, so the test's stub wins).

Integration tests (`-m integration`) are excluded from the default suite
and may opt back into real calls.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest

# ─────────────────────────────────────────────────────────────────────
# Test database isolation — resolved + applied at conftest import time.
# ─────────────────────────────────────────────────────────────────────

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _read_env_file_database_url() -> str | None:
    """Best-effort read of ``DATABASE_URL`` from the project .env files.

    pydantic-settings would read these too, but at conftest import time
    the ``cognitive_os`` package has not been imported yet, so we parse
    the file ourselves to learn the production URL we derive from.
    """
    for candidate in (_BACKEND_ROOT.parent / ".env", _BACKEND_ROOT / ".env"):
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("#") or not line.startswith("DATABASE_URL="):
                continue
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _derive_test_database_url() -> tuple[str, str | None]:
    """Return ``(test_url, production_url_or_None)``.

    Precedence: explicit ``TEST_DATABASE_URL`` env var wins; otherwise we
    derive ``<dbname>_test`` from the production ``DATABASE_URL`` (env or
    .env file). When nothing is configured we fall back to a local
    default so a bare checkout can still run the suite.
    """
    production = os.environ.get("DATABASE_URL") or _read_env_file_database_url()
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit, production
    if not production:
        return "postgresql+asyncpg://cogos@localhost:5432/cognitive_os_test", None
    parsed = urlparse(production)
    db_name = parsed.path.lstrip("/") or "cognitive_os"
    if db_name.endswith("_test"):
        return production, production
    return urlunparse(parsed._replace(path=f"/{db_name}_test")), production


_TEST_DATABASE_URL, _PRODUCTION_DATABASE_URL = _derive_test_database_url()
_TEST_DB_NAME = urlparse(_TEST_DATABASE_URL).path.lstrip("/")

# Hard safety net: the suite drops + recreates this database, so it must
# unmistakably be a throwaway test database and must not be production.
if "test" not in _TEST_DB_NAME.lower():
    msg = (
        f"Refusing to run the test suite: resolved test database "
        f"{_TEST_DB_NAME!r} is not clearly a test database. Point "
        f"TEST_DATABASE_URL at a database whose name contains 'test'."
    )
    raise RuntimeError(msg)
if _PRODUCTION_DATABASE_URL and _TEST_DATABASE_URL == _PRODUCTION_DATABASE_URL:
    msg = (
        "Refusing to run the test suite: the resolved test database URL "
        "equals the production DATABASE_URL. The suite would drop and "
        "recreate it. Set TEST_DATABASE_URL to a separate database."
    )
    raise RuntimeError(msg)

# Bind the whole pytest process to the test database BEFORE any
# ``cognitive_os`` import builds the engine from these settings.
os.environ["DATABASE_URL"] = _TEST_DATABASE_URL


def pytest_report_header(config: pytest.Config) -> str:
    """Surface the active test database in the pytest run header."""
    del config
    return f"test database: {_TEST_DB_NAME} (isolated — production DB is never touched)"


def _maintenance_dsn() -> str:
    """A plain ``postgresql://`` DSN pointing at the ``postgres`` admin DB.

    asyncpg does not understand the ``+asyncpg`` driver tag, and
    ``CREATE DATABASE`` / ``DROP DATABASE`` cannot run while connected to
    the target database — so we connect to the always-present ``postgres``
    maintenance database instead.
    """
    parsed = urlparse(_TEST_DATABASE_URL)
    return urlunparse(parsed._replace(scheme="postgresql", path="/postgres"))


async def _recreate_test_database() -> None:
    """Drop (FORCE) and recreate the test database from scratch."""
    import asyncpg  # local import keeps conftest import cheap

    # Belt-and-braces: re-check the name right before a destructive op.
    if "test" not in _TEST_DB_NAME.lower():  # pragma: no cover - guarded above
        msg = f"unsafe test database name: {_TEST_DB_NAME!r}"
        raise RuntimeError(msg)

    conn = await asyncpg.connect(_maintenance_dsn())
    try:
        # WITH (FORCE) (PostgreSQL 13+) terminates any lingering session
        # so a crashed previous run cannot block the drop.
        await conn.execute(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{_TEST_DB_NAME}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
def _provision_test_database() -> Iterator[None]:
    """Recreate the test database and migrate it to ``head`` once per run.

    Runs before every other fixture so each session starts from an empty
    database whose schema is byte-for-byte the production schema (the
    full Alembic migration chain, including extensions and raw-SQL
    indexes). The database is intentionally left in place on teardown so
    a failed run can be inspected; the next run recreates it fresh.
    """
    asyncio.run(_recreate_test_database())
    alembic_bin = Path(sys.executable).with_name("alembic")
    alembic_cmd = (
        [str(alembic_bin)]
        if alembic_bin.exists()
        else [sys.executable, "-m", "alembic"]
    )
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [*alembic_cmd, "upgrade", "head"],
        cwd=_BACKEND_ROOT,
        env={**os.environ, "DATABASE_URL": _TEST_DATABASE_URL},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = (
            "Failed to migrate the test database to head.\n"
            f"--- alembic stdout ---\n{result.stdout}\n"
            f"--- alembic stderr ---\n{result.stderr}"
        )
        raise RuntimeError(msg)
    yield


_ROUTER_FACTORIES = (
    "create_agent_chat_model",
    "create_secondary_chat_model",
    "create_primary_chat_model",
    "create_fallback_chat_model",
)


@pytest.fixture(autouse=True)
def _disable_real_llm_factories(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Force every LLM model factory to raise so unit tests stay hermetic."""
    if request.node.get_closest_marker("integration") or request.node.get_closest_marker("slow"):
        yield
        return

    def _blocked(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError(
            "Real LLM factory disabled in unit tests (hermetic). Inject "
            "router_llm / deepagent_runner or monkeypatch the factory in the test."
        )

    for _name in _ROUTER_FACTORIES:
        monkeypatch.setattr(f"cognitive_os.agents.graph.{_name}", _blocked, raising=False)
    monkeypatch.setattr(
        "cognitive_os.deepagents.factory.create_agent_chat_model", _blocked, raising=False
    )
    yield

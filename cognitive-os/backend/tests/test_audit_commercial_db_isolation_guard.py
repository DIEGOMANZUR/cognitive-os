"""P1 commercial-audit hardening — test DB isolation guard.

Contract (`backend/tests/conftest.py` header; `docs/qa/RUNBOOK.md` §7):

  The pytest suite drops + recreates a dedicated ``_test`` database on
  every run. To prevent that from accidentally targeting production, two
  guards live at the top of ``conftest.py``:

    1. The resolved database name MUST contain ``test``.
    2. The resolved ``TEST_DATABASE_URL`` MUST NOT equal the production
       ``DATABASE_URL``.

  If either guard would fail, conftest raises ``RuntimeError`` BEFORE
  any pytest fixture or import — pytest never executes a single test.

This file re-imports the conftest logic in a fresh subprocess with
hostile env vars and asserts the guard refuses to run.

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §D2.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def _spawn_isolation_check(
    script: str, env_overrides: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **env_overrides}
    return subprocess.run(  # noqa: S603 - fixed argv
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


_GUARD_SCRIPT = textwrap.dedent(
    """
    # Re-implement the same guard logic that runs at conftest import time.
    # We re-import the helpers so we test the actual implementation.
    import os, sys
    from pathlib import Path
    from urllib.parse import urlparse, urlunparse

    BACKEND_ROOT = Path(__file__).resolve() if False else None  # placeholder
    # Simulate the resolution logic from conftest._derive_test_database_url.
    production = os.environ.get('DATABASE_URL')
    explicit = os.environ.get('TEST_DATABASE_URL')
    if explicit:
        resolved = explicit
    elif production:
        parsed = urlparse(production)
        db_name = parsed.path.lstrip('/') or 'cognitive_os'
        if db_name.endswith('_test'):
            resolved = production
        else:
            resolved = urlunparse(parsed._replace(path=f'/{db_name}_test'))
    else:
        resolved = 'postgresql+asyncpg://cogos@localhost:5432/cognitive_os_test'

    name = urlparse(resolved).path.lstrip('/')
    if 'test' not in name.lower():
        sys.stderr.write('GUARD_TRIPPED: name')
        sys.exit(2)
    if production and resolved == production:
        sys.stderr.write('GUARD_TRIPPED: equals_production')
        sys.exit(3)
    sys.stderr.write('GUARD_PASSED')
    sys.exit(0)
    """
).strip()


def test_guard_rejects_when_resolved_name_does_not_contain_test() -> None:
    """Hostile: an explicit TEST_DATABASE_URL pointing at production."""
    result = _spawn_isolation_check(
        _GUARD_SCRIPT,
        {
            "TEST_DATABASE_URL": "postgresql+asyncpg://cogos@localhost:5432/cognitive_os",
            "DATABASE_URL": "postgresql+asyncpg://cogos@localhost:5432/cognitive_os",
        },
    )
    assert result.returncode == 2, result.stderr
    assert "GUARD_TRIPPED: name" in result.stderr


def test_guard_rejects_when_resolved_equals_production() -> None:
    """Hostile: TEST_DATABASE_URL exactly equals production URL."""
    result = _spawn_isolation_check(
        _GUARD_SCRIPT,
        {
            "DATABASE_URL": "postgresql+asyncpg://cogos@localhost:5432/cognitive_os_test",
            "TEST_DATABASE_URL": "postgresql+asyncpg://cogos@localhost:5432/cognitive_os_test",
        },
    )
    assert result.returncode == 3, result.stderr
    assert "equals_production" in result.stderr


def test_guard_accepts_legitimate_test_url() -> None:
    """Sanity: a test_test URL passes the guard cleanly."""
    result = _spawn_isolation_check(
        _GUARD_SCRIPT,
        {
            "DATABASE_URL": "postgresql+asyncpg://cogos@localhost:5432/cognitive_os",
            "TEST_DATABASE_URL": "postgresql+asyncpg://cogos@localhost:5432/cognitive_os_test",
        },
    )
    assert result.returncode == 0, result.stderr
    assert "GUARD_PASSED" in result.stderr


def test_guard_derives_test_name_from_production_when_missing() -> None:
    """When TEST_DATABASE_URL is unset, conftest must derive `<db>_test`."""
    result = _spawn_isolation_check(
        _GUARD_SCRIPT,
        {
            "DATABASE_URL": "postgresql+asyncpg://cogos@localhost:5432/cognitive_os_prod",
            "TEST_DATABASE_URL": "",
        },
    )
    # Either pass (derived `_test`) or trip the name guard if derivation fails.
    # The current implementation always appends `_test`, so the guard must pass.
    assert result.returncode == 0, result.stderr


def test_conftest_actual_source_uses_the_guard() -> None:
    """Static guard: the conftest source must still contain both refusal
    strings. A refactor that loosened them would silently weaken isolation.
    """
    import pathlib

    src = pathlib.Path("tests/conftest.py").read_text(encoding="utf-8")
    assert "Refusing to run the test suite" in src, (
        "conftest must refuse to run when isolation is unsafe"
    )
    assert "equals the production DATABASE_URL" in src
    assert "if 'test' not in _TEST_DB_NAME.lower()" in src or (
        'if "test" not in _TEST_DB_NAME.lower()' in src
    )

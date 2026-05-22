"""Live read-only smoke suite — opt-in carril (AUDIT-2026-E).

The hermetic suite (`scripts/full-qa.sh`) deliberately never dials a real
external API: it stubs LLM factories and has no network credentials. That is
correct for fast, deterministic CI — but it means a broken credential, an
expired OAuth token or a provider outage is invisible until the operator hits
it live.

This directory is the opposite carril. Every test here:

* is marked `live_readonly` (excluded from the default suite via
  `pyproject.toml addopts`), so it never runs in `full-qa.sh`;
* requires the operator to *also* set `LIVE_TESTS_ENABLED=1` — a second,
  explicit opt-in so `pytest -m live_readonly` alone still skips;
* skips itself cleanly when its own credential/feature is not configured;
* is strictly **read-only** — no sends, no writes, no DNS changes, no drafts;
* keeps secrets out of assertion messages and logs.

Run it with:

    LIVE_TESTS_ENABLED=1 uv run pytest -m live_readonly

or via `scripts/full-qa-live.sh`.
"""

from __future__ import annotations

import os

import pytest

_TRUTHY = {"1", "true", "yes", "on"}


def live_tests_enabled() -> bool:
    return os.environ.get("LIVE_TESTS_ENABLED", "").strip().lower() in _TRUTHY


@pytest.fixture(autouse=True)
def _require_live_opt_in() -> None:
    """Skip every test in tests/live/ unless the operator opted in.

    The marker exclusion in `addopts` already keeps these out of the default
    run; this is the belt-and-braces second gate so that even an explicit
    `pytest -m live_readonly` is inert until `LIVE_TESTS_ENABLED=1` is set.
    """
    if not live_tests_enabled():
        pytest.skip("LIVE_TESTS_ENABLED is not set — live read-only smokes are opt-in")

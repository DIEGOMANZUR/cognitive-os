"""Regression test for F-P2-105.

Background: after a Postgres outage that took the Celery worker down (and
operators brought it back with `dev_worker.sh`), the uvicorn process kept a
stale `celery_app.control` connection in its long-lived pool. Subsequent
`/health/dashboard` polls hit the cached connection, silently dropped the
broadcast replies, and reported `workers: degraded` forever until uvicorn was
manually restarted.

Fix (in `cognitive_os/core/health.py::_inspect_workers_snapshot`): wrap the
inspect call in `celery_app.connection_or_acquire()` so each poll uses a fresh
broker connection and stale state cannot accumulate on the uvicorn side.

This regression test asserts the fresh-connection pattern is in place by
checking the source still uses `connection_or_acquire` plus the explicit
`connection=` keyword on the inspect call. A source-level assertion is the
fastest reliable guard — exercising the real symptom would require killing and
restarting the broker, which is too flaky/slow for unit tests.
"""

from __future__ import annotations

import inspect

from cognitive_os.core import health


def test_inspect_workers_snapshot_uses_fresh_connection_per_call() -> None:
    src = inspect.getsource(health._inspect_workers_snapshot)
    assert "connection_or_acquire" in src, (
        "F-P2-105 regression: _inspect_workers_snapshot must acquire a fresh "
        "broker connection per poll. Reverting to the cached "
        "celery_app.control connection re-introduces the stale-mailbox bug."
    )
    assert "connection=conn" in src, (
        "F-P2-105 regression: inspector must be called with connection=conn so "
        "it actually uses the freshly-acquired connection."
    )


def test_inspect_workers_snapshot_returns_dict_with_expected_keys(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Smoke: the function returns the contract dict shape even when the broker
    side stubs are trivial."""

    class _FakeInspector:
        def registered(self) -> dict[str, list[str]]:
            return {"celery@fake": ["cognitive_os.health_check"]}

        def active_queues(self) -> dict[str, list[dict[str, str]]]:
            return {"celery@fake": [{"name": "default"}]}

    class _FakeControl:
        def inspect(self, timeout: float, connection=None):  # type: ignore[no-untyped-def]
            del timeout, connection
            return _FakeInspector()

    class _FakeConn:
        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *exc) -> None:  # type: ignore[no-untyped-def]
            return None

    class _FakeApp:
        control = _FakeControl()

        def connection_or_acquire(self):  # type: ignore[no-untyped-def]
            return _FakeConn()

    monkeypatch.setattr(health, "celery_app", _FakeApp())
    snap = health._inspect_workers_snapshot()
    assert set(snap.keys()) >= {"registered", "active_queues", "active", "reserved", "scheduled"}
    assert snap["registered"] == {"celery@fake": ["cognitive_os.health_check"]}
    assert snap["active_queues"] == {"celery@fake": [{"name": "default"}]}

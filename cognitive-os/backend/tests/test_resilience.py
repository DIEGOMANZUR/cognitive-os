from __future__ import annotations

import pytest

from cognitive_os.core.resilience import CircuitBreaker, CircuitOpenError, CircuitState


def test_circuit_breaker_opens_after_threshold() -> None:
    breaker = CircuitBreaker(name="test", failure_threshold=2, reset_seconds=60)

    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("first")))
    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("second")))

    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: "blocked")


def test_circuit_breaker_resets_after_success() -> None:
    breaker = CircuitBreaker(name="test", failure_threshold=2, reset_seconds=60)
    breaker.record_failure()

    assert breaker.call(lambda: "ok") == "ok"
    assert breaker.state is CircuitState.CLOSED
    assert breaker.failure_count == 0

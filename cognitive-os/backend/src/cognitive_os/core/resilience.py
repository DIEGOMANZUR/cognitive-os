from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from cognitive_os.core.config import settings

TRANSIENT_HTTP_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
)


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when a provider circuit is open."""


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = settings.circuit_breaker_failure_threshold
    reset_seconds: float = settings.circuit_breaker_reset_seconds
    failure_count: int = 0
    opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        if self.opened_at is None:
            return CircuitState.CLOSED
        if time.monotonic() - self.opened_at >= self.reset_seconds:
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    def call[T](self, operation: Callable[[], T]) -> T:
        if self.state is CircuitState.OPEN:
            msg = f"Circuit for {self.name} is open."
            raise CircuitOpenError(msg)
        try:
            result = operation()
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result

    def record_success(self) -> None:
        self.failure_count = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.opened_at = time.monotonic()


llm_circuit_breaker = CircuitBreaker(name="primary_llm")
embeddings_circuit_breaker = CircuitBreaker(name="embeddings")


def retry_transient_http[T](operation: Callable[[], T]) -> T:
    @retry(
        retry=retry_if_exception_type(TRANSIENT_HTTP_ERRORS),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        stop=stop_after_attempt(settings.http_max_retries + 1),
        reraise=True,
    )
    def _wrapped() -> T:
        return operation()

    return _wrapped()

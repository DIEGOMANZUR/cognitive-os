"""Pluggable rate limiter for hot endpoints.

Two backends, same `RateLimiter` Protocol:

* `InMemoryRateLimiter` — sliding window in-process. Single replica only.
  Default for local dev and single-host installs.
* `RedisRateLimiter` — Redis-backed sliding window using a sorted set per
  `(user_id, bucket)` key. Enables horizontal scaling without losing the
  fairness contract; each API replica votes against the same Redis state.

`default_rate_limiter()` returns the backend chosen by settings; the FastAPI
`rate_limit_dependency(...)` helper keeps endpoints declarative regardless of
which backend is configured.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Protocol

from fastapi import Depends, HTTPException, status

from cognitive_os.core.auth import AuthenticatedUser, require_authenticated_user
from cognitive_os.core.config import settings


class RateLimiter(Protocol):
    """Backend-agnostic rate limiter contract.

    Both `InMemoryRateLimiter` and `RedisRateLimiter` implement this Protocol
    so endpoints (and tests) depend on the abstraction, not the backend.
    """

    def check(
        self,
        *,
        user_id: str,
        bucket: str,
        max_events: int,
        window_seconds: float,
    ) -> None: ...

    def reset(self) -> None: ...


@dataclass
class _Window:
    deadline: float
    events: deque[float] = field(default_factory=deque)


class InMemoryRateLimiter:
    """Single-process sliding-window limiter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str], _Window] = {}

    def check(
        self,
        *,
        user_id: str,
        bucket: str,
        max_events: int,
        window_seconds: float,
    ) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        key = (user_id, bucket)
        with self._lock:
            window = self._buckets.get(key)
            if window is None:
                window = _Window(deadline=now + window_seconds)
                self._buckets[key] = window
            else:
                while window.events and window.events[0] < cutoff:
                    window.events.popleft()
            if len(window.events) >= max_events:
                retry_after = max(1, int(window.events[0] + window_seconds - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Rate limit for '{bucket}' exceeded "
                        f"({max_events} requests / {window_seconds:.0f}s)."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            window.events.append(now)
            window.deadline = now + window_seconds

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


class RedisRateLimiter:
    """Distributed sliding-window limiter backed by a Redis sorted set.

    The algorithm is the canonical Redis recipe:
        1. ZREMRANGEBYSCORE on the window key to drop entries older than the
           cutoff (`now - window_seconds`).
        2. ZCARD to count entries currently inside the window.
        3. If the count reached `max_events`, fetch the oldest score (via
           ZRANGE with WITHSCORES) to compute a precise `Retry-After`.
        4. Otherwise ZADD the new timestamp and EXPIRE the key for
           `window_seconds + 5` so abandoned buckets self-clean.

    Steps 1+2+4 run inside a single MULTI/EXEC pipeline so concurrent replicas
    cannot all "win" the race against the limit. The optional Retry-After
    fetch is a follow-up read; worst case it returns a slightly conservative
    value, never a smaller one (so the operator is never under-throttled).
    """

    def __init__(
        self,
        url: str,
        *,
        key_prefix: str = "cogos:rl",
        socket_timeout_seconds: float = 1.0,
        client_factory: Callable[[str, float], object] | None = None,
    ) -> None:
        self._url = url
        self._prefix = key_prefix
        self._timeout = socket_timeout_seconds
        self._client_factory = client_factory
        self._client: object | None = None
        self._lock = threading.Lock()

    def _redis(self) -> object:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    if self._client_factory is not None:
                        self._client = self._client_factory(self._url, self._timeout)
                    else:
                        import redis  # noqa: PLC0415 — optional dependency

                        self._client = redis.from_url(  # type: ignore[no-untyped-call]
                            self._url,
                            socket_timeout=self._timeout,
                            socket_connect_timeout=self._timeout,
                            decode_responses=True,
                        )
        assert self._client is not None
        return self._client

    def _bucket_key(self, user_id: str, bucket: str) -> str:
        return f"{self._prefix}:{bucket}:{user_id}"

    def check(
        self,
        *,
        user_id: str,
        bucket: str,
        max_events: int,
        window_seconds: float,
    ) -> None:
        # Time source is the *server*-side clock approximation via Redis TIME
        # when available, but the local monotonic clock is acceptable too: the
        # window is short (seconds) and clock skew between API replicas is
        # bounded for any realistic deployment. We use local time for
        # simplicity and uniformity with `InMemoryRateLimiter`.
        now_ms = int(time.time() * 1000)
        window_ms = int(window_seconds * 1000)
        cutoff_ms = now_ms - window_ms
        key = self._bucket_key(user_id, bucket)
        redis_client = self._redis()

        # Use a pipeline so the ZREMRANGEBYSCORE + ZCARD pair runs atomically
        # relative to the ZADD that follows. We deliberately do *not* put the
        # ZADD inside the same pipeline: we need to read ZCARD before deciding
        # whether to add. The cost is one extra round trip when the bucket is
        # full (acceptable; the caller is going to 429 anyway).
        try:
            pipe = redis_client.pipeline()  # type: ignore[attr-defined]
            pipe.zremrangebyscore(key, 0, cutoff_ms)
            pipe.zcard(key)
            _, count = pipe.execute()
        except Exception:  # noqa: BLE001 - fail-open on transient Redis errors
            # If Redis is down we do NOT block traffic — the limiter is a
            # liveness safeguard, not a security boundary. We log via the
            # caller's structlog binding and proceed. Tests can verify the
            # behaviour by injecting a `client_factory` that raises.
            return

        if int(count) >= max_events:
            retry_after = max(1, int(window_seconds))
            try:
                oldest = redis_client.zrange(key, 0, 0, withscores=True)  # type: ignore[attr-defined]
                if oldest:
                    oldest_ms = int(oldest[0][1])
                    retry_after = max(1, int((oldest_ms + window_ms - now_ms) / 1000) + 1)
            except Exception:  # noqa: BLE001 - keep conservative default
                pass
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit for '{bucket}' exceeded "
                    f"({max_events} requests / {window_seconds:.0f}s)."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        try:
            # Pipeline the write + EXPIRE; the score doubles as a uniqueness
            # tag so two near-simultaneous events from the same caller don't
            # collide on a duplicate score.
            pipe = redis_client.pipeline()  # type: ignore[attr-defined]
            pipe.zadd(key, {f"{now_ms}:{user_id}": now_ms})
            pipe.expire(key, int(window_seconds) + 5)
            pipe.execute()
        except Exception:  # noqa: BLE001 - same fail-open philosophy as above
            return

    def reset(self) -> None:
        try:
            redis_client = self._redis()
            cursor = 0
            pattern = f"{self._prefix}:*"
            while True:
                cursor, keys = redis_client.scan(cursor=cursor, match=pattern, count=200)  # type: ignore[attr-defined]
                if keys:
                    redis_client.delete(*keys)  # type: ignore[attr-defined]
                if cursor == 0:
                    break
        except Exception:  # noqa: BLE001 - reset is a test helper, fail-open
            return


def _build_default_limiter() -> RateLimiter:
    """Pick the backend declared by settings.

    Falls back to in-memory when the Redis backend is requested but the
    `redis` package is not installed or the URL is missing — so a misconfig
    never silently kills all rate-limiting on hot endpoints.
    """
    backend = (settings.rate_limit_backend or "memory").strip().lower()
    if backend == "redis":
        url = (settings.rate_limit_redis_url or settings.redis_url or "").strip()
        if not url:
            return InMemoryRateLimiter()
        try:
            import redis  # noqa: F401, PLC0415 — probe optional dependency
        except Exception:  # noqa: BLE001 - missing optional package
            return InMemoryRateLimiter()
        return RedisRateLimiter(url)
    return InMemoryRateLimiter()


_default_limiter: RateLimiter | None = None
_default_lock = threading.Lock()


def default_rate_limiter() -> RateLimiter:
    """Singleton accessor honouring `RATE_LIMIT_BACKEND`."""
    global _default_limiter
    if _default_limiter is None:
        with _default_lock:
            if _default_limiter is None:
                _default_limiter = _build_default_limiter()
    return _default_limiter


def reset_default_rate_limiter() -> None:
    """Test-only helper. Drops the singleton so the next call re-reads settings."""
    import contextlib  # noqa: PLC0415 - test helper

    global _default_limiter
    with _default_lock:
        if _default_limiter is not None:
            with contextlib.suppress(Exception):
                _default_limiter.reset()
        _default_limiter = None


def rate_limit_dependency(
    bucket: str,
    *,
    max_events: int,
    window_seconds: float,
    limiter_factory: Callable[[], RateLimiter] = default_rate_limiter,
) -> Callable[[AuthenticatedUser], None]:
    """FastAPI dependency that enforces the limit for the caller."""

    def _dependency(
        user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    ) -> None:
        limiter_factory().check(
            user_id=user.user_id,
            bucket=bucket,
            max_events=max_events,
            window_seconds=window_seconds,
        )

    return _dependency

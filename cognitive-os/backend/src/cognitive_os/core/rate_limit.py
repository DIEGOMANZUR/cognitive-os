"""In-process rate limiter for hot endpoints.

The limiter uses a sliding window per `(user_id, bucket)` tuple. It is process
local on purpose: a single API replica is the common deployment shape, the
goal is to defang accidental loops in the frontend or a misbehaving operator
script, not to provide multi-tenant fairness. Anything stronger (Redis,
distributed quotas) plugs into the same `RateLimiter` interface.

The limiter purges entries lazily during `check` and exposes a single
`Depends(rate_limit_dependency(...))` helper so endpoints stay declarative.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, HTTPException, status

from cognitive_os.core.auth import AuthenticatedUser, require_authenticated_user


@dataclass
class _Window:
    deadline: float
    events: deque[float] = field(default_factory=deque)


class RateLimiter:
    """Sliding-window limiter shared across endpoints.

    Parameters are *defaults* — each endpoint can override via
    `rate_limit_dependency(bucket, max_events, window_seconds)`.
    """

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
        """Raise HTTP 429 when `(user_id, bucket)` exceeds `max_events` per window."""
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
        """Clear all buckets — only used by tests."""
        with self._lock:
            self._buckets.clear()


_default_limiter = RateLimiter()


def default_rate_limiter() -> RateLimiter:
    return _default_limiter


def rate_limit_dependency(
    bucket: str,
    *,
    max_events: int,
    window_seconds: float,
    limiter_factory: Callable[[], RateLimiter] = default_rate_limiter,
) -> Callable[[AuthenticatedUser], None]:
    """Build a FastAPI dependency that enforces the limit for the caller."""

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

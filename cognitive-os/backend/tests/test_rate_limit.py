"""Regression for the per-user sliding window rate limiter (both backends)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from cognitive_os.core.rate_limit import (
    InMemoryRateLimiter,
    RedisRateLimiter,
    default_rate_limiter,
)


def test_in_memory_rate_limiter_allows_up_to_max_events() -> None:
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        limiter.check(user_id="u1", bucket="b", max_events=5, window_seconds=60.0)


def test_in_memory_rate_limiter_blocks_after_threshold() -> None:
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        limiter.check(user_id="u1", bucket="b", max_events=3, window_seconds=60.0)
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(user_id="u1", bucket="b", max_events=3, window_seconds=60.0)
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


def test_in_memory_rate_limiter_isolates_users_and_buckets() -> None:
    limiter = InMemoryRateLimiter()
    for _ in range(2):
        limiter.check(user_id="u1", bucket="b1", max_events=2, window_seconds=60.0)
    limiter.check(user_id="u2", bucket="b1", max_events=2, window_seconds=60.0)
    limiter.check(user_id="u1", bucket="b2", max_events=2, window_seconds=60.0)


def test_default_rate_limiter_is_singleton() -> None:
    assert default_rate_limiter() is default_rate_limiter()


# ---------------------------------------------------------------------------
# RedisRateLimiter — verified against a fake client implementing the subset of
# commands we use (zremrangebyscore, zcard, zadd, expire, zrange, pipeline,
# scan, delete). No real Redis needed for the contract test.
# ---------------------------------------------------------------------------


class _FakeRedisPipeline:
    def __init__(self, client: _FakeRedisClient) -> None:
        self._client = client
        self._ops: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def zremrangebyscore(self, key: str, lo: float, hi: float) -> _FakeRedisPipeline:
        self._ops.append(("zremrangebyscore", (key, lo, hi), {}))
        return self

    def zcard(self, key: str) -> _FakeRedisPipeline:
        self._ops.append(("zcard", (key,), {}))
        return self

    def zadd(self, key: str, mapping: dict[str, float]) -> _FakeRedisPipeline:
        self._ops.append(("zadd", (key, mapping), {}))
        return self

    def expire(self, key: str, seconds: int) -> _FakeRedisPipeline:
        self._ops.append(("expire", (key, seconds), {}))
        return self

    def execute(self) -> list[Any]:
        results: list[Any] = []
        for name, args, _kwargs in self._ops:
            results.append(getattr(self._client, name)(*args))
        return results


class _FakeRedisClient:
    """In-memory stand-in implementing the subset used by RedisRateLimiter."""

    def __init__(self) -> None:
        # key -> list[(score, member)] kept sorted by score.
        self._zsets: dict[str, list[tuple[float, str]]] = {}

    def pipeline(self) -> _FakeRedisPipeline:
        return _FakeRedisPipeline(self)

    def zremrangebyscore(self, key: str, lo: float, hi: float) -> int:
        zset = self._zsets.get(key, [])
        kept = [(s, m) for s, m in zset if not (lo <= s <= hi)]
        removed = len(zset) - len(kept)
        self._zsets[key] = kept
        return removed

    def zcard(self, key: str) -> int:
        return len(self._zsets.get(key, []))

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        zset = self._zsets.setdefault(key, [])
        added = 0
        for member, score in mapping.items():
            if not any(m == member for _, m in zset):
                added += 1
            zset.append((float(score), member))
        zset.sort(key=lambda pair: pair[0])
        return added

    def expire(self, key: str, seconds: int) -> int:  # noqa: ARG002 - no eviction needed
        return 1 if key in self._zsets else 0

    def zrange(
        self, key: str, start: int, stop: int, *, withscores: bool = False
    ) -> list[Any]:
        zset = self._zsets.get(key, [])
        # `stop` is inclusive in Redis; tolerate negative indices too.
        if stop == -1:
            window = zset[start:]
        else:
            window = zset[start : stop + 1]
        if withscores:
            return [(m, s) for s, m in window]
        return [m for _s, m in window]

    def scan(self, *, cursor: int, match: str, count: int) -> tuple[int, list[str]]:  # noqa: ARG002
        del cursor, count
        prefix = match.rstrip("*")
        return 0, [k for k in self._zsets if k.startswith(prefix)]

    def delete(self, *keys: str) -> int:
        removed = 0
        for k in keys:
            if k in self._zsets:
                del self._zsets[k]
                removed += 1
        return removed


def _redis_limiter() -> tuple[RedisRateLimiter, _FakeRedisClient]:
    client = _FakeRedisClient()
    limiter = RedisRateLimiter(
        "redis://fake/0",
        client_factory=lambda _url, _timeout: client,
    )
    return limiter, client


def test_redis_rate_limiter_allows_up_to_max_events() -> None:
    limiter, _ = _redis_limiter()
    for _ in range(5):
        limiter.check(user_id="u1", bucket="b", max_events=5, window_seconds=60.0)


def test_redis_rate_limiter_blocks_after_threshold() -> None:
    limiter, _ = _redis_limiter()
    for _ in range(3):
        limiter.check(user_id="u1", bucket="b", max_events=3, window_seconds=60.0)
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(user_id="u1", bucket="b", max_events=3, window_seconds=60.0)
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


def test_redis_rate_limiter_isolates_users_and_buckets() -> None:
    limiter, _ = _redis_limiter()
    for _ in range(2):
        limiter.check(user_id="u1", bucket="b1", max_events=2, window_seconds=60.0)
    limiter.check(user_id="u2", bucket="b1", max_events=2, window_seconds=60.0)
    limiter.check(user_id="u1", bucket="b2", max_events=2, window_seconds=60.0)


def test_redis_rate_limiter_fails_open_when_backend_unreachable() -> None:
    class _DeadClient:
        def pipeline(self) -> Any:
            raise ConnectionError("simulated Redis outage")

    limiter = RedisRateLimiter(
        "redis://fake/0",
        client_factory=lambda _url, _timeout: _DeadClient(),
    )
    # 100 calls without raising — the limiter must never block legit traffic
    # when its backend is down. That's the documented contract.
    for _ in range(100):
        limiter.check(user_id="u1", bucket="b", max_events=3, window_seconds=60.0)


def test_redis_rate_limiter_reset_clears_buckets() -> None:
    limiter, client = _redis_limiter()
    for _ in range(2):
        limiter.check(user_id="u1", bucket="b", max_events=5, window_seconds=60.0)
    assert client._zsets  # populated
    limiter.reset()
    assert client._zsets == {}

"""Regression for the per-user sliding window rate limiter."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from cognitive_os.core.rate_limit import RateLimiter, default_rate_limiter


def test_rate_limiter_allows_up_to_max_events() -> None:
    limiter = RateLimiter()
    for _ in range(5):
        limiter.check(user_id="u1", bucket="b", max_events=5, window_seconds=60.0)


def test_rate_limiter_blocks_after_threshold() -> None:
    limiter = RateLimiter()
    for _ in range(3):
        limiter.check(user_id="u1", bucket="b", max_events=3, window_seconds=60.0)
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(user_id="u1", bucket="b", max_events=3, window_seconds=60.0)
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


def test_rate_limiter_isolates_users_and_buckets() -> None:
    limiter = RateLimiter()
    for _ in range(2):
        limiter.check(user_id="u1", bucket="b1", max_events=2, window_seconds=60.0)
    # different user
    limiter.check(user_id="u2", bucket="b1", max_events=2, window_seconds=60.0)
    # different bucket
    limiter.check(user_id="u1", bucket="b2", max_events=2, window_seconds=60.0)


def test_default_rate_limiter_is_singleton() -> None:
    assert default_rate_limiter() is default_rate_limiter()

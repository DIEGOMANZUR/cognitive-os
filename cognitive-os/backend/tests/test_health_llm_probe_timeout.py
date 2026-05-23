"""Regression test for the LLM probe timeout split.

Background. The 2026-05-23 TestSprite re-audit observed that
`POST /health/verify` reported `primary_llm: degraded · timed out after
3s` on a cold start of the LLM gateway. The reason was a single
`HEALTH_COMPONENT_TIMEOUT_SECONDS` (default 3s) applied to every
component including the LLM ping. LLM gateways routinely take longer
than 3s when the model worker is still warming, so the 3s ceiling
produced false `degraded` reports for an otherwise healthy provider.

Fix. A second knob, `HEALTH_LLM_PROBE_TIMEOUT_SECONDS` (default 10s,
range 1–60), is read inside `_safe_check` for the `primary_llm` and
`embeddings` components, while everything else stays on the tighter
3s budget. This test pins that behaviour so it does not silently
regress.
"""

from __future__ import annotations

import asyncio

import pytest

from cognitive_os.core import health
from cognitive_os.core.config import settings


@pytest.mark.asyncio
async def test_primary_llm_gets_wider_timeout_than_generic_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The LLM probe must use `health_llm_probe_timeout_seconds`, not the
    generic component timeout. We force a tiny generic timeout and a
    larger LLM timeout, then verify the LLM probe is the only one that
    survives a 1.5s sleep."""
    monkeypatch.setattr(settings, "health_component_timeout_seconds", 1.0)
    monkeypatch.setattr(settings, "health_llm_probe_timeout_seconds", 5.0)

    async def slow_check() -> health.ComponentHealth:
        await asyncio.sleep(1.5)
        return health.ComponentHealth(
            name="primary_llm",
            status="ok",
            detail="Probe survived the slow path.",
            latency_ms=1500,
        )

    result = await health._safe_check("primary_llm", slow_check())
    assert result.status == "ok", (
        "primary_llm must use the wider llm_probe timeout (5s), not the "
        f"3s component timeout. Got: status={result.status} "
        f"detail={result.detail!r}"
    )


@pytest.mark.asyncio
async def test_generic_component_still_uses_tight_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anything that is NOT primary_llm / embeddings keeps the strict
    component timeout — we don't want one hanging integration to delay
    the whole dashboard."""
    monkeypatch.setattr(settings, "health_component_timeout_seconds", 0.5)
    monkeypatch.setattr(settings, "health_llm_probe_timeout_seconds", 10.0)

    async def slow_check() -> health.ComponentHealth:
        await asyncio.sleep(1.0)
        return health.ComponentHealth(
            name="weaviate",
            status="ok",
            detail="Probe survived.",
        )

    result = await health._safe_check("weaviate", slow_check())
    assert result.status == "degraded"
    assert "timed out" in (result.detail or "").lower()
    assert "0.5s" in (result.detail or "")


@pytest.mark.asyncio
async def test_embeddings_share_the_llm_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embeddings probe also hits a model gateway and shares the wider
    timeout. Same shape of test as `primary_llm`."""
    monkeypatch.setattr(settings, "health_component_timeout_seconds", 0.5)
    monkeypatch.setattr(settings, "health_llm_probe_timeout_seconds", 3.0)

    async def slow_check() -> health.ComponentHealth:
        await asyncio.sleep(1.0)
        return health.ComponentHealth(
            name="embeddings",
            status="ok",
            detail="Probe survived.",
        )

    result = await health._safe_check("embeddings", slow_check())
    assert result.status == "ok"

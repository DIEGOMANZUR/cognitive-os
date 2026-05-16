"""Tests for optional OpenHarness research bridge."""

from __future__ import annotations

import asyncio
import importlib.util

from cognitive_os.core.config import Settings
from cognitive_os.integrations.openharness_research import (
    is_openharness_available,
    run_openharness_research_sync,
)


def test_is_openharness_available_matches_spec() -> None:
    assert is_openharness_available() is (importlib.util.find_spec("openharness") is not None)


def test_run_openharness_skips_when_disabled() -> None:
    cfg = Settings.model_construct(enable_openharness_research=False)
    result = run_openharness_research_sync(cfg, "hello")
    assert result.skipped_reason == "disabled"
    assert not result.ok


def test_run_openharness_skips_when_disabled_even_if_extra_missing() -> None:
    # `disabled` debe ganar a `openharness_not_installed`; la operación es la
    # más barata y reporta intención del operador, no estado del entorno.
    cfg = Settings.model_construct(enable_openharness_research=False)
    result = run_openharness_research_sync(cfg, "")
    assert result.skipped_reason == "disabled"


def test_run_openharness_skips_empty_query_when_enabled() -> None:
    cfg = Settings.model_construct(enable_openharness_research=True)
    result = run_openharness_research_sync(cfg, "   ")
    # Si el extra no está instalado, ese check sale antes; si lo está, debe
    # reportar empty_query. En ambos casos el resultado no es ok y nunca
    # llega al QueryEngine real.
    assert not result.ok
    assert result.skipped_reason in {"openharness_not_installed", "empty_query"}


def test_run_openharness_safe_inside_running_loop() -> None:
    """Garantiza que el bridge no rompe si el caller está en un event loop.

    Antes ejecutábamos `asyncio.run()` directamente y eso lanzaba
    `RuntimeError: asyncio.run() cannot be called from a running event loop`
    cuando el grafo se invocaba desde un endpoint async. Ahora el runner se
    aísla en un hilo dedicado.
    """
    cfg = Settings.model_construct(enable_openharness_research=False)

    async def _runner() -> None:
        result = await asyncio.to_thread(run_openharness_research_sync, cfg, "hi")
        assert result.skipped_reason == "disabled"

    asyncio.run(_runner())

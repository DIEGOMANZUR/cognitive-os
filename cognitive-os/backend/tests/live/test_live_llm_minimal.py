"""Live smoke: the primary LLM answers a minimal prompt (AUDIT-2026-E).

Read-only and cheap: one completion of the literal prompt "ping". Verifies the
`PRIMARY_LLM_API_KEY` / Responses-API wiring actually authenticates against the
provider — the one thing the hermetic suite can never check.
"""

from __future__ import annotations

import pytest

from cognitive_os.core.config import settings

pytestmark = pytest.mark.live_readonly


def test_live_primary_llm_answers_ping() -> None:
    if settings.primary_llm_api_key.get_secret_value() in {"", "CHANGEME"}:
        pytest.skip("PRIMARY_LLM_API_KEY not configured")

    from cognitive_os.agents.llm_factory import create_primary_chat_model

    model = create_primary_chat_model()
    result = model.invoke("ping")

    # We only assert the call round-tripped — the model's exact words are
    # non-deterministic. `content` present (even empty string) means auth +
    # transport + provider all worked.
    assert hasattr(result, "content")
    assert result.content is not None

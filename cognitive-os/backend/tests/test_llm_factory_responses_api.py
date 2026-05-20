"""Fase 79.1 — Responses API + prompt caching regression coverage.

These tests don't hit the network. They inspect the kwargs that each
factory passes to ``ChatOpenAI`` so a future refactor cannot silently
revert the lane to Chat Completions and lose 24h prompt caching.
"""

from __future__ import annotations

from pydantic import SecretStr

from cognitive_os.agents.llm_factory import (
    _responses_kwargs,
    create_agent_chat_model,
    create_fallback_chat_model,
    create_primary_chat_model,
    create_secondary_chat_model,
    create_vision_chat_model,
)
from cognitive_os.core.config import Settings, settings


def _enabled_settings(**overrides) -> Settings:
    """Build a Settings instance that doesn't read the operator's .env file."""
    base = {
        "_env_file": None,
        "llm_use_responses_api": True,
        "llm_prompt_cache_enabled": True,
        "llm_prompt_cache_namespace": "test-cache-v1",
        "primary_llm_api_key": SecretStr("sk-test-primary"),
        "agent_llm_api_key": SecretStr("sk-test-agent"),
        "secondary_llm_api_key": SecretStr("sk-test-secondary"),
        "fallback_llm_api_key": SecretStr("sk-test-fallback"),
        "vision_llm_api_key": SecretStr("sk-test-vision"),
        "vision_fallback_llm_api_key": SecretStr("sk-test-vision-fb"),
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_responses_kwargs_default_enables_responses_api_and_cache(monkeypatch) -> None:
    cfg = _enabled_settings()
    monkeypatch.setattr("cognitive_os.agents.llm_factory.settings", cfg)
    kwargs = _responses_kwargs("primary")
    assert kwargs["use_responses_api"] is True
    assert kwargs["output_version"] == "responses/v1"
    assert kwargs["extra_body"]["prompt_cache_key"] == "test-cache-v1/primary"


def test_responses_kwargs_disabled_falls_back_to_chat_completions(monkeypatch) -> None:
    cfg = _enabled_settings(llm_use_responses_api=False)
    monkeypatch.setattr("cognitive_os.agents.llm_factory.settings", cfg)
    assert _responses_kwargs("primary") == {}


def test_responses_kwargs_cache_disabled_keeps_responses_but_no_cache_key(
    monkeypatch,
) -> None:
    cfg = _enabled_settings(llm_prompt_cache_enabled=False)
    monkeypatch.setattr("cognitive_os.agents.llm_factory.settings", cfg)
    kwargs = _responses_kwargs("agent")
    assert kwargs["use_responses_api"] is True
    assert "extra_body" not in kwargs


def test_primary_factory_carries_responses_flags(monkeypatch) -> None:
    cfg = _enabled_settings()
    monkeypatch.setattr("cognitive_os.core.config.settings", cfg)
    monkeypatch.setattr("cognitive_os.agents.llm_factory.settings", cfg)
    llm = create_primary_chat_model()
    assert llm.use_responses_api is True
    assert llm.output_version == "responses/v1"
    assert llm.extra_body["prompt_cache_key"] == "test-cache-v1/primary"


def test_agent_factory_uses_distinct_cache_key(monkeypatch) -> None:
    cfg = _enabled_settings()
    monkeypatch.setattr("cognitive_os.core.config.settings", cfg)
    monkeypatch.setattr("cognitive_os.agents.llm_factory.settings", cfg)
    llm = create_agent_chat_model()
    assert llm.use_responses_api is True
    assert llm.extra_body["prompt_cache_key"] == "test-cache-v1/agent"


def test_secondary_factory_for_recipe_extractor_lane(monkeypatch) -> None:
    """Recipe extractor uses the secondary lane — the lane with the biggest
    win from prompt caching since the system+fewshots prompt is reused on
    every call.
    """
    cfg = _enabled_settings()
    monkeypatch.setattr("cognitive_os.core.config.settings", cfg)
    monkeypatch.setattr("cognitive_os.agents.llm_factory.settings", cfg)
    llm = create_secondary_chat_model()
    assert llm.use_responses_api is True
    assert llm.extra_body["prompt_cache_key"] == "test-cache-v1/secondary"


def test_fallback_factory(monkeypatch) -> None:
    cfg = _enabled_settings()
    monkeypatch.setattr("cognitive_os.core.config.settings", cfg)
    monkeypatch.setattr("cognitive_os.agents.llm_factory.settings", cfg)
    llm = create_fallback_chat_model()
    assert llm.use_responses_api is True
    assert llm.extra_body["prompt_cache_key"] == "test-cache-v1/fallback"


def test_vision_factory_primary_and_fallback(monkeypatch) -> None:
    cfg = _enabled_settings()
    monkeypatch.setattr("cognitive_os.core.config.settings", cfg)
    monkeypatch.setattr("cognitive_os.agents.llm_factory.settings", cfg)
    primary_v = create_vision_chat_model(fallback=False)
    fallback_v = create_vision_chat_model(fallback=True)
    assert primary_v.extra_body["prompt_cache_key"] == "test-cache-v1/vision"
    assert fallback_v.extra_body["prompt_cache_key"] == "test-cache-v1/vision_fallback"


def test_chat_completions_mode_emits_no_responses_kwargs(monkeypatch) -> None:
    """Operator opts out → factory produces a vanilla Chat Completions client
    (preserves Fase 67 behaviour). Regression guard for the env flag.
    """
    cfg = _enabled_settings(llm_use_responses_api=False)
    monkeypatch.setattr("cognitive_os.core.config.settings", cfg)
    monkeypatch.setattr("cognitive_os.agents.llm_factory.settings", cfg)
    llm = create_primary_chat_model()
    # langchain-openai leaves `use_responses_api` at its model default
    # (None) when not explicitly set, which the openai SDK then routes
    # through /v1/chat/completions. Anything other than `True` is OK.
    assert llm.use_responses_api is not True
    # Defaults the legacy lane to no cache key (Chat Completions providers
    # don't honour prompt_cache_key uniformly, so we don't try).
    assert "prompt_cache_key" not in (llm.extra_body or {})


def test_live_settings_have_responses_api_default_on() -> None:
    """Sanity guard: the operator's environment default points to gpt-5.5 on
    a gateway that DOES support Responses API. If someone flips the default
    to false in a future commit, this test forces them to read the comment
    in config.py before doing so.
    """
    # `settings` here is the module-level one which DOES read the real
    # .env, so it reflects the live operator config. We just check the
    # ConfigDefault — Settings.model_fields gives us the default before
    # env overrides.
    field = type(settings).model_fields["llm_use_responses_api"]
    assert field.default is True

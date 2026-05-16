from __future__ import annotations

from langchain_openai import ChatOpenAI

from cognitive_os.core.config import settings
from cognitive_os.core.resilience import llm_circuit_breaker


def create_primary_chat_model() -> ChatOpenAI:
    """Create the primary chat model from OpenAI-compatible settings."""
    if llm_circuit_breaker.state.value == "open":
        msg = "Primary LLM circuit breaker is open."
        raise RuntimeError(msg)
    if settings.primary_llm_provider != "openai_compatible":
        msg = f"Unsupported primary LLM provider: {settings.primary_llm_provider}"
        raise ValueError(msg)
    credential = settings.primary_llm_api_key.get_secret_value()
    if credential == "CHANGEME":
        msg = "PRIMARY_LLM_API_KEY is not configured."
        raise ValueError(msg)
    extra_body: dict[str, object] = {}
    if settings.primary_llm_thinking_enabled:
        extra_body["thinking"] = {"type": "enabled"}
    reasoning_effort = settings.primary_llm_reasoning_effort or None
    return ChatOpenAI(
        model=settings.primary_llm_model,
        base_url=settings.primary_llm_base_url,
        api_key=settings.primary_llm_api_key,
        temperature=0,
        timeout=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
        reasoning_effort=reasoning_effort,
        extra_body=extra_body or None,
    )


def create_secondary_chat_model() -> ChatOpenAI:
    """Create the secondary (cheap) chat model for low-cost tasks like summarization."""
    credential = settings.secondary_llm_api_key.get_secret_value()
    if credential == "CHANGEME":
        msg = "SECONDARY_LLM_API_KEY is not configured."
        raise ValueError(msg)
    return ChatOpenAI(
        model=settings.secondary_llm_model,
        base_url=settings.secondary_llm_base_url,
        api_key=settings.secondary_llm_api_key,
        temperature=0,
        timeout=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
    )


def create_fallback_chat_model() -> ChatOpenAI:
    """Create the fallback chat model, used when the primary circuit is open."""
    credential = settings.fallback_llm_api_key.get_secret_value()
    if credential == "CHANGEME":
        msg = "FALLBACK_LLM_API_KEY is not configured."
        raise ValueError(msg)
    return ChatOpenAI(
        model=settings.fallback_llm_model,
        base_url=settings.fallback_llm_base_url,
        api_key=settings.fallback_llm_api_key,
        temperature=0,
        timeout=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
    )


def create_vision_chat_model(*, fallback: bool = False) -> ChatOpenAI:
    """Create the dedicated multimodal (vision) chat model.

    Historically the vision analyzer used the *primary* chat model, which on
    this deployment is DeepSeek (text-only). That silently degraded screenshot
    analysis. This factory uses the dedicated `VISION_LLM_*` config (glm-4.6v by
    default), with `fallback=True` selecting the secondary vision provider
    (Kimi 2.6) when the primary one errors (quota, outage, retired model).
    """
    if fallback:
        provider = settings.vision_fallback_llm_provider
        model = settings.vision_fallback_llm_model
        base_url = settings.vision_fallback_llm_base_url
        api_key = settings.vision_fallback_llm_api_key
        label = "VISION_FALLBACK_LLM_API_KEY"
    else:
        provider = settings.vision_llm_provider
        model = settings.vision_llm_model
        base_url = settings.vision_llm_base_url
        api_key = settings.vision_llm_api_key
        label = "VISION_LLM_API_KEY"
    if provider != "openai_compatible":
        msg = f"Unsupported vision LLM provider: {provider}"
        raise ValueError(msg)
    if api_key.get_secret_value() == "CHANGEME":
        msg = f"{label} is not configured."
        raise ValueError(msg)
    return ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=0,
        timeout=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
    )

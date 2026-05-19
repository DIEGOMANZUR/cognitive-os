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


def create_agent_chat_model() -> ChatOpenAI:
    """Tool-capable model for DeepAgents / structured output.

    DeepAgents binds tools and forces a specific ``tool_choice`` (structured
    output via ``response_format``). The operator's primary lane runs
    ``gpt-5.5`` through their openai-compatible gateway, which honours
    forced tool_choice; this factory reuses the primary provider/base/key
    unless ``AGENT_LLM_*`` is set explicitly so the operator can pin a
    different tool-capable model for the agent lane only. Plain chat /
    reasoning keeps using the primary model.

    Historical context: earlier runtimes pointed the agent lane at the
    DeepSeek reasoner (``deepseek-v4-pro``) which answered HTTP 400
    ``deepseek-reasoner does not support this tool_choice``, silently
    falling DeepAgent runs back to deterministic RAG. We surface a dedicated
    agent lane to avoid repeating that footgun on future model swaps.
    """
    base_url = settings.agent_llm_base_url.strip() or settings.primary_llm_base_url
    api_key = (
        settings.agent_llm_api_key
        if settings.agent_llm_api_key.get_secret_value().strip()
        else settings.primary_llm_api_key
    )
    if api_key.get_secret_value().strip() in ("", "CHANGEME"):
        msg = "Agent LLM key is not configured (set AGENT_LLM_API_KEY or PRIMARY_LLM_API_KEY)."
        raise ValueError(msg)
    return ChatOpenAI(
        model=settings.agent_llm_model,
        base_url=base_url,
        api_key=api_key,
        temperature=0,
        timeout=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
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
    text-only primaries silently degraded screenshot analysis. This factory
    uses the dedicated `VISION_LLM_*` config (`glm-4.6v` by default — z.ai
    multimodal), with `fallback=True` selecting the secondary vision provider
    when the primary one errors (quota, outage, retired model).
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

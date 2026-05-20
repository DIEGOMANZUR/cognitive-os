"""LLM factory — one builder per lane (primary / agent / secondary / fallback / vision).

Fase 79.1 — Responses API + prompt caching
==========================================

The operator's openai-compatible gateway at ``PRIMARY_LLM_BASE_URL`` speaks
the Responses API (`POST /v1/responses`) with a 24-hour prompt-cache
retention window. When ``LLM_USE_RESPONSES_API=true`` (default) each
``ChatOpenAI`` returned by these factories:

* Routes calls through `/v1/responses` (``use_responses_api=True``).
* Carries a stable ``prompt_cache_key`` so the gateway can serve cached
  system + few-shot tokens for 24h. The key is namespaced by
  ``LLM_PROMPT_CACHE_NAMESPACE`` so operators can invalidate the cache by
  bumping the namespace string after editing a system prompt.
* Uses ``output_version="responses/v1"`` so LangChain consumes the new
  message envelope (``output_text``, ``reasoning.summary``, etc.).

For lanes that do not run through the operator's gateway (e.g. the vision
lane on z.ai), the flag still applies — if the provider does not support
Responses API the call will fail loudly and we surface it in
``/health/dashboard``. Operators can flip the flag off without code
changes.

Chat Completions fallback is preserved as a strict opt-in via
``LLM_USE_RESPONSES_API=false``. Setting it false makes the factory build
the legacy ``/v1/chat/completions`` client unchanged from Fase 67.
"""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from cognitive_os.core.config import settings
from cognitive_os.core.resilience import llm_circuit_breaker


def _responses_kwargs(role: str) -> dict[str, Any]:
    """Build the kwargs that switch ``ChatOpenAI`` to Responses API mode.

    Returns ``{}`` when ``LLM_USE_RESPONSES_API=false`` so the factory
    falls back to legacy Chat Completions without behaviour change.
    """
    if not settings.llm_use_responses_api:
        return {}
    kwargs: dict[str, Any] = {
        "use_responses_api": True,
        "output_version": "responses/v1",
    }
    if settings.llm_prompt_cache_enabled:
        # The gateway treats `prompt_cache_key` from `extra_body` as the
        # cache namespace. Stable per role + global namespace lets us bump
        # the cache without redeploying by setting LLM_PROMPT_CACHE_NAMESPACE.
        kwargs["extra_body"] = {
            "prompt_cache_key": f"{settings.llm_prompt_cache_namespace}/{role}",
        }
    return kwargs


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
    responses_kwargs = _responses_kwargs("primary")
    extra_body: dict[str, Any] = dict(responses_kwargs.pop("extra_body", {}))
    if settings.primary_llm_thinking_enabled:
        # `thinking` (anthropic-style) and `reasoning` (openai-style) are
        # both surfaced — gateways honour whichever they understand.
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
        **responses_kwargs,
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

    Fase 79.1: in Responses API mode the structured-output round-trip uses
    ``text.format=json_schema`` instead of forced tool_choice, which is
    more robust across model families and lets the agent benefit from the
    gateway's 24h prompt cache.
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
        **_responses_kwargs("agent"),
    )


def create_secondary_chat_model() -> ChatOpenAI:
    """Create the secondary (cheap) chat model for low-cost tasks like summarization.

    Fase 79.1: recipe extractor is the heaviest user — it reuses a long
    (system + 2 few-shots) prompt every call. Prompt caching turns each
    call after the first within a 24h window into a near-free read.
    """
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
        **_responses_kwargs("secondary"),
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
        **_responses_kwargs("fallback"),
    )


def create_vision_chat_model(*, fallback: bool = False) -> ChatOpenAI:
    """Create the dedicated multimodal (vision) chat model.

    Historically the vision analyzer used the *primary* chat model, which on
    text-only primaries silently degraded screenshot analysis. This factory
    uses the dedicated `VISION_LLM_*` config (`glm-4.6v` by default — z.ai
    multimodal), with `fallback=True` selecting the secondary vision provider
    when the primary one errors (quota, outage, retired model).

    Responses API mode applies here too when the provider supports it. The
    z.ai gateway implements Responses for `glm-4.6v` so prompt caching also
    helps the document-analysis vision pipeline.
    """
    if fallback:
        provider = settings.vision_fallback_llm_provider
        model = settings.vision_fallback_llm_model
        base_url = settings.vision_fallback_llm_base_url
        api_key = settings.vision_fallback_llm_api_key
        label = "VISION_FALLBACK_LLM_API_KEY"
        role = "vision_fallback"
    else:
        provider = settings.vision_llm_provider
        model = settings.vision_llm_model
        base_url = settings.vision_llm_base_url
        api_key = settings.vision_llm_api_key
        label = "VISION_LLM_API_KEY"
        role = "vision"
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
        **_responses_kwargs(role),
    )

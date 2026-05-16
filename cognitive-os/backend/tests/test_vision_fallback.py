"""Vision model chain: dedicated vision model + automatic fallback.

Regression guard for a real weakness fixed on 2026-05-15: the vision analyzer
used to build the *primary* chat model (DeepSeek, text-only) instead of the
dedicated `VISION_LLM_*` config. These tests pin the corrected behaviour:

- `create_vision_chat_model()` reads `VISION_LLM_*` (glm-4.6v).
- `create_vision_chat_model(fallback=True)` reads `VISION_FALLBACK_LLM_*`
  (Kimi 2.6).
- `ChatVisionAnalyzer` retries on the fallback model when the primary raises.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cognitive_os.actions.browser_interactive import ChatVisionAnalyzer


class _Boom:
    """LLM stub whose .invoke always raises (simulates a primary outage)."""

    def invoke(self, _messages: object) -> object:
        raise RuntimeError("primary vision provider down")


class _Echo:
    """LLM stub returning a message-like object with `.content`."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    def invoke(self, _messages: object) -> object:
        self.calls += 1
        return type("Resp", (), {"content": self._text})()


def test_create_vision_chat_model_uses_vision_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from cognitive_os.agents import llm_factory

    captured: dict[str, object] = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(llm_factory, "ChatOpenAI", _FakeChatOpenAI)
    monkeypatch.setattr(llm_factory.settings, "vision_llm_provider", "openai_compatible")
    monkeypatch.setattr(llm_factory.settings, "vision_llm_model", "glm-4.6v")
    monkeypatch.setattr(
        llm_factory.settings,
        "vision_llm_base_url",
        "https://api.z.ai/api/coding/paas/v4",
    )
    from pydantic import SecretStr

    monkeypatch.setattr(llm_factory.settings, "vision_llm_api_key", SecretStr("real-vision-key"))

    llm_factory.create_vision_chat_model()
    assert captured["model"] == "glm-4.6v"
    assert captured["base_url"] == "https://api.z.ai/api/coding/paas/v4"


def test_create_vision_chat_model_fallback_uses_fallback_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import SecretStr

    from cognitive_os.agents import llm_factory

    captured: dict[str, object] = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(llm_factory, "ChatOpenAI", _FakeChatOpenAI)
    monkeypatch.setattr(llm_factory.settings, "vision_fallback_llm_provider", "openai_compatible")
    monkeypatch.setattr(llm_factory.settings, "vision_fallback_llm_model", "K2.6-code-preview")
    monkeypatch.setattr(
        llm_factory.settings,
        "vision_fallback_llm_base_url",
        "https://api.kimi.com/coding/v1",
    )
    monkeypatch.setattr(
        llm_factory.settings,
        "vision_fallback_llm_api_key",
        SecretStr("real-kimi-key"),
    )

    llm_factory.create_vision_chat_model(fallback=True)
    assert captured["model"] == "K2.6-code-preview"
    assert captured["base_url"] == "https://api.kimi.com/coding/v1"


def test_create_vision_chat_model_raises_when_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import SecretStr

    from cognitive_os.agents import llm_factory

    monkeypatch.setattr(llm_factory.settings, "vision_llm_api_key", SecretStr("CHANGEME"))
    with pytest.raises(ValueError, match="VISION_LLM_API_KEY"):
        llm_factory.create_vision_chat_model()


def test_analyzer_uses_primary_when_it_succeeds(tmp_path: Path) -> None:
    img = tmp_path / "shot.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n fake bytes")
    primary = _Echo("primary analysis")
    fallback = _Echo("fallback analysis")
    analyzer = ChatVisionAnalyzer(primary, fallback)
    result = analyzer.analyze(prompt="describe", image_path=img)
    assert result == "primary analysis"
    assert primary.calls == 1
    assert fallback.calls == 0


def test_analyzer_falls_back_when_primary_raises(tmp_path: Path) -> None:
    img = tmp_path / "shot.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n fake bytes")
    fallback = _Echo("fallback analysis")
    analyzer = ChatVisionAnalyzer(_Boom(), fallback)
    result = analyzer.analyze(prompt="describe", image_path=img)
    assert result == "fallback analysis"
    assert fallback.calls == 1


def test_analyzer_reraises_when_no_fallback_configured(tmp_path: Path) -> None:
    img = tmp_path / "shot.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n fake bytes")
    analyzer = ChatVisionAnalyzer(_Boom(), None)
    with pytest.raises(RuntimeError, match="primary vision provider down"):
        analyzer.analyze(prompt="describe", image_path=img)

from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from cognitive_os.api.app import app
from cognitive_os.core.config import Settings
from cognitive_os.voice.service import (
    ElevenLabsSTTProvider,
    ElevenLabsTTSProvider,
    FakeSTTProvider,
    FakeTTSProvider,
    VoiceError,
    VoiceService,
    _redact,
)


def _settings(
    *, enabled: bool = True, key: str = "sk_realkey123", max_bytes: int = 1000
) -> Settings:
    return Settings.model_construct(
        voice_enabled=enabled,
        elevenlabs_api_key=SecretStr(key),
        elevenlabs_base_url="https://api.elevenlabs.io",
        voice_stt_model="scribe_v1",
        voice_tts_model="eleven_multilingual_v2",
        voice_tts_voice_id="voice-123",
        voice_max_audio_bytes=max_bytes,
        voice_default_language="es",
        http_timeout_seconds=5.0,
    )


def test_status_disabled_blocked_ready() -> None:
    assert VoiceService(app_settings=_settings(enabled=False)).status().status == "disabled"
    assert VoiceService(app_settings=_settings(key="CHANGEME")).status().status == "blocked"
    ready = VoiceService(app_settings=_settings()).status()
    assert ready.status == "ready"
    assert ready.tts_voice_id == "configured"


def test_transcribe_and_synthesize_blocked_when_not_ready() -> None:
    service = VoiceService(
        stt_provider=FakeSTTProvider(),
        tts_provider=FakeTTSProvider(),
        app_settings=_settings(enabled=False),
    )
    with pytest.raises(VoiceError, match="VOICE_ENABLED"):
        service.transcribe(b"audio")
    with pytest.raises(VoiceError, match="VOICE_ENABLED"):
        service.synthesize("hola")


def test_transcribe_enforces_size_cap_and_empty_payload() -> None:
    service = VoiceService(
        stt_provider=FakeSTTProvider(),
        app_settings=_settings(max_bytes=10),
    )
    with pytest.raises(VoiceError, match="empty"):
        service.transcribe(b"")
    with pytest.raises(VoiceError, match="cap"):
        service.transcribe(b"x" * 11)


def test_transcribe_uses_provider_and_default_language() -> None:
    stt = FakeSTTProvider(text="hola mundo")
    service = VoiceService(stt_provider=stt, app_settings=_settings())
    result = service.transcribe(b"audio-bytes", content_type="audio/ogg")
    assert result.text == "hola mundo"
    assert stt.calls[0]["language"] == "es"
    assert stt.calls[0]["content_type"] == "audio/ogg"


def test_synthesize_uses_provider_defaults_and_rejects_empty_text() -> None:
    tts = FakeTTSProvider(audio=b"mp3")
    service = VoiceService(tts_provider=tts, app_settings=_settings())
    with pytest.raises(VoiceError, match="must not be empty"):
        service.synthesize("   ")
    result = service.synthesize("hola")
    assert result.audio == b"mp3"
    assert result.voice_id == "voice-123"
    assert result.model == "eleven_multilingual_v2"


def test_provider_failure_surfaces_voice_error() -> None:
    service = VoiceService(
        stt_provider=FakeSTTProvider(raises=True),
        app_settings=_settings(),
    )
    with pytest.raises(VoiceError, match="fake stt failure"):
        service.transcribe(b"audio")


def test_redact_strips_api_keys() -> None:
    assert "[REDACTED]" in _redact("boom xi-api-key: sk_secret_value")
    assert "sk_secret_value" not in _redact("boom xi-api-key=sk_secret_value")


def test_elevenlabs_stt_provider_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json={"text": "transcripción real", "language_code": "es"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = ElevenLabsSTTProvider(_settings()).transcribe(
        b"audio",
        content_type="audio/mpeg",
        language="es",
    )
    assert result.text == "transcripción real"
    assert result.language_code == "es"
    assert result.model == "scribe_v1"


def test_elevenlabs_stt_provider_rejects_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, json={"text": "  "}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(VoiceError, match="empty transcription"):
        ElevenLabsSTTProvider(_settings()).transcribe(
            b"audio",
            content_type="audio/mpeg",
            language=None,
        )


def test_elevenlabs_tts_provider_returns_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"\xff\xf3mp3-bytes",
            headers={"content-type": "audio/mpeg"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = ElevenLabsTTSProvider(_settings()).synthesize(
        "hola",
        voice_id="voice-123",
        model="eleven_multilingual_v2",
    )
    assert result.audio == b"\xff\xf3mp3-bytes"
    assert result.media_type == "audio/mpeg"


def test_elevenlabs_tts_provider_rejects_empty_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, content=b"", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(VoiceError, match="empty audio"):
        ElevenLabsTTSProvider(_settings()).synthesize(
            "hola",
            voice_id="voice-123",
            model="eleven_multilingual_v2",
        )


@pytest.mark.asyncio
async def test_voice_endpoints_require_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        status_resp = await client.get("/voice/status")
        speak_resp = await client.post("/voice/speak", json={"text": "hola"})
        transcribe_resp = await client.post(
            "/voice/transcribe",
            files={"file": ("a.ogg", b"audio", "audio/ogg")},
        )
    assert status_resp.status_code == 401
    assert speak_resp.status_code == 401
    assert transcribe_resp.status_code == 401

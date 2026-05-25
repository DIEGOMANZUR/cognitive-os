"""Voice I/O service: ElevenLabs STT/TTS behind injectable providers.

`VoiceService` gates on `VOICE_ENABLED` + a real `ELEVENLABS_API_KEY`, enforces
the `VOICE_MAX_AUDIO_BYTES` cap on uploads, and delegates to provider Protocols.
The real providers call the ElevenLabs REST API; tests inject `FakeSTTProvider`
/ `FakeTTSProvider` so the suite never touches the network or spends credits.
"""

from __future__ import annotations

import re
from typing import Literal, Protocol

import httpx

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.resilience import retry_transient_http
from cognitive_os.voice.schemas import SpeechResult, TranscriptionResult, VoiceStatus

_SECRET_RE = re.compile(r"(?i)(xi-api-key|api[_-]?key|bearer)\s*[:=]?\s*[A-Za-z0-9._-]+")


class VoiceError(RuntimeError):
    """Raised when a voice operation cannot be completed."""


def _redact(value: str) -> str:
    return _SECRET_RE.sub(r"\1 [REDACTED]", value)


class SpeechToTextProvider(Protocol):
    def transcribe(
        self,
        audio: bytes,
        *,
        content_type: str,
        language: str | None,
    ) -> TranscriptionResult: ...


class TextToSpeechProvider(Protocol):
    def synthesize(self, text: str, *, voice_id: str, model: str) -> SpeechResult: ...


class FakeSTTProvider:
    def __init__(self, *, text: str = "transcripción simulada", raises: bool = False) -> None:
        self._text = text
        self._raises = raises
        self.calls: list[dict[str, object]] = []

    def transcribe(
        self,
        audio: bytes,
        *,
        content_type: str,
        language: str | None,
    ) -> TranscriptionResult:
        self.calls.append({"size": len(audio), "content_type": content_type, "language": language})
        if self._raises:
            raise VoiceError("fake stt failure")
        return TranscriptionResult(text=self._text, language_code=language, model="fake-stt")


class FakeTTSProvider:
    def __init__(self, *, audio: bytes = b"fake-audio", raises: bool = False) -> None:
        self._audio = audio
        self._raises = raises
        self.calls: list[dict[str, object]] = []

    def synthesize(self, text: str, *, voice_id: str, model: str) -> SpeechResult:
        self.calls.append({"text": text, "voice_id": voice_id, "model": model})
        if self._raises:
            raise VoiceError("fake tts failure")
        return SpeechResult(
            audio=self._audio,
            media_type="audio/mpeg",
            voice_id=voice_id,
            model=model,
        )


class ElevenLabsSTTProvider:
    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    def transcribe(
        self,
        audio: bytes,
        *,
        content_type: str,
        language: str | None,
    ) -> TranscriptionResult:
        url = f"{self._settings.elevenlabs_base_url.rstrip('/')}/v1/speech-to-text"
        model = self._settings.voice_stt_model
        data: dict[str, str] = {"model_id": model}
        if language:
            data["language_code"] = language
        try:
            response = retry_transient_http(
                lambda: httpx.post(
                    url,
                    headers={"xi-api-key": self._settings.elevenlabs_api_key.get_secret_value()},
                    data=data,
                    files={"file": ("audio", audio, content_type)},
                    timeout=self._settings.http_timeout_seconds,
                )
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise VoiceError(f"ElevenLabs STT failed: {_redact(str(exc))}") from exc
        except ValueError as exc:
            raise VoiceError("ElevenLabs STT returned invalid JSON.") from exc
        text = str(payload.get("text") or "").strip()
        if not text:
            raise VoiceError("ElevenLabs STT returned an empty transcription.")
        language_code = payload.get("language_code")
        return TranscriptionResult(
            text=text,
            language_code=str(language_code) if language_code else language,
            model=model,
        )


class ElevenLabsTTSProvider:
    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    def synthesize(self, text: str, *, voice_id: str, model: str) -> SpeechResult:
        base = self._settings.elevenlabs_base_url.rstrip("/")
        url = f"{base}/v1/text-to-speech/{voice_id}"
        try:
            response = retry_transient_http(
                lambda: httpx.post(
                    url,
                    headers={
                        "xi-api-key": self._settings.elevenlabs_api_key.get_secret_value(),
                        "accept": "audio/mpeg",
                    },
                    json={"text": text, "model_id": model},
                    timeout=self._settings.http_timeout_seconds,
                )
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VoiceError(f"ElevenLabs TTS failed: {_redact(str(exc))}") from exc
        audio = response.content
        if not audio:
            raise VoiceError("ElevenLabs TTS returned empty audio.")
        media_type = response.headers.get("content-type", "audio/mpeg").split(";")[0]
        return SpeechResult(audio=audio, media_type=media_type, voice_id=voice_id, model=model)


class VoiceService:
    """Capability-gated facade over the STT/TTS providers."""

    def __init__(
        self,
        *,
        stt_provider: SpeechToTextProvider | None = None,
        tts_provider: TextToSpeechProvider | None = None,
        app_settings: Settings = settings,
    ) -> None:
        self._settings = app_settings
        self._stt = stt_provider
        self._tts = tts_provider

    def _status(
        self,
        state: Literal["disabled", "blocked", "ready"],
        reason: str | None,
    ) -> VoiceStatus:
        return VoiceStatus(
            status=state,
            reason=reason,
            stt_model=self._settings.voice_stt_model,
            tts_model=self._settings.voice_tts_model,
            tts_voice_id="configured" if self._settings.voice_tts_voice_id else "missing",
            max_audio_bytes=self._settings.voice_max_audio_bytes,
        )

    def status(self) -> VoiceStatus:
        if not self._settings.voice_enabled:
            return self._status("disabled", "VOICE_ENABLED is false.")
        key = self._settings.elevenlabs_api_key.get_secret_value()
        if not key or "CHANGEME" in key:
            return self._status("blocked", "ELEVENLABS_API_KEY is not configured.")
        return self._status("ready", None)

    def _require_ready(self) -> None:
        current = self.status()
        if current.status != "ready":
            raise VoiceError(current.reason or "Voice I/O is not available.")

    def _resolve_stt(self) -> SpeechToTextProvider:
        if self._stt is None:
            self._stt = ElevenLabsSTTProvider(self._settings)
        return self._stt

    def _resolve_tts(self) -> TextToSpeechProvider:
        if self._tts is None:
            self._tts = ElevenLabsTTSProvider(self._settings)
        return self._tts

    def transcribe(
        self,
        audio: bytes,
        *,
        content_type: str = "application/octet-stream",
        language: str | None = None,
    ) -> TranscriptionResult:
        if not audio:
            raise VoiceError("Audio payload is empty.")
        if len(audio) > self._settings.voice_max_audio_bytes:
            raise VoiceError(f"Audio exceeds the {self._settings.voice_max_audio_bytes}-byte cap.")
        self._require_ready()
        return self._resolve_stt().transcribe(
            audio,
            content_type=content_type or "application/octet-stream",
            language=language or self._settings.voice_default_language,
        )

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        model: str | None = None,
    ) -> SpeechResult:
        cleaned = text.strip()
        if not cleaned:
            raise VoiceError("Text to synthesize must not be empty.")
        self._require_ready()
        return self._resolve_tts().synthesize(
            cleaned,
            voice_id=voice_id or self._settings.voice_tts_voice_id,
            model=model or self._settings.voice_tts_model,
        )

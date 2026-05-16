from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


class VoiceStatus(BaseModel):
    status: Literal["disabled", "blocked", "ready"]
    reason: str | None = None
    stt_model: str
    tts_model: str
    tts_voice_id: str
    max_audio_bytes: int


class TranscriptionResult(BaseModel):
    text: str
    language_code: str | None = None
    model: str


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice_id: str | None = Field(default=None, max_length=128)
    model: str | None = Field(default=None, max_length=128)


@dataclass(frozen=True)
class SpeechResult:
    """Synthesized audio. Not a pydantic model — the endpoint streams raw bytes."""

    audio: bytes
    media_type: str
    voice_id: str
    model: str

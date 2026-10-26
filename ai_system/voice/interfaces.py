from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

MAX_TRANSIENT_AUDIO_BYTES = 10 * 1024 * 1024


class AdapterStatus(StrEnum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AudioFrame:
    pcm_s16le: bytes
    sample_rate_hz: int = 16000
    channels: int = 1

    def __post_init__(self):
        if (
            not isinstance(self.pcm_s16le, bytes)
            or not self.pcm_s16le
            or len(self.pcm_s16le) > MAX_TRANSIENT_AUDIO_BYTES
            or len(self.pcm_s16le) % 2
            or self.sample_rate_hz not in {8000, 16000, 22050, 24000, 44100, 48000}
            or self.channels != 1
        ):
            raise ValueError("A valid mono PCM16 audio frame is required.")


@dataclass(frozen=True, slots=True)
class VoiceSegment:
    start_sample: int
    end_sample: int


@dataclass(frozen=True, slots=True)
class VoiceActivityResult:
    status: AdapterStatus
    segments: tuple[VoiceSegment, ...] = ()
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    status: AdapterStatus
    text: str = ""
    language_code: str = "en"
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class SpeechSynthesisResult:
    status: AdapterStatus
    audio_bytes: bytes = b""
    media_type: str = "audio/wav"
    error_code: str | None = None


class AudioInputAdapter(Protocol):
    def read(self) -> AudioFrame | None: ...


class AudioOutputAdapter(Protocol):
    def play(self, result: SpeechSynthesisResult) -> bool: ...


class VoiceActivityAdapter(Protocol):
    def detect(self, audio: AudioFrame) -> VoiceActivityResult: ...


class SpeechToTextAdapter(Protocol):
    def transcribe(self, audio: AudioFrame) -> TranscriptionResult: ...


class TextToSpeechAdapter(Protocol):
    def synthesize(self, text: str) -> SpeechSynthesisResult: ...

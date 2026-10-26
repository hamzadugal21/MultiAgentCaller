import io
import wave
from pathlib import Path

from ai_system.voice.interfaces import (
    AdapterStatus,
    SpeechSynthesisResult,
    TranscriptionResult,
    VoiceActivityResult,
    VoiceSegment,
)

MAX_TRANSCRIPT_CHARACTERS = 8000
MAX_SYNTHESIS_CHARACTERS = 2000


class UnavailableAudioInput:
    """Represent a missing or unsupported microphone without raising."""

    def read(self):
        return None


class SileroVadAdapter:
    def __init__(self, *, model_loader=None, detector=None):
        self._model_loader = model_loader
        self._detector = detector
        self._model = None

    def _components(self):
        if self._model_loader is None or self._detector is None:
            from silero_vad import get_speech_timestamps, load_silero_vad

            self._model_loader = load_silero_vad
            self._detector = get_speech_timestamps
        if self._model is None:
            self._model = self._model_loader()
        return self._model, self._detector

    def detect(self, audio):
        try:
            import numpy
            import torch

            model, detector = self._components()
            samples = numpy.frombuffer(audio.pcm_s16le, dtype=numpy.int16).astype(
                numpy.float32
            )
            tensor = torch.from_numpy(samples / 32768.0)
            raw_segments = detector(
                tensor,
                model,
                sampling_rate=audio.sample_rate_hz,
            )
            segments = tuple(
                VoiceSegment(
                    start_sample=int(segment["start"]),
                    end_sample=int(segment["end"]),
                )
                for segment in raw_segments
            )
            return VoiceActivityResult(
                status=AdapterStatus.SUCCESS,
                segments=segments,
            )
        except (ImportError, ModuleNotFoundError):
            return VoiceActivityResult(
                status=AdapterStatus.UNAVAILABLE,
                error_code="vad_dependency_unavailable",
            )
        except Exception:
            return VoiceActivityResult(
                status=AdapterStatus.FAILED,
                error_code="vad_processing_failed",
            )


class FasterWhisperAdapter:
    def __init__(self, *, model_identifier="small.en", model_loader=None):
        self._model_identifier = model_identifier
        self._model_loader = model_loader
        self._model = None

    def _load_model(self):
        if self._model is None:
            if self._model_loader is None:
                from faster_whisper import WhisperModel

                self._model_loader = WhisperModel
            self._model = self._model_loader(
                self._model_identifier,
                device="auto",
                local_files_only=True,
            )
        return self._model

    def transcribe(self, audio):
        try:
            import numpy

            samples = numpy.frombuffer(audio.pcm_s16le, dtype=numpy.int16).astype(
                numpy.float32
            )
            model = self._load_model()
            segments, info = model.transcribe(
                samples / 32768.0,
                language="en",
                beam_size=1,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            return TranscriptionResult(
                status=AdapterStatus.SUCCESS,
                text=text[:MAX_TRANSCRIPT_CHARACTERS],
                language_code=(getattr(info, "language", None) or "en")[:10],
            )
        except (ImportError, ModuleNotFoundError):
            return TranscriptionResult(
                status=AdapterStatus.UNAVAILABLE,
                error_code="stt_dependency_unavailable",
            )
        except Exception:
            return TranscriptionResult(
                status=AdapterStatus.FAILED,
                error_code="stt_processing_failed",
            )


class PiperTtsAdapter:
    def __init__(self, *, model_path, voice_loader=None):
        self._model_path = Path(model_path)
        self._voice_loader = voice_loader
        self._voice = None

    def _load_voice(self):
        if not self._model_path.is_file() or self._model_path.suffix != ".onnx":
            return None
        if self._voice is None:
            if self._voice_loader is None:
                from piper_plus.voice import PiperVoice

                self._voice_loader = PiperVoice.load
            self._voice = self._voice_loader(self._model_path)
        return self._voice

    def synthesize(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_SYNTHESIS_CHARACTERS:
            return SpeechSynthesisResult(
                status=AdapterStatus.FAILED,
                error_code="tts_text_invalid",
            )
        try:
            voice = self._load_voice()
            if voice is None:
                return SpeechSynthesisResult(
                    status=AdapterStatus.UNAVAILABLE,
                    error_code="tts_model_unavailable",
                )
            output = io.BytesIO()
            with wave.open(output, "wb") as wav_file:
                voice.synthesize(text.strip(), wav_file)
            return SpeechSynthesisResult(
                status=AdapterStatus.SUCCESS,
                audio_bytes=output.getvalue(),
            )
        except (ImportError, ModuleNotFoundError):
            return SpeechSynthesisResult(
                status=AdapterStatus.UNAVAILABLE,
                error_code="tts_dependency_unavailable",
            )
        except Exception:
            return SpeechSynthesisResult(
                status=AdapterStatus.FAILED,
                error_code="tts_processing_failed",
            )


class DiscardingAudioOutput:
    """Accept synthesized audio without storing or playing it."""

    def play(self, result):
        return result.status == AdapterStatus.SUCCESS and bool(result.audio_bytes)

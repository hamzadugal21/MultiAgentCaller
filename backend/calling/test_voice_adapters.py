from types import SimpleNamespace

import pytest
from ai_system.voice.interfaces import AdapterStatus, AudioFrame, SpeechSynthesisResult
from ml.voice.local_adapters import (
    DiscardingAudioOutput,
    FasterWhisperAdapter,
    PiperTtsAdapter,
    SileroVadAdapter,
    UnavailableAudioInput,
)


def _audio():
    return AudioFrame(pcm_s16le=(b"\x00\x00" * 320), sample_rate_hz=16000)


@pytest.mark.parametrize(
    "values",
    [
        {"pcm_s16le": b""},
        {"pcm_s16le": b"\x00"},
        {"pcm_s16le": b"\x00\x00", "channels": 2},
        {"pcm_s16le": b"\x00\x00", "sample_rate_hz": 12345},
    ],
)
def test_transient_audio_frame_rejects_invalid_input(values):
    with pytest.raises(ValueError, match="PCM16"):
        AudioFrame(**values)


def test_silero_adapter_returns_structured_success_and_safe_failure():
    def detector(tensor, model, sampling_rate):
        return [{"start": 10, "end": 40}]

    adapter = SileroVadAdapter(model_loader=lambda: object(), detector=detector)
    result = adapter.detect(_audio())
    assert result.status == AdapterStatus.SUCCESS
    assert result.segments[0].start_sample == 10
    assert result.segments[0].end_sample == 40

    failed = SileroVadAdapter(
        model_loader=lambda: (_ for _ in ()).throw(RuntimeError("private path")),
        detector=detector,
    ).detect(_audio())
    assert failed.status == AdapterStatus.FAILED
    assert failed.error_code == "vad_processing_failed"
    assert "private" not in str(failed)


def test_whisper_adapter_is_lazy_bounded_and_fails_safely():
    class Model:
        def transcribe(self, samples, **kwargs):
            segment = SimpleNamespace(text=" synthetic answer text ")
            return iter([segment]), SimpleNamespace(language="en")

    calls = []

    def loader(*args, **kwargs):
        calls.append((args, kwargs))
        return Model()

    adapter = FasterWhisperAdapter(model_identifier="local-test", model_loader=loader)
    assert calls == []
    result = adapter.transcribe(_audio())
    assert result.status == AdapterStatus.SUCCESS
    assert result.text == "synthetic answer text"
    assert calls[0][1]["local_files_only"] is True

    failed = FasterWhisperAdapter(
        model_loader=lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("private model location")
        )
    ).transcribe(_audio())
    assert failed.status == AdapterStatus.FAILED
    assert failed.error_code == "stt_processing_failed"
    assert "private" not in str(failed)


def test_piper_adapter_requires_local_model_and_returns_safe_results(tmp_path):
    missing = PiperTtsAdapter(model_path=tmp_path / "missing.onnx")
    assert missing.synthesize("Synthetic question").status == AdapterStatus.UNAVAILABLE

    model_path = tmp_path / "voice.onnx"
    model_path.write_bytes(b"synthetic-model-placeholder")

    class Voice:
        def synthesize(self, text, wav_file):
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\x00\x00" * 20)

    adapter = PiperTtsAdapter(model_path=model_path, voice_loader=lambda path: Voice())
    result = adapter.synthesize("Synthetic question")
    assert result.status == AdapterStatus.SUCCESS
    assert result.media_type == "audio/wav"
    assert result.audio_bytes.startswith(b"RIFF")

    invalid = adapter.synthesize("x" * 2001)
    assert invalid.status == AdapterStatus.FAILED
    assert invalid.error_code == "tts_text_invalid"


def test_discarding_audio_output_does_not_retain_audio():
    output = DiscardingAudioOutput()
    result = SpeechSynthesisResult(
        status=AdapterStatus.SUCCESS,
        audio_bytes=b"transient-audio",
    )
    assert output.play(result) is True
    assert vars(output) == {}
    assert UnavailableAudioInput().read() is None

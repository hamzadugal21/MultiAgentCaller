"""Short-lived synthetic speech worker for the isolated QA release command.

The worker deliberately owns all native speech runtimes in a separate process.
When it exits, Windows releases their native allocations before llama.cpp starts.
It has no Django, database, network, shell, or model-action capability.
"""

from __future__ import annotations

import argparse
import json
import wave
from io import BytesIO
from pathlib import Path

from ml.voice.local_adapters import (
    FasterWhisperAdapter,
    PiperTtsAdapter,
    SileroVadAdapter,
)

from ai_system.voice.interfaces import AdapterStatus, AudioFrame

QA_SYNTHETIC_ANSWERS = (
    "I wrote unit tests and integration tests then I reviewed failures and fixed database transactions",
    "I used transactions row locks constraints idempotency and audit rollback so partial changes and duplicate work were prevented",
    "I documented the critical issue shared the evidence with the reviewer and paused the release until the fix was verified",
)


class QaSpeechWorkerError(RuntimeError):
    """Privacy-safe worker failure."""


def _wav_to_audio_frame(audio_wav: bytes) -> AudioFrame:
    import numpy

    try:
        with wave.open(BytesIO(audio_wav), "rb") as source:
            if source.getnchannels() != 1 or source.getsampwidth() != 2:
                raise QaSpeechWorkerError("qa_tts_audio_invalid")
            source_rate = source.getframerate()
            samples = numpy.frombuffer(
                source.readframes(source.getnframes()), dtype=numpy.int16
            ).astype(numpy.float32)
    except (EOFError, ValueError, wave.Error) as error:
        raise QaSpeechWorkerError("qa_tts_audio_invalid") from error
    if not len(samples):
        raise QaSpeechWorkerError("qa_tts_audio_empty")
    target_count = round(len(samples) * 16000 / source_rate)
    positions = numpy.linspace(
        0,
        len(samples) - 1,
        num=max(target_count, 1),
        dtype=numpy.float32,
    )
    pcm = numpy.interp(
        positions,
        numpy.arange(len(samples), dtype=numpy.float32),
        samples,
    ).astype(numpy.int16)
    return AudioFrame(pcm_s16le=pcm.tobytes(), sample_rate_hz=16000)


def run_synthetic_speech(
    *,
    piper_model: Path,
    whisper_model: Path,
    whisper_device: str,
    whisper_compute_type: str,
    whisper_language: str,
) -> dict[str, object]:
    tts = PiperTtsAdapter(model_path=piper_model)
    vad = SileroVadAdapter()
    stt = FasterWhisperAdapter(
        model_identifier=str(whisper_model),
        device=whisper_device,
        compute_type=whisper_compute_type,
        language=whisper_language,
    )
    turns: list[dict[str, object]] = []
    for spoken_answer in QA_SYNTHETIC_ANSWERS:
        synthesized = tts.synthesize(spoken_answer)
        if synthesized.status is not AdapterStatus.SUCCESS or not synthesized.audio_bytes:
            raise QaSpeechWorkerError(synthesized.error_code or "qa_tts_failed")
        frame = _wav_to_audio_frame(synthesized.audio_bytes)
        voice = vad.detect(frame)
        if voice.status is not AdapterStatus.SUCCESS or not voice.segments:
            raise QaSpeechWorkerError(voice.error_code or "qa_vad_failed")
        transcript = stt.transcribe(frame)
        if transcript.status is not AdapterStatus.SUCCESS or not transcript.text.strip():
            raise QaSpeechWorkerError(transcript.error_code or "qa_stt_failed")
        turns.append(
            {
                "transcript": transcript.text.strip(),
                "vad_segments": len(voice.segments),
            }
        )
    return {"turns": turns}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--piper-model", type=Path, required=True)
    parser.add_argument("--whisper-model", type=Path, required=True)
    parser.add_argument("--whisper-device", required=True)
    parser.add_argument("--whisper-compute-type", required=True)
    parser.add_argument("--whisper-language", required=True)
    args = parser.parse_args()
    try:
        report = run_synthetic_speech(
            piper_model=args.piper_model,
            whisper_model=args.whisper_model,
            whisper_device=args.whisper_device,
            whisper_compute_type=args.whisper_compute_type,
            whisper_language=args.whisper_language,
        )
    except QaSpeechWorkerError as error:
        print(str(error), file=__import__("sys").stderr)
        return 2
    print(json.dumps(report, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

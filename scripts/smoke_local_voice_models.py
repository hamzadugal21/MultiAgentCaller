"""Run local-only inference smoke checks for the optional voice models.

This script uses a fixed synthetic sentence, retains no audio, and never
downloads model weights. Run the explicit download scripts first.
"""

import argparse
import sys
import wave
from io import BytesIO
from pathlib import Path

import numpy

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def main() -> None:
    from ai_system.voice.interfaces import AdapterStatus, AudioFrame
    from ml.voice.local_adapters import (
        FasterWhisperAdapter,
        PiperTtsAdapter,
        SileroVadAdapter,
    )

    def as_16khz_frame(audio_wav: bytes) -> AudioFrame:
        with wave.open(BytesIO(audio_wav), "rb") as source:
            if source.getnchannels() != 1 or source.getsampwidth() != 2:
                raise ValueError(
                    "The local Piper model did not produce mono PCM16 WAV audio."
                )
            source_rate = source.getframerate()
            samples = numpy.frombuffer(
                source.readframes(source.getnframes()), dtype=numpy.int16
            ).astype(numpy.float32)
        if not len(samples):
            raise ValueError("The local Piper model produced empty WAV audio.")
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

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--whisper-model",
        type=Path,
        default=Path("var/models/whisper/base"),
    )
    parser.add_argument(
        "--piper-model",
        type=Path,
        default=Path("var/models/piper/tsukuyomi-zs-v1/releases/zs-v1/tsukuyomi.onnx"),
    )
    args = parser.parse_args()

    tts = PiperTtsAdapter(model_path=args.piper_model).synthesize(
        "Hello this is a local interview answer test"
    )
    if tts.status is not AdapterStatus.SUCCESS or not tts.audio_bytes:
        raise SystemExit(f"Piper Plus smoke check failed: {tts.error_code or tts.status.value}")
    frame = as_16khz_frame(tts.audio_bytes)

    vad = SileroVadAdapter().detect(frame)
    if vad.status is not AdapterStatus.SUCCESS:
        raise SystemExit(f"Silero VAD smoke check failed: {vad.error_code or vad.status.value}")

    stt = FasterWhisperAdapter(
        model_identifier=str(args.whisper_model),
        device="cpu",
        compute_type="int8",
        language="en",
    ).transcribe(frame)
    if stt.status is not AdapterStatus.SUCCESS:
        raise SystemExit(
            f"Faster-Whisper smoke check failed: {stt.error_code or stt.status.value}"
        )

    print(
        "LOCAL_VOICE_SMOKE_OK "
        f"vad_segments={len(vad.segments)} transcript_characters={len(stt.text)}"
    )


if __name__ == "__main__":
    main()

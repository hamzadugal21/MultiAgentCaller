import io
from dataclasses import dataclass

from ai_system.voice.interfaces import AdapterStatus, AudioFrame
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from ml.voice.local_adapters import (
    MAX_TRANSCRIPT_CHARACTERS,
    FasterWhisperAdapter,
    SileroVadAdapter,
)

from auditlog.models import AuditEvent
from auditlog.services import AuditCommand, record_domain_event
from calling.models import CallSession
from calling.services import (
    CallSessionServiceError,
    _eligible_schedule,
    get_candidate_simulated_interview_state,
)

ALLOWED_AUDIO_TYPES = frozenset({"audio/webm", "audio/ogg", "audio/wav"})


class TranscriptionError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    duration_seconds: int
    vad_segments: int


def _duration_bucket(seconds):
    if seconds <= 10:
        return "up_to_10s"
    if seconds <= 30:
        return "up_to_30s"
    return "up_to_max"


def _rate_limit(*, actor, session):
    key = f"calling:stt:{actor.pk}:{session.pk}"
    limit = settings.WHISPER_TRANSCRIPTION_RATE_LIMIT
    window = settings.WHISPER_TRANSCRIPTION_RATE_WINDOW_SECONDS
    if cache.add(key, 1, timeout=window):
        return
    try:
        attempts = cache.incr(key)
    except ValueError:
        attempts = limit + 1
    if attempts > limit:
        raise TranscriptionError("transcription_rate_limited")


def decode_browser_audio(audio_bytes):
    try:
        import av
    except (ImportError, ModuleNotFoundError) as error:
        raise TranscriptionError("audio_decoder_unavailable") from error
    try:
        container = av.open(io.BytesIO(audio_bytes), mode="r")
        stream = next(item for item in container.streams if item.type == "audio")
        resampler = av.audio.resampler.AudioResampler(
            format="s16", layout="mono", rate=16000
        )
        pcm = bytearray()
        max_samples = settings.WHISPER_MAX_AUDIO_SECONDS * 16000
        for frame in container.decode(stream):
            for output in resampler.resample(frame):
                chunk = bytes(output.planes[0])
                pcm.extend(chunk)
                if len(pcm) // 2 > max_samples:
                    raise TranscriptionError("audio_too_long")
        container.close()
        if not pcm:
            raise TranscriptionError("audio_empty")
        return AudioFrame(pcm_s16le=bytes(pcm), sample_rate_hz=16000)
    except TranscriptionError:
        raise
    except Exception as error:
        raise TranscriptionError("audio_invalid") from error


def _adapter():
    return FasterWhisperAdapter(
        model_identifier=str(settings.WHISPER_MODEL_PATH),
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
        language=settings.WHISPER_LANGUAGE,
    )


def _vad_adapter():
    return SileroVadAdapter()


def transcribe_candidate_audio(
    *,
    session,
    actor,
    uploaded_audio,
    decoder=decode_browser_audio,
    stt=None,
    vad=None,
):
    content_type = (getattr(uploaded_audio, "content_type", "") or "").split(";", 1)[0]
    if uploaded_audio is None or content_type not in ALLOWED_AUDIO_TYPES:
        raise TranscriptionError("audio_type_invalid")
    if uploaded_audio.size <= 0:
        raise TranscriptionError("audio_empty")
    if uploaded_audio.size > settings.WHISPER_MAX_UPLOAD_BYTES:
        raise TranscriptionError("audio_too_large")
    raw_audio = uploaded_audio.read(settings.WHISPER_MAX_UPLOAD_BYTES + 1)
    if not raw_audio or len(raw_audio) > settings.WHISPER_MAX_UPLOAD_BYTES:
        raise TranscriptionError("audio_too_large")
    try:
        state = get_candidate_simulated_interview_state(session=session, actor=actor)
        if state.session.status != CallSession.Status.ACTIVE or not state.current_question:
            raise TranscriptionError("transcription_not_available")
        _eligible_schedule(
            state.session.schedule,
            policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
            now=timezone.now(),
        )
        _rate_limit(actor=actor, session=state.session)
        frame = decoder(raw_audio)
        seconds = max(1, len(frame.pcm_s16le) // 2 // frame.sample_rate_hz)
        if seconds > settings.WHISPER_MAX_AUDIO_SECONDS:
            raise TranscriptionError("audio_too_long")
        voice = (vad or _vad_adapter()).detect(frame)
        if voice.status != AdapterStatus.SUCCESS:
            raise TranscriptionError(voice.error_code or "vad_unavailable")
        if not voice.segments:
            raise TranscriptionError("no_speech_detected")
        result = (stt or _adapter()).transcribe(frame)
        if result.status != AdapterStatus.SUCCESS or not result.text.strip():
            raise TranscriptionError(result.error_code or "transcription_unavailable")
        text = result.text.strip()[: min(MAX_TRANSCRIPT_CHARACTERS, 4000)]
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.INTERVIEW,
                event_type="call_session.transcription_succeeded",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="calling.CallSession",
                resource_id=state.session.pk,
                actor=actor,
                metadata={
                    "application_id": state.session.schedule.application_id,
                    "interview_schedule_id": state.session.schedule_id,
                    "question_id": state.current_question.pk,
                    "question_index": state.session.current_question_index,
                    "duration_bucket": _duration_bucket(seconds),
                },
            )
        )
        return TranscriptionResult(
            text=text,
            duration_seconds=seconds,
            vad_segments=len(voice.segments),
        )
    except CallSessionServiceError as error:
        raise TranscriptionError("transcription_not_available") from error
    finally:
        raw_audio = b""

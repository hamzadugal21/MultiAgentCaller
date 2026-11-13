"""QA-only transient Piper playback for the current approved question."""

from __future__ import annotations

from ai_system.voice.interfaces import AdapterStatus
from django.conf import settings
from ml.voice.local_adapters import PiperTtsAdapter

from calling.models import CallSession
from calling.services import (
    CallSessionServiceError,
    get_candidate_simulated_interview_state,
)


class QaVoiceError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def synthesize_qa_question(*, session, actor, tts=None) -> bytes:
    """Return transient WAV bytes without persisting audio or question text."""
    if (
        settings.SETTINGS_MODULE != "config.settings_qa"
        or not getattr(settings, "QA_BROWSER_VOICE_ENABLED", False)
    ):
        raise QaVoiceError("qa_voice_disabled")
    try:
        state = get_candidate_simulated_interview_state(session=session, actor=actor)
    except CallSessionServiceError as error:
        raise QaVoiceError("qa_voice_not_available") from error
    if state.session.status != CallSession.Status.ACTIVE or state.current_question is None:
        raise QaVoiceError("qa_voice_not_available")
    adapter = tts or PiperTtsAdapter(model_path=settings.PIPER_MODEL_PATH)
    result = adapter.synthesize(state.current_question.question_text)
    if result.status is not AdapterStatus.SUCCESS or not result.audio_bytes:
        raise QaVoiceError(result.error_code or "qa_voice_unavailable")
    return result.audio_bytes

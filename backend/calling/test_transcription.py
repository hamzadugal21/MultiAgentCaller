import uuid
from types import SimpleNamespace

import pytest
from ai_system.voice.interfaces import (
    AdapterStatus,
    AudioFrame,
    TranscriptionResult,
    VoiceActivityResult,
    VoiceSegment,
)
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from auditlog.models import AuditEvent
from calling.models import CallSession, SimulatedInterviewResponse
from calling.services import prepare_simulated_call_session, transition_call_session
from calling.transcription_services import (
    TranscriptionError,
    transcribe_candidate_audio,
)
from recruitment.models import InterviewQuestion

pytest_plugins = ("calling.test_call_session_services",)
pytestmark = pytest.mark.django_db


def _active_session(call_data):
    InterviewQuestion.objects.create(
        job=call_data["application"].job,
        question_text="Synthetic approved question",
        order=1,
    )
    session = prepare_simulated_call_session(
        schedule=call_data["schedule"],
        actor=call_data["candidate_user"],
        idempotency_key=uuid.uuid4(),
        policy_version="ai-processing-v1",
    )
    return transition_call_session(
        session=session,
        target_status=CallSession.Status.ACTIVE,
        actor=call_data["candidate_user"],
        policy_version="ai-processing-v1",
    )


class _SuccessStt:
    def transcribe(self, audio):
        return TranscriptionResult(status=AdapterStatus.SUCCESS, text="reviewable text")


class _SuccessVad:
    def detect(self, audio):
        return VoiceActivityResult(
            status=AdapterStatus.SUCCESS,
            segments=(VoiceSegment(start_sample=0, end_sample=16000),),
        )


class _SilentVad:
    def detect(self, audio):
        return VoiceActivityResult(status=AdapterStatus.SUCCESS)


def _upload(content=b"synthetic-audio", content_type="audio/wav"):
    return SimpleUploadedFile("ignored.wav", content, content_type=content_type)


def test_transcription_is_transient_audited_and_not_an_answer(call_data):
    session = _active_session(call_data)
    result = transcribe_candidate_audio(
        session=session,
        actor=call_data["candidate_user"],
        uploaded_audio=_upload(),
        decoder=lambda _raw: AudioFrame(pcm_s16le=b"\x00\x00" * 16000),
        stt=_SuccessStt(),
        vad=_SuccessVad(),
    )

    assert result.text == "reviewable text"
    assert not SimulatedInterviewResponse.objects.filter(call_session=session).exists()
    event = AuditEvent.objects.get(event_type="call_session.transcription_succeeded")
    assert "reviewable" not in str(event.metadata)
    assert "audio" not in str(event.metadata)


def test_transcription_rejects_silence_before_whisper(call_data):
    session = _active_session(call_data)
    with pytest.raises(TranscriptionError, match="no_speech_detected"):
        transcribe_candidate_audio(
            session=session,
            actor=call_data["candidate_user"],
            uploaded_audio=_upload(),
            decoder=lambda _raw: AudioFrame(pcm_s16le=b"\x00\x00" * 16000),
            stt=_SuccessStt(),
            vad=_SilentVad(),
        )


def test_transcription_rejects_invalid_audio_before_decoding(call_data):
    session = _active_session(call_data)
    with pytest.raises(TranscriptionError, match="audio_type_invalid"):
        transcribe_candidate_audio(
            session=session,
            actor=call_data["candidate_user"],
            uploaded_audio=_upload(content_type="text/plain"),
        )


def test_transcription_endpoint_requires_candidate_csrf_and_preserves_answer(
    call_data, monkeypatch
):
    session = _active_session(call_data)
    monkeypatch.setattr(
        "calling.views.transcribe_candidate_audio",
        lambda **_kwargs: SimpleNamespace(text="editable transcript", vad_segments=1),
    )
    url = reverse("calling:transcribe_answer", args=[session.pk])
    anonymous = Client()
    assert anonymous.post(url, {"audio": _upload()}).status_code == 302

    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(call_data["candidate_user"])
    assert csrf_client.post(url, {"audio": _upload()}).status_code == 403
    page = csrf_client.get(reverse("calling:candidate_session_detail", args=[session.pk]))
    token = page.cookies["csrftoken"].value
    response = csrf_client.post(
        url,
        {"audio": _upload(), "csrfmiddlewaretoken": token},
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "transcript": "editable transcript",
        "vad_segments": 1,
    }
    assert not SimulatedInterviewResponse.objects.filter(call_session=session).exists()


def test_transcription_endpoint_denies_recruiter_and_wrong_candidate(call_data):
    session = _active_session(call_data)
    url = reverse("calling:transcribe_answer", args=[session.pk])
    for user in (call_data["recruiter_user"], call_data["admin"]):
        client = Client()
        client.force_login(user)
        assert client.post(url, {"audio": _upload()}).status_code == 403


@override_settings(SPEECH_FEATURE_ENABLED=False)
def test_text_only_mode_hides_voice_controls_and_disables_transcription_endpoint(
    call_data, monkeypatch
):
    session = _active_session(call_data)
    client = Client()
    client.force_login(call_data["candidate_user"])
    detail_url = reverse("calling:candidate_session_detail", args=[session.pk])
    page = client.get(detail_url)

    assert page.status_code == 200
    assert b"data-record-answer" not in page.content
    assert b"transcription.js" not in page.content
    assert b"Speech input is unavailable on this deployment" in page.content

    monkeypatch.setattr(
        "calling.views.transcribe_candidate_audio",
        lambda **_kwargs: pytest.fail("speech adapter must not be called"),
    )
    response = client.post(
        reverse("calling:transcribe_answer", args=[session.pk]),
        {"audio": _upload()},
    )
    assert response.status_code == 404
    assert response.json() == {"status": "error", "code": "speech_disabled"}

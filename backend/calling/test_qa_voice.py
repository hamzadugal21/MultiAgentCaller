"""Authorization and persistence tests for QA-only Piper browser playback."""

import uuid

import pytest
from ai_system.voice.interfaces import AdapterStatus, SpeechSynthesisResult
from django.test import Client, override_settings
from django.urls import reverse

from calling.models import CallSession, SimulatedInterviewResponse
from calling.qa_voice import QaVoiceError, synthesize_qa_question
from calling.services import prepare_simulated_call_session, transition_call_session
from recruitment.models import InterviewQuestion

pytest_plugins = ("calling.test_call_session_services",)
pytestmark = pytest.mark.django_db


def _active_session(call_data):
    InterviewQuestion.objects.create(
        job=call_data["application"].job,
        question_text="Synthetic QA playback question",
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


class _SuccessTts:
    def synthesize(self, text):
        assert text == "Synthetic QA playback question"
        return SpeechSynthesisResult(
            status=AdapterStatus.SUCCESS,
            audio_bytes=b"RIFF-synthetic-wav",
        )


@override_settings(
    SETTINGS_MODULE="config.settings_qa",
    QA_BROWSER_VOICE_ENABLED=True,
)
def test_qa_piper_playback_is_transient_and_does_not_create_an_answer(call_data):
    session = _active_session(call_data)

    audio = synthesize_qa_question(
        session=session,
        actor=call_data["candidate_user"],
        tts=_SuccessTts(),
    )

    assert audio == b"RIFF-synthetic-wav"
    assert not SimulatedInterviewResponse.objects.filter(call_session=session).exists()


def test_qa_piper_playback_fails_closed_outside_qa(call_data):
    session = _active_session(call_data)
    with pytest.raises(QaVoiceError, match="qa_voice_disabled"):
        synthesize_qa_question(
            session=session,
            actor=call_data["candidate_user"],
            tts=_SuccessTts(),
        )


def test_qa_piper_endpoint_requires_candidate_csrf_and_returns_no_store_audio(
    call_data, monkeypatch
):
    session = _active_session(call_data)
    monkeypatch.setattr(
        "calling.views.synthesize_qa_question",
        lambda **_kwargs: b"RIFF-synthetic-wav",
    )
    url = reverse("calling:speak_question", args=[session.pk])

    anonymous = Client()
    assert anonymous.post(url).status_code == 302

    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(call_data["candidate_user"])
    assert csrf_client.post(url).status_code == 403
    page = csrf_client.get(reverse("calling:candidate_session_detail", args=[session.pk]))
    token = page.cookies["csrftoken"].value
    response = csrf_client.post(
        url,
        {"csrfmiddlewaretoken": token},
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "audio/wav"
    assert response["Cache-Control"] == "no-store"
    assert response.content == b"RIFF-synthetic-wav"
    assert not SimulatedInterviewResponse.objects.filter(call_session=session).exists()


def test_qa_piper_endpoint_denies_recruiter_and_administrator(call_data):
    session = _active_session(call_data)
    url = reverse("calling:speak_question", args=[session.pk])
    for user in (call_data["recruiter_user"], call_data["admin"]):
        client = Client()
        client.force_login(user)
        assert client.post(url).status_code == 403


@override_settings(SPEECH_FEATURE_ENABLED=False)
def test_text_only_mode_disables_piper_endpoint_without_initializing_tts(
    call_data, monkeypatch
):
    session = _active_session(call_data)
    client = Client()
    client.force_login(call_data["candidate_user"])
    monkeypatch.setattr(
        "calling.views.synthesize_qa_question",
        lambda **_kwargs: pytest.fail("Piper must not be initialized"),
    )

    response = client.post(reverse("calling:speak_question", args=[session.pk]))

    assert response.status_code == 404
    assert response.json() == {"status": "error", "code": "speech_disabled"}

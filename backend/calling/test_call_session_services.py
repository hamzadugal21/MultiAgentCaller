import uuid

import pytest
from ai_system.interview.coordinator import (
    ALLOWED_COORDINATOR_ACTIONS,
    COORDINATOR_POLICY_VERSION,
    CoordinatorAction,
    CoordinatorCommand,
    CoordinatorDirective,
    CoordinatorToolError,
    DeterministicInterviewCoordinator,
)
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from auditlog.consent_services import (
    grant_application_ai_interview_consent,
    grant_general_ai_processing_consent,
    revoke_general_ai_processing_consent,
)
from auditlog.models import AuditEvent
from auditlog.services import DomainAuditPersistenceError
from calling.coordinator_tools import DjangoInterviewCoordinatorTools
from calling.models import CallSession, SimulatedInterviewResponse
from calling.realtime import session_group_name
from calling.services import (
    CALL_SESSION_TRANSITIONS,
    CallSessionAuthorizationError,
    CallSessionServiceError,
    CallSessionTransitionError,
    create_call_session,
    get_call_session_for_actor,
    prepare_simulated_call_session,
    submit_simulated_answer,
    transition_call_session,
)
from candidates.models import CandidateProfile, Resume
from config.asgi import application as asgi_application
from interviews.models import InterviewSchedule
from recruitment.models import (
    Company,
    InterviewQuestion,
    JobApplication,
    JobPosting,
    RecruiterProfile,
)

pytestmark = pytest.mark.django_db
POLICY_VERSION = "ai-processing-v1"


@pytest.fixture
def call_data(db):
    company = Company.objects.create(name="Call Runtime Company")
    recruiter_user = User.objects.create_user(
        email="call-recruiter@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
    )
    recruiter = RecruiterProfile.objects.create(
        user=recruiter_user,
        company=company,
        is_verified=True,
        can_review_candidates=True,
    )
    job = JobPosting.objects.create(
        company=company,
        created_by=recruiter,
        title="Call Runtime Role",
        reference_code="CALL-RUNTIME-001",
        description="Synthetic test role",
        status=JobPosting.Status.OPEN,
    )
    candidate_user = User.objects.create_user(
        email="call-candidate@example.com",
        password="TestingOnly!9384",
        email_verified=True,
    )
    candidate = CandidateProfile.objects.get(user=candidate_user)
    resume = Resume.objects.create(
        candidate=candidate,
        file="candidate-resumes/synthetic-call.pdf",
        original_filename="synthetic-call.pdf",
        processing_status=Resume.ProcessingStatus.COMPLETED,
        is_active=True,
    )
    application = JobApplication.objects.create(
        job=job,
        candidate=candidate,
        resume=resume,
        status=JobApplication.Status.INVITED,
    )
    grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    grant_application_ai_interview_consent(
        application=application,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    now = timezone.now()
    schedule = InterviewSchedule.objects.create(
        application=application,
        scheduled_by=recruiter_user,
        scheduled_start=now - timezone.timedelta(minutes=1),
        scheduled_end=now + timezone.timedelta(hours=1),
        status=InterviewSchedule.Status.CONFIRMED,
        confirmed_at=now - timezone.timedelta(minutes=2),
        invitation_expires_at=now + timezone.timedelta(minutes=30),
    )
    admin = User.objects.create_user(
        email="call-admin@example.com",
        password="TestingOnly!9384",
        role=User.Role.ADMIN,
    )
    return {
        "company": company,
        "recruiter_user": recruiter_user,
        "candidate_user": candidate_user,
        "candidate": candidate,
        "application": application,
        "schedule": schedule,
        "admin": admin,
    }


def _create(data, **overrides):
    values = {
        "schedule": data["schedule"],
        "actor": data["candidate_user"],
        "idempotency_key": uuid.uuid4(),
        "policy_version": POLICY_VERSION,
    }
    values.update(overrides)
    return create_call_session(**values)


def test_call_session_model_lifecycle_schema_and_indexes(call_data):
    session = _create(call_data)

    assert session.status == CallSession.Status.PENDING
    assert session.simulated_mode is True
    assert session.current_question_index == 0
    assert session.expires_at == call_data["schedule"].scheduled_end
    assert session.schedule.application_id == call_data["application"].pk
    assert set(CallSession.Status.values) == {
        "pending",
        "ready",
        "active",
        "paused",
        "completed",
        "cancelled",
        "expired",
        "failed",
    }
    assert "call_status_expires" in {
        index.name for index in CallSession._meta.indexes
    }
    assert {
        "unique_call_session_per_schedule",
        "call_started_state_consistent",
        "call_terminal_end_consistent",
    } <= {constraint.name for constraint in CallSession._meta.constraints}


def test_creation_is_idempotent_and_one_session_per_schedule(call_data):
    key = uuid.uuid4()
    created = _create(call_data, idempotency_key=key)
    replay = _create(call_data, idempotency_key=key)

    assert replay.pk == created.pk
    assert CallSession.objects.count() == 1
    with pytest.raises(CallSessionServiceError, match="already exists"):
        _create(call_data, idempotency_key=uuid.uuid4())
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CallSession.objects.create(
                schedule=call_data["schedule"],
                creation_idempotency_key=uuid.uuid4(),
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CallSession.objects.filter(pk=created.pk).update(
                status=CallSession.Status.ACTIVE
            )


def test_creation_requires_confirmed_current_schedule_and_current_consent(call_data):
    call_data["schedule"].status = InterviewSchedule.Status.CANCELLED
    call_data["schedule"].save(update_fields=("status",))
    with pytest.raises(CallSessionServiceError, match="not eligible"):
        _create(call_data)

    call_data["schedule"].status = InterviewSchedule.Status.CONFIRMED
    call_data["schedule"].save(update_fields=("status",))
    revoke_general_ai_processing_consent(
        candidate=call_data["candidate"],
        actor=call_data["candidate_user"],
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    with pytest.raises(CallSessionServiceError, match="consent"):
        _create(call_data)


def test_actor_access_is_candidate_owned_company_scoped_and_admin_bounded(call_data):
    session = _create(call_data)
    assert get_call_session_for_actor(
        session=session, actor=call_data["candidate_user"]
    ).pk == session.pk
    assert get_call_session_for_actor(
        session=session, actor=call_data["recruiter_user"]
    ).pk == session.pk
    assert get_call_session_for_actor(session=session, actor=call_data["admin"]).pk == session.pk

    other_candidate = User.objects.create_user(
        email="other-call-candidate@example.com",
        password="TestingOnly!9384",
    )
    with pytest.raises(CallSessionAuthorizationError):
        get_call_session_for_actor(session=session, actor=other_candidate)

    other_company = Company.objects.create(name="Other Call Company")
    other_recruiter = User.objects.create_user(
        email="other-call-recruiter@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
    )
    RecruiterProfile.objects.create(
        user=other_recruiter,
        company=other_company,
        is_verified=True,
        can_review_candidates=True,
    )
    with pytest.raises(CallSessionAuthorizationError):
        get_call_session_for_actor(session=session, actor=other_recruiter)


def test_valid_lifecycle_and_repeat_transition_are_deterministic(call_data):
    session = _create(call_data)
    session = transition_call_session(
        session=session,
        target_status=CallSession.Status.READY,
        policy_version=POLICY_VERSION,
    )
    session = transition_call_session(
        session=session,
        target_status=CallSession.Status.ACTIVE,
        actor=call_data["candidate_user"],
        policy_version=POLICY_VERSION,
    )
    session = transition_call_session(
        session=session,
        target_status=CallSession.Status.PAUSED,
        actor=call_data["candidate_user"],
    )
    session = transition_call_session(
        session=session,
        target_status=CallSession.Status.ACTIVE,
        actor=call_data["candidate_user"],
        policy_version=POLICY_VERSION,
    )
    session = transition_call_session(
        session=session,
        target_status=CallSession.Status.COMPLETED,
        actor=call_data["candidate_user"],
        reason_code="questions_completed",
    )
    event_count = AuditEvent.objects.filter(
        resource_type="calling.CallSession", resource_id=str(session.pk)
    ).count()
    replay = transition_call_session(
        session=session,
        target_status=CallSession.Status.COMPLETED,
        actor=call_data["candidate_user"],
        reason_code="questions_completed",
    )

    assert replay.pk == session.pk
    assert replay.started_at is not None
    assert replay.ended_at is not None
    assert replay.duration_seconds >= 0
    assert replay.completion_reason == "questions_completed"
    assert AuditEvent.objects.filter(
        resource_type="calling.CallSession", resource_id=str(session.pk)
    ).count() == event_count


def test_invalid_transitions_and_actor_rules_are_rejected(call_data):
    session = _create(call_data)
    with pytest.raises(CallSessionTransitionError):
        transition_call_session(
            session=session,
            target_status=CallSession.Status.ACTIVE,
            actor=call_data["candidate_user"],
        )
    with pytest.raises(CallSessionAuthorizationError, match="system"):
        transition_call_session(
            session=session,
            target_status=CallSession.Status.READY,
            actor=call_data["recruiter_user"],
        )
    ready = transition_call_session(
        session=session,
        target_status=CallSession.Status.READY,
    )
    with pytest.raises(CallSessionAuthorizationError):
        transition_call_session(
            session=ready,
            target_status=CallSession.Status.ACTIVE,
            actor=call_data["recruiter_user"],
        )
    with pytest.raises(CallSessionServiceError, match="reason code"):
        transition_call_session(
            session=ready,
            target_status=CallSession.Status.CANCELLED,
            actor=call_data["admin"],
            reason_code="private narrative with spaces",
        )


def test_audit_event_uses_safe_resource_and_metadata(call_data):
    session = _create(call_data)
    event = AuditEvent.objects.get(event_type="call_session.created")

    assert event.resource_type == "calling.CallSession"
    assert event.resource_id == str(session.pk)
    assert event.metadata == {
        "application_id": str(call_data["application"].pk),
        "interview_schedule_id": str(call_data["schedule"].pk),
        "simulated_mode": True,
        "status_to": "pending",
    }
    assert not {
        "email",
        "resume_text",
        "transcript_text",
        "raw_token",
        "filesystem_path",
    } & set(event.metadata)


def test_mandatory_audit_failure_rolls_back_creation_and_transition(
    monkeypatch, call_data
):
    def fail_audit(command):
        raise DomainAuditPersistenceError("Audit event could not be recorded.")

    monkeypatch.setattr("calling.services.record_domain_event", fail_audit)
    with pytest.raises(DomainAuditPersistenceError):
        _create(call_data)
    assert not CallSession.objects.exists()

    monkeypatch.undo()
    session = _create(call_data)
    monkeypatch.setattr("calling.services.record_domain_event", fail_audit)
    with pytest.raises(DomainAuditPersistenceError):
        transition_call_session(
            session=session,
            target_status=CallSession.Status.READY,
        )
    session.refresh_from_db()
    assert session.status == CallSession.Status.PENDING


def test_transition_registry_is_immutable_and_complete():
    assert set(CALL_SESSION_TRANSITIONS) == set(CallSession.Status.values)
    with pytest.raises(TypeError):
        CALL_SESSION_TRANSITIONS[CallSession.Status.COMPLETED] = frozenset()


def _questions(data):
    return [
        InterviewQuestion.objects.create(
            job=data["application"].job,
            question_text="Describe a synthetic project example.",
            question_type=InterviewQuestion.QuestionType.EXPERIENCE,
            order=1,
        ),
        InterviewQuestion.objects.create(
            job=data["application"].job,
            question_text="How would you handle a synthetic incident?",
            question_type=InterviewQuestion.QuestionType.BEHAVIORAL,
            order=2,
        ),
    ]


def _active_session(data):
    session = prepare_simulated_call_session(
        schedule=data["schedule"],
        actor=data["candidate_user"],
        idempotency_key=uuid.uuid4(),
        policy_version=POLICY_VERSION,
    )
    return transition_call_session(
        session=session,
        target_status=CallSession.Status.ACTIVE,
        actor=data["candidate_user"],
        policy_version=POLICY_VERSION,
    )


def test_simulated_answer_progression_completion_and_idempotency(call_data):
    questions = _questions(call_data)
    session = _active_session(call_data)
    first_key = uuid.uuid4()
    first, session = submit_simulated_answer(
        session=session,
        actor=call_data["candidate_user"],
        answer_text="A bounded synthetic answer.",
        idempotency_key=first_key,
        policy_version=POLICY_VERSION,
    )
    replay, replayed_session = submit_simulated_answer(
        session=session,
        actor=call_data["candidate_user"],
        answer_text="A bounded synthetic answer.",
        idempotency_key=first_key,
        policy_version=POLICY_VERSION,
    )
    assert replay.pk == first.pk
    assert replayed_session.current_question_index == 1

    second, completed = submit_simulated_answer(
        session=session,
        actor=call_data["candidate_user"],
        answer_text="A second bounded synthetic answer.",
        idempotency_key=uuid.uuid4(),
        policy_version=POLICY_VERSION,
    )
    assert first.question == questions[0]
    assert second.question == questions[1]
    assert completed.status == CallSession.Status.COMPLETED
    assert completed.current_question_index == 2
    assert SimulatedInterviewResponse.objects.filter(call_session=session).count() == 2

    events = AuditEvent.objects.filter(event_type="call_session.answer_submitted")
    assert events.count() == 2
    assert set(events.first().metadata) == {
        "application_id",
        "interview_schedule_id",
        "question_id",
        "question_index",
    }
    assert "bounded synthetic answer" not in str(list(events.values("metadata")))


def test_simulated_answer_conflict_validation_and_audit_rollback(
    monkeypatch, call_data
):
    _questions(call_data)
    session = _active_session(call_data)
    key = uuid.uuid4()
    submit_simulated_answer(
        session=session,
        actor=call_data["candidate_user"],
        answer_text="Original synthetic answer.",
        idempotency_key=key,
        policy_version=POLICY_VERSION,
    )
    with pytest.raises(CallSessionServiceError, match="idempotency"):
        submit_simulated_answer(
            session=session,
            actor=call_data["candidate_user"],
            answer_text="Changed synthetic answer.",
            idempotency_key=key,
            policy_version=POLICY_VERSION,
        )

    def fail_audit(command):
        raise DomainAuditPersistenceError("Audit event could not be recorded.")

    monkeypatch.setattr("calling.services.record_domain_event", fail_audit)
    with pytest.raises(DomainAuditPersistenceError):
        submit_simulated_answer(
            session=session,
            actor=call_data["candidate_user"],
            answer_text="This answer must roll back.",
            idempotency_key=uuid.uuid4(),
            policy_version=POLICY_VERSION,
        )
    session.refresh_from_db()
    assert session.current_question_index == 1
    assert SimulatedInterviewResponse.objects.filter(call_session=session).count() == 1


def test_revoked_consent_blocks_simulated_answer(call_data):
    _questions(call_data)
    session = _active_session(call_data)
    revoke_general_ai_processing_consent(
        candidate=call_data["candidate"],
        actor=call_data["candidate_user"],
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    with pytest.raises(CallSessionServiceError, match="consent"):
        submit_simulated_answer(
            session=session,
            actor=call_data["candidate_user"],
            answer_text="This answer must not be stored.",
            idempotency_key=uuid.uuid4(),
            policy_version=POLICY_VERSION,
        )
    assert not SimulatedInterviewResponse.objects.exists()


def test_simulated_preparation_requires_an_approved_question(call_data):
    with pytest.raises(CallSessionServiceError, match="approved interview questions"):
        prepare_simulated_call_session(
            schedule=call_data["schedule"],
            actor=call_data["candidate_user"],
            idempotency_key=uuid.uuid4(),
            policy_version=POLICY_VERSION,
        )
    assert not CallSession.objects.exists()


def test_candidate_http_simulated_lifecycle_is_post_only_and_owned(call_data):
    _questions(call_data)
    client = Client()
    client.force_login(call_data["candidate_user"])
    prepare_url = reverse(
        "calling:prepare_session", args=(call_data["schedule"].pk,)
    )
    assert client.get(prepare_url).status_code == 405
    response = client.post(prepare_url, {"idempotency_key": uuid.uuid4()})
    session = CallSession.objects.get()
    assert response.status_code == 302
    assert session.status == CallSession.Status.READY

    detail_url = reverse("calling:candidate_session_detail", args=(session.pk,))
    assert client.get(detail_url).status_code == 200
    start_url = reverse("calling:start_or_resume_session", args=(session.pk,))
    assert client.get(start_url).status_code == 405
    assert client.post(start_url).status_code == 302
    session.refresh_from_db()
    assert session.status == CallSession.Status.ACTIVE

    answer_url = reverse("calling:submit_answer", args=(session.pk,))
    answer = client.post(
        answer_url,
        {
            "answer_text": "A view-submitted synthetic answer.",
            "idempotency_key": uuid.uuid4(),
        },
    )
    assert answer.status_code == 302
    session.refresh_from_db()
    assert session.current_question_index == 1

    other_candidate = User.objects.create_user(
        email="view-other-candidate@example.com",
        password="TestingOnly!9384",
    )
    client.force_login(other_candidate)
    assert client.get(detail_url).status_code == 404
    assert client.post(answer_url, {}).status_code == 404


def test_candidate_simulated_mutations_enforce_csrf(call_data):
    _questions(call_data)
    session = prepare_simulated_call_session(
        schedule=call_data["schedule"],
        actor=call_data["candidate_user"],
        idempotency_key=uuid.uuid4(),
        policy_version=POLICY_VERSION,
    )
    client = Client(enforce_csrf_checks=True)
    client.force_login(call_data["candidate_user"])
    start_url = reverse("calling:start_or_resume_session", args=(session.pk,))
    assert client.post(start_url).status_code == 403
    detail = client.get(
        reverse("calling:candidate_session_detail", args=(session.pk,))
    )
    assert detail.status_code == 200
    csrf_token = client.cookies["csrftoken"].value
    assert client.post(start_url, {"csrfmiddlewaretoken": csrf_token}).status_code == 302


def test_recruiter_status_view_is_company_scoped_and_hides_answers(call_data):
    _questions(call_data)
    session = _active_session(call_data)
    private_answer = "Private synthetic answer not for the status page."
    submit_simulated_answer(
        session=session,
        actor=call_data["candidate_user"],
        answer_text=private_answer,
        idempotency_key=uuid.uuid4(),
        policy_version=POLICY_VERSION,
    )
    url = reverse("calling:recruiter_session_detail", args=(session.pk,))
    client = Client()
    client.force_login(call_data["recruiter_user"])
    response = client.get(url)
    assert response.status_code == 200
    assert private_answer.encode() not in response.content

    other_company = Company.objects.create(name="View Other Company")
    other_recruiter = User.objects.create_user(
        email="view-other-recruiter@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
    )
    RecruiterProfile.objects.create(
        user=other_recruiter,
        company=other_company,
        is_verified=True,
        can_review_candidates=True,
    )
    client.force_login(other_recruiter)
    assert client.get(url).status_code == 404


def _websocket_headers(user=None):
    headers = [
        (b"host", b"localhost"),
        (b"origin", b"http://localhost"),
    ]
    if user is not None:
        client = Client()
        client.force_login(user)
        session_cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
        headers.append(
            (
                b"cookie",
                f"{settings.SESSION_COOKIE_NAME}={session_cookie}".encode(),
            )
        )
    return headers


@pytest.mark.django_db(transaction=True)
def test_websocket_requires_authentication_and_exact_session_authorization(call_data):
    _questions(call_data)
    session = _active_session(call_data)
    path = f"/ws/calling/sessions/{session.pk}/status/"
    candidate_headers = _websocket_headers(call_data["candidate_user"])

    async def scenario():
        anonymous = WebsocketCommunicator(
            asgi_application,
            path,
            headers=_websocket_headers(),
        )
        connected, close_code = await anonymous.connect()
        assert connected is False
        assert close_code == 4401

        candidate = WebsocketCommunicator(
            asgi_application,
            path,
            headers=candidate_headers,
        )
        connected, _ = await candidate.connect()
        assert connected is True
        payload = await candidate.receive_json_from()
        assert payload == {
            "type": "session.status",
            "session_id": str(session.pk),
            "status": "active",
            "current_question_index": 0,
            "simulated_mode": True,
        }
        await candidate.send_json_to({"type": "unsupported", "raw_token": "unsafe"})
        assert await candidate.receive_json_from() == {
            "type": "session.error",
            "code": "unsupported_message",
        }
        await candidate.disconnect()

    async_to_sync(scenario)()

    other_candidate = User.objects.create_user(
        email="websocket-other-candidate@example.com",
        password="TestingOnly!9384",
    )
    other_company = Company.objects.create(name="WebSocket Other Company")
    other_recruiter = User.objects.create_user(
        email="websocket-other-recruiter@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
    )
    RecruiterProfile.objects.create(
        user=other_recruiter,
        company=other_company,
        is_verified=True,
        can_review_candidates=True,
    )
    denied_headers = [
        _websocket_headers(other_candidate),
        _websocket_headers(other_recruiter),
    ]

    async def denied_scenario():
        for headers in denied_headers:
            denied = WebsocketCommunicator(
                asgi_application,
                path,
                headers=headers,
            )
            connected, close_code = await denied.connect()
            assert connected is False
            assert close_code == 4403

    async_to_sync(denied_scenario)()


@pytest.mark.django_db(transaction=True)
def test_websocket_groups_are_isolated_and_payloads_are_server_derived(call_data):
    _questions(call_data)
    first = _active_session(call_data)
    call_data["schedule"].is_current = False
    call_data["schedule"].save(update_fields=("is_current",))
    now = timezone.now()
    second_schedule = InterviewSchedule.objects.create(
        application=call_data["application"],
        scheduled_by=call_data["recruiter_user"],
        scheduled_start=now - timezone.timedelta(minutes=1),
        scheduled_end=now + timezone.timedelta(hours=1),
        status=InterviewSchedule.Status.CONFIRMED,
        confirmed_at=now - timezone.timedelta(minutes=2),
        invitation_expires_at=now + timezone.timedelta(minutes=30),
    )
    second = CallSession.objects.create(
        schedule=second_schedule,
        status=CallSession.Status.READY,
        expires_at=second_schedule.scheduled_end,
        creation_idempotency_key=uuid.uuid4(),
    )
    admin_headers = _websocket_headers(call_data["admin"])

    async def scenario():
        first_socket = WebsocketCommunicator(
            asgi_application,
            f"/ws/calling/sessions/{first.pk}/status/",
            headers=admin_headers,
        )
        second_socket = WebsocketCommunicator(
            asgi_application,
            f"/ws/calling/sessions/{second.pk}/status/",
            headers=admin_headers,
        )
        assert (await first_socket.connect())[0] is True
        assert (await second_socket.connect())[0] is True
        await first_socket.receive_json_from()
        await second_socket.receive_json_from()

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            session_group_name(first.pk),
            {
                "type": "session.status",
                "payload": {
                    "raw_token": "must-not-be-forwarded",
                    "transcript_text": "must-not-be-forwarded",
                },
            },
        )
        payload = await first_socket.receive_json_from()
        assert payload["session_id"] == str(first.pk)
        assert set(payload) == {
            "type",
            "session_id",
            "status",
            "current_question_index",
            "simulated_mode",
        }
        assert await second_socket.receive_nothing(timeout=0.1)
        await first_socket.disconnect()
        await second_socket.disconnect()

    async_to_sync(scenario)()


def test_deterministic_coordinator_asks_only_approved_questions(call_data):
    questions = _questions(call_data)
    session = prepare_simulated_call_session(
        schedule=call_data["schedule"],
        actor=call_data["candidate_user"],
        idempotency_key=uuid.uuid4(),
        policy_version=POLICY_VERSION,
    )
    coordinator = DeterministicInterviewCoordinator(
        DjangoInterviewCoordinatorTools()
    )
    status = coordinator.execute(
        CoordinatorCommand(
            action=CoordinatorAction.STATUS,
            session_id=session.pk,
            actor=call_data["candidate_user"],
        )
    )
    assert status.directive == CoordinatorDirective.START_REQUIRED
    assert status.policy_version == COORDINATOR_POLICY_VERSION

    started = coordinator.execute(
        CoordinatorCommand(
            action=CoordinatorAction.START,
            session_id=session.pk,
            actor=call_data["candidate_user"],
        )
    )
    assert started.directive == CoordinatorDirective.ASK_QUESTION
    assert started.snapshot.current_question_id == questions[0].pk
    assert started.snapshot.current_question_text == questions[0].question_text

    progressed = coordinator.execute(
        CoordinatorCommand(
            action=CoordinatorAction.SUBMIT_ANSWER,
            session_id=session.pk,
            actor=call_data["candidate_user"],
            answer_text="First coordinator answer.",
            idempotency_key=uuid.uuid4(),
        )
    )
    assert progressed.directive == CoordinatorDirective.ASK_QUESTION
    assert progressed.snapshot.current_question_id == questions[1].pk

    completed = coordinator.execute(
        CoordinatorCommand(
            action=CoordinatorAction.SUBMIT_ANSWER,
            session_id=session.pk,
            actor=call_data["candidate_user"],
            answer_text="Second coordinator answer.",
            idempotency_key=uuid.uuid4(),
        )
    )
    assert completed.directive == CoordinatorDirective.TERMINAL
    assert completed.snapshot.status == CallSession.Status.COMPLETED


def test_coordinator_allowlist_excludes_privileged_and_external_actions(call_data):
    assert {action.value for action in ALLOWED_COORDINATOR_ACTIONS} == {
        "status",
        "start",
        "pause",
        "cancel",
        "submit_answer",
    }
    coordinator = DeterministicInterviewCoordinator(
        DjangoInterviewCoordinatorTools()
    )
    result = coordinator.execute(
        CoordinatorCommand(
            action="hire_candidate",
            session_id=uuid.uuid4(),
            actor=call_data["admin"],
        )
    )
    assert result.directive == CoordinatorDirective.STOPPED
    assert result.error_code == "unsupported_action"
    assert result.snapshot is None


def test_coordinator_candidate_tools_reject_recruiter_impersonation(call_data):
    _questions(call_data)
    session = prepare_simulated_call_session(
        schedule=call_data["schedule"],
        actor=call_data["candidate_user"],
        idempotency_key=uuid.uuid4(),
        policy_version=POLICY_VERSION,
    )
    coordinator = DeterministicInterviewCoordinator(
        DjangoInterviewCoordinatorTools()
    )
    result = coordinator.execute(
        CoordinatorCommand(
            action=CoordinatorAction.START,
            session_id=session.pk,
            actor=call_data["recruiter_user"],
        )
    )
    session.refresh_from_db()
    assert result.directive == CoordinatorDirective.STOPPED
    assert result.error_code == "action_rejected"
    assert session.status == CallSession.Status.READY


def test_coordinator_failure_fallback_does_not_expose_internal_error(call_data):
    class FailingTools:
        def snapshot(self, **kwargs):
            raise CoordinatorToolError("secret database location")

    result = DeterministicInterviewCoordinator(FailingTools()).execute(
        CoordinatorCommand(
            action=CoordinatorAction.STATUS,
            session_id=uuid.uuid4(),
            actor=call_data["candidate_user"],
        )
    )
    assert result.directive == CoordinatorDirective.STOPPED
    assert result.error_code == "action_rejected"
    assert "secret" not in str(result)

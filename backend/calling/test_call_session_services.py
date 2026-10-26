import uuid

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from auditlog.consent_services import (
    grant_application_ai_interview_consent,
    grant_general_ai_processing_consent,
    revoke_general_ai_processing_consent,
)
from auditlog.models import AuditEvent
from auditlog.services import DomainAuditPersistenceError
from calling.models import CallSession
from calling.services import (
    CALL_SESSION_TRANSITIONS,
    CallSessionAuthorizationError,
    CallSessionServiceError,
    CallSessionTransitionError,
    create_call_session,
    get_call_session_for_actor,
    transition_call_session,
)
from candidates.models import CandidateProfile, Resume
from interviews.models import InterviewSchedule
from recruitment.models import Company, JobApplication, JobPosting, RecruiterProfile

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

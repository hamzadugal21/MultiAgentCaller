import uuid

import pytest
from ai_system.interview.coordinator import (
    CoordinatorAction,
    CoordinatorCommand,
    CoordinatorDirective,
    DeterministicInterviewCoordinator,
)
from django.utils import timezone

from accounts.models import User
from auditlog.consent_services import (
    grant_application_ai_interview_consent,
    grant_general_ai_processing_consent,
)
from auditlog.models import AuditEvent
from calling.coordinator_tools import DjangoInterviewCoordinatorTools
from calling.models import CallSession, SimulatedInterviewResponse
from calling.services import prepare_simulated_call_session
from candidates.models import CandidateProfile, Resume
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


def test_complete_simulated_interview_runtime_and_audit_flow():
    company = Company.objects.create(name="Synthetic Week 3 Company")
    recruiter_user = User.objects.create_user(
        email="week3-recruiter@example.com",
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
        title="Synthetic Runtime Engineer",
        reference_code="WEEK3-E2E-001",
        description="Synthetic integration test role.",
        status=JobPosting.Status.OPEN,
    )
    questions = [
        InterviewQuestion.objects.create(
            job=job,
            question_text="Describe a synthetic project.",
            question_type=InterviewQuestion.QuestionType.EXPERIENCE,
            order=1,
        ),
        InterviewQuestion.objects.create(
            job=job,
            question_text="Describe a synthetic recovery plan.",
            question_type=InterviewQuestion.QuestionType.BEHAVIORAL,
            order=2,
        ),
    ]
    candidate_user = User.objects.create_user(
        email="week3-candidate@example.com",
        password="TestingOnly!9384",
        email_verified=True,
    )
    candidate = CandidateProfile.objects.get(user=candidate_user)
    resume = Resume.objects.create(
        candidate=candidate,
        file="candidate-resumes/synthetic-week3.pdf",
        original_filename="synthetic-week3.pdf",
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
    session = prepare_simulated_call_session(
        schedule=schedule,
        actor=candidate_user,
        idempotency_key=uuid.uuid4(),
        policy_version=POLICY_VERSION,
    )
    coordinator = DeterministicInterviewCoordinator(
        DjangoInterviewCoordinatorTools()
    )

    started = coordinator.execute(
        CoordinatorCommand(
            action=CoordinatorAction.START,
            session_id=session.pk,
            actor=candidate_user,
        )
    )
    assert started.directive == CoordinatorDirective.ASK_QUESTION
    assert started.snapshot.current_question_id == questions[0].pk

    first = coordinator.execute(
        CoordinatorCommand(
            action=CoordinatorAction.SUBMIT_ANSWER,
            session_id=session.pk,
            actor=candidate_user,
            answer_text="A bounded synthetic integration answer.",
            idempotency_key=uuid.uuid4(),
        )
    )
    assert first.directive == CoordinatorDirective.ASK_QUESTION
    assert first.snapshot.current_question_id == questions[1].pk

    completed = coordinator.execute(
        CoordinatorCommand(
            action=CoordinatorAction.SUBMIT_ANSWER,
            session_id=session.pk,
            actor=candidate_user,
            answer_text="A second bounded synthetic integration answer.",
            idempotency_key=uuid.uuid4(),
        )
    )
    assert completed.directive == CoordinatorDirective.TERMINAL
    assert completed.snapshot.status == CallSession.Status.COMPLETED
    assert SimulatedInterviewResponse.objects.filter(call_session=session).count() == 2

    required_events = {
        "call_session.created",
        "call_session.ready",
        "call_session.started",
        "call_session.answer_submitted",
        "call_session.completed",
    }
    assert required_events <= set(
        AuditEvent.objects.filter(
            resource_id=str(session.pk)
        ).values_list("event_type", flat=True)
    )
    audit_metadata = " ".join(
        str(value)
        for value in AuditEvent.objects.filter(
            resource_id=str(session.pk)
        ).values_list("metadata", flat=True)
    )
    assert "bounded synthetic integration answer" not in audit_metadata
    assert "week3-candidate@example.com" not in audit_metadata

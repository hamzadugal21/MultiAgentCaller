import uuid
from decimal import Decimal
from io import BytesIO

import pytest
from ai_system.interview.coordinator import (
    CoordinatorAction,
    CoordinatorCommand,
    CoordinatorDirective,
    DeterministicInterviewCoordinator,
)
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from docx import Document

from accounts.email_verification_services import (
    create_email_verification_challenge,
    verify_email_verification_token,
)
from accounts.models import User
from auditlog.consent_services import grant_general_ai_processing_consent
from auditlog.models import AuditEvent
from calling.coordinator_tools import DjangoInterviewCoordinatorTools
from calling.models import CallSession
from calling.services import prepare_simulated_call_session
from interviews.evaluation_services import (
    CriterionReview,
    finalize_human_evaluation,
    save_human_evaluation,
    start_human_evaluation,
)
from interviews.models import (
    CandidateEvaluation,
    EvaluationCriterion,
    EvaluationRubric,
    InterviewSchedule,
)
from interviews.scheduling_services import (
    confirm_interview_invitation,
    create_interview_invitation,
)
from recruitment.administration_services import create_company, provision_recruiter
from recruitment.job_services import create_job
from recruitment.models import InterviewQuestion, JobApplication, JobPosting
from recruitment.transition_services import transition_job

pytestmark = pytest.mark.django_db
POLICY_VERSION = "ai-processing-v1"


def _synthetic_docx_upload():
    buffer = BytesIO()
    document = Document()
    document.add_paragraph("Synthetic Python and Django project experience.")
    document.save(buffer)
    return SimpleUploadedFile(
        "synthetic-week4-resume.docx",
        buffer.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )


@override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
)
def test_synthetic_recruitment_flow_ends_in_explicit_human_review(
    client,
    tmp_path,
    settings,
):
    settings.MEDIA_ROOT = tmp_path
    cache.clear()
    administrator = User.objects.create_superuser(
        email="week4-synthetic-admin@example.com",
        password="TestPassword123!",
    )
    company = create_company(actor=administrator, name="Week 4 Synthetic Company")
    recruiter_user = User.objects.create_user(
        email="week4-synthetic-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
        first_name="Synthetic",
        last_name="Reviewer",
    )
    provision_recruiter(
        actor=administrator,
        user=recruiter_user,
        company=company,
        is_verified=True,
    )
    job = create_job(
        actor=recruiter_user,
        values={
            "title": "Synthetic Evaluation Engineer",
            "reference_code": "WEEK4-E2E-001",
            "description": "A synthetic role used only for automated testing.",
        },
    )
    job = transition_job(
        job=job,
        target_status=JobPosting.Status.OPEN,
        actor=recruiter_user,
    )
    questions = (
        InterviewQuestion.objects.create(
            job=job,
            question_text="Describe a synthetic project delivery example.",
            question_type=InterviewQuestion.QuestionType.EXPERIENCE,
            order=1,
        ),
        InterviewQuestion.objects.create(
            job=job,
            question_text="Describe a synthetic incident recovery example.",
            question_type=InterviewQuestion.QuestionType.BEHAVIORAL,
            order=2,
        ),
    )
    rubric = EvaluationRubric.objects.create(
        job=job,
        name="Synthetic job rubric",
        version=1,
        passing_score=Decimal("60"),
    )
    criteria = (
        EvaluationCriterion.objects.create(
            rubric=rubric,
            name="Relevant experience",
            description="Assess job-related delivery evidence only.",
            order=1,
            weight=Decimal("0.600"),
        ),
        EvaluationCriterion.objects.create(
            rubric=rubric,
            name="Structured communication",
            description="Assess clarity against the approved question.",
            order=2,
            weight=Decimal("0.400"),
        ),
    )

    signup = client.post(
        reverse("accounts:signup"),
        {
            "first_name": "Synthetic",
            "last_name": "Candidate",
            "email": "week4-synthetic-candidate@example.com",
            "password1": "TestingOnly!9384",
            "password2": "TestingOnly!9384",
        },
    )
    assert signup.status_code == 302
    candidate_user = User.objects.get(email="week4-synthetic-candidate@example.com")
    issued_email = create_email_verification_challenge(user=candidate_user)
    verify_email_verification_token(
        token=issued_email.token,
        attempt_key="a" * 64,
    )
    candidate_user.refresh_from_db()
    assert candidate_user.email_verified is True

    profile_update = client.post(
        reverse("candidates:profile_edit"),
        {
            "city": "Synthetic City",
            "country_code": "PK",
            "timezone": "Asia/Karachi",
            "professional_summary": "Synthetic profile information for testing only.",
            "years_of_experience": 4,
            "availability": "available",
        },
    )
    assert profile_update.status_code == 302
    grant_general_ai_processing_consent(
        candidate=candidate_user.candidate_profile,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    upload = client.post(
        reverse("candidates:resume_upload"),
        {"file": _synthetic_docx_upload()},
    )
    assert upload.status_code == 302
    resume = candidate_user.candidate_profile.resumes.get(is_active=True)

    application_response = client.post(
        reverse("recruitment:application_create", args=(job.pk,)),
        {
            "resume": resume.pk,
            "cover_note": "Synthetic cover note that must not enter audit metadata.",
            "consent_to_ai_interview": "on",
        },
    )
    assert application_response.status_code == 302
    application = JobApplication.objects.get(
        job=job,
        candidate=candidate_user.candidate_profile,
    )

    scheduled_start = timezone.now() + timezone.timedelta(minutes=5)
    issued_invitation = create_interview_invitation(
        application=application,
        actor=recruiter_user,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_start + timezone.timedelta(hours=1),
        timezone_name="Asia/Karachi",
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    schedule = confirm_interview_invitation(
        token=issued_invitation.token,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        consent_idempotency_key=uuid.uuid4(),
    )
    assert schedule.status == InterviewSchedule.Status.CONFIRMED
    # Simulate arrival of the confirmed interview window without sleeping.
    interview_now = timezone.now()
    InterviewSchedule.objects.filter(pk=schedule.pk).update(
        scheduled_start=interview_now - timezone.timedelta(minutes=1),
        scheduled_end=interview_now + timezone.timedelta(hours=1),
    )
    schedule.refresh_from_db()

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
    first_answer = "Synthetic answer one; never copy this into audit metadata."
    second_answer = "Synthetic answer two; never copy this into audit metadata."
    coordinator.execute(
        CoordinatorCommand(
            action=CoordinatorAction.SUBMIT_ANSWER,
            session_id=session.pk,
            actor=candidate_user,
            answer_text=first_answer,
            idempotency_key=uuid.uuid4(),
        )
    )
    completed = coordinator.execute(
        CoordinatorCommand(
            action=CoordinatorAction.SUBMIT_ANSWER,
            session_id=session.pk,
            actor=candidate_user,
            answer_text=second_answer,
            idempotency_key=uuid.uuid4(),
        )
    )
    assert completed.directive == CoordinatorDirective.TERMINAL
    assert completed.snapshot.status == CallSession.Status.COMPLETED

    evaluation = start_human_evaluation(
        application=application,
        actor=recruiter_user,
        source_session=session,
    )
    evaluation = save_human_evaluation(
        evaluation=evaluation,
        actor=recruiter_user,
        criterion_reviews=(
            CriterionReview(
                criteria[0].pk,
                "82",
                "0.80",
                "Concise evidence aligned with the delivery criterion.",
            ),
            CriterionReview(
                criteria[1].pk,
                "76",
                "0.75",
                "Structured evidence aligned with the communication criterion.",
            ),
        ),
        summary="Synthetic rubric evidence supports human review.",
        reviewer_notes="Restricted synthetic reviewer note.",
    )
    assert evaluation.is_final is False
    application.refresh_from_db()
    assert application.status == JobApplication.Status.INVITED

    finalized = finalize_human_evaluation(
        evaluation=evaluation,
        actor=recruiter_user,
        review_outcome=CandidateEvaluation.ReviewOutcome.ADVANCE,
        reviewer_notes="Explicit authorized synthetic human rationale.",
    )
    application.refresh_from_db()
    assert finalized.is_final is True
    assert finalized.reviewed_by_id == recruiter_user.pk
    assert application.status == JobApplication.Status.SHORTLISTED

    required_events = {
        "email_verification.succeeded",
        "consent.granted",
        "resume.processing_succeeded",
        "application.created",
        "interview.confirmed",
        "call_session.completed",
        "evaluation.started",
        "evaluation.scored",
        "evaluation.finalized",
    }
    assert required_events <= set(
        AuditEvent.objects.values_list("event_type", flat=True)
    )
    audit_metadata = " ".join(
        str(value) for value in AuditEvent.objects.values_list("metadata", flat=True)
    )
    for forbidden in (
        candidate_user.email,
        resume.extracted_text,
        "Synthetic cover note",
        first_answer,
        second_answer,
        issued_email.token,
        issued_invitation.token,
        "Restricted synthetic reviewer note",
        str(tmp_path),
    ):
        assert forbidden not in audit_metadata

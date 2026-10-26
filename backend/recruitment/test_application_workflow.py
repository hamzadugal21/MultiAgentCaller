import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditEvent, ConsentRecord
from calling.models import CallSession
from candidates.models import CandidateProfile, Resume
from interviews.models import InterviewSchedule
from recruitment.application_services import ApplicationServiceError, create_application
from recruitment.models import Company, JobApplication, JobPosting, RecruiterProfile

pytestmark = pytest.mark.django_db


@pytest.fixture
def application_data(db):
    company = Company.objects.create(name="Application Company")
    recruiter_user = User.objects.create_user(
        email="application-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    recruiter = RecruiterProfile.objects.create(
        user=recruiter_user,
        company=company,
        is_verified=True,
    )
    job = JobPosting.objects.create(
        company=company,
        created_by=recruiter,
        title="Application Role",
        reference_code="APP-001",
        description="Role",
        status=JobPosting.Status.OPEN,
        application_deadline=timezone.now() + timezone.timedelta(days=5),
    )
    candidate_user = User.objects.create_user(
        email="application-candidate@example.com",
        password="TestPassword123!",
        email_verified=True,
    )
    candidate = CandidateProfile.objects.get(user=candidate_user)
    resume = Resume.objects.create(
        candidate=candidate,
        file="candidate-resumes/application.pdf",
        original_filename="application.pdf",
        processing_status=Resume.ProcessingStatus.COMPLETED,
        is_active=True,
    )
    return {
        "company": company,
        "recruiter_user": recruiter_user,
        "recruiter": recruiter,
        "job": job,
        "candidate_user": candidate_user,
        "candidate": candidate,
        "resume": resume,
    }


def test_application_requires_verified_email(application_data):
    application_data["candidate_user"].email_verified = False
    application_data["candidate_user"].save(update_fields=("email_verified",))
    with pytest.raises(ApplicationServiceError, match="Email verification"):
        create_application(
            actor=application_data["candidate_user"],
            job=application_data["job"],
            resume=application_data["resume"],
        )


def test_application_requires_owned_active_resume(application_data):
    other_user = User.objects.create_user(
        email="other-resume-candidate@example.com",
        password="TestPassword123!",
        email_verified=True,
    )
    other_profile = CandidateProfile.objects.get(user=other_user)
    other_resume = Resume.objects.create(
        candidate=other_profile,
        file="candidate-resumes/other.pdf",
        original_filename="other.pdf",
        processing_status=Resume.ProcessingStatus.COMPLETED,
        is_active=True,
    )
    with pytest.raises(ApplicationServiceError, match="not eligible"):
        create_application(
            actor=application_data["candidate_user"],
            job=application_data["job"],
            resume=other_resume,
        )


def test_application_creation_prevents_duplicates_and_can_record_consent(application_data):
    application = create_application(
        actor=application_data["candidate_user"],
        job=application_data["job"],
        resume=application_data["resume"],
        grant_interview_consent=True,
        policy_version="ai-processing-v1",
        consent_idempotency_key="7c624770-4c22-44ef-9c45-2b34693cfef9",
    )
    application.refresh_from_db()
    assert application.consent_to_ai_interview is True
    assert ConsentRecord.objects.filter(application=application).exists()
    assert AuditEvent.objects.filter(event_type="application.created").exists()
    with pytest.raises(ApplicationServiceError, match="already exists"):
        create_application(
            actor=application_data["candidate_user"],
            job=application_data["job"],
            resume=application_data["resume"],
        )


def test_application_view_ignores_status_and_candidate_mass_assignment(client, application_data):
    client.force_login(application_data["candidate_user"])
    response = client.post(
        reverse("recruitment:application_create", args=(application_data["job"].pk,)),
        {
            "resume": application_data["resume"].pk,
            "cover_note": "Interested",
            "status": JobApplication.Status.SHORTLISTED,
            "candidate": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code == 302
    application = JobApplication.objects.get()
    assert application.status == JobApplication.Status.APPLIED
    assert application.candidate == application_data["candidate"]


def test_withdrawal_cancels_current_schedule_transactionally(client, application_data):
    application = create_application(
        actor=application_data["candidate_user"],
        job=application_data["job"],
        resume=application_data["resume"],
    )
    schedule = InterviewSchedule.objects.create(
        application=application,
        scheduled_by=application_data["recruiter_user"],
        scheduled_start=timezone.now() + timezone.timedelta(days=2),
        scheduled_end=timezone.now() + timezone.timedelta(days=2, hours=1),
    )
    client.force_login(application_data["candidate_user"])
    response = client.post(
        reverse("recruitment:application_withdraw", args=(application.pk,))
    )
    assert response.status_code == 302
    application.refresh_from_db()
    schedule.refresh_from_db()
    assert application.status == JobApplication.Status.WITHDRAWN
    assert schedule.status == InterviewSchedule.Status.CANCELLED
    assert schedule.is_current is False


def test_withdrawal_is_blocked_after_call_begins(client, application_data):
    application = create_application(
        actor=application_data["candidate_user"],
        job=application_data["job"],
        resume=application_data["resume"],
    )
    schedule = InterviewSchedule.objects.create(
        application=application,
        scheduled_start=timezone.now() + timezone.timedelta(days=2),
        scheduled_end=timezone.now() + timezone.timedelta(days=2, hours=1),
    )
    CallSession.objects.create(schedule=schedule, status=CallSession.Status.IN_PROGRESS)
    client.force_login(application_data["candidate_user"])
    client.post(reverse("recruitment:application_withdraw", args=(application.pk,)))
    application.refresh_from_db()
    assert application.status == JobApplication.Status.APPLIED


def test_candidate_and_recruiter_cross_object_access_is_denied(client, application_data):
    application = create_application(
        actor=application_data["candidate_user"],
        job=application_data["job"],
        resume=application_data["resume"],
    )
    other_candidate = User.objects.create_user(
        email="other-application-candidate@example.com",
        password="TestPassword123!",
    )
    client.force_login(other_candidate)
    assert (
        client.get(reverse("recruitment:application_detail", args=(application.pk,))).status_code
        == 404
    )

    other_company = Company.objects.create(name="Other Application Company")
    other_recruiter = User.objects.create_user(
        email="other-application-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    RecruiterProfile.objects.create(
        user=other_recruiter,
        company=other_company,
        is_verified=True,
    )
    client.force_login(other_recruiter)
    assert (
        client.get(reverse("recruitment:application_detail", args=(application.pk,))).status_code
        == 404
    )


def test_application_consent_and_withdrawal_are_post_only(client, application_data):
    application = create_application(
        actor=application_data["candidate_user"],
        job=application_data["job"],
        resume=application_data["resume"],
    )
    client.force_login(application_data["candidate_user"])
    assert client.get(reverse("recruitment:application_consent", args=(application.pk,))).status_code == 405
    assert client.get(reverse("recruitment:application_withdraw", args=(application.pk,))).status_code == 405

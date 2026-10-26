import uuid
from io import BytesIO

import pytest
from django.core import mail
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
from interviews.models import InterviewSchedule
from interviews.scheduling_services import (
    confirm_interview_invitation,
    create_interview_invitation,
    deliver_interview_invitation,
)
from recruitment.administration_services import create_company, provision_recruiter
from recruitment.job_services import create_job
from recruitment.models import JobApplication, JobPosting
from recruitment.transition_services import transition_job

pytestmark = pytest.mark.django_db
POLICY = "ai-processing-v1"


def _docx_upload():
    buffer = BytesIO()
    document = Document()
    document.add_paragraph("Synthetic Python and Django experience")
    document.save(buffer)
    return SimpleUploadedFile(
        "synthetic-resume.docx",
        buffer.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )


@override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
)
def test_complete_week2_pre_interview_workflow(client, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    cache.clear()

    administrator = User.objects.create_superuser(
        email="integration-admin@example.com", password="TestPassword123!"
    )
    company = create_company(actor=administrator, name="Integration Company")
    recruiter_user = User.objects.create_user(
        email="integration-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
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
            "title": "Integration Engineer",
            "reference_code": "E2E-001",
            "description": "Synthetic test role",
        },
    )
    job = transition_job(job=job, target_status=JobPosting.Status.OPEN, actor=recruiter_user)

    signup_response = client.post(
        reverse("accounts:signup"),
        {
            "first_name": "Synthetic",
            "last_name": "Candidate",
            "email": "integration-candidate@example.com",
            "password1": "TestingOnly!9384",
            "password2": "TestingOnly!9384",
        },
    )
    assert signup_response.status_code == 302
    candidate_user = User.objects.get(email="integration-candidate@example.com")
    issued_email = create_email_verification_challenge(user=candidate_user)
    verify_email_verification_token(
        token=issued_email.token,
        attempt_key="a" * 64,
    )
    candidate_user.refresh_from_db()
    assert candidate_user.email_verified is True

    profile_response = client.post(
        reverse("candidates:profile_edit"),
        {
            "city": "Lahore",
            "country_code": "PK",
            "timezone": "Asia/Karachi",
            "years_of_experience": 3,
            "availability": "available",
        },
    )
    assert profile_response.status_code == 302
    grant_general_ai_processing_consent(
        candidate=candidate_user.candidate_profile,
        actor=candidate_user,
        policy_version=POLICY,
        idempotency_key=uuid.uuid4(),
    )
    upload_response = client.post(
        reverse("candidates:resume_upload"), {"file": _docx_upload()}
    )
    assert upload_response.status_code == 302
    resume = candidate_user.candidate_profile.resumes.get(is_active=True)

    browse_response = client.get(reverse("recruitment:job_detail", args=(job.pk,)))
    assert browse_response.status_code == 200
    apply_response = client.post(
        reverse("recruitment:application_create", args=(job.pk,)),
        {
            "resume": resume.pk,
            "cover_note": "Synthetic application",
            "consent_to_ai_interview": "on",
        },
    )
    assert apply_response.status_code == 302
    application = JobApplication.objects.get(job=job, candidate=candidate_user.candidate_profile)

    client.force_login(recruiter_user)
    recruiter_view = client.get(
        reverse("recruitment:application_detail", args=(application.pk,))
    )
    assert recruiter_view.status_code == 200
    start = timezone.now() + timezone.timedelta(days=3)
    issued_invitation = create_interview_invitation(
        application=application,
        actor=recruiter_user,
        scheduled_start=start,
        scheduled_end=start + timezone.timedelta(hours=1),
        timezone_name="Asia/Karachi",
        policy_version=POLICY,
        idempotency_key=uuid.uuid4(),
    )
    assert deliver_interview_invitation(
        issued=issued_invitation,
        confirmation_url=f"https://example.test/interviews/confirm/{issued_invitation.token}/",
    )
    assert len(mail.outbox) == 1

    schedule = confirm_interview_invitation(
        token=issued_invitation.token,
        actor=candidate_user,
        policy_version=POLICY,
        consent_idempotency_key=uuid.uuid4(),
    )
    assert schedule.status == InterviewSchedule.Status.CONFIRMED

    required_events = {
        "company.created",
        "recruiter.provisioned",
        "job.created",
        "job.published",
        "email_verification.requested",
        "email_verification.succeeded",
        "profile.updated",
        "consent.granted",
        "resume.uploaded",
        "resume.processing_started",
        "resume.processing_succeeded",
        "resume.activated",
        "application.created",
        "application.status_changed",
        "interview.invited",
        "interview.confirmed",
    }
    assert required_events <= set(AuditEvent.objects.values_list("event_type", flat=True))
    serialized_metadata = " ".join(str(value) for value in AuditEvent.objects.values_list("metadata", flat=True))
    assert "integration-candidate@example.com" not in serialized_metadata
    assert issued_invitation.token not in serialized_metadata

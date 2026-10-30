import uuid

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from auditlog.consent_services import grant_general_ai_processing_consent
from auditlog.models import AuditEvent, ConsentRecord
from calling.models import CallSession
from candidates.models import CandidateProfile, CandidateSkill, Resume, Skill
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
            "consent_to_ai_interview": "on",
            "status": JobApplication.Status.SHORTLISTED,
            "candidate": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code == 302
    application = JobApplication.objects.get()
    assert application.status == JobApplication.Status.APPLIED
    assert application.candidate == application_data["candidate"]
    assert application.cover_note == "Interested"
    assert application.consent_to_ai_interview is True
    assert ConsentRecord.objects.filter(application=application).exists()


def test_application_form_access_and_resume_choices_are_candidate_scoped(
    client, application_data
):
    url = reverse(
        "recruitment:application_create", args=(application_data["job"].pk,)
    )
    response = client.get(url)
    assert response.status_code == 302

    client.force_login(application_data["recruiter_user"])
    assert client.get(url).status_code == 403

    admin = User.objects.create_user(
        email="application-admin@example.com",
        password="TestPassword123!",
        role=User.Role.ADMIN,
    )
    client.force_login(admin)
    assert client.get(url).status_code == 403

    other_user = User.objects.create_user(
        email="application-form-other@example.com",
        password="TestPassword123!",
    )
    other_resume = Resume.objects.create(
        candidate=CandidateProfile.objects.get(user=other_user),
        file="candidate-resumes/private-other.pdf",
        original_filename="private-other.pdf",
        processing_status=Resume.ProcessingStatus.COMPLETED,
        is_active=True,
    )
    client.force_login(application_data["candidate_user"])
    response = client.get(url)
    content = response.content.decode()
    assert response.status_code == 200
    assert application_data["resume"].original_filename in content
    assert other_resume.original_filename not in content
    assert other_resume.file.name not in content
    assert "AI interview consent" in content
    assert "csrfmiddlewaretoken" in content


def test_application_form_displays_validation_and_duplicate_errors(
    client, application_data
):
    url = reverse(
        "recruitment:application_create", args=(application_data["job"].pk,)
    )
    client.force_login(application_data["candidate_user"])

    invalid_response = client.post(url, {"cover_note": "Missing resume"})
    assert invalid_response.status_code == 200
    assert "This field is required." in invalid_response.content.decode()
    assert JobApplication.objects.count() == 0

    create_application(
        actor=application_data["candidate_user"],
        job=application_data["job"],
        resume=application_data["resume"],
    )
    duplicate_response = client.post(
        url,
        {"resume": application_data["resume"].pk, "cover_note": "Again"},
    )
    assert duplicate_response.status_code == 200
    assert "An application already exists." in duplicate_response.content.decode()
    assert JobApplication.objects.count() == 1


def test_candidate_application_list_access_and_empty_state(client, application_data):
    url = reverse("recruitment:application_list")
    assert client.get(url).status_code == 302

    client.force_login(application_data["recruiter_user"])
    recruiter_response = client.get(url)
    assert recruiter_response.status_code == 200
    assert "recruitment/recruiter_application_list.html" in {
        template.name for template in recruiter_response.templates
    }
    recruiter_content = recruiter_response.content.decode()
    assert "candidate-applications-page" not in recruiter_content
    assert "No applications are available for review" in recruiter_content
    assert "Candidate search and filtering are not available" in recruiter_content

    admin = User.objects.create_user(
        email="application-list-admin@example.com",
        password="TestPassword123!",
        role=User.Role.ADMIN,
    )
    client.force_login(admin)
    assert client.get(url).status_code == 403

    empty_candidate = User.objects.create_user(
        email="empty-application-list@example.com",
        password="TestPassword123!",
    )
    client.force_login(empty_candidate)
    empty_response = client.get(url)
    content = empty_response.content.decode()
    assert empty_response.status_code == 200
    assert "No applications yet" in content
    assert "No confirmed upcoming interview is currently available." in content


def test_recruiter_application_list_denies_ineligible_recruiters(
    client, application_data
):
    url = reverse("recruitment:application_list")
    recruiter = application_data["recruiter"]
    recruiter.is_verified = False
    recruiter.save(update_fields=("is_verified",))
    client.force_login(application_data["recruiter_user"])

    assert client.get(url).status_code == 403

    recruiter.is_verified = True
    recruiter.can_review_candidates = False
    recruiter.save(update_fields=("is_verified", "can_review_candidates"))

    assert client.get(url).status_code == 403


def test_recruiter_application_list_is_company_scoped_with_safe_detail_links(
    client, application_data
):
    application_data["candidate_user"].first_name = "Ayesha"
    application_data["candidate_user"].last_name = "Khan"
    application_data["candidate_user"].save(
        update_fields=("first_name", "last_name")
    )
    own_application = create_application(
        actor=application_data["candidate_user"],
        job=application_data["job"],
        resume=application_data["resume"],
    )

    other_company = Company.objects.create(name="Private Other Application Company")
    other_recruiter_user = User.objects.create_user(
        email="private-list-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    other_recruiter = RecruiterProfile.objects.create(
        user=other_recruiter_user,
        company=other_company,
        is_verified=True,
    )
    other_job = JobPosting.objects.create(
        company=other_company,
        created_by=other_recruiter,
        title="Other Company Private Role",
        reference_code="APP-LIST-OTHER",
        description="Private synthetic role.",
        status=JobPosting.Status.OPEN,
    )
    other_candidate_user = User.objects.create_user(
        email="private-list-candidate@example.com",
        password="TestPassword123!",
        first_name="Private",
        last_name="Candidate",
        email_verified=True,
    )
    other_resume = Resume.objects.create(
        candidate=other_candidate_user.candidate_profile,
        file="candidate-resumes/private-list.pdf",
        original_filename="private-list.pdf",
        processing_status=Resume.ProcessingStatus.COMPLETED,
        is_active=True,
    )
    other_application = create_application(
        actor=other_candidate_user,
        job=other_job,
        resume=other_resume,
    )
    client.force_login(application_data["recruiter_user"])

    response = client.get(reverse("recruitment:application_list"))

    assert response.status_code == 200
    assert len(response.context["application_entries"]) == 1
    content = response.content.decode()
    assert "Ayesha Khan" in content
    assert application_data["job"].title in content
    assert reverse(
        "recruitment:application_detail",
        args=(own_application.pk,),
    ) in content
    assert "Other Company Private Role" not in content
    assert "Private Candidate" not in content
    assert reverse(
        "recruitment:application_detail",
        args=(other_application.pk,),
    ) not in content
    assert application_data["resume"].original_filename not in content
    assert application_data["resume"].file.name not in content
    assert other_resume.original_filename not in content
    assert other_resume.file.name not in content
    assert "Candidate summary" not in content
    assert 'aria-current="page"' in content


def test_recruiter_application_detail_renders_safe_authorized_workspace(
    client, application_data
):
    candidate_user = application_data["candidate_user"]
    candidate_user.first_name = "Ayesha"
    candidate_user.last_name = "Khan"
    candidate_user.save(update_fields=("first_name", "last_name"))
    candidate = application_data["candidate"]
    candidate.city = "Lahore"
    candidate.years_of_experience = 2
    candidate.save(update_fields=("city", "years_of_experience"))
    skill = Skill.objects.create(name="Django")
    CandidateSkill.objects.create(candidate=candidate, skill=skill)
    resume = application_data["resume"]
    resume.original_filename = "ayesha-resume.pdf"
    resume.sha256_checksum = "a" * 64
    resume.extracted_text = "PRIVATE RESUME TEXT"
    resume.save(
        update_fields=("original_filename", "sha256_checksum", "extracted_text")
    )
    policy_version = settings.CURRENT_AI_CONSENT_POLICY_VERSION
    grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=policy_version,
        idempotency_key=uuid.uuid4(),
    )
    application = create_application(
        actor=candidate_user,
        job=application_data["job"],
        resume=resume,
        grant_interview_consent=True,
        policy_version=policy_version,
        consent_idempotency_key=uuid.uuid4(),
    )
    start = timezone.now() + timezone.timedelta(days=2)
    schedule = InterviewSchedule.objects.create(
        application=application,
        scheduled_by=application_data["recruiter_user"],
        scheduled_start=start,
        scheduled_end=start + timezone.timedelta(hours=1),
        status=InterviewSchedule.Status.CONFIRMED,
        confirmed_at=timezone.now(),
        timezone="Asia/Karachi",
    )
    session = CallSession.objects.create(
        schedule=schedule,
        status=CallSession.Status.READY,
        expires_at=schedule.scheduled_end,
    )
    client.force_login(application_data["recruiter_user"])

    response = client.get(
        reverse("recruitment:application_detail", args=(application.pk,))
    )

    assert response.status_code == 200
    assert "recruitment/recruiter_application_list.html" in {
        template.name for template in response.templates
    }
    content = response.content.decode()
    assert "Ayesha Khan" in content
    assert "Candidate summary" in content
    assert "Lahore, PK" in content
    assert "Django" in content
    assert "Email verified" in content
    assert "AI processing consent active" in content
    assert "AI interview consent active" in content
    assert resume.original_filename in content
    assert "View résumé unavailable" in content
    assert reverse("candidates:resume_download", args=(resume.pk,)) not in content
    assert reverse("calling:recruiter_session_detail", args=(session.pk,)) in content
    assert "Application history" in content
    assert 'aria-current="page"' in content
    assert resume.file.name not in content
    assert resume.sha256_checksum not in content
    assert resume.extracted_text not in content


def test_recruiter_application_detail_restricts_review_and_interview_actions(
    client, application_data
):
    application = create_application(
        actor=application_data["candidate_user"],
        job=application_data["job"],
        resume=application_data["resume"],
    )
    detail_url = reverse("recruitment:application_detail", args=(application.pk,))
    client.force_login(application_data["recruiter_user"])

    response = client.get(detail_url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Manage interview unavailable" in content
    assert (
        reverse("interviews:invitation_create", args=(application.pk,)) not in content
    )
    assert reverse(
        "candidates:resume_download", args=(application_data["resume"].pk,)
    ) not in content

    application_data["recruiter"].can_review_candidates = False
    application_data["recruiter"].save(update_fields=("can_review_candidates",))
    assert client.get(detail_url).status_code == 403


def test_candidate_application_list_is_owned_and_shows_safe_interview_actions(
    client, application_data
):
    policy_version = settings.CURRENT_AI_CONSENT_POLICY_VERSION
    grant_general_ai_processing_consent(
        candidate=application_data["candidate"],
        actor=application_data["candidate_user"],
        policy_version=policy_version,
        idempotency_key=uuid.uuid4(),
    )
    application = create_application(
        actor=application_data["candidate_user"],
        job=application_data["job"],
        resume=application_data["resume"],
        grant_interview_consent=True,
        policy_version=policy_version,
        consent_idempotency_key=uuid.uuid4(),
    )
    start = timezone.now() + timezone.timedelta(days=2)
    schedule = InterviewSchedule.objects.create(
        application=application,
        scheduled_by=application_data["recruiter_user"],
        scheduled_start=start,
        scheduled_end=start + timezone.timedelta(hours=1),
        status=InterviewSchedule.Status.CONFIRMED,
        confirmed_at=timezone.now(),
        timezone="Asia/Karachi",
    )
    session = CallSession.objects.create(
        schedule=schedule,
        status=CallSession.Status.READY,
        expires_at=schedule.scheduled_end,
    )

    other_user = User.objects.create_user(
        email="private-other-application@example.com",
        password="TestPassword123!",
        email_verified=True,
    )
    other_candidate = CandidateProfile.objects.get(user=other_user)
    other_resume = Resume.objects.create(
        candidate=other_candidate,
        file="candidate-resumes/private-application.pdf",
        original_filename="private-application.pdf",
        processing_status=Resume.ProcessingStatus.COMPLETED,
        is_active=True,
    )
    other_job = JobPosting.objects.create(
        company=application_data["company"],
        created_by=application_data["recruiter"],
        title="Private Other Candidate Role",
        reference_code="APP-PRIVATE",
        description="Private synthetic role",
        status=JobPosting.Status.OPEN,
    )
    other_application = create_application(
        actor=other_user,
        job=other_job,
        resume=other_resume,
    )
    InterviewSchedule.objects.create(
        application=other_application,
        scheduled_by=application_data["recruiter_user"],
        scheduled_start=start,
        scheduled_end=start + timezone.timedelta(hours=1),
        status=InterviewSchedule.Status.CONFIRMED,
        confirmed_at=timezone.now(),
        timezone="UTC",
    )

    client.force_login(application_data["candidate_user"])
    response = client.get(reverse("recruitment:application_list"))
    content = response.content.decode()
    assert response.status_code == 200
    assert application_data["job"].title in content
    assert application_data["company"].name in content
    assert reverse("recruitment:application_detail", args=(application.pk,)) in content
    assert reverse("calling:candidate_session_detail", args=(session.pk,)) in content
    assert reverse("interviews:reschedule_request", args=(schedule.pk,)) in content
    assert "Email verified" in content
    assert "Resume ready" in content
    assert "Interview consent active" in content
    assert "Private Other Candidate Role" not in content
    assert other_resume.original_filename not in content
    assert other_resume.file.name not in content


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
    CallSession.objects.create(
        schedule=schedule,
        status=CallSession.Status.ACTIVE,
        started_at=timezone.now(),
    )
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

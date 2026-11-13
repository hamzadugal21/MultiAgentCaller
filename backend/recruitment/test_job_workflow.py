import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditEvent
from candidates.models import Skill
from recruitment.administration_services import (
    AdministrationServiceError,
    create_company,
    provision_recruiter,
)
from recruitment.models import (
    Company,
    InterviewQuestion,
    JobApplication,
    JobFAQ,
    JobPosting,
    JobSkillRequirement,
    RecruiterProfile,
)

pytestmark = pytest.mark.django_db


def _admin():
    return User.objects.create_superuser(
        email="jobs-admin@example.com", password="TestPassword123!"
    )


def _recruiter(company, *, email="jobs-recruiter@example.com", verified=True):
    user = User.objects.create_user(
        email=email,
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    profile = RecruiterProfile.objects.create(
        user=user,
        company=company,
        is_verified=verified,
    )
    return user, profile


def _job(company, recruiter, **overrides):
    values = {
        "title": "Platform Engineer",
        "reference_code": "JOB-001",
        "description": "Build reliable systems.",
    }
    values.update(overrides)
    return JobPosting.objects.create(
        company=company, created_by=recruiter, **values
    )


def _job_form_data(**overrides):
    values = {
        "title": "Backend Engineer",
        "reference_code": "BACK-001",
        "description": "Build backend services.",
        "responsibilities": "Develop features.",
        "minimum_qualifications": "Python",
        "preferred_qualifications": "Django",
        "location": "Remote",
        "employment_type": JobPosting.EmploymentType.FULL_TIME,
        "workplace_type": JobPosting.WorkplaceType.REMOTE,
        "minimum_experience_years": 2,
        "maximum_experience_years": 5,
        "salary_currency": "PKR",
    }
    values.update(overrides)
    return values


def test_administrator_services_control_company_and_recruiter_provisioning():
    administrator = _admin()
    company = create_company(actor=administrator, name="Provisioned Company")
    recruiter_user = User.objects.create_user(
        email="provisioned-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    recruiter = provision_recruiter(
        actor=administrator,
        user=recruiter_user,
        company=company,
        is_verified=True,
    )
    assert recruiter.is_verified is True
    assert AuditEvent.objects.filter(event_type="company.created").exists()
    assert AuditEvent.objects.filter(event_type="recruiter.provisioned").exists()
    with pytest.raises(AdministrationServiceError):
        create_company(actor=recruiter_user, name="Unauthorized Company")


def test_verified_recruiter_creates_only_draft_for_own_company(client):
    own_company = Company.objects.create(name="Own Job Company")
    other_company = Company.objects.create(name="Injected Job Company")
    user, recruiter = _recruiter(own_company)
    client.force_login(user)
    response = client.post(
        reverse("recruitment:job_create"),
        _job_form_data(
            company=other_company.pk,
            created_by=999,
            status=JobPosting.Status.OPEN,
        ),
    )
    assert response.status_code == 302
    job = JobPosting.objects.get()
    assert job.company == own_company
    assert job.created_by == recruiter
    assert job.status == JobPosting.Status.DRAFT


def test_unverified_or_incapable_recruiter_cannot_manage_jobs(client):
    company = Company.objects.create(name="Restricted Job Company")
    user, recruiter = _recruiter(company, verified=False)
    client.force_login(user)
    assert client.get(reverse("recruitment:job_list")).status_code == 403
    recruiter.is_verified = True
    recruiter.can_manage_jobs = False
    recruiter.save(update_fields=("is_verified", "can_manage_jobs"))
    assert client.get(reverse("recruitment:job_list")).status_code == 403
    recruiter.can_manage_jobs = True
    recruiter.save(update_fields=("can_manage_jobs",))
    company.is_active = False
    company.save(update_fields=("is_active",))
    assert client.get(reverse("recruitment:job_list")).status_code == 403


def test_recruiter_manage_jobs_screen_is_company_scoped_with_safe_actions(client):
    own_company = Company.objects.create(name="Manage Jobs Company")
    other_company = Company.objects.create(name="Hidden Jobs Company")
    user, recruiter = _recruiter(own_company)
    user.first_name = "Ali"
    user.last_name = "Raza"
    user.save(update_fields=("first_name", "last_name"))
    recruiter.job_title = "Talent Recruiter"
    recruiter.save(update_fields=("job_title",))
    _, other_recruiter = _recruiter(
        other_company,
        email="hidden-manage-jobs-recruiter@example.com",
    )
    published_job = _job(
        own_company,
        recruiter,
        title="Published Company Role",
        reference_code="MANAGE-PUBLISHED",
        status=JobPosting.Status.OPEN,
    )
    draft_job = _job(
        own_company,
        recruiter,
        title="Draft Company Role",
        reference_code="MANAGE-DRAFT",
        status=JobPosting.Status.DRAFT,
    )
    closed_job = _job(
        own_company,
        recruiter,
        title="Closed Company Role",
        reference_code="MANAGE-CLOSED",
        status=JobPosting.Status.CLOSED,
    )
    other_job = _job(
        other_company,
        other_recruiter,
        title="Other Company Confidential Role",
        reference_code="MANAGE-HIDDEN",
        status=JobPosting.Status.OPEN,
    )
    candidate = User.objects.create_user(
        email="manage-jobs-candidate@example.com",
        password="TestPassword123!",
    )
    JobApplication.objects.create(
        job=published_job,
        candidate=candidate.candidate_profile,
    )
    client.force_login(user)

    response = client.get(reverse("recruitment:job_list"))

    assert response.status_code == 200
    assert response.templates[0].name == "recruitment/recruiter_job_list.html"
    assert response.context["published_job_count"] == 1
    assert response.context["draft_job_count"] == 1
    assert response.context["closed_job_count"] == 1
    rendered_jobs = list(response.context["jobs"])
    assert next(
        job for job in rendered_jobs if job.pk == published_job.pk
    ).applicant_count == 1
    content = response.content.decode()
    for title in (
        published_job.title,
        draft_job.title,
        closed_job.title,
    ):
        assert title in content
    assert other_job.title not in content
    assert reverse("recruitment:job_create") in content
    assert reverse("recruitment:job_edit", args=(published_job.pk,)) in content
    assert reverse("recruitment:job_state", args=(published_job.pk,)) in content
    assert '<input type="hidden" name="status" value="open">' in content
    assert '<input type="hidden" name="status" value="closed">' in content
    assert reverse("recruitment:job_edit", args=(other_job.pk,)) not in content
    assert "Search, filtering, sorting, and department data are not available" in content
    assert "Only published jobs are visible to eligible candidates" in content


def test_recruiter_manage_jobs_screen_has_safe_empty_state(client):
    company = Company.objects.create(name="Empty Manage Jobs Company")
    user, _ = _recruiter(company)
    client.force_login(user)

    response = client.get(reverse("recruitment:job_list"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "No jobs have been created yet" in content
    assert reverse("recruitment:job_create") in content


def test_candidate_receives_browse_jobs_not_recruiter_manage_jobs(client):
    candidate = User.objects.create_user(
        email="candidate-not-recruiter@example.com",
        password="TestPassword123!",
    )
    client.force_login(candidate)

    response = client.get(reverse("recruitment:job_list"))

    assert response.status_code == 200
    assert response.templates[0].name == "recruitment/job_list.html"
    assert "Create new job" not in response.content.decode()


def test_recruiter_cannot_access_other_company_job(client):
    company = Company.objects.create(name="Primary Job Company")
    other_company = Company.objects.create(name="Other Job Company")
    user, _ = _recruiter(company)
    _, other_recruiter = _recruiter(
        other_company, email="other-jobs-recruiter@example.com"
    )
    other_job = _job(other_company, other_recruiter)
    client.force_login(user)
    assert (
        client.get(reverse("recruitment:job_edit", args=(other_job.pk,))).status_code
        == 404
    )


def test_job_edit_state_form_keeps_distinct_submitter_status_values(client):
    company = Company.objects.create(name="Job State Form Company")
    user, recruiter = _recruiter(company)
    job = _job(company, recruiter, title="State Form Job")
    client.force_login(user)

    response = client.get(reverse("recruitment:job_edit", args=(job.pk,)))

    assert response.status_code == 200
    content = response.content.decode()
    for status in ("open", "paused", "closed", "archived"):
        assert f'name="status" value="{status}"' in content


def test_recruiter_adds_skill_question_faq_and_publishes(client):
    company = Company.objects.create(name="Configured Job Company")
    user, recruiter = _recruiter(company)
    job = _job(company, recruiter)
    client.force_login(user)
    skill_response = client.post(
        reverse("recruitment:job_skill", args=(job.pk,)),
        {
            "skill_name": "Python",
            "minimum_proficiency": 3,
            "minimum_years": 2,
            "weight": "1.000",
            "is_mandatory": "on",
        },
    )
    question_response = client.post(
        reverse("recruitment:job_question", args=(job.pk,)),
        {
            "question_text": "Describe a reliable service.",
            "question_type": "technical",
            "order": 1,
            "maximum_response_seconds": 120,
            "is_required": "on",
            "is_active": "on",
        },
    )
    faq_response = client.post(
        reverse("recruitment:job_faq", args=(job.pk,)),
        {"question": "Is this remote?", "answer": "Yes.", "is_active": "on"},
    )
    state_response = client.post(
        reverse("recruitment:job_state", args=(job.pk,)), {"status": "open"}
    )
    assert all(
        response.status_code == 302
        for response in (skill_response, question_response, faq_response, state_response)
    )
    assert JobSkillRequirement.objects.filter(job=job).exists()
    assert InterviewQuestion.objects.filter(job=job).exists()
    assert JobFAQ.objects.filter(job=job).exists()
    job.refresh_from_db()
    assert job.status == JobPosting.Status.OPEN


def test_expired_draft_publish_explains_required_deadline_and_preserves_state(client):
    company = Company.objects.create(name="QA Deadline Company")
    user, recruiter = _recruiter(company)
    job = _job(
        company,
        recruiter,
        application_deadline=timezone.now() - timezone.timedelta(days=1),
    )
    client.force_login(user)

    response = client.post(
        reverse("recruitment:job_state", args=(job.pk,)), {"status": "open"}
    )

    assert response.status_code == 302
    assert any(
        "Set a future application deadline" in str(message)
        for message in get_messages(response.wsgi_request)
    )
    job.refresh_from_db()
    assert job.status == JobPosting.Status.DRAFT
    assert not AuditEvent.objects.filter(event_type="job.published", resource_id=str(job.pk)).exists()


def test_candidate_browses_only_open_eligible_jobs(client):
    company = Company.objects.create(name="Browse Job Company")
    inactive_company = Company.objects.create(
        name="Inactive Browse Company",
        is_active=False,
    )
    _, recruiter = _recruiter(company)
    _, inactive_recruiter = _recruiter(
        inactive_company,
        email="inactive-jobs-recruiter@example.com",
    )
    open_job = _job(company, recruiter, status=JobPosting.Status.OPEN)
    _job(
        company,
        recruiter,
        title="Expired",
        reference_code="JOB-EXPIRED",
        status=JobPosting.Status.OPEN,
        application_deadline=timezone.now() - timezone.timedelta(days=1),
    )
    _job(
        company,
        recruiter,
        title="Draft",
        reference_code="JOB-DRAFT",
        status=JobPosting.Status.DRAFT,
    )
    _job(
        inactive_company,
        inactive_recruiter,
        title="Inactive Company Role",
        reference_code="JOB-INACTIVE-COMPANY",
        status=JobPosting.Status.OPEN,
    )
    candidate = User.objects.create_user(
        email="job-browser@example.com", password="TestPassword123!"
    )
    client.force_login(candidate)
    response = client.get(reverse("recruitment:job_list"))
    content = response.content.decode()
    assert response.status_code == 200
    assert open_job.title in content
    assert reverse("recruitment:job_detail", args=(open_job.pk,)) in content
    assert "Expired" not in content
    assert "Draft" not in content
    assert "Inactive Company Role" not in content
    assert "Browse Jobs" in content
    assert 'aria-current="page"' in content
    assert "Search and filters are coming soon. All available jobs are listed below." in content
    assert 'type="search"' in content and 'type="button" disabled>Search' in content
    assert content.count("<select disabled>") >= 4


def test_candidate_job_list_has_safe_empty_state(client):
    candidate = User.objects.create_user(
        email="empty-job-browser@example.com",
        password="TestPassword123!",
    )
    client.force_login(candidate)

    response = client.get(reverse("recruitment:job_list"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "<strong>0</strong> jobs found" in content
    assert "No open jobs are available right now" in content
    assert reverse("candidates:profile_edit") in content


def test_candidate_job_detail_is_scoped_and_links_secure_application(client):
    company = Company.objects.create(
        name="Detail Company",
        description="A safe public company summary.",
    )
    inactive_company = Company.objects.create(
        name="Hidden Detail Company",
        is_active=False,
    )
    _, recruiter = _recruiter(company, email="detail-recruiter@example.com")
    _, inactive_recruiter = _recruiter(
        inactive_company,
        email="hidden-detail-recruiter@example.com",
    )
    open_job = _job(
        company,
        recruiter,
        title="Accessible Engineer",
        reference_code="JOB-DETAIL-OPEN",
        status=JobPosting.Status.OPEN,
        responsibilities="Build accessible interfaces.",
        minimum_qualifications="Experience with semantic HTML.",
    )
    skill = Skill.objects.create(name="Accessibility")
    JobSkillRequirement.objects.create(job=open_job, skill=skill)
    hidden_jobs = (
        _job(
            company,
            recruiter,
            title="Detail Draft",
            reference_code="JOB-DETAIL-DRAFT",
            status=JobPosting.Status.DRAFT,
        ),
        _job(
            company,
            recruiter,
            title="Detail Expired",
            reference_code="JOB-DETAIL-EXPIRED",
            status=JobPosting.Status.OPEN,
            application_deadline=timezone.now() - timezone.timedelta(hours=1),
        ),
        _job(
            inactive_company,
            inactive_recruiter,
            title="Inactive Detail",
            reference_code="JOB-DETAIL-INACTIVE",
            status=JobPosting.Status.OPEN,
        ),
    )
    candidate = User.objects.create_user(
        email="detail-candidate@example.com",
        password="TestPassword123!",
    )
    client.force_login(candidate)

    response = client.get(reverse("recruitment:job_detail", args=(open_job.pk,)))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Accessible Engineer" in content
    assert "A safe public company summary." in content
    assert "Build accessible interfaces." in content
    assert "Experience with semantic HTML." in content
    assert "Accessibility" in content
    assert reverse("recruitment:application_create", args=(open_job.pk,)) in content
    assert "Save job — unavailable" in content
    for hidden_job in hidden_jobs:
        assert (
            client.get(
                reverse("recruitment:job_detail", args=(hidden_job.pk,))
            ).status_code
            == 404
        )


def test_administrator_cannot_access_candidate_job_browser(client):
    client.force_login(_admin())

    assert client.get(reverse("recruitment:job_list")).status_code == 403


def test_anonymous_job_browsing_and_get_state_mutation_are_blocked(client):
    assert client.get(reverse("recruitment:job_list")).status_code == 302
    company = Company.objects.create(name="Method Job Company")
    user, recruiter = _recruiter(company)
    job = _job(company, recruiter)
    client.force_login(user)
    assert client.get(reverse("recruitment:job_state", args=(job.pk,))).status_code == 405

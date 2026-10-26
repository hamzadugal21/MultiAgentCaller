import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditEvent
from recruitment.administration_services import (
    AdministrationServiceError,
    create_company,
    provision_recruiter,
)
from recruitment.models import (
    Company,
    InterviewQuestion,
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


def test_candidate_browses_only_open_eligible_jobs(client):
    company = Company.objects.create(name="Browse Job Company")
    _, recruiter = _recruiter(company)
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
    candidate = User.objects.create_user(
        email="job-browser@example.com", password="TestPassword123!"
    )
    client.force_login(candidate)
    response = client.get(reverse("recruitment:job_list"))
    content = response.content.decode()
    assert response.status_code == 200
    assert open_job.title in content
    assert "Expired" not in content
    assert "Draft" not in content


def test_anonymous_job_browsing_and_get_state_mutation_are_blocked(client):
    assert client.get(reverse("recruitment:job_list")).status_code == 302
    company = Company.objects.create(name="Method Job Company")
    user, recruiter = _recruiter(company)
    job = _job(company, recruiter)
    client.force_login(user)
    assert client.get(reverse("recruitment:job_state", args=(job.pk,))).status_code == 405

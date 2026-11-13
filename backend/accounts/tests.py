import pytest
from django.contrib.auth.hashers import identify_hasher
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditEvent
from interviews.models import InterviewSchedule
from recruitment.models import (
    Company,
    JobApplication,
    JobPosting,
    RecruiterProfile,
)

pytestmark = pytest.mark.django_db


SIGNUP_DATA = {
    "first_name": "Test",
    "last_name": "Candidate",
    "email": "candidate@example.com",
    "password1": "TestingOnly!9384",
    "password2": "TestingOnly!9384",
}


def test_homepage_is_public_and_uses_focused_landing_template(client):
    response = client.get(reverse("accounts:home"))

    assert response.status_code == 200
    assert response.templates[0].name == "accounts/home.html"
    assert b"Hire better with structured recruitment" in response.content
    assert b"Human-reviewed outcomes" in response.content


def test_homepage_links_to_existing_account_and_job_routes(client):
    response = client.get(reverse("accounts:home"))

    content = response.content.decode()
    assert reverse("accounts:login") in content
    assert reverse("accounts:signup") in content
    assert reverse("recruitment:job_list") in content


def test_public_page_includes_the_shared_accessible_loading_boundary(client):
    response = client.get(reverse("accounts:home"))

    content = response.content.decode()
    assert 'data-page-loader' in content
    assert 'accounts/js/loading.js' in content


def test_how_it_works_page_is_public_and_uses_focused_template(client):
    response = client.get(reverse("accounts:how_it_works"))

    assert response.status_code == 200
    assert response.templates[0].name == "accounts/how_it_works.html"
    assert b"Five steps, one connected process" in response.content
    assert b"No automatic hiring decisions" in response.content


def test_how_it_works_page_links_to_existing_public_routes(client):
    response = client.get(reverse("accounts:how_it_works"))

    content = response.content.decode()
    assert reverse("accounts:home") in content
    assert reverse("accounts:login") in content
    assert reverse("accounts:signup") in content
    assert reverse("recruitment:job_list") in content


def test_login_page_uses_focused_figma_template_with_secure_form(client):
    response = client.get(reverse("accounts:login"))

    assert response.status_code == 200
    assert response.templates[0].name == "accounts/login.html"
    content = response.content.decode()
    assert "Your next opportunity" in content
    assert 'name="username"' in content
    assert 'name="password"' in content
    assert "csrfmiddlewaretoken" in content
    assert reverse("accounts:signup") in content


def test_signup_page_is_public(client):
    response = client.get(reverse("accounts:signup"))

    assert response.status_code == 200


def test_signup_page_uses_candidate_only_figma_form(client):
    response = client.get(reverse("accounts:signup"))

    assert response.templates[0].name == "accounts/signup.html"
    content = response.content.decode()
    for field_name in ("first_name", "last_name", "email", "password1", "password2"):
        assert f'name="{field_name}"' in content
    assert 'name="role"' not in content
    assert "csrfmiddlewaretoken" in content
    assert "Public registration creates a candidate account" in content


def test_public_signup_creates_candidate_only(client):
    response = client.post(
        reverse("accounts:signup"),
        {
            **SIGNUP_DATA,
            "role": User.Role.ADMIN,
            "is_staff": True,
            "is_superuser": True,
        },
    )

    assert response.status_code == 302

    user = User.objects.get(email="candidate@example.com")

    assert user.role == User.Role.CANDIDATE
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.is_authenticated is True


def test_signup_password_uses_argon2(client):
    client.post(reverse("accounts:signup"), SIGNUP_DATA)

    user = User.objects.get(email="candidate@example.com")
    hasher = identify_hasher(user.password)

    assert hasher.algorithm == "argon2"
    assert user.check_password("TestingOnly!9384") is True


def test_create_user_stores_complete_email_in_lowercase():
    user = User.objects.create_user(
        email="Mixed.Case@EXAMPLE.COM",
        password="TestingOnly!9384",
    )

    user.refresh_from_db()

    assert user.email == "mixed.case@example.com"


def test_database_rejects_case_variant_email_duplicate():
    User.objects.create_user(
        email="candidate@example.com",
        password="TestingOnly!9384",
    )

    duplicate = User(email="CANDIDATE@EXAMPLE.COM")
    duplicate.set_unusable_password()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            duplicate.save(force_insert=True)

    assert User.objects.count() == 1


def test_duplicate_email_is_rejected_case_insensitively(client):
    User.objects.create_user(
        email="candidate@example.com",
        password="TestingOnly!9384",
    )

    response = client.post(
        reverse("accounts:signup"),
        {
            **SIGNUP_DATA,
            "email": "CANDIDATE@EXAMPLE.COM",
        },
    )

    assert response.status_code == 200
    assert User.objects.count() == 1
    assert "already exists" in response.content.decode().lower()


def test_email_login_redirects_to_correct_dashboard(client):
    User.objects.create_user(
        email="candidate@example.com",
        password="TestingOnly!9384",
    )

    response = client.post(
        reverse("accounts:login"),
        {
            "username": "candidate@example.com",
            "password": "TestingOnly!9384",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("accounts:dashboard")


def test_anonymous_dashboard_access_redirects_to_login(client):
    response = client.get(reverse("accounts:candidate_dashboard"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_candidate_dashboard_uses_real_empty_states(client):
    candidate = User.objects.create_user(
        email="candidate@example.com",
        password="TestingOnly!9384",
        first_name="Ayesha",
        last_name="Khan",
    )
    client.force_login(candidate)

    response = client.get(reverse("accounts:candidate_dashboard"))

    assert response.status_code == 200
    assert response.templates[0].name == "accounts/candidate_dashboard.html"
    content = response.content.decode()
    assert "Welcome back, Ayesha" in content
    assert "No upcoming interviews are scheduled." in content
    assert "No applications yet" in content
    assert "No active resume" in content


def test_candidate_dashboard_displays_scoped_application_and_interview(client):
    company = Company.objects.create(name="NovaTech Solutions")
    recruiter_user = User.objects.create_user(
        email="recruiter@example.com",
        password="TestingOnly!9384",
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
        title="Frontend Developer",
        reference_code="DASHBOARD-001",
        description="A synthetic dashboard test role.",
        status=JobPosting.Status.OPEN,
    )
    candidate = User.objects.create_user(
        email="candidate@example.com",
        password="TestingOnly!9384",
        first_name="Ayesha",
        last_name="Khan",
    )
    application = JobApplication.objects.create(
        job=job,
        candidate=candidate.candidate_profile,
        status=JobApplication.Status.INVITED,
    )
    InterviewSchedule.objects.create(
        application=application,
        scheduled_by=recruiter_user,
        scheduled_start=timezone.now() + timezone.timedelta(days=2),
        scheduled_end=timezone.now() + timezone.timedelta(days=2, hours=1),
        status=InterviewSchedule.Status.CONFIRMED,
    )
    client.force_login(candidate)

    response = client.get(reverse("accounts:candidate_dashboard"))

    assert response.status_code == 200
    assert response.context["active_application_count"] == 1
    assert response.context["upcoming_interview_count"] == 1
    assert b"Frontend Developer" in response.content
    assert b"NovaTech Solutions" in response.content
    assert b"Confirmed" in response.content


def test_recruiter_cannot_access_candidate_dashboard(client):
    recruiter = User.objects.create_user(
        email="recruiter@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
    )
    client.force_login(recruiter)

    response = client.get(reverse("accounts:candidate_dashboard"))

    assert response.status_code == 403


def test_candidate_cannot_access_recruiter_dashboard(client):
    user = User.objects.create_user(
        email="candidate@example.com",
        password="TestingOnly!9384",
    )
    client.force_login(user)

    response = client.get(reverse("accounts:recruiter_dashboard"))

    assert response.status_code == 403


def test_anonymous_recruiter_dashboard_access_redirects_to_login(client):
    response = client.get(reverse("accounts:recruiter_dashboard"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_recruiter_can_access_recruiter_dashboard(client):
    company = Company.objects.create(name="Recruiter Dashboard Company")
    recruiter = User.objects.create_user(
        email="recruiter@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
        first_name="Rina",
    )
    RecruiterProfile.objects.create(
        user=recruiter,
        company=company,
        is_verified=True,
    )
    client.force_login(recruiter)

    response = client.get(reverse("accounts:recruiter_dashboard"))

    assert response.status_code == 200
    assert response.templates[0].name == "accounts/recruiter_dashboard.html"
    content = response.content.decode()
    assert "Good morning, Rina" in content
    assert "No applications to review" in content
    assert "No upcoming interviews" in content
    assert "No active jobs" in content


def test_administrator_cannot_access_recruiter_dashboard(client):
    administrator = User.objects.create_superuser(
        email="administrator@example.com",
        password="TestingOnly!9384",
    )
    client.force_login(administrator)

    response = client.get(reverse("accounts:recruiter_dashboard"))

    assert response.status_code == 403


def test_recruiter_dashboard_denies_recruiter_without_profile(client):
    recruiter = User.objects.create_user(
        email="recruiter@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
    )
    client.force_login(recruiter)

    response = client.get(reverse("accounts:recruiter_dashboard"))

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("is_verified", "company_is_active", "can_manage_jobs", "can_review_candidates"),
    (
        (False, True, True, True),
        (True, False, True, True),
        (True, True, False, False),
    ),
)
def test_recruiter_dashboard_denies_ineligible_recruiters(
    client,
    is_verified,
    company_is_active,
    can_manage_jobs,
    can_review_candidates,
):
    company = Company.objects.create(
        name=f"Eligibility Company {is_verified} {company_is_active} {can_manage_jobs}",
        is_active=company_is_active,
    )
    recruiter = User.objects.create_user(
        email=f"recruiter-{is_verified}-{company_is_active}-{can_manage_jobs}@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
    )
    RecruiterProfile.objects.create(
        user=recruiter,
        company=company,
        is_verified=is_verified,
        can_manage_jobs=can_manage_jobs,
        can_review_candidates=can_review_candidates,
    )
    client.force_login(recruiter)

    response = client.get(reverse("accounts:recruiter_dashboard"))

    assert response.status_code == 403


def test_recruiter_dashboard_is_company_scoped_and_uses_safe_links(client):
    own_company = Company.objects.create(name="Own Company")
    other_company = Company.objects.create(name="Other Company")
    recruiter_user = User.objects.create_user(
        email="recruiter@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
        first_name="Rina",
        last_name="Shah",
    )
    recruiter = RecruiterProfile.objects.create(
        user=recruiter_user,
        company=own_company,
        is_verified=True,
        can_manage_jobs=True,
        can_review_candidates=True,
    )
    other_recruiter_user = User.objects.create_user(
        email="other-recruiter@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
    )
    other_recruiter = RecruiterProfile.objects.create(
        user=other_recruiter_user,
        company=other_company,
        is_verified=True,
    )
    own_job = JobPosting.objects.create(
        company=own_company,
        created_by=recruiter,
        title="Own Company Engineer",
        reference_code="RECRUITER-DASHBOARD-OWN",
        description="Synthetic company-scoped role.",
        status=JobPosting.Status.OPEN,
        published_at=timezone.now(),
    )
    other_job = JobPosting.objects.create(
        company=other_company,
        created_by=other_recruiter,
        title="Other Company Secret Role",
        reference_code="RECRUITER-DASHBOARD-OTHER",
        description="Synthetic out-of-scope role.",
        status=JobPosting.Status.OPEN,
        published_at=timezone.now(),
    )
    own_candidate = User.objects.create_user(
        email="own-candidate@example.com",
        password="TestingOnly!9384",
        first_name="Ayesha",
        last_name="Khan",
    )
    other_candidate = User.objects.create_user(
        email="other-candidate@example.com",
        password="TestingOnly!9384",
        first_name="Other",
        last_name="Candidate",
    )
    own_application = JobApplication.objects.create(
        job=own_job,
        candidate=own_candidate.candidate_profile,
        status=JobApplication.Status.APPLIED,
    )
    other_application = JobApplication.objects.create(
        job=other_job,
        candidate=other_candidate.candidate_profile,
        status=JobApplication.Status.APPLIED,
    )
    InterviewSchedule.objects.create(
        application=own_application,
        scheduled_by=recruiter_user,
        scheduled_start=timezone.now() + timezone.timedelta(days=1),
        scheduled_end=timezone.now() + timezone.timedelta(days=1, hours=1),
        status=InterviewSchedule.Status.CONFIRMED,
    )
    InterviewSchedule.objects.create(
        application=other_application,
        scheduled_by=other_recruiter_user,
        scheduled_start=timezone.now() + timezone.timedelta(days=1),
        scheduled_end=timezone.now() + timezone.timedelta(days=1, hours=1),
        status=InterviewSchedule.Status.CONFIRMED,
    )
    client.force_login(recruiter_user)

    response = client.get(reverse("accounts:recruiter_dashboard"))

    assert response.status_code == 200
    assert response.context["active_job_count"] == 1
    assert response.context["new_application_count"] == 1
    assert response.context["awaiting_review_count"] == 1
    content = response.content.decode()
    assert "Own Company Engineer" in content
    assert "Ayesha Khan" in content
    assert "Other Company Secret Role" not in content
    assert "Other Candidate" not in content
    assert "other-candidate@example.com" not in content
    assert reverse("recruitment:job_create") in content
    assert reverse("recruitment:job_detail", args=[own_job.id]) in content
    assert reverse("recruitment:job_edit", args=[own_job.id]) in content
    assert reverse(
        "recruitment:application_detail",
        args=[own_application.id],
    ) in content
    assert reverse("calling:recruiter_session_list") in content


def test_administrator_can_access_administrator_dashboard(client):
    administrator = User.objects.create_superuser(
        email="administrator@example.com",
        password="TestingOnly!9384",
    )
    client.force_login(administrator)

    response = client.get(reverse("accounts:admin_dashboard"))

    assert response.status_code == 200
    assert response.templates[0].name == "accounts/admin_dashboard.html"
    content = response.content.decode()
    assert "No companies yet" in content
    assert "No recruiter access records" in content
    assert "No platform activity yet" in content
    assert reverse("admin:recruitment_company_add") in content
    assert reverse("admin:accounts_user_add") in content


def test_active_superuser_can_access_agent_demo(client):
    user = User.objects.create_superuser(
        email="qa-agent-demo-superuser@example.test",
        password="TestingOnly!9384",
    )
    client.force_login(user)

    response = client.get(reverse("accounts:agent_demo"))

    assert response.status_code == 200
    assert b"AI Agent Demonstration" in response.content

    management_response = client.get(
        f'{reverse("accounts:admin_dashboard")}?section=management'
    )
    assert management_response.status_code == 200
    assert management_response.templates[0].name == "accounts/admin_management.html"
    management_content = management_response.content.decode()
    assert "No companies yet" in management_content
    assert "No recruiter profiles yet" in management_content
    assert reverse("admin:recruitment_company_add") in management_content
    assert reverse("admin:accounts_user_add") in management_content


def test_anonymous_administrator_dashboard_redirects_to_login(client):
    for url in (
        reverse("accounts:admin_dashboard"),
        f'{reverse("accounts:admin_dashboard")}?section=management',
    ):
        response = client.get(url)

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url


@pytest.mark.parametrize("role", (User.Role.CANDIDATE, User.Role.RECRUITER))
def test_non_administrator_roles_cannot_access_administrator_dashboard(client, role):
    user = User.objects.create_user(
        email=f"{role}@example.com",
        password="TestingOnly!9384",
        role=role,
    )
    client.force_login(user)

    for url in (
        reverse("accounts:admin_dashboard"),
        f'{reverse("accounts:admin_dashboard")}?section=management',
    ):
        response = client.get(url)

        assert response.status_code == 403


def test_administrator_dashboard_renders_safe_persisted_platform_data(client):
    administrator = User.objects.create_superuser(
        email="administrator@example.com",
        password="TestingOnly!9384",
        first_name="System",
        last_name="Administrator",
    )
    company = Company.objects.create(name="Safe Platform Company")
    Company.objects.create(name="Inactive Platform Company", is_active=False)
    recruiter_user = User.objects.create_user(
        email="verified-recruiter@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
        first_name="Rina",
        last_name="Shah",
    )
    recruiter = RecruiterProfile.objects.create(
        user=recruiter_user,
        company=company,
        is_verified=True,
    )
    pending_recruiter_user = User.objects.create_user(
        email="pending-recruiter@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
        first_name="Pending",
        last_name="Recruiter",
    )
    RecruiterProfile.objects.create(
        user=pending_recruiter_user,
        company=company,
        is_verified=False,
    )
    job = JobPosting.objects.create(
        company=company,
        created_by=recruiter,
        title="Platform Engineer",
        reference_code="ADMIN-DASHBOARD-JOB",
        description="Synthetic dashboard test role.",
        status=JobPosting.Status.OPEN,
        published_at=timezone.now(),
    )
    candidate = User.objects.create_user(
        email="candidate@example.com",
        password="TestingOnly!9384",
    )
    application = JobApplication.objects.create(
        job=job,
        candidate=candidate.candidate_profile,
    )
    InterviewSchedule.objects.create(
        application=application,
        scheduled_by=recruiter_user,
        scheduled_start=timezone.now() + timezone.timedelta(hours=2),
        scheduled_end=timezone.now() + timezone.timedelta(hours=3),
        status=InterviewSchedule.Status.CONFIRMED,
    )
    AuditEvent.objects.create(
        actor=administrator,
        category=AuditEvent.Category.ADMINISTRATION,
        event_type="company.created",
        action="Private caller-controlled audit prose",
        outcome=AuditEvent.Outcome.SUCCESS,
        severity=AuditEvent.Severity.INFO,
        resource_type="recruitment.Company",
        resource_id=company.id,
        description="Private audit description must not render",
        metadata={"private_note": "Private audit metadata must not render"},
    )
    client.force_login(administrator)

    response = client.get(reverse("accounts:admin_dashboard"))

    assert response.status_code == 200
    assert response.context["active_company_count"] == 1
    assert response.context["verified_recruiter_count"] == 1
    assert response.context["published_job_count"] == 1
    assert response.context["interviews_this_week_count"] == 1
    content = response.content.decode()
    assert "Safe Platform Company" in content
    assert "Rina Shah" in content
    assert "Pending verification" in content
    assert "Company created" in content
    assert "Private caller-controlled audit prose" not in content
    assert "Private audit description must not render" not in content
    assert "Private audit metadata must not render" not in content
    assert "verified-recruiter@example.com" not in content
    assert "pending-recruiter@example.com" not in content
    assert reverse("admin:recruitment_company_add") in content
    assert reverse("admin:accounts_user_add") in content
    assert reverse(
        "admin:recruitment_recruiterprofile_change",
        args=[recruiter.id],
    ) in content

    management_response = client.get(
        f'{reverse("accounts:admin_dashboard")}?section=management'
    )
    assert management_response.status_code == 200
    assert management_response.templates[0].name == "accounts/admin_management.html"
    management_content = management_response.content.decode()
    assert "Safe Platform Company" in management_content
    assert "Inactive Platform Company" in management_content
    assert "1 recruiter" not in management_content
    assert "2 recruiters" in management_content
    assert "1 job" in management_content
    assert "Active" in management_content
    assert "Inactive" in management_content
    assert "Rina Shah" in management_content
    assert "Pending Recruiter" in management_content
    assert "Verified" in management_content
    assert "Pending verification" in management_content
    assert "verified-recruiter@example.com" not in management_content
    assert "pending-recruiter@example.com" not in management_content
    assert "Private audit metadata must not render" not in management_content
    assert reverse(
        "admin:recruitment_company_change",
        args=[company.id],
    ) in management_content
    assert reverse(
        "admin:recruitment_recruiterprofile_change",
        args=[recruiter.id],
    ) in management_content


def test_logout_requires_post(client):
    user = User.objects.create_user(
        email="candidate@example.com",
        password="TestingOnly!9384",
    )
    client.force_login(user)

    get_response = client.get(reverse("accounts:logout"))
    assert get_response.status_code == 405

    post_response = client.post(reverse("accounts:logout"))
    assert post_response.status_code == 302

    protected_response = client.get(reverse("accounts:candidate_dashboard"))
    assert protected_response.status_code == 302


def test_superuser_is_forced_to_administrator_role():
    user = User.objects.create_superuser(
        email="administrator@example.com",
        password="TestingOnly!9384",
        role=User.Role.CANDIDATE,
    )

    assert user.role == User.Role.ADMIN
    assert user.is_staff is True
    assert user.is_superuser is True


def test_admin_can_block_and_unblock_user_with_audit(client):
    admin_user = User.objects.create_superuser(email="admin-controls@example.com", password="TestingOnly!9384")
    target = User.objects.create_user(email="qa-block-target@example.com", password="TestingOnly!9384")
    client.force_login(admin_user)

    response = client.post(reverse("admin:accounts_user_block", args=[target.pk]))
    target.refresh_from_db()
    assert response.status_code == 302
    assert target.is_active is False
    assert AuditEvent.objects.filter(event_type="account.blocked").exists()

    response = client.post(reverse("admin:accounts_user_unblock", args=[target.pk]))
    target.refresh_from_db()
    assert response.status_code == 302
    assert target.is_active is True
    assert AuditEvent.objects.filter(event_type="account.unblocked").exists()


def test_admin_cannot_block_self_or_other_roles_cannot_use_controls(client):
    admin_user = User.objects.create_superuser(email="admin-self@example.com", password="TestingOnly!9384")
    client.force_login(admin_user)
    response = client.post(reverse("admin:accounts_user_block", args=[admin_user.pk]))
    assert response.status_code == 302
    admin_user.refresh_from_db()
    assert admin_user.is_active is True

    candidate = User.objects.create_user(email="qa-non-admin@example.com", password="TestingOnly!9384")
    client.force_login(candidate)
    response = client.post(reverse("admin:accounts_user_block", args=[admin_user.pk]))
    assert response.status_code in (302, 403)


def test_admin_unlocks_shared_axes_login_attempts_with_explicit_confirmation(client):
    from axes.models import AccessAttempt

    admin_user = User.objects.create_superuser(email="admin-unlock@example.com", password="TestingOnly!9384")
    target = User.objects.create_user(email="qa-unlock-target@example.com", password="TestingOnly!9384")
    AccessAttempt.objects.create(username=None, ip_address="127.0.0.1", failures_since_start=5)
    client.force_login(admin_user)

    response = client.post(reverse("admin:accounts_user_unlock_login", args=[target.pk]), {"confirm_shared": "yes"})

    assert response.status_code == 302
    assert not AccessAttempt.objects.filter(ip_address="127.0.0.1").exists()
    assert AuditEvent.objects.filter(event_type="account.login_attempts_unlocked").exists()

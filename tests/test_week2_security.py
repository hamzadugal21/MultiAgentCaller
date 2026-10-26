import uuid

import pytest
from django.test import Client
from django.urls import reverse

from accounts.models import User
from auditlog.models import ConsentRecord
from recruitment.models import Company, JobPosting, RecruiterProfile

pytestmark = pytest.mark.django_db


def test_csrf_is_required_for_consent_mutation():
    user = User.objects.create_user(
        email="csrf-candidate@example.com", password="TestPassword123!"
    )
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    assert (
        csrf_client.post(
            reverse("candidates:general_consent"), {"action": "grant"}
        ).status_code
        == 403
    )
    page = csrf_client.get(reverse("accounts:candidate_dashboard"))
    token = page.cookies["csrftoken"].value
    response = csrf_client.post(
        reverse("candidates:general_consent"),
        {"action": "grant", "csrfmiddlewaretoken": token},
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 302
    assert ConsentRecord.objects.filter(candidate=user.candidate_profile).exists()


def test_templates_escape_untrusted_job_content(client):
    company = Company.objects.create(name="Escaping Company")
    recruiter_user = User.objects.create_user(
        email="escaping-recruiter@example.com",
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
        title="<script>alert(1)</script>",
        reference_code=f"ESC-{uuid.uuid4().hex[:8]}",
        description="<img src=x onerror=alert(1)>",
        status=JobPosting.Status.OPEN,
    )
    candidate = User.objects.create_user(
        email="escaping-candidate@example.com", password="TestPassword123!"
    )
    client.force_login(candidate)
    response = client.get(reverse("recruitment:job_detail", args=(job.pk,)))
    content = response.content.decode()
    assert "<script>" not in content
    assert "&lt;script&gt;" in content
    assert "<img" not in content
    assert "&lt;img" in content

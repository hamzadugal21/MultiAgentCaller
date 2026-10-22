import pytest
from django.contrib.auth.hashers import identify_hasher
from django.db import IntegrityError, transaction
from django.urls import reverse

from accounts.models import User

pytestmark = pytest.mark.django_db


SIGNUP_DATA = {
    "first_name": "Test",
    "last_name": "Candidate",
    "email": "candidate@example.com",
    "password1": "TestingOnly!9384",
    "password2": "TestingOnly!9384",
}


def test_signup_page_is_public(client):
    response = client.get(reverse("accounts:signup"))

    assert response.status_code == 200


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


def test_candidate_cannot_access_recruiter_dashboard(client):
    user = User.objects.create_user(
        email="candidate@example.com",
        password="TestingOnly!9384",
    )
    client.force_login(user)

    response = client.get(reverse("accounts:recruiter_dashboard"))

    assert response.status_code == 403


def test_recruiter_can_access_recruiter_dashboard(client):
    recruiter = User.objects.create_user(
        email="recruiter@example.com",
        password="TestingOnly!9384",
        role=User.Role.RECRUITER,
    )
    client.force_login(recruiter)

    response = client.get(reverse("accounts:recruiter_dashboard"))

    assert response.status_code == 200


def test_administrator_can_access_administrator_dashboard(client):
    administrator = User.objects.create_superuser(
        email="administrator@example.com",
        password="TestingOnly!9384",
    )
    client.force_login(administrator)

    response = client.get(reverse("accounts:admin_dashboard"))

    assert response.status_code == 200


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

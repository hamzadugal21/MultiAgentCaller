import re

import pytest
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from accounts.email_verification_services import create_email_verification_challenge
from accounts.models import User

pytestmark = pytest.mark.django_db


@override_settings(
    MAILERS={
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
    }
)
def test_candidate_can_request_verification_without_token_in_response(client):
    user = User.objects.create_user(
        email="verification-view@example.com", password="TestPassword123!"
    )
    client.force_login(user)
    response = client.post(reverse("accounts:email_verification_request"))
    assert response.status_code == 302
    assert len(mail.outbox) == 1
    token = re.search(r"/email/verify/(.+)/", mail.outbox[0].body).group(1)
    assert token.encode() not in response.content


def test_confirmation_requires_post_and_marks_email_verified(client, settings):
    settings.EMAIL_VERIFICATION_INVALID_ATTEMPT_LIMIT = 50
    user = User.objects.create_user(
        email="verification-confirm@example.com", password="TestPassword123!"
    )
    issued = create_email_verification_challenge(user=user)
    url = reverse("accounts:email_verification_confirm", args=(issued.token,))
    get_response = client.get(url)
    assert get_response.status_code == 200
    user.refresh_from_db()
    assert user.email_verified is False
    post_response = client.post(url)
    assert post_response.status_code == 200
    user.refresh_from_db()
    assert user.email_verified is True


def test_verification_request_is_candidate_only(client):
    recruiter = User.objects.create_user(
        email="verification-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    client.force_login(recruiter)
    assert client.post(reverse("accounts:email_verification_request")).status_code == 403

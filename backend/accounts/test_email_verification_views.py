import pytest
from django.urls import resolve
from django.urls.exceptions import Resolver404

from accounts.models import User

pytestmark = pytest.mark.django_db


def test_candidate_email_verification_routes_are_unavailable(client):
    for path in ("/email/verify/request/", "/email/verify/unused-token/"):
        with pytest.raises(Resolver404):
            resolve(path)
        assert client.post(path).status_code == 404


def test_unverified_candidate_has_no_verification_prompt(client):
    user = User.objects.create_user(
        email="verification-view@example.com", password="TestPassword123!"
    )
    client.force_login(user)
    response = client.get("/dashboard/candidate/")
    assert response.status_code == 200
    assert b"/email/verify/" not in response.content

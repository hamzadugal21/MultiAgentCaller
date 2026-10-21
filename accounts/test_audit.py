import json
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from accounts.models import User
from auditlog.models import AuditEvent
from candidates.models import CandidateProfile

pytestmark = pytest.mark.django_db


PASSWORD = "TestingOnly!9384"


def create_audit_event(**overrides):
    values = {
        "category": AuditEvent.Category.SYSTEM,
        "event_type": "test.event",
        "action": "Test action",
        "outcome": AuditEvent.Outcome.SUCCESS,
        "severity": AuditEvent.Severity.INFO,
    }
    values.update(overrides)

    return AuditEvent.objects.create(**values)


def test_candidate_profile_is_created_automatically():
    candidate = User.objects.create_user(
        email="profile-candidate@example.com",
        password=PASSWORD,
        role=User.Role.CANDIDATE,
    )

    assert CandidateProfile.objects.filter(user=candidate).exists()


def test_recruiter_does_not_receive_candidate_profile():
    recruiter = User.objects.create_user(
        email="profile-recruiter@example.com",
        password=PASSWORD,
        role=User.Role.RECRUITER,
    )

    assert not CandidateProfile.objects.filter(user=recruiter).exists()


def test_successful_login_creates_audit_event(client):
    user = User.objects.create_user(
        email="login-audit@example.com",
        password=PASSWORD,
    )

    response = client.post(
        reverse("accounts:login"),
        {
            "username": "login-audit@example.com",
            "password": PASSWORD,
        },
        HTTP_USER_AGENT="Audit Test Browser",
        REMOTE_ADDR="127.0.0.1",
    )

    assert response.status_code == 302

    event = AuditEvent.objects.get(
        event_type="user.login.success",
    )

    assert event.actor == user
    assert event.actor_email_snapshot == user.email
    assert event.outcome == AuditEvent.Outcome.SUCCESS
    assert event.ip_address_hash
    assert event.ip_address_hash != "127.0.0.1"
    assert event.user_agent_summary == "Audit Test Browser"
    assert len(event.event_hash) == 64


def test_failed_login_creates_sanitized_audit_event(client):
    User.objects.create_user(
        email="failed-login@example.com",
        password=PASSWORD,
    )

    response = client.post(
        reverse("accounts:login"),
        {
            "username": "failed-login@example.com",
            "password": "IncorrectPassword!123",
        },
        REMOTE_ADDR="127.0.0.1",
    )

    assert response.status_code == 200

    event = AuditEvent.objects.get(
        event_type="user.login.failure",
    )

    serialized_metadata = json.dumps(event.metadata)

    assert event.actor is None
    assert event.outcome == AuditEvent.Outcome.FAILURE
    assert event.metadata["identifier_hash"]
    assert "failed-login@example.com" not in serialized_metadata
    assert "IncorrectPassword" not in serialized_metadata


def test_logout_creates_audit_event(client):
    user = User.objects.create_user(
        email="logout-audit@example.com",
        password=PASSWORD,
    )
    client.force_login(user)

    response = client.post(reverse("accounts:logout"))

    assert response.status_code == 302
    assert AuditEvent.objects.filter(
        actor=user,
        event_type="user.logout",
    ).exists()


def test_audit_event_cannot_be_modified_or_deleted():
    event = create_audit_event()

    event.description = "Attempted modification"

    with pytest.raises(ValidationError):
        event.save()

    with pytest.raises(ValidationError):
        event.delete()


def test_audit_hash_covers_private_request_metadata():
    event = AuditEvent(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        category=AuditEvent.Category.SECURITY,
        event_type="security.test",
        action="Test security event",
        outcome=AuditEvent.Outcome.WARNING,
        severity=AuditEvent.Severity.MEDIUM,
        ip_address_hash="first-ip-hash",
        user_agent_summary="First browser",
    )

    first_hash = event.build_event_hash()

    event.ip_address_hash = "second-ip-hash"
    second_hash = event.build_event_hash()

    event.ip_address_hash = "first-ip-hash"
    event.user_agent_summary = "Second browser"
    third_hash = event.build_event_hash()

    assert first_hash != second_hash
    assert first_hash != third_hash

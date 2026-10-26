import hashlib
import json
import uuid
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.utils import timezone

from accounts import email_verification_services
from accounts.email_verification_services import (
    GENERIC_REQUEST_ERROR,
    GENERIC_VERIFICATION_ERROR,
    EmailVerificationRateLimitError,
    EmailVerificationValidationError,
    create_email_verification_challenge,
    invalidate_email_verification_after_email_change,
    resend_email_verification_challenge,
    verify_email_verification_token,
)
from accounts.models import EmailVerificationChallenge, User
from auditlog.models import AuditEvent

pytestmark = pytest.mark.django_db

ATTEMPT_KEY = "a" * 64


@pytest.fixture(autouse=True)
def clear_rate_limit_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user():
    return User.objects.create_user(
        email="verify-candidate@example.com",
        password=None,
        role=User.Role.CANDIDATE,
    )


def test_challenge_creation_stores_only_keyed_digests(user):
    request_id = uuid.uuid4()
    issued = create_email_verification_challenge(
        user=user,
        request_id=request_id,
    )
    challenge = issued.challenge
    plain_email_digest = hashlib.sha256(user.email.encode()).hexdigest()
    plain_token_digest = hashlib.sha256(issued.token.encode()).hexdigest()

    assert challenge.user == user
    assert challenge.purpose_version == "email-verification-v1"
    assert challenge.request_id == request_id
    assert challenge.used_at is None
    assert challenge.invalidated_at is None
    assert challenge.expires_at > challenge.created_at
    assert challenge.token_digest != issued.token
    assert challenge.token_digest != plain_token_digest
    assert challenge.email_hmac != user.email
    assert challenge.email_hmac != plain_email_digest
    assert len(challenge.token_digest) == 64
    assert len(challenge.email_hmac) == 64
    assert issued.token not in json.dumps(
        {
            "token_digest": challenge.token_digest,
            "email_hmac": challenge.email_hmac,
            "purpose": challenge.purpose_version,
        }
    )


def test_creation_records_privacy_safe_deterministic_audit_event(user):
    issued = create_email_verification_challenge(user=user)
    event = AuditEvent.objects.get(event_type="email_verification.requested")

    assert event.resource_type == "accounts.EmailVerificationChallenge"
    assert event.resource_id == str(issued.challenge.id)
    assert event.actor == user
    assert event.metadata == {
        "delivery_channel": "email",
        "request_kind": "initial",
    }
    serialized = json.dumps(event.metadata)
    assert user.email not in serialized
    assert issued.token not in serialized


def test_valid_token_is_consumed_once_and_verifies_current_email(user):
    issued = create_email_verification_challenge(user=user)

    verified_user = verify_email_verification_token(
        token=issued.token,
        attempt_key=ATTEMPT_KEY,
    )

    issued.challenge.refresh_from_db()
    user.refresh_from_db()
    assert verified_user.pk == user.pk
    assert user.email_verified is True
    assert issued.challenge.used_at is not None
    assert AuditEvent.objects.filter(
        event_type="email_verification.succeeded",
        resource_id=str(issued.challenge.id),
    ).exists()

    with pytest.raises(
        EmailVerificationValidationError,
        match=GENERIC_VERIFICATION_ERROR,
    ):
        verify_email_verification_token(
            token=issued.token,
            attempt_key=ATTEMPT_KEY,
        )


def test_resend_invalidates_prior_active_challenge(user):
    first = create_email_verification_challenge(user=user)
    second = resend_email_verification_challenge(user=user)
    first.challenge.refresh_from_db()

    assert first.challenge.invalidated_at is not None
    assert second.challenge.id != first.challenge.id
    assert second.token != first.token
    assert AuditEvent.objects.filter(
        event_type="email_verification.invalidated",
        resource_id=str(first.challenge.id),
        metadata={"reason_code": "resend"},
    ).exists()

    with pytest.raises(EmailVerificationValidationError):
        verify_email_verification_token(
            token=first.token,
            attempt_key=ATTEMPT_KEY,
        )

    verified = verify_email_verification_token(
        token=second.token,
        attempt_key="b" * 64,
    )
    assert verified.pk == user.pk


def test_email_change_breaks_binding_and_invalidates_challenge(user):
    issued = create_email_verification_challenge(user=user)
    User.objects.filter(pk=user.pk).update(email="changed@example.com")

    with pytest.raises(
        EmailVerificationValidationError,
        match=GENERIC_VERIFICATION_ERROR,
    ):
        verify_email_verification_token(
            token=issued.token,
            attempt_key=ATTEMPT_KEY,
        )

    issued.challenge.refresh_from_db()
    user.refresh_from_db()
    assert issued.challenge.invalidated_at is not None
    assert user.email_verified is False
    assert AuditEvent.objects.filter(
        event_type="email_verification.failed",
        metadata={"failure_code": "email_changed"},
    ).exists()


def test_email_change_service_invalidates_active_challenges_and_cache(user):
    first = create_email_verification_challenge(user=user)
    second = create_email_verification_challenge(user=user)
    User.objects.filter(pk=user.pk).update(email_verified=True)
    user.refresh_from_db()

    invalidate_email_verification_after_email_change(user=user)

    first.challenge.refresh_from_db()
    second.challenge.refresh_from_db()
    user.refresh_from_db()
    assert first.challenge.invalidated_at is not None
    assert second.challenge.invalidated_at is not None
    assert user.email_verified is False


def test_expired_and_invalid_tokens_return_same_generic_error(user):
    issued = create_email_verification_challenge(user=user)
    historical_created_at = timezone.now() - timedelta(days=2)
    EmailVerificationChallenge.objects.filter(pk=issued.challenge.pk).update(
        created_at=historical_created_at,
        expires_at=historical_created_at + timedelta(days=1),
    )

    errors = []
    for token, key in ((issued.token, "c" * 64), ("invalid-token", "d" * 64)):
        with pytest.raises(EmailVerificationValidationError) as error:
            verify_email_verification_token(
                token=token,
                attempt_key=key,
            )
        errors.append(str(error.value))

    assert errors == [GENERIC_VERIFICATION_ERROR, GENERIC_VERIFICATION_ERROR]


def test_invalid_attempt_audit_contains_no_token(user):
    token = "private-invalid-token"

    with pytest.raises(EmailVerificationValidationError):
        verify_email_verification_token(
            token=token,
            attempt_key=ATTEMPT_KEY,
        )

    event = AuditEvent.objects.get(event_type="email_verification.failed")
    assert event.resource_id == ""
    assert event.metadata == {"failure_code": "invalid_token"}
    assert token not in json.dumps(event.metadata)


@override_settings(
    EMAIL_VERIFICATION_REQUEST_LIMIT=1,
    EMAIL_VERIFICATION_REQUEST_WINDOW_SECONDS=60,
)
def test_challenge_requests_are_rate_limited(user):
    create_email_verification_challenge(user=user)

    with pytest.raises(EmailVerificationRateLimitError, match=GENERIC_REQUEST_ERROR):
        create_email_verification_challenge(user=user)


@override_settings(
    EMAIL_VERIFICATION_RESEND_LIMIT=1,
    EMAIL_VERIFICATION_RESEND_WINDOW_SECONDS=60,
)
def test_resends_are_rate_limited(user):
    create_email_verification_challenge(user=user)
    resend_email_verification_challenge(user=user)

    with pytest.raises(EmailVerificationRateLimitError, match=GENERIC_REQUEST_ERROR):
        resend_email_verification_challenge(user=user)


@override_settings(
    EMAIL_VERIFICATION_INVALID_ATTEMPT_LIMIT=1,
    EMAIL_VERIFICATION_INVALID_ATTEMPT_WINDOW_SECONDS=60,
)
def test_invalid_token_attempts_are_rate_limited(user):
    with pytest.raises(EmailVerificationValidationError):
        verify_email_verification_token(
            token="first-invalid-token",
            attempt_key=ATTEMPT_KEY,
        )

    with pytest.raises(
        EmailVerificationRateLimitError,
        match=GENERIC_VERIFICATION_ERROR,
    ):
        verify_email_verification_token(
            token="second-invalid-token",
            attempt_key=ATTEMPT_KEY,
        )


def test_creation_audit_failure_rolls_back_challenge(user, monkeypatch):
    def fail_audit(command):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(
        email_verification_services,
        "record_domain_event",
        fail_audit,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        create_email_verification_challenge(user=user)

    assert not EmailVerificationChallenge.objects.filter(user=user).exists()


def test_success_audit_failure_rolls_back_consumption(user, monkeypatch):
    issued = create_email_verification_challenge(user=user)
    original_audit = email_verification_services.record_domain_event

    def fail_success(command):
        if command.event_type == "email_verification.succeeded":
            raise RuntimeError("audit unavailable")
        return original_audit(command)

    monkeypatch.setattr(
        email_verification_services,
        "record_domain_event",
        fail_success,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        verify_email_verification_token(
            token=issued.token,
            attempt_key=ATTEMPT_KEY,
        )

    issued.challenge.refresh_from_db()
    user.refresh_from_db()
    assert issued.challenge.used_at is None
    assert user.email_verified is False


def test_expiry_and_terminal_state_database_constraints(user):
    now = timezone.now()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmailVerificationChallenge.objects.create(
                user=user,
                token_digest="a" * 64,
                email_hmac="b" * 64,
                created_at=now,
                expires_at=now,
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmailVerificationChallenge.objects.create(
                user=user,
                token_digest="c" * 64,
                email_hmac="d" * 64,
                expires_at=now + timedelta(hours=1),
                used_at=now,
                invalidated_at=now,
            )

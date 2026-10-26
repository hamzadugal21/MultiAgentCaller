import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from auditlog.models import AuditEvent
from auditlog.services import AuditCommand, record_domain_event

from .models import EmailVerificationChallenge, User

SIGNING_SALT = "accounts.email-verification.token.v1"
TOKEN_DIGEST_SALT = "accounts.email-verification.digest.v1"
EMAIL_BINDING_SALT = "accounts.email-verification.email.v1"
RATE_LIMIT_SALT = "accounts.email-verification.rate-limit.v1"
GENERIC_VERIFICATION_ERROR = "Email verification could not be completed."
GENERIC_REQUEST_ERROR = "Email verification request could not be completed."


class EmailVerificationError(Exception):
    """Base exception for safe email-verification failures."""


class EmailVerificationValidationError(EmailVerificationError):
    """Raised when an email-verification operation is not permitted."""


class EmailVerificationRateLimitError(EmailVerificationError):
    """Raised when a configured verification attempt limit is exceeded."""


@dataclass(frozen=True, slots=True)
class IssuedEmailVerification:
    challenge: EmailVerificationChallenge
    token: str


def _hmac(*, salt, value):
    return salted_hmac(
        salt,
        str(value),
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()


def _normalized_email(email):
    return User.objects.normalize_email(email).strip().lower()


def _token_digest(token):
    return _hmac(salt=TOKEN_DIGEST_SALT, value=token)


def _email_hmac(email):
    return _hmac(salt=EMAIL_BINDING_SALT, value=_normalized_email(email))


def _request_uuid(request_id):
    if request_id is None or request_id == "":
        return None
    try:
        return request_id if isinstance(request_id, uuid.UUID) else uuid.UUID(str(request_id))
    except (AttributeError, TypeError, ValueError) as error:
        raise EmailVerificationValidationError(GENERIC_REQUEST_ERROR) from error


def _persisted_active_user(user):
    user_id = getattr(user, "pk", None)
    if user_id is None:
        raise EmailVerificationValidationError(GENERIC_REQUEST_ERROR)
    try:
        return User.objects.select_for_update().get(pk=user_id, is_active=True)
    except (TypeError, ValueError, User.DoesNotExist) as error:
        raise EmailVerificationValidationError(GENERIC_REQUEST_ERROR) from error


def _rate_limit(*, scope, identifier, limit, window_seconds, error_message):
    if limit < 1 or window_seconds < 1:
        raise EmailVerificationRateLimitError(error_message)
    identifier_digest = _hmac(salt=RATE_LIMIT_SALT, value=identifier)
    key = f"email-verification:{scope}:{identifier_digest}"
    if cache.add(key, 1, timeout=window_seconds):
        return
    try:
        attempts = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_seconds)
        attempts = 1
    if attempts > limit:
        raise EmailVerificationRateLimitError(error_message)


def _audit_requested(challenge, *, request_kind):
    record_domain_event(
        AuditCommand(
            category=AuditEvent.Category.AUTHENTICATION,
            event_type="email_verification.requested",
            outcome=AuditEvent.Outcome.SUCCESS,
            severity=AuditEvent.Severity.INFO,
            resource_type="accounts.EmailVerificationChallenge",
            resource_id=challenge.id,
            actor=challenge.user,
            request_id=challenge.request_id,
            metadata={
                "delivery_channel": "email",
                "request_kind": request_kind,
            },
        )
    )


def _audit_invalidated(challenge, *, reason_code):
    record_domain_event(
        AuditCommand(
            category=AuditEvent.Category.AUTHENTICATION,
            event_type="email_verification.invalidated",
            outcome=AuditEvent.Outcome.SUCCESS,
            severity=AuditEvent.Severity.INFO,
            resource_type="accounts.EmailVerificationChallenge",
            resource_id=challenge.id,
            actor=challenge.user,
            request_id=challenge.request_id,
            metadata={"reason_code": reason_code},
        )
    )


def _audit_succeeded(challenge, *, request_id):
    record_domain_event(
        AuditCommand(
            category=AuditEvent.Category.AUTHENTICATION,
            event_type="email_verification.succeeded",
            outcome=AuditEvent.Outcome.SUCCESS,
            severity=AuditEvent.Severity.INFO,
            resource_type="accounts.EmailVerificationChallenge",
            resource_id=challenge.id,
            actor=challenge.user,
            request_id=request_id,
        )
    )


def _audit_failed(*, challenge, failure_code, request_id):
    record_domain_event(
        AuditCommand(
            category=AuditEvent.Category.SECURITY,
            event_type="email_verification.failed",
            outcome=AuditEvent.Outcome.FAILURE,
            severity=AuditEvent.Severity.LOW,
            resource_type="accounts.EmailVerificationChallenge",
            resource_id=challenge.id if challenge is not None else None,
            actor=None,
            request_id=request_id,
            metadata={"failure_code": failure_code},
        )
    )


def _build_token(*, challenge_id):
    payload = {
        "challenge_id": str(challenge_id),
        "nonce": secrets.token_urlsafe(32),
        "purpose": EmailVerificationChallenge.PURPOSE_VERSION,
    }
    return signing.dumps(payload, salt=SIGNING_SALT, compress=False)


def _create_challenge(*, user, request_id, request_kind):
    now = timezone.now()
    challenge_id = uuid.uuid4()
    token = _build_token(challenge_id=challenge_id)
    challenge = EmailVerificationChallenge.objects.create(
        id=challenge_id,
        user=user,
        token_digest=_token_digest(token),
        email_hmac=_email_hmac(user.email),
        expires_at=now
        + timedelta(seconds=settings.EMAIL_VERIFICATION_LIFETIME_SECONDS),
        request_id=request_id,
    )
    _audit_requested(challenge, request_kind=request_kind)
    return IssuedEmailVerification(challenge=challenge, token=token)


def create_email_verification_challenge(*, user, request_id=None):
    request_id = _request_uuid(request_id)
    with transaction.atomic():
        persisted_user = _persisted_active_user(user)
        if persisted_user.email_verified:
            raise EmailVerificationValidationError(GENERIC_REQUEST_ERROR)
        _rate_limit(
            scope="request",
            identifier=persisted_user.pk,
            limit=settings.EMAIL_VERIFICATION_REQUEST_LIMIT,
            window_seconds=settings.EMAIL_VERIFICATION_REQUEST_WINDOW_SECONDS,
            error_message=GENERIC_REQUEST_ERROR,
        )
        return _create_challenge(
            user=persisted_user,
            request_id=request_id,
            request_kind="initial",
        )


def _active_challenges(user):
    now = timezone.now()
    return list(
        EmailVerificationChallenge.objects.select_for_update()
        .filter(
            user=user,
            used_at__isnull=True,
            invalidated_at__isnull=True,
            expires_at__gt=now,
        )
        .order_by("created_at", "id")
    )


def _invalidate_challenges(challenges, *, reason_code, invalidated_at):
    for challenge in challenges:
        challenge.invalidated_at = invalidated_at
        challenge.save(update_fields=("invalidated_at",))
        _audit_invalidated(challenge, reason_code=reason_code)


def resend_email_verification_challenge(*, user, request_id=None):
    request_id = _request_uuid(request_id)
    with transaction.atomic():
        persisted_user = _persisted_active_user(user)
        if persisted_user.email_verified:
            raise EmailVerificationValidationError(GENERIC_REQUEST_ERROR)
        _rate_limit(
            scope="resend",
            identifier=persisted_user.pk,
            limit=settings.EMAIL_VERIFICATION_RESEND_LIMIT,
            window_seconds=settings.EMAIL_VERIFICATION_RESEND_WINDOW_SECONDS,
            error_message=GENERIC_REQUEST_ERROR,
        )
        _invalidate_challenges(
            _active_challenges(persisted_user),
            reason_code="resend",
            invalidated_at=timezone.now(),
        )
        return _create_challenge(
            user=persisted_user,
            request_id=request_id,
            request_kind="resend",
        )


def invalidate_email_verification_after_email_change(*, user):
    with transaction.atomic():
        persisted_user = _persisted_active_user(user)
        _invalidate_challenges(
            _active_challenges(persisted_user),
            reason_code="email_changed",
            invalidated_at=timezone.now(),
        )
        if persisted_user.email_verified:
            persisted_user.email_verified = False
            persisted_user.save(update_fields=("email_verified",))


def _validated_attempt_key(attempt_key):
    if (
        not isinstance(attempt_key, str)
        or len(attempt_key) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in attempt_key)
    ):
        raise EmailVerificationValidationError(GENERIC_VERIFICATION_ERROR)
    return attempt_key.lower()


def _token_payload(token):
    try:
        payload = signing.loads(
            token,
            salt=SIGNING_SALT,
            max_age=settings.EMAIL_VERIFICATION_LIFETIME_SECONDS,
        )
    except signing.SignatureExpired:
        return None, "expired"
    except (signing.BadSignature, TypeError, ValueError):
        return None, "invalid_token"
    if not isinstance(payload, dict):
        return None, "invalid_token"
    try:
        challenge_id = uuid.UUID(str(payload.get("challenge_id")))
    except (TypeError, ValueError):
        return None, "invalid_token"
    if (
        payload.get("purpose") != EmailVerificationChallenge.PURPOSE_VERSION
        or not isinstance(payload.get("nonce"), str)
        or len(payload["nonce"]) < 32
    ):
        return None, "invalid_token"
    return challenge_id, None


def verify_email_verification_token(
    *,
    token,
    attempt_key,
    request_id=None,
):
    request_id = _request_uuid(request_id)
    attempt_key = _validated_attempt_key(attempt_key)
    _rate_limit(
        scope="invalid-attempt",
        identifier=attempt_key,
        limit=settings.EMAIL_VERIFICATION_INVALID_ATTEMPT_LIMIT,
        window_seconds=settings.EMAIL_VERIFICATION_INVALID_ATTEMPT_WINDOW_SECONDS,
        error_message=GENERIC_VERIFICATION_ERROR,
    )

    challenge_id, token_error = _token_payload(token)
    if token_error is not None:
        _audit_failed(
            challenge=None,
            failure_code=token_error,
            request_id=request_id,
        )
        raise EmailVerificationValidationError(GENERIC_VERIFICATION_ERROR)

    digest = _token_digest(token)
    failure_code = None
    challenge = None
    with transaction.atomic():
        challenge = (
            EmailVerificationChallenge.objects.select_for_update()
            .select_related("user")
            .filter(token_digest=digest)
            .first()
        )
        if challenge is None or challenge.id != challenge_id:
            failure_code = "invalid_token"
        elif challenge.purpose_version != EmailVerificationChallenge.PURPOSE_VERSION:
            failure_code = "invalid_purpose"
        elif challenge.used_at is not None:
            failure_code = "already_used"
        elif challenge.invalidated_at is not None:
            failure_code = "invalidated"
        elif challenge.expires_at <= timezone.now():
            failure_code = "expired"
        elif not challenge.user.is_active:
            failure_code = "inactive_user"
        elif not constant_time_compare(
            challenge.email_hmac,
            _email_hmac(challenge.user.email),
        ):
            challenge.invalidated_at = timezone.now()
            challenge.save(update_fields=("invalidated_at",))
            _audit_invalidated(challenge, reason_code="email_changed")
            failure_code = "email_changed"
        else:
            now = timezone.now()
            challenge.used_at = now
            challenge.save(update_fields=("used_at",))
            if not challenge.user.email_verified:
                challenge.user.email_verified = True
                challenge.user.save(update_fields=("email_verified",))
            _audit_succeeded(challenge, request_id=request_id)
            return challenge.user

    _audit_failed(
        challenge=challenge,
        failure_code=failure_code,
        request_id=request_id,
    )
    raise EmailVerificationValidationError(GENERIC_VERIFICATION_ERROR)

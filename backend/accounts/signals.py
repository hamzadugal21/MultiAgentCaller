import hashlib
import hmac
import logging

from django.conf import settings
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models.signals import post_save
from django.dispatch import receiver

from auditlog.models import AuditEvent
from candidates.models import CandidateProfile

from .models import User

logger = logging.getLogger(__name__)


def hash_private_value(value):
    """Create a non-reversible keyed hash for private identifiers."""
    if not value:
        return ""

    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        str(value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def get_request_metadata(request):
    """Collect privacy-safe request information."""
    if request is None:
        return {
            "ip_address_hash": "",
            "user_agent_summary": "",
            "request_id": None,
        }

    ip_address = request.META.get("REMOTE_ADDR", "")
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    return {
        "ip_address_hash": hash_private_value(ip_address),
        "user_agent_summary": user_agent[:255],
        "request_id": getattr(request, "request_id", None),
    }


def get_valid_actor(user):
    """Return a database user or None, never AnonymousUser."""
    if (
        user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "pk", None)
    ):
        return user

    return None


def write_authentication_audit_event(
    *,
    request,
    event_type,
    action,
    outcome,
    severity,
    actor=None,
    metadata=None,
):
    """Write a sanitized authentication event without blocking login."""
    request_metadata = get_request_metadata(request)
    actor = get_valid_actor(actor)

    try:
        AuditEvent.objects.create(
            actor=actor,
            category=AuditEvent.Category.AUTHENTICATION,
            event_type=event_type,
            action=action,
            outcome=outcome,
            severity=severity,
            resource_type="accounts.User",
            resource_id=str(actor.pk) if actor else "",
            request_id=request_metadata["request_id"],
            ip_address_hash=request_metadata["ip_address_hash"],
            user_agent_summary=request_metadata["user_agent_summary"],
            metadata=metadata or {},
        )
    except Exception:
        logger.exception("Authentication audit event could not be recorded.")


@receiver(
    post_save,
    sender=User,
    dispatch_uid="accounts.ensure_candidate_profile",
)
def ensure_candidate_profile(sender, instance, **kwargs):
    """Ensure every candidate has exactly one candidate profile."""
    if instance.role == User.Role.CANDIDATE:
        CandidateProfile.objects.get_or_create(user=instance)


@receiver(
    user_logged_in,
    dispatch_uid="accounts.audit_successful_login",
)
def record_successful_login(sender, request, user, **kwargs):
    write_authentication_audit_event(
        request=request,
        event_type="user.login.success",
        action="User logged in",
        outcome=AuditEvent.Outcome.SUCCESS,
        severity=AuditEvent.Severity.INFO,
        actor=user,
    )


@receiver(
    user_logged_out,
    dispatch_uid="accounts.audit_logout",
)
def record_logout(sender, request, user, **kwargs):
    write_authentication_audit_event(
        request=request,
        event_type="user.logout",
        action="User logged out",
        outcome=AuditEvent.Outcome.SUCCESS,
        severity=AuditEvent.Severity.INFO,
        actor=user,
    )


@receiver(
    user_login_failed,
    dispatch_uid="accounts.audit_failed_login",
)
def record_failed_login(sender, credentials, request, **kwargs):
    supplied_identifier = credentials.get("username") or credentials.get("email") or ""

    write_authentication_audit_event(
        request=request,
        event_type="user.login.failure",
        action="Login attempt failed",
        outcome=AuditEvent.Outcome.FAILURE,
        severity=AuditEvent.Severity.MEDIUM,
        metadata={
            "identifier_hash": hash_private_value(supplied_identifier.strip().lower()),
        },
    )

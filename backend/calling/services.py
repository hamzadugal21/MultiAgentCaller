import uuid
from types import MappingProxyType

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from auditlog.consent_services import (
    has_effective_application_ai_interview_consent,
    has_effective_general_ai_processing_consent,
)
from auditlog.models import AuditEvent
from auditlog.services import SAFE_CODE_PATTERN, AuditCommand, record_domain_event
from calling.models import CallSession
from interviews.models import InterviewSchedule
from recruitment.models import JobApplication, RecruiterProfile


class CallSessionServiceError(Exception):
    """Base exception for safe call-session failures."""


class CallSessionAuthorizationError(CallSessionServiceError):
    """Raised when an actor cannot access or change a call session."""


class CallSessionTransitionError(CallSessionServiceError):
    """Raised when a call-session lifecycle transition is not allowed."""


CALL_SESSION_TRANSITIONS = MappingProxyType(
    {
        CallSession.Status.PENDING: frozenset(
            {
                CallSession.Status.READY,
                CallSession.Status.CANCELLED,
                CallSession.Status.EXPIRED,
                CallSession.Status.FAILED,
            }
        ),
        CallSession.Status.READY: frozenset(
            {
                CallSession.Status.ACTIVE,
                CallSession.Status.CANCELLED,
                CallSession.Status.EXPIRED,
                CallSession.Status.FAILED,
            }
        ),
        CallSession.Status.ACTIVE: frozenset(
            {
                CallSession.Status.PAUSED,
                CallSession.Status.COMPLETED,
                CallSession.Status.CANCELLED,
                CallSession.Status.EXPIRED,
                CallSession.Status.FAILED,
            }
        ),
        CallSession.Status.PAUSED: frozenset(
            {
                CallSession.Status.ACTIVE,
                CallSession.Status.COMPLETED,
                CallSession.Status.CANCELLED,
                CallSession.Status.EXPIRED,
                CallSession.Status.FAILED,
            }
        ),
        CallSession.Status.COMPLETED: frozenset(),
        CallSession.Status.CANCELLED: frozenset(),
        CallSession.Status.EXPIRED: frozenset(),
        CallSession.Status.FAILED: frozenset(),
    }
)

TERMINAL_STATUSES = frozenset(
    {
        CallSession.Status.COMPLETED,
        CallSession.Status.CANCELLED,
        CallSession.Status.EXPIRED,
        CallSession.Status.FAILED,
    }
)


def _required_uuid(value, name):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise CallSessionServiceError(f"A valid {name} is required.") from error


def _safe_code(value, name):
    if not isinstance(value, str) or not SAFE_CODE_PATTERN.fullmatch(value):
        raise CallSessionServiceError(f"A valid {name} is required.")
    return value


def _persisted_actor(actor):
    actor_id = getattr(actor, "pk", None)
    try:
        return User.objects.get(pk=actor_id, is_active=True)
    except (TypeError, ValueError, User.DoesNotExist) as error:
        raise CallSessionAuthorizationError("The actor is not authorized.") from error


def _authorize_actor(actor, *, application, candidate_only=False):
    actor = _persisted_actor(actor)
    if actor.role == User.Role.CANDIDATE:
        if actor.pk != application.candidate.user_id:
            raise CallSessionAuthorizationError("The actor is not authorized.")
        return actor
    if candidate_only:
        raise CallSessionAuthorizationError("The actor is not authorized.")
    if actor.is_superuser or actor.role == User.Role.ADMIN:
        return actor
    if actor.role != User.Role.RECRUITER:
        raise CallSessionAuthorizationError("The actor is not authorized.")
    try:
        recruiter = RecruiterProfile.objects.get(user=actor)
    except RecruiterProfile.DoesNotExist as error:
        raise CallSessionAuthorizationError("The actor is not authorized.") from error
    if (
        not recruiter.is_verified
        or not recruiter.can_review_candidates
        or recruiter.company_id != application.job.company_id
    ):
        raise CallSessionAuthorizationError("The actor is not authorized.")
    return actor


def _eligible_schedule(schedule, *, policy_version, now):
    application = schedule.application
    if (
        schedule.status != InterviewSchedule.Status.CONFIRMED
        or not schedule.is_current
        or schedule.confirmed_at is None
        or schedule.invitation_expires_at is None
        or schedule.confirmed_at > schedule.invitation_expires_at
        or schedule.scheduled_end <= now
        or application.status != JobApplication.Status.INVITED
        or not application.candidate.user.email_verified
    ):
        raise CallSessionServiceError("The interview is not eligible for a call session.")
    if not has_effective_general_ai_processing_consent(
        candidate=application.candidate,
        policy_version=policy_version,
    ) or not has_effective_application_ai_interview_consent(
        application=application,
        policy_version=policy_version,
    ):
        raise CallSessionServiceError("Current candidate consent is required.")
    return application


def _session_queryset():
    return CallSession.objects.select_related(
        "schedule__application__candidate__user",
        "schedule__application__job__company",
    )


def get_call_session_for_actor(*, session, actor):
    try:
        persisted = _session_queryset().get(pk=session.pk)
    except (AttributeError, CallSession.DoesNotExist) as error:
        raise CallSessionServiceError("The call session is not available.") from error
    _authorize_actor(actor, application=persisted.schedule.application)
    return persisted


def create_call_session(
    *,
    schedule,
    actor=None,
    idempotency_key,
    policy_version=None,
    simulated_mode=True,
    request_id=None,
    correlation_id=None,
):
    idempotency_key = _required_uuid(idempotency_key, "idempotency key")
    if simulated_mode is not True:
        raise CallSessionServiceError("Only simulated call sessions are available.")
    policy_version = policy_version or settings.CURRENT_AI_CONSENT_POLICY_VERSION
    with transaction.atomic():
        try:
            schedule = (
                InterviewSchedule.objects.select_for_update()
                .select_related("application__candidate__user", "application__job__company")
                .get(pk=schedule.pk)
            )
        except (AttributeError, InterviewSchedule.DoesNotExist) as error:
            raise CallSessionServiceError("The interview is not available.") from error
        application = _eligible_schedule(
            schedule,
            policy_version=policy_version,
            now=timezone.now(),
        )
        persisted_actor = (
            _authorize_actor(actor, application=application) if actor is not None else None
        )

        existing = _session_queryset().filter(
            creation_idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            if existing.schedule_id != schedule.pk or not existing.simulated_mode:
                raise CallSessionServiceError(
                    "The idempotency key was used for another call session."
                )
            return existing
        if CallSession.objects.filter(schedule=schedule).exists():
            raise CallSessionServiceError("A call session already exists for this interview.")

        session = CallSession.objects.create(
            schedule=schedule,
            creation_idempotency_key=idempotency_key,
            expires_at=schedule.scheduled_end,
            simulated_mode=True,
            candidate_consent=True,
            consent_recorded_at=timezone.now(),
            recording_enabled=False,
            recording_file=None,
        )
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.INTERVIEW,
                event_type="call_session.created",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="calling.CallSession",
                resource_id=session.pk,
                actor=persisted_actor,
                request_id=request_id,
                correlation_id=correlation_id,
                metadata={
                    "application_id": application.pk,
                    "interview_schedule_id": schedule.pk,
                    "simulated_mode": True,
                    "status_to": CallSession.Status.PENDING,
                },
            )
        )
        return session


def transition_call_session(
    *,
    session,
    target_status,
    actor=None,
    reason_code=None,
    failure_code=None,
    policy_version=None,
    request_id=None,
    correlation_id=None,
):
    policy_version = policy_version or settings.CURRENT_AI_CONSENT_POLICY_VERSION
    with transaction.atomic():
        try:
            locked = (
                _session_queryset()
                .select_for_update()
                .get(pk=session.pk)
            )
        except (AttributeError, CallSession.DoesNotExist) as error:
            raise CallSessionTransitionError("The call session is not available.") from error

        if target_status == locked.status:
            return locked
        if target_status not in CALL_SESSION_TRANSITIONS.get(
            locked.status, frozenset()
        ):
            raise CallSessionTransitionError(
                "The call-session transition is not allowed."
            )

        now = timezone.now()
        application = locked.schedule.application
        if target_status in {CallSession.Status.READY, CallSession.Status.ACTIVE}:
            _eligible_schedule(
                locked.schedule,
                policy_version=policy_version,
                now=now,
            )
        if target_status == CallSession.Status.READY:
            if actor is not None:
                raise CallSessionAuthorizationError(
                    "Readiness is a system transition."
                )
            persisted_actor = None
        elif target_status == CallSession.Status.ACTIVE:
            persisted_actor = _authorize_actor(
                actor,
                application=application,
                candidate_only=True,
            )
            if locked.status == CallSession.Status.READY and not (
                locked.schedule.scheduled_start <= now < locked.expires_at
            ):
                raise CallSessionTransitionError(
                    "The call session cannot start outside its scheduled window."
                )
        elif target_status in {CallSession.Status.PAUSED, CallSession.Status.COMPLETED}:
            persisted_actor = _authorize_actor(
                actor,
                application=application,
                candidate_only=True,
            )
        elif target_status == CallSession.Status.CANCELLED:
            persisted_actor = _authorize_actor(actor, application=application)
        else:
            if actor is not None:
                raise CallSessionAuthorizationError(
                    "This is a system transition."
                )
            persisted_actor = None

        status_from = locked.status
        event_type = {
            CallSession.Status.READY: "call_session.ready",
            CallSession.Status.PAUSED: "call_session.paused",
            CallSession.Status.COMPLETED: "call_session.completed",
            CallSession.Status.CANCELLED: "call_session.cancelled",
            CallSession.Status.EXPIRED: "call_session.expired",
            CallSession.Status.FAILED: "call_session.failed",
        }.get(target_status)
        if target_status == CallSession.Status.ACTIVE:
            event_type = (
                "call_session.resumed"
                if status_from == CallSession.Status.PAUSED
                else "call_session.started"
            )

        metadata = {
            "application_id": application.pk,
            "interview_schedule_id": locked.schedule_id,
            "status_from": status_from,
            "status_to": target_status,
        }
        if target_status in {CallSession.Status.COMPLETED, CallSession.Status.CANCELLED}:
            reason_code = _safe_code(reason_code, "reason code")
            locked.completion_reason = reason_code
            metadata["reason_code"] = reason_code
        elif target_status == CallSession.Status.EXPIRED:
            locked.completion_reason = "session_expired"
            metadata["reason_code"] = "session_expired"
        elif target_status == CallSession.Status.FAILED:
            failure_code = _safe_code(failure_code, "failure code")
            locked.failure_code = failure_code
            metadata["failure_code"] = failure_code

        locked.status = target_status
        locked.last_activity_at = now
        if target_status == CallSession.Status.ACTIVE and locked.started_at is None:
            locked.started_at = now
        if target_status in TERMINAL_STATUSES:
            locked.ended_at = now
            if locked.started_at is not None:
                locked.duration_seconds = max(
                    0,
                    int((locked.ended_at - locked.started_at).total_seconds()),
                )
        locked.save()
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.INTERVIEW,
                event_type=event_type,
                outcome=(
                    AuditEvent.Outcome.FAILURE
                    if target_status == CallSession.Status.FAILED
                    else AuditEvent.Outcome.SUCCESS
                ),
                severity=(
                    AuditEvent.Severity.MEDIUM
                    if target_status == CallSession.Status.FAILED
                    else AuditEvent.Severity.INFO
                ),
                resource_type="calling.CallSession",
                resource_id=locked.pk,
                actor=persisted_actor,
                request_id=request_id,
                correlation_id=correlation_id,
                metadata=metadata,
            )
        )
        return locked

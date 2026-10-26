from types import MappingProxyType

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditEvent
from auditlog.services import SAFE_CODE_PATTERN, AuditCommand, record_domain_event
from interviews.models import InterviewSchedule
from recruitment.models import RecruiterProfile


class InterviewTransitionError(Exception):
    """Base exception for safe interview workflow failures."""


class InterviewAuthorizationError(InterviewTransitionError):
    """Raised when an actor cannot transition an interview."""


INTERVIEW_TRANSITIONS = MappingProxyType(
    {
        InterviewSchedule.Status.PENDING: frozenset(
            {
                InterviewSchedule.Status.CONFIRMED,
                InterviewSchedule.Status.RESCHEDULED,
                InterviewSchedule.Status.CANCELLED,
                InterviewSchedule.Status.EXPIRED,
            }
        ),
        InterviewSchedule.Status.CONFIRMED: frozenset(
            {
                InterviewSchedule.Status.RESCHEDULED,
                InterviewSchedule.Status.COMPLETED,
                InterviewSchedule.Status.CANCELLED,
            }
        ),
        InterviewSchedule.Status.RESCHEDULED: frozenset(),
        InterviewSchedule.Status.COMPLETED: frozenset(),
        InterviewSchedule.Status.CANCELLED: frozenset(),
        InterviewSchedule.Status.EXPIRED: frozenset(),
    }
)


def _persisted_actor(actor):
    actor_id = getattr(actor, "pk", None)
    try:
        return User.objects.get(pk=actor_id, is_active=True)
    except (TypeError, ValueError, User.DoesNotExist) as error:
        raise InterviewAuthorizationError("An authorized actor is required.") from error


def _authorize_candidate(actor, schedule):
    actor = _persisted_actor(actor)
    if (
        actor.role != User.Role.CANDIDATE
        or actor.pk != schedule.application.candidate.user_id
    ):
        raise InterviewAuthorizationError("The actor is not authorized.")
    return actor


def _authorize_recruiter(actor, schedule):
    actor = _persisted_actor(actor)
    if actor.is_superuser or actor.role == User.Role.ADMIN:
        return actor
    if actor.role != User.Role.RECRUITER:
        raise InterviewAuthorizationError("The actor is not authorized.")
    try:
        recruiter = RecruiterProfile.objects.get(user=actor)
    except RecruiterProfile.DoesNotExist as error:
        raise InterviewAuthorizationError("The actor is not authorized.") from error
    if (
        not recruiter.is_verified
        or not recruiter.can_review_candidates
        or recruiter.company_id != schedule.application.job.company_id
    ):
        raise InterviewAuthorizationError("The actor is not authorized.")
    return actor


def transition_interview(
    *,
    schedule,
    target_status,
    actor=None,
    replacement_schedule=None,
    reason_code=None,
    request_id=None,
    correlation_id=None,
):
    with transaction.atomic():
        try:
            locked = (
                InterviewSchedule.objects.select_for_update()
                .select_related("application__candidate__user", "application__job")
                .get(pk=schedule.pk)
            )
        except (AttributeError, InterviewSchedule.DoesNotExist) as error:
            raise InterviewTransitionError("A valid interview is required.") from error
        if target_status not in INTERVIEW_TRANSITIONS.get(
            locked.status, frozenset()
        ):
            raise InterviewTransitionError("The interview transition is not allowed.")

        if target_status == InterviewSchedule.Status.CONFIRMED:
            persisted_actor = _authorize_candidate(actor, locked)
        elif target_status == InterviewSchedule.Status.EXPIRED:
            if actor is not None:
                raise InterviewAuthorizationError(
                    "Expiration is a system transition."
                )
            persisted_actor = None
        else:
            persisted_actor = _authorize_recruiter(actor, locked)

        status_from = locked.status
        metadata = {
            "application_id": locked.application_id,
            "status_from": status_from,
            "status_to": target_status,
        }
        event_type = {
            InterviewSchedule.Status.CONFIRMED: "interview.confirmed",
            InterviewSchedule.Status.COMPLETED: "interview.completed",
            InterviewSchedule.Status.CANCELLED: "interview.cancelled",
            InterviewSchedule.Status.EXPIRED: "interview.expired",
            InterviewSchedule.Status.RESCHEDULED: "interview.rescheduled",
        }[target_status]

        if target_status == InterviewSchedule.Status.CONFIRMED:
            locked.confirmed_at = timezone.now()
        if target_status == InterviewSchedule.Status.CANCELLED:
            if not isinstance(reason_code, str) or not SAFE_CODE_PATTERN.fullmatch(
                reason_code
            ):
                raise InterviewTransitionError("A valid reason code is required.")
            locked.cancellation_reason = reason_code
            metadata["reason_code"] = reason_code
        if target_status == InterviewSchedule.Status.RESCHEDULED:
            try:
                replacement = InterviewSchedule.objects.select_for_update().get(
                    pk=replacement_schedule.pk
                )
            except (AttributeError, InterviewSchedule.DoesNotExist) as error:
                raise InterviewTransitionError(
                    "A valid replacement schedule is required."
                ) from error
            if (
                replacement.pk == locked.pk
                or replacement.application_id != locked.application_id
                or replacement.status != InterviewSchedule.Status.PENDING
            ):
                raise InterviewTransitionError(
                    "A valid replacement schedule is required."
                )
            metadata["replacement_schedule_id"] = replacement.pk

        locked.status = target_status
        if target_status in {
            InterviewSchedule.Status.RESCHEDULED,
            InterviewSchedule.Status.COMPLETED,
            InterviewSchedule.Status.CANCELLED,
            InterviewSchedule.Status.EXPIRED,
        }:
            locked.is_current = False
        locked.save()
        if target_status == InterviewSchedule.Status.RESCHEDULED:
            replacement.is_current = True
            replacement.save(update_fields=("is_current",))
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.INTERVIEW,
                event_type=event_type,
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="interviews.InterviewSchedule",
                resource_id=locked.pk,
                actor=persisted_actor,
                request_id=request_id,
                correlation_id=correlation_id,
                metadata=metadata,
            )
        )
        return locked


def cancel_interview_for_application_withdrawal(*, schedule, actor):
    with transaction.atomic():
        try:
            locked = (
                InterviewSchedule.objects.select_for_update()
                .select_related("application__candidate__user")
                .get(pk=schedule.pk, is_current=True)
            )
        except (AttributeError, InterviewSchedule.DoesNotExist) as error:
            raise InterviewTransitionError("A valid interview is required.") from error
        persisted_actor = _authorize_candidate(actor, locked)
        if locked.status not in {
            InterviewSchedule.Status.PENDING,
            InterviewSchedule.Status.CONFIRMED,
        }:
            raise InterviewTransitionError("The interview transition is not allowed.")
        status_from = locked.status
        locked.status = InterviewSchedule.Status.CANCELLED
        locked.is_current = False
        locked.cancellation_reason = "application_withdrawn"
        locked.save(update_fields=("status", "is_current", "cancellation_reason", "updated_at"))
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.INTERVIEW,
                event_type="interview.cancelled",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="interviews.InterviewSchedule",
                resource_id=locked.pk,
                actor=persisted_actor,
                metadata={
                    "application_id": locked.application_id,
                    "reason_code": "application_withdrawn",
                    "status_from": status_from,
                    "status_to": InterviewSchedule.Status.CANCELLED,
                },
            )
        )
        return locked

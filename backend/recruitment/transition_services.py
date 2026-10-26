from types import MappingProxyType

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditEvent
from auditlog.services import AuditCommand, record_domain_event
from recruitment.models import JobApplication, JobPosting, RecruiterProfile


class WorkflowTransitionError(Exception):
    """Base exception for safe recruitment workflow failures."""


class WorkflowAuthorizationError(WorkflowTransitionError):
    """Raised when an actor cannot perform a workflow transition."""


class InvalidWorkflowTransitionError(WorkflowTransitionError):
    """Raised when a requested state change is not allowed."""


JOB_TRANSITIONS = MappingProxyType(
    {
        JobPosting.Status.DRAFT: frozenset(
            {JobPosting.Status.OPEN, JobPosting.Status.ARCHIVED}
        ),
        JobPosting.Status.OPEN: frozenset(
            {JobPosting.Status.PAUSED, JobPosting.Status.CLOSED}
        ),
        JobPosting.Status.PAUSED: frozenset(
            {
                JobPosting.Status.OPEN,
                JobPosting.Status.CLOSED,
                JobPosting.Status.ARCHIVED,
            }
        ),
        JobPosting.Status.CLOSED: frozenset(
            {JobPosting.Status.OPEN, JobPosting.Status.ARCHIVED}
        ),
        JobPosting.Status.ARCHIVED: frozenset(),
    }
)

APPLICATION_TRANSITIONS = MappingProxyType(
    {
        JobApplication.Status.APPLIED: frozenset(
            {JobApplication.Status.SCREENING, JobApplication.Status.WITHDRAWN}
        ),
        JobApplication.Status.SCREENING: frozenset(
            {
                JobApplication.Status.INVITED,
                JobApplication.Status.REJECTED,
                JobApplication.Status.WITHDRAWN,
            }
        ),
        JobApplication.Status.INVITED: frozenset(
            {JobApplication.Status.INTERVIEWED, JobApplication.Status.WITHDRAWN}
        ),
        JobApplication.Status.INTERVIEWED: frozenset(
            {JobApplication.Status.SHORTLISTED, JobApplication.Status.REJECTED}
        ),
        JobApplication.Status.SHORTLISTED: frozenset(
            {JobApplication.Status.REJECTED}
        ),
        JobApplication.Status.REJECTED: frozenset(),
        JobApplication.Status.WITHDRAWN: frozenset(),
    }
)

JOB_AUDIT_EVENTS = MappingProxyType(
    {
        JobPosting.Status.OPEN: {
            JobPosting.Status.DRAFT: "job.published",
            JobPosting.Status.PAUSED: "job.reopened",
            JobPosting.Status.CLOSED: "job.reopened",
        },
        JobPosting.Status.PAUSED: {JobPosting.Status.OPEN: "job.paused"},
        JobPosting.Status.CLOSED: {
            JobPosting.Status.OPEN: "job.closed",
            JobPosting.Status.PAUSED: "job.closed",
        },
        JobPosting.Status.ARCHIVED: {
            JobPosting.Status.DRAFT: "job.archived",
            JobPosting.Status.PAUSED: "job.archived",
            JobPosting.Status.CLOSED: "job.archived",
        },
    }
)


def _persisted_actor(actor):
    actor_id = getattr(actor, "pk", None)
    try:
        return User.objects.get(pk=actor_id, is_active=True)
    except (TypeError, ValueError, User.DoesNotExist) as error:
        raise WorkflowAuthorizationError("An authorized actor is required.") from error


def _authorize_recruiter(actor, *, company_id, capability):
    actor = _persisted_actor(actor)
    if actor.is_superuser or actor.role == User.Role.ADMIN:
        return actor
    if actor.role != User.Role.RECRUITER:
        raise WorkflowAuthorizationError("The actor is not authorized.")
    try:
        recruiter = RecruiterProfile.objects.get(user=actor)
    except RecruiterProfile.DoesNotExist as error:
        raise WorkflowAuthorizationError("The actor is not authorized.") from error
    if (
        not recruiter.is_verified
        or recruiter.company_id != company_id
        or not getattr(recruiter, capability)
    ):
        raise WorkflowAuthorizationError("The actor is not authorized.")
    return actor


def transition_job(*, job, target_status, actor, request_id=None, correlation_id=None):
    with transaction.atomic():
        try:
            locked = JobPosting.objects.select_for_update().get(pk=job.pk)
        except (AttributeError, JobPosting.DoesNotExist) as error:
            raise InvalidWorkflowTransitionError("A valid job is required.") from error
        actor = _authorize_recruiter(
            actor,
            company_id=locked.company_id,
            capability="can_manage_jobs",
        )
        if target_status not in JOB_TRANSITIONS.get(locked.status, frozenset()):
            raise InvalidWorkflowTransitionError("The job transition is not allowed.")
        if target_status == JobPosting.Status.OPEN:
            if not locked.company.is_active:
                raise InvalidWorkflowTransitionError("The job cannot be published.")
            if locked.created_by.company_id != locked.company_id:
                raise InvalidWorkflowTransitionError("The job cannot be published.")
            if locked.application_deadline and locked.application_deadline <= timezone.now():
                raise InvalidWorkflowTransitionError("The job cannot be published.")

        status_from = locked.status
        locked.status = target_status
        update_fields = ["status", "updated_at"]
        if target_status == JobPosting.Status.OPEN:
            locked.published_at = timezone.now()
            locked.closed_at = None
            update_fields.extend(("published_at", "closed_at"))
        elif target_status in {JobPosting.Status.CLOSED, JobPosting.Status.ARCHIVED}:
            locked.closed_at = timezone.now()
            update_fields.append("closed_at")
        locked.save(update_fields=update_fields)
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.DATA_CHANGE,
                event_type=JOB_AUDIT_EVENTS[target_status][status_from],
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="recruitment.JobPosting",
                resource_id=locked.pk,
                actor=actor,
                request_id=request_id,
                correlation_id=correlation_id,
                metadata={"status_from": status_from, "status_to": target_status},
            )
        )
        return locked


def transition_application(
    *, application, target_status, actor, request_id=None, correlation_id=None
):
    with transaction.atomic():
        try:
            locked = (
                JobApplication.objects.select_for_update()
                .select_related("candidate__user", "job")
                .get(pk=application.pk)
            )
        except (AttributeError, JobApplication.DoesNotExist) as error:
            raise InvalidWorkflowTransitionError(
                "A valid application is required."
            ) from error

        persisted_actor = _persisted_actor(actor)
        if target_status == JobApplication.Status.WITHDRAWN:
            if (
                persisted_actor.role != User.Role.CANDIDATE
                or persisted_actor.pk != locked.candidate.user_id
            ):
                raise WorkflowAuthorizationError("The actor is not authorized.")
        else:
            persisted_actor = _authorize_recruiter(
                persisted_actor,
                company_id=locked.job.company_id,
                capability="can_review_candidates",
            )
        if target_status not in APPLICATION_TRANSITIONS.get(
            locked.status, frozenset()
        ):
            raise InvalidWorkflowTransitionError(
                "The application transition is not allowed."
            )

        status_from = locked.status
        locked.status = target_status
        locked.save(update_fields=("status", "updated_at"))
        event_type = (
            "application.withdrawn"
            if target_status == JobApplication.Status.WITHDRAWN
            else "application.status_changed"
        )
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.DATA_CHANGE,
                event_type=event_type,
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="recruitment.JobApplication",
                resource_id=locked.pk,
                actor=persisted_actor,
                request_id=request_id,
                correlation_id=correlation_id,
                metadata={"status_from": status_from, "status_to": target_status},
            )
        )
        return locked

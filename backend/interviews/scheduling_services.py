import uuid
from dataclasses import dataclass
from datetime import UTC, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from accounts.models import User
from auditlog.consent_services import (
    grant_application_ai_interview_consent,
    has_effective_application_ai_interview_consent,
    has_effective_general_ai_processing_consent,
)
from auditlog.models import AuditEvent, ConsentRecord
from auditlog.services import AuditCommand, record_domain_event
from interviews.models import InterviewRescheduleRequest, InterviewSchedule
from interviews.transition_services import (
    InterviewTransitionError,
    transition_interview,
)
from recruitment.models import JobApplication, RecruiterProfile
from recruitment.transition_services import (
    WorkflowTransitionError,
    transition_application,
)

INVITATION_SIGNING_SALT = "interviews.invitation.token.v1"
INVITATION_DIGEST_SALT = "interviews.invitation.digest.v1"
INVITATION_PURPOSE = "interview-invitation-v1"


class SchedulingServiceError(Exception):
    """Raised for safe scheduling and invitation failures."""


@dataclass(frozen=True, slots=True)
class IssuedInterviewInvitation:
    schedule: InterviewSchedule
    token: str


def _uuid(value, name):
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise SchedulingServiceError(f"A valid {name} is required.") from error


def _recruiter(actor, application):
    try:
        actor = User.objects.get(pk=actor.pk, is_active=True, role=User.Role.RECRUITER)
        recruiter = RecruiterProfile.objects.get(
            user=actor,
            is_verified=True,
            can_review_candidates=True,
            company_id=application.job.company_id,
        )
    except (AttributeError, User.DoesNotExist, RecruiterProfile.DoesNotExist) as error:
        raise SchedulingServiceError("The recruiter is not authorized.") from error
    return recruiter


def _candidate(actor, application):
    try:
        actor = User.objects.get(
            pk=actor.pk,
            is_active=True,
            role=User.Role.CANDIDATE,
            candidate_profile=application.candidate,
        )
    except (AttributeError, User.DoesNotExist) as error:
        raise SchedulingServiceError("The candidate is not authorized.") from error
    return actor


def _schedule_values(start, end, timezone_name):
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, TypeError, ValueError) as error:
        raise SchedulingServiceError("A valid IANA timezone is required.") from error
    if timezone.is_naive(start) or timezone.is_naive(end):
        raise SchedulingServiceError("Timezone-aware schedule times are required.")
    start = start.astimezone(UTC)
    end = end.astimezone(UTC)
    if start <= timezone.now() or end <= start:
        raise SchedulingServiceError("A valid future schedule is required.")
    return start, end, timezone_name


def _token(schedule_id, idempotency_key):
    return signing.Signer(
        key=settings.SECRET_KEY,
        salt=INVITATION_SIGNING_SALT,
        algorithm="sha256",
    ).sign_object(
        {
            "schedule_id": str(schedule_id),
            "nonce": str(idempotency_key),
            "purpose": INVITATION_PURPOSE,
        },
        compress=True,
    )


def _token_digest(token):
    return salted_hmac(
        INVITATION_DIGEST_SALT,
        token,
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()


def _validate_current_consent(application, policy_version):
    if not application.candidate.user.email_verified:
        raise SchedulingServiceError("Verified candidate email is required.")
    if not has_effective_general_ai_processing_consent(
        candidate=application.candidate,
        policy_version=policy_version,
    ) or not has_effective_application_ai_interview_consent(
        application=application,
        policy_version=policy_version,
    ):
        raise SchedulingServiceError("Current candidate consent is required.")


def create_interview_invitation(
    *,
    application,
    actor,
    scheduled_start,
    scheduled_end,
    timezone_name,
    policy_version,
    idempotency_key,
):
    idempotency_key = _uuid(idempotency_key, "idempotency key")
    scheduled_start, scheduled_end, timezone_name = _schedule_values(
        scheduled_start, scheduled_end, timezone_name
    )
    with transaction.atomic():
        try:
            application = (
                JobApplication.objects.select_for_update()
                .select_related("candidate__user", "job")
                .get(pk=application.pk)
            )
        except (AttributeError, JobApplication.DoesNotExist) as error:
            raise SchedulingServiceError("The application is not available.") from error
        recruiter = _recruiter(actor, application)
        _validate_current_consent(application, policy_version)

        existing = InterviewSchedule.objects.filter(
            invitation_idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            if (
                existing.application_id != application.pk
                or existing.scheduled_start != scheduled_start
                or existing.scheduled_end != scheduled_end
                or existing.timezone != timezone_name
            ):
                raise SchedulingServiceError(
                    "The idempotency key was used for another invitation."
                )
            return IssuedInterviewInvitation(
                schedule=existing,
                token=_token(existing.pk, idempotency_key),
            )
        if InterviewSchedule.objects.filter(
            application=application, is_current=True
        ).exists():
            raise SchedulingServiceError("A current schedule already exists.")

        schedule_id = uuid.uuid4()
        token = _token(schedule_id, idempotency_key)
        expires_at = min(timezone.now() + timedelta(hours=48), scheduled_start)
        schedule = InterviewSchedule.objects.create(
            id=schedule_id,
            application=application,
            scheduled_by=recruiter.user,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            timezone=timezone_name,
            access_token_hash=_token_digest(token),
            invitation_expires_at=expires_at,
            invitation_idempotency_key=idempotency_key,
        )
        try:
            if application.status == JobApplication.Status.APPLIED:
                application = transition_application(
                    application=application,
                    target_status=JobApplication.Status.SCREENING,
                    actor=recruiter.user,
                )
            if application.status == JobApplication.Status.SCREENING:
                transition_application(
                    application=application,
                    target_status=JobApplication.Status.INVITED,
                    actor=recruiter.user,
                )
            elif application.status != JobApplication.Status.INVITED:
                raise SchedulingServiceError("The application cannot be invited.")
        except WorkflowTransitionError as error:
            raise SchedulingServiceError("The application cannot be invited.") from error
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.INTERVIEW,
                event_type="interview.invited",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="interviews.InterviewSchedule",
                resource_id=schedule.pk,
                actor=recruiter.user,
                metadata={
                    "application_id": application.pk,
                    "invitation_expires_at": expires_at,
                },
            )
        )
        return IssuedInterviewInvitation(schedule=schedule, token=token)


def deliver_interview_invitation(*, issued, confirmation_url):
    schedule = issued.schedule
    if schedule.invitation_delivery_status == InterviewSchedule.DeliveryStatus.SENT:
        return True
    try:
        send_mail(
            "Confirm your interview",
            f"Confirm your interview using this link: {confirmation_url}",
            getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost"),
            [schedule.application.candidate.user.email],
            fail_silently=False,
        )
    except Exception:
        with transaction.atomic():
            locked = InterviewSchedule.objects.select_for_update().get(pk=schedule.pk)
            locked.invitation_delivery_status = InterviewSchedule.DeliveryStatus.FAILED
            locked.invitation_last_error_code = "email_delivery_failed"
            locked.save(
                update_fields=(
                    "invitation_delivery_status",
                    "invitation_last_error_code",
                    "updated_at",
                )
            )
            record_domain_event(
                AuditCommand(
                    category=AuditEvent.Category.INTERVIEW,
                    event_type="interview.invitation_delivery_failed",
                    outcome=AuditEvent.Outcome.FAILURE,
                    severity=AuditEvent.Severity.MEDIUM,
                    resource_type="interviews.InterviewSchedule",
                    resource_id=locked.pk,
                    actor=locked.scheduled_by,
                    metadata={
                        "application_id": locked.application_id,
                        "failure_code": "email_delivery_failed",
                    },
                )
            )
        return False
    with transaction.atomic():
        locked = InterviewSchedule.objects.select_for_update().get(pk=schedule.pk)
        locked.invitation_delivery_status = InterviewSchedule.DeliveryStatus.SENT
        locked.invitation_last_error_code = ""
        locked.invitation_sent_at = timezone.now()
        locked.save(
            update_fields=(
                "invitation_delivery_status",
                "invitation_last_error_code",
                "invitation_sent_at",
                "updated_at",
            )
        )
    return True


def reissue_interview_invitation(*, schedule, actor):
    try:
        schedule = (
            InterviewSchedule.objects.select_related(
                "application__candidate__user", "application__job"
            )
            .get(pk=schedule.pk, status=InterviewSchedule.Status.PENDING, is_current=True)
        )
    except (AttributeError, InterviewSchedule.DoesNotExist) as error:
        raise SchedulingServiceError("The invitation is not available.") from error
    _recruiter(actor, schedule.application)
    if (
        schedule.invitation_idempotency_key is None
        or schedule.invitation_expires_at is None
        or schedule.invitation_expires_at <= timezone.now()
    ):
        raise SchedulingServiceError("The invitation is not available.")
    return IssuedInterviewInvitation(
        schedule=schedule,
        token=_token(schedule.pk, schedule.invitation_idempotency_key),
    )


def _token_schedule(token):
    try:
        payload = signing.Signer(
            key=settings.SECRET_KEY,
            salt=INVITATION_SIGNING_SALT,
            algorithm="sha256",
        ).unsign_object(token)
        schedule_id = uuid.UUID(payload["schedule_id"])
        idempotency_key = uuid.UUID(payload["nonce"])
    except (signing.BadSignature, KeyError, TypeError, ValueError) as error:
        raise SchedulingServiceError("The invitation is not valid.") from error
    if payload.get("purpose") != INVITATION_PURPOSE:
        raise SchedulingServiceError("The invitation is not valid.")
    return schedule_id, idempotency_key


def confirm_interview_invitation(
    *, token, actor, policy_version, consent_idempotency_key
):
    schedule_id, invitation_key = _token_schedule(token)
    with transaction.atomic():
        try:
            schedule = (
                InterviewSchedule.objects.select_for_update()
                .select_related("application__candidate__user", "application__job")
                .get(pk=schedule_id, invitation_idempotency_key=invitation_key)
            )
        except InterviewSchedule.DoesNotExist as error:
            raise SchedulingServiceError("The invitation is not valid.") from error
        actor = _candidate(actor, schedule.application)
        if (
            schedule.status != InterviewSchedule.Status.PENDING
            or not schedule.is_current
            or schedule.invitation_expires_at is None
            or schedule.invitation_expires_at <= timezone.now()
            or not constant_time_compare(schedule.access_token_hash, _token_digest(token))
        ):
            raise SchedulingServiceError("The invitation is not valid.")
        _validate_current_consent(schedule.application, policy_version)
        grant_application_ai_interview_consent(
            application=schedule.application,
            actor=actor,
            policy_version=policy_version,
            idempotency_key=consent_idempotency_key,
            collection_source=ConsentRecord.CollectionSource.INTERVIEW_CONFIRMATION,
            interview_schedule=schedule,
        )
        try:
            return transition_interview(
                schedule=schedule,
                target_status=InterviewSchedule.Status.CONFIRMED,
                actor=actor,
            )
        except InterviewTransitionError as error:
            raise SchedulingServiceError("The invitation is not valid.") from error


def request_interview_reschedule(
    *, schedule, actor, proposed_start, proposed_end, timezone_name, reason=""
):
    proposed_start, proposed_end, timezone_name = _schedule_values(
        proposed_start, proposed_end, timezone_name
    )
    with transaction.atomic():
        try:
            schedule = (
                InterviewSchedule.objects.select_for_update()
                .select_related("application__candidate__user")
                .get(pk=schedule.pk, is_current=True)
            )
        except (AttributeError, InterviewSchedule.DoesNotExist) as error:
            raise SchedulingServiceError("The interview is not available.") from error
        actor = _candidate(actor, schedule.application)
        if schedule.status not in {
            InterviewSchedule.Status.PENDING,
            InterviewSchedule.Status.CONFIRMED,
        }:
            raise SchedulingServiceError("The interview cannot be rescheduled.")
        try:
            request = InterviewRescheduleRequest.objects.create(
                schedule=schedule,
                requested_by=actor,
                proposed_start=proposed_start,
                proposed_end=proposed_end,
                timezone=timezone_name,
                reason=reason[:1000],
            )
        except IntegrityError as error:
            raise SchedulingServiceError("A reschedule request is already pending.") from error
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.INTERVIEW,
                event_type="interview.reschedule_requested",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="interviews.InterviewSchedule",
                resource_id=schedule.pk,
                actor=actor,
                metadata={
                    "application_id": schedule.application_id,
                    "request_id": request.pk,
                },
            )
        )
        return request


def review_reschedule_request(
    *, reschedule_request, actor, approve, invitation_idempotency_key=None
):
    with transaction.atomic():
        try:
            request = (
                InterviewRescheduleRequest.objects.select_for_update()
                .select_related("schedule__application__job")
                .get(pk=reschedule_request.pk, status=InterviewRescheduleRequest.Status.PENDING)
            )
        except (AttributeError, InterviewRescheduleRequest.DoesNotExist) as error:
            raise SchedulingServiceError("The reschedule request is not available.") from error
        recruiter = _recruiter(actor, request.schedule.application)
        request.reviewed_by = recruiter.user
        request.reviewed_at = timezone.now()
        if not approve:
            request.status = InterviewRescheduleRequest.Status.REJECTED
            request.save(update_fields=("status", "reviewed_by", "reviewed_at", "updated_at"))
            record_domain_event(
                AuditCommand(
                    category=AuditEvent.Category.INTERVIEW,
                    event_type="interview.reschedule_rejected",
                    outcome=AuditEvent.Outcome.SUCCESS,
                    severity=AuditEvent.Severity.INFO,
                    resource_type="interviews.InterviewSchedule",
                    resource_id=request.schedule_id,
                    actor=recruiter.user,
                    metadata={
                        "application_id": request.schedule.application_id,
                        "request_id": request.pk,
                    },
                )
            )
            return request, None

        invitation_idempotency_key = _uuid(
            invitation_idempotency_key, "invitation idempotency key"
        )
        replacement_id = uuid.uuid4()
        token = _token(replacement_id, invitation_idempotency_key)
        expires_at = min(
            timezone.now() + timedelta(hours=48), request.proposed_start
        )
        replacement = InterviewSchedule.objects.create(
            id=replacement_id,
            application=request.schedule.application,
            scheduled_by=recruiter.user,
            scheduled_start=request.proposed_start,
            scheduled_end=request.proposed_end,
            timezone=request.timezone,
            access_token_hash=_token_digest(token),
            invitation_expires_at=expires_at,
            invitation_idempotency_key=invitation_idempotency_key,
            is_current=False,
        )
        try:
            transition_interview(
                schedule=request.schedule,
                target_status=InterviewSchedule.Status.RESCHEDULED,
                actor=recruiter.user,
                replacement_schedule=replacement,
            )
        except InterviewTransitionError as error:
            raise SchedulingServiceError(
                "The reschedule request could not be approved."
            ) from error
        request.status = InterviewRescheduleRequest.Status.APPROVED
        request.save(update_fields=("status", "reviewed_by", "reviewed_at", "updated_at"))
        replacement.refresh_from_db()
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.INTERVIEW,
                event_type="interview.invited",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="interviews.InterviewSchedule",
                resource_id=replacement.pk,
                actor=recruiter.user,
                metadata={
                    "application_id": replacement.application_id,
                    "invitation_expires_at": expires_at,
                },
            )
        )
        return request, IssuedInterviewInvitation(schedule=replacement, token=token)


def cancel_interview(*, schedule, actor, reason_code):
    try:
        return transition_interview(
            schedule=schedule,
            target_status=InterviewSchedule.Status.CANCELLED,
            actor=actor,
            reason_code=reason_code,
        )
    except InterviewTransitionError as error:
        raise SchedulingServiceError("The interview could not be cancelled.") from error


def expire_interview_invitation(*, schedule, actor):
    try:
        schedule = InterviewSchedule.objects.select_related("application__job").get(pk=schedule.pk)
    except (AttributeError, InterviewSchedule.DoesNotExist) as error:
        raise SchedulingServiceError("The interview is not available.") from error
    _recruiter(actor, schedule.application)
    if schedule.invitation_expires_at is None or schedule.invitation_expires_at > timezone.now():
        raise SchedulingServiceError("The invitation has not expired.")
    try:
        return transition_interview(
            schedule=schedule,
            target_status=InterviewSchedule.Status.EXPIRED,
            actor=None,
        )
    except InterviewTransitionError as error:
        raise SchedulingServiceError("The interview could not be expired.") from error

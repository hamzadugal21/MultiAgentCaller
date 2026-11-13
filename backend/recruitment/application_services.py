import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from auditlog.consent_services import grant_application_ai_interview_consent
from auditlog.models import AuditEvent, ConsentRecord
from auditlog.services import AuditCommand, record_domain_event
from calling.models import CallSession
from candidates.models import CandidateProfile, Resume
from interviews.models import InterviewSchedule
from interviews.transition_services import cancel_interview_for_application_withdrawal
from recruitment.models import JobApplication, JobPosting, RecruiterProfile
from recruitment.transition_services import transition_application


class ApplicationServiceError(Exception):
    """Raised for safe application-workflow failures."""


def _candidate_actor(actor):
    try:
        actor = User.objects.get(
            pk=actor.pk,
            is_active=True,
            role=User.Role.CANDIDATE,
        )
        candidate = CandidateProfile.objects.get(user=actor)
    except (AttributeError, User.DoesNotExist, CandidateProfile.DoesNotExist) as error:
        raise ApplicationServiceError("The candidate is not authorized.") from error
    return actor, candidate


def create_application(
    *,
    actor,
    job,
    resume,
    cover_note="",
    grant_interview_consent=False,
    policy_version=None,
    consent_idempotency_key=None,
):
    with transaction.atomic():
        actor, candidate = _candidate_actor(actor)
        try:
            job = JobPosting.objects.select_for_update().get(
                pk=job.pk,
                status=JobPosting.Status.OPEN,
                company__is_active=True,
            )
            resume = Resume.objects.get(
                pk=resume.pk,
                candidate=candidate,
                is_active=True,
                processing_status=Resume.ProcessingStatus.COMPLETED,
            )
        except (AttributeError, JobPosting.DoesNotExist, Resume.DoesNotExist) as error:
            raise ApplicationServiceError("The application is not eligible.") from error
        if job.application_deadline and job.application_deadline <= timezone.now():
            raise ApplicationServiceError("The application is not eligible.")
        try:
            application = JobApplication.objects.create(
                job=job,
                candidate=candidate,
                resume=resume,
                cover_note=cover_note,
                status=JobApplication.Status.APPLIED,
                consent_to_ai_interview=False,
            )
        except IntegrityError as error:
            raise ApplicationServiceError("An application already exists.") from error
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.DATA_CHANGE,
                event_type="application.created",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="recruitment.JobApplication",
                resource_id=application.pk,
                actor=actor,
                metadata={"job_id": job.pk, "resume_id": resume.pk},
            )
        )
        if grant_interview_consent:
            if not policy_version or not consent_idempotency_key:
                raise ApplicationServiceError("Current consent details are required.")
            grant_application_ai_interview_consent(
                application=application,
                actor=actor,
                policy_version=policy_version,
                idempotency_key=consent_idempotency_key,
                collection_source=ConsentRecord.CollectionSource.APPLICATION,
            )
        return application


def change_application_interview_consent(
    *, application, actor, operation, policy_version
):
    actor, candidate = _candidate_actor(actor)
    try:
        application = JobApplication.objects.get(
            pk=application.pk, candidate=candidate
        )
    except (AttributeError, JobApplication.DoesNotExist) as error:
        raise ApplicationServiceError("The application is not available.") from error
    return operation(
        application=application,
        actor=actor,
        policy_version=policy_version,
        idempotency_key=uuid.uuid4(),
        collection_source=ConsentRecord.CollectionSource.APPLICATION,
    )


def withdraw_application(*, application, actor):
    with transaction.atomic():
        actor, candidate = _candidate_actor(actor)
        try:
            locked = (
                JobApplication.objects.select_for_update()
                .select_related("candidate")
                .get(pk=application.pk, candidate=candidate)
            )
        except (AttributeError, JobApplication.DoesNotExist) as error:
            raise ApplicationServiceError("The application is not available.") from error

        if CallSession.objects.filter(
            schedule__application=locked,
            started_at__isnull=False,
        ).exists():
            raise ApplicationServiceError("The application cannot be withdrawn.")

        schedule = (
            InterviewSchedule.objects.select_for_update()
            .filter(application=locked, is_current=True)
            .first()
        )
        if schedule is not None:
            cancel_interview_for_application_withdrawal(
                schedule=schedule,
                actor=actor,
            )
        return transition_application(
            application=locked,
            target_status=JobApplication.Status.WITHDRAWN,
            actor=actor,
        )


def recruiter_applications(actor):
    try:
        actor = User.objects.get(pk=actor.pk, is_active=True, role=User.Role.RECRUITER)
        recruiter = RecruiterProfile.objects.get(
            user=actor,
            is_verified=True,
            can_review_candidates=True,
        )
    except (AttributeError, User.DoesNotExist, RecruiterProfile.DoesNotExist) as error:
        raise ApplicationServiceError("The recruiter is not authorized.") from error
    return JobApplication.objects.filter(job__company=recruiter.company).select_related(
        "job", "candidate__user", "resume"
    )

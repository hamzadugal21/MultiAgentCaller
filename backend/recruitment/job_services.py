from django.db import transaction

from accounts.models import User
from auditlog.models import AuditEvent
from auditlog.services import AuditCommand, record_domain_event
from candidates.models import Skill
from recruitment.models import (
    InterviewQuestion,
    JobFAQ,
    JobPosting,
    JobSkillRequirement,
    RecruiterProfile,
)


class JobServiceError(Exception):
    """Raised for safe job-management failures."""


def authorized_job_recruiter(actor):
    try:
        actor = User.objects.get(pk=actor.pk, is_active=True, role=User.Role.RECRUITER)
        recruiter = RecruiterProfile.objects.select_related("company").get(user=actor)
    except (AttributeError, User.DoesNotExist, RecruiterProfile.DoesNotExist) as error:
        raise JobServiceError("The recruiter is not authorized.") from error
    if not recruiter.is_verified or not recruiter.can_manage_jobs or not recruiter.company.is_active:
        raise JobServiceError("The recruiter is not authorized.")
    return recruiter


def recruiter_jobs(actor):
    recruiter = authorized_job_recruiter(actor)
    return JobPosting.objects.filter(company=recruiter.company).select_related("company")


def create_job(*, actor, values):
    with transaction.atomic():
        recruiter = authorized_job_recruiter(actor)
        job = JobPosting.objects.create(
            company=recruiter.company,
            created_by=recruiter,
            status=JobPosting.Status.DRAFT,
            **values,
        )
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.DATA_CHANGE,
                event_type="job.created",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="recruitment.JobPosting",
                resource_id=job.pk,
                actor=recruiter.user,
            )
        )
        return job


def update_job(*, actor, job, values, changed_fields):
    with transaction.atomic():
        recruiter = authorized_job_recruiter(actor)
        try:
            locked = JobPosting.objects.select_for_update().get(
                pk=job.pk, company=recruiter.company
            )
        except (AttributeError, JobPosting.DoesNotExist) as error:
            raise JobServiceError("The job is not available.") from error
        if locked.status == JobPosting.Status.ARCHIVED:
            raise JobServiceError("The job cannot be edited.")
        for field, value in values.items():
            setattr(locked, field, value)
        locked.save(update_fields=tuple(values) + ("updated_at",))
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.DATA_CHANGE,
                event_type="job.updated",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="recruitment.JobPosting",
                resource_id=locked.pk,
                actor=recruiter.user,
                metadata={"changed_fields": sorted(changed_fields)},
            )
        )
        return locked


def _locked_owned_job(*, actor, job):
    recruiter = authorized_job_recruiter(actor)
    try:
        return recruiter, JobPosting.objects.select_for_update().get(
            pk=job.pk, company=recruiter.company
        )
    except (AttributeError, JobPosting.DoesNotExist) as error:
        raise JobServiceError("The job is not available.") from error


def add_job_skill(*, actor, job, values):
    with transaction.atomic():
        recruiter, job = _locked_owned_job(actor=actor, job=job)
        skill_name = values.pop("skill_name").strip()
        skill = Skill.objects.filter(name__iexact=skill_name).first()
        if skill is None:
            skill = Skill.objects.create(name=skill_name)
        requirement, _ = JobSkillRequirement.objects.update_or_create(
            job=job, skill=skill, defaults=values
        )
        _audit_child_change(job, recruiter.user, "skill_requirements")
        return requirement


def add_interview_question(*, actor, job, values):
    with transaction.atomic():
        recruiter, job = _locked_owned_job(actor=actor, job=job)
        question = InterviewQuestion.objects.create(job=job, **values)
        _audit_child_change(job, recruiter.user, "interview_questions")
        return question


def add_job_faq(*, actor, job, values):
    with transaction.atomic():
        recruiter, job = _locked_owned_job(actor=actor, job=job)
        faq = JobFAQ.objects.create(job=job, **values)
        _audit_child_change(job, recruiter.user, "faqs")
        return faq


def _audit_child_change(job, actor, changed_field):
    record_domain_event(
        AuditCommand(
            category=AuditEvent.Category.DATA_CHANGE,
            event_type="job.updated",
            outcome=AuditEvent.Outcome.SUCCESS,
            severity=AuditEvent.Severity.INFO,
            resource_type="recruitment.JobPosting",
            resource_id=job.pk,
            actor=actor,
            metadata={"changed_fields": [changed_field]},
        )
    )

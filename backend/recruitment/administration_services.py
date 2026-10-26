from django.db import transaction

from accounts.models import User
from auditlog.models import AuditEvent
from auditlog.services import AuditCommand, record_domain_event
from recruitment.models import Company, RecruiterProfile


class AdministrationServiceError(Exception):
    """Raised for safe administrator-provisioning failures."""


def _administrator(actor):
    try:
        actor = User.objects.get(pk=actor.pk, is_active=True)
    except (AttributeError, User.DoesNotExist) as error:
        raise AdministrationServiceError("An administrator is required.") from error
    if not (actor.is_superuser or actor.role == User.Role.ADMIN):
        raise AdministrationServiceError("An administrator is required.")
    return actor


def create_company(*, actor, name, **attributes):
    with transaction.atomic():
        actor = _administrator(actor)
        company = Company.objects.create(name=name, **attributes)
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.ADMINISTRATION,
                event_type="company.created",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="recruitment.Company",
                resource_id=company.pk,
                actor=actor,
            )
        )
        return company


def provision_recruiter(
    *,
    actor,
    user,
    company,
    is_verified=False,
    can_manage_jobs=True,
    can_review_candidates=True,
):
    with transaction.atomic():
        actor = _administrator(actor)
        try:
            user = User.objects.select_for_update().get(pk=user.pk, is_active=True)
            company = Company.objects.get(pk=company.pk, is_active=True)
        except (AttributeError, User.DoesNotExist, Company.DoesNotExist) as error:
            raise AdministrationServiceError("Valid provisioning records are required.") from error
        if user.role != User.Role.RECRUITER:
            raise AdministrationServiceError("The user must have the recruiter role.")
        recruiter = RecruiterProfile.objects.create(
            user=user,
            company=company,
            is_verified=is_verified,
            can_manage_jobs=can_manage_jobs,
            can_review_candidates=can_review_candidates,
        )
        capabilities = []
        if can_manage_jobs:
            capabilities.append("manage_jobs")
        if can_review_candidates:
            capabilities.append("review_candidates")
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.ADMINISTRATION,
                event_type="recruiter.provisioned",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="recruitment.RecruiterProfile",
                resource_id=recruiter.pk,
                actor=actor,
                metadata={
                    "company_id": company.pk,
                    "capabilities": capabilities,
                    "is_verified": is_verified,
                },
            )
        )
        return recruiter

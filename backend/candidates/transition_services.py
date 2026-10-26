from types import MappingProxyType

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditEvent
from auditlog.services import SAFE_CODE_PATTERN, AuditCommand, record_domain_event
from candidates.models import CandidateProfile, Resume


class ResumeTransitionError(Exception):
    """Raised for safe resume lifecycle failures."""


RESUME_TRANSITIONS = MappingProxyType(
    {
        Resume.ProcessingStatus.PENDING: frozenset(
            {Resume.ProcessingStatus.PROCESSING}
        ),
        Resume.ProcessingStatus.PROCESSING: frozenset(
            {Resume.ProcessingStatus.COMPLETED, Resume.ProcessingStatus.FAILED}
        ),
        Resume.ProcessingStatus.FAILED: frozenset(
            {Resume.ProcessingStatus.PROCESSING}
        ),
        Resume.ProcessingStatus.COMPLETED: frozenset(),
    }
)


def _safe_code(value, field_name):
    if not isinstance(value, str) or not SAFE_CODE_PATTERN.fullmatch(value):
        raise ResumeTransitionError(f"A valid {field_name} is required.")
    return value


def transition_resume_processing(
    *,
    resume,
    target_status,
    parser,
    extracted_text=None,
    failure_code=None,
    request_id=None,
    correlation_id=None,
):
    parser = _safe_code(parser, "parser")
    with transaction.atomic():
        try:
            locked = Resume.objects.select_for_update().get(pk=resume.pk)
        except (AttributeError, Resume.DoesNotExist) as error:
            raise ResumeTransitionError("A valid resume is required.") from error
        if target_status not in RESUME_TRANSITIONS.get(
            locked.processing_status, frozenset()
        ):
            raise ResumeTransitionError("The resume transition is not allowed.")

        locked.processing_status = target_status
        update_fields = ["processing_status"]
        if target_status == Resume.ProcessingStatus.PROCESSING:
            locked.processing_error = ""
            update_fields.append("processing_error")
            event_type = "resume.processing_started"
            metadata = {"parser": parser}
        elif target_status == Resume.ProcessingStatus.COMPLETED:
            if not isinstance(extracted_text, str):
                raise ResumeTransitionError("Extracted text is required.")
            locked.extracted_text = extracted_text
            locked.processing_error = ""
            locked.processed_at = timezone.now()
            update_fields.extend(("extracted_text", "processing_error", "processed_at"))
            event_type = "resume.processing_succeeded"
            metadata = {
                "parser": parser,
                "extracted_character_count": len(extracted_text),
            }
        else:
            failure_code = _safe_code(failure_code, "failure code")
            locked.extracted_text = ""
            locked.processing_error = failure_code
            locked.processed_at = timezone.now()
            update_fields.extend(("extracted_text", "processing_error", "processed_at"))
            event_type = "resume.processing_failed"
            metadata = {"parser": parser, "failure_code": failure_code}
        locked.save(update_fields=update_fields)
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.SYSTEM,
                event_type=event_type,
                outcome=(
                    AuditEvent.Outcome.FAILURE
                    if target_status == Resume.ProcessingStatus.FAILED
                    else AuditEvent.Outcome.SUCCESS
                ),
                severity=AuditEvent.Severity.INFO,
                resource_type="candidates.Resume",
                resource_id=locked.pk,
                actor=None,
                request_id=request_id,
                correlation_id=correlation_id,
                metadata=metadata,
            )
        )
        return locked


def activate_processed_resume(
    *, resume, actor, request_id=None, correlation_id=None
):
    with transaction.atomic():
        try:
            candidate = CandidateProfile.objects.select_for_update().get(
                pk=resume.candidate_id
            )
            locked = Resume.objects.select_for_update().get(pk=resume.pk)
            persisted_actor = User.objects.get(pk=actor.pk, is_active=True)
        except (AttributeError, CandidateProfile.DoesNotExist, Resume.DoesNotExist, User.DoesNotExist) as error:
            raise ResumeTransitionError("The resume cannot be activated.") from error
        if (
            persisted_actor.pk != candidate.user_id
            or persisted_actor.role != User.Role.CANDIDATE
            or locked.candidate_id != candidate.pk
            or locked.processing_status != Resume.ProcessingStatus.COMPLETED
        ):
            raise ResumeTransitionError("The resume cannot be activated.")

        previous = (
            Resume.objects.select_for_update()
            .filter(candidate=candidate, is_active=True)
            .exclude(pk=locked.pk)
            .first()
        )
        if previous is not None:
            previous.is_active = False
            previous.save(update_fields=("is_active",))
        if not locked.is_active:
            locked.is_active = True
            locked.save(update_fields=("is_active",))
        metadata = {}
        if previous is not None:
            metadata["replaced_resume_id"] = previous.pk
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.DATA_CHANGE,
                event_type="resume.activated",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="candidates.Resume",
                resource_id=locked.pk,
                actor=persisted_actor,
                request_id=request_id,
                correlation_id=correlation_id,
                metadata=metadata,
            )
        )
        return locked

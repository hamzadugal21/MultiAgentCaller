import uuid
from types import MappingProxyType

from django.db import transaction

from accounts.models import User
from auditlog.models import AuditEvent, ConsentRecord
from auditlog.services import SAFE_CODE_PATTERN, AuditCommand, record_domain_event
from candidates.models import CandidateProfile
from interviews.models import InterviewSchedule
from recruitment.models import JobApplication

LEGACY_POLICY_VERSION = "legacy-unversioned"
MAX_POLICY_VERSION_LENGTH = ConsentRecord._meta.get_field("policy_version").max_length

CONSENT_TRANSITIONS = MappingProxyType(
    {
        None: frozenset(
            {ConsentRecord.Action.GRANTED, ConsentRecord.Action.REVOKED}
        ),
        ConsentRecord.Action.GRANTED: frozenset(
            {ConsentRecord.Action.GRANTED, ConsentRecord.Action.REVOKED}
        ),
        ConsentRecord.Action.REVOKED: frozenset(
            {ConsentRecord.Action.GRANTED, ConsentRecord.Action.REVOKED}
        ),
    }
)


class ConsentServiceError(Exception):
    """Base exception for safe deterministic consent-service failures."""


class ConsentValidationError(ConsentServiceError):
    """Raised when a consent request violates a validation or authorization rule."""


class ConsentIdempotencyConflictError(ConsentServiceError):
    """Raised when an idempotency key is reused for different consent semantics."""


def _required_uuid(value, *, field_name):
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ConsentValidationError(f"A valid {field_name} is required.") from error


def _optional_uuid(value, *, field_name):
    if value is None or value == "":
        return None
    return _required_uuid(value, field_name=field_name)


def _validated_policy_version(value):
    if not isinstance(value, str):
        raise ConsentValidationError("A valid policy version is required.")

    if (
        len(value) > MAX_POLICY_VERSION_LENGTH
        or value == LEGACY_POLICY_VERSION
        or not SAFE_CODE_PATTERN.fullmatch(value)
    ):
        raise ConsentValidationError("A valid policy version is required.")
    return value


def _validated_actor(*, actor, candidate, collection_source):
    actor_id = getattr(actor, "pk", None)
    if actor_id is None:
        raise ConsentValidationError("An authorized consent actor is required.")

    try:
        persisted_actor = User.objects.get(pk=actor_id, is_active=True)
    except (TypeError, ValueError, User.DoesNotExist) as error:
        raise ConsentValidationError("An authorized consent actor is required.") from error

    candidate_sources = {
        ConsentRecord.CollectionSource.PROFILE,
        ConsentRecord.CollectionSource.APPLICATION,
        ConsentRecord.CollectionSource.INTERVIEW_CONFIRMATION,
    }
    if (
        collection_source in candidate_sources
        and (
            persisted_actor.pk != candidate.user_id
            or persisted_actor.role != User.Role.CANDIDATE
        )
    ):
        raise ConsentValidationError("The consent actor is not authorized.")

    if collection_source == ConsentRecord.CollectionSource.ADMIN_ASSISTED and not (
        persisted_actor.role == User.Role.ADMIN or persisted_actor.is_superuser
    ):
        raise ConsentValidationError("The consent actor is not authorized.")
    return persisted_actor


def _validate_collection_source(collection_source, *, allowed_sources):
    if collection_source not in allowed_sources:
        raise ConsentValidationError("The consent collection source is not allowed.")


def _record_semantics(record):
    return {
        "candidate_id": record.candidate_id,
        "consent_type": record.consent_type,
        "action": record.action,
        "policy_version": record.policy_version,
        "collection_source": record.collection_source,
        "application_id": record.application_id,
        "interview_schedule_id": record.interview_schedule_id,
        "recorded_by_id": record.recorded_by_id,
    }


def _expected_semantics(
    *,
    candidate_id,
    consent_type,
    action,
    policy_version,
    collection_source,
    application_id,
    interview_schedule_id,
    actor_id,
):
    return {
        "candidate_id": candidate_id,
        "consent_type": consent_type,
        "action": action,
        "policy_version": policy_version,
        "collection_source": collection_source,
        "application_id": application_id,
        "interview_schedule_id": interview_schedule_id,
        "recorded_by_id": actor_id,
    }


def _existing_idempotent_record(*, idempotency_key, expected_semantics):
    existing = ConsentRecord.objects.filter(idempotency_key=idempotency_key).first()
    if existing is None:
        return None
    if _record_semantics(existing) != expected_semantics:
        raise ConsentIdempotencyConflictError(
            "The idempotency key was already used for a different consent request."
        )
    return existing


def _latest_record(*, candidate_id, consent_type, application_id):
    records = ConsentRecord.objects.filter(
        candidate_id=candidate_id,
        consent_type=consent_type,
    )
    if application_id is None:
        records = records.filter(application__isnull=True)
    else:
        records = records.filter(application_id=application_id)
    return records.order_by("-recorded_at", "-id").first()


def _validate_consent_transition(*, latest, target_action):
    current_action = latest.action if latest is not None else None
    if target_action not in CONSENT_TRANSITIONS[current_action]:
        raise ConsentValidationError("The consent transition is not allowed.")


def _audit_consent_record(record):
    metadata = {
        "candidate_id": record.candidate_id,
        "consent_type": record.consent_type,
        "policy_version": record.policy_version,
        "collection_source": record.collection_source,
    }
    if record.application_id is not None:
        metadata["application_id"] = record.application_id
    if record.interview_schedule_id is not None:
        metadata["interview_schedule_id"] = record.interview_schedule_id

    return record_domain_event(
        AuditCommand(
            category=AuditEvent.Category.DATA_CHANGE,
            event_type=f"consent.{record.action}",
            outcome=AuditEvent.Outcome.SUCCESS,
            severity=AuditEvent.Severity.INFO,
            resource_type="auditlog.ConsentRecord",
            resource_id=record.id,
            actor=record.recorded_by,
            request_id=record.request_id,
            correlation_id=record.correlation_id,
            metadata=metadata,
        )
    )


def _change_general_consent(
    *,
    candidate,
    actor,
    action,
    policy_version,
    collection_source,
    idempotency_key,
    request_id,
    correlation_id,
):
    policy_version = _validated_policy_version(policy_version)
    idempotency_key = _required_uuid(
        idempotency_key,
        field_name="idempotency key",
    )
    request_id = _optional_uuid(request_id, field_name="request ID")
    correlation_id = _optional_uuid(correlation_id, field_name="correlation ID")
    _validate_collection_source(
        collection_source,
        allowed_sources={
            ConsentRecord.CollectionSource.PROFILE,
            ConsentRecord.CollectionSource.ADMIN_ASSISTED,
        },
    )

    with transaction.atomic():
        try:
            locked_candidate = (
                CandidateProfile.objects.select_for_update()
                .select_related("user")
                .get(pk=candidate.pk)
            )
        except (AttributeError, CandidateProfile.DoesNotExist) as error:
            raise ConsentValidationError("A valid candidate is required.") from error

        persisted_actor = _validated_actor(
            actor=actor,
            candidate=locked_candidate,
            collection_source=collection_source,
        )
        expected = _expected_semantics(
            candidate_id=locked_candidate.pk,
            consent_type=ConsentRecord.ConsentType.GENERAL_AI_PROCESSING,
            action=action,
            policy_version=policy_version,
            collection_source=collection_source,
            application_id=None,
            interview_schedule_id=None,
            actor_id=persisted_actor.pk,
        )
        existing = _existing_idempotent_record(
            idempotency_key=idempotency_key,
            expected_semantics=expected,
        )
        if existing is not None:
            return existing

        _validate_consent_transition(
            latest=_latest_record(
                candidate_id=locked_candidate.pk,
                consent_type=ConsentRecord.ConsentType.GENERAL_AI_PROCESSING,
                application_id=None,
            ),
            target_action=action,
        )

        record = ConsentRecord.objects.create(
            candidate=locked_candidate,
            consent_type=ConsentRecord.ConsentType.GENERAL_AI_PROCESSING,
            action=action,
            policy_version=policy_version,
            collection_source=collection_source,
            recorded_by=persisted_actor,
            idempotency_key=idempotency_key,
            request_id=request_id,
            correlation_id=correlation_id,
        )
        locked_candidate.ai_processing_consent = action == ConsentRecord.Action.GRANTED
        locked_candidate.consent_recorded_at = record.recorded_at
        locked_candidate.save(
            update_fields=("ai_processing_consent", "consent_recorded_at")
        )
        _audit_consent_record(record)
        return record


def grant_general_ai_processing_consent(
    *,
    candidate,
    actor,
    policy_version,
    idempotency_key,
    collection_source=ConsentRecord.CollectionSource.PROFILE,
    request_id=None,
    correlation_id=None,
):
    return _change_general_consent(
        candidate=candidate,
        actor=actor,
        action=ConsentRecord.Action.GRANTED,
        policy_version=policy_version,
        collection_source=collection_source,
        idempotency_key=idempotency_key,
        request_id=request_id,
        correlation_id=correlation_id,
    )


def revoke_general_ai_processing_consent(
    *,
    candidate,
    actor,
    policy_version,
    idempotency_key,
    collection_source=ConsentRecord.CollectionSource.PROFILE,
    request_id=None,
    correlation_id=None,
):
    return _change_general_consent(
        candidate=candidate,
        actor=actor,
        action=ConsentRecord.Action.REVOKED,
        policy_version=policy_version,
        collection_source=collection_source,
        idempotency_key=idempotency_key,
        request_id=request_id,
        correlation_id=correlation_id,
    )


def _change_interview_consent(
    *,
    application,
    actor,
    action,
    policy_version,
    collection_source,
    idempotency_key,
    interview_schedule,
    request_id,
    correlation_id,
):
    policy_version = _validated_policy_version(policy_version)
    idempotency_key = _required_uuid(
        idempotency_key,
        field_name="idempotency key",
    )
    request_id = _optional_uuid(request_id, field_name="request ID")
    correlation_id = _optional_uuid(correlation_id, field_name="correlation ID")
    _validate_collection_source(
        collection_source,
        allowed_sources={
            ConsentRecord.CollectionSource.APPLICATION,
            ConsentRecord.CollectionSource.INTERVIEW_CONFIRMATION,
            ConsentRecord.CollectionSource.ADMIN_ASSISTED,
        },
    )

    with transaction.atomic():
        try:
            locked_application = (
                JobApplication.objects.select_for_update()
                .select_related("candidate__user")
                .get(pk=application.pk)
            )
        except (AttributeError, JobApplication.DoesNotExist) as error:
            raise ConsentValidationError("A valid application is required.") from error

        locked_candidate = locked_application.candidate
        persisted_actor = _validated_actor(
            actor=actor,
            candidate=locked_candidate,
            collection_source=collection_source,
        )

        schedule_id = None
        persisted_schedule = None
        if interview_schedule is not None:
            schedule_id = _required_uuid(
                getattr(interview_schedule, "pk", None),
                field_name="interview schedule ID",
            )
            try:
                persisted_schedule = InterviewSchedule.objects.get(pk=schedule_id)
            except InterviewSchedule.DoesNotExist as error:
                raise ConsentValidationError(
                    "A valid interview schedule is required."
                ) from error
            if persisted_schedule.application_id != locked_application.pk:
                raise ConsentValidationError(
                    "The interview schedule does not belong to the application."
                )
        if (
            collection_source == ConsentRecord.CollectionSource.INTERVIEW_CONFIRMATION
            and schedule_id is None
        ):
            raise ConsentValidationError(
                "Interview confirmation consent requires a schedule."
            )

        expected = _expected_semantics(
            candidate_id=locked_candidate.pk,
            consent_type=ConsentRecord.ConsentType.AI_INTERVIEW,
            action=action,
            policy_version=policy_version,
            collection_source=collection_source,
            application_id=locked_application.pk,
            interview_schedule_id=schedule_id,
            actor_id=persisted_actor.pk,
        )
        existing = _existing_idempotent_record(
            idempotency_key=idempotency_key,
            expected_semantics=expected,
        )
        if existing is not None:
            return existing

        _validate_consent_transition(
            latest=_latest_record(
                candidate_id=locked_candidate.pk,
                consent_type=ConsentRecord.ConsentType.AI_INTERVIEW,
                application_id=locked_application.pk,
            ),
            target_action=action,
        )

        record = ConsentRecord.objects.create(
            candidate=locked_candidate,
            consent_type=ConsentRecord.ConsentType.AI_INTERVIEW,
            action=action,
            policy_version=policy_version,
            collection_source=collection_source,
            application=locked_application,
            interview_schedule=persisted_schedule,
            recorded_by=persisted_actor,
            idempotency_key=idempotency_key,
            request_id=request_id,
            correlation_id=correlation_id,
        )
        locked_application.consent_to_ai_interview = (
            action == ConsentRecord.Action.GRANTED
        )
        locked_application.save(update_fields=("consent_to_ai_interview",))
        _audit_consent_record(record)
        return record


def grant_application_ai_interview_consent(
    *,
    application,
    actor,
    policy_version,
    idempotency_key,
    collection_source=ConsentRecord.CollectionSource.APPLICATION,
    interview_schedule=None,
    request_id=None,
    correlation_id=None,
):
    return _change_interview_consent(
        application=application,
        actor=actor,
        action=ConsentRecord.Action.GRANTED,
        policy_version=policy_version,
        collection_source=collection_source,
        idempotency_key=idempotency_key,
        interview_schedule=interview_schedule,
        request_id=request_id,
        correlation_id=correlation_id,
    )


def revoke_application_ai_interview_consent(
    *,
    application,
    actor,
    policy_version,
    idempotency_key,
    collection_source=ConsentRecord.CollectionSource.APPLICATION,
    interview_schedule=None,
    request_id=None,
    correlation_id=None,
):
    return _change_interview_consent(
        application=application,
        actor=actor,
        action=ConsentRecord.Action.REVOKED,
        policy_version=policy_version,
        collection_source=collection_source,
        idempotency_key=idempotency_key,
        interview_schedule=interview_schedule,
        request_id=request_id,
        correlation_id=correlation_id,
    )


def has_effective_general_ai_processing_consent(*, candidate, policy_version):
    if policy_version == LEGACY_POLICY_VERSION:
        return False
    policy_version = _validated_policy_version(policy_version)
    latest = _latest_record(
        candidate_id=candidate.pk,
        consent_type=ConsentRecord.ConsentType.GENERAL_AI_PROCESSING,
        application_id=None,
    )
    return (
        latest is not None
        and latest.action == ConsentRecord.Action.GRANTED
        and latest.policy_version == policy_version
        and latest.policy_version != LEGACY_POLICY_VERSION
    )


def has_effective_application_ai_interview_consent(
    *,
    application,
    policy_version,
):
    if policy_version == LEGACY_POLICY_VERSION:
        return False
    policy_version = _validated_policy_version(policy_version)
    latest = _latest_record(
        candidate_id=application.candidate_id,
        consent_type=ConsentRecord.ConsentType.AI_INTERVIEW,
        application_id=application.pk,
    )
    return (
        latest is not None
        and latest.action == ConsentRecord.Action.GRANTED
        and latest.policy_version == policy_version
        and latest.policy_version != LEGACY_POLICY_VERSION
    )

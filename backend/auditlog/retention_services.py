import uuid
from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from auditlog.models import AuditEvent, DataRetentionRecord
from auditlog.services import SAFE_CODE_PATTERN, AuditCommand, record_domain_event
from calling.models import CallSession, SimulatedInterviewResponse, TranscriptSegment

CURRENT_RETENTION_POLICY_VERSION = "mvp-retention-v1"
DEFAULT_RETENTION_DAYS = 30
DEFAULT_BATCH_SIZE = 100
MAX_RETENTION_DAYS = 3650
MAX_BATCH_SIZE = 500
TERMINAL_SESSION_STATUSES = (
    CallSession.Status.COMPLETED,
    CallSession.Status.CANCELLED,
    CallSession.Status.EXPIRED,
    CallSession.Status.FAILED,
)


class RetentionCategory:
    SIMULATED_ANSWERS = "simulated_interview_answers"
    TRANSCRIPT_SEGMENTS = "transcript_segments"


RETENTION_RESOURCE_TYPES = MappingProxyType(
    {
        RetentionCategory.SIMULATED_ANSWERS: "calling.SimulatedInterviewResponse",
        RetentionCategory.TRANSCRIPT_SEGMENTS: "calling.TranscriptSegment",
    }
)


class RetentionServiceError(Exception):
    """Raised when a retention operation cannot be completed safely."""


class RetentionValidationError(RetentionServiceError):
    """Raised for invalid policy, category, or execution parameters."""


class RetentionReplayConflictError(RetentionServiceError):
    """Raised when a run identifier is reused with different semantics."""


@dataclass(frozen=True, slots=True)
class RetentionResult:
    category: str
    execution_mode: str
    result: str
    eligible_count: int
    processed_count: int
    replayed: bool = False
    record: DataRetentionRecord | None = None


def _validated_parameters(*, category, policy_version, retention_days, batch_size):
    if category not in RETENTION_RESOURCE_TYPES:
        raise RetentionValidationError("The retention category is not supported.")
    if (
        not isinstance(policy_version, str)
        or not SAFE_CODE_PATTERN.fullmatch(policy_version)
        or policy_version != CURRENT_RETENTION_POLICY_VERSION
    ):
        raise RetentionValidationError("The retention policy version is not supported.")
    if (
        isinstance(retention_days, bool)
        or not isinstance(retention_days, int)
        or not 1 <= retention_days <= MAX_RETENTION_DAYS
    ):
        raise RetentionValidationError("The retention period is not valid.")
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or not 1 <= batch_size <= MAX_BATCH_SIZE
    ):
        raise RetentionValidationError("The retention batch size is not valid.")


def _run_uuid(value):
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise RetentionValidationError("The retention run identifier is not valid.") from error


def _eligible_queryset(*, category, cutoff_at):
    session_filters = {
        "call_session__status__in": TERMINAL_SESSION_STATUSES,
        "call_session__ended_at__isnull": False,
        "call_session__ended_at__lte": cutoff_at,
    }
    if category == RetentionCategory.SIMULATED_ANSWERS:
        return SimulatedInterviewResponse.objects.filter(
            **session_filters,
        ).exclude(answer_text="")
    return TranscriptSegment.objects.filter(**session_filters).exclude(
        text="",
        redacted_text="",
    )


def preview_retention(
    *,
    category,
    policy_version=CURRENT_RETENTION_POLICY_VERSION,
    retention_days=DEFAULT_RETENTION_DAYS,
    batch_size=DEFAULT_BATCH_SIZE,
):
    _validated_parameters(
        category=category,
        policy_version=policy_version,
        retention_days=retention_days,
        batch_size=batch_size,
    )
    cutoff_at = timezone.now() - timedelta(days=retention_days)
    eligible_count = min(
        _eligible_queryset(category=category, cutoff_at=cutoff_at).count(),
        batch_size,
    )
    return RetentionResult(
        category=category,
        execution_mode=DataRetentionRecord.ExecutionMode.DRY_RUN,
        result=DataRetentionRecord.Result.PREVIEWED,
        eligible_count=eligible_count,
        processed_count=0,
    )


def _matching_replay(
    record,
    *,
    category,
    policy_version,
    retention_days,
    batch_size,
):
    return (
        record.execution_mode == DataRetentionRecord.ExecutionMode.APPLY
        and record.data_category == category
        and record.policy_version == policy_version
        and record.retention_days == retention_days
        and record.batch_size == batch_size
    )


def _anonymize_locked_records(*, category, records):
    identifiers = [record.pk for record in records]
    if not identifiers:
        return 0
    if category == RetentionCategory.SIMULATED_ANSWERS:
        return SimulatedInterviewResponse.objects.filter(pk__in=identifiers).update(
            answer_text=""
        )
    return TranscriptSegment.objects.filter(pk__in=identifiers).update(
        text="",
        redacted_text="",
        contains_sensitive_data=False,
    )


def apply_retention(
    *,
    category,
    run_id,
    policy_version=CURRENT_RETENTION_POLICY_VERSION,
    retention_days=DEFAULT_RETENTION_DAYS,
    batch_size=DEFAULT_BATCH_SIZE,
):
    _validated_parameters(
        category=category,
        policy_version=policy_version,
        retention_days=retention_days,
        batch_size=batch_size,
    )
    run_id = _run_uuid(run_id)
    execution_time = timezone.now()
    cutoff_at = execution_time - timedelta(days=retention_days)

    with transaction.atomic():
        existing = DataRetentionRecord.objects.select_for_update().filter(
            run_id=run_id
        ).first()
        if existing is not None:
            if not _matching_replay(
                existing,
                category=category,
                policy_version=policy_version,
                retention_days=retention_days,
                batch_size=batch_size,
            ):
                raise RetentionReplayConflictError(
                    "The retention run identifier has conflicting parameters."
                )
            return RetentionResult(
                category=category,
                execution_mode=existing.execution_mode,
                result=existing.result,
                eligible_count=existing.eligible_count,
                processed_count=existing.processed_count,
                replayed=True,
                record=existing,
            )

        records = list(
            _eligible_queryset(category=category, cutoff_at=cutoff_at)
            .select_for_update(of=("self",))
            .order_by("submitted_at" if category == RetentionCategory.SIMULATED_ANSWERS else "created_at", "pk")[:batch_size]
        )
        eligible_count = len(records)
        processed_count = _anonymize_locked_records(
            category=category,
            records=records,
        )
        result = (
            DataRetentionRecord.Result.APPLIED
            if processed_count
            else DataRetentionRecord.Result.NOOP
        )
        record_id = uuid.uuid4()
        audit_event = record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.SYSTEM,
                event_type="retention.applied",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="auditlog.DataRetentionRecord",
                resource_id=record_id,
                actor=None,
                metadata={
                    "eligible_count": eligible_count,
                    "policy_version": policy_version,
                    "processed_count": processed_count,
                    "retention_category": category,
                    "retention_result": result,
                },
            )
        )
        resource_hash = salted_hmac(
            "auditlog.retention.run.v1",
            f"{category}:{run_id}",
            secret=settings.SECRET_KEY,
            algorithm="sha256",
        ).hexdigest()
        record = DataRetentionRecord.objects.create(
            id=record_id,
            run_id=run_id,
            policy_version=policy_version,
            execution_mode=DataRetentionRecord.ExecutionMode.APPLY,
            result=result,
            data_category=category,
            resource_type=RETENTION_RESOURCE_TYPES[category],
            resource_identifier_hash=resource_hash,
            action=DataRetentionRecord.Action.ANONYMIZED,
            retention_days=retention_days,
            batch_size=batch_size,
            eligible_count=eligible_count,
            processed_count=processed_count,
            reason="Policy-based anonymization of eligible private content.",
            performed_at=execution_time,
            cutoff_at=cutoff_at,
            completed_at=execution_time,
            audit_event=audit_event,
            metadata={},
        )
        return RetentionResult(
            category=category,
            execution_mode=record.execution_mode,
            result=record.result,
            eligible_count=record.eligible_count,
            processed_count=record.processed_count,
            record=record,
        )

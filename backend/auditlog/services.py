import json
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from auditlog.models import AuditEvent

MAX_METADATA_KEYS = 20
MAX_METADATA_ITEMS = 20
MAX_METADATA_STRING_LENGTH = 255
MAX_METADATA_JSON_BYTES = 4096

UUID_METADATA_KEYS = frozenset(
    {
        "application_id",
        "cancelled_schedule_id",
        "candidate_id",
        "company_id",
        "interview_schedule_id",
        "job_id",
        "question_id",
        "replaced_resume_id",
        "replacement_schedule_id",
        "replaces_resume_id",
        "request_id",
        "resume_id",
    }
)
IDENTIFIER_LIST_METADATA_KEYS = frozenset({"capabilities", "changed_fields"})
INTEGER_METADATA_KEYS = frozenset(
    {"extracted_character_count", "question_index", "size_bytes"}
)
BOOLEAN_METADATA_KEYS = frozenset({"is_verified", "simulated_mode"})
TIMESTAMP_METADATA_KEYS = frozenset({"invitation_expires_at"})
CODE_METADATA_KEYS = frozenset(
    {
        "collection_source",
        "consent_type",
        "delivery_channel",
        "failure_code",
        "file_type",
        "parser",
        "policy_version",
        "request_kind",
        "reason_code",
        "status_from",
        "status_to",
    }
)
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
SAFE_CODE_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:/+-]{0,119}$")
HEX_DIGEST_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


class DomainAuditError(Exception):
    """Base exception for mandatory domain-audit failures."""


class DomainAuditValidationError(DomainAuditError):
    """Raised when a domain-audit command is not safe or valid."""


class DomainAuditPersistenceError(DomainAuditError):
    """Raised when a validated mandatory audit event cannot be persisted."""


@dataclass(frozen=True, slots=True)
class AuditEventSpec:
    category: str
    resource_type: str
    action: str
    allowed_metadata_keys: frozenset[str] = frozenset()
    required_metadata_keys: frozenset[str] = frozenset()
    actor_required: bool = True
    resource_id_required: bool = True

    def __post_init__(self):
        if (
            not isinstance(self.action, str)
            or not self.action.strip()
            or self.action != self.action.strip()
            or len(self.action) > 160
            or any(ord(character) < 32 for character in self.action)
        ):
            raise ValueError("Audit event specifications require a canonical action.")
        if not self.required_metadata_keys <= self.allowed_metadata_keys:
            raise ValueError(
                "Required audit metadata must be included in the allowed metadata."
            )


@dataclass(frozen=True, slots=True)
class AuditCommand:
    category: str
    event_type: str
    outcome: str
    severity: str
    resource_type: str
    resource_id: uuid.UUID | str | None
    actor: Any | None
    request_id: uuid.UUID | str | None = None
    correlation_id: uuid.UUID | str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


def _spec(
    category: str,
    resource_type: str,
    action: str,
    metadata: set[str] | None = None,
    *,
    required_metadata: set[str] | None = None,
    actor_required: bool = True,
    resource_id_required: bool = True,
) -> AuditEventSpec:
    return AuditEventSpec(
        category=category,
        resource_type=resource_type,
        action=action,
        allowed_metadata_keys=frozenset(metadata or set()),
        required_metadata_keys=frozenset(required_metadata or set()),
        actor_required=actor_required,
        resource_id_required=resource_id_required,
    )


EVENT_SPECS = MappingProxyType(
    {
    # Candidate profile
    "profile.updated": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "candidates.CandidateProfile",
        "Candidate profile updated",
        {"changed_fields"},
        required_metadata={"changed_fields"},
    ),
    # Consent history
    "consent.granted": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "auditlog.ConsentRecord",
        "AI processing consent granted",
        {
            "application_id",
            "candidate_id",
            "collection_source",
            "consent_type",
            "interview_schedule_id",
            "policy_version",
        },
        required_metadata={
            "candidate_id",
            "collection_source",
            "consent_type",
            "policy_version",
        },
    ),
    "consent.revoked": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "auditlog.ConsentRecord",
        "AI processing consent revoked",
        {
            "application_id",
            "candidate_id",
            "collection_source",
            "consent_type",
            "interview_schedule_id",
            "policy_version",
        },
        required_metadata={
            "candidate_id",
            "collection_source",
            "consent_type",
            "policy_version",
        },
    ),
    # Email verification
    "email_verification.requested": _spec(
        AuditEvent.Category.AUTHENTICATION,
        "accounts.EmailVerificationChallenge",
        "Email verification requested",
        {"delivery_channel", "request_kind"},
        required_metadata={"delivery_channel"},
        actor_required=False,
    ),
    "email_verification.succeeded": _spec(
        AuditEvent.Category.AUTHENTICATION,
        "accounts.EmailVerificationChallenge",
        "Email verification completed",
        set(),
        actor_required=False,
    ),
    "email_verification.failed": _spec(
        AuditEvent.Category.SECURITY,
        "accounts.EmailVerificationChallenge",
        "Email verification failed",
        {"failure_code"},
        required_metadata={"failure_code"},
        actor_required=False,
        resource_id_required=False,
    ),
    "email_verification.invalidated": _spec(
        AuditEvent.Category.AUTHENTICATION,
        "accounts.EmailVerificationChallenge",
        "Email verification challenge invalidated",
        {"reason_code"},
        required_metadata={"reason_code"},
        actor_required=False,
    ),
    # Resume lifecycle
    "resume.uploaded": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "candidates.Resume",
        "Resume uploaded",
        {"checksum", "file_type", "replaces_resume_id", "size_bytes"},
        required_metadata={"checksum", "file_type", "size_bytes"},
    ),
    "resume.processing_started": _spec(
        AuditEvent.Category.SYSTEM,
        "candidates.Resume",
        "Resume processing started",
        {"parser"},
        required_metadata={"parser"},
        actor_required=False,
    ),
    "resume.processing_succeeded": _spec(
        AuditEvent.Category.SYSTEM,
        "candidates.Resume",
        "Resume processing completed",
        {"extracted_character_count", "parser"},
        required_metadata={"extracted_character_count", "parser"},
        actor_required=False,
    ),
    "resume.processing_failed": _spec(
        AuditEvent.Category.SYSTEM,
        "candidates.Resume",
        "Resume processing failed",
        {"failure_code", "parser"},
        required_metadata={"failure_code", "parser"},
        actor_required=False,
    ),
    "resume.downloaded": _spec(
        AuditEvent.Category.DATA_ACCESS,
        "candidates.Resume",
        "Resume downloaded",
    ),
    "resume.activated": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "candidates.Resume",
        "Resume activated",
        {"replaced_resume_id"},
    ),
    # Company and recruiter administration
    "company.created": _spec(
        AuditEvent.Category.ADMINISTRATION,
        "recruitment.Company",
        "Company created",
    ),
    "company.updated": _spec(
        AuditEvent.Category.ADMINISTRATION,
        "recruitment.Company",
        "Company updated",
        {"changed_fields"},
        required_metadata={"changed_fields"},
    ),
    "recruiter.provisioned": _spec(
        AuditEvent.Category.ADMINISTRATION,
        "recruitment.RecruiterProfile",
        "Recruiter provisioned",
        {"capabilities", "company_id", "is_verified"},
        required_metadata={"capabilities", "company_id", "is_verified"},
    ),
    "recruiter.updated": _spec(
        AuditEvent.Category.ADMINISTRATION,
        "recruitment.RecruiterProfile",
        "Recruiter updated",
        {"changed_fields"},
        required_metadata={"changed_fields"},
    ),
    # Job workflow
    "job.created": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "recruitment.JobPosting",
        "Job created",
    ),
    "job.updated": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "recruitment.JobPosting",
        "Job updated",
        {"changed_fields"},
        required_metadata={"changed_fields"},
    ),
    "job.published": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "recruitment.JobPosting",
        "Job published",
        {"status_from", "status_to"},
        required_metadata={"status_from", "status_to"},
    ),
    "job.paused": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "recruitment.JobPosting",
        "Job paused",
        {"status_from", "status_to"},
        required_metadata={"status_from", "status_to"},
    ),
    "job.reopened": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "recruitment.JobPosting",
        "Job reopened",
        {"status_from", "status_to"},
        required_metadata={"status_from", "status_to"},
    ),
    "job.closed": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "recruitment.JobPosting",
        "Job closed",
        {"status_from", "status_to"},
        required_metadata={"status_from", "status_to"},
    ),
    "job.archived": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "recruitment.JobPosting",
        "Job archived",
        {"status_from", "status_to"},
        required_metadata={"status_from", "status_to"},
    ),
    # Application workflow
    "application.created": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "recruitment.JobApplication",
        "Job application created",
        {"job_id", "resume_id"},
        required_metadata={"job_id", "resume_id"},
    ),
    "application.status_changed": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "recruitment.JobApplication",
        "Job application status changed",
        {"status_from", "status_to"},
        required_metadata={"status_from", "status_to"},
    ),
    "application.withdrawn": _spec(
        AuditEvent.Category.DATA_CHANGE,
        "recruitment.JobApplication",
        "Job application withdrawn",
        {"cancelled_schedule_id", "status_from", "status_to"},
        required_metadata={"status_from", "status_to"},
    ),
    # Interview scheduling
    "interview.invited": _spec(
        AuditEvent.Category.INTERVIEW,
        "interviews.InterviewSchedule",
        "Interview invitation sent",
        {"application_id", "invitation_expires_at"},
        required_metadata={"application_id", "invitation_expires_at"},
    ),
    "interview.confirmed": _spec(
        AuditEvent.Category.INTERVIEW,
        "interviews.InterviewSchedule",
        "Interview confirmed",
        {"application_id", "status_from", "status_to"},
        required_metadata={"application_id", "status_from", "status_to"},
    ),
    "interview.reschedule_requested": _spec(
        AuditEvent.Category.INTERVIEW,
        "interviews.InterviewSchedule",
        "Interview reschedule requested",
        {"application_id", "request_id"},
        required_metadata={"application_id", "request_id"},
    ),
    "interview.rescheduled": _spec(
        AuditEvent.Category.INTERVIEW,
        "interviews.InterviewSchedule",
        "Interview rescheduled",
        {"application_id", "replacement_schedule_id", "status_from", "status_to"},
        required_metadata={
            "application_id",
            "replacement_schedule_id",
            "status_from",
            "status_to",
        },
    ),
    "interview.cancelled": _spec(
        AuditEvent.Category.INTERVIEW,
        "interviews.InterviewSchedule",
        "Interview cancelled",
        {"application_id", "reason_code", "status_from", "status_to"},
        required_metadata={
            "application_id",
            "reason_code",
            "status_from",
            "status_to",
        },
    ),
    "interview.expired": _spec(
        AuditEvent.Category.INTERVIEW,
        "interviews.InterviewSchedule",
        "Interview invitation expired",
        {"application_id", "status_from", "status_to"},
        required_metadata={"application_id", "status_from", "status_to"},
        actor_required=False,
    ),
    "interview.completed": _spec(
        AuditEvent.Category.INTERVIEW,
        "interviews.InterviewSchedule",
        "Interview completed",
        {"application_id", "status_from", "status_to"},
        required_metadata={"application_id", "status_from", "status_to"},
    ),
    "interview.invitation_delivery_failed": _spec(
        AuditEvent.Category.INTERVIEW,
        "interviews.InterviewSchedule",
        "Interview invitation delivery failed",
        {"application_id", "failure_code"},
        required_metadata={"application_id", "failure_code"},
    ),
    "interview.reschedule_rejected": _spec(
        AuditEvent.Category.INTERVIEW,
        "interviews.InterviewSchedule",
        "Interview reschedule request rejected",
        {"application_id", "request_id"},
        required_metadata={"application_id", "request_id"},
    ),
    # Interview call sessions
    "call_session.created": _spec(
        AuditEvent.Category.INTERVIEW,
        "calling.CallSession",
        "Interview call session created",
        {
            "application_id",
            "interview_schedule_id",
            "simulated_mode",
            "status_to",
        },
        required_metadata={
            "application_id",
            "interview_schedule_id",
            "simulated_mode",
            "status_to",
        },
        actor_required=False,
    ),
    "call_session.ready": _spec(
        AuditEvent.Category.INTERVIEW,
        "calling.CallSession",
        "Interview call session marked ready",
        {"application_id", "interview_schedule_id", "status_from", "status_to"},
        required_metadata={
            "application_id",
            "interview_schedule_id",
            "status_from",
            "status_to",
        },
        actor_required=False,
    ),
    "call_session.started": _spec(
        AuditEvent.Category.INTERVIEW,
        "calling.CallSession",
        "Interview call session started",
        {"application_id", "interview_schedule_id", "status_from", "status_to"},
        required_metadata={
            "application_id",
            "interview_schedule_id",
            "status_from",
            "status_to",
        },
    ),
    "call_session.paused": _spec(
        AuditEvent.Category.INTERVIEW,
        "calling.CallSession",
        "Interview call session paused",
        {"application_id", "interview_schedule_id", "status_from", "status_to"},
        required_metadata={
            "application_id",
            "interview_schedule_id",
            "status_from",
            "status_to",
        },
    ),
    "call_session.resumed": _spec(
        AuditEvent.Category.INTERVIEW,
        "calling.CallSession",
        "Interview call session resumed",
        {"application_id", "interview_schedule_id", "status_from", "status_to"},
        required_metadata={
            "application_id",
            "interview_schedule_id",
            "status_from",
            "status_to",
        },
    ),
    "call_session.completed": _spec(
        AuditEvent.Category.INTERVIEW,
        "calling.CallSession",
        "Interview call session completed",
        {
            "application_id",
            "interview_schedule_id",
            "reason_code",
            "status_from",
            "status_to",
        },
        required_metadata={
            "application_id",
            "interview_schedule_id",
            "reason_code",
            "status_from",
            "status_to",
        },
    ),
    "call_session.cancelled": _spec(
        AuditEvent.Category.INTERVIEW,
        "calling.CallSession",
        "Interview call session cancelled",
        {
            "application_id",
            "interview_schedule_id",
            "reason_code",
            "status_from",
            "status_to",
        },
        required_metadata={
            "application_id",
            "interview_schedule_id",
            "reason_code",
            "status_from",
            "status_to",
        },
    ),
    "call_session.expired": _spec(
        AuditEvent.Category.INTERVIEW,
        "calling.CallSession",
        "Interview call session expired",
        {
            "application_id",
            "interview_schedule_id",
            "reason_code",
            "status_from",
            "status_to",
        },
        required_metadata={
            "application_id",
            "interview_schedule_id",
            "reason_code",
            "status_from",
            "status_to",
        },
        actor_required=False,
    ),
    "call_session.failed": _spec(
        AuditEvent.Category.INTERVIEW,
        "calling.CallSession",
        "Interview call session failed",
        {
            "application_id",
            "failure_code",
            "interview_schedule_id",
            "status_from",
            "status_to",
        },
        required_metadata={
            "application_id",
            "failure_code",
            "interview_schedule_id",
            "status_from",
            "status_to",
        },
        actor_required=False,
    ),
    "call_session.answer_submitted": _spec(
        AuditEvent.Category.INTERVIEW,
        "calling.CallSession",
        "Simulated interview answer submitted",
        {
            "application_id",
            "interview_schedule_id",
            "question_id",
            "question_index",
        },
        required_metadata={
            "application_id",
            "interview_schedule_id",
            "question_id",
            "question_index",
        },
    ),
    }
)


FORBIDDEN_KEY_TERMS = frozenset(
    {
        "credential",
        "database_url",
        "db_password",
        "file_path",
        "filepath",
        "password",
        "private_key",
        "raw_token",
        "resume_content",
        "resume_text",
        "secret",
        "secret_key",
        "token",
        "transcript",
        "transcript_text",
    }
)

FORBIDDEN_VALUE_PATTERNS = (
    re.compile(r"(?i)\b(?:password|passwd|secret(?:_key)?|token)\s*[:=]"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb)://"),
    re.compile(r"^eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$"),
    re.compile(r"(?i)^(?:gh[pousr]_|sk-|xox[baprs]-)"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"^[a-zA-Z]:[\\/]"),
    re.compile(r"^\\\\"),
    re.compile(r"^/"),
    re.compile(r"(?:^|[\\/])\.\.(?:[\\/]|$)"),
    re.compile(r"(?i)^file://"),
)


def _required_text(value: Any, *, field_name: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise DomainAuditValidationError(f"{field_name} must be text.")

    normalized = value.strip()
    if not normalized:
        raise DomainAuditValidationError(f"{field_name} is required.")
    if len(normalized) > max_length:
        raise DomainAuditValidationError(f"{field_name} is too long.")
    if any(ord(character) < 32 for character in normalized):
        raise DomainAuditValidationError(f"{field_name} contains invalid characters.")

    return normalized


def _choice(value: Any, *, field_name: str, choices: set[str]) -> str:
    normalized = _required_text(value, field_name=field_name, max_length=30)
    if normalized not in choices:
        raise DomainAuditValidationError(f"{field_name} is invalid.")
    return normalized


def _uuid(value: uuid.UUID | str | None, *, field_name: str, required: bool):
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise DomainAuditValidationError(f"{field_name} is required.")
        return None

    try:
        return uuid.UUID(str(value).strip())
    except (AttributeError, TypeError, ValueError):
        raise DomainAuditValidationError(f"{field_name} must be a valid UUID.") from None


def _actor(actor: Any | None, *, required: bool):
    if actor is None:
        if required:
            raise DomainAuditValidationError("actor is required.")
        return None

    if not getattr(actor, "is_authenticated", False) or not getattr(actor, "pk", None):
        raise DomainAuditValidationError("actor must be an authenticated persisted user.")

    return actor


def _contains_forbidden_key_term(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    return any(
        normalized == term
        or normalized.startswith(f"{term}_")
        or normalized.endswith(f"_{term}")
        for term in FORBIDDEN_KEY_TERMS
    )


def _safe_string(value: str) -> str:
    if len(value) > MAX_METADATA_STRING_LENGTH:
        raise DomainAuditValidationError("Metadata contains an overlong text value.")
    if any(ord(character) < 32 and character not in "\t" for character in value):
        raise DomainAuditValidationError("Metadata contains invalid characters.")
    if any(pattern.search(value) for pattern in FORBIDDEN_VALUE_PATTERNS):
        raise DomainAuditValidationError("Metadata contains a forbidden value.")
    return value


def _metadata_value(key: str, value: Any):
    if key in UUID_METADATA_KEYS:
        normalized = _uuid(value, field_name="metadata identifier", required=True)
        return str(normalized)

    if key in IDENTIFIER_LIST_METADATA_KEYS:
        if not isinstance(value, Sequence) or isinstance(
            value, (str, bytes, bytearray)
        ):
            raise DomainAuditValidationError("Metadata contains an invalid collection.")
        if len(value) > MAX_METADATA_ITEMS:
            raise DomainAuditValidationError("Metadata contains too many collection items.")

        normalized_items = []
        for item in value:
            if not isinstance(item, str):
                raise DomainAuditValidationError(
                    "Metadata collection items must be safe identifiers."
                )
            item = _safe_string(item)
            if not SAFE_IDENTIFIER_PATTERN.fullmatch(item):
                raise DomainAuditValidationError(
                    "Metadata collection items must be safe identifiers."
                )
            normalized_items.append(item)
        return normalized_items

    if key in INTEGER_METADATA_KEYS:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DomainAuditValidationError("Metadata contains an invalid count.")
        return value

    if key in BOOLEAN_METADATA_KEYS:
        if not isinstance(value, bool):
            raise DomainAuditValidationError("Metadata contains an invalid boolean.")
        return value

    if key == "checksum":
        if not isinstance(value, str) or not HEX_DIGEST_PATTERN.fullmatch(value):
            raise DomainAuditValidationError("Metadata contains an invalid digest.")
        return value.lower()

    if key in TIMESTAMP_METADATA_KEYS:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                raise DomainAuditValidationError(
                    "Metadata contains an invalid timestamp."
                ) from None
        else:
            raise DomainAuditValidationError("Metadata contains an invalid timestamp.")
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise DomainAuditValidationError("Metadata timestamp must include a timezone.")
        return parsed.isoformat()

    if key in CODE_METADATA_KEYS:
        if not isinstance(value, str):
            raise DomainAuditValidationError("Metadata contains an invalid code.")
        value = _safe_string(value)
        if not SAFE_CODE_PATTERN.fullmatch(value):
            raise DomainAuditValidationError("Metadata contains an invalid code.")
        return value

    raise DomainAuditValidationError("Metadata contains an unsupported value type.")


def _metadata(metadata: Mapping[str, Any], *, spec: AuditEventSpec) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        raise DomainAuditValidationError("metadata must be a mapping.")
    if len(metadata) > MAX_METADATA_KEYS:
        raise DomainAuditValidationError("Metadata contains too many keys.")

    for key in metadata:
        if not isinstance(key, str) or _contains_forbidden_key_term(key):
            raise DomainAuditValidationError("Metadata contains a forbidden field name.")
        if key not in spec.allowed_metadata_keys:
            raise DomainAuditValidationError("Metadata contains a key not allowed for this event.")

    if not spec.required_metadata_keys.issubset(metadata):
        raise DomainAuditValidationError("Required metadata is missing.")

    normalized = {}
    for key, value in metadata.items():
        normalized[key] = _metadata_value(key, value)

    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_METADATA_JSON_BYTES:
        raise DomainAuditValidationError("Metadata is too large.")

    return normalized


def record_domain_event(command: AuditCommand) -> AuditEvent:
    """Validate and persist one mandatory, privacy-safe domain audit event."""
    if not isinstance(command, AuditCommand):
        raise DomainAuditValidationError("A valid audit command is required.")

    event_type = _required_text(
        command.event_type,
        field_name="event_type",
        max_length=100,
    )
    spec = EVENT_SPECS.get(event_type)
    if spec is None:
        raise DomainAuditValidationError("event_type is not registered.")

    category = _choice(
        command.category,
        field_name="category",
        choices=set(AuditEvent.Category.values),
    )
    if category != spec.category:
        raise DomainAuditValidationError("category does not match event_type.")

    resource_type = _required_text(
        command.resource_type,
        field_name="resource_type",
        max_length=120,
    )
    if resource_type != spec.resource_type:
        raise DomainAuditValidationError("resource_type does not match event_type.")

    actor = _actor(command.actor, required=spec.actor_required)
    resource_id = _uuid(
        command.resource_id,
        field_name="resource_id",
        required=spec.resource_id_required,
    )
    request_id = _uuid(command.request_id, field_name="request_id", required=False)
    correlation_id = _uuid(
        command.correlation_id,
        field_name="correlation_id",
        required=False,
    )
    outcome = _choice(
        command.outcome,
        field_name="outcome",
        choices=set(AuditEvent.Outcome.values),
    )
    severity = _choice(
        command.severity,
        field_name="severity",
        choices=set(AuditEvent.Severity.values),
    )
    metadata = _metadata(command.metadata, spec=spec)

    try:
        return AuditEvent.objects.create(
            actor=actor,
            category=category,
            event_type=event_type,
            action=spec.action,
            outcome=outcome,
            severity=severity,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else "",
            request_id=request_id,
            correlation_id=correlation_id,
            metadata=metadata,
        )
    except DomainAuditError:
        raise
    except Exception:
        raise DomainAuditPersistenceError(
            "The mandatory audit event could not be recorded."
        ) from None

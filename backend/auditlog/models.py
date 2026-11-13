import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class AuditEvent(models.Model):
    class Category(models.TextChoices):
        AUTHENTICATION = "authentication", "Authentication"
        AUTHORIZATION = "authorization", "Authorization"
        DATA_ACCESS = "data_access", "Data access"
        DATA_CHANGE = "data_change", "Data change"
        AGENT_ACTION = "agent_action", "Agent action"
        INTERVIEW = "interview", "Interview"
        ADMINISTRATION = "administration", "Administration"
        SECURITY = "security", "Security"
        SYSTEM = "system", "System"

    class Outcome(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"
        DENIED = "denied", "Denied"
        WARNING = "warning", "Warning"

    class Severity(models.TextChoices):
        INFO = "info", "Information"
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    event_timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        editable=False,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    actor_email_snapshot = models.EmailField(
        blank=True,
        editable=False,
    )
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        db_index=True,
    )
    event_type = models.CharField(
        max_length=100,
        db_index=True,
    )
    action = models.CharField(max_length=160)
    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        db_index=True,
    )
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.INFO,
        db_index=True,
    )
    resource_type = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
    )
    resource_id = models.CharField(
        max_length=255,
        blank=True,
    )
    request_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )
    correlation_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )
    ip_address_hash = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
    )
    user_agent_summary = models.CharField(
        max_length=255,
        blank=True,
    )
    description = models.TextField(blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
    )
    previous_event_hash = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
    )
    event_hash = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
    )

    class Meta:
        ordering = ("-event_timestamp",)
        indexes = [
            models.Index(fields=("category", "event_timestamp")),
            models.Index(fields=("actor", "event_timestamp")),
            models.Index(fields=("resource_type", "resource_id")),
            models.Index(fields=("severity", "outcome", "event_timestamp")),
        ]

    def build_event_hash(self):
        payload = {
            "id": str(self.id),
            "timestamp": self.event_timestamp.isoformat(),
            "actor_id": str(self.actor_id or ""),
            "actor_email": self.actor_email_snapshot,
            "category": self.category,
            "event_type": self.event_type,
            "action": self.action,
            "outcome": self.outcome,
            "severity": self.severity,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "ip_address_hash": self.ip_address_hash,
            "user_agent_summary": self.user_agent_summary,
            "request_id": str(self.request_id or ""),
            "correlation_id": str(self.correlation_id or ""),
            "description": self.description,
            "metadata": self.metadata,
            "previous_event_hash": self.previous_event_hash,
        }

        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

        return hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            serialized.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Audit events are immutable and cannot be modified.")

        if self.actor and not self.actor_email_snapshot:
            self.actor_email_snapshot = self.actor.email

        self.event_hash = self.build_event_hash()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events are immutable and cannot be deleted.")

    def __str__(self):
        return f"{self.event_type} — {self.outcome}"


class ConsentRecord(models.Model):
    class ConsentType(models.TextChoices):
        GENERAL_AI_PROCESSING = (
            "general_ai_processing",
            "General AI processing",
        )
        AI_INTERVIEW = "ai_interview", "AI interview"

    class Action(models.TextChoices):
        GRANTED = "granted", "Granted"
        REVOKED = "revoked", "Revoked"

    class CollectionSource(models.TextChoices):
        PROFILE = "profile", "Profile"
        APPLICATION = "application", "Application"
        INTERVIEW_CONFIRMATION = (
            "interview_confirmation",
            "Interview confirmation",
        )
        ADMIN_ASSISTED = "admin_assisted", "Administrator assisted"
        LEGACY_IMPORT = "legacy_import", "Legacy import"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    candidate = models.ForeignKey(
        "candidates.CandidateProfile",
        on_delete=models.PROTECT,
        related_name="consent_records",
    )
    consent_type = models.CharField(
        max_length=40,
        choices=ConsentType.choices,
    )
    action = models.CharField(
        max_length=10,
        choices=Action.choices,
    )
    policy_version = models.CharField(max_length=100)
    collection_source = models.CharField(
        max_length=30,
        choices=CollectionSource.choices,
    )
    application = models.ForeignKey(
        "recruitment.JobApplication",
        on_delete=models.PROTECT,
        related_name="consent_records",
        null=True,
        blank=True,
    )
    interview_schedule = models.ForeignKey(
        "interviews.InterviewSchedule",
        on_delete=models.PROTECT,
        related_name="consent_records",
        null=True,
        blank=True,
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_consents",
        null=True,
        blank=True,
    )
    recorded_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
    )
    idempotency_key = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    request_id = models.UUIDField(null=True, blank=True)
    correlation_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ("-recorded_at", "-id")
        indexes = [
            models.Index(
                fields=("candidate", "consent_type", "recorded_at"),
                name="consent_candidate_type_time",
            ),
            models.Index(
                fields=("application", "consent_type", "recorded_at"),
                name="consent_app_type_time",
            ),
            models.Index(
                fields=("interview_schedule", "recorded_at"),
                name="consent_schedule_time",
            ),
            models.Index(
                fields=("action", "recorded_at"),
                name="consent_action_time",
            ),
            models.Index(fields=("request_id",), name="consent_request_id"),
            models.Index(
                fields=("correlation_id",),
                name="consent_correlation_id",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~Q(consent_type="general_ai_processing")
                    | (
                        Q(application__isnull=True)
                        & Q(interview_schedule__isnull=True)
                    )
                ),
                name="consent_general_no_context",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(consent_type="ai_interview")
                    | Q(application__isnull=False)
                ),
                name="consent_interview_has_app",
            ),
            models.CheckConstraint(
                condition=(
                    Q(interview_schedule__isnull=True)
                    | Q(application__isnull=False)
                ),
                name="consent_schedule_has_app",
            ),
            models.CheckConstraint(
                condition=(
                    Q(collection_source="legacy_import")
                    | Q(recorded_by__isnull=False)
                ),
                name="consent_nonlegacy_has_actor",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Consent records are immutable and cannot be modified.")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Consent records are immutable and cannot be deleted.")

    def __str__(self):
        return f"{self.consent_type}: {self.action}"


class SecurityIncident(models.Model):
    class Category(models.TextChoices):
        AUTHENTICATION = "authentication", "Authentication attack"
        AUTHORIZATION = "authorization", "Unauthorized access"
        DATA_EXPOSURE = "data_exposure", "Potential data exposure"
        MALICIOUS_INPUT = "malicious_input", "Malicious input"
        AGENT_SAFETY = "agent_safety", "Agent safety violation"
        SERVICE_ABUSE = "service_abuse", "Service abuse"
        SYSTEM = "system", "System security failure"

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        INVESTIGATING = "investigating", "Investigating"
        CONTAINED = "contained", "Contained"
        RESOLVED = "resolved", "Resolved"
        FALSE_POSITIVE = "false_positive", "False positive"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    title = models.CharField(max_length=200)
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        db_index=True,
    )
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    description = models.TextField()
    related_events = models.ManyToManyField(
        AuditEvent,
        related_name="security_incidents",
        blank=True,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_security_incidents",
        null=True,
        blank=True,
    )
    containment_actions = models.TextField(blank=True)
    resolution_notes = models.TextField(blank=True)
    detected_at = models.DateTimeField(default=timezone.now)
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-detected_at",)
        indexes = [
            models.Index(fields=("status", "severity", "detected_at")),
            models.Index(fields=("category", "status")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(resolved_at__isnull=True) | Q(resolved_at__gte=F("detected_at"))
                ),
                name="incident_resolution_after_detection",
            ),
        ]

    def __str__(self):
        return f"{self.title} — {self.severity}"


class DataRetentionRecord(models.Model):
    class Action(models.TextChoices):
        SCHEDULED = "scheduled", "Deletion scheduled"
        ANONYMIZED = "anonymized", "Data anonymized"
        DELETED = "deleted", "Data deleted"
        RETAINED = "retained", "Retention extended"
        FAILED = "failed", "Retention action failed"

    class ExecutionMode(models.TextChoices):
        LEGACY = "legacy", "Legacy record"
        DRY_RUN = "dry_run", "Dry run"
        APPLY = "apply", "Applied mutation"

    class Result(models.TextChoices):
        LEGACY = "legacy", "Legacy result"
        PREVIEWED = "previewed", "Previewed"
        APPLIED = "applied", "Applied"
        NOOP = "noop", "No eligible records"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    run_id = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )
    policy_version = models.CharField(
        max_length=100,
        default="legacy-unversioned",
    )
    execution_mode = models.CharField(
        max_length=20,
        choices=ExecutionMode.choices,
        default=ExecutionMode.LEGACY,
    )
    result = models.CharField(
        max_length=20,
        choices=Result.choices,
        default=Result.LEGACY,
    )
    data_category = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=120)
    resource_identifier_hash = models.CharField(max_length=64)
    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        db_index=True,
    )
    retention_days = models.PositiveIntegerField(default=0)
    batch_size = models.PositiveIntegerField(default=0)
    eligible_count = models.PositiveIntegerField(default=0)
    processed_count = models.PositiveIntegerField(default=0)
    reason = models.TextField()
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="data_retention_actions",
        null=True,
        blank=True,
    )
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
    )
    performed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    cutoff_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    audit_event = models.ForeignKey(
        AuditEvent,
        on_delete=models.PROTECT,
        related_name="retention_records",
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("action", "created_at")),
            models.Index(fields=("resource_type", "resource_identifier_hash")),
            models.Index(
                fields=("data_category", "policy_version", "cutoff_at"),
                name="ret_category_policy_cutoff",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(processed_count__lte=F("eligible_count")),
                name="retention_processed_lte_eligible",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(execution_mode="apply")
                    | Q(
                        audit_event__isnull=False,
                        batch_size__gte=1,
                        completed_at__isnull=False,
                        cutoff_at__isnull=False,
                        retention_days__gte=1,
                        run_id__isnull=False,
                    )
                ),
                name="retention_apply_has_evidence",
            ),
        ]

    def __str__(self):
        return f"{self.data_category}: {self.action}"

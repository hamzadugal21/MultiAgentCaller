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

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    data_category = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=120)
    resource_identifier_hash = models.CharField(max_length=64)
    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        db_index=True,
    )
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
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("action", "created_at")),
            models.Index(fields=("resource_type", "resource_identifier_hash")),
        ]

    def __str__(self):
        return f"{self.data_category}: {self.action}"

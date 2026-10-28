import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from calling.models import CallSession
from recruitment.models import JobApplication


class AgentDefinition(models.Model):
    class AgentType(models.TextChoices):
        ORCHESTRATOR = "orchestrator", "Calling orchestrator"
        PROFILE = "profile", "Candidate profile agent"
        INTERVIEW = "interview", "Interview agent"
        EVALUATION = "evaluation", "Evaluation agent"
        FAQ = "faq", "FAQ agent"
        SCHEDULING = "scheduling", "Scheduling agent"
        SAFETY = "safety", "Safety agent"
        ESCALATION = "escalation", "Escalation agent"
        AUDIT = "audit", "Audit agent"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180)
    agent_type = models.CharField(
        max_length=30,
        choices=AgentType.choices,
        db_index=True,
    )
    version = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    model_name = models.CharField(max_length=120, blank=True)
    prompt_template = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    permitted_tools = models.JSONField(default=list, blank=True)
    timeout_seconds = models.PositiveIntegerField(default=30)
    maximum_retries = models.PositiveSmallIntegerField(default=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("agent_type", "-version")
        constraints = [
            models.UniqueConstraint(
                fields=("slug", "version"),
                name="unique_agent_version",
            ),
            models.UniqueConstraint(
                fields=("slug",),
                condition=Q(is_active=True),
                name="one_active_agent_version",
            ),
        ]

    def __str__(self):
        return f"{self.name} v{self.version}"


class AgentRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        TIMED_OUT = "timed_out", "Timed out"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    correlation_id = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        editable=False,
    )
    agent = models.ForeignKey(
        AgentDefinition,
        on_delete=models.PROTECT,
        related_name="runs",
    )
    call_session = models.ForeignKey(
        CallSession,
        on_delete=models.CASCADE,
        related_name="agent_runs",
        null=True,
        blank=True,
    )
    application = models.ForeignKey(
        JobApplication,
        on_delete=models.PROTECT,
        related_name="agent_runs",
        null=True,
        blank=True,
    )
    parent_run = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="child_runs",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    input_context = models.JSONField(default=dict, blank=True)
    output_result = models.JSONField(default=dict, blank=True)
    decision_summary = models.TextField(blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    retry_number = models.PositiveSmallIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=("call_session", "status")),
            models.Index(fields=("application", "status")),
            models.Index(fields=("agent", "status", "created_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(call_session__isnull=False) | Q(application__isnull=False)
                ),
                name="agent_run_requires_context",
            ),
            models.CheckConstraint(
                condition=(
                    Q(completed_at__isnull=True)
                    | Q(started_at__isnull=True)
                    | Q(completed_at__gte=F("started_at"))
                ),
                name="agent_run_completion_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.agent.slug}: {self.status}"


class AgentAction(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        BLOCKED = "blocked", "Blocked"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    agent_run = models.ForeignKey(
        AgentRun,
        on_delete=models.CASCADE,
        related_name="actions",
    )
    sequence_number = models.PositiveIntegerField()
    action_type = models.CharField(max_length=80)
    tool_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    input_summary = models.JSONField(default=dict, blank=True)
    output_summary = models.JSONField(default=dict, blank=True)
    requires_human_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_agent_actions",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("agent_run", "sequence_number")
        constraints = [
            models.UniqueConstraint(
                fields=("agent_run", "sequence_number"),
                name="unique_action_sequence_per_run",
            ),
        ]

    def __str__(self):
        return f"{self.agent_run_id} — {self.action_type}"


class AgentHandoff(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    call_session = models.ForeignKey(
        CallSession,
        on_delete=models.CASCADE,
        related_name="agent_handoffs",
    )
    from_agent = models.ForeignKey(
        AgentDefinition,
        on_delete=models.PROTECT,
        related_name="outgoing_handoffs",
    )
    to_agent = models.ForeignKey(
        AgentDefinition,
        on_delete=models.PROTECT,
        related_name="incoming_handoffs",
    )
    reason = models.CharField(max_length=255)
    context_summary = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("occurred_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(from_agent=F("to_agent")),
                name="agent_handoff_different_agents",
            ),
        ]

    def __str__(self):
        return f"{self.from_agent.slug} → {self.to_agent.slug}"


class AgentEscalation(models.Model):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    class Category(models.TextChoices):
        SAFETY = "safety", "Safety concern"
        PRIVACY = "privacy", "Privacy concern"
        BIAS = "bias", "Potential bias"
        TECHNICAL = "technical", "Technical failure"
        CANDIDATE_REQUEST = "candidate_request", "Candidate requested human"
        POLICY = "policy", "Policy violation"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    call_session = models.ForeignKey(
        CallSession,
        on_delete=models.CASCADE,
        related_name="escalations",
    )
    detected_by = models.ForeignKey(
        AgentDefinition,
        on_delete=models.PROTECT,
        related_name="detected_escalations",
        null=True,
        blank=True,
    )
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
    reason_code = models.CharField(max_length=80, blank=True)
    idempotency_key = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )
    evidence_summary = models.JSONField(default=dict, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_agent_escalations",
        null=True,
        blank=True,
    )
    resolution_notes = models.TextField(blank=True)
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "severity", "created_at")),
            models.Index(fields=("call_session", "status")),
        ]

    def __str__(self):
        return f"{self.category} — {self.severity}"

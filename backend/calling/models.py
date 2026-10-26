import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from interviews.models import InterviewSchedule


class CallSession(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        READY = "ready", "Ready"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    schedule = models.ForeignKey(
        InterviewSchedule,
        on_delete=models.PROTECT,
        related_name="call_sessions",
    )
    attempt_number = models.PositiveSmallIntegerField(default=1)
    creation_idempotency_key = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    simulated_mode = models.BooleanField(default=True)
    completion_reason = models.CharField(max_length=80, blank=True)
    current_question_index = models.PositiveIntegerField(default=0)
    browser_access_token_hash = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )
    websocket_channel_name = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
    )
    language_code = models.CharField(
        max_length=10,
        default="en",
    )
    speech_to_text_engine = models.CharField(
        max_length=100,
        default="faster-whisper",
    )
    text_to_speech_engine = models.CharField(
        max_length=100,
        default="piper",
    )
    voice_activity_engine = models.CharField(
        max_length=100,
        default="silero-vad",
    )
    model_configuration = models.JSONField(
        default=dict,
        blank=True,
    )
    candidate_consent = models.BooleanField(default=False)
    consent_recorded_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    client_ip_hash = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
    )
    recording_enabled = models.BooleanField(default=False)
    recording_file = models.FileField(
        upload_to="protected-call-recordings/%Y/%m/",
        null=True,
        blank=True,
    )
    audio_retention_until = models.DateTimeField(
        null=True,
        blank=True,
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    last_activity_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    duration_seconds = models.PositiveIntegerField(default=0)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.TextField(blank=True)
    termination_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "created_at")),
            models.Index(fields=("schedule", "status")),
            models.Index(
                fields=("status", "expires_at"),
                name="call_status_expires",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("schedule",),
                name="unique_call_session_per_schedule",
            ),
            models.CheckConstraint(
                condition=(
                    Q(ended_at__isnull=True)
                    | Q(started_at__isnull=True)
                    | Q(ended_at__gte=F("started_at"))
                ),
                name="call_end_not_before_start",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status__in=("pending", "ready"), started_at__isnull=True)
                    | Q(
                        status__in=("active", "paused", "completed"),
                        started_at__isnull=False,
                    )
                    | Q(status__in=("cancelled", "expired", "failed"))
                ),
                name="call_started_state_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status__in=("pending", "ready", "active", "paused"),
                        ended_at__isnull=True,
                    )
                    | Q(
                        status__in=(
                            "completed",
                            "cancelled",
                            "expired",
                            "failed",
                        ),
                        ended_at__isnull=False,
                    )
                ),
                name="call_terminal_end_consistent",
            ),
        ]

    def __str__(self):
        return f"Call {self.id} — {self.status}"


class TranscriptSegment(models.Model):
    class Speaker(models.TextChoices):
        CANDIDATE = "candidate", "Candidate"
        AGENT = "agent", "AI agent"
        SYSTEM = "system", "System"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    call_session = models.ForeignKey(
        CallSession,
        on_delete=models.CASCADE,
        related_name="transcript_segments",
    )
    sequence_number = models.PositiveIntegerField()
    speaker = models.CharField(
        max_length=20,
        choices=Speaker.choices,
    )
    text = models.TextField()
    redacted_text = models.TextField(blank=True)
    start_time_ms = models.PositiveBigIntegerField()
    end_time_ms = models.PositiveBigIntegerField()
    confidence = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ],
    )
    language_code = models.CharField(
        max_length=10,
        default="en",
    )
    is_final = models.BooleanField(default=True)
    contains_sensitive_data = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("call_session", "sequence_number")
        constraints = [
            models.UniqueConstraint(
                fields=("call_session", "sequence_number"),
                name="unique_transcript_sequence_per_call",
            ),
            models.CheckConstraint(
                condition=Q(end_time_ms__gte=F("start_time_ms")),
                name="transcript_end_not_before_start",
            ),
            models.CheckConstraint(
                condition=(
                    Q(confidence__isnull=True) | Q(confidence__gte=0, confidence__lte=1)
                ),
                name="transcript_confidence_0_to_1",
            ),
        ]
        indexes = [
            models.Index(fields=("call_session", "speaker")),
            models.Index(fields=("call_session", "created_at")),
        ]

    def __str__(self):
        return f"{self.call_session_id} #{self.sequence_number} — {self.speaker}"


class CallEvent(models.Model):
    class EventType(models.TextChoices):
        SESSION_CREATED = "session_created", "Session created"
        CONNECTED = "connected", "Connected"
        DISCONNECTED = "disconnected", "Disconnected"
        RECONNECTED = "reconnected", "Reconnected"
        SPEECH_STARTED = "speech_started", "Speech started"
        SPEECH_ENDED = "speech_ended", "Speech ended"
        AGENT_CHANGED = "agent_changed", "Agent changed"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        SESSION_ENDED = "session_ended", "Session ended"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    call_session = models.ForeignKey(
        CallSession,
        on_delete=models.CASCADE,
        related_name="events",
    )
    sequence_number = models.PositiveIntegerField()
    event_type = models.CharField(
        max_length=40,
        choices=EventType.choices,
        db_index=True,
    )
    payload = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("call_session", "sequence_number")
        constraints = [
            models.UniqueConstraint(
                fields=("call_session", "sequence_number"),
                name="unique_event_sequence_per_call",
            ),
        ]
        indexes = [
            models.Index(fields=("call_session", "event_type")),
        ]

    def __str__(self):
        return f"{self.call_session_id}: {self.event_type}"


class CallMetric(models.Model):
    class MetricName(models.TextChoices):
        STT_LATENCY = "stt_latency_ms", "Speech-to-text latency"
        AGENT_LATENCY = "agent_latency_ms", "Agent response latency"
        TTS_LATENCY = "tts_latency_ms", "Text-to-speech latency"
        ROUND_TRIP = "round_trip_ms", "Complete response latency"
        PACKET_LOSS = "packet_loss_percent", "Packet loss"
        AUDIO_LEVEL = "audio_level", "Audio level"
        RECONNECT_COUNT = "reconnect_count", "Reconnect count"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    call_session = models.ForeignKey(
        CallSession,
        on_delete=models.CASCADE,
        related_name="metrics",
    )
    metric_name = models.CharField(
        max_length=40,
        choices=MetricName.choices,
        db_index=True,
    )
    value = models.DecimalField(
        max_digits=14,
        decimal_places=4,
    )
    unit = models.CharField(max_length=30)
    metadata = models.JSONField(default=dict, blank=True)
    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("recorded_at",)
        indexes = [
            models.Index(fields=("call_session", "metric_name", "recorded_at")),
        ]

    def __str__(self):
        return f"{self.metric_name}: {self.value} {self.unit}"

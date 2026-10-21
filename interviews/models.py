import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from recruitment.models import JobApplication, JobPosting


class InterviewSchedule(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        RESCHEDULED = "rescheduled", "Rescheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    application = models.ForeignKey(
        JobApplication,
        on_delete=models.PROTECT,
        related_name="interview_schedules",
    )
    scheduled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="scheduled_interviews",
        null=True,
        blank=True,
    )
    scheduled_start = models.DateTimeField(db_index=True)
    scheduled_end = models.DateTimeField()
    timezone = models.CharField(
        max_length=64,
        default="Asia/Karachi",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    access_token_hash = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )
    invitation_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    cancellation_reason = models.TextField(blank=True)
    candidate_instructions = models.TextField(blank=True)
    reschedule_count = models.PositiveSmallIntegerField(default=0)
    is_current = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("scheduled_start",)
        indexes = [
            models.Index(fields=("status", "scheduled_start")),
            models.Index(fields=("application", "status")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(scheduled_end__gt=F("scheduled_start")),
                name="interview_end_after_start",
            ),
            models.UniqueConstraint(
                fields=("application",),
                condition=Q(is_current=True),
                name="one_current_schedule_per_application",
            ),
        ]

    def __str__(self):
        return f"{self.application.candidate.user.email} — {self.scheduled_start}"


class EvaluationRubric(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    job = models.ForeignKey(
        JobPosting,
        on_delete=models.CASCADE,
        related_name="evaluation_rubrics",
    )
    name = models.CharField(max_length=160)
    version = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    passing_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=60,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("job", "-version")
        constraints = [
            models.UniqueConstraint(
                fields=("job", "version"),
                name="unique_rubric_version_per_job",
            ),
            models.UniqueConstraint(
                fields=("job",),
                condition=Q(is_active=True),
                name="one_active_rubric_per_job",
            ),
        ]

    def __str__(self):
        return f"{self.job.title} — {self.name} v{self.version}"


class EvaluationCriterion(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    rubric = models.ForeignKey(
        EvaluationRubric,
        on_delete=models.CASCADE,
        related_name="criteria",
    )
    name = models.CharField(max_length=160)
    description = models.TextField()
    order = models.PositiveSmallIntegerField()
    weight = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ],
    )
    scoring_guidance = models.TextField(blank=True)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ("rubric", "order")
        constraints = [
            models.UniqueConstraint(
                fields=("rubric", "order"),
                name="unique_criterion_order_per_rubric",
            ),
            models.CheckConstraint(
                condition=Q(weight__gte=0, weight__lte=1),
                name="criterion_weight_0_to_1",
            ),
        ]

    def __str__(self):
        return f"{self.rubric.name}: {self.name}"


class CandidateEvaluation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        REVIEWED = "reviewed", "Human reviewed"
        FAILED = "failed", "Failed"

    class Recommendation(models.TextChoices):
        STRONG_YES = "strong_yes", "Strong yes"
        YES = "yes", "Yes"
        REVIEW = "review", "Needs review"
        NO = "no", "No"
        STRONG_NO = "strong_no", "Strong no"

    class EvaluatorType(models.TextChoices):
        AI = "ai", "AI"
        HUMAN = "human", "Human"
        HYBRID = "hybrid", "AI with human review"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    application = models.ForeignKey(
        JobApplication,
        on_delete=models.PROTECT,
        related_name="evaluations",
    )
    rubric = models.ForeignKey(
        EvaluationRubric,
        on_delete=models.PROTECT,
        related_name="evaluations",
    )
    evaluator_type = models.CharField(
        max_length=20,
        choices=EvaluatorType.choices,
        default=EvaluatorType.AI,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    overall_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )
    recommendation = models.CharField(
        max_length=20,
        choices=Recommendation.choices,
        blank=True,
    )
    summary = models.TextField(blank=True)
    strengths = models.JSONField(default=list, blank=True)
    concerns = models.JSONField(default=list, blank=True)
    model_name = models.CharField(max_length=120, blank=True)
    model_version = models.CharField(max_length=80, blank=True)
    prompt_version = models.CharField(max_length=80, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_evaluations",
        null=True,
        blank=True,
    )
    reviewer_notes = models.TextField(blank=True)
    is_final = models.BooleanField(default=False)
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
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("application",),
                condition=Q(is_final=True),
                name="one_final_evaluation_per_application",
            ),
            models.CheckConstraint(
                condition=(
                    Q(overall_score__isnull=True)
                    | Q(overall_score__gte=0, overall_score__lte=100)
                ),
                name="evaluation_score_0_to_100",
            ),
        ]
        indexes = [
            models.Index(fields=("application", "status")),
            models.Index(fields=("recommendation", "is_final")),
        ]

    def __str__(self):
        return f"Evaluation: {self.application}"


class CriterionScore(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    evaluation = models.ForeignKey(
        CandidateEvaluation,
        on_delete=models.CASCADE,
        related_name="criterion_scores",
    )
    criterion = models.ForeignKey(
        EvaluationCriterion,
        on_delete=models.PROTECT,
        related_name="scores",
    )
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )
    confidence = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ],
    )
    evidence = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("criterion__order",)
        constraints = [
            models.UniqueConstraint(
                fields=("evaluation", "criterion"),
                name="unique_criterion_score_per_evaluation",
            ),
            models.CheckConstraint(
                condition=Q(score__gte=0, score__lte=100),
                name="criterion_score_0_to_100",
            ),
            models.CheckConstraint(
                condition=Q(confidence__gte=0, confidence__lte=1),
                name="criterion_confidence_0_to_1",
            ),
        ]

    def __str__(self):
        return f"{self.criterion.name}: {self.score}"

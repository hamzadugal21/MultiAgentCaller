import uuid
from pathlib import Path

from django.conf import settings
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.db.models.functions import Lower

from .validators import validate_resume_file

phone_validator = RegexValidator(
    regex=r"^\+?[1-9]\d{7,14}$",
    message="Enter a valid international phone number.",
)


def resume_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    safe_filename = f"{uuid.uuid4().hex}{extension}"

    return f"candidate-resumes/{instance.candidate_id}/{safe_filename}"


class CandidateProfile(models.Model):
    class Availability(models.TextChoices):
        AVAILABLE = "available", "Available"
        EMPLOYED = "employed", "Currently employed"
        NOT_AVAILABLE = "not_available", "Not available"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    phone_number = models.CharField(
        max_length=16,
        blank=True,
        validators=[phone_validator],
    )
    city = models.CharField(max_length=100, blank=True)
    country_code = models.CharField(
        max_length=2,
        default="PK",
    )
    timezone = models.CharField(
        max_length=64,
        default="Asia/Karachi",
    )
    professional_summary = models.TextField(blank=True)
    years_of_experience = models.PositiveSmallIntegerField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(60),
        ],
    )
    availability = models.CharField(
        max_length=20,
        choices=Availability.choices,
        default=Availability.AVAILABLE,
    )
    ai_processing_consent = models.BooleanField(default=False)
    consent_recorded_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    profile_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Candidate: {self.user.email}"


class Skill(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(max_length=100)
    normalized_name = models.CharField(
        max_length=100,
        blank=True,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_skill_name_case_insensitive",
            ),
        ]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.normalized_name = self.name.casefold()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class CandidateSkill(models.Model):
    class Source(models.TextChoices):
        SELF_REPORTED = "self_reported", "Self-reported"
        RESUME = "resume", "Extracted from resume"
        AGENT = "agent", "Verified by AI agent"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="candidate_skills",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="candidate_skills",
    )
    proficiency = models.PositiveSmallIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
    )
    years_of_experience = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(60),
        ],
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.SELF_REPORTED,
    )
    confidence_score = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=1,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("skill__name",)
        constraints = [
            models.UniqueConstraint(
                fields=("candidate", "skill"),
                name="unique_candidate_skill",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    proficiency__gte=1,
                    proficiency__lte=5,
                ),
                name="candidate_skill_proficiency_1_to_5",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    confidence_score__gte=0,
                    confidence_score__lte=1,
                ),
                name="candidate_skill_confidence_0_to_1",
            ),
        ]

    def __str__(self):
        return f"{self.candidate.user.email}: {self.skill.name}"


class Resume(models.Model):
    class ProcessingStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="resumes",
    )
    file = models.FileField(
        upload_to=resume_upload_path,
        validators=[validate_resume_file],
    )
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField(default=0)
    sha256_checksum = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
    )
    mime_type = models.CharField(max_length=100, blank=True)
    extracted_text = models.TextField(blank=True)
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    processing_error = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-uploaded_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("candidate",),
                condition=models.Q(is_active=True),
                name="one_active_resume_per_candidate",
            ),
        ]

    def __str__(self):
        return f"{self.candidate.user.email}: {self.original_filename}"

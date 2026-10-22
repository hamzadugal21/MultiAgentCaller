import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils.text import slugify

from candidates.models import CandidateProfile, Resume, Skill


class Company(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=230,
        unique=True,
        blank=True,
    )
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    industry = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("name"),
                name="unique_company_name_case_insensitive",
            ),
        ]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()

        if not self.slug:
            base_slug = slugify(self.name)[:190] or "company"
            self.slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class RecruiterProfile(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recruiter_profile",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="recruiters",
    )
    job_title = models.CharField(max_length=120, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    can_manage_jobs = models.BooleanField(default=True)
    can_review_candidates = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("company__name", "user__email")

    def __str__(self):
        return f"{self.user.email} — {self.company.name}"


class JobPosting(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"
        ARCHIVED = "archived", "Archived"

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full time"
        PART_TIME = "part_time", "Part time"
        CONTRACT = "contract", "Contract"
        INTERNSHIP = "internship", "Internship"

    class WorkplaceType(models.TextChoices):
        ON_SITE = "on_site", "On-site"
        HYBRID = "hybrid", "Hybrid"
        REMOTE = "remote", "Remote"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="jobs",
    )
    created_by = models.ForeignKey(
        RecruiterProfile,
        on_delete=models.PROTECT,
        related_name="created_jobs",
    )
    title = models.CharField(max_length=200)
    reference_code = models.CharField(
        max_length=40,
        unique=True,
    )
    description = models.TextField()
    responsibilities = models.TextField(blank=True)
    minimum_qualifications = models.TextField(blank=True)
    preferred_qualifications = models.TextField(blank=True)
    location = models.CharField(max_length=160, blank=True)
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    workplace_type = models.CharField(
        max_length=20,
        choices=WorkplaceType.choices,
        default=WorkplaceType.ON_SITE,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    minimum_experience_years = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(60)],
    )
    maximum_experience_years = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(60)],
    )
    salary_minimum = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    salary_maximum = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    salary_currency = models.CharField(
        max_length=3,
        default="PKR",
    )
    application_deadline = models.DateTimeField(
        null=True,
        blank=True,
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    required_skills = models.ManyToManyField(
        Skill,
        through="JobSkillRequirement",
        related_name="job_postings",
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "created_at")),
            models.Index(fields=("company", "status")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(maximum_experience_years__isnull=True)
                    | Q(maximum_experience_years__gte=F("minimum_experience_years"))
                ),
                name="job_valid_experience_range",
            ),
            models.CheckConstraint(
                condition=(
                    Q(salary_minimum__isnull=True)
                    | Q(salary_maximum__isnull=True)
                    | Q(salary_maximum__gte=F("salary_minimum"))
                ),
                name="job_valid_salary_range",
            ),
        ]

    def __str__(self):
        return f"{self.title} — {self.company.name}"


class JobSkillRequirement(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    job = models.ForeignKey(
        JobPosting,
        on_delete=models.CASCADE,
        related_name="skill_requirements",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="job_requirements",
    )
    minimum_proficiency = models.PositiveSmallIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
    )
    minimum_years = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(60),
        ],
    )
    weight = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=1,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ],
    )
    is_mandatory = models.BooleanField(default=False)

    class Meta:
        ordering = ("-is_mandatory", "skill__name")
        constraints = [
            models.UniqueConstraint(
                fields=("job", "skill"),
                name="unique_job_skill_requirement",
            ),
            models.CheckConstraint(
                condition=Q(
                    minimum_proficiency__gte=1,
                    minimum_proficiency__lte=5,
                ),
                name="job_skill_proficiency_1_to_5",
            ),
            models.CheckConstraint(
                condition=Q(weight__gte=0, weight__lte=1),
                name="job_skill_weight_0_to_1",
            ),
        ]

    def __str__(self):
        return f"{self.job.title}: {self.skill.name}"


class JobApplication(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        SCREENING = "screening", "Screening"
        INVITED = "invited", "Interview invited"
        INTERVIEWED = "interviewed", "Interviewed"
        SHORTLISTED = "shortlisted", "Shortlisted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    job = models.ForeignKey(
        JobPosting,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    resume = models.ForeignKey(
        Resume,
        on_delete=models.PROTECT,
        related_name="applications",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.APPLIED,
        db_index=True,
    )
    cover_note = models.TextField(blank=True)
    consent_to_ai_interview = models.BooleanField(default=False)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-applied_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("job", "candidate"),
                name="unique_candidate_job_application",
            ),
        ]
        indexes = [
            models.Index(fields=("job", "status")),
            models.Index(fields=("candidate", "status")),
        ]

    def __str__(self):
        return f"{self.candidate.user.email} → {self.job.title}"


class InterviewQuestion(models.Model):
    class QuestionType(models.TextChoices):
        SCREENING = "screening", "Screening"
        EXPERIENCE = "experience", "Experience"
        TECHNICAL = "technical", "Technical"
        BEHAVIORAL = "behavioral", "Behavioral"
        CLOSING = "closing", "Closing"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    job = models.ForeignKey(
        JobPosting,
        on_delete=models.CASCADE,
        related_name="interview_questions",
    )
    question_text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
    )
    order = models.PositiveSmallIntegerField()
    maximum_response_seconds = models.PositiveSmallIntegerField(
        default=120,
        validators=[
            MinValueValidator(15),
            MaxValueValidator(600),
        ],
    )
    scoring_guidance = models.TextField(blank=True)
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("job", "order")
        constraints = [
            models.UniqueConstraint(
                fields=("job", "order"),
                name="unique_question_order_per_job",
            ),
        ]

    def __str__(self):
        return f"{self.job.title} — Question {self.order}"


class JobFAQ(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    job = models.ForeignKey(
        JobPosting,
        on_delete=models.CASCADE,
        related_name="faqs",
    )
    question = models.TextField()
    answer = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"FAQ: {self.job.title}"

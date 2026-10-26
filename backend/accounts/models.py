import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    """Manage users authenticated by email instead of username."""

    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")

        email = self.normalize_email(email).lower()
        extra_fields.setdefault("role", User.Role.CANDIDATE)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["role"] = User.Role.ADMIN
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("email_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        CANDIDATE = "candidate", "Candidate"
        RECRUITER = "recruiter", "Recruiter"
        ADMIN = "admin", "Administrator"

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CANDIDATE,
    )
    email_verified = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
            ),
        ]

    def __str__(self):
        return self.email


class EmailVerificationChallenge(models.Model):
    PURPOSE_VERSION = "email-verification-v1"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_verification_challenges",
    )
    token_digest = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
    )
    email_hmac = models.CharField(
        max_length=64,
        editable=False,
    )
    purpose_version = models.CharField(
        max_length=40,
        default=PURPOSE_VERSION,
        editable=False,
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
    )
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    request_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("user", "created_at"),
                name="email_verify_user_created",
            ),
            models.Index(
                fields=("user", "expires_at"),
                name="email_verify_user_expires",
            ),
            models.Index(
                fields=("used_at", "invalidated_at"),
                name="email_verify_terminal",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(expires_at__gt=F("created_at")),
                name="email_verify_expiry_after_create",
            ),
            models.CheckConstraint(
                condition=(Q(used_at__isnull=True) | Q(invalidated_at__isnull=True)),
                name="email_verify_one_terminal_state",
            ),
        ]

    def __str__(self):
        return f"Email verification challenge {self.id}"

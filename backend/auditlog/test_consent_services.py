import importlib
import uuid
from datetime import timedelta

import pytest
from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from auditlog import consent_services
from auditlog.consent_services import (
    LEGACY_POLICY_VERSION,
    ConsentIdempotencyConflictError,
    ConsentValidationError,
    grant_application_ai_interview_consent,
    grant_general_ai_processing_consent,
    has_effective_application_ai_interview_consent,
    has_effective_general_ai_processing_consent,
    revoke_application_ai_interview_consent,
    revoke_general_ai_processing_consent,
)
from auditlog.models import AuditEvent, ConsentRecord
from candidates.models import CandidateProfile
from interviews.models import InterviewSchedule
from recruitment.models import (
    Company,
    JobApplication,
    JobPosting,
    RecruiterProfile,
)

pytestmark = pytest.mark.django_db

POLICY_VERSION = "ai-consent-2026-10"


@pytest.fixture
def candidate_user():
    return User.objects.create_user(
        email="consent-candidate@example.com",
        password=None,
        role=User.Role.CANDIDATE,
    )


@pytest.fixture
def candidate(candidate_user):
    return CandidateProfile.objects.get(user=candidate_user)


@pytest.fixture
def application_factory(candidate):
    counter = 0

    def create_application(*, application_candidate=None):
        nonlocal counter
        counter += 1
        suffix = f"{counter}-{uuid.uuid4().hex[:8]}"
        recruiter_user = User.objects.create_user(
            email=f"recruiter-{suffix}@example.com",
            password=None,
            role=User.Role.RECRUITER,
        )
        company = Company.objects.create(name=f"Consent Company {suffix}")
        recruiter = RecruiterProfile.objects.create(
            user=recruiter_user,
            company=company,
            is_verified=True,
        )
        job = JobPosting.objects.create(
            company=company,
            created_by=recruiter,
            title=f"Consent Job {suffix}",
            reference_code=f"CONSENT-{suffix}",
            description="Synthetic test job.",
        )
        return JobApplication.objects.create(
            job=job,
            candidate=application_candidate or candidate,
        )

    return create_application


@pytest.fixture
def application(application_factory):
    return application_factory()


def create_schedule(application):
    start = timezone.now() + timedelta(days=1)
    return InterviewSchedule.objects.create(
        application=application,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
    )


def create_legacy_record(candidate, **overrides):
    values = {
        "candidate": candidate,
        "consent_type": ConsentRecord.ConsentType.GENERAL_AI_PROCESSING,
        "action": ConsentRecord.Action.GRANTED,
        "policy_version": LEGACY_POLICY_VERSION,
        "collection_source": ConsentRecord.CollectionSource.LEGACY_IMPORT,
    }
    values.update(overrides)
    return ConsentRecord.objects.create(**values)


def test_consent_record_choices_and_uuid_defaults(candidate):
    record = ConsentRecord(
        candidate=candidate,
        consent_type=ConsentRecord.ConsentType.GENERAL_AI_PROCESSING,
        action=ConsentRecord.Action.GRANTED,
        policy_version=LEGACY_POLICY_VERSION,
        collection_source=ConsentRecord.CollectionSource.LEGACY_IMPORT,
    )

    assert set(ConsentRecord.ConsentType.values) == {
        "general_ai_processing",
        "ai_interview",
    }
    assert set(ConsentRecord.Action.values) == {"granted", "revoked"}
    assert set(ConsentRecord.CollectionSource.values) == {
        "profile",
        "application",
        "interview_confirmation",
        "admin_assisted",
        "legacy_import",
    }
    assert isinstance(record.id, uuid.UUID)
    assert isinstance(record.idempotency_key, uuid.UUID)


def test_general_consent_cannot_reference_application(candidate, application):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_legacy_record(candidate, application=application)


def test_interview_consent_requires_application(candidate):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_legacy_record(
                candidate,
                consent_type=ConsentRecord.ConsentType.AI_INTERVIEW,
            )


def test_schedule_reference_requires_application(candidate, application):
    schedule = create_schedule(application)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_legacy_record(candidate, interview_schedule=schedule)


def test_nonlegacy_record_requires_actor(candidate):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ConsentRecord.objects.create(
                candidate=candidate,
                consent_type=ConsentRecord.ConsentType.GENERAL_AI_PROCESSING,
                action=ConsentRecord.Action.GRANTED,
                policy_version=POLICY_VERSION,
                collection_source=ConsentRecord.CollectionSource.PROFILE,
            )


def test_legacy_import_may_have_null_actor(candidate):
    record = create_legacy_record(candidate)

    assert record.recorded_by is None


def test_general_grant_and_revocation_update_cache_and_history(
    candidate,
    candidate_user,
):
    grant = grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    candidate.refresh_from_db()

    assert grant.action == ConsentRecord.Action.GRANTED
    assert candidate.ai_processing_consent is True
    assert candidate.consent_recorded_at == grant.recorded_at
    assert has_effective_general_ai_processing_consent(
        candidate=candidate,
        policy_version=POLICY_VERSION,
    )

    revocation = revoke_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    candidate.refresh_from_db()

    assert revocation.action == ConsentRecord.Action.REVOKED
    assert candidate.ai_processing_consent is False
    assert candidate.consent_recorded_at == revocation.recorded_at
    assert not has_effective_general_ai_processing_consent(
        candidate=candidate,
        policy_version=POLICY_VERSION,
    )


def test_interview_grant_and_revocation_update_application_cache(
    application,
    candidate_user,
):
    grant = grant_application_ai_interview_consent(
        application=application,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    application.refresh_from_db()

    assert grant.candidate_id == application.candidate_id
    assert application.consent_to_ai_interview is True
    assert has_effective_application_ai_interview_consent(
        application=application,
        policy_version=POLICY_VERSION,
    )

    revoke_application_ai_interview_consent(
        application=application,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    application.refresh_from_db()

    assert application.consent_to_ai_interview is False
    assert not has_effective_application_ai_interview_consent(
        application=application,
        policy_version=POLICY_VERSION,
    )


def test_candidate_actor_must_own_application_consent(application):
    other_user = User.objects.create_user(
        email="other-consent-candidate@example.com",
        password=None,
        role=User.Role.CANDIDATE,
    )

    with pytest.raises(ConsentValidationError, match="not authorized"):
        grant_application_ai_interview_consent(
            application=application,
            actor=other_user,
            policy_version=POLICY_VERSION,
            idempotency_key=uuid.uuid4(),
        )


def test_actor_authorization_uses_persisted_role(candidate, candidate_user):
    candidate_user.role = User.Role.ADMIN

    with pytest.raises(ConsentValidationError, match="not authorized"):
        grant_general_ai_processing_consent(
            candidate=candidate,
            actor=candidate_user,
            policy_version=POLICY_VERSION,
            idempotency_key=uuid.uuid4(),
            collection_source=ConsentRecord.CollectionSource.ADMIN_ASSISTED,
        )


def test_candidate_source_requires_persisted_candidate_role(candidate, candidate_user):
    User.objects.filter(pk=candidate_user.pk).update(role=User.Role.RECRUITER)

    with pytest.raises(ConsentValidationError, match="not authorized"):
        grant_general_ai_processing_consent(
            candidate=candidate,
            actor=candidate_user,
            policy_version=POLICY_VERSION,
            idempotency_key=uuid.uuid4(),
        )


def test_recruiter_cannot_record_candidate_originated_consent(
    candidate,
):
    recruiter = User.objects.create_user(
        email="consent-recruiter-denied@example.com",
        password=None,
        role=User.Role.RECRUITER,
    )

    with pytest.raises(ConsentValidationError, match="not authorized"):
        grant_general_ai_processing_consent(
            candidate=candidate,
            actor=recruiter,
            policy_version=POLICY_VERSION,
            idempotency_key=uuid.uuid4(),
        )


def test_administrator_must_use_admin_assisted_source(candidate):
    administrator = User.objects.create_user(
        email="consent-administrator@example.com",
        password=None,
        role=User.Role.ADMIN,
    )

    with pytest.raises(ConsentValidationError, match="not authorized"):
        grant_general_ai_processing_consent(
            candidate=candidate,
            actor=administrator,
            policy_version=POLICY_VERSION,
            idempotency_key=uuid.uuid4(),
        )

    record = grant_general_ai_processing_consent(
        candidate=candidate,
        actor=administrator,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
        collection_source=ConsentRecord.CollectionSource.ADMIN_ASSISTED,
    )

    assert record.recorded_by == administrator


def test_application_candidate_is_loaded_from_database(
    application,
    candidate_user,
):
    other_user = User.objects.create_user(
        email="stale-application-candidate@example.com",
        password=None,
        role=User.Role.CANDIDATE,
    )
    application.candidate = other_user.candidate_profile

    record = grant_application_ai_interview_consent(
        application=application,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )

    assert record.candidate.user_id == candidate_user.pk
    assert record.application_id == application.pk


def test_schedule_must_belong_to_same_application(
    application,
    application_factory,
    candidate_user,
):
    other_application = application_factory()
    other_schedule = create_schedule(other_application)

    with pytest.raises(ConsentValidationError, match="does not belong"):
        grant_application_ai_interview_consent(
            application=application,
            actor=candidate_user,
            policy_version=POLICY_VERSION,
            idempotency_key=uuid.uuid4(),
            collection_source=ConsentRecord.CollectionSource.INTERVIEW_CONFIRMATION,
            interview_schedule=other_schedule,
        )


def test_schedule_ownership_is_loaded_from_database(
    application,
    application_factory,
    candidate_user,
):
    other_application = application_factory()
    other_schedule = create_schedule(other_application)
    other_schedule.application_id = application.pk

    with pytest.raises(ConsentValidationError, match="does not belong"):
        grant_application_ai_interview_consent(
            application=application,
            actor=candidate_user,
            policy_version=POLICY_VERSION,
            idempotency_key=uuid.uuid4(),
            collection_source=ConsentRecord.CollectionSource.INTERVIEW_CONFIRMATION,
            interview_schedule=other_schedule,
        )


def test_interview_confirmation_adds_schedule_linked_evidence(
    application,
    candidate_user,
):
    initial = grant_application_ai_interview_consent(
        application=application,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    schedule = create_schedule(application)
    confirmation = grant_application_ai_interview_consent(
        application=application,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
        collection_source=ConsentRecord.CollectionSource.INTERVIEW_CONFIRMATION,
        interview_schedule=schedule,
    )

    assert confirmation.pk != initial.pk
    assert confirmation.interview_schedule == schedule
    assert ConsentRecord.objects.filter(application=application).count() == 2


def test_legacy_evidence_never_authorizes_current_processing(candidate):
    create_legacy_record(candidate)
    CandidateProfile.objects.filter(pk=candidate.pk).update(
        ai_processing_consent=True
    )
    candidate.refresh_from_db()

    assert candidate.ai_processing_consent is True
    assert not has_effective_general_ai_processing_consent(
        candidate=candidate,
        policy_version=POLICY_VERSION,
    )
    assert not has_effective_general_ai_processing_consent(
        candidate=candidate,
        policy_version=LEGACY_POLICY_VERSION,
    )


def test_new_policy_version_requires_reconfirmation(candidate, candidate_user):
    first = grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version="ai-consent-2026-09",
        idempotency_key=uuid.uuid4(),
    )
    second = grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )

    assert first.pk != second.pk
    assert ConsentRecord.objects.filter(candidate=candidate).count() == 2
    assert has_effective_general_ai_processing_consent(
        candidate=candidate,
        policy_version=POLICY_VERSION,
    )


def test_same_idempotency_key_returns_existing_record(candidate, candidate_user):
    key = uuid.uuid4()
    first = grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=key,
    )
    second = grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=key,
    )

    assert second.pk == first.pk
    assert ConsentRecord.objects.filter(candidate=candidate).count() == 1


def test_conflicting_idempotency_key_reuse_is_rejected(candidate, candidate_user):
    key = uuid.uuid4()
    grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=key,
    )

    with pytest.raises(ConsentIdempotencyConflictError):
        revoke_general_ai_processing_consent(
            candidate=candidate,
            actor=candidate_user,
            policy_version=POLICY_VERSION,
            idempotency_key=key,
        )


def test_new_idempotency_key_creates_new_explicit_history(
    candidate,
    candidate_user,
):
    first = grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    second = grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )

    assert second.pk != first.pk
    assert ConsentRecord.objects.filter(candidate=candidate).count() == 2
    assert AuditEvent.objects.filter(event_type="consent.granted").count() == 2


@pytest.mark.parametrize(
    "policy_version",
    [
        " policy-2026-10",
        "policy 2026-10",
        "policy@2026",
        "policy-2026-10 ",
    ],
)
def test_policy_version_uses_audit_safe_code_rules(
    candidate,
    candidate_user,
    policy_version,
):
    with pytest.raises(ConsentValidationError, match="valid policy version"):
        grant_general_ai_processing_consent(
            candidate=candidate,
            actor=candidate_user,
            policy_version=policy_version,
            idempotency_key=uuid.uuid4(),
        )


def test_latest_cross_policy_general_action_controls_effective_consent(
    candidate,
    candidate_user,
):
    grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    revoke_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version="ai-consent-2026-11",
        idempotency_key=uuid.uuid4(),
    )
    candidate.refresh_from_db()

    assert candidate.ai_processing_consent is False
    assert not has_effective_general_ai_processing_consent(
        candidate=candidate,
        policy_version=POLICY_VERSION,
    )

    grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    candidate.refresh_from_db()

    assert candidate.ai_processing_consent is True
    assert has_effective_general_ai_processing_consent(
        candidate=candidate,
        policy_version=POLICY_VERSION,
    )


def test_latest_cross_policy_application_action_controls_effective_consent(
    application,
    candidate_user,
):
    grant_application_ai_interview_consent(
        application=application,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    revoke_application_ai_interview_consent(
        application=application,
        actor=candidate_user,
        policy_version="ai-consent-2026-11",
        idempotency_key=uuid.uuid4(),
    )
    application.refresh_from_db()

    assert application.consent_to_ai_interview is False
    assert not has_effective_application_ai_interview_consent(
        application=application,
        policy_version=POLICY_VERSION,
    )

    grant_application_ai_interview_consent(
        application=application,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    application.refresh_from_db()

    assert application.consent_to_ai_interview is True
    assert has_effective_application_ai_interview_consent(
        application=application,
        policy_version=POLICY_VERSION,
    )


def test_consent_audit_uses_record_resource_and_safe_metadata(
    candidate,
    candidate_user,
):
    record = grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY_VERSION,
        idempotency_key=uuid.uuid4(),
    )
    event = AuditEvent.objects.get(event_type="consent.granted")

    assert event.resource_type == "auditlog.ConsentRecord"
    assert event.resource_id == str(record.pk)
    assert event.metadata == {
        "candidate_id": str(candidate.pk),
        "consent_type": "general_ai_processing",
        "policy_version": POLICY_VERSION,
        "collection_source": "profile",
    }
    assert "email" not in event.metadata
    assert "wording" not in event.metadata


def test_mandatory_audit_failure_rolls_back_record_and_cache(
    candidate,
    candidate_user,
    monkeypatch,
):
    def fail_audit(command):
        raise RuntimeError("mandatory audit unavailable")

    monkeypatch.setattr(consent_services, "record_domain_event", fail_audit)

    with pytest.raises(RuntimeError, match="mandatory audit unavailable"):
        grant_general_ai_processing_consent(
            candidate=candidate,
            actor=candidate_user,
            policy_version=POLICY_VERSION,
            idempotency_key=uuid.uuid4(),
        )

    candidate.refresh_from_db()
    assert not ConsentRecord.objects.filter(candidate=candidate).exists()
    assert candidate.ai_processing_consent is False
    assert candidate.consent_recorded_at is None


def test_model_save_and_delete_are_rejected(candidate):
    record = create_legacy_record(candidate)
    record.action = ConsentRecord.Action.REVOKED

    with pytest.raises(ValidationError, match="immutable"):
        record.save()
    with pytest.raises(ValidationError, match="immutable"):
        record.delete()


def test_queryset_update_and_delete_are_rejected(candidate):
    record = create_legacy_record(candidate)

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            ConsentRecord.objects.filter(pk=record.pk).update(
                action=ConsentRecord.Action.REVOKED
            )
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            ConsentRecord.objects.filter(pk=record.pk).delete()

    assert ConsentRecord.objects.filter(
        pk=record.pk,
        action=ConsentRecord.Action.GRANTED,
    ).exists()


def test_legacy_backfill_preserves_evidence_resets_caches_and_skips_audit(
    candidate,
    application,
):
    recorded_at = timezone.now() - timedelta(days=30)
    CandidateProfile.objects.filter(pk=candidate.pk).update(
        ai_processing_consent=True,
        consent_recorded_at=recorded_at,
    )
    JobApplication.objects.filter(pk=application.pk).update(
        consent_to_ai_interview=True
    )
    migration = importlib.import_module(
        "auditlog.migrations.0004_backfill_legacy_consents"
    )

    migration.backfill_legacy_consents(django_apps, None)

    candidate.refresh_from_db()
    application.refresh_from_db()
    records = ConsentRecord.objects.filter(
        collection_source=ConsentRecord.CollectionSource.LEGACY_IMPORT,
        policy_version=LEGACY_POLICY_VERSION,
    )
    assert records.count() == 2
    assert records.filter(
        candidate=candidate,
        consent_type=ConsentRecord.ConsentType.GENERAL_AI_PROCESSING,
        recorded_by__isnull=True,
    ).exists()
    assert records.filter(
        application=application,
        consent_type=ConsentRecord.ConsentType.AI_INTERVIEW,
        recorded_by__isnull=True,
    ).exists()
    assert candidate.ai_processing_consent is False
    assert candidate.consent_recorded_at is None
    assert application.consent_to_ai_interview is False
    assert not AuditEvent.objects.filter(event_type__startswith="consent.").exists()
    assert not has_effective_general_ai_processing_consent(
        candidate=candidate,
        policy_version=POLICY_VERSION,
    )
    assert not has_effective_application_ai_interview_consent(
        application=application,
        policy_version=POLICY_VERSION,
    )

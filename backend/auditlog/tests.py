import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction

from accounts.models import User
from auditlog.models import AuditEvent
from auditlog.services import (
    EVENT_SPECS,
    AuditCommand,
    AuditEventSpec,
    DomainAuditPersistenceError,
    DomainAuditValidationError,
    record_domain_event,
)

pytestmark = pytest.mark.django_db


PASSWORD = "TestingOnly!9384"


@pytest.fixture
def actor():
    return User.objects.create_user(
        email="domain-auditor@example.com",
        password=PASSWORD,
        role=User.Role.ADMIN,
    )


def command_values(default_actor, **overrides):
    values = {
        "category": AuditEvent.Category.DATA_CHANGE,
        "event_type": "profile.updated",
        "outcome": AuditEvent.Outcome.SUCCESS,
        "severity": AuditEvent.Severity.INFO,
        "resource_type": "candidates.CandidateProfile",
        "resource_id": uuid.uuid4(),
        "actor": default_actor,
        "request_id": uuid.uuid4(),
        "correlation_id": uuid.uuid4(),
        "metadata": {"changed_fields": ["city", "phone_number"]},
    }
    values.update(overrides)
    return values


def make_command(default_actor, **overrides):
    return AuditCommand(**command_values(default_actor, **overrides))


def test_valid_domain_event_is_created_inside_callers_transaction(actor):
    command = make_command(actor)

    with transaction.atomic():
        event = record_domain_event(command)

    event.refresh_from_db()

    assert event.event_type == command.event_type
    assert event.action == "Candidate profile updated"
    assert event.actor == actor
    assert event.metadata == command.metadata
    assert len(event.event_hash) == 64


@pytest.mark.parametrize(
    ("override", "expected_message"),
    [
        ({"resource_id": None}, "resource_id is required"),
        ({"actor": None}, "actor is required"),
    ],
)
def test_required_fields_are_enforced(actor, override, expected_message):
    with pytest.raises(DomainAuditValidationError, match=expected_message):
        record_domain_event(make_command(actor, **override))


def test_unknown_event_type_is_rejected(actor):
    with pytest.raises(DomainAuditValidationError, match="not registered"):
        record_domain_event(make_command(actor, event_type="profile.unknown"))


def test_unknown_metadata_key_is_rejected(actor):
    with pytest.raises(DomainAuditValidationError, match="not allowed"):
        record_domain_event(make_command(actor, metadata={"unapproved_note": "safe"}))


def test_canonical_action_is_persisted_from_event_spec(actor):
    event = record_domain_event(make_command(actor))

    assert event.action == EVENT_SPECS["profile.updated"].action


def test_callers_cannot_supply_private_or_arbitrary_action_text(actor):
    values = command_values(actor)
    values["action"] = "Private resume narrative supplied by a caller"

    with pytest.raises(TypeError, match="action"):
        AuditCommand(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"metadata": {}},
        {
            "event_type": "consent.granted",
            "resource_type": "auditlog.ConsentRecord",
            "metadata": {
                "consent_type": "general_ai",
                "policy_version": "2026-10",
            },
        },
        {
            "event_type": "resume.uploaded",
            "resource_type": "candidates.Resume",
            "metadata": {"file_type": "application/pdf", "size_bytes": 100},
        },
        {
            "category": AuditEvent.Category.ADMINISTRATION,
            "event_type": "recruiter.provisioned",
            "resource_type": "recruitment.RecruiterProfile",
            "metadata": {"capabilities": [], "company_id": uuid.uuid4()},
        },
        {
            "event_type": "job.published",
            "resource_type": "recruitment.JobPosting",
            "metadata": {"status_from": "draft"},
        },
        {
            "event_type": "application.created",
            "resource_type": "recruitment.JobApplication",
            "metadata": {"job_id": uuid.uuid4()},
        },
        {
            "category": AuditEvent.Category.INTERVIEW,
            "event_type": "interview.invited",
            "resource_type": "interviews.InterviewSchedule",
            "metadata": {"application_id": uuid.uuid4()},
        },
    ],
)
def test_missing_required_metadata_is_rejected_safely(actor, overrides):
    with pytest.raises(DomainAuditValidationError) as error:
        record_domain_event(make_command(actor, **overrides))

    assert str(error.value) == "Required metadata is missing."


def test_optional_metadata_may_be_omitted(actor):
    event = record_domain_event(
        make_command(
            actor,
            event_type="resume.uploaded",
            resource_type="candidates.Resume",
            metadata={
                "checksum": "a" * 64,
                "file_type": "application/pdf",
                "size_bytes": 100,
            },
        )
    )

    assert "replaces_resume_id" not in event.metadata


def test_event_spec_rejects_required_metadata_that_is_not_allowed():
    with pytest.raises(ValueError, match="Required audit metadata"):
        AuditEventSpec(
            category=AuditEvent.Category.SYSTEM,
            resource_type="tests.Resource",
            action="Test action",
            allowed_metadata_keys=frozenset(),
            required_metadata_keys=frozenset({"missing_key"}),
        )


def test_event_registry_is_immutable():
    with pytest.raises(TypeError):
        EVENT_SPECS["test.event"] = EVENT_SPECS["profile.updated"]


@pytest.mark.parametrize(
    "metadata",
    [
        {"raw_token": "not-a-real-token"},
        {"resume_text": "Private resume contents"},
        {"transcript_text": "Private transcript contents"},
        {"changed_fields": ["password=not-a-real-password"]},
        {"changed_fields": [r"C:\private\resume.pdf"]},
        {"changed_fields": ["postgresql://user:password@database.invalid/example"]},
    ],
)
def test_forbidden_metadata_names_and_values_are_rejected(actor, metadata):
    with pytest.raises(DomainAuditValidationError, match="forbidden"):
        record_domain_event(make_command(actor, metadata=metadata))


@pytest.mark.parametrize(
    "metadata",
    [
        {"changed_fields": [["nested-too-deep"]]},
        {"changed_fields": list(range(21))},
        {"changed_fields": ["x" * 256]},
        {"changed_fields": ["raw private resume sentence"]},
    ],
)
def test_deep_or_large_metadata_is_rejected(actor, metadata):
    with pytest.raises(DomainAuditValidationError):
        record_domain_event(make_command(actor, metadata=metadata))


def test_uuid_identifiers_are_normalized(actor):
    resource_id = uuid.uuid4()
    request_id = uuid.uuid4()
    correlation_id = uuid.uuid4()

    event = record_domain_event(
        make_command(
            actor,
            resource_id="{" + str(resource_id).upper() + "}",
            request_id="{" + str(request_id).upper() + "}",
            correlation_id="{" + str(correlation_id).upper() + "}",
        )
    )

    assert event.resource_id == str(resource_id)
    assert event.request_id == request_id
    assert event.correlation_id == correlation_id


def test_actor_email_is_snapshotted_by_model(actor):
    event = record_domain_event(make_command(actor))

    assert event.actor_email_snapshot == actor.email


def test_service_created_event_remains_immutable(actor):
    event = record_domain_event(make_command(actor))
    event.action = "Changed action"

    with pytest.raises(ValidationError, match="immutable"):
        event.save()

    with pytest.raises(ValidationError, match="immutable"):
        event.delete()


def test_queryset_update_and_delete_protection_remains_effective(actor):
    event = record_domain_event(make_command(actor))

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            AuditEvent.objects.filter(pk=event.pk).update(action="Changed action")

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            AuditEvent.objects.filter(pk=event.pk).delete()

    assert AuditEvent.objects.filter(pk=event.pk, action=event.action).exists()


def test_persistence_errors_do_not_expose_internal_details(actor, monkeypatch):
    def fail_create(**kwargs):
        raise RuntimeError("database-password=not-a-real-secret")

    monkeypatch.setattr(AuditEvent.objects, "create", fail_create)

    with pytest.raises(DomainAuditPersistenceError) as error:
        record_domain_event(make_command(actor))

    assert "not-a-real-secret" not in str(error.value)


def test_event_registry_contains_exact_expected_event_types():
    assert set(EVENT_SPECS) == {
        "application.created",
        "application.status_changed",
        "application.withdrawn",
        "call_session.cancelled",
        "call_session.completed",
        "call_session.created",
        "call_session.expired",
        "call_session.failed",
        "call_session.paused",
        "call_session.ready",
        "call_session.resumed",
        "call_session.started",
        "company.created",
        "company.updated",
        "consent.granted",
        "consent.revoked",
        "email_verification.failed",
        "email_verification.invalidated",
        "email_verification.requested",
        "email_verification.succeeded",
        "interview.cancelled",
        "interview.completed",
        "interview.invitation_delivery_failed",
        "interview.reschedule_rejected",
        "interview.confirmed",
        "interview.expired",
        "interview.invited",
        "interview.reschedule_requested",
        "interview.rescheduled",
        "job.archived",
        "job.closed",
        "job.created",
        "job.paused",
        "job.published",
        "job.reopened",
        "job.updated",
        "profile.updated",
        "recruiter.provisioned",
        "recruiter.updated",
        "resume.activated",
        "resume.downloaded",
        "resume.processing_failed",
        "resume.processing_started",
        "resume.processing_succeeded",
        "resume.uploaded",
    }


def test_event_registry_has_exact_required_metadata_rules():
    expected = {
        "application.created": {"job_id", "resume_id"},
        "application.status_changed": {"status_from", "status_to"},
        "application.withdrawn": {"status_from", "status_to"},
        "call_session.cancelled": {
            "application_id",
            "interview_schedule_id",
            "reason_code",
            "status_from",
            "status_to",
        },
        "call_session.completed": {
            "application_id",
            "interview_schedule_id",
            "reason_code",
            "status_from",
            "status_to",
        },
        "call_session.created": {
            "application_id",
            "interview_schedule_id",
            "simulated_mode",
            "status_to",
        },
        "call_session.expired": {
            "application_id",
            "interview_schedule_id",
            "reason_code",
            "status_from",
            "status_to",
        },
        "call_session.failed": {
            "application_id",
            "failure_code",
            "interview_schedule_id",
            "status_from",
            "status_to",
        },
        "call_session.paused": {
            "application_id",
            "interview_schedule_id",
            "status_from",
            "status_to",
        },
        "call_session.ready": {
            "application_id",
            "interview_schedule_id",
            "status_from",
            "status_to",
        },
        "call_session.resumed": {
            "application_id",
            "interview_schedule_id",
            "status_from",
            "status_to",
        },
        "call_session.started": {
            "application_id",
            "interview_schedule_id",
            "status_from",
            "status_to",
        },
        "company.created": set(),
        "company.updated": {"changed_fields"},
        "consent.granted": {
            "candidate_id",
            "collection_source",
            "consent_type",
            "policy_version",
        },
        "consent.revoked": {
            "candidate_id",
            "collection_source",
            "consent_type",
            "policy_version",
        },
        "email_verification.failed": {"failure_code"},
        "email_verification.invalidated": {"reason_code"},
        "email_verification.requested": {"delivery_channel"},
        "email_verification.succeeded": set(),
        "interview.cancelled": {
            "application_id",
            "reason_code",
            "status_from",
            "status_to",
        },
        "interview.completed": {"application_id", "status_from", "status_to"},
        "interview.invitation_delivery_failed": {"application_id", "failure_code"},
        "interview.reschedule_rejected": {"application_id", "request_id"},
        "interview.confirmed": {"application_id", "status_from", "status_to"},
        "interview.expired": {"application_id", "status_from", "status_to"},
        "interview.invited": {"application_id", "invitation_expires_at"},
        "interview.reschedule_requested": {"application_id", "request_id"},
        "interview.rescheduled": {
            "application_id",
            "replacement_schedule_id",
            "status_from",
            "status_to",
        },
        "job.archived": {"status_from", "status_to"},
        "job.closed": {"status_from", "status_to"},
        "job.created": set(),
        "job.paused": {"status_from", "status_to"},
        "job.published": {"status_from", "status_to"},
        "job.reopened": {"status_from", "status_to"},
        "job.updated": {"changed_fields"},
        "profile.updated": {"changed_fields"},
        "recruiter.provisioned": {"capabilities", "company_id", "is_verified"},
        "recruiter.updated": {"changed_fields"},
        "resume.activated": set(),
        "resume.downloaded": set(),
        "resume.processing_failed": {"failure_code", "parser"},
        "resume.processing_started": {"parser"},
        "resume.processing_succeeded": {"extracted_character_count", "parser"},
        "resume.uploaded": {"checksum", "file_type", "size_bytes"},
    }

    assert {
        event_type: set(spec.required_metadata_keys)
        for event_type, spec in EVENT_SPECS.items()
    } == expected
    assert all(spec.required_metadata_keys <= spec.allowed_metadata_keys for spec in EVENT_SPECS.values())

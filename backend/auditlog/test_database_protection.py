import pytest
from django.db import DatabaseError, transaction

from accounts.models import User
from auditlog.models import AuditEvent, ConsentRecord
from candidates.models import CandidateProfile

pytestmark = pytest.mark.django_db(transaction=True)


def create_event(event_type):
    return AuditEvent.objects.create(
        category=AuditEvent.Category.SECURITY,
        event_type=event_type,
        action="Test database protection",
        outcome=AuditEvent.Outcome.SUCCESS,
        severity=AuditEvent.Severity.INFO,
    )


def test_postgresql_blocks_bulk_audit_event_update():
    event = create_event("test.database.update")

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            AuditEvent.objects.filter(pk=event.pk).update(
                description="Unauthorized modification"
            )

    event.refresh_from_db()

    assert event.description == ""


def test_postgresql_blocks_bulk_audit_event_delete():
    event = create_event("test.database.delete")

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            AuditEvent.objects.filter(pk=event.pk).delete()

    assert AuditEvent.objects.filter(pk=event.pk).exists()


def create_consent_record():
    user = User.objects.create_user(
        email="consent-trigger@example.com",
        password=None,
        role=User.Role.CANDIDATE,
    )
    candidate = CandidateProfile.objects.get(user=user)
    return ConsentRecord.objects.create(
        candidate=candidate,
        consent_type=ConsentRecord.ConsentType.GENERAL_AI_PROCESSING,
        action=ConsentRecord.Action.GRANTED,
        policy_version="legacy-unversioned",
        collection_source=ConsentRecord.CollectionSource.LEGACY_IMPORT,
    )


def test_postgresql_blocks_direct_consent_record_update():
    record = create_consent_record()

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE auditlog_consentrecord SET action = %s WHERE id = %s",
                    [ConsentRecord.Action.REVOKED, record.pk],
                )

    record.refresh_from_db()
    assert record.action == ConsentRecord.Action.GRANTED


def test_postgresql_blocks_direct_consent_record_delete():
    record = create_consent_record()

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM auditlog_consentrecord WHERE id = %s",
                    [record.pk],
                )

    assert ConsentRecord.objects.filter(pk=record.pk).exists()

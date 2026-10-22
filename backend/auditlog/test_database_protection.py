import pytest
from django.db import DatabaseError, transaction

from auditlog.models import AuditEvent

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

from django.db import migrations


CREATE_IMMUTABILITY_TRIGGER = """
CREATE OR REPLACE FUNCTION auditlog_prevent_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'Audit events are immutable and cannot be updated or deleted.'
        USING ERRCODE = '23000';
END;
$$;

DROP TRIGGER IF EXISTS auditlog_event_immutable
ON auditlog_auditevent;

CREATE TRIGGER auditlog_event_immutable
BEFORE UPDATE OR DELETE
ON auditlog_auditevent
FOR EACH ROW
EXECUTE FUNCTION auditlog_prevent_event_mutation();
"""


REMOVE_IMMUTABILITY_TRIGGER = """
DROP TRIGGER IF EXISTS auditlog_event_immutable
ON auditlog_auditevent;

DROP FUNCTION IF EXISTS auditlog_prevent_event_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("auditlog", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_IMMUTABILITY_TRIGGER,
            reverse_sql=REMOVE_IMMUTABILITY_TRIGGER,
        ),
    ]

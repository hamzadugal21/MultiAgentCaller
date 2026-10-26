from django.db import migrations


CREATE_IMMUTABILITY_TRIGGER = """
CREATE OR REPLACE FUNCTION auditlog_prevent_consent_record_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'Consent records are immutable and cannot be updated or deleted.'
        USING ERRCODE = '23000';
END;
$$;

DROP TRIGGER IF EXISTS auditlog_consent_record_immutable
ON auditlog_consentrecord;

CREATE TRIGGER auditlog_consent_record_immutable
BEFORE UPDATE OR DELETE
ON auditlog_consentrecord
FOR EACH ROW
EXECUTE FUNCTION auditlog_prevent_consent_record_mutation();
"""


REMOVE_IMMUTABILITY_TRIGGER = """
DROP TRIGGER IF EXISTS auditlog_consent_record_immutable
ON auditlog_consentrecord;

DROP FUNCTION IF EXISTS auditlog_prevent_consent_record_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("auditlog", "0004_backfill_legacy_consents"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_IMMUTABILITY_TRIGGER,
            reverse_sql=REMOVE_IMMUTABILITY_TRIGGER,
        ),
    ]

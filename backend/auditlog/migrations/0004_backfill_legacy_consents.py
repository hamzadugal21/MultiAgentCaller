import uuid

from django.db import migrations
from django.utils import timezone


LEGACY_POLICY_VERSION = "legacy-unversioned"


def backfill_legacy_consents(apps, schema_editor):
    CandidateProfile = apps.get_model("candidates", "CandidateProfile")
    JobApplication = apps.get_model("recruitment", "JobApplication")
    ConsentRecord = apps.get_model("auditlog", "ConsentRecord")

    imported_at = timezone.now()
    general_records = [
        ConsentRecord(
            candidate_id=profile.pk,
            consent_type="general_ai_processing",
            action="granted",
            policy_version=LEGACY_POLICY_VERSION,
            collection_source="legacy_import",
            recorded_at=profile.consent_recorded_at or imported_at,
            idempotency_key=uuid.uuid4(),
        )
        for profile in CandidateProfile.objects.filter(ai_processing_consent=True)
    ]
    ConsentRecord.objects.bulk_create(general_records)
    CandidateProfile.objects.filter(ai_processing_consent=True).update(
        ai_processing_consent=False,
        consent_recorded_at=None,
    )

    interview_records = [
        ConsentRecord(
            candidate_id=application.candidate_id,
            consent_type="ai_interview",
            action="granted",
            policy_version=LEGACY_POLICY_VERSION,
            collection_source="legacy_import",
            application_id=application.pk,
            recorded_at=imported_at,
            idempotency_key=uuid.uuid4(),
        )
        for application in JobApplication.objects.filter(
            consent_to_ai_interview=True
        )
    ]
    ConsentRecord.objects.bulk_create(interview_records)
    JobApplication.objects.filter(consent_to_ai_interview=True).update(
        consent_to_ai_interview=False
    )


def restore_legacy_caches(apps, schema_editor):
    CandidateProfile = apps.get_model("candidates", "CandidateProfile")
    JobApplication = apps.get_model("recruitment", "JobApplication")
    ConsentRecord = apps.get_model("auditlog", "ConsentRecord")

    legacy_records = ConsentRecord.objects.filter(
        collection_source="legacy_import",
        policy_version=LEGACY_POLICY_VERSION,
        action="granted",
    ).order_by("recorded_at", "id")
    for record in legacy_records:
        if record.consent_type == "general_ai_processing":
            CandidateProfile.objects.filter(pk=record.candidate_id).update(
                ai_processing_consent=True,
                consent_recorded_at=record.recorded_at,
            )
        elif record.consent_type == "ai_interview" and record.application_id:
            JobApplication.objects.filter(pk=record.application_id).update(
                consent_to_ai_interview=True
            )

    legacy_records.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auditlog", "0003_consentrecord"),
    ]

    operations = [
        migrations.RunPython(
            backfill_legacy_consents,
            reverse_code=restore_legacy_caches,
        ),
    ]

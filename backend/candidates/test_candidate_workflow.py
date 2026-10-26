from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from docx import Document
from pypdf import PdfWriter

from accounts.models import User
from auditlog.models import AuditEvent, ConsentRecord
from candidates.models import CandidateProfile, Resume

pytestmark = pytest.mark.django_db


def _candidate(email="candidate-workflow@example.com"):
    user = User.objects.create_user(email=email, password="TestPassword123!")
    return user, CandidateProfile.objects.get(user=user)


def _pdf_upload(name="resume.pdf"):
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/pdf")


def _docx_upload(name="resume.docx"):
    buffer = BytesIO()
    document = Document()
    document.add_paragraph("Python engineering experience")
    document.save(buffer)
    return SimpleUploadedFile(
        name,
        buffer.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )


def test_candidate_profile_uses_allowlist_and_audits_changes(client):
    user, profile = _candidate()
    client.force_login(user)
    response = client.post(
        reverse("candidates:profile_edit"),
        {
            "city": "Lahore",
            "country_code": "PK",
            "timezone": "Asia/Karachi",
            "years_of_experience": 4,
            "availability": CandidateProfile.Availability.AVAILABLE,
            "ai_processing_consent": "on",
            "user": 999,
        },
    )
    assert response.status_code == 302
    profile.refresh_from_db()
    assert profile.city == "Lahore"
    assert profile.ai_processing_consent is False
    event = AuditEvent.objects.get(event_type="profile.updated")
    assert "ai_processing_consent" not in event.metadata["changed_fields"]


def test_recruiter_cannot_edit_candidate_profile(client):
    recruiter = User.objects.create_user(
        email="candidate-workflow-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    client.force_login(recruiter)
    assert client.get(reverse("candidates:profile_edit")).status_code == 403


def test_consent_mutation_is_post_only_and_records_history(client):
    user, profile = _candidate()
    client.force_login(user)
    assert client.get(reverse("candidates:general_consent")).status_code == 405
    response = client.post(
        reverse("candidates:general_consent"), {"action": "grant"}
    )
    assert response.status_code == 302
    profile.refresh_from_db()
    assert profile.ai_processing_consent is True
    assert ConsentRecord.objects.filter(candidate=profile, action="granted").exists()


def test_pdf_upload_processes_and_activates_resume(client, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    user, _ = _candidate()
    client.force_login(user)
    response = client.post(
        reverse("candidates:resume_upload"), {"file": _pdf_upload()}
    )
    assert response.status_code == 302
    resume = Resume.objects.get()
    assert resume.processing_status == Resume.ProcessingStatus.COMPLETED
    assert resume.is_active is True
    assert len(resume.sha256_checksum) == 64
    assert "resume.pdf" not in resume.file.name


def test_docx_upload_extracts_basic_text(client, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    user, _ = _candidate("docx-candidate@example.com")
    client.force_login(user)
    client.post(reverse("candidates:resume_upload"), {"file": _docx_upload()})
    resume = Resume.objects.get()
    assert "Python engineering experience" in resume.extracted_text
    assert resume.is_active is True


def test_failed_replacement_keeps_old_resume_active(client, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    user, profile = _candidate("replacement-candidate@example.com")
    old = Resume.objects.create(
        candidate=profile,
        file="candidate-resumes/old.pdf",
        original_filename="old.pdf",
        processing_status=Resume.ProcessingStatus.COMPLETED,
        is_active=True,
    )
    client.force_login(user)
    invalid = SimpleUploadedFile(
        "replacement.pdf", b"%PDF-invalid", content_type="application/pdf"
    )
    response = client.post(reverse("candidates:resume_upload"), {"file": invalid})
    assert response.status_code == 302
    old.refresh_from_db()
    replacement = Resume.objects.exclude(pk=old.pk).get()
    assert old.is_active is True
    assert replacement.processing_status == Resume.ProcessingStatus.FAILED
    assert replacement.is_active is False


def test_resume_download_is_owner_protected(client, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    owner, profile = _candidate("resume-owner@example.com")
    other, _ = _candidate("resume-other@example.com")
    client.force_login(owner)
    client.post(reverse("candidates:resume_upload"), {"file": _pdf_upload()})
    resume = Resume.objects.get(candidate=profile)
    client.force_login(other)
    assert (
        client.get(reverse("candidates:resume_download", args=(resume.pk,))).status_code
        == 404
    )

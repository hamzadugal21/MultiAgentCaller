from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from docx import Document
from pypdf import PdfWriter

from accounts.models import User
from auditlog.models import AuditEvent, ConsentRecord
from candidates.models import CandidateProfile, CandidateSkill, Resume, Skill

pytestmark = pytest.mark.django_db


def _candidate(email="candidate-workflow@example.com"):
    user = User.objects.create_user(email=email, password="TestPassword123!")
    return user, CandidateProfile.objects.get(user=user)


def _profile_payload(**overrides):
    data = {
        "phone_number": "+923001234567",
        "city": "Lahore",
        "country_code": "PK",
        "timezone": "Asia/Karachi",
        "professional_summary": "Accessible frontend engineering.",
        "years_of_experience": 4,
        "availability": CandidateProfile.Availability.AVAILABLE,
    }
    data.update(overrides)
    return data


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


def test_anonymous_user_is_redirected_from_candidate_profile(client):
    response = client.get(reverse("candidates:profile_edit"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_recruiter_cannot_edit_candidate_profile(client):
    recruiter = User.objects.create_user(
        email="candidate-workflow-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    client.force_login(recruiter)
    assert client.get(reverse("candidates:profile_edit")).status_code == 403


def test_administrator_cannot_edit_candidate_profile(client):
    administrator = User.objects.create_superuser(
        email="candidate-workflow-admin@example.com",
        password="TestPassword123!",
    )
    client.force_login(administrator)

    assert client.get(reverse("candidates:profile_edit")).status_code == 403


def test_candidate_profile_update_is_scoped_to_signed_in_candidate(client):
    user, profile = _candidate("profile-owner@example.com")
    _, other_profile = _candidate("profile-other@example.com")
    client.force_login(user)

    response = client.post(
        reverse("candidates:profile_edit"),
        _profile_payload(city="Islamabad"),
    )

    assert response.status_code == 302
    profile.refresh_from_db()
    other_profile.refresh_from_db()
    assert profile.city == "Islamabad"
    assert other_profile.city == ""


def test_candidate_profile_page_shows_real_fields_skills_and_consent_control(client):
    user, profile = _candidate()
    skill = Skill.objects.create(name="Python")
    CandidateSkill.objects.create(candidate=profile, skill=skill)
    client.force_login(user)

    response = client.get(reverse("candidates:profile_edit"))

    assert response.status_code == 200
    content = response.content.decode()
    for field_name in (
        "phone_number",
        "city",
        "country_code",
        "timezone",
        "professional_summary",
        "years_of_experience",
        "availability",
    ):
        assert f'name="{field_name}"' in content
    assert "Python" in content
    assert 'name="action" value="grant"' in content
    assert "csrfmiddlewaretoken" in content


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


def test_profile_consent_control_grants_and_revokes_append_only_history(client):
    user, profile = _candidate("profile-consent@example.com")
    client.force_login(user)

    grant_response = client.post(
        reverse("candidates:general_consent"),
        {"action": "grant", "return_to": "profile"},
    )

    assert grant_response.status_code == 302
    assert grant_response.url == reverse("candidates:profile_edit")
    profile.refresh_from_db()
    assert profile.ai_processing_consent is True
    active_page = client.get(reverse("candidates:profile_edit"))
    assert b"Consent active" in active_page.content
    assert b'name="action" value="revoke"' in active_page.content

    revoke_response = client.post(
        reverse("candidates:general_consent"),
        {"action": "revoke", "return_to": "profile"},
    )

    assert revoke_response.status_code == 302
    profile.refresh_from_db()
    assert profile.ai_processing_consent is False
    assert list(
        ConsentRecord.objects.filter(candidate=profile).values_list(
            "action", flat=True
        )
    ) == ["revoked", "granted"]


def test_anonymous_user_is_redirected_from_resume_page(client):
    response = client.get(reverse("candidates:resume_list"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.parametrize("role", (User.Role.RECRUITER, User.Role.ADMIN))
def test_non_candidate_cannot_access_resume_page(client, role):
    user = User.objects.create_user(
        email=f"resume-{role}@example.com",
        password="TestPassword123!",
        role=role,
    )
    client.force_login(user)

    assert client.get(reverse("candidates:resume_list")).status_code == 403
    assert client.get(reverse("candidates:resume_upload")).status_code == 403


def test_resume_page_has_safe_empty_state_and_secure_upload_form(client):
    user, _ = _candidate("resume-empty@example.com")
    client.force_login(user)

    response = client.get(reverse("candidates:resume_list"))

    assert response.status_code == 200
    assert response.templates[0].name == "candidates/resume_list.html"
    content = response.content.decode()
    assert "No active résumé" in content
    assert "No previous uploads" in content
    assert reverse("candidates:resume_upload") in content
    assert 'enctype="multipart/form-data"' in content
    assert 'name="file"' in content
    assert "csrfmiddlewaretoken" in content


def test_resume_page_shows_only_owned_safe_metadata_and_download_link(client):
    user, profile = _candidate("resume-page-owner@example.com")
    other_user, other_profile = _candidate("resume-page-other@example.com")
    active = Resume.objects.create(
        candidate=profile,
        file="candidate-resumes/private/opaque-active.pdf",
        original_filename="Candidate_Resume.pdf",
        file_size=1_800_000,
        sha256_checksum="a" * 64,
        mime_type="application/pdf",
        processing_status=Resume.ProcessingStatus.COMPLETED,
        is_active=True,
    )
    Resume.objects.create(
        candidate=profile,
        file="candidate-resumes/private/opaque-previous.docx",
        original_filename="Previous_Resume.docx",
        file_size=900_000,
        sha256_checksum="b" * 64,
        mime_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        processing_status=Resume.ProcessingStatus.COMPLETED,
    )
    Resume.objects.create(
        candidate=other_profile,
        file="candidate-resumes/private/other.pdf",
        original_filename="Other_Candidate_Private.pdf",
        processing_status=Resume.ProcessingStatus.COMPLETED,
        is_active=True,
    )
    client.force_login(user)

    response = client.get(reverse("candidates:resume_list"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Candidate_Resume.pdf" in content
    assert "Previous_Resume.docx" in content
    assert "Other_Candidate_Private.pdf" not in content
    assert reverse("candidates:resume_download", args=(active.pk,)) in content
    assert active.file.name not in content
    assert active.sha256_checksum not in content
    assert other_user.email not in content


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

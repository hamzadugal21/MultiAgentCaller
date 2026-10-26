import pytest

from accounts.models import User
from auditlog.models import AuditEvent
from candidates.models import CandidateProfile, Resume
from candidates.transition_services import (
    RESUME_TRANSITIONS,
    ResumeTransitionError,
    activate_processed_resume,
    transition_resume_processing,
)


@pytest.fixture
def resume_data(db):
    user = User.objects.create_user(
        email="resume-workflow@example.com", password="TestPassword123!"
    )
    candidate = CandidateProfile.objects.get(user=user)
    old_resume = Resume.objects.create(
        candidate=candidate,
        file="candidate-resumes/old.pdf",
        original_filename="old.pdf",
        processing_status=Resume.ProcessingStatus.COMPLETED,
        is_active=True,
    )
    new_resume = Resume.objects.create(
        candidate=candidate,
        file="candidate-resumes/new.pdf",
        original_filename="new.pdf",
    )
    return user, old_resume, new_resume


@pytest.mark.django_db
def test_resume_processing_and_successful_replacement(resume_data):
    user, old_resume, new_resume = resume_data
    assert new_resume.is_active is False
    assert Resume.ProcessingStatus.PROCESSING in RESUME_TRANSITIONS["pending"]
    transition_resume_processing(
        resume=new_resume,
        target_status=Resume.ProcessingStatus.PROCESSING,
        parser="pypdf-v1",
    )
    completed = transition_resume_processing(
        resume=new_resume,
        target_status=Resume.ProcessingStatus.COMPLETED,
        parser="pypdf-v1",
        extracted_text="Safe extracted content",
    )
    activated = activate_processed_resume(resume=completed, actor=user)
    old_resume.refresh_from_db()
    assert activated.is_active is True
    assert old_resume.is_active is False
    assert AuditEvent.objects.filter(event_type="resume.activated").exists()


@pytest.mark.django_db
def test_resume_failure_keeps_previous_active_and_terminal_is_rejected(resume_data):
    _, old_resume, new_resume = resume_data
    processing = transition_resume_processing(
        resume=new_resume,
        target_status=Resume.ProcessingStatus.PROCESSING,
        parser="python-docx-v1",
    )
    failed = transition_resume_processing(
        resume=processing,
        target_status=Resume.ProcessingStatus.FAILED,
        parser="python-docx-v1",
        failure_code="invalid-structure",
    )
    old_resume.refresh_from_db()
    assert failed.is_active is False
    assert old_resume.is_active is True
    with pytest.raises(ResumeTransitionError):
        transition_resume_processing(
            resume=old_resume,
            target_status=Resume.ProcessingStatus.PROCESSING,
            parser="pypdf-v1",
        )


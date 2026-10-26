import uuid

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from accounts.models import User
from auditlog.consent_services import (
    grant_general_ai_processing_consent,
    revoke_general_ai_processing_consent,
)
from auditlog.models import AuditEvent, ConsentRecord
from candidates.models import CandidateProfile, Resume
from interviews.models import InterviewRescheduleRequest, InterviewSchedule
from interviews.scheduling_services import (
    SchedulingServiceError,
    cancel_interview,
    confirm_interview_invitation,
    create_interview_invitation,
    deliver_interview_invitation,
    expire_interview_invitation,
    request_interview_reschedule,
    review_reschedule_request,
)
from recruitment.application_services import create_application
from recruitment.models import Company, JobPosting, RecruiterProfile

pytestmark = pytest.mark.django_db
POLICY = "ai-processing-v1"


@pytest.fixture
def scheduling_data(db):
    company = Company.objects.create(name="Scheduling Company")
    recruiter_user = User.objects.create_user(
        email="scheduling-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    recruiter = RecruiterProfile.objects.create(
        user=recruiter_user,
        company=company,
        is_verified=True,
    )
    job = JobPosting.objects.create(
        company=company,
        created_by=recruiter,
        title="Scheduling Role",
        reference_code="SCH-001",
        description="Role",
        status=JobPosting.Status.OPEN,
    )
    candidate_user = User.objects.create_user(
        email="scheduling-candidate@example.com",
        password="TestPassword123!",
        email_verified=True,
    )
    candidate = CandidateProfile.objects.get(user=candidate_user)
    resume = Resume.objects.create(
        candidate=candidate,
        file="candidate-resumes/scheduling.pdf",
        original_filename="scheduling.pdf",
        processing_status=Resume.ProcessingStatus.COMPLETED,
        is_active=True,
    )
    grant_general_ai_processing_consent(
        candidate=candidate,
        actor=candidate_user,
        policy_version=POLICY,
        idempotency_key=uuid.uuid4(),
    )
    application = create_application(
        actor=candidate_user,
        job=job,
        resume=resume,
        grant_interview_consent=True,
        policy_version=POLICY,
        consent_idempotency_key=uuid.uuid4(),
    )
    return {
        "company": company,
        "recruiter_user": recruiter_user,
        "candidate_user": candidate_user,
        "candidate": candidate,
        "application": application,
    }


def _invite(data, *, start=None, idempotency_key=None):
    start = start or timezone.now() + timezone.timedelta(days=3)
    return create_interview_invitation(
        application=data["application"],
        actor=data["recruiter_user"],
        scheduled_start=start,
        scheduled_end=start + timezone.timedelta(hours=1),
        timezone_name="Asia/Karachi",
        policy_version=POLICY,
        idempotency_key=idempotency_key or uuid.uuid4(),
    )


def test_invitation_is_hmac_only_expiring_and_idempotent(scheduling_data):
    key = uuid.uuid4()
    start = timezone.now() + timezone.timedelta(days=3)
    issued = _invite(scheduling_data, start=start, idempotency_key=key)
    replay = _invite(scheduling_data, start=start, idempotency_key=key)
    schedule = issued.schedule
    assert replay.schedule.pk == schedule.pk
    assert replay.token == issued.token
    assert issued.token not in schedule.access_token_hash
    assert len(schedule.access_token_hash) == 64
    assert schedule.invitation_expires_at <= timezone.now() + timezone.timedelta(hours=48)
    assert InterviewSchedule.objects.count() == 1


@override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
)
def test_invitation_delivery_is_idempotent_after_success(scheduling_data):
    issued = _invite(scheduling_data)
    assert deliver_interview_invitation(
        issued=issued, confirmation_url=f"https://example.test/{issued.token}"
    )
    issued.schedule.refresh_from_db()
    assert issued.schedule.invitation_delivery_status == "sent"
    assert deliver_interview_invitation(
        issued=issued, confirmation_url=f"https://example.test/{issued.token}"
    )
    assert len(mail.outbox) == 1


def test_delivery_failure_is_safe_and_audited(monkeypatch, scheduling_data):
    issued = _invite(scheduling_data)

    def fail_delivery(*args, **kwargs):
        raise OSError("private mail failure detail")

    monkeypatch.setattr("interviews.scheduling_services.send_mail", fail_delivery)
    assert deliver_interview_invitation(
        issued=issued, confirmation_url="https://example.test/confirm"
    ) is False
    issued.schedule.refresh_from_db()
    assert issued.schedule.invitation_last_error_code == "email_delivery_failed"
    event = AuditEvent.objects.get(event_type="interview.invitation_delivery_failed")
    assert "private" not in str(event.metadata)


def test_candidate_confirmation_is_single_use_and_schedule_links_consent(scheduling_data):
    issued = _invite(scheduling_data)
    schedule = confirm_interview_invitation(
        token=issued.token,
        actor=scheduling_data["candidate_user"],
        policy_version=POLICY,
        consent_idempotency_key=uuid.uuid4(),
    )
    assert schedule.status == InterviewSchedule.Status.CONFIRMED
    assert ConsentRecord.objects.filter(interview_schedule=schedule).exists()
    with pytest.raises(SchedulingServiceError):
        confirm_interview_invitation(
            token=issued.token,
            actor=scheduling_data["candidate_user"],
            policy_version=POLICY,
            consent_idempotency_key=uuid.uuid4(),
        )


def test_revoked_general_consent_blocks_invitation(scheduling_data):
    revoke_general_ai_processing_consent(
        candidate=scheduling_data["candidate"],
        actor=scheduling_data["candidate_user"],
        policy_version=POLICY,
        idempotency_key=uuid.uuid4(),
    )
    with pytest.raises(SchedulingServiceError, match="consent"):
        _invite(scheduling_data)


def test_invalid_timezone_and_cross_company_recruiter_are_denied(scheduling_data):
    start = timezone.now() + timezone.timedelta(days=2)
    with pytest.raises(SchedulingServiceError, match="IANA"):
        create_interview_invitation(
            application=scheduling_data["application"],
            actor=scheduling_data["recruiter_user"],
            scheduled_start=start,
            scheduled_end=start + timezone.timedelta(hours=1),
            timezone_name="Not/A_Zone",
            policy_version=POLICY,
            idempotency_key=uuid.uuid4(),
        )
    other_company = Company.objects.create(name="Other Scheduling Company")
    other_user = User.objects.create_user(
        email="other-scheduling-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    RecruiterProfile.objects.create(
        user=other_user, company=other_company, is_verified=True
    )
    with pytest.raises(SchedulingServiceError, match="authorized"):
        create_interview_invitation(
            application=scheduling_data["application"],
            actor=other_user,
            scheduled_start=start,
            scheduled_end=start + timezone.timedelta(hours=1),
            timezone_name="UTC",
            policy_version=POLICY,
            idempotency_key=uuid.uuid4(),
        )


def test_reschedule_request_rejection_preserves_schedule(scheduling_data):
    issued = _invite(scheduling_data)
    start = timezone.now() + timezone.timedelta(days=5)
    request = request_interview_reschedule(
        schedule=issued.schedule,
        actor=scheduling_data["candidate_user"],
        proposed_start=start,
        proposed_end=start + timezone.timedelta(hours=1),
        timezone_name="UTC",
        reason="Conflict",
    )
    reviewed, replacement = review_reschedule_request(
        reschedule_request=request,
        actor=scheduling_data["recruiter_user"],
        approve=False,
    )
    issued.schedule.refresh_from_db()
    assert reviewed.status == InterviewRescheduleRequest.Status.REJECTED
    assert replacement is None
    assert issued.schedule.is_current is True


def test_reschedule_approval_replaces_schedule_and_issues_new_token(scheduling_data):
    issued = _invite(scheduling_data)
    start = timezone.now() + timezone.timedelta(days=5)
    request = request_interview_reschedule(
        schedule=issued.schedule,
        actor=scheduling_data["candidate_user"],
        proposed_start=start,
        proposed_end=start + timezone.timedelta(hours=1),
        timezone_name="UTC",
    )
    reviewed, replacement_issued = review_reschedule_request(
        reschedule_request=request,
        actor=scheduling_data["recruiter_user"],
        approve=True,
        invitation_idempotency_key=uuid.uuid4(),
    )
    issued.schedule.refresh_from_db()
    assert reviewed.status == InterviewRescheduleRequest.Status.APPROVED
    assert issued.schedule.status == InterviewSchedule.Status.RESCHEDULED
    assert replacement_issued.schedule.is_current is True
    assert replacement_issued.schedule.status == InterviewSchedule.Status.PENDING
    assert replacement_issued.token not in replacement_issued.schedule.access_token_hash


def test_recruiter_can_cancel_and_expire_only_due_invitation(scheduling_data):
    issued = _invite(scheduling_data)
    cancelled = cancel_interview(
        schedule=issued.schedule,
        actor=scheduling_data["recruiter_user"],
        reason_code="recruiter_cancelled",
    )
    assert cancelled.status == InterviewSchedule.Status.CANCELLED

    scheduling_data["application"].status = "screening"
    scheduling_data["application"].save(update_fields=("status",))
    second = _invite(scheduling_data)
    with pytest.raises(SchedulingServiceError, match="not expired"):
        expire_interview_invitation(
            schedule=second.schedule, actor=scheduling_data["recruiter_user"]
        )
    InterviewSchedule.objects.filter(pk=second.schedule.pk).update(
        invitation_expires_at=timezone.now() - timezone.timedelta(seconds=1)
    )
    expired = expire_interview_invitation(
        schedule=second.schedule, actor=scheduling_data["recruiter_user"]
    )
    assert expired.status == InterviewSchedule.Status.EXPIRED

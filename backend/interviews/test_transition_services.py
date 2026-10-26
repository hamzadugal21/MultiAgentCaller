import pytest
from django.utils import timezone

from accounts.models import User
from candidates.models import CandidateProfile
from interviews.models import InterviewSchedule
from interviews.transition_services import (
    INTERVIEW_TRANSITIONS,
    InterviewAuthorizationError,
    InterviewTransitionError,
    transition_interview,
)
from recruitment.models import Company, JobApplication, JobPosting, RecruiterProfile


@pytest.fixture
def interview_data(db):
    company = Company.objects.create(name="Interview Workflow Company")
    recruiter_user = User.objects.create_user(
        email="interview-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    recruiter = RecruiterProfile.objects.create(
        user=recruiter_user, company=company, is_verified=True
    )
    candidate_user = User.objects.create_user(
        email="interview-candidate@example.com", password="TestPassword123!"
    )
    candidate = CandidateProfile.objects.get(user=candidate_user)
    job = JobPosting.objects.create(
        company=company,
        created_by=recruiter,
        title="Interview Role",
        reference_code="INT-001",
        description="Role",
    )
    application = JobApplication.objects.create(job=job, candidate=candidate)
    schedule = InterviewSchedule.objects.create(
        application=application,
        scheduled_by=recruiter_user,
        scheduled_start=timezone.now() + timezone.timedelta(days=2),
        scheduled_end=timezone.now() + timezone.timedelta(days=2, hours=1),
    )
    return recruiter_user, candidate_user, application, schedule


@pytest.mark.django_db
def test_candidate_confirmation_and_forbidden_replay(interview_data):
    _, candidate_user, _, schedule = interview_data
    assert InterviewSchedule.Status.CONFIRMED in INTERVIEW_TRANSITIONS["pending"]
    confirmed = transition_interview(
        schedule=schedule,
        target_status=InterviewSchedule.Status.CONFIRMED,
        actor=candidate_user,
    )
    assert confirmed.confirmed_at is not None
    with pytest.raises(InterviewTransitionError):
        transition_interview(
            schedule=confirmed,
            target_status=InterviewSchedule.Status.CONFIRMED,
            actor=candidate_user,
        )


@pytest.mark.django_db
def test_confirmation_rejects_recruiter_and_expiry_is_system_only(interview_data):
    recruiter_user, _, _, schedule = interview_data
    with pytest.raises(InterviewAuthorizationError):
        transition_interview(
            schedule=schedule,
            target_status=InterviewSchedule.Status.CONFIRMED,
            actor=recruiter_user,
        )
    expired = transition_interview(
        schedule=schedule,
        target_status=InterviewSchedule.Status.EXPIRED,
    )
    assert expired.is_current is False


@pytest.mark.django_db
def test_reschedule_requires_same_application_replacement(interview_data):
    recruiter_user, _, application, schedule = interview_data
    replacement = InterviewSchedule.objects.create(
        application=application,
        scheduled_by=recruiter_user,
        scheduled_start=timezone.now() + timezone.timedelta(days=3),
        scheduled_end=timezone.now() + timezone.timedelta(days=3, hours=1),
        is_current=False,
    )
    changed = transition_interview(
        schedule=schedule,
        target_status=InterviewSchedule.Status.RESCHEDULED,
        actor=recruiter_user,
        replacement_schedule=replacement,
    )
    replacement.refresh_from_db()
    assert changed.is_current is False
    assert replacement.is_current is True


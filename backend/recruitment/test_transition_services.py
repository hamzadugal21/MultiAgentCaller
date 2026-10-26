import pytest
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditEvent
from candidates.models import CandidateProfile
from recruitment.models import Company, JobApplication, JobPosting, RecruiterProfile
from recruitment.transition_services import (
    APPLICATION_TRANSITIONS,
    JOB_TRANSITIONS,
    InvalidWorkflowTransitionError,
    WorkflowAuthorizationError,
    transition_application,
    transition_job,
)


@pytest.fixture
def workflow_data(db):
    company = Company.objects.create(name="Workflow Company")
    recruiter_user = User.objects.create_user(
        email="workflow-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    recruiter = RecruiterProfile.objects.create(
        user=recruiter_user,
        company=company,
        is_verified=True,
    )
    candidate_user = User.objects.create_user(
        email="workflow-candidate@example.com",
        password="TestPassword123!",
    )
    candidate = CandidateProfile.objects.get(user=candidate_user)
    job = JobPosting.objects.create(
        company=company,
        created_by=recruiter,
        title="Engineer",
        reference_code="WF-001",
        description="Role description",
        application_deadline=timezone.now() + timezone.timedelta(days=7),
    )
    application = JobApplication.objects.create(job=job, candidate=candidate)
    return {
        "company": company,
        "recruiter_user": recruiter_user,
        "recruiter": recruiter,
        "candidate_user": candidate_user,
        "candidate": candidate,
        "job": job,
        "application": application,
    }


@pytest.mark.django_db
def test_job_transition_table_and_canonical_audit(workflow_data):
    assert JobPosting.Status.OPEN in JOB_TRANSITIONS[JobPosting.Status.DRAFT]
    job = transition_job(
        job=workflow_data["job"],
        target_status=JobPosting.Status.OPEN,
        actor=workflow_data["recruiter_user"],
    )
    assert job.status == JobPosting.Status.OPEN
    assert job.published_at is not None
    event = AuditEvent.objects.get(event_type="job.published")
    assert event.metadata == {"status_from": "draft", "status_to": "open"}


@pytest.mark.django_db
def test_job_transition_rejects_forbidden_state_and_wrong_company(workflow_data):
    other_company = Company.objects.create(name="Other Workflow Company")
    other_user = User.objects.create_user(
        email="other-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    RecruiterProfile.objects.create(
        user=other_user, company=other_company, is_verified=True
    )
    with pytest.raises(WorkflowAuthorizationError):
        transition_job(
            job=workflow_data["job"],
            target_status=JobPosting.Status.OPEN,
            actor=other_user,
        )
    workflow_data["job"].status = JobPosting.Status.ARCHIVED
    workflow_data["job"].save(update_fields=("status",))
    with pytest.raises(InvalidWorkflowTransitionError):
        transition_job(
            job=workflow_data["job"],
            target_status=JobPosting.Status.OPEN,
            actor=workflow_data["recruiter_user"],
        )


@pytest.mark.django_db
def test_application_transitions_enforce_actor_and_terminal_states(workflow_data):
    application = transition_application(
        application=workflow_data["application"],
        target_status=JobApplication.Status.SCREENING,
        actor=workflow_data["recruiter_user"],
    )
    assert application.status == JobApplication.Status.SCREENING
    assert JobApplication.Status.WITHDRAWN in APPLICATION_TRANSITIONS["screening"]
    with pytest.raises(WorkflowAuthorizationError):
        transition_application(
            application=application,
            target_status=JobApplication.Status.WITHDRAWN,
            actor=workflow_data["recruiter_user"],
        )
    application = transition_application(
        application=application,
        target_status=JobApplication.Status.WITHDRAWN,
        actor=workflow_data["candidate_user"],
    )
    assert application.status == JobApplication.Status.WITHDRAWN
    with pytest.raises(InvalidWorkflowTransitionError):
        transition_application(
            application=application,
            target_status=JobApplication.Status.SCREENING,
            actor=workflow_data["recruiter_user"],
        )


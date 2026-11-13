import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditEvent, ConsentRecord, DataRetentionRecord
from auditlog.retention_services import (
    CURRENT_RETENTION_POLICY_VERSION,
    RetentionCategory,
    RetentionReplayConflictError,
    RetentionValidationError,
    apply_retention,
    preview_retention,
)
from calling.models import CallSession, SimulatedInterviewResponse, TranscriptSegment
from candidates.models import CandidateProfile
from interviews.models import (
    CandidateEvaluation,
    EvaluationCriterion,
    EvaluationRubric,
    InterviewSchedule,
)
from recruitment.models import (
    Company,
    InterviewQuestion,
    JobApplication,
    JobPosting,
    RecruiterProfile,
)

pytestmark = pytest.mark.django_db


def _session_context(*, label, status=CallSession.Status.COMPLETED, age_days=40):
    company = Company.objects.create(name=f"Synthetic Retention Company {label}")
    recruiter_user = User.objects.create_user(
        email=f"retention-recruiter-{label}@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    recruiter = RecruiterProfile.objects.create(
        user=recruiter_user,
        company=company,
        is_verified=True,
        can_review_candidates=True,
    )
    job = JobPosting.objects.create(
        company=company,
        created_by=recruiter,
        title=f"Synthetic Retention Role {label}",
        reference_code=f"RET-{label}",
        description="Synthetic retention test role.",
    )
    candidate_user = User.objects.create_user(
        email=f"retention-candidate-{label}@example.com",
        password="TestPassword123!",
    )
    candidate = CandidateProfile.objects.get(user=candidate_user)
    application = JobApplication.objects.create(
        job=job,
        candidate=candidate,
        status=JobApplication.Status.INVITED,
    )
    now = timezone.now()
    schedule = InterviewSchedule.objects.create(
        application=application,
        scheduled_by=recruiter_user,
        scheduled_start=now - timezone.timedelta(days=age_days, hours=2),
        scheduled_end=now - timezone.timedelta(days=age_days, hours=1),
        status=InterviewSchedule.Status.COMPLETED,
        is_current=False,
    )
    started_at = now - timezone.timedelta(days=age_days, hours=2)
    terminal = status in {
        CallSession.Status.COMPLETED,
        CallSession.Status.CANCELLED,
        CallSession.Status.EXPIRED,
        CallSession.Status.FAILED,
    }
    session = CallSession.objects.create(
        schedule=schedule,
        status=status,
        started_at=(
            started_at
            if status
            in {
                CallSession.Status.ACTIVE,
                CallSession.Status.PAUSED,
                CallSession.Status.COMPLETED,
            }
            else None
        ),
        ended_at=(now - timezone.timedelta(days=age_days) if terminal else None),
        last_activity_at=now - timezone.timedelta(days=age_days),
        candidate_consent=True,
    )
    question = InterviewQuestion.objects.create(
        job=job,
        question_text="Describe a synthetic retention scenario.",
        question_type=InterviewQuestion.QuestionType.BEHAVIORAL,
        order=1,
    )
    response = SimulatedInterviewResponse.objects.create(
        call_session=session,
        question=question,
        question_index=0,
        answer_text=f"SYNTHETIC_PRIVATE_ANSWER_{label}",
        idempotency_key=uuid.uuid4(),
    )
    transcript = TranscriptSegment.objects.create(
        call_session=session,
        sequence_number=1,
        speaker=TranscriptSegment.Speaker.CANDIDATE,
        text=f"SYNTHETIC_PRIVATE_TRANSCRIPT_{label}",
        redacted_text=f"SYNTHETIC_REDACTED_TRANSCRIPT_{label}",
        start_time_ms=0,
        end_time_ms=1000,
        contains_sensitive_data=True,
    )
    return {
        "application": application,
        "candidate": candidate,
        "company": company,
        "job": job,
        "recruiter_user": recruiter_user,
        "response": response,
        "session": session,
        "transcript": transcript,
    }


def test_default_command_is_read_only_and_requires_apply_for_mutation():
    context = _session_context(label="dry-run")
    output = StringIO()

    call_command(
        "run_retention",
        RetentionCategory.SIMULATED_ANSWERS,
        stdout=output,
    )

    context["response"].refresh_from_db()
    assert context["response"].answer_text == "SYNTHETIC_PRIVATE_ANSWER_dry-run"
    assert not DataRetentionRecord.objects.exists()
    assert not AuditEvent.objects.filter(event_type="retention.applied").exists()
    assert "mode=dry_run" in output.getvalue()
    assert "eligible=1" in output.getvalue()


def test_apply_requires_an_explicit_replay_safe_run_identifier():
    _session_context(label="missing-run-id")

    with pytest.raises(CommandError, match="explicit --run-id UUID"):
        call_command(
            "run_retention",
            RetentionCategory.SIMULATED_ANSWERS,
            "--apply",
        )

    assert not DataRetentionRecord.objects.exists()


def test_selection_anonymizes_only_old_terminal_content_across_companies():
    eligible = _session_context(label="eligible")
    recent = _session_context(label="recent", age_days=5)
    active_other_company = _session_context(
        label="active-other",
        status=CallSession.Status.ACTIVE,
        age_days=40,
    )

    result = apply_retention(
        category=RetentionCategory.SIMULATED_ANSWERS,
        run_id=uuid.uuid4(),
    )

    eligible["response"].refresh_from_db()
    recent["response"].refresh_from_db()
    active_other_company["response"].refresh_from_db()
    assert result.eligible_count == 1
    assert result.processed_count == 1
    assert eligible["response"].answer_text == ""
    assert recent["response"].answer_text == "SYNTHETIC_PRIVATE_ANSWER_recent"
    assert (
        active_other_company["response"].answer_text
        == "SYNTHETIC_PRIVATE_ANSWER_active-other"
    )


def test_transcript_category_clears_content_but_preserves_structure():
    context = _session_context(label="transcript")

    result = apply_retention(
        category=RetentionCategory.TRANSCRIPT_SEGMENTS,
        run_id=uuid.uuid4(),
    )

    context["transcript"].refresh_from_db()
    assert result.processed_count == 1
    assert context["transcript"].text == ""
    assert context["transcript"].redacted_text == ""
    assert context["transcript"].contains_sensitive_data is False
    assert context["transcript"].call_session_id == context["session"].pk
    assert context["transcript"].sequence_number == 1


@pytest.mark.parametrize(
    "overrides",
    (
        {"category": "unsupported_private_records"},
        {"policy_version": "legacy-unversioned"},
        {"policy_version": "contains private prose"},
        {"retention_days": 0},
        {"batch_size": 501},
    ),
)
def test_policy_category_and_bounds_are_validated(overrides):
    values = {
        "category": RetentionCategory.SIMULATED_ANSWERS,
        "policy_version": CURRENT_RETENTION_POLICY_VERSION,
        "retention_days": 30,
        "batch_size": 100,
    }
    values.update(overrides)

    with pytest.raises(RetentionValidationError):
        preview_retention(**values)


def test_apply_is_idempotent_and_conflicting_run_reuse_is_rejected():
    context = _session_context(label="idempotent")
    run_id = uuid.uuid4()

    first = apply_retention(
        category=RetentionCategory.SIMULATED_ANSWERS,
        run_id=run_id,
    )
    replay = apply_retention(
        category=RetentionCategory.SIMULATED_ANSWERS,
        run_id=run_id,
    )

    assert replay.replayed is True
    assert replay.record.pk == first.record.pk
    assert DataRetentionRecord.objects.count() == 1
    assert AuditEvent.objects.filter(event_type="retention.applied").count() == 1
    context["response"].refresh_from_db()
    assert context["response"].answer_text == ""

    with pytest.raises(RetentionReplayConflictError):
        apply_retention(
            category=RetentionCategory.TRANSCRIPT_SEGMENTS,
            run_id=run_id,
        )


def test_required_audit_failure_rolls_back_private_content(monkeypatch):
    context = _session_context(label="rollback")

    def fail_audit(_command):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(
        "auditlog.retention_services.record_domain_event",
        fail_audit,
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        apply_retention(
            category=RetentionCategory.SIMULATED_ANSWERS,
            run_id=uuid.uuid4(),
        )

    context["response"].refresh_from_db()
    assert context["response"].answer_text == "SYNTHETIC_PRIVATE_ANSWER_rollback"
    assert not DataRetentionRecord.objects.exists()


def test_apply_preserves_immutable_governance_and_final_review_records():
    context = _session_context(label="protected")
    consent = ConsentRecord.objects.create(
        candidate=context["candidate"],
        consent_type=ConsentRecord.ConsentType.GENERAL_AI_PROCESSING,
        action=ConsentRecord.Action.GRANTED,
        policy_version="legacy-unversioned",
        collection_source=ConsentRecord.CollectionSource.LEGACY_IMPORT,
    )
    immutable_event = AuditEvent.objects.create(
        category=AuditEvent.Category.SECURITY,
        event_type="synthetic.retention.protection",
        action="Synthetic retention protection evidence",
        outcome=AuditEvent.Outcome.SUCCESS,
    )
    rubric = EvaluationRubric.objects.create(
        job=context["job"],
        name="Synthetic protected rubric",
        version=1,
    )
    EvaluationCriterion.objects.create(
        rubric=rubric,
        name="Synthetic criterion",
        description="Synthetic job criterion.",
        order=1,
        weight="1.000",
    )
    evaluation = CandidateEvaluation.objects.create(
        application=context["application"],
        rubric=rubric,
        source_session=context["session"],
        evaluator_type=CandidateEvaluation.EvaluatorType.HUMAN,
        status=CandidateEvaluation.Status.REVIEWED,
        overall_score="75.00",
        overall_confidence="0.800",
        recommendation=CandidateEvaluation.Recommendation.YES,
        reviewed_by=context["recruiter_user"],
        reviewer_notes="Restricted synthetic review evidence.",
        review_outcome=CandidateEvaluation.ReviewOutcome.ADVANCE,
        is_final=True,
        reviewed_at=timezone.now(),
    )

    apply_retention(
        category=RetentionCategory.SIMULATED_ANSWERS,
        run_id=uuid.uuid4(),
    )

    assert AuditEvent.objects.filter(pk=immutable_event.pk).exists()
    assert ConsentRecord.objects.filter(pk=consent.pk).exists()
    evaluation.refresh_from_db()
    assert evaluation.is_final is True
    assert evaluation.review_outcome == CandidateEvaluation.ReviewOutcome.ADVANCE


def test_command_batch_limit_and_outputs_are_privacy_safe():
    contexts = [
        _session_context(label=f"batch-{index}")
        for index in range(3)
    ]
    output = StringIO()

    call_command(
        "run_retention",
        RetentionCategory.SIMULATED_ANSWERS,
        "--apply",
        "--batch-size=2",
        f"--run-id={uuid.uuid4()}",
        stdout=output,
    )

    remaining = SimulatedInterviewResponse.objects.exclude(answer_text="").count()
    assert remaining == 1
    command_output = output.getvalue()
    assert "eligible=2" in command_output
    assert "processed=2" in command_output
    for context in contexts:
        assert context["response"].answer_text not in command_output
        assert context["candidate"].user.email not in command_output

    event = AuditEvent.objects.get(event_type="retention.applied")
    assert event.metadata == {
        "eligible_count": 2,
        "policy_version": CURRENT_RETENTION_POLICY_VERSION,
        "processed_count": 2,
        "retention_category": RetentionCategory.SIMULATED_ANSWERS,
        "retention_result": DataRetentionRecord.Result.APPLIED,
    }
    audit_text = str(event.metadata)
    assert "SYNTHETIC_PRIVATE" not in audit_text
    assert "candidate-resumes" not in audit_text


def test_command_rejects_invalid_policy_without_exposing_internal_details():
    output = StringIO()
    with pytest.raises(CommandError, match="policy version is not supported"):
        call_command(
            "run_retention",
            RetentionCategory.SIMULATED_ANSWERS,
            "--apply",
            "--policy-version=invalid-policy",
            f"--run-id={uuid.uuid4()}",
            stdout=output,
        )
    assert output.getvalue() == ""

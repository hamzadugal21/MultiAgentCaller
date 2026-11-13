import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditEvent
from calling.models import CallSession, SimulatedInterviewResponse
from candidates.models import CandidateProfile
from interviews.evaluation_services import (
    CriterionReview,
    EvaluationAuthorizationError,
    EvaluationValidationError,
    finalize_human_evaluation,
    save_human_evaluation,
    start_human_evaluation,
)
from interviews.models import (
    CandidateEvaluation,
    CriterionScore,
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


@pytest.fixture
def evaluation_data(db):
    company = Company.objects.create(name="Evaluation Company")
    recruiter_user = User.objects.create_user(
        email="evaluation-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    recruiter = RecruiterProfile.objects.create(
        user=recruiter_user,
        company=company,
        is_verified=True,
        can_review_candidates=True,
    )
    candidate_user = User.objects.create_user(
        email="evaluation-candidate@example.com",
        password="TestPassword123!",
        first_name="Ayesha",
        last_name="Khan",
        email_verified=True,
    )
    candidate = CandidateProfile.objects.get(user=candidate_user)
    job = JobPosting.objects.create(
        company=company,
        created_by=recruiter,
        title="Evaluation Engineer",
        reference_code="EVAL-001",
        description="Synthetic evaluation role.",
        status=JobPosting.Status.OPEN,
    )
    application = JobApplication.objects.create(
        job=job,
        candidate=candidate,
        status=JobApplication.Status.INVITED,
    )
    now = timezone.now()
    schedule = InterviewSchedule.objects.create(
        application=application,
        scheduled_by=recruiter_user,
        scheduled_start=now - timezone.timedelta(hours=2),
        scheduled_end=now - timezone.timedelta(hours=1),
        status=InterviewSchedule.Status.COMPLETED,
        is_current=False,
    )
    session = CallSession.objects.create(
        schedule=schedule,
        status=CallSession.Status.COMPLETED,
        started_at=now - timezone.timedelta(minutes=50),
        ended_at=now - timezone.timedelta(minutes=20),
        last_activity_at=now - timezone.timedelta(minutes=20),
        completion_reason="questions_completed",
        candidate_consent=True,
    )
    question = InterviewQuestion.objects.create(
        job=job,
        question_text="Describe a relevant project.",
        question_type=InterviewQuestion.QuestionType.EXPERIENCE,
        order=1,
    )
    SimulatedInterviewResponse.objects.create(
        call_session=session,
        question=question,
        question_index=0,
        answer_text="Synthetic test answer that must not enter audit metadata.",
        idempotency_key=uuid.uuid4(),
    )
    rubric = EvaluationRubric.objects.create(
        job=job,
        name="Structured reviewer rubric",
        version=1,
        passing_score=Decimal("60"),
        is_active=True,
    )
    criterion_one = EvaluationCriterion.objects.create(
        rubric=rubric,
        name="Relevant experience",
        description="Assess job-related examples.",
        order=1,
        weight=Decimal("0.600"),
        is_required=True,
    )
    criterion_two = EvaluationCriterion.objects.create(
        rubric=rubric,
        name="Communication",
        description="Assess clarity of the response.",
        order=2,
        weight=Decimal("0.400"),
        is_required=True,
    )
    return {
        "application": application,
        "candidate_user": candidate_user,
        "company": company,
        "criteria": (criterion_one, criterion_two),
        "job": job,
        "recruiter": recruiter,
        "recruiter_user": recruiter_user,
        "rubric": rubric,
        "session": session,
    }


def _reviews(data, *, first_score="80", second_score="70"):
    first, second = data["criteria"]
    return (
        CriterionReview(
            criterion_id=first.pk,
            score=first_score,
            confidence="0.8",
            evidence="The candidate gave a concise job-related example.",
            explanation="The example addressed the published criterion.",
        ),
        CriterionReview(
            criterion_id=second.pk,
            score=second_score,
            confidence="0.7",
            evidence="The response was structured and understandable.",
        ),
    )


def _saved_evaluation(data):
    evaluation = start_human_evaluation(
        application=data["application"],
        actor=data["recruiter_user"],
    )
    return save_human_evaluation(
        evaluation=evaluation,
        actor=data["recruiter_user"],
        criterion_reviews=_reviews(data),
        summary="The structured evidence meets the approved rubric.",
        reviewer_notes="Human review completed against job-related criteria.",
    )


def test_start_evaluation_requires_completed_evidence_and_records_safe_audit(
    evaluation_data,
):
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )
    replay = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )

    assert replay.pk == evaluation.pk
    assert evaluation.evaluator_type == CandidateEvaluation.EvaluatorType.HUMAN
    assert evaluation.source_session_id == evaluation_data["session"].pk
    event = AuditEvent.objects.get(event_type="evaluation.started")
    assert event.resource_id == str(evaluation.pk)
    assert event.metadata == {
        "application_id": str(evaluation_data["application"].pk),
        "call_session_id": str(evaluation_data["session"].pk),
        "rubric_id": str(evaluation_data["rubric"].pk),
        "status_to": CandidateEvaluation.Status.PENDING,
    }
    assert "answer" not in str(event.metadata).lower()


def test_start_evaluation_enforces_persisted_reviewer_authority(evaluation_data):
    stale_recruiter = evaluation_data["recruiter_user"]
    User.objects.filter(pk=stale_recruiter.pk).update(role=User.Role.CANDIDATE)

    with pytest.raises(EvaluationAuthorizationError):
        start_human_evaluation(
            application=evaluation_data["application"],
            actor=stale_recruiter,
        )

    assert not CandidateEvaluation.objects.exists()


def test_start_evaluation_rejects_cross_company_and_incomplete_sessions(
    evaluation_data,
):
    other_company = Company.objects.create(name="Other Evaluation Company")
    other_user = User.objects.create_user(
        email="other-evaluator@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    RecruiterProfile.objects.create(
        user=other_user,
        company=other_company,
        is_verified=True,
        can_review_candidates=True,
    )
    with pytest.raises(EvaluationAuthorizationError):
        start_human_evaluation(
            application=evaluation_data["application"],
            actor=other_user,
        )

    evaluation_data["session"].status = CallSession.Status.FAILED
    evaluation_data["session"].save(update_fields=("status",))
    with pytest.raises(EvaluationValidationError):
        start_human_evaluation(
            application=evaluation_data["application"],
            actor=evaluation_data["recruiter_user"],
        )


def test_save_evaluation_calculates_weighted_advisory_result(evaluation_data):
    evaluation = _saved_evaluation(evaluation_data)

    assert evaluation.status == CandidateEvaluation.Status.COMPLETED
    assert evaluation.overall_score == Decimal("76.00")
    assert evaluation.overall_confidence == Decimal("0.760")
    assert evaluation.recommendation == CandidateEvaluation.Recommendation.YES
    assert evaluation.is_final is False
    assert evaluation.criterion_scores.count() == 2
    event = AuditEvent.objects.get(event_type="evaluation.scored")
    assert event.metadata["criterion_count"] == 2
    assert "evidence" not in event.metadata
    assert "summary" not in event.metadata


def test_save_evaluation_requires_complete_valid_rubric_scores(evaluation_data):
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )
    with pytest.raises(EvaluationValidationError):
        save_human_evaluation(
            evaluation=evaluation,
            actor=evaluation_data["recruiter_user"],
            criterion_reviews=_reviews(evaluation_data)[:1],
        )
    with pytest.raises(EvaluationValidationError):
        save_human_evaluation(
            evaluation=evaluation,
            actor=evaluation_data["recruiter_user"],
            criterion_reviews=_reviews(evaluation_data, first_score="101"),
        )


@pytest.mark.parametrize(
    ("outcome", "expected_status"),
    (
        (CandidateEvaluation.ReviewOutcome.ADVANCE, JobApplication.Status.SHORTLISTED),
        (CandidateEvaluation.ReviewOutcome.DECLINE, JobApplication.Status.REJECTED),
    ),
)
def test_human_finalization_controls_application_outcome(
    evaluation_data,
    outcome,
    expected_status,
):
    evaluation = _saved_evaluation(evaluation_data)
    finalized = finalize_human_evaluation(
        evaluation=evaluation,
        actor=evaluation_data["recruiter_user"],
        review_outcome=outcome,
        reviewer_notes="Authorized human outcome with a documented rationale.",
    )

    finalized.application.refresh_from_db()
    assert finalized.is_final is True
    assert finalized.status == CandidateEvaluation.Status.REVIEWED
    assert finalized.reviewed_by_id == evaluation_data["recruiter_user"].pk
    assert finalized.reviewed_at is not None
    assert finalized.application.status == expected_status
    event = AuditEvent.objects.get(event_type="evaluation.finalized")
    assert event.metadata["review_outcome"] == outcome
    assert event.metadata["application_status_to"] == expected_status
    assert "rationale" not in event.metadata


def test_finalization_is_idempotent_but_conflicting_outcome_is_rejected(
    evaluation_data,
):
    evaluation = _saved_evaluation(evaluation_data)
    finalized = finalize_human_evaluation(
        evaluation=evaluation,
        actor=evaluation_data["recruiter_user"],
        review_outcome=CandidateEvaluation.ReviewOutcome.ADVANCE,
        reviewer_notes="Authorized human rationale.",
    )
    replay = finalize_human_evaluation(
        evaluation=finalized,
        actor=evaluation_data["recruiter_user"],
        review_outcome=CandidateEvaluation.ReviewOutcome.ADVANCE,
        reviewer_notes="Authorized human rationale.",
    )
    assert replay.pk == finalized.pk
    with pytest.raises(EvaluationValidationError):
        finalize_human_evaluation(
            evaluation=finalized,
            actor=evaluation_data["recruiter_user"],
            review_outcome=CandidateEvaluation.ReviewOutcome.DECLINE,
            reviewer_notes="Conflicting outcome.",
        )


def test_mandatory_final_audit_failure_rolls_back_outcome(
    evaluation_data,
    monkeypatch,
):
    evaluation = _saved_evaluation(evaluation_data)

    def fail_audit(_command):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(
        "interviews.evaluation_services.record_domain_event",
        fail_audit,
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        finalize_human_evaluation(
            evaluation=evaluation,
            actor=evaluation_data["recruiter_user"],
            review_outcome=CandidateEvaluation.ReviewOutcome.ADVANCE,
            reviewer_notes="This must roll back with the failed audit.",
        )

    evaluation.refresh_from_db()
    evaluation_data["application"].refresh_from_db()
    assert evaluation.is_final is False
    assert evaluation_data["application"].status == JobApplication.Status.INVITED


def test_final_evaluation_model_and_postgresql_triggers_are_immutable(
    evaluation_data,
):
    evaluation = _saved_evaluation(evaluation_data)
    finalized = finalize_human_evaluation(
        evaluation=evaluation,
        actor=evaluation_data["recruiter_user"],
        review_outcome=CandidateEvaluation.ReviewOutcome.ADVANCE,
        reviewer_notes="Authorized human rationale.",
    )
    score = finalized.criterion_scores.first()

    finalized.summary = "Changed"
    with pytest.raises(ValidationError):
        finalized.save()
    with pytest.raises(ValidationError):
        finalized.delete()
    score.evidence = "Changed"
    with pytest.raises(ValidationError):
        score.save()
    with pytest.raises(ValidationError):
        score.delete()

    with pytest.raises(DatabaseError), transaction.atomic():
        CandidateEvaluation.objects.filter(pk=finalized.pk).update(summary="Changed")
    with pytest.raises(DatabaseError), transaction.atomic():
        CriterionScore.objects.filter(pk=score.pk).update(evidence="Changed")


def test_used_rubric_content_and_criteria_are_version_locked(evaluation_data):
    start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )
    rubric = evaluation_data["rubric"]
    criterion = evaluation_data["criteria"][0]

    rubric.name = "Rewritten rubric"
    with pytest.raises(ValidationError):
        rubric.save()
    criterion.weight = Decimal("0.500")
    with pytest.raises(ValidationError):
        criterion.save()
    with pytest.raises(ValidationError):
        EvaluationCriterion.objects.create(
            rubric=rubric,
            name="Late criterion",
            description="Must require a new rubric version.",
            order=3,
            weight=Decimal("0.100"),
        )

    with pytest.raises(DatabaseError), transaction.atomic():
        EvaluationRubric.objects.filter(pk=rubric.pk).update(
            passing_score=Decimal("90")
        )
    with pytest.raises(DatabaseError), transaction.atomic():
        EvaluationCriterion.objects.filter(pk=criterion.pk).update(
            description="Rewritten criterion"
        )
    with pytest.raises(DatabaseError), transaction.atomic():
        EvaluationCriterion.objects.bulk_create(
            [
                EvaluationCriterion(
                    rubric=rubric,
                    name="Bypass criterion",
                    description="Must be rejected by PostgreSQL.",
                    order=4,
                    weight=Decimal("0.100"),
                )
            ]
        )

    assert EvaluationRubric.objects.filter(pk=rubric.pk).update(is_active=False) == 1


def test_evaluation_views_enforce_role_scope_csrf_and_render_safe_content(
    evaluation_data,
):
    start_url = reverse(
        "interviews:evaluation_start",
        args=(evaluation_data["application"].pk,),
    )
    anonymous = Client()
    assert anonymous.post(start_url).status_code == 302

    candidate_client = Client()
    candidate_client.force_login(evaluation_data["candidate_user"])
    assert candidate_client.post(start_url).status_code == 403

    client = Client(enforce_csrf_checks=True)
    client.force_login(evaluation_data["recruiter_user"])
    assert client.post(start_url).status_code == 403

    regular_client = Client()
    regular_client.force_login(evaluation_data["recruiter_user"])
    response = regular_client.post(start_url)
    evaluation = CandidateEvaluation.objects.get()
    assert response.status_code == 302
    assert response.url == reverse(
        "interviews:evaluation_review",
        args=(evaluation.pk,),
    )

    response = regular_client.get(response.url)
    content = response.content.decode()
    assert response.status_code == 200
    assert "Human evaluation review" in content
    assert evaluation_data["rubric"].name in content
    assert "Synthetic test answer" not in content
    assert "Finalize human outcome" in content


def test_evaluation_review_form_saves_and_finalizes_explicit_human_outcome(
    client,
    evaluation_data,
):
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )
    first, second = evaluation_data["criteria"]
    payload = {
        "action": "finalize",
        "summary": "Structured evidence meets the approved rubric.",
        "reviewer_notes": "Authorized human rationale for the recorded outcome.",
        "review_outcome": CandidateEvaluation.ReviewOutcome.ADVANCE,
        f"criterion_{first.pk}_score": "80",
        f"criterion_{first.pk}_confidence": "0.8",
        f"criterion_{first.pk}_evidence": "Concise job-related evidence.",
        f"criterion_{first.pk}_explanation": "Aligned with the criterion.",
        f"criterion_{second.pk}_score": "70",
        f"criterion_{second.pk}_confidence": "0.7",
        f"criterion_{second.pk}_evidence": "Clear structured communication.",
        f"criterion_{second.pk}_explanation": "",
    }
    client.force_login(evaluation_data["recruiter_user"])

    response = client.post(
        reverse("interviews:evaluation_review", args=(evaluation.pk,)),
        payload,
    )

    assert response.status_code == 302
    evaluation.refresh_from_db()
    evaluation_data["application"].refresh_from_db()
    assert evaluation.is_final is True
    assert evaluation.review_outcome == CandidateEvaluation.ReviewOutcome.ADVANCE
    assert evaluation_data["application"].status == JobApplication.Status.SHORTLISTED


def test_evaluation_review_view_rejects_cross_company_reviewer(
    client,
    evaluation_data,
):
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )
    other_company = Company.objects.create(name="Evaluation View Other Company")
    other_user = User.objects.create_user(
        email="evaluation-view-other@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    RecruiterProfile.objects.create(
        user=other_user,
        company=other_company,
        is_verified=True,
        can_review_candidates=True,
    )
    client.force_login(other_user)

    response = client.get(
        reverse("interviews:evaluation_review", args=(evaluation.pk,))
    )

    assert response.status_code == 404


def test_application_detail_shows_only_authorized_evaluation_entry_point(
    client,
    evaluation_data,
):
    client.force_login(evaluation_data["recruiter_user"])
    detail_url = reverse(
        "recruitment:application_detail",
        args=(evaluation_data["application"].pk,),
    )
    response = client.get(detail_url)
    assert response.status_code == 200
    assert "Begin human review" in response.content.decode()

    evaluation = _saved_evaluation(evaluation_data)
    response = client.get(detail_url)
    content = response.content.decode()
    assert "Continue human review" in content
    assert reverse("interviews:evaluation_review", args=(evaluation.pk,)) in content
    assert evaluation.criterion_scores.first().evidence not in content


def test_identical_inputs_produce_repeatable_weighted_results(evaluation_data):
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )

    first = save_human_evaluation(
        evaluation=evaluation,
        actor=evaluation_data["recruiter_user"],
        criterion_reviews=_reviews(evaluation_data),
        summary="A deterministic synthetic review.",
        reviewer_notes="Restricted human notes.",
    )
    first_result = (
        first.overall_score,
        first.overall_confidence,
        first.recommendation,
        tuple(
            first.criterion_scores.order_by("criterion__order").values_list(
                "score",
                "confidence",
            )
        ),
    )

    replay = save_human_evaluation(
        evaluation=evaluation,
        actor=evaluation_data["recruiter_user"],
        criterion_reviews=_reviews(evaluation_data),
        summary="A deterministic synthetic review.",
        reviewer_notes="Restricted human notes.",
    )
    replay_result = (
        replay.overall_score,
        replay.overall_confidence,
        replay.recommendation,
        tuple(
            replay.criterion_scores.order_by("criterion__order").values_list(
                "score",
                "confidence",
            )
        ),
    )

    assert replay_result == first_result
    assert replay.is_final is False
    evaluation_data["application"].refresh_from_db()
    assert evaluation_data["application"].status == JobApplication.Status.INVITED


def test_completed_evaluation_keeps_its_exact_rubric_version(evaluation_data):
    evaluation = _saved_evaluation(evaluation_data)
    original_rubric_id = evaluation.rubric_id

    EvaluationRubric.objects.filter(pk=original_rubric_id).update(is_active=False)
    replacement = EvaluationRubric.objects.create(
        job=evaluation_data["job"],
        name="Replacement structured rubric",
        version=2,
        passing_score=Decimal("65"),
        is_active=True,
    )
    EvaluationCriterion.objects.create(
        rubric=replacement,
        name="Replacement criterion",
        description="A new versioned job criterion.",
        order=1,
        weight=Decimal("1.000"),
    )

    evaluation.refresh_from_db()
    assert evaluation.rubric_id == original_rubric_id
    assert evaluation.rubric.version == 1
    assert evaluation.rubric_id != replacement.pk


@pytest.mark.parametrize(
    ("score", "recommendation"),
    (
        ("80", CandidateEvaluation.Recommendation.STRONG_YES),
        ("79.99", CandidateEvaluation.Recommendation.YES),
        ("60", CandidateEvaluation.Recommendation.YES),
        ("59.99", CandidateEvaluation.Recommendation.REVIEW),
        ("50", CandidateEvaluation.Recommendation.REVIEW),
        ("49.99", CandidateEvaluation.Recommendation.NO),
        ("35", CandidateEvaluation.Recommendation.NO),
        ("34.99", CandidateEvaluation.Recommendation.STRONG_NO),
    ),
)
def test_recommendation_thresholds_are_deterministic(
    evaluation_data,
    score,
    recommendation,
):
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )
    saved = save_human_evaluation(
        evaluation=evaluation,
        actor=evaluation_data["recruiter_user"],
        criterion_reviews=_reviews(
            evaluation_data,
            first_score=score,
            second_score=score,
        ),
    )

    assert saved.overall_score == Decimal(score).quantize(Decimal("0.01"))
    assert saved.recommendation == recommendation
    assert saved.is_final is False


def test_score_confidence_weight_and_passing_score_bounds_are_validated(
    evaluation_data,
):
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )
    first, second = evaluation_data["criteria"]
    invalid_reviews = (
        CriterionReview(
            criterion_id=first.pk,
            score="101",
            confidence="0.8",
            evidence="Synthetic job-related evidence.",
        ),
        CriterionReview(
            criterion_id=second.pk,
            score="70",
            confidence="1.001",
            evidence="Synthetic job-related evidence.",
        ),
    )
    with pytest.raises(EvaluationValidationError):
        save_human_evaluation(
            evaluation=evaluation,
            actor=evaluation_data["recruiter_user"],
            criterion_reviews=invalid_reviews,
        )

    evaluation_data["rubric"].passing_score = Decimal("100.01")
    with pytest.raises(ValidationError):
        evaluation_data["rubric"].full_clean()
    first.weight = Decimal("1.001")
    with pytest.raises(ValidationError):
        first.full_clean()


def test_missing_evidence_is_honestly_rejected_without_partial_result(
    evaluation_data,
):
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )
    first, second = evaluation_data["criteria"]
    reviews = (
        CriterionReview(first.pk, "80", "0.8", ""),
        CriterionReview(second.pk, "70", "0.7", "Synthetic evidence."),
    )

    with pytest.raises(
        EvaluationValidationError,
        match="valid criterion evidence",
    ):
        save_human_evaluation(
            evaluation=evaluation,
            actor=evaluation_data["recruiter_user"],
            criterion_reviews=reviews,
        )

    evaluation.refresh_from_db()
    assert evaluation.status == CandidateEvaluation.Status.PENDING
    assert evaluation.overall_score is None
    assert not evaluation.criterion_scores.exists()
    assert not AuditEvent.objects.filter(event_type="evaluation.scored").exists()


def test_inactive_invalid_weight_and_wrong_job_rubrics_cannot_be_used(
    evaluation_data,
):
    EvaluationRubric.objects.filter(pk=evaluation_data["rubric"].pk).update(
        is_active=False
    )
    with pytest.raises(EvaluationValidationError, match="active evaluation rubric"):
        start_human_evaluation(
            application=evaluation_data["application"],
            actor=evaluation_data["recruiter_user"],
        )

    EvaluationRubric.objects.filter(pk=evaluation_data["rubric"].pk).update(
        is_active=True
    )
    first, second = evaluation_data["criteria"]
    EvaluationCriterion.objects.filter(pk=first.pk).update(weight=Decimal("0.500"))
    with pytest.raises(EvaluationValidationError, match="rubric is not ready"):
        start_human_evaluation(
            application=evaluation_data["application"],
            actor=evaluation_data["recruiter_user"],
        )
    EvaluationCriterion.objects.filter(pk=first.pk).update(weight=Decimal("0.600"))

    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )
    other_company = Company.objects.create(name="Foreign Rubric Company")
    other_recruiter_user = User.objects.create_user(
        email="foreign-rubric-recruiter@example.com",
        password="TestPassword123!",
        role=User.Role.RECRUITER,
    )
    other_recruiter = RecruiterProfile.objects.create(
        user=other_recruiter_user,
        company=other_company,
        is_verified=True,
    )
    other_job = JobPosting.objects.create(
        company=other_company,
        created_by=other_recruiter,
        title="Foreign rubric job",
        reference_code="FOREIGN-RUBRIC",
        description="Synthetic foreign role.",
    )
    other_rubric = EvaluationRubric.objects.create(
        job=other_job,
        name="Foreign rubric",
        version=1,
    )
    foreign_criterion = EvaluationCriterion.objects.create(
        rubric=other_rubric,
        name="Foreign criterion",
        description="Must not be accepted.",
        order=1,
        weight=Decimal("1.000"),
    )
    reviews = (
        CriterionReview(first.pk, "80", "0.8", "Synthetic evidence."),
        CriterionReview(second.pk, "70", "0.7", "Synthetic evidence."),
        CriterionReview(
            foreign_criterion.pk,
            "90",
            "0.9",
            "Foreign synthetic evidence.",
        ),
    )
    with pytest.raises(EvaluationValidationError, match="invalid criterion"):
        save_human_evaluation(
            evaluation=evaluation,
            actor=evaluation_data["recruiter_user"],
            criterion_reviews=reviews,
        )


def test_demographic_and_unrelated_profile_fields_do_not_change_scoring(
    evaluation_data,
):
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )
    initial = save_human_evaluation(
        evaluation=evaluation,
        actor=evaluation_data["recruiter_user"],
        criterion_reviews=_reviews(evaluation_data),
    )
    baseline = (
        initial.overall_score,
        initial.overall_confidence,
        initial.recommendation,
    )

    candidate_user = evaluation_data["candidate_user"]
    candidate_user.first_name = "Synthetic Changed"
    candidate_user.last_name = "Identity"
    candidate_user.save(update_fields=("first_name", "last_name"))
    candidate = candidate_user.candidate_profile
    candidate.city = "Synthetic City"
    candidate.country_code = "GB"
    candidate.timezone = "Europe/London"
    candidate.professional_summary = "Unrelated synthetic profile text."
    candidate.save(
        update_fields=(
            "city",
            "country_code",
            "timezone",
            "professional_summary",
            "updated_at",
        )
    )

    repeated = save_human_evaluation(
        evaluation=evaluation,
        actor=evaluation_data["recruiter_user"],
        criterion_reviews=_reviews(evaluation_data),
    )
    assert (
        repeated.overall_score,
        repeated.overall_confidence,
        repeated.recommendation,
    ) == baseline
    model_fields = {field.name for field in CandidateEvaluation._meta.get_fields()}
    assert not model_fields & {
        "age",
        "date_of_birth",
        "ethnicity",
        "gender",
        "nationality",
        "protected_traits",
        "rank",
    }


def test_low_confidence_result_remains_advisory_until_explicit_human_action(
    evaluation_data,
):
    first, second = evaluation_data["criteria"]
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )
    saved = save_human_evaluation(
        evaluation=evaluation,
        actor=evaluation_data["recruiter_user"],
        criterion_reviews=(
            CriterionReview(first.pk, "95", "0.01", "Synthetic evidence."),
            CriterionReview(second.pk, "95", "0.01", "Synthetic evidence."),
        ),
    )

    evaluation_data["application"].refresh_from_db()
    assert saved.overall_confidence == Decimal("0.010")
    assert saved.recommendation == CandidateEvaluation.Recommendation.STRONG_YES
    assert saved.is_final is False
    assert saved.review_outcome == ""
    assert evaluation_data["application"].status == JobApplication.Status.INVITED


def test_scoring_audit_failure_rolls_back_scores_and_result(
    evaluation_data,
    monkeypatch,
):
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )

    def fail_scored_audit(command):
        if command.event_type == "evaluation.scored":
            raise RuntimeError("audit unavailable")
        return None

    monkeypatch.setattr(
        "interviews.evaluation_services.record_domain_event",
        fail_scored_audit,
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        save_human_evaluation(
            evaluation=evaluation,
            actor=evaluation_data["recruiter_user"],
            criterion_reviews=_reviews(evaluation_data),
        )

    evaluation.refresh_from_db()
    assert evaluation.status == CandidateEvaluation.Status.PENDING
    assert evaluation.overall_score is None
    assert not evaluation.criterion_scores.exists()


def test_restricted_review_notes_and_source_evidence_are_not_rendered_or_audited(
    client,
    evaluation_data,
):
    restricted_notes = "Restricted reviewer note sentinel."
    source_answer = "Synthetic test answer that must not enter audit metadata."
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )
    saved = save_human_evaluation(
        evaluation=evaluation,
        actor=evaluation_data["recruiter_user"],
        criterion_reviews=_reviews(evaluation_data),
        summary="Safe job-related summary.",
        reviewer_notes=restricted_notes,
    )
    finalized = finalize_human_evaluation(
        evaluation=saved,
        actor=evaluation_data["recruiter_user"],
        review_outcome=CandidateEvaluation.ReviewOutcome.ADVANCE,
        reviewer_notes=restricted_notes,
    )

    client.force_login(evaluation_data["recruiter_user"])
    response = client.get(
        reverse("interviews:evaluation_review", args=(finalized.pk,))
    )
    content = response.content.decode()
    assert response.status_code == 200
    assert restricted_notes not in content
    assert source_answer not in content
    assert evaluation_data["candidate_user"].email not in content

    audit_text = " ".join(
        str(value)
        for value in AuditEvent.objects.filter(
            event_type__startswith="evaluation."
        ).values_list("metadata", flat=True)
    )
    for forbidden in (
        restricted_notes,
        source_answer,
        evaluation_data["candidate_user"].email,
        "candidate-resumes/",
        "password",
        "token",
        "secret",
    ):
        assert forbidden.casefold() not in audit_text.casefold()


def test_review_endpoints_reject_ineligible_roles_get_mutation_and_missing_csrf(
    evaluation_data,
):
    start_url = reverse(
        "interviews:evaluation_start",
        args=(evaluation_data["application"].pk,),
    )
    recruiter = evaluation_data["recruiter"]
    recruiter_user = evaluation_data["recruiter_user"]

    authorized = Client()
    authorized.force_login(recruiter_user)
    assert authorized.get(start_url).status_code == 405

    administrator = User.objects.create_superuser(
        email="evaluation-admin@example.com",
        password="TestPassword123!",
    )
    admin_client = Client()
    admin_client.force_login(administrator)
    assert admin_client.post(start_url).status_code == 403

    recruiter.is_verified = False
    recruiter.save(update_fields=("is_verified",))
    assert authorized.post(start_url).status_code == 403
    recruiter.is_verified = True
    recruiter.can_review_candidates = False
    recruiter.save(update_fields=("is_verified", "can_review_candidates"))
    assert authorized.post(start_url).status_code == 403

    recruiter.can_review_candidates = True
    recruiter.save(update_fields=("can_review_candidates",))
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=recruiter_user,
    )
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(recruiter_user)
    review_url = reverse("interviews:evaluation_review", args=(evaluation.pk,))
    assert csrf_client.post(
        review_url,
        {"action": "finalize"},
    ).status_code == 403

    saved = save_human_evaluation(
        evaluation=evaluation,
        actor=recruiter_user,
        criterion_reviews=_reviews(evaluation_data),
    )
    page = csrf_client.get(review_url)
    assert page.status_code == 200
    csrf_token = csrf_client.cookies["csrftoken"].value
    first, second = evaluation_data["criteria"]
    response = csrf_client.post(
        review_url,
        {
            "csrfmiddlewaretoken": csrf_token,
            "action": "finalize",
            "summary": saved.summary,
            "reviewer_notes": "Explicit authorized human rationale.",
            "review_outcome": CandidateEvaluation.ReviewOutcome.ADVANCE,
            f"criterion_{first.pk}_score": "80",
            f"criterion_{first.pk}_confidence": "0.8",
            f"criterion_{first.pk}_evidence": "Concise job-related evidence.",
            f"criterion_{first.pk}_explanation": "",
            f"criterion_{second.pk}_score": "70",
            f"criterion_{second.pk}_confidence": "0.7",
            f"criterion_{second.pk}_evidence": "Structured job-related evidence.",
            f"criterion_{second.pk}_explanation": "",
        },
    )
    assert response.status_code == 302
    evaluation.refresh_from_db()
    assert evaluation.is_final is True


def test_deterministic_evaluation_uses_a_bounded_local_query_budget(
    evaluation_data,
    django_assert_max_num_queries,
):
    evaluation = start_human_evaluation(
        application=evaluation_data["application"],
        actor=evaluation_data["recruiter_user"],
    )

    # This is a generous local database-query regression bound, not a production
    # latency claim. The service performs no network, model, audio, or sleep work.
    with django_assert_max_num_queries(40):
        saved = save_human_evaluation(
            evaluation=evaluation,
            actor=evaluation_data["recruiter_user"],
            criterion_reviews=_reviews(evaluation_data),
        )

    assert saved.status == CandidateEvaluation.Status.COMPLETED

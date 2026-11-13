from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from auditlog.models import AuditEvent
from auditlog.services import AuditCommand, record_domain_event
from calling.models import CallSession
from interviews.models import (
    CandidateEvaluation,
    CriterionScore,
    EvaluationCriterion,
    EvaluationRubric,
)
from recruitment.models import JobApplication, RecruiterProfile
from recruitment.transition_services import transition_application


class EvaluationServiceError(Exception):
    """Raised when an evaluation operation cannot be completed safely."""


class EvaluationAuthorizationError(EvaluationServiceError):
    """Raised when the persisted actor cannot review the application."""


class EvaluationValidationError(EvaluationServiceError):
    """Raised when rubric scores or review data are incomplete or invalid."""


@dataclass(frozen=True, slots=True)
class CriterionReview:
    criterion_id: object
    score: Decimal | int | str
    confidence: Decimal | int | str
    evidence: str
    explanation: str = ""


def _reviewer(actor, *, company_id):
    actor_id = getattr(actor, "pk", None)
    try:
        persisted = User.objects.get(
            pk=actor_id,
            is_active=True,
            role=User.Role.RECRUITER,
        )
        recruiter = RecruiterProfile.objects.select_related("company").get(
            user=persisted,
            company_id=company_id,
            company__is_active=True,
            is_verified=True,
            can_review_candidates=True,
        )
    except (TypeError, ValueError, User.DoesNotExist, RecruiterProfile.DoesNotExist) as error:
        raise EvaluationAuthorizationError("The reviewer is not authorized.") from error
    return persisted, recruiter


def _safe_review_text(value, *, label, maximum, required=False):
    if not isinstance(value, str):
        raise EvaluationValidationError(f"A valid {label} is required.")
    value = value.strip()
    if required and not value:
        raise EvaluationValidationError(f"A valid {label} is required.")
    if len(value) > maximum or any(ord(character) < 32 and character not in "\n\t" for character in value):
        raise EvaluationValidationError(f"A valid {label} is required.")
    return value


def _bounded_decimal(value, *, label, minimum, maximum, places):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise EvaluationValidationError(f"A valid {label} is required.") from error
    if not number.is_finite() or number < minimum or number > maximum:
        raise EvaluationValidationError(f"A valid {label} is required.")
    quantum = Decimal("1").scaleb(-places)
    return number.quantize(quantum, rounding=ROUND_HALF_UP)


def _rubric_for_job(job_id):
    rubric = (
        EvaluationRubric.objects.select_for_update()
        .filter(job_id=job_id, is_active=True)
        .first()
    )
    if rubric is None:
        raise EvaluationValidationError("An active evaluation rubric is required.")
    criteria = list(
        EvaluationCriterion.objects.select_for_update()
        .filter(rubric=rubric)
        .order_by("order")
    )
    if not criteria or sum((criterion.weight for criterion in criteria), Decimal("0")) != Decimal("1"):
        raise EvaluationValidationError("The active evaluation rubric is not ready.")
    return rubric, criteria


def _completed_session(application_id, source_session=None):
    sessions = CallSession.objects.filter(
        schedule__application_id=application_id,
        status=CallSession.Status.COMPLETED,
    ).select_related("schedule")
    if source_session is not None:
        sessions = sessions.filter(pk=getattr(source_session, "pk", None))
    session = sessions.order_by("-ended_at", "-created_at").first()
    if session is None:
        raise EvaluationValidationError("A completed interview is required.")
    if session.simulated_mode and not session.simulated_responses.exists():
        raise EvaluationValidationError("A completed interview response is required.")
    return session


def start_human_evaluation(*, application, actor, source_session=None):
    with transaction.atomic():
        try:
            application = (
                JobApplication.objects.select_for_update()
                .select_related("job__company")
                .get(pk=application.pk)
            )
        except (AttributeError, JobApplication.DoesNotExist) as error:
            raise EvaluationValidationError("The application is not available.") from error
        actor, _recruiter = _reviewer(actor, company_id=application.job.company_id)
        if application.status not in {
            JobApplication.Status.INVITED,
            JobApplication.Status.INTERVIEWED,
        }:
            raise EvaluationValidationError("The application is not ready for evaluation.")
        final = CandidateEvaluation.objects.filter(
            application=application,
            is_final=True,
        ).first()
        if final is not None:
            return final
        rubric, _criteria = _rubric_for_job(application.job_id)
        session = _completed_session(application.pk, source_session)
        existing = CandidateEvaluation.objects.filter(
            application=application,
            is_final=False,
        ).first()
        if existing is not None:
            if existing.rubric_id != rubric.pk or existing.source_session_id != session.pk:
                raise EvaluationValidationError("An evaluation draft already exists.")
            return existing
        evaluation = CandidateEvaluation.objects.create(
            application=application,
            rubric=rubric,
            source_session=session,
            evaluator_type=CandidateEvaluation.EvaluatorType.HUMAN,
            status=CandidateEvaluation.Status.PENDING,
        )
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.INTERVIEW,
                event_type="evaluation.started",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="interviews.CandidateEvaluation",
                resource_id=evaluation.pk,
                actor=actor,
                metadata={
                    "application_id": application.pk,
                    "call_session_id": session.pk,
                    "rubric_id": rubric.pk,
                    "status_to": CandidateEvaluation.Status.PENDING,
                },
            )
        )
        return evaluation


def _recommendation(*, score, passing_score):
    if score >= min(Decimal("100"), passing_score + Decimal("20")):
        return CandidateEvaluation.Recommendation.STRONG_YES
    if score >= passing_score:
        return CandidateEvaluation.Recommendation.YES
    if score >= max(Decimal("0"), passing_score - Decimal("10")):
        return CandidateEvaluation.Recommendation.REVIEW
    if score >= max(Decimal("0"), passing_score - Decimal("25")):
        return CandidateEvaluation.Recommendation.NO
    return CandidateEvaluation.Recommendation.STRONG_NO


def save_human_evaluation(
    *,
    evaluation,
    actor,
    criterion_reviews,
    summary="",
    reviewer_notes="",
):
    with transaction.atomic():
        try:
            locked = (
                CandidateEvaluation.objects.select_for_update(of=("self",))
                .select_related("application__job__company", "rubric", "source_session")
                .get(pk=evaluation.pk)
            )
        except (AttributeError, CandidateEvaluation.DoesNotExist) as error:
            raise EvaluationValidationError("The evaluation is not available.") from error
        actor, _recruiter = _reviewer(
            actor,
            company_id=locked.application.job.company_id,
        )
        if locked.is_final:
            raise EvaluationValidationError("The final evaluation cannot be changed.")
        if locked.rubric.job_id != locked.application.job_id:
            raise EvaluationValidationError("The evaluation rubric is not valid.")
        if locked.source_session_id is None:
            raise EvaluationValidationError("A completed interview is required.")
        _completed_session(locked.application_id, locked.source_session)

        criteria = list(locked.rubric.criteria.all())
        if not criteria or sum((criterion.weight for criterion in criteria), Decimal("0")) != Decimal("1"):
            raise EvaluationValidationError("The evaluation rubric is not ready.")
        reviews = list(criterion_reviews)
        review_by_id = {str(review.criterion_id): review for review in reviews}
        if len(review_by_id) != len(reviews):
            raise EvaluationValidationError("Each criterion may be scored once.")
        criterion_by_id = {str(criterion.pk): criterion for criterion in criteria}
        if not set(review_by_id) <= set(criterion_by_id):
            raise EvaluationValidationError("The evaluation contains an invalid criterion.")
        missing_required = {
            str(criterion.pk)
            for criterion in criteria
            if criterion.is_required and str(criterion.pk) not in review_by_id
        }
        if missing_required:
            raise EvaluationValidationError("All required criteria must be scored.")

        normalized = []
        for criterion_id, review in review_by_id.items():
            criterion = criterion_by_id[criterion_id]
            normalized.append(
                (
                    criterion,
                    _bounded_decimal(
                        review.score,
                        label="criterion score",
                        minimum=Decimal("0"),
                        maximum=Decimal("100"),
                        places=2,
                    ),
                    _bounded_decimal(
                        review.confidence,
                        label="criterion confidence",
                        minimum=Decimal("0"),
                        maximum=Decimal("1"),
                        places=3,
                    ),
                    _safe_review_text(
                        review.evidence,
                        label="criterion evidence",
                        maximum=1200,
                        required=criterion.is_required,
                    ),
                    _safe_review_text(
                        review.explanation,
                        label="criterion explanation",
                        maximum=1200,
                    ),
                )
            )
        if not normalized:
            raise EvaluationValidationError("At least one criterion must be scored.")

        total_weight = sum((item[0].weight for item in normalized), Decimal("0"))
        weighted_score = sum((item[1] * item[0].weight for item in normalized), Decimal("0")) / total_weight
        weighted_confidence = sum((item[2] * item[0].weight for item in normalized), Decimal("0")) / total_weight
        overall_score = weighted_score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        overall_confidence = weighted_confidence.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        status_from = locked.status

        CriterionScore.objects.filter(evaluation=locked).delete()
        CriterionScore.objects.bulk_create(
            [
                CriterionScore(
                    evaluation=locked,
                    criterion=criterion,
                    score=score,
                    confidence=confidence,
                    evidence=evidence,
                    explanation=explanation,
                )
                for criterion, score, confidence, evidence, explanation in normalized
            ]
        )
        locked.evaluator_type = CandidateEvaluation.EvaluatorType.HUMAN
        locked.status = CandidateEvaluation.Status.COMPLETED
        locked.overall_score = overall_score
        locked.overall_confidence = overall_confidence
        locked.recommendation = _recommendation(
            score=overall_score,
            passing_score=locked.rubric.passing_score,
        )
        locked.summary = _safe_review_text(
            summary,
            label="evaluation summary",
            maximum=2000,
        )
        locked.reviewer_notes = _safe_review_text(
            reviewer_notes,
            label="reviewer notes",
            maximum=2000,
        )
        locked.completed_at = timezone.now()
        locked.save()
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.INTERVIEW,
                event_type="evaluation.scored",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="interviews.CandidateEvaluation",
                resource_id=locked.pk,
                actor=actor,
                metadata={
                    "application_id": locked.application_id,
                    "call_session_id": locked.source_session_id,
                    "criterion_count": len(normalized),
                    "recommendation": locked.recommendation,
                    "rubric_id": locked.rubric_id,
                    "status_from": status_from,
                    "status_to": locked.status,
                },
            )
        )
        return locked


def finalize_human_evaluation(*, evaluation, actor, review_outcome, reviewer_notes):
    with transaction.atomic():
        try:
            locked = (
                CandidateEvaluation.objects.select_for_update(of=("self",))
                .select_related("application__job__company", "rubric", "source_session")
                .get(pk=evaluation.pk)
            )
        except (AttributeError, CandidateEvaluation.DoesNotExist) as error:
            raise EvaluationValidationError("The evaluation is not available.") from error
        actor, _recruiter = _reviewer(
            actor,
            company_id=locked.application.job.company_id,
        )
        if review_outcome not in CandidateEvaluation.ReviewOutcome.values:
            raise EvaluationValidationError("A valid human review outcome is required.")
        notes = _safe_review_text(
            reviewer_notes,
            label="reviewer notes",
            maximum=2000,
            required=True,
        )
        if locked.is_final:
            if locked.review_outcome == review_outcome and locked.reviewed_by_id == actor.pk:
                return locked
            raise EvaluationValidationError("The final evaluation cannot be changed.")
        if locked.status != CandidateEvaluation.Status.COMPLETED:
            raise EvaluationValidationError("The evaluation must be completed first.")
        criteria = list(locked.rubric.criteria.all())
        scored_ids = set(locked.criterion_scores.values_list("criterion_id", flat=True))
        if any(criterion.is_required and criterion.pk not in scored_ids for criterion in criteria):
            raise EvaluationValidationError("All required criteria must be scored.")

        application = JobApplication.objects.select_for_update().get(
            pk=locked.application_id
        )
        application_status_from = application.status
        if application.status == JobApplication.Status.INVITED:
            application = transition_application(
                application=application,
                target_status=JobApplication.Status.INTERVIEWED,
                actor=actor,
            )
        if application.status != JobApplication.Status.INTERVIEWED:
            raise EvaluationValidationError("The application is not ready for final review.")
        target_status = (
            JobApplication.Status.SHORTLISTED
            if review_outcome == CandidateEvaluation.ReviewOutcome.ADVANCE
            else JobApplication.Status.REJECTED
        )
        application = transition_application(
            application=application,
            target_status=target_status,
            actor=actor,
        )

        status_from = locked.status
        locked.status = CandidateEvaluation.Status.REVIEWED
        locked.review_outcome = review_outcome
        locked.reviewer_notes = notes
        locked.reviewed_by = actor
        locked.reviewed_at = timezone.now()
        locked.is_final = True
        locked.save()
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.INTERVIEW,
                event_type="evaluation.finalized",
                outcome=AuditEvent.Outcome.SUCCESS,
                severity=AuditEvent.Severity.INFO,
                resource_type="interviews.CandidateEvaluation",
                resource_id=locked.pk,
                actor=actor,
                metadata={
                    "application_id": locked.application_id,
                    "application_status_from": application_status_from,
                    "application_status_to": application.status,
                    "call_session_id": locked.source_session_id,
                    "criterion_count": len(scored_ids),
                    "recommendation": locked.recommendation,
                    "review_outcome": locked.review_outcome,
                    "rubric_id": locked.rubric_id,
                    "status_from": status_from,
                    "status_to": locked.status,
                },
            )
        )
        return locked

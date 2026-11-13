"""Fail-closed QA-only Qwen-to-Django interview release workflow."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from decimal import Decimal

from ai_system.agents.gateway import AgentRequest, DetachedAgentGateway
from ai_system.framework.agents import AgentName, BoundedAgentRunner
from ai_system.interview.coordinator import (
    CoordinatorAction,
    CoordinatorCommand,
    CoordinatorDirective,
    DeterministicInterviewCoordinator,
)
from ai_system.rag.service import (
    LocalMiniLMEmbedder,
    RagDocument,
    RetrievalPrincipal,
    SharedRagService,
)
from ai_system.runtime.llama_cpp import LlamaCppServerRuntime, LocalLlmError
from ai_system.runtime.qa_preflight import (
    get_preflight_runtime,
    get_preflight_speech_results,
)
from ai_system.voice.qa_speech_client import QaSpeechClientError, run_speech_worker
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import User
from agents.escalation_services import record_technical_failure
from auditlog.consent_services import (
    grant_application_ai_interview_consent,
    grant_general_ai_processing_consent,
)
from auditlog.models import AuditEvent
from calling.coordinator_tools import DjangoInterviewCoordinatorTools
from calling.models import CallSession, SimulatedInterviewResponse, TranscriptSegment
from calling.services import prepare_simulated_call_session
from candidates.models import CandidateProfile
from interviews.evaluation_services import (
    CriterionReview,
    save_human_evaluation,
    start_human_evaluation,
)
from interviews.models import EvaluationCriterion, EvaluationRubric, InterviewSchedule
from recruitment.models import (
    Company,
    InterviewQuestion,
    JobApplication,
    JobPosting,
    RecruiterProfile,
)

EXPECTED_QA_DATABASE = "hireflow_qa_release"
EXPECTED_QA_ROLE = "hireflow_qa_runner"
_QA_LABEL = re.compile(r"QA_[A-Z0-9_]{3,32}\Z")
_QUESTIONS = (
    "Describe a concrete testing example and how you handled a failure.",
    "How do you protect important database state changes?",
    "How do you communicate and handle a critical release issue?",
)


class QaReleaseError(RuntimeError):
    """Safe failure for the isolated release workflow."""


@dataclass(frozen=True, slots=True)
class QaInterviewFixture:
    label: str
    company: Company
    recruiter_user: User
    candidate_user: User
    candidate: CandidateProfile
    application: JobApplication
    schedule: InterviewSchedule
    session: CallSession
    questions: tuple[InterviewQuestion, ...]
    rubric: EvaluationRubric
    criteria: tuple[EvaluationCriterion, ...]


def validate_qa_label(label: str) -> str:
    if not isinstance(label, str) or not _QA_LABEL.fullmatch(label):
        raise QaReleaseError("qa_label_invalid")
    return label


def verify_qa_write_boundary() -> tuple[str, str]:
    """Recheck the exact connected identity immediately before QA writes."""
    if settings.SETTINGS_MODULE != "config.settings_qa":
        raise QaReleaseError("qa_settings_required")
    if not getattr(settings, "QA_MODEL_ACTIONS_ENABLED", False):
        raise QaReleaseError("qa_model_actions_disabled")
    configured = settings.DATABASES["default"]
    if (
        configured["NAME"] != EXPECTED_QA_DATABASE
        or configured["USER"] != EXPECTED_QA_ROLE
    ):
        raise QaReleaseError("qa_configuration_identity_invalid")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user")
        database_name, database_role = cursor.fetchone()
    if database_name != EXPECTED_QA_DATABASE or database_role != EXPECTED_QA_ROLE:
        raise QaReleaseError("qa_connection_identity_invalid")
    return database_name, database_role


def _create_fixture(*, label: str, questions: tuple[str, ...]) -> QaInterviewFixture:
    validate_qa_label(label)
    policy = settings.CURRENT_AI_CONSENT_POLICY_VERSION
    now = timezone.now()
    email_stem = label.lower()
    with transaction.atomic():
        company = Company.objects.create(
            name=f"{label} Company",
            description="Synthetic isolated QA release evidence only.",
        )
        recruiter_user = User.objects.create_user(
            email=f"{email_stem}_recruiter@example.invalid",
            password=None,
            role=User.Role.RECRUITER,
            email_verified=True,
        )
        recruiter = RecruiterProfile.objects.create(
            user=recruiter_user,
            company=company,
            is_verified=True,
            can_manage_jobs=True,
            can_review_candidates=True,
        )
        job = JobPosting.objects.create(
            company=company,
            created_by=recruiter,
            title=f"{label} Synthetic QA Engineer",
            reference_code=label,
            description="Synthetic Django and PostgreSQL quality-assurance role.",
            minimum_qualifications="Testing, transaction safety, and evidence review.",
            status=JobPosting.Status.OPEN,
            published_at=now,
        )
        created_questions = tuple(
            InterviewQuestion.objects.create(
                job=job,
                question_text=text,
                question_type=InterviewQuestion.QuestionType.TECHNICAL,
                order=index,
                scoring_guidance="Require concrete, reviewable synthetic evidence.",
            )
            for index, text in enumerate(questions, start=1)
        )
        rubric = EvaluationRubric.objects.create(
            job=job,
            name=f"{label} Advisory Rubric",
            version=1,
            passing_score=Decimal("60"),
            is_active=True,
        )
        criteria = (
            EvaluationCriterion.objects.create(
                rubric=rubric,
                name="Technical evidence",
                description="Assess concrete testing and transaction-safety evidence.",
                order=1,
                weight=Decimal("0.600"),
                scoring_guidance="Evidence must remain advisory and reviewable.",
            ),
            EvaluationCriterion.objects.create(
                rubric=rubric,
                name="Communication",
                description="Assess clear escalation and communication evidence.",
                order=2,
                weight=Decimal("0.400"),
                scoring_guidance="An authorized human controls any final decision.",
            ),
        )
        candidate_user = User.objects.create_user(
            email=f"{email_stem}_candidate@example.invalid",
            password=None,
            role=User.Role.CANDIDATE,
            email_verified=True,
        )
        candidate = CandidateProfile.objects.get(user=candidate_user)
        candidate.professional_summary = "Synthetic QA fixture; no real candidate data."
        candidate.profile_completed = True
        candidate.save(update_fields=("professional_summary", "profile_completed", "updated_at"))
        application = JobApplication.objects.create(
            job=job,
            candidate=candidate,
            status=JobApplication.Status.INVITED,
            cover_note="Synthetic QA fixture.",
        )
        grant_general_ai_processing_consent(
            candidate=candidate,
            actor=candidate_user,
            policy_version=policy,
            idempotency_key=uuid.uuid4(),
        )
        grant_application_ai_interview_consent(
            application=application,
            actor=candidate_user,
            policy_version=policy,
            idempotency_key=uuid.uuid4(),
        )
        schedule = InterviewSchedule.objects.create(
            application=application,
            scheduled_by=recruiter_user,
            scheduled_start=now - timezone.timedelta(minutes=5),
            scheduled_end=now + timezone.timedelta(hours=1),
            status=InterviewSchedule.Status.CONFIRMED,
            confirmed_at=now - timezone.timedelta(minutes=10),
            invitation_expires_at=now + timezone.timedelta(minutes=30),
            candidate_instructions="Synthetic isolated QA session.",
        )
        session = prepare_simulated_call_session(
            schedule=schedule,
            actor=candidate_user,
            idempotency_key=uuid.uuid4(),
            policy_version=policy,
        )
    return QaInterviewFixture(
        label=label,
        company=company,
        recruiter_user=recruiter_user,
        candidate_user=candidate_user,
        candidate=candidate,
        application=application,
        schedule=schedule,
        session=session,
        questions=created_questions,
        rubric=rubric,
        criteria=criteria,
    )


def _run_speech_worker() -> list[tuple[str, int]]:
    try:
        return run_speech_worker(
            project_root=settings.PROJECT_ROOT,
            piper_model=settings.PIPER_MODEL_PATH,
            whisper_model=settings.WHISPER_MODEL_PATH,
            whisper_device=str(settings.WHISPER_DEVICE),
            whisper_compute_type=str(settings.WHISPER_COMPUTE_TYPE),
            whisper_language=str(settings.WHISPER_LANGUAGE),
        )
    except QaSpeechClientError as error:
        raise QaReleaseError(str(error)) from error


def _real_rag(fixture: QaInterviewFixture) -> SharedRagService:
    rag = SharedRagService(LocalMiniLMEmbedder())
    company_id = str(fixture.company.pk)
    rag.reindex(
        [
            RagDocument(
                source_id=f"{fixture.label}_JOB",
                domain="job",
                version="1",
                text=(
                    "The synthetic QA role requires Django testing, PostgreSQL "
                    "transaction safety, and reviewable evidence."
                ),
                company_id=company_id,
            ),
            RagDocument(
                source_id=f"{fixture.label}_POLICY",
                domain="policy",
                version="1",
                text=(
                    "Interview evidence remains advisory, persistent audio recording "
                    "is disabled, and an authorized human controls employment decisions."
                ),
                company_id=company_id,
            ),
            RagDocument(
                source_id=f"{fixture.label}_RUBRIC",
                domain="rubric",
                version="1",
                text=(
                    "The advisory rubric requires concrete technical evidence, clear "
                    "communication, and an authorized human review before any outcome."
                ),
                company_id=company_id,
            ),
        ]
    )
    return rag


def run_qa_release_interview(*, label: str) -> dict[str, object]:
    database_name, database_role = verify_qa_write_boundary()
    voice_results = get_preflight_speech_results() or _run_speech_worker()
    runtime = get_preflight_runtime() or LlamaCppServerRuntime()
    fixture: QaInterviewFixture | None = None
    turn_evidence: list[dict[str, object]] = []
    try:
        # Preflight Qwen before creating any database fixture. The speech child has
        # exited, so its native allocations cannot overlap the llama.cpp process.
        try:
            runtime.start(timeout_seconds=45)
        except LocalLlmError as error:
            raise QaReleaseError(str(error)) from error
        fixture = _create_fixture(label=label, questions=_QUESTIONS)
        rag = _real_rag(fixture)
        coordinator = DeterministicInterviewCoordinator(DjangoInterviewCoordinatorTools())
        principal = RetrievalPrincipal(
            user_id=str(fixture.candidate_user.pk),
            role=User.Role.CANDIDATE,
            company_id=str(fixture.company.pk),
            candidate_id=str(fixture.candidate.pk),
            ai_processing_consented=True,
        )
        started = coordinator.execute(
            CoordinatorCommand(
                action=CoordinatorAction.START,
                session_id=fixture.session.pk,
                actor=fixture.candidate_user,
            )
        )
        if started.directive is not CoordinatorDirective.ASK_QUESTION:
            raise QaReleaseError("qa_session_start_rejected")
        gateway = DetachedAgentGateway(
            runner=BoundedAgentRunner(runtime, timeout_seconds=20),
            rag=rag,
        )
        for index, (question, voice_result) in enumerate(
            zip(fixture.questions, voice_results, strict=True), start=1
        ):
            transcript_text, vad_segments = voice_result
            decision = gateway.propose(
                AgentRequest(
                    agent_name=AgentName.INTERVIEW,
                    principal=principal,
                    context={
                        "session_status": CallSession.Status.ACTIVE,
                        "approved_question": question.question_text,
                        "response": transcript_text,
                    },
                    retrieval_query=question.question_text,
                )
            )
            if (
                decision.proposal.fallback_code is not None
                or decision.proposal.action != "continue"
                or decision.injection_source_ids
                or not decision.source_ids
            ):
                raise QaReleaseError(
                    f"qa_model_action_rejected_{decision.proposal.action}"
                )
            answer_key = uuid.uuid4()
            result = coordinator.execute(
                CoordinatorCommand(
                    action=CoordinatorAction.SUBMIT_ANSWER,
                    session_id=fixture.session.pk,
                    actor=fixture.candidate_user,
                    answer_text=transcript_text,
                    idempotency_key=answer_key,
                )
            )
            expected = (
                CoordinatorDirective.TERMINAL
                if index == len(fixture.questions)
                else CoordinatorDirective.ASK_QUESTION
            )
            if result.directive is not expected:
                raise QaReleaseError("qa_persistence_rejected")
            response = SimulatedInterviewResponse.objects.get(idempotency_key=answer_key)
            turn_evidence.append(
                {
                    "question_index": index,
                    "response_id": str(response.pk),
                    "proposal_action": decision.proposal.action,
                    "rag_source_ids": list(decision.source_ids),
                    "vad_segments": vad_segments,
                    "transcript_characters": len(transcript_text),
                }
            )

        evaluation_decision = gateway.propose(
            AgentRequest(
                agent_name=AgentName.EVALUATION,
                principal=principal,
                context={
                    "evidence_available": True,
                    "criterion_count": len(fixture.criteria),
                },
                retrieval_query="technical evidence communication human review rubric",
            )
        )
        if (
            evaluation_decision.proposal.fallback_code is not None
            or evaluation_decision.proposal.action != "recommend_human_review"
            or not evaluation_decision.source_ids
        ):
            raise QaReleaseError("qa_advisory_evaluation_rejected")
        evaluation = start_human_evaluation(
            application=fixture.application,
            actor=fixture.recruiter_user,
            source_session=fixture.session,
        )
        evaluation = save_human_evaluation(
            evaluation=evaluation,
            actor=fixture.recruiter_user,
            criterion_reviews=(
                CriterionReview(
                    criterion_id=fixture.criteria[0].pk,
                    score="78",
                    confidence="0.800",
                    evidence="Three synthetic QA answers supplied reviewable technical evidence.",
                ),
                CriterionReview(
                    criterion_id=fixture.criteria[1].pk,
                    score="74",
                    confidence="0.750",
                    evidence="The synthetic critical-issue response described escalation.",
                ),
            ),
            summary="Synthetic QA advisory evaluation; human finalization remains required.",
        )
    except Exception:
        if fixture is not None:
            fixture.session.refresh_from_db()
            if fixture.session.status in {
                CallSession.Status.PENDING,
                CallSession.Status.READY,
                CallSession.Status.ACTIVE,
                CallSession.Status.PAUSED,
            }:
                try:
                    record_technical_failure(
                        session=fixture.session,
                        failure_code="qa_release_runtime_failure",
                        idempotency_key=uuid.uuid4(),
                    )
                except Exception as cleanup_error:
                    raise QaReleaseError("qa_failure_state_cleanup_failed") from cleanup_error
        raise
    finally:
        runtime.stop()
    if fixture is None:
        raise QaReleaseError("qa_fixture_unavailable")
    fixture.session.refresh_from_db()
    response_count = SimulatedInterviewResponse.objects.filter(
        call_session=fixture.session
    ).count()
    transcript_segment_count = TranscriptSegment.objects.filter(
        call_session=fixture.session
    ).count()
    answer_audit_count = AuditEvent.objects.filter(
        event_type="call_session.answer_submitted",
        resource_id=str(fixture.session.pk),
    ).count()
    completion_audit_count = AuditEvent.objects.filter(
        event_type="call_session.completed",
        resource_id=str(fixture.session.pk),
    ).count()
    evaluation_audit_count = AuditEvent.objects.filter(
        event_type__in=("evaluation.started", "evaluation.scored"),
        resource_id=str(evaluation.pk),
    ).count()
    if (
        fixture.session.status != CallSession.Status.COMPLETED
        or response_count != len(fixture.questions)
        or transcript_segment_count != 0
        or fixture.session.recording_enabled
        or bool(fixture.session.recording_file)
        or answer_audit_count != len(fixture.questions)
        or completion_audit_count != 1
        or evaluation_audit_count != 2
        or evaluation.is_final
    ):
        raise QaReleaseError("qa_release_evidence_invalid")
    return {
        "label": fixture.label,
        "database": database_name,
        "role": database_role,
        "settings": settings.SETTINGS_MODULE,
        "company_id": str(fixture.company.pk),
        "candidate_email": fixture.candidate_user.email,
        "application_id": str(fixture.application.pk),
        "session_id": str(fixture.session.pk),
        "session_status": fixture.session.status,
        "persisted_response_count": response_count,
        "persistent_audio_recording": False,
        "transcript_segment_count": transcript_segment_count,
        "answer_audit_count": answer_audit_count,
        "completion_audit_count": completion_audit_count,
        "evaluation_id": str(evaluation.pk),
        "evaluation_status": evaluation.status,
        "advisory_recommendation": evaluation.recommendation,
        "human_finalization_recorded": evaluation.is_final,
        "evaluation_audit_count": evaluation_audit_count,
        "evaluation_model_action": evaluation_decision.proposal.action,
        "evaluation_rag_source_ids": list(evaluation_decision.source_ids),
        "qwen_load_ms": runtime.load_ms,
        "qwen_last_generation_ms": runtime.last_generation_ms,
        "qwen_peak_working_set_bytes": runtime.last_peak_working_set_bytes,
        "turns": turn_evidence,
    }


def prepare_manual_browser_fixture(*, label: str) -> dict[str, object]:
    verify_qa_write_boundary()
    fixture = _create_fixture(label=label, questions=(_QUESTIONS[0],))
    coordinator = DeterministicInterviewCoordinator(DjangoInterviewCoordinatorTools())
    result = coordinator.execute(
        CoordinatorCommand(
            action=CoordinatorAction.START,
            session_id=fixture.session.pk,
            actor=fixture.candidate_user,
        )
    )
    if result.directive is not CoordinatorDirective.ASK_QUESTION:
        raise QaReleaseError("qa_manual_session_start_rejected")
    return {
        "label": fixture.label,
        "candidate_email": fixture.candidate_user.email,
        "session_id": str(fixture.session.pk),
        "session_path": f"/calling/sessions/{fixture.session.pk}/",
        "password_usable": fixture.candidate_user.has_usable_password(),
    }

from ai_system.interview.coordinator import CoordinatorSnapshot, CoordinatorToolError
from django.conf import settings

from calling.models import CallSession
from calling.services import (
    CallSessionServiceError,
    get_candidate_call_session,
    get_candidate_simulated_interview_state,
    submit_simulated_answer,
    transition_call_session,
)


class DjangoInterviewCoordinatorTools:
    """Narrow Django adapter for deterministic interview coordinator actions."""

    def _session(self, *, session_id, actor):
        try:
            return get_candidate_call_session(session_id=session_id, actor=actor)
        except CallSessionServiceError as error:
            raise CoordinatorToolError("Coordinator action was rejected.") from error

    def snapshot(self, *, session_id, actor):
        session = self._session(session_id=session_id, actor=actor)
        try:
            state = get_candidate_simulated_interview_state(
                session=session,
                actor=actor,
            )
        except CallSessionServiceError as error:
            raise CoordinatorToolError("Coordinator action was rejected.") from error
        question = state.current_question
        return CoordinatorSnapshot(
            session_id=state.session.pk,
            status=state.session.status,
            current_question_id=question.pk if question is not None else None,
            current_question_text=(
                question.question_text if question is not None else None
            ),
            answered_questions=state.answered_questions,
            total_questions=state.total_questions,
        )

    def start(self, *, session_id, actor):
        self._transition(
            session_id=session_id,
            actor=actor,
            target_status=CallSession.Status.ACTIVE,
        )

    def pause(self, *, session_id, actor):
        self._transition(
            session_id=session_id,
            actor=actor,
            target_status=CallSession.Status.PAUSED,
        )

    def cancel(self, *, session_id, actor):
        self._transition(
            session_id=session_id,
            actor=actor,
            target_status=CallSession.Status.CANCELLED,
            reason_code="candidate_cancelled",
        )

    def _transition(self, *, session_id, actor, target_status, reason_code=None):
        session = self._session(session_id=session_id, actor=actor)
        try:
            transition_call_session(
                session=session,
                target_status=target_status,
                actor=actor,
                reason_code=reason_code,
                policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
            )
        except CallSessionServiceError as error:
            raise CoordinatorToolError("Coordinator action was rejected.") from error

    def submit_answer(
        self,
        *,
        session_id,
        actor,
        answer_text,
        idempotency_key,
    ):
        session = self._session(session_id=session_id, actor=actor)
        try:
            submit_simulated_answer(
                session=session,
                actor=actor,
                answer_text=answer_text,
                idempotency_key=idempotency_key,
                policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
            )
        except CallSessionServiceError as error:
            raise CoordinatorToolError("Coordinator action was rejected.") from error

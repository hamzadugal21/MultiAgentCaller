import uuid
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

COORDINATOR_POLICY_VERSION = "deterministic-interview-v1"


class CoordinatorAction(StrEnum):
    STATUS = "status"
    START = "start"
    PAUSE = "pause"
    CANCEL = "cancel"
    SUBMIT_ANSWER = "submit_answer"
    REQUEST_HUMAN = "request_human"


class CoordinatorDirective(StrEnum):
    START_REQUIRED = "start_required"
    ASK_QUESTION = "ask_question"
    PAUSED = "paused"
    TERMINAL = "terminal"
    STOPPED = "stopped"
    ESCALATED = "escalated"


ALLOWED_COORDINATOR_ACTIONS = frozenset(CoordinatorAction)
TERMINAL_SESSION_STATUSES = frozenset(
    {"completed", "cancelled", "expired", "failed"}
)


class CoordinatorToolError(Exception):
    """Safe error raised by a narrow coordinator tool adapter."""


@dataclass(frozen=True, slots=True)
class CoordinatorCommand:
    action: CoordinatorAction | str
    session_id: uuid.UUID
    actor: object
    answer_text: str | None = None
    idempotency_key: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class CoordinatorSnapshot:
    session_id: uuid.UUID
    status: str
    current_question_id: uuid.UUID | None
    current_question_text: str | None
    answered_questions: int
    total_questions: int


@dataclass(frozen=True, slots=True)
class CoordinatorResult:
    policy_version: str
    directive: CoordinatorDirective
    snapshot: CoordinatorSnapshot | None
    error_code: str | None = None


class InterviewCoordinatorTools(Protocol):
    def snapshot(self, *, session_id, actor) -> CoordinatorSnapshot: ...

    def start(self, *, session_id, actor) -> None: ...

    def pause(self, *, session_id, actor) -> None: ...

    def cancel(self, *, session_id, actor) -> None: ...

    def submit_answer(
        self,
        *,
        session_id,
        actor,
        answer_text,
        idempotency_key,
    ) -> None: ...

    def request_human(
        self,
        *,
        session_id,
        actor,
        idempotency_key,
    ) -> None: ...


DIRECTIVES_BY_STATUS = MappingProxyType(
    {
        "pending": CoordinatorDirective.STOPPED,
        "ready": CoordinatorDirective.START_REQUIRED,
        "active": CoordinatorDirective.ASK_QUESTION,
        "paused": CoordinatorDirective.PAUSED,
        "completed": CoordinatorDirective.TERMINAL,
        "cancelled": CoordinatorDirective.TERMINAL,
        "expired": CoordinatorDirective.TERMINAL,
        "failed": CoordinatorDirective.TERMINAL,
    }
)


class DeterministicInterviewCoordinator:
    def __init__(self, tools: InterviewCoordinatorTools):
        self._tools = tools

    def execute(self, command):
        try:
            action = CoordinatorAction(command.action)
        except (AttributeError, TypeError, ValueError):
            return self._stopped("unsupported_action")
        if action not in ALLOWED_COORDINATOR_ACTIONS:
            return self._stopped("unsupported_action")
        try:
            if action == CoordinatorAction.START:
                self._tools.start(
                    session_id=command.session_id,
                    actor=command.actor,
                )
            elif action == CoordinatorAction.PAUSE:
                self._tools.pause(
                    session_id=command.session_id,
                    actor=command.actor,
                )
            elif action == CoordinatorAction.CANCEL:
                self._tools.cancel(
                    session_id=command.session_id,
                    actor=command.actor,
                )
            elif action == CoordinatorAction.SUBMIT_ANSWER:
                if command.answer_text is None or command.idempotency_key is None:
                    return self._stopped("invalid_command")
                self._tools.submit_answer(
                    session_id=command.session_id,
                    actor=command.actor,
                    answer_text=command.answer_text,
                    idempotency_key=command.idempotency_key,
                )
            elif action == CoordinatorAction.REQUEST_HUMAN:
                if command.idempotency_key is None:
                    return self._stopped("invalid_command")
                self._tools.request_human(
                    session_id=command.session_id,
                    actor=command.actor,
                    idempotency_key=command.idempotency_key,
                )
            snapshot = self._tools.snapshot(
                session_id=command.session_id,
                actor=command.actor,
            )
        except CoordinatorToolError:
            return self._stopped("action_rejected")
        directive = DIRECTIVES_BY_STATUS.get(
            snapshot.status,
            CoordinatorDirective.STOPPED,
        )
        if action == CoordinatorAction.REQUEST_HUMAN:
            directive = CoordinatorDirective.ESCALATED
        if directive == CoordinatorDirective.ASK_QUESTION and (
            snapshot.current_question_id is None
            or snapshot.current_question_text is None
        ):
            return CoordinatorResult(
                policy_version=COORDINATOR_POLICY_VERSION,
                directive=CoordinatorDirective.STOPPED,
                snapshot=snapshot,
                error_code="question_unavailable",
            )
        return CoordinatorResult(
            policy_version=COORDINATOR_POLICY_VERSION,
            directive=directive,
            snapshot=snapshot,
        )

    @staticmethod
    def _stopped(error_code):
        return CoordinatorResult(
            policy_version=COORDINATOR_POLICY_VERSION,
            directive=CoordinatorDirective.STOPPED,
            snapshot=None,
            error_code=error_code,
        )

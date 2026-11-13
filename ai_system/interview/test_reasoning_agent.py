import uuid

from ai_system.interview.coordinator import (
    CoordinatorSnapshot,
    DeterministicInterviewCoordinator,
)
from ai_system.interview.reasoning_agent import (
    InterviewReasoningAgent,
    InterviewReasoningContext,
    ModelDrivenInterviewCoordinator,
    ReasoningAction,
)


class StaticRuntime:
    def __init__(self, output):
        self.output = output
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.output, 7


def _context(answer="I used tests and peer review to validate the release."):
    return InterviewReasoningContext(
        session_status="active",
        question_text="How did you validate the release?",
        candidate_answer=answer,
        answered_questions=1,
        total_questions=3,
    )


def _output(action="continue"):
    return '{"action":"%s"}' % action


def test_reasoning_agent_validates_model_schema_and_never_executes_a_tool():
    runtime = StaticRuntime(_output("ask_follow_up"))

    outcome = InterviewReasoningAgent(runtime).decide(_context())

    assert outcome.proposal.action is ReasoningAction.ASK_FOLLOW_UP
    assert outcome.permitted_action == "display_candidate_message"
    assert outcome.model_latency_ms == 7
    assert "I used tests and peer review" in runtime.prompts[0]


def test_reasoning_agent_rejects_invalid_json_and_hallucinated_actions_safely():
    invalid = InterviewReasoningAgent(StaticRuntime("not json")).decide(_context())
    hallucinated = InterviewReasoningAgent(StaticRuntime(_output("hire_candidate"))).decide(
        _context()
    )

    assert invalid.fallback_code == "reasoning_output_invalid"
    assert hallucinated.fallback_code == "reasoning_output_invalid"
    assert invalid.permitted_action == hallucinated.permitted_action == "none"


def test_reasoning_agent_human_review_is_only_a_recommendation():
    outcome = InterviewReasoningAgent(
        StaticRuntime(_output("recommend_human_review"))
    ).decide(_context("I want a human interviewer now."))

    assert outcome.proposal.requires_human_review is True
    assert outcome.permitted_action == "recommend_human_review"
    assert outcome.proposal.action is ReasoningAction.RECOMMEND_HUMAN_REVIEW


def test_model_cannot_inject_arbitrary_message_or_extra_fields():
    outcome = InterviewReasoningAgent(
        StaticRuntime('{"action":"continue","message":"private text"}')
    ).decide(_context())

    assert outcome.fallback_code == "reasoning_output_invalid"
    assert outcome.permitted_action == "none"


class SnapshotOnlyTools:
    def __init__(self, snapshot):
        self.snapshot_value = snapshot
        self.calls = []

    def snapshot(self, **kwargs):
        self.calls.append("snapshot")
        return self.snapshot_value

    def start(self, **kwargs):
        self.calls.append("start")

    def pause(self, **kwargs):
        self.calls.append("pause")

    def cancel(self, **kwargs):
        self.calls.append("cancel")

    def submit_answer(self, **kwargs):
        self.calls.append("submit_answer")

    def request_human(self, **kwargs):
        self.calls.append("request_human")


def test_model_driven_bridge_executes_only_authorized_read_only_status_tool():
    tools = SnapshotOnlyTools(
        CoordinatorSnapshot(
            session_id=uuid.uuid4(),
            status="active",
            current_question_id=uuid.uuid4(),
            current_question_text="Explain your testing approach.",
            answered_questions=0,
            total_questions=2,
        )
    )
    bridge = ModelDrivenInterviewCoordinator(
        coordinator=DeterministicInterviewCoordinator(tools),
        reasoning_agent=InterviewReasoningAgent(StaticRuntime(_output("continue"))),
    )

    outcome = bridge.advise(
        session_id=tools.snapshot_value.session_id,
        actor=object(),
        candidate_answer="I used focused tests and review.",
    )

    assert outcome.proposal.action is ReasoningAction.CONTINUE
    assert outcome.permitted_action == "none"
    assert tools.calls == ["snapshot"]


def test_model_driven_bridge_stops_without_model_call_for_non_active_session():
    tools = SnapshotOnlyTools(
        CoordinatorSnapshot(
            session_id=uuid.uuid4(),
            status="paused",
            current_question_id=None,
            current_question_text=None,
            answered_questions=0,
            total_questions=2,
        )
    )
    runtime = StaticRuntime(_output("continue"))
    bridge = ModelDrivenInterviewCoordinator(
        coordinator=DeterministicInterviewCoordinator(tools),
        reasoning_agent=InterviewReasoningAgent(runtime),
    )

    outcome = bridge.advise(
        session_id=tools.snapshot_value.session_id,
        actor=object(),
        candidate_answer="Any answer.",
    )

    assert outcome.fallback_code == "session_not_ready_for_reasoning"
    assert runtime.prompts == []

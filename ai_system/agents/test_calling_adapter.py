import uuid

from ai_system.agents.calling_adapter import ProposalAwareCoordinator
from ai_system.agents.gateway import DetachedAgentGateway
from ai_system.framework.agents import BoundedAgentRunner
from ai_system.interview.coordinator import CoordinatorAction, CoordinatorCommand
from ai_system.rag.service import RetrievalPrincipal


class Runtime:
    def generate_decision(self, **_kwargs):
        return {
            "action": "recommend_human_review",
            "message": "Synthetic proposal.",
            "requires_human_review": True,
        }


class Coordinator:
    def __init__(self):
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        return "deterministic-result"


def test_model_advice_cannot_replace_deterministic_call_execution():
    coordinator = Coordinator()
    adapter = ProposalAwareCoordinator(
        coordinator=coordinator,
        gateway=DetachedAgentGateway(runner=BoundedAgentRunner(Runtime())),
    )
    command = CoordinatorCommand(
        action=CoordinatorAction.STATUS,
        session_id=uuid.uuid4(),
        actor=object(),
    )

    assert adapter.execute(command) == "deterministic-result"
    advice = adapter.propose_routing(
        principal=RetrievalPrincipal("candidate-a", "candidate", candidate_id="candidate-a"),
        session_status="active",
        candidate_requested_human=True,
    )

    assert coordinator.commands == [command]
    assert advice.proposal.action == "recommend_human_review"
    assert advice.execution_enabled is False

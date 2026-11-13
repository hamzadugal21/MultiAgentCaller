"""Read-only model advice around the authoritative deterministic coordinator."""

from __future__ import annotations

from ai_system.agents.gateway import AgentDecision, AgentRequest, DetachedAgentGateway
from ai_system.framework.agents import AgentName
from ai_system.interview.coordinator import (
    CoordinatorCommand,
    DeterministicInterviewCoordinator,
)
from ai_system.rag.service import RetrievalPrincipal


class ProposalAwareCoordinator:
    """Keep lifecycle execution deterministic; expose optional detached advice only."""

    def __init__(self, *, coordinator: DeterministicInterviewCoordinator, gateway: DetachedAgentGateway):
        self._coordinator = coordinator
        self._gateway = gateway

    def execute(self, command: CoordinatorCommand):
        """Delegate every transition to the pre-existing deterministic coordinator."""
        return self._coordinator.execute(command)

    def propose_routing(
        self,
        *,
        principal: RetrievalPrincipal,
        session_status: str,
        candidate_requested_human: bool = False,
    ) -> AgentDecision:
        """Return advisory routing only; it cannot pause, resume, or mutate a session."""
        return self._gateway.propose(
            AgentRequest(
                agent_name=AgentName.ORCHESTRATOR,
                principal=principal,
                context={
                    "session_status": session_status,
                    "candidate_requested_human": candidate_requested_human,
                },
            )
        )

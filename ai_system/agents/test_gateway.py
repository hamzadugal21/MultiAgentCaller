import pytest

from ai_system.agents.gateway import (
    AgentGatewayError,
    AgentRequest,
    DetachedAgentGateway,
)
from ai_system.framework.agents import AgentName, BoundedAgentRunner
from ai_system.rag.service import RetrievalPrincipal


class Runtime:
    def generate_decision(self, **kwargs):
        action = sorted(kwargs["allowed_actions"])[0]
        return {
            "action": action,
            "message": "Synthetic detached proposal.",
            "requires_human_review": False,
        }


class Result:
    source_id = "safe-source"
    domain = "job"
    text = "Approved synthetic source."
    injection_warning = False


class Rag:
    def __init__(self):
        self.principal = None

    def retrieve(self, *, query, principal, limit=4):
        self.principal = principal
        return [Result()]


def _principal():
    return RetrievalPrincipal("candidate-a", "candidate", candidate_id="candidate-a", ai_processing_consented=True)


@pytest.mark.parametrize(
    ("agent_name", "context"),
    [
        (AgentName.ORCHESTRATOR, {"session_status": "active"}),
        (AgentName.PROFILE, {"missing_fields": []}),
        (AgentName.INTERVIEW, {"session_status": "active", "approved_question": "Synthetic?", "response": "Synthetic."}),
        (AgentName.FAQ, {"question": "Synthetic?"}),
        (AgentName.SCHEDULING, {"authorized_slots": []}),
        (AgentName.EVALUATION, {"evidence_available": False}),
        (AgentName.SAFETY, {"response": "Synthetic."}),
        (AgentName.ESCALATION, {"reason_code": "candidate_requested_human"}),
        (AgentName.AUDIT, {"event_type": "synthetic"}),
    ],
)
def test_every_logical_agent_has_a_typed_detached_request(agent_name, context):
    decision = DetachedAgentGateway(runner=BoundedAgentRunner(Runtime())).propose(
        AgentRequest(agent_name, _principal(), context)
    )

    assert decision.agent_name == agent_name
    assert decision.execution_enabled is False
    assert decision.proposal.action


def test_rag_uses_the_authorized_principal_and_safe_audit_summary():
    rag = Rag()
    decision = DetachedAgentGateway(runner=BoundedAgentRunner(Runtime()), rag=rag).propose(
        AgentRequest(AgentName.FAQ, _principal(), {"question": "Synthetic?"}, "synthetic")
    )
    summary = DetachedAgentGateway.audit_summary(decision)

    assert rag.principal.candidate_id == "candidate-a"
    assert decision.source_ids == ("safe-source",)
    assert summary.source_count == 1
    assert not hasattr(summary, "text")


def test_gateway_rejects_missing_context_and_refuses_execution():
    gateway = DetachedAgentGateway(runner=BoundedAgentRunner(Runtime()))
    with pytest.raises(AgentGatewayError, match="context_incomplete"):
        gateway.propose(AgentRequest(AgentName.INTERVIEW, _principal(), {"response": "x"}))
    with pytest.raises(AgentGatewayError, match="agent_execution_disabled"):
        gateway.execute()


def test_rag_unavailable_and_handoff_cycle_fail_closed():
    gateway = DetachedAgentGateway(runner=BoundedAgentRunner(Runtime()))
    with pytest.raises(AgentGatewayError, match="rag_unavailable"):
        gateway.propose(AgentRequest(AgentName.FAQ, _principal(), {"question": "x"}, "x"))
    result = gateway.propose(
        AgentRequest(
            AgentName.INTERVIEW,
            _principal(),
            {"session_status": "active", "approved_question": "x", "response": "x"},
            handoff_path=(AgentName.INTERVIEW,),
        )
    )
    assert result.proposal.fallback_code == "handoff_cycle_rejected"

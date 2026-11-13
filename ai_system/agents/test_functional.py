import pytest

from ai_system.agents.functional import FunctionalAgentError, project
from ai_system.agents.gateway import AgentDecision
from ai_system.framework.agents import AgentName, AgentProposal


def _decision(agent, action, sources=(), review=False):
    return AgentDecision(
        agent_name=agent,
        proposal=AgentProposal(action, "Synthetic bounded message.", requires_human_review=review),
        source_ids=sources,
        injection_source_ids=(),
    )


@pytest.mark.parametrize(
    ("agent", "action", "context", "sources"),
    [
        (AgentName.ORCHESTRATOR, "continue", {"session_status": "active"}, ()),
        (AgentName.PROFILE, "request_profile_completion", {"skills": ["Python"], "experience_summary": "API work"}, ()),
        (AgentName.INTERVIEW, "ask_follow_up", {"response": "brief"}, ("job-1",)),
        (AgentName.FAQ, "answer_from_sources", {"question": "x"}, ("faq-1",)),
        (AgentName.SCHEDULING, "present_authorized_options", {"authorized_slots": ["slot-1"]}, ()),
        (AgentName.EVALUATION, "insufficient_evidence", {"evidence_available": False}, ("rubric-1",)),
        (AgentName.SAFETY, "recommend_human_review", {"response": "unsafe"}, ()),
        (AgentName.ESCALATION, "recommend_human_review", {"reason_code": "candidate_requested_human"}, ()),
        (AgentName.AUDIT, "stop", {"event_type": "agent.proposal"}, ()),
    ],
)
def test_each_agent_has_a_safe_functional_projection(agent, action, context, sources):
    output = project(decision=_decision(agent, action, sources), context=context)

    assert output.agent_name is agent
    assert output.action == action
    assert "Synthetic" in output.content or agent is AgentName.AUDIT


def test_profile_projection_does_not_invent_undeclared_evidence():
    output = project(
        decision=_decision(AgentName.PROFILE, "request_profile_completion"),
        context={"skills": ["Python"], "experience_summary": ""},
    )

    assert "Python" in output.content
    assert "Django" not in output.content


@pytest.mark.parametrize(
    ("agent", "action", "context", "sources", "code"),
    [
        (AgentName.FAQ, "answer_from_sources", {"question": "x"}, (), "source_evidence_required"),
        (AgentName.SCHEDULING, "present_authorized_options", {"authorized_slots": []}, (), "authorized_slots_required"),
        (AgentName.AUDIT, "record_required_event", {"event_type": "x"}, (), "deterministic_audit_required"),
    ],
)
def test_unsafe_functional_projection_is_rejected(agent, action, context, sources, code):
    with pytest.raises(FunctionalAgentError, match=code):
        project(decision=_decision(agent, action, sources), context=context)

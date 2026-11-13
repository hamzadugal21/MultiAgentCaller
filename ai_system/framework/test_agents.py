from ai_system.framework.agents import (
    AGENT_REGISTRY,
    AgentContext,
    AgentName,
    BoundedAgentRunner,
)


class StaticRuntime:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate_decision(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def test_nine_logical_agents_have_immutable_narrow_registry_entries():
    assert len(AGENT_REGISTRY) == 9
    assert AGENT_REGISTRY[AgentName.AUDIT].model_enabled is False
    assert "audit.record_event" in AGENT_REGISTRY[AgentName.AUDIT].allowed_tools
    assert "sql" not in AGENT_REGISTRY[AgentName.INTERVIEW].allowed_tools


def test_valid_model_proposal_is_limited_to_registered_action_and_never_executes_tool():
    runtime = StaticRuntime(
        {
            "action": "ask_follow_up",
            "message": "Could you provide a concrete example?",
            "requires_human_review": False,
        }
    )
    proposal = BoundedAgentRunner(runtime).propose(
        AgentName.INTERVIEW,
        AgentContext("candidate-1", "candidate", {"answer": "synthetic"}),
    )

    assert proposal.action == "ask_follow_up"
    assert proposal.fallback_code is None
    assert len(runtime.calls) == 1
    assert runtime.calls[0]["allowed_actions"] == AGENT_REGISTRY[AgentName.INTERVIEW].allowed_actions


def test_runner_can_narrow_but_never_expand_registered_actions():
    runtime = StaticRuntime(
        {"action": "answer_from_sources", "message": "Grounded answer.", "requires_human_review": False}
    )
    runner = BoundedAgentRunner(runtime)
    proposal = runner.propose(
        AgentName.FAQ,
        AgentContext("candidate-1", "candidate", {"question": "synthetic"}),
        allowed_actions=frozenset({"answer_from_sources", "recommend_human_review"}),
    )
    expanded = runner.propose(
        AgentName.FAQ,
        AgentContext("candidate-1", "candidate", {"question": "synthetic"}),
        allowed_actions=frozenset({"answer_from_sources", "hire_candidate"}),
    )

    assert proposal.action == "answer_from_sources"
    assert runtime.calls[0]["allowed_actions"] == frozenset({"answer_from_sources", "recommend_human_review"})
    assert expanded.fallback_code == "agent_action_scope_invalid"


def test_hallucinated_action_schema_failure_and_handoff_cycle_fail_closed():
    invalid = BoundedAgentRunner(
        StaticRuntime(
            {
                "action": "hire_candidate",
                "message": "No.",
                "requires_human_review": False,
            }
        )
    ).propose(AgentName.EVALUATION, AgentContext("recruiter-1", "recruiter", {}))
    cycle = BoundedAgentRunner(StaticRuntime({})).propose(
        AgentName.FAQ,
        AgentContext("candidate-1", "candidate", {}, handoff_path=(AgentName.FAQ,)),
    )

    assert invalid.fallback_code == "agent_runtime_unavailable"
    assert cycle.fallback_code == "handoff_cycle_rejected"


def test_cancellation_and_audit_policy_do_not_call_the_model():
    runtime = StaticRuntime({})
    runner = BoundedAgentRunner(runtime)

    cancelled = runner.propose(
        AgentName.INTERVIEW,
        AgentContext("candidate-1", "candidate", {}, cancelled=True),
    )
    audit = runner.propose(AgentName.AUDIT, AgentContext("system", "system", {}))

    assert cancelled.fallback_code == "agent_cancelled"
    assert audit.fallback_code == "deterministic_policy_required"
    assert runtime.calls == []

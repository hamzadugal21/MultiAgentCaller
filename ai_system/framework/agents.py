"""Shared model-proposal framework with deterministic authority boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol


class AgentName(StrEnum):
    ORCHESTRATOR = "calling_orchestrator"
    PROFILE = "candidate_profile"
    INTERVIEW = "interview"
    FAQ = "faq"
    SCHEDULING = "scheduling"
    EVALUATION = "evaluation"
    SAFETY = "safety"
    ESCALATION = "escalation"
    AUDIT = "audit"


@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: AgentName
    allowed_actions: frozenset[str]
    allowed_tools: frozenset[str]
    allow_rag: bool
    model_enabled: bool = True
    maximum_calls: int = 1
    maximum_handoffs: int = 1


def _spec(
    name: AgentName,
    actions: set[str],
    tools: set[str],
    *,
    rag: bool = False,
    model_enabled: bool = True,
) -> AgentSpec:
    return AgentSpec(name, frozenset(actions), frozenset(tools), rag, model_enabled)


AGENT_REGISTRY = MappingProxyType(
    {
        AgentName.ORCHESTRATOR: _spec(
            AgentName.ORCHESTRATOR,
            {"continue", "pause", "recommend_human_review"},
            {"calling.get_status"},
        ),
        AgentName.PROFILE: _spec(
            AgentName.PROFILE,
            {"request_profile_completion", "recommend_human_review"},
            {"candidate.get_authorized_profile"},
            rag=True,
        ),
        AgentName.INTERVIEW: _spec(
            AgentName.INTERVIEW,
            {"continue", "ask_follow_up", "clarify", "recommend_human_review", "stop"},
            {"calling.get_status"},
            rag=True,
        ),
        AgentName.FAQ: _spec(
            AgentName.FAQ,
            {"answer_from_sources", "clarify", "recommend_human_review"},
            set(),
            rag=True,
        ),
        AgentName.SCHEDULING: _spec(
            AgentName.SCHEDULING,
            {"present_authorized_options", "recommend_human_review"},
            {"interviews.get_authorized_schedule"},
            rag=True,
        ),
        AgentName.EVALUATION: _spec(
            AgentName.EVALUATION,
            {"recommend_human_review", "insufficient_evidence"},
            {"interviews.get_authorized_evaluation"},
            rag=True,
        ),
        AgentName.SAFETY: _spec(
            AgentName.SAFETY,
            {"recommend_human_review", "stop"},
            set(),
            rag=True,
        ),
        AgentName.ESCALATION: _spec(
            AgentName.ESCALATION,
            {"recommend_human_review"},
            {"agents.get_authorized_escalation"},
        ),
        # Audit decisions remain deterministic by policy; an LLM never controls them.
        AgentName.AUDIT: _spec(
            AgentName.AUDIT,
            {"record_required_event"},
            {"audit.record_event"},
            model_enabled=False,
        ),
    }
)


@dataclass(frozen=True, slots=True)
class AgentContext:
    principal_id: str
    principal_role: str
    payload: dict[str, object]
    handoff_path: tuple[AgentName, ...] = ()
    cancelled: bool = False


@dataclass(frozen=True, slots=True)
class AgentProposal:
    action: str
    message: str
    source_ids: tuple[str, ...] = ()
    requires_human_review: bool = False
    fallback_code: str | None = None


class DecisionRuntime(Protocol):
    def generate_decision(
        self,
        *,
        agent_name: str,
        context: dict[str, object],
        allowed_actions: frozenset[str],
        timeout_seconds: float,
    ) -> dict[str, object]: ...


class BoundedAgentRunner:
    """Validate untrusted model proposals; it deliberately executes no tools."""

    def __init__(self, runtime: DecisionRuntime, *, timeout_seconds: float = 8.0):
        self._runtime = runtime
        self._timeout_seconds = timeout_seconds

    def propose(
        self,
        agent_name: AgentName,
        context: AgentContext,
        *,
        allowed_actions: frozenset[str] | None = None,
    ) -> AgentProposal:
        spec = AGENT_REGISTRY[agent_name]
        actions = allowed_actions or spec.allowed_actions
        if not actions or not actions.issubset(spec.allowed_actions):
            return self._fallback("agent_action_scope_invalid")
        if context.cancelled:
            return self._fallback("agent_cancelled")
        if agent_name in context.handoff_path:
            return self._fallback("handoff_cycle_rejected")
        if len(context.handoff_path) >= spec.maximum_handoffs:
            return self._fallback("handoff_limit_reached")
        if not spec.model_enabled:
            return self._fallback("deterministic_policy_required")
        try:
            raw = self._runtime.generate_decision(
                agent_name=agent_name.value,
                context=context.payload,
                allowed_actions=actions,
                timeout_seconds=self._timeout_seconds,
            )
            proposal = self._validate(raw, spec)
            if proposal.action not in actions:
                return self._fallback("agent_action_scope_invalid")
            return proposal
        except (TypeError, ValueError, RuntimeError, TimeoutError):
            return self._fallback("agent_runtime_unavailable")

    @staticmethod
    def _validate(raw: dict[str, object], spec: AgentSpec) -> AgentProposal:
        if not isinstance(raw, dict) or set(raw) != {
            "action",
            "message",
            "requires_human_review",
        }:
            raise ValueError("agent schema invalid")
        action = raw["action"]
        message = raw["message"]
        review = raw["requires_human_review"]
        if (
            not isinstance(action, str)
            or action not in spec.allowed_actions
            or not isinstance(message, str)
            or not isinstance(review, bool)
        ):
            raise ValueError("agent proposal invalid")
        message = re.sub(r"(?is)<think>.*?</think>", "", message)
        message = re.sub(r"(?is)<analysis>.*?</analysis>", "", message)
        message = re.sub(r"(?is)^(thinking|analysis|reasoning)\s*:\s*.*?(?=(answer|final)\s*:)", "", message)
        message = re.sub(r"(?i)^(answer|final)\s*:\s*", "", message).strip()
        if not 1 <= len(message) <= 280 or re.search(r"(?i)\b(chain of thought|system prompt|developer message)\b", message):
            raise ValueError("agent proposal contains non-user-facing content")
        # No model proposal grants authority. Review can only become an advisory flag.
        return AgentProposal(
            action=action,
            message=" ".join(message.split()),
            requires_human_review=review or action == "recommend_human_review",
        )

    @staticmethod
    def _fallback(code: str) -> AgentProposal:
        return AgentProposal(
            action="stop",
            message="Please continue through the approved workflow.",
            requires_human_review=False,
            fallback_code=code,
        )

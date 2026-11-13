"""Detached functional projections for shared-model agent proposals.

These projections intentionally expose only evidence already supplied by an
authorized caller. They neither query Django nor perform a state transition.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_system.agents.gateway import AgentDecision
from ai_system.framework.agents import AgentName


class FunctionalAgentError(Exception):
    """Safe error for an unsupported functional projection."""


@dataclass(frozen=True, slots=True)
class FunctionalOutput:
    agent_name: AgentName
    action: str
    content: str
    evidence: tuple[str, ...]
    requires_human_review: bool
    fallback_code: str | None


def project(*, decision: AgentDecision, context: dict[str, object]) -> FunctionalOutput:
    """Convert a validated proposal into bounded, domain-specific safe output.

    Evidence is always identifiers, never RAG text, answers, resumes, or prompts.
    """
    if not isinstance(context, dict):
        raise FunctionalAgentError("context_invalid")
    proposal = decision.proposal
    _validate(decision.agent_name, proposal.action, context, decision.source_ids)
    content = proposal.message
    if decision.agent_name is AgentName.PROFILE:
        declared = _declared_profile_evidence(context)
        content = f"{proposal.message} Declared evidence: {declared or 'none'}"
    elif decision.agent_name is AgentName.FAQ and proposal.action == "answer_from_sources":
        content = f"{proposal.message} Source-grounded response available."
    elif decision.agent_name is AgentName.EVALUATION:
        content = f"{proposal.message} Advisory only; authorized human review is required."
    elif decision.agent_name is AgentName.AUDIT:
        content = "Deterministic audit routing is required."
    return FunctionalOutput(
        agent_name=decision.agent_name,
        action=proposal.action,
        content=content[:320],
        evidence=decision.source_ids,
        requires_human_review=proposal.requires_human_review,
        fallback_code=proposal.fallback_code,
    )


def _declared_profile_evidence(context: dict[str, object]) -> str:
    """Never infer skills or experience not explicitly supplied by the caller."""
    pieces: list[str] = []
    for key in ("skills", "experience_summary"):
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            pieces.append(value.strip()[:120])
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            pieces.extend(item.strip()[:60] for item in value if item.strip())
    return "; ".join(pieces[:8])


def _validate(
    agent_name: AgentName,
    action: str,
    context: dict[str, object],
    source_ids: tuple[str, ...],
) -> None:
    if agent_name is AgentName.FAQ and action == "answer_from_sources" and not source_ids:
        raise FunctionalAgentError("source_evidence_required")
    if agent_name is AgentName.SCHEDULING and action == "present_authorized_options":
        if not context.get("authorized_slots"):
            raise FunctionalAgentError("authorized_slots_required")
    if agent_name is AgentName.EVALUATION and action not in {
        "recommend_human_review",
        "insufficient_evidence",
    }:
        raise FunctionalAgentError("evaluation_action_invalid")
    if agent_name is AgentName.AUDIT and action != "stop":
        raise FunctionalAgentError("deterministic_audit_required")

"""Feature-gated proposal gateway for the nine logical agents.

The gateway has no ORM, network, shell, or tool-execution capability. Django
domain services remain the only authority for state changes. It may be used in
detached evaluation to give a shared model only minimum, already-authorized
context and RAG excerpts.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from ai_system.framework.agents import (
    AGENT_REGISTRY,
    AgentContext,
    AgentName,
    AgentProposal,
    BoundedAgentRunner,
)
from ai_system.rag.service import RetrievalPrincipal, RetrievalResult, SharedRagService


class AgentGatewayError(Exception):
    """Safe error for rejected detached agent requests."""


_REQUIRED_CONTEXT = MappingProxyType(
    {
        AgentName.ORCHESTRATOR: frozenset({"session_status"}),
        AgentName.PROFILE: frozenset({"missing_fields"}),
        AgentName.INTERVIEW: frozenset({"session_status", "approved_question", "response"}),
        AgentName.FAQ: frozenset({"question"}),
        AgentName.SCHEDULING: frozenset({"authorized_slots"}),
        AgentName.EVALUATION: frozenset({"evidence_available"}),
        AgentName.SAFETY: frozenset({"response"}),
        AgentName.ESCALATION: frozenset({"reason_code"}),
        AgentName.AUDIT: frozenset({"event_type"}),
    }
)


@dataclass(frozen=True, slots=True)
class AgentRequest:
    agent_name: AgentName
    principal: RetrievalPrincipal
    context: dict[str, object]
    retrieval_query: str | None = None
    handoff_path: tuple[AgentName, ...] = ()
    cancelled: bool = False
    allowed_actions: frozenset[str] | None = None
    retrieval_limit: int = 4


@dataclass(frozen=True, slots=True)
class AgentDecision:
    agent_name: AgentName
    proposal: AgentProposal
    source_ids: tuple[str, ...]
    injection_source_ids: tuple[str, ...]
    execution_enabled: bool = False


@dataclass(frozen=True, slots=True)
class AgentAuditSummary:
    """Safe, non-persistent metadata for a caller-owned registered audit event."""

    agent_name: str
    action: str
    fallback_code: str | None
    source_count: int
    injection_source_count: int


class DetachedAgentGateway:
    """Run bounded proposals only; never execute a Django-domain action."""

    def __init__(self, *, runner: BoundedAgentRunner, rag: SharedRagService | None = None):
        self._runner = runner
        self._rag = rag

    def propose(self, request: AgentRequest) -> AgentDecision:
        self._validate(request)
        sources = self._retrieve(request)
        context = dict(request.context)
        if sources:
            context["approved_sources"] = [
                {"source_id": item.source_id, "domain": item.domain, "text": item.text}
                for item in sources
            ]
        proposal = self._runner.propose(
            request.agent_name,
            AgentContext(
                principal_id=request.principal.user_id,
                principal_role=request.principal.role,
                payload=context,
                handoff_path=request.handoff_path,
                cancelled=request.cancelled,
            ),
            allowed_actions=request.allowed_actions,
        )
        return AgentDecision(
            agent_name=request.agent_name,
            proposal=proposal,
            source_ids=tuple(item.source_id for item in sources),
            injection_source_ids=tuple(
                item.source_id for item in sources if item.injection_warning
            ),
        )

    @staticmethod
    def execute(*_args, **_kwargs) -> None:
        """Refuse execution until a future explicit feature-gate approval."""
        raise AgentGatewayError("agent_execution_disabled")

    @staticmethod
    def audit_summary(decision: AgentDecision) -> AgentAuditSummary:
        """Never include prompts, answers, RAG text, or private identifiers."""
        return AgentAuditSummary(
            agent_name=decision.agent_name.value,
            action=decision.proposal.action,
            fallback_code=decision.proposal.fallback_code,
            source_count=len(decision.source_ids),
            injection_source_count=len(decision.injection_source_ids),
        )

    def _retrieve(self, request: AgentRequest) -> list[RetrievalResult]:
        spec = AGENT_REGISTRY[request.agent_name]
        if not request.retrieval_query or not spec.allow_rag:
            return []
        if self._rag is None:
            raise AgentGatewayError("rag_unavailable")
        return self._rag.retrieve(
            query=request.retrieval_query,
            principal=request.principal,
            limit=request.retrieval_limit,
        )

    @staticmethod
    def _validate(request: AgentRequest) -> None:
        if not isinstance(request.agent_name, AgentName):
            raise AgentGatewayError("agent_invalid")
        if not isinstance(request.context, dict):
            raise AgentGatewayError("context_invalid")
        missing = _REQUIRED_CONTEXT[request.agent_name].difference(request.context)
        if missing:
            raise AgentGatewayError("context_incomplete")
        if not isinstance(request.principal, RetrievalPrincipal):
            raise AgentGatewayError("principal_invalid")
        if request.allowed_actions is not None:
            spec = AGENT_REGISTRY[request.agent_name]
            if not request.allowed_actions or not request.allowed_actions.issubset(spec.allowed_actions):
                raise AgentGatewayError("action_scope_invalid")
        if not isinstance(request.retrieval_limit, int) or not 1 <= request.retrieval_limit <= 8:
            raise AgentGatewayError("retrieval_limit_invalid")

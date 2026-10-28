import uuid
from dataclasses import dataclass
from types import MappingProxyType

from django.db import transaction

from accounts.models import User
from agents.models import AgentEscalation
from auditlog.models import AuditEvent
from auditlog.services import AuditCommand, record_domain_event
from calling.models import CallSession
from calling.services import (
    CallSessionServiceError,
    get_call_session_for_actor,
    transition_call_session,
)


class EscalationServiceError(Exception):
    """Raised when a human escalation cannot be safely recorded."""


@dataclass(frozen=True, slots=True)
class EscalationPolicy:
    category: str
    severity: str
    description: str


ESCALATION_POLICIES = MappingProxyType(
    {
        "candidate_requested_human": EscalationPolicy(
            category=AgentEscalation.Category.CANDIDATE_REQUEST,
            severity=AgentEscalation.Severity.MEDIUM,
            description="The candidate requested authorized human assistance.",
        ),
        "runtime_failure": EscalationPolicy(
            category=AgentEscalation.Category.TECHNICAL,
            severity=AgentEscalation.Severity.HIGH,
            description="The interview runtime requires authorized human review.",
        ),
        "service_unavailable": EscalationPolicy(
            category=AgentEscalation.Category.TECHNICAL,
            severity=AgentEscalation.Severity.MEDIUM,
            description="An optional interview service is unavailable.",
        ),
        "unsafe_state": EscalationPolicy(
            category=AgentEscalation.Category.SAFETY,
            severity=AgentEscalation.Severity.HIGH,
            description="The interview entered a state requiring human review.",
        ),
        "consent_revoked": EscalationPolicy(
            category=AgentEscalation.Category.POLICY,
            severity=AgentEscalation.Severity.MEDIUM,
            description="Current interview consent is no longer available.",
        ),
    }
)


def _required_uuid(value, name):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise EscalationServiceError(f"A valid {name} is required.") from error


def _actor(actor, session, reason_code):
    if actor is None:
        if reason_code == "candidate_requested_human":
            raise EscalationServiceError("An authorized actor is required.")
        return None
    try:
        persisted = User.objects.get(pk=actor.pk, is_active=True)
        get_call_session_for_actor(session=session, actor=persisted)
    except (AttributeError, User.DoesNotExist, CallSessionServiceError) as error:
        raise EscalationServiceError("The actor is not authorized.") from error
    if (
        reason_code == "candidate_requested_human"
        and (
            persisted.role != User.Role.CANDIDATE
            or persisted.pk != session.schedule.application.candidate.user_id
        )
    ):
        raise EscalationServiceError("The actor is not authorized.")
    return persisted


def request_human_escalation(
    *,
    session,
    actor,
    reason_code,
    idempotency_key,
    request_id=None,
    correlation_id=None,
):
    idempotency_key = _required_uuid(idempotency_key, "idempotency key")
    policy = ESCALATION_POLICIES.get(reason_code)
    if policy is None:
        raise EscalationServiceError("A valid escalation reason is required.")
    with transaction.atomic():
        try:
            locked = (
                CallSession.objects.select_for_update()
                .select_related(
                    "schedule__application__candidate__user",
                    "schedule__application__job__company",
                )
                .get(pk=session.pk)
            )
        except (AttributeError, CallSession.DoesNotExist) as error:
            raise EscalationServiceError("The call session is not available.") from error
        persisted_actor = _actor(actor, locked, reason_code)

        existing = AgentEscalation.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            if (
                existing.call_session_id != locked.pk
                or existing.reason_code != reason_code
            ):
                raise EscalationServiceError(
                    "The idempotency key was used for another escalation."
                )
            return existing
        if locked.status in {
            CallSession.Status.COMPLETED,
            CallSession.Status.CANCELLED,
            CallSession.Status.EXPIRED,
        } or (
            locked.status == CallSession.Status.FAILED
            and reason_code != "runtime_failure"
        ):
            raise EscalationServiceError("The call session cannot be escalated.")

        if (
            reason_code == "candidate_requested_human"
            and locked.status == CallSession.Status.ACTIVE
        ):
            locked = transition_call_session(
                session=locked,
                target_status=CallSession.Status.PAUSED,
                actor=persisted_actor,
            )

        escalation = AgentEscalation.objects.create(
            call_session=locked,
            detected_by=None,
            category=policy.category,
            severity=policy.severity,
            description=policy.description,
            reason_code=reason_code,
            idempotency_key=idempotency_key,
            evidence_summary={},
        )
        record_domain_event(
            AuditCommand(
                category=AuditEvent.Category.SECURITY,
                event_type="call_session.escalated",
                outcome=AuditEvent.Outcome.WARNING,
                severity=AuditEvent.Severity.MEDIUM,
                resource_type="agents.AgentEscalation",
                resource_id=escalation.pk,
                actor=persisted_actor,
                request_id=request_id,
                correlation_id=correlation_id,
                metadata={
                    "application_id": locked.schedule.application_id,
                    "call_session_id": locked.pk,
                    "escalation_category": policy.category,
                    "escalation_severity": policy.severity,
                    "reason_code": reason_code,
                },
            )
        )
        return escalation


def record_technical_failure(
    *,
    session,
    failure_code,
    idempotency_key,
    request_id=None,
    correlation_id=None,
):
    idempotency_key = _required_uuid(idempotency_key, "idempotency key")
    with transaction.atomic():
        existing = (
            AgentEscalation.objects.select_related("call_session")
            .filter(idempotency_key=idempotency_key)
            .first()
        )
        if existing is not None:
            if (
                existing.call_session_id != getattr(session, "pk", None)
                or existing.reason_code != "runtime_failure"
                or existing.call_session.failure_code != failure_code
            ):
                raise EscalationServiceError(
                    "The idempotency key was used for another escalation."
                )
            return existing.call_session, existing
        try:
            locked = CallSession.objects.select_for_update().get(pk=session.pk)
            if locked.status == CallSession.Status.FAILED:
                raise EscalationServiceError(
                    "The runtime failure has already been recorded."
                )
            failed = transition_call_session(
                session=locked,
                target_status=CallSession.Status.FAILED,
                actor=None,
                failure_code=failure_code,
                request_id=request_id,
                correlation_id=correlation_id,
            )
            escalation = request_human_escalation(
                session=failed,
                actor=None,
                reason_code="runtime_failure",
                idempotency_key=idempotency_key,
                request_id=request_id,
                correlation_id=correlation_id,
            )
        except (AttributeError, CallSession.DoesNotExist, CallSessionServiceError) as error:
            raise EscalationServiceError(
                "The runtime failure could not be recorded."
            ) from error
        return failed, escalation

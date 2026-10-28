from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from agents.escalation_services import EscalationServiceError, request_human_escalation
from calling.forms import (
    HumanEscalationForm,
    SessionPreparationForm,
    SimulatedAnswerForm,
)
from calling.models import CallSession
from calling.services import (
    CallSessionServiceError,
    get_call_session_for_actor,
    get_simulated_interview_state,
    prepare_simulated_call_session,
    submit_simulated_answer,
    transition_call_session,
)
from candidates.models import CandidateProfile
from interviews.models import InterviewSchedule
from recruitment.models import RecruiterProfile


def _candidate_actor(user):
    try:
        actor = User.objects.get(
            pk=user.pk,
            is_active=True,
            role=User.Role.CANDIDATE,
        )
        candidate = CandidateProfile.objects.get(user=actor)
    except (AttributeError, User.DoesNotExist, CandidateProfile.DoesNotExist) as error:
        raise PermissionDenied from error
    return actor, candidate


def _review_actor(user):
    try:
        actor = User.objects.get(pk=user.pk, is_active=True)
    except (AttributeError, User.DoesNotExist) as error:
        raise PermissionDenied from error
    if actor.is_superuser or actor.role == User.Role.ADMIN:
        return actor, None
    if actor.role != User.Role.RECRUITER:
        raise PermissionDenied
    try:
        recruiter = RecruiterProfile.objects.get(
            user=actor,
            is_verified=True,
            can_review_candidates=True,
        )
    except RecruiterProfile.DoesNotExist as error:
        raise PermissionDenied from error
    return actor, recruiter


def _candidate_session(session_id, actor):
    session = get_object_or_404(CallSession, pk=session_id)
    try:
        return get_call_session_for_actor(session=session, actor=actor)
    except CallSessionServiceError as error:
        raise Http404 from error


@login_required
def candidate_session_list(request):
    actor, candidate = _candidate_actor(request.user)
    schedules = (
        InterviewSchedule.objects.filter(
            application__candidate=candidate,
            status=InterviewSchedule.Status.CONFIRMED,
            is_current=True,
        )
        .select_related("application__job")
        .prefetch_related("call_sessions")
    )
    schedule_entries = [
        {"schedule": schedule, "form": SessionPreparationForm()}
        for schedule in schedules
    ]
    return render(
        request,
        "calling/candidate_session_list.html",
        {
            "actor": actor,
            "schedule_entries": schedule_entries,
        },
    )


@login_required
@require_POST
def prepare_session(request, schedule_id):
    actor, candidate = _candidate_actor(request.user)
    schedule = get_object_or_404(
        InterviewSchedule.objects.select_related("application__candidate"),
        pk=schedule_id,
        application__candidate=candidate,
    )
    form = SessionPreparationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "The interview session could not be prepared.")
        return redirect("calling:candidate_session_list")
    try:
        session = prepare_simulated_call_session(
            schedule=schedule,
            actor=actor,
            idempotency_key=form.cleaned_data["idempotency_key"],
            policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
        )
    except CallSessionServiceError:
        messages.error(request, "The interview session could not be prepared.")
        return redirect("calling:candidate_session_list")
    return redirect("calling:candidate_session_detail", session_id=session.pk)


@login_required
def candidate_session_detail(request, session_id):
    actor, _candidate = _candidate_actor(request.user)
    session = _candidate_session(session_id, actor)
    state = get_simulated_interview_state(session=session, actor=actor)
    return render(
        request,
        "calling/candidate_session_detail.html",
        {
            "state": state,
            "answer_form": SimulatedAnswerForm(),
            "escalation_form": HumanEscalationForm(),
        },
    )


@login_required
@require_POST
def start_or_resume_session(request, session_id):
    actor, _candidate = _candidate_actor(request.user)
    session = _candidate_session(session_id, actor)
    try:
        transition_call_session(
            session=session,
            target_status=CallSession.Status.ACTIVE,
            actor=actor,
            policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
        )
    except CallSessionServiceError:
        messages.error(request, "The interview session could not be started.")
    return redirect("calling:candidate_session_detail", session_id=session.pk)


@login_required
@require_POST
def pause_session(request, session_id):
    actor, _candidate = _candidate_actor(request.user)
    session = _candidate_session(session_id, actor)
    try:
        transition_call_session(
            session=session,
            target_status=CallSession.Status.PAUSED,
            actor=actor,
        )
    except CallSessionServiceError:
        messages.error(request, "The interview session could not be paused.")
    return redirect("calling:candidate_session_detail", session_id=session.pk)


@login_required
@require_POST
def submit_answer(request, session_id):
    actor, _candidate = _candidate_actor(request.user)
    session = _candidate_session(session_id, actor)
    form = SimulatedAnswerForm(request.POST)
    if not form.is_valid():
        messages.error(request, "A valid answer is required.")
        return redirect("calling:candidate_session_detail", session_id=session.pk)
    try:
        submit_simulated_answer(
            session=session,
            actor=actor,
            answer_text=form.cleaned_data["answer_text"],
            idempotency_key=form.cleaned_data["idempotency_key"],
            policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
        )
    except CallSessionServiceError:
        messages.error(request, "The answer could not be submitted.")
    return redirect("calling:candidate_session_detail", session_id=session.pk)


@login_required
@require_POST
def cancel_candidate_session(request, session_id):
    actor, _candidate = _candidate_actor(request.user)
    session = _candidate_session(session_id, actor)
    try:
        transition_call_session(
            session=session,
            target_status=CallSession.Status.CANCELLED,
            actor=actor,
            reason_code="candidate_cancelled",
        )
    except CallSessionServiceError:
        messages.error(request, "The interview session could not be cancelled.")
    return redirect("calling:candidate_session_detail", session_id=session.pk)


@login_required
@require_POST
def request_human_review(request, session_id):
    actor, _candidate = _candidate_actor(request.user)
    session = _candidate_session(session_id, actor)
    form = HumanEscalationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Human assistance could not be requested.")
        return redirect("calling:candidate_session_detail", session_id=session.pk)
    try:
        request_human_escalation(
            session=session,
            actor=actor,
            reason_code="candidate_requested_human",
            idempotency_key=form.cleaned_data["idempotency_key"],
        )
        messages.success(request, "Human assistance has been requested.")
    except EscalationServiceError:
        messages.error(request, "Human assistance could not be requested.")
    return redirect("calling:candidate_session_detail", session_id=session.pk)


@login_required
def recruiter_session_list(request):
    actor, recruiter = _review_actor(request.user)
    sessions = CallSession.objects.select_related(
        "schedule__application__candidate__user",
        "schedule__application__job__company",
    )
    if recruiter is not None:
        sessions = sessions.filter(
            schedule__application__job__company=recruiter.company
        )
    return render(
        request,
        "calling/recruiter_session_list.html",
        {"actor": actor, "sessions": sessions},
    )


@login_required
def recruiter_session_detail(request, session_id):
    actor, _recruiter = _review_actor(request.user)
    session = get_object_or_404(CallSession, pk=session_id)
    try:
        state = get_simulated_interview_state(session=session, actor=actor)
    except CallSessionServiceError as error:
        raise Http404 from error
    return render(
        request,
        "calling/recruiter_session_detail.html",
        {"state": state},
    )


@login_required
@require_POST
def cancel_review_session(request, session_id):
    actor, _recruiter = _review_actor(request.user)
    session = get_object_or_404(CallSession, pk=session_id)
    try:
        session = get_call_session_for_actor(session=session, actor=actor)
        transition_call_session(
            session=session,
            target_status=CallSession.Status.CANCELLED,
            actor=actor,
            reason_code="reviewer_cancelled",
        )
    except CallSessionServiceError as error:
        raise Http404 from error
    return redirect("calling:recruiter_session_detail", session_id=session.pk)

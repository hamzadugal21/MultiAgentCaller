from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from agents.escalation_services import EscalationServiceError, request_human_escalation
from auditlog.consent_services import (
    has_effective_application_ai_interview_consent,
    has_effective_general_ai_processing_consent,
)
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
from interviews.models import InterviewRescheduleRequest, InterviewSchedule
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
    if recruiter is None or not recruiter.company.is_active:
        raise PermissionDenied
    now = timezone.now()
    schedules = list(
        InterviewSchedule.objects.filter(
            application__job__company=recruiter.company,
            is_current=True,
        )
        .select_related(
            "application__candidate__user",
            "application__job__company",
        )
        .prefetch_related("call_sessions")
        .order_by("scheduled_start", "id")
    )
    upcoming_entries = []
    for schedule in schedules:
        if (
            schedule.status
            not in {
                InterviewSchedule.Status.PENDING,
                InterviewSchedule.Status.CONFIRMED,
            }
            or schedule.scheduled_end <= now
        ):
            continue
        try:
            display_timezone = ZoneInfo(schedule.timezone)
        except (ZoneInfoNotFoundError, TypeError, ValueError):
            display_timezone = timezone.get_default_timezone()
        candidate_user = schedule.application.candidate.user
        candidate_name = candidate_user.get_full_name().strip() or "Candidate"
        sessions = list(schedule.call_sessions.all())
        upcoming_entries.append(
            {
                "candidate_name": candidate_name,
                "display_start": timezone.localtime(
                    schedule.scheduled_start,
                    display_timezone,
                ),
                "schedule": schedule,
                "session": sessions[0] if sessions else None,
                "status_class": schedule.status,
                "status_label": (
                    "Awaiting confirmation"
                    if schedule.status == InterviewSchedule.Status.PENDING
                    else schedule.get_status_display()
                ),
            }
        )
    selected_entry = None
    selected_schedule_id = request.GET.get("schedule")
    if selected_schedule_id:
        selected_entry = next(
            (
                entry
                for entry in upcoming_entries
                if str(entry["schedule"].pk) == selected_schedule_id
            ),
            None,
        )
        if selected_entry is None:
            raise Http404
    elif upcoming_entries:
        selected_entry = upcoming_entries[0]

    pending_reschedules = list(
        InterviewRescheduleRequest.objects.filter(
            schedule__application__job__company=recruiter.company,
            schedule__is_current=True,
            status=InterviewRescheduleRequest.Status.PENDING,
        )
        .select_related(
            "schedule__application__candidate__user",
            "schedule__application__job",
        )
        .order_by("created_at", "id")
    )
    selected_context = {}
    if selected_entry is not None:
        selected_schedule = selected_entry["schedule"]
        application = selected_schedule.application
        policy_version = settings.CURRENT_AI_CONSENT_POLICY_VERSION
        selected_context = {
            "general_consent_active": has_effective_general_ai_processing_consent(
                candidate=application.candidate,
                policy_version=policy_version,
            ),
            "interview_consent_active": has_effective_application_ai_interview_consent(
                application=application,
                policy_version=policy_version,
            ),
            "selected_entry": selected_entry,
        }
    display_name = actor.get_full_name().strip() or actor.email
    initials = "".join(
        part[0].upper() for part in (actor.first_name, actor.last_name) if part
    )[:2] or actor.email[0].upper()
    return render(
        request,
        "calling/recruiter_session_list.html",
        {
            "actor": actor,
            "awaiting_confirmation_count": sum(
                entry["schedule"].status == InterviewSchedule.Status.PENDING
                for entry in upcoming_entries
            ),
            "display_name": display_name,
            "initials": initials,
            "pending_reschedules": pending_reschedules,
            "recruiter": recruiter,
            "reschedule_request_count": len(pending_reschedules),
            "upcoming_entries": upcoming_entries,
            "upcoming_interview_count": len(upcoming_entries),
            **selected_context,
        },
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

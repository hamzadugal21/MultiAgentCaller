
import logging
import re
import uuid
from datetime import datetime, timedelta

from ai_system.agents.gateway import AgentRequest, DetachedAgentGateway
from ai_system.framework.agents import AgentName, BoundedAgentRunner
from ai_system.rag.service import RetrievalPrincipal
from ai_system.runtime.gemini import GeminiRuntime
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
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
from calling.qa_voice import QaVoiceError, synthesize_qa_question
from calling.services import (
    CallSessionServiceError,
    get_call_session_for_actor,
    get_simulated_interview_state,
    prepare_simulated_call_session,
    submit_simulated_answer,
    transition_call_session,
)
from calling.transcription_services import (
    TranscriptionError,
    transcribe_candidate_audio,
)
from candidates.models import CandidateProfile
from interviews.models import InterviewRescheduleRequest, InterviewSchedule
from interviews.scheduling_services import (
    SchedulingServiceError,
    create_confirmed_interview,
)
from recruitment.application_services import recruiter_applications
from recruitment.models import JobApplication, RecruiterProfile

logger = logging.getLogger(__name__)
_INTERVAL_PATTERN = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$")


def _parse_bulk_interval(*, date_text, raw):
    match = _INTERVAL_PATTERN.fullmatch(raw or "")
    if match is None:
        raise ValueError("Use intervals in HH:MM-HH:MM format, for example 09:00-11:00.")
    start_hour, start_minute, end_hour, end_minute = (int(value) for value in match.groups())
    if start_hour > 23 or end_hour > 23 or start_minute > 59 or end_minute > 59:
        raise ValueError("Availability times must use valid 24-hour clock values.")
    try:
        start = datetime.strptime(f"{date_text} {start_hour:02d}:{start_minute:02d}", "%Y-%m-%d %H:%M")
        end = datetime.strptime(f"{date_text} {end_hour:02d}:{end_minute:02d}", "%Y-%m-%d %H:%M")
    except ValueError as error:
        raise ValueError("Enter a valid interview date and availability time.") from error
    return start, end


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


def _speech_feature_enabled():
    """Keep optional local speech out of text-only production requests."""
    return bool(getattr(settings, "SPEECH_FEATURE_ENABLED", False))


@login_required
def candidate_session_list(request):
    actor, candidate = _candidate_actor(request.user)
    schedules = (
        InterviewSchedule.objects.filter(
            application__candidate=candidate,
            is_current=True,
        )
        .select_related("application__job")
        .prefetch_related("call_sessions")
    )

    schedule_entries = []
    for schedule in schedules:
        session = schedule.call_sessions.first()
        schedule_entries.append({"schedule": schedule, "session": session, "form": SessionPreparationForm(), "local_start": timezone.localtime(schedule.scheduled_start), "local_end": timezone.localtime(schedule.scheduled_end), "duration_minutes": max(1, round((schedule.scheduled_end - schedule.scheduled_start).total_seconds() / 60))})
    upcoming_statuses = {InterviewSchedule.Status.PENDING, InterviewSchedule.Status.CONFIRMED}
    history_statuses = {InterviewSchedule.Status.COMPLETED, InterviewSchedule.Status.CANCELLED, InterviewSchedule.Status.EXPIRED}
    return render(request, "calling/candidate_session_list.html", {"actor": actor, "schedule_entries": schedule_entries, "upcoming_entries": [entry for entry in schedule_entries if entry["schedule"].status in upcoming_statuses], "pending_entries": [entry for entry in schedule_entries if entry["schedule"].status == InterviewSchedule.Status.PENDING], "history_entries": [entry for entry in schedule_entries if entry["schedule"].status in history_statuses or entry["schedule"].scheduled_end <= timezone.now()], "upcoming_count": sum(entry["schedule"].status in upcoming_statuses for entry in schedule_entries), "pending_count": sum(entry["schedule"].status == InterviewSchedule.Status.PENDING for entry in schedule_entries), "completed_count": sum(entry["schedule"].status == InterviewSchedule.Status.COMPLETED for entry in schedule_entries), "reschedule_count": InterviewRescheduleRequest.objects.filter(schedule__application__candidate=candidate, status=InterviewRescheduleRequest.Status.PENDING).count()})


@login_required
def bulk_schedule_view(request):
    actor, recruiter = _review_actor(request.user)
    if recruiter is None:
        raise PermissionDenied
    applications = recruiter_applications(actor).exclude(
        status__in=(JobApplication.Status.REJECTED, JobApplication.Status.WITHDRAWN)
    ).select_related("candidate__user", "job")
    result = request.session.get("bulk_schedule_preview")
    if request.method == "POST":
        if request.POST.get("action") == "confirm":
            if not result or not result.get("allocations"):
                messages.error(request, "This schedule preview is no longer available. Generate it again.")
                return redirect("calling:bulk_schedule")
            if result.get("ai_fallback"):
                messages.error(request, "AI validation was unavailable for this preview. Generate a new schedule before confirming.")
                return redirect("calling:bulk_schedule")
            try:
                confirmed = 0
                allowed = applications.filter(pk__in=[item["application_id"] for item in result["allocations"]])
                for item in result["allocations"]:
                    application = allowed.get(pk=item["application_id"])
                    create_confirmed_interview(application=application, actor=actor, scheduled_start=datetime.fromisoformat(item["start_iso"]), scheduled_end=datetime.fromisoformat(item["end_iso"]), timezone_name=settings.TIME_ZONE, policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION, idempotency_key=uuid.UUID(item["idempotency_key"]))
                    confirmed += 1
                request.session.pop("bulk_schedule_preview", None)
                messages.success(request, f"{confirmed} interview(s) scheduled in the candidate portal. No email was sent.")
                return redirect("calling:recruiter_session_list")
            except (KeyError, ValueError, JobApplication.DoesNotExist, SchedulingServiceError):
                messages.error(request, "The schedule changed or is no longer valid. Generate a new preview.")
                request.session.pop("bulk_schedule_preview", None)
                return redirect("calling:bulk_schedule")
        try:
            selected = list(applications.filter(pk__in=request.POST.getlist("application_ids")))
            if not selected:
                raise ValueError("Select at least one eligible candidate.")
            date_text = request.POST.get("date", "")
            duration = int(request.POST.get("duration", "30"))
            break_minutes = int(request.POST.get("break_minutes", "0"))
            intervals = []
            for raw in request.POST.getlist("intervals"):
                intervals.append(_parse_bulk_interval(date_text=date_text, raw=raw))
            if duration not in {15, 30, 45, 60}:
                raise ValueError("Choose a valid interview duration.")
            if break_minutes not in {0, 5, 10, 15}:
                raise ValueError("Choose a valid break duration.")
            if not intervals:
                raise ValueError("Add at least one availability interval.")
            local_zone = timezone.get_current_timezone()
            aware_intervals = [(timezone.make_aware(start, local_zone), timezone.make_aware(end, local_zone)) for start, end in intervals]
            aware_intervals.sort()
            if any(start <= timezone.now() for start, _ in aware_intervals):
                raise ValueError("Interview date and availability must be in the future.")
            if any(start >= end for start, end in aware_intervals):
                raise ValueError("Each availability interval must end after it starts.")
            if any(current_end > next_start for (_, current_end), (next_start, _) in zip(aware_intervals, aware_intervals[1:], strict=False)):
                raise ValueError("Availability intervals overlap.")
            if any(not has_effective_application_ai_interview_consent(application=application, policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION) for application in selected):
                raise ValueError("Candidate consent is missing for one or more selected applications.")
            if InterviewSchedule.objects.filter(application_id__in=[application.pk for application in selected], is_current=True).exists():
                raise ValueError("One or more selected candidates already have a current interview.")
            slots = []
            for start, end in aware_intervals:
                cursor = start
                while cursor + timedelta(minutes=duration) <= end:
                    slots.append((cursor, cursor + timedelta(minutes=duration)))
                    cursor += timedelta(minutes=duration + break_minutes)
            existing = set(InterviewSchedule.objects.filter(scheduled_by=actor, is_current=True, scheduled_start__lt=max((end for _, end in aware_intervals), default=timezone.now()), scheduled_end__gt=min((start for start, _ in aware_intervals), default=timezone.now())).values_list("scheduled_start", "scheduled_end"))
            allocations = []
            for application, (start, end) in zip(selected, slots, strict=False):
                if start <= timezone.now() or any(start < old_end and end > old_start for old_start, old_end in existing):
                    continue
                allocations.append({"application_id": str(application.pk), "candidate": application.candidate.user.get_full_name() or "Candidate", "job": application.job.title, "start": timezone.localtime(start).strftime("%d %b %Y %H:%M"), "end": timezone.localtime(end).strftime("%H:%M"), "start_iso": start.isoformat(), "end_iso": end.isoformat()})
            if not allocations:
                raise ValueError("No available slots match the requested duration and breaks.")
            runtime = GeminiRuntime()
            try:
                decision = DetachedAgentGateway(runner=BoundedAgentRunner(runtime, timeout_seconds=25)).propose(AgentRequest(agent_name=AgentName.SCHEDULING, principal=RetrievalPrincipal(user_id=str(actor.pk), role="recruiter", company_id=str(recruiter.company_id), ai_processing_consented=True), context={"authorized_slots": [item["start_iso"] for item in allocations]}))
            finally:
                runtime.stop()
            result = {"allocations": [dict(item, idempotency_key=str(uuid.uuid4())) for item in allocations], "unscheduled": len(selected) - len(allocations), "duration": duration, "break_minutes": break_minutes, "ai_message": decision.proposal.message, "ai_fallback": bool(decision.proposal.fallback_code), "configuration": {"date": date_text, "application_ids": [str(application.pk) for application in selected], "intervals": request.POST.getlist("intervals"), "duration": str(duration), "break_minutes": str(break_minutes)}}
            request.session["bulk_schedule_preview"] = result
        except (ValueError, SchedulingServiceError) as error:
            messages.error(request, str(error))
        except Exception:
            logger.exception("Bulk scheduling preview failed")
            messages.error(request, "The scheduling preview is temporarily unavailable. No interviews were created.")
    selected_ids = set((result or {}).get("configuration", {}).get("application_ids", []))
    application_entries = [{"application": application, "selected": str(application.pk) in selected_ids} for application in applications]
    return render(request, "calling/bulk_schedule.html", {"applications": application_entries, "preview": result})
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
    except CallSessionServiceError as error:
        messages.error(request, str(error))
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
            "speech_feature_enabled": _speech_feature_enabled(),
            "whisper_max_audio_seconds": settings.WHISPER_MAX_AUDIO_SECONDS,
            "piper_playback_enabled": (
                _speech_feature_enabled()
                and
                settings.SETTINGS_MODULE == "config.settings_qa"
                and getattr(settings, "QA_BROWSER_VOICE_ENABLED", False)
            ),
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
def transcribe_answer(request, session_id):
    actor, _candidate = _candidate_actor(request.user)
    session = _candidate_session(session_id, actor)
    if not _speech_feature_enabled():
        return JsonResponse({"status": "error", "code": "speech_disabled"}, status=404)
    if set(request.FILES) != {"audio"}:
        return JsonResponse({"status": "error", "code": "audio_invalid"}, status=400)
    try:
        result = transcribe_candidate_audio(
            session=session,
            actor=actor,
            uploaded_audio=request.FILES["audio"],
        )
    except TranscriptionError as error:
        status = 429 if error.code == "transcription_rate_limited" else 400
        return JsonResponse({"status": "error", "code": error.code}, status=status)
    return JsonResponse(
        {
            "status": "success",
            "transcript": result.text,
            "vad_segments": result.vad_segments,
        },
        json_dumps_params={"ensure_ascii": True},
    )


@login_required
@require_POST
def speak_question(request, session_id):
    actor, _candidate = _candidate_actor(request.user)
    session = _candidate_session(session_id, actor)
    if not _speech_feature_enabled():
        return JsonResponse({"status": "error", "code": "speech_disabled"}, status=404)
    try:
        audio = synthesize_qa_question(session=session, actor=actor)
    except QaVoiceError as error:
        status = 404 if error.code == "qa_voice_disabled" else 503
        return JsonResponse({"status": "error", "code": error.code}, status=status)
    response = HttpResponse(audio, content_type="audio/wav")
    response["Cache-Control"] = "no-store"
    return response


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
        candidate_user = schedule.application.candidate.user
        candidate_name = candidate_user.get_full_name().strip() or "Candidate"
        sessions = list(schedule.call_sessions.all())
        upcoming_entries.append(
            {
                "candidate_name": candidate_name,
                "display_start": timezone.localtime(
                    schedule.scheduled_start,
                    timezone.get_default_timezone(),
                ),
                "schedule": schedule,
                "session": sessions[0] if sessions else None,
                "status_class": schedule.status,
                "status_label": (
                    "Pending activation"
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

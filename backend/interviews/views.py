import uuid

from ai_system.agents.gateway import AgentRequest, DetachedAgentGateway
from ai_system.framework.agents import AgentName, BoundedAgentRunner
from ai_system.rag.service import RetrievalPrincipal
from ai_system.runtime.gemini import GeminiRuntime
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.views import role_required
from interviews.evaluation_forms import HumanEvaluationForm
from interviews.evaluation_services import (
    EvaluationServiceError,
    finalize_human_evaluation,
    save_human_evaluation,
    start_human_evaluation,
)
from interviews.models import (
    CandidateEvaluation,
    InterviewRescheduleRequest,
    InterviewSchedule,
)
from interviews.scheduling_services import (
    SchedulingServiceError,
    activate_pending_interview,
    cancel_interview,
    create_confirmed_interview,
    expire_interview_invitation,
    request_interview_reschedule,
    review_reschedule_request,
)
from recruitment.application_services import (
    ApplicationServiceError,
    recruiter_applications,
)
from recruitment.forms import InterviewInvitationForm, InterviewRescheduleForm


def _recruiter_application(request, application_id):
    try:
        return get_object_or_404(
            recruiter_applications(request.user), pk=application_id
        )
    except ApplicationServiceError as error:
        raise PermissionDenied from error


def _recruiter_evaluation(request, evaluation_id):
    try:
        allowed_applications = recruiter_applications(request.user).values("pk")
    except ApplicationServiceError as error:
        raise PermissionDenied from error
    return get_object_or_404(
        CandidateEvaluation.objects.select_related(
            "application__candidate__user",
            "application__job__company",
            "rubric",
            "source_session",
            "reviewed_by",
        ).prefetch_related("rubric__criteria", "criterion_scores__criterion"),
        pk=evaluation_id,
        application_id__in=allowed_applications,
    )


@require_POST
@role_required(User.Role.RECRUITER)
def evaluation_start_view(request, application_id):
    application = _recruiter_application(request, application_id)
    try:
        evaluation = start_human_evaluation(
            application=application,
            actor=request.user,
        )
    except EvaluationServiceError:
        messages.error(request, "The evaluation review cannot be started.")
        return redirect(
            "recruitment:application_detail",
            application_id=application.pk,
        )
    return redirect("interviews:evaluation_review", evaluation_id=evaluation.pk)


@role_required(User.Role.RECRUITER)
def evaluation_review_view(request, evaluation_id):
    evaluation = _recruiter_evaluation(request, evaluation_id)
    form = HumanEvaluationForm(
        request.POST or None,
        evaluation=evaluation,
    )
    if request.method == "POST" and not evaluation.is_final and form.is_valid():
        action = request.POST.get("action")
        try:
            with transaction.atomic():
                evaluation = save_human_evaluation(
                    evaluation=evaluation,
                    actor=request.user,
                    criterion_reviews=form.criterion_reviews(),
                    summary=form.cleaned_data["summary"],
                    reviewer_notes=form.cleaned_data["reviewer_notes"],
                )
                if action == "finalize":
                    evaluation = finalize_human_evaluation(
                        evaluation=evaluation,
                        actor=request.user,
                        review_outcome=form.cleaned_data["review_outcome"],
                        reviewer_notes=form.cleaned_data["reviewer_notes"],
                    )
                elif action != "save":
                    raise EvaluationServiceError("The review action is not valid.")
        except EvaluationServiceError as error:
            form.add_error(None, str(error))
        else:
            messages.success(
                request,
                "The human review was finalized."
                if evaluation.is_final
                else "The evaluation draft was saved.",
            )
            return redirect(
                "interviews:evaluation_review",
                evaluation_id=evaluation.pk,
            )

    reviewer = request.user.recruiter_profile
    candidate_user = evaluation.application.candidate.user
    candidate_name = candidate_user.get_full_name().strip() or "Candidate"
    display_name = request.user.get_full_name().strip() or request.user.email
    initials = "".join(
        part[0].upper()
        for part in (request.user.first_name, request.user.last_name)
        if part
    )[:2] or request.user.email[0].upper()
    criterion_fields = []
    if not evaluation.is_final:
        for criterion in evaluation.rubric.criteria.all():
            prefix = f"criterion_{criterion.pk}"
            criterion_fields.append(
                {
                    "criterion": criterion,
                    "confidence": form[f"{prefix}_confidence"],
                    "evidence": form[f"{prefix}_evidence"],
                    "explanation": form[f"{prefix}_explanation"],
                    "score": form[f"{prefix}_score"],
                }
            )
    return render(
        request,
        "interviews/evaluation_review.html",
        {
            "candidate_name": candidate_name,
            "criterion_fields": criterion_fields,
            "display_name": display_name,
            "evaluation": evaluation,
            "form": form,
            "initials": initials,
            "recruiter": reviewer,
        },
    )


@role_required(User.Role.RECRUITER)
def invitation_create_view(request, application_id):
    application = _recruiter_application(request, application_id)
    form = InterviewInvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if request.POST.get("action") == "check_ai":
            runtime = GeminiRuntime()
            try:
                decision = DetachedAgentGateway(
                    runner=BoundedAgentRunner(runtime, timeout_seconds=25)
                ).propose(AgentRequest(
                    agent_name=AgentName.SCHEDULING,
                    principal=RetrievalPrincipal(user_id=str(request.user.pk), role="recruiter", company_id=str(application.job.company_id), ai_processing_consented=True),
                    context={"authorized_slots": [form.cleaned_data["scheduled_start"].isoformat()]},
                ))
                if decision.proposal.fallback_code:
                    form.add_error(None, "AI scheduling validation is unavailable; no schedule was created.")
                else:
                    form.add_error(None, f"AI availability check: {decision.proposal.message}")
            except Exception:
                form.add_error(None, "AI scheduling validation is unavailable; no schedule was created.")
            finally:
                runtime.stop()
        elif request.POST.get("action") != "confirm_schedule":
            form.add_error(None, "Confirm the schedule action before creating an interview.")
        else:
            try:
                create_confirmed_interview(
                    application=application,
                    actor=request.user,
                    scheduled_start=form.cleaned_data["scheduled_start"],
                    scheduled_end=form.cleaned_data["scheduled_end"],
                    timezone_name=settings.TIME_ZONE,
                    policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
                    idempotency_key=uuid.uuid4(),
                )
            except SchedulingServiceError as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, "The interview was scheduled and is available in the candidate portal.")
                return redirect("recruitment:application_detail", application_id=application.pk)
    return render(
        request,
        "interviews/invitation_form.html",
        {"form": form, "application": application},
    )


@require_POST
@role_required(User.Role.RECRUITER)
def pending_activate_view(request, schedule_id):
    try:
        applications = recruiter_applications(request.user)
    except ApplicationServiceError as error:
        raise PermissionDenied from error
    schedule = get_object_or_404(
        InterviewSchedule, pk=schedule_id, application__in=applications
    )
    try:
        activate_pending_interview(
            schedule=schedule,
            actor=request.user,
            policy_version=settings.CURRENT_AI_CONSENT_POLICY_VERSION,
        )
    except SchedulingServiceError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "The interview is available in the candidate portal.")
    return redirect("recruitment:application_detail", application_id=schedule.application_id)


@role_required(User.Role.CANDIDATE)
def reschedule_request_view(request, schedule_id):
    schedule = get_object_or_404(
        InterviewSchedule.objects.select_related("application__candidate"),
        pk=schedule_id,
        application__candidate__user=request.user,
        is_current=True,
    )
    form = InterviewRescheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            request_interview_reschedule(
                schedule=schedule,
                actor=request.user,
                proposed_start=form.cleaned_data["scheduled_start"],
                proposed_end=form.cleaned_data["scheduled_end"],
                timezone_name=settings.TIME_ZONE,
                reason=form.cleaned_data["reason"],
            )
        except SchedulingServiceError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, "Your reschedule request was submitted.")
            return redirect(
                "recruitment:application_detail",
                application_id=schedule.application_id,
            )
    return render(
        request,
        "interviews/reschedule_form.html",
        {"form": form, "schedule": schedule},
    )


@require_POST
@role_required(User.Role.RECRUITER)
def reschedule_review_view(request, request_id):
    reschedule = get_object_or_404(InterviewRescheduleRequest, pk=request_id)
    application_id = reschedule.schedule.application_id
    approve = request.POST.get("decision") == "approve"
    try:
        review_reschedule_request(
            reschedule_request=reschedule,
            actor=request.user,
            approve=approve,
            invitation_idempotency_key=uuid.uuid4() if approve else None,
        )
    except SchedulingServiceError:
        messages.error(request, "The reschedule request could not be reviewed.")
    else:
        messages.success(request, "The reschedule request was reviewed.")
    return redirect(
        "recruitment:application_detail",
        application_id=application_id,
    )


@require_POST
@role_required(User.Role.RECRUITER)
def schedule_cancel_view(request, schedule_id):
    schedule = get_object_or_404(InterviewSchedule, pk=schedule_id)
    try:
        cancel_interview(
            schedule=schedule,
            actor=request.user,
            reason_code=request.POST.get("reason_code", "recruiter_cancelled"),
        )
    except SchedulingServiceError:
        messages.error(request, "The interview could not be cancelled.")
    return redirect(
        "recruitment:application_detail", application_id=schedule.application_id
    )


@require_POST
@role_required(User.Role.RECRUITER)
def schedule_expire_view(request, schedule_id):
    schedule = get_object_or_404(InterviewSchedule, pk=schedule_id)
    try:
        expire_interview_invitation(schedule=schedule, actor=request.user)
    except SchedulingServiceError:
        messages.error(request, "The invitation is not yet eligible for expiration.")
    return redirect(
        "recruitment:application_detail", application_id=schedule.application_id
    )
